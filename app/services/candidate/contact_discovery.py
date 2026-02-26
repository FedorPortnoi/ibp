"""
Contact Discovery Service (Stage 4)
====================================
Extracts phones and emails from VK/Telegram profiles, business records,
guesses emails from usernames, queries breach databases, verifies
with Holehe, runs forgot-password oracle, and mines Russian marketplaces.

Discovery chain (order matters — each step feeds the next):
 1. Extract from VK profiles (API)
 2. Extract from Telegram profiles (parse existing data)
 3. Extract from business/FSSP records
 4. Guess emails from usernames
 5. LeakDB name lookup (local breach data)
 6. Breach API enrichment (HudsonRock, LeakCheck, ProxyNova COMB)
 7. LeakDB cross-reference (snowball: phone→email, email→phone)
 8. Forgot-password oracle (VK, Mail.ru, Yandex, OK, Gosuslugi, TG, Avito, Sberbank)
 9. Marketplace mining (Avito, Youla, CIAN, Auto.ru, Yandex, VK Market)
10. Verify emails with Holehe
11. Deduplicate, merge sources, and score
"""

import logging
import os
import re
import time
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

from app.utils.phone import normalize_phone

logger = logging.getLogger(__name__)

# Regex patterns for contact extraction
# Handles: +7 (916) 123-45-67, 8-916-123-45-67, +7 916 1234567, +79161234567
PHONE_PATTERN = re.compile(
    r'(?:\+7|8)[\s\-]*\(?\d{3}\)?[\s\-]*\d{3}[\s\-]?\d{2}[\s\-]?\d{2}'
)
EMAIL_PATTERN = re.compile(
    r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
)

# Domains for email guessing
GUESS_DOMAINS = [
    'gmail.com', 'mail.ru', 'yandex.ru',
    'inbox.ru', 'bk.ru', 'list.ru', 'rambler.ru',
    'outlook.com', 'hotmail.com', 'internet.ru', 'icloud.com',
]
NAME_GUESS_DOMAINS = ['gmail.com', 'mail.ru', 'yandex.ru']

# Max emails to verify with Holehe (expensive operation)
MAX_HOLEHE_EMAILS = 20

# VK API version
VK_API_VERSION = '5.131'

# ── Confidence Scores ─────────────────────────────────────────────
# Numeric confidence scores by source (Phase 5 overhaul)
CONFIDENCE_SCORES = {
    'input':                    0.99,  # user typed it
    'vk_profile_contacts':      0.95,  # VK profile contacts field (explicit)
    'marketplace':              0.90,  # person posted it on Avito/Youla/etc
    'getcontact_confirmed':     0.90,  # GetContact confirmed + named
    'forgot_password_multi':    0.90,  # 2+ services confirm via password oracle
    'vk_wall_by_subject':       0.85,  # VK wall post by the subject themselves
    'telegram':                 0.85,  # Telegram profile data
    'breach_telco':             0.82,  # breach data (telco/GetContact DB)
    'forgot_password_single':   0.78,  # 1 service confirms via password oracle
    'holehe_verified':          0.80,  # Holehe confirms email exists
    'vk_wall_by_others':        0.70,  # VK wall post comment by others
    'leak_db':                  0.65,  # local leak database
    'breach_api':               0.60,  # free breach API (HudsonRock, LeakCheck)
    'egrul':                    0.50,  # business registry (company phone, not personal)
    'fssp':                     0.45,  # FSSP enforcement records
    'email_guess':              0.40,  # pattern-generated (unverified)
    'leak_db_xref':             0.55,  # cross-referenced from leak DB
}

# Cross-source boost: if same contact found in 3+ independent sources
CROSS_SOURCE_BOOST = 0.15
CROSS_SOURCE_THRESHOLD = 3
MAX_CONFIDENCE = 0.98


def _score_to_label(score: float) -> str:
    """Convert numeric confidence to Russian label for backward compat."""
    if score >= 0.75:
        return 'высокая'
    elif score >= 0.50:
        return 'средняя'
    return 'низкая'


def _label_to_score(label: str) -> float:
    """Convert Russian confidence label to numeric score."""
    return {'высокая': 0.85, 'средняя': 0.60, 'низкая': 0.40}.get(label, 0.40)


@dataclass
class DiscoveredPhone:
    number: str                             # normalized +79161234567
    source: str                             # primary source key
    confidence: str                         # "высокая", "средняя", "низкая" (backward compat)
    profile_name: str                       # which profile it came from
    raw_value: str                          # original before normalization
    confidence_score: float = 0.50          # numeric confidence [0..1]
    sources: List[str] = field(default_factory=list)  # ALL sources that found this

    def to_dict(self):
        d = asdict(self)
        d['confidence_score'] = round(self.confidence_score, 2)
        return d


@dataclass
class DiscoveredEmail:
    email: str                              # normalized lowercase
    source: str                             # primary source key
    confidence: str                         # "высокая", "средняя", "низкая" (backward compat)
    verified: bool                          # True if Holehe confirmed
    profile_name: str                       # which profile/method it came from
    services: List[str] = field(default_factory=list)  # Holehe services found on
    confidence_score: float = 0.50          # numeric confidence [0..1]
    sources: List[str] = field(default_factory=list)  # ALL sources that found this

    def to_dict(self):
        d = asdict(self)
        d['confidence_score'] = round(self.confidence_score, 2)
        return d


def _confidence_rank(confidence: str) -> int:
    return {'высокая': 3, 'средняя': 2, 'низкая': 1}.get(confidence, 0)


def _get_score(source_key: str) -> float:
    """Get numeric confidence for a source key."""
    return CONFIDENCE_SCORES.get(source_key, 0.50)


class ContactDiscoveryService:
    """Discovers phones and emails from existing check data."""

    def __init__(self):
        self.vk_token = os.environ.get('VK_SERVICE_TOKEN') or os.environ.get('VK_TOKEN')
        self.found_phones: List[DiscoveredPhone] = []
        self.found_emails: List[DiscoveredEmail] = []

    def discover(self, check) -> dict:
        """
        Main entry point. Runs all discovery steps in order.

        Args:
            check: CandidateCheck model instance

        Returns:
            {"phones": [...], "emails": [...]} with serialized results
        """
        # Add input contacts first (if provided on the form)
        if check.phone:
            normalized = normalize_phone(check.phone)
            self.found_phones.append(DiscoveredPhone(
                number=normalized,
                source='input',
                confidence='высокая',
                profile_name='Форма ввода',
                raw_value=check.phone,
                confidence_score=_get_score('input'),
                sources=['input'],
            ))

        if check.email:
            self.found_emails.append(DiscoveredEmail(
                email=check.email.lower().strip(),
                source='input',
                confidence='высокая',
                verified=False,
                profile_name='Форма ввода',
                confidence_score=_get_score('input'),
                sources=['input'],
            ))

        social_profiles = check.social_media_profiles or []

        # Step 1: VK profiles
        try:
            self._extract_from_vk(social_profiles)
        except Exception as e:
            logger.warning(f"VK contact extraction error: {e}")

        # Step 2: Telegram profiles
        try:
            self._extract_from_telegram(social_profiles)
        except Exception as e:
            logger.warning(f"Telegram contact extraction error: {e}")

        # Step 3: Business/FSSP records
        try:
            self._extract_from_business(check.business_records or [])
            self._extract_from_fssp(check.fssp_records or [])
        except Exception as e:
            logger.warning(f"Business/FSSP contact extraction error: {e}")

        # Step 4: Email guessing from usernames
        try:
            self._guess_emails(social_profiles, check.full_name)
        except Exception as e:
            logger.warning(f"Email guessing error: {e}")

        # Step 5: LeakDB name lookup
        try:
            self._query_leakdb_by_name(check.full_name)
        except Exception as e:
            logger.warning(f"LeakDB name lookup error: {e}")

        # Step 6: Breach API enrichment
        try:
            self._query_breach_apis(social_profiles)
        except Exception as e:
            logger.warning(f"Breach API query error: {e}")

        # Step 7: LeakDB cross-reference (snowball)
        try:
            self._cross_lookup_leakdb()
        except Exception as e:
            logger.warning(f"LeakDB cross-lookup error: {e}")

        # Step 8: Forgot-password oracle
        try:
            self._run_forgot_password_oracle(check)
        except Exception as e:
            logger.warning(f"Forgot-password oracle error: {e}")

        # Step 9: Marketplace mining
        try:
            self._run_marketplace_scan(check)
        except Exception as e:
            logger.warning(f"Marketplace scan error: {e}")

        # Step 10: Holehe verification
        try:
            self._verify_with_holehe()
        except Exception as e:
            logger.warning(f"Holehe verification error: {e}")

        # Step 11: Deduplicate, merge sources, score
        self._deduplicate_contacts()

        return {
            'phones': [p.to_dict() for p in self.found_phones],
            'emails': [e.to_dict() for e in self.found_emails],
        }

    # ── Step 1: VK Profiles ──────────────────────────────────────────

    def _extract_from_vk(self, social_profiles: list):
        """Extract contacts from VK profiles via API."""
        vk_profiles = [p for p in social_profiles if p.get('platform') == 'vk']
        if not vk_profiles:
            return

        if not self.vk_token:
            logger.warning("No VK token — skipping VK contact extraction")
            return

        for profile in vk_profiles:
            vk_id = self._extract_vk_id(profile)
            if not vk_id:
                continue

            display_name = profile.get('display_name', '')

            try:
                data = self._vk_api_get_contacts(vk_id)
                if not data:
                    continue

                user = data[0] if isinstance(data, list) and data else data

                # Direct phone fields
                for phone_field in ('mobile_phone', 'home_phone'):
                    raw = (user.get(phone_field) or '').strip()
                    if raw and PHONE_PATTERN.search(raw):
                        normalized = normalize_phone(PHONE_PATTERN.search(raw).group())
                        score = _get_score('vk_profile_contacts')
                        self.found_phones.append(DiscoveredPhone(
                            number=normalized,
                            source='vk_profile',
                            confidence=_score_to_label(score),
                            profile_name=display_name,
                            raw_value=raw,
                            confidence_score=score,
                            sources=['vk_profile_contacts'],
                        ))

                # Check site, about, status for phones/emails
                for text_field in ('site', 'about', 'status'):
                    text = (user.get(text_field) or '').strip()
                    if not text:
                        continue

                    for match in PHONE_PATTERN.finditer(text):
                        normalized = normalize_phone(match.group())
                        score = _get_score('vk_wall_by_subject')
                        self.found_phones.append(DiscoveredPhone(
                            number=normalized,
                            source='vk_profile',
                            confidence=_score_to_label(score),
                            profile_name=display_name,
                            raw_value=match.group(),
                            confidence_score=score,
                            sources=['vk_profile'],
                        ))

                    for match in EMAIL_PATTERN.finditer(text):
                        email = match.group().lower()
                        score = _get_score('vk_profile_contacts')
                        self.found_emails.append(DiscoveredEmail(
                            email=email,
                            source='vk_profile',
                            confidence=_score_to_label(score),
                            verified=False,
                            profile_name=display_name,
                            confidence_score=score,
                            sources=['vk_profile'],
                        ))

            except Exception as e:
                logger.warning(f"VK API error for {vk_id}: {e}")

    def _extract_vk_id(self, profile: dict) -> Optional[str]:
        """Extract VK user ID from profile data."""
        # Try direct ID field
        url = profile.get('url', '')
        username = profile.get('username', '')

        # From URL: https://vk.com/id12345 or https://vk.com/username
        if url:
            m = re.search(r'vk\.com/(?:id)?(\w+)', url)
            if m:
                return m.group(1)

        # From username
        if username:
            return username

        return None

    def _vk_api_get_contacts(self, vk_id: str) -> Optional[list]:
        """Call VK API users.get with contact fields."""
        try:
            resp = requests.get(
                'https://api.vk.com/method/users.get',
                params={
                    'user_ids': vk_id,
                    'fields': 'contacts,phone,mobile_phone,home_phone,site,about,status',
                    'access_token': self.vk_token,
                    'v': VK_API_VERSION,
                },
                timeout=10,
            )
            data = resp.json()
            if 'error' in data:
                logger.debug(f"VK API error: {data['error'].get('error_msg', '')}")
                return None
            return data.get('response', [])
        except requests.Timeout:
            logger.warning(f"VK API timeout for {vk_id}")
            return None
        except Exception as e:
            logger.warning(f"VK API request failed for {vk_id}: {e}")
            return None

    # ── Step 2: Telegram Profiles ────────────────────────────────────

    def _extract_from_telegram(self, social_profiles: list):
        """Extract contacts from Telegram profile data (already fetched by Stage 3)."""
        tg_profiles = [p for p in social_profiles if p.get('platform') == 'telegram']

        for profile in tg_profiles:
            display_name = profile.get('display_name', '')

            # Phone from Telethon data
            phone = (profile.get('phone') or '').strip()
            if phone:
                normalized = normalize_phone(phone)
                score = _get_score('telegram')
                self.found_phones.append(DiscoveredPhone(
                    number=normalized,
                    source='telegram',
                    confidence=_score_to_label(score),
                    profile_name=display_name,
                    raw_value=phone,
                    confidence_score=score,
                    sources=['telegram'],
                ))

            # Check bio/about for contacts
            for text_field in ('bio', 'about'):
                text = (profile.get(text_field) or '').strip()
                if not text:
                    continue

                for match in PHONE_PATTERN.finditer(text):
                    normalized = normalize_phone(match.group())
                    score = _get_score('telegram')
                    self.found_phones.append(DiscoveredPhone(
                        number=normalized,
                        source='telegram',
                        confidence=_score_to_label(score),
                        profile_name=display_name,
                        raw_value=match.group(),
                        confidence_score=score,
                        sources=['telegram'],
                    ))

                for match in EMAIL_PATTERN.finditer(text):
                    email = match.group().lower()
                    score = _get_score('telegram')
                    self.found_emails.append(DiscoveredEmail(
                        email=email,
                        source='telegram',
                        confidence=_score_to_label(score),
                        verified=False,
                        profile_name=display_name,
                        confidence_score=score,
                        sources=['telegram'],
                    ))

    # ── Step 3: Business / FSSP Records ──────────────────────────────

    def _extract_from_business(self, business_records: list):
        """Extract contacts from ЕГРЮЛ company records."""
        for biz in business_records:
            company_name = biz.get('name', biz.get('company_name', ''))

            # Company phone
            for phone_field in ('phone', 'contact_phone'):
                raw = (biz.get(phone_field) or '').strip()
                if raw and PHONE_PATTERN.search(raw):
                    normalized = normalize_phone(PHONE_PATTERN.search(raw).group())
                    score = _get_score('egrul')
                    self.found_phones.append(DiscoveredPhone(
                        number=normalized,
                        source='egrul',
                        confidence=_score_to_label(score),
                        profile_name=company_name,
                        raw_value=raw,
                        confidence_score=score,
                        sources=['egrul'],
                    ))

            # Company email
            for email_field in ('email', 'contact_email'):
                raw = (biz.get(email_field) or '').strip()
                if raw and EMAIL_PATTERN.match(raw):
                    score = _get_score('egrul')
                    self.found_emails.append(DiscoveredEmail(
                        email=raw.lower(),
                        source='egrul',
                        confidence=_score_to_label(score),
                        verified=False,
                        profile_name=company_name,
                        confidence_score=score,
                        sources=['egrul'],
                    ))

    def _extract_from_fssp(self, fssp_records: list):
        """Extract contacts from ФССП enforcement records."""
        for proc in fssp_records:
            if proc.get('source') == 'manual':
                continue
            # Some FSSP records may contain contact phones
            for phone_field in ('debtor_phone', 'phone', 'contact_phone'):
                raw = (proc.get(phone_field) or '').strip()
                if raw and PHONE_PATTERN.search(raw):
                    normalized = normalize_phone(PHONE_PATTERN.search(raw).group())
                    score = _get_score('fssp')
                    self.found_phones.append(DiscoveredPhone(
                        number=normalized,
                        source='fssp',
                        confidence=_score_to_label(score),
                        profile_name='ФССП',
                        raw_value=raw,
                        confidence_score=score,
                        sources=['fssp'],
                    ))

    # ── Step 4: Email Guessing ───────────────────────────────────────

    def _guess_emails(self, social_profiles: list, full_name: str):
        """Generate email guesses from usernames and name transliteration."""
        usernames = set()
        for profile in social_profiles:
            username = (profile.get('username') or '').strip()
            if username and len(username) >= 3:
                # Skip default VK IDs like "id123456"
                if not (username.startswith('id') and username[2:].isdigit()):
                    usernames.add(username.lower())

        # Username-based guesses
        for username in usernames:
            clean = re.sub(r'[^a-z0-9._-]', '', username)
            if len(clean) < 3:
                continue
            score = _get_score('email_guess')
            for domain in GUESS_DOMAINS:
                self.found_emails.append(DiscoveredEmail(
                    email=f'{clean}@{domain}',
                    source='email_guess',
                    confidence=_score_to_label(score),
                    verified=False,
                    profile_name=f'@{username}',
                    confidence_score=score,
                    sources=['email_guess'],
                ))

        # Name-based guesses (transliterated)
        if full_name:
            parts = full_name.strip().split()
            if len(parts) >= 2:
                try:
                    from app.services.phase1.transliteration import transliterate_name_part
                    last_variants = transliterate_name_part(parts[0], max_variants=2)
                    first_variants = transliterate_name_part(parts[1], max_variants=2)

                    guess_score = _get_score('email_guess')
                    for last_lat in last_variants:
                        for first_lat in first_variants:
                            last_clean = re.sub(r"[^a-z]", '', last_lat.lower())
                            first_clean = re.sub(r"[^a-z]", '', first_lat.lower())
                            if not last_clean or not first_clean:
                                continue
                            for domain in NAME_GUESS_DOMAINS:
                                for pattern in (
                                    f'{first_clean}.{last_clean}',
                                    f'{last_clean}.{first_clean}',
                                    f'{first_clean}{last_clean}',
                                    f'{last_clean}{first_clean}',
                                ):
                                    self.found_emails.append(DiscoveredEmail(
                                        email=f'{pattern}@{domain}',
                                        source='email_guess',
                                        confidence=_score_to_label(guess_score),
                                        verified=False,
                                        profile_name='Имя (транслит)',
                                        confidence_score=guess_score,
                                        sources=['email_guess'],
                                    ))
                except ImportError:
                    logger.debug("Transliteration module not available for email guessing")

    # ── Step 5: LeakDB Name Lookup ────────────────────────────────────

    def _query_leakdb_by_name(self, full_name: str):
        """Query local LeakDB for records matching the candidate's name."""
        if not full_name:
            return

        from app.services.phase2.sources.leak_sources import LeakDB

        db = LeakDB.get_instance()
        records = db.query_name(full_name)
        logger.info(f"LeakDB name lookup: '{full_name}' → {len(records)} records")

        for rec in records:
            if rec.get('phone'):
                normalized = normalize_phone(rec['phone'])
                if normalized:
                    score = _get_score('leak_db')
                    self.found_phones.append(DiscoveredPhone(
                        number=normalized,
                        source='leak_db',
                        confidence=_score_to_label(score),
                        profile_name=f"LeakDB ({rec.get('source', 'unknown')})",
                        raw_value=rec['phone'],
                        confidence_score=score,
                        sources=['leak_db'],
                    ))
            if rec.get('email'):
                score = _get_score('leak_db')
                self.found_emails.append(DiscoveredEmail(
                    email=rec['email'].lower(),
                    source='leak_db',
                    confidence=_score_to_label(score),
                    verified=False,
                    profile_name=f"LeakDB ({rec.get('source', 'unknown')})",
                    confidence_score=score,
                    sources=['leak_db'],
                ))

    # ── Step 6: Breach API Enrichment ──────────────────────────────────

    def _query_breach_apis(self, social_profiles: list):
        """Query free breach APIs with discovered emails and usernames."""
        # Collect unique emails discovered so far
        emails_to_check = list({e.email.lower() for e in self.found_emails})[:10]

        # Collect usernames from social profiles
        usernames = set()
        for profile in social_profiles:
            username = (profile.get('username') or '').strip()
            if username and len(username) >= 3:
                if not (username.startswith('id') and username[2:].isdigit()):
                    usernames.add(username.lower())
        usernames = list(usernames)[:5]

        if not emails_to_check and not usernames:
            return

        logger.info(
            f"Breach API enrichment: {len(emails_to_check)} emails, "
            f"{len(usernames)} usernames"
        )

        from app.services.phase2.sources.breach_api import (
            HudsonRockSource, LeakCheckSource, ProxyNovaCOMBSource,
        )

        sources = [HudsonRockSource(), LeakCheckSource(), ProxyNovaCOMBSource()]

        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = []
            for src in sources:
                futures.append(executor.submit(
                    src.query,
                    email=emails_to_check[0] if emails_to_check else None,
                    username=usernames[0] if usernames else None,
                    email_candidates=[{'email': e} for e in emails_to_check[1:]],
                ))

            for future in as_completed(futures, timeout=30):
                try:
                    results = future.result(timeout=15)
                    for r in (results or []):
                        if r.data_type == 'email' and r.value:
                            email_lower = r.value.lower()
                            if not any(e.email == email_lower for e in self.found_emails):
                                score = _get_score('breach_api')
                                self.found_emails.append(DiscoveredEmail(
                                    email=email_lower,
                                    source='breach_api',
                                    confidence=_score_to_label(score),
                                    verified=r.verified,
                                    profile_name=r.source_name,
                                    confidence_score=score,
                                    sources=['breach_api'],
                                ))
                        elif r.data_type == 'phone' and r.value:
                            normalized = normalize_phone(r.value)
                            if normalized and not any(p.number == normalized for p in self.found_phones):
                                score = _get_score('breach_api')
                                self.found_phones.append(DiscoveredPhone(
                                    number=normalized,
                                    source='breach_api',
                                    confidence=_score_to_label(score),
                                    profile_name=r.source_name,
                                    raw_value=r.value,
                                    confidence_score=score,
                                    sources=['breach_api'],
                                ))
                except Exception as e:
                    logger.warning(f"Breach API query error: {e}")

    # ── Step 7: LeakDB Cross-Reference ─────────────────────────────────

    def _cross_lookup_leakdb(self):
        """Cross-reference discovered contacts against LeakDB for snowball discovery."""
        from app.services.phase2.sources.leak_sources import LeakDB

        db = LeakDB.get_instance()
        new_emails = 0
        new_phones = 0

        # For each discovered phone, look up linked emails
        for phone in list(self.found_phones):
            records = db.query_phone(phone.number)
            for rec in records:
                if rec.get('email'):
                    email_lower = rec['email'].lower()
                    if not any(e.email == email_lower for e in self.found_emails):
                        score = _get_score('leak_db_xref')
                        self.found_emails.append(DiscoveredEmail(
                            email=email_lower,
                            source='leak_db_xref',
                            confidence=_score_to_label(score),
                            verified=False,
                            profile_name=f"LeakDB \u2190 {phone.number}",
                            confidence_score=score,
                            sources=['leak_db_xref'],
                        ))
                        new_emails += 1

        # For each discovered email, look up linked phones
        for email in list(self.found_emails):
            records = db.query_email(email.email)
            for rec in records:
                if rec.get('phone'):
                    normalized = normalize_phone(rec['phone'])
                    if normalized and not any(p.number == normalized for p in self.found_phones):
                        score = _get_score('leak_db_xref')
                        self.found_phones.append(DiscoveredPhone(
                            number=normalized,
                            source='leak_db_xref',
                            confidence=_score_to_label(score),
                            profile_name=f"LeakDB \u2190 {email.email}",
                            raw_value=rec['phone'],
                            confidence_score=score,
                            sources=['leak_db_xref'],
                        ))
                        new_phones += 1

        if new_emails or new_phones:
            logger.info(f"LeakDB cross-ref: +{new_emails} emails, +{new_phones} phones")

    # ── Step 8: Holehe Verification ──────────────────────────────────

    def _verify_with_holehe(self):
        """Verify discovered/guessed emails with Holehe."""
        if not self.found_emails:
            return

        # Prioritize: username-based guesses first, then name-based
        prioritized = sorted(
            self.found_emails,
            key=lambda e: (
                0 if e.source in ('vk_profile', 'telegram', 'input') else
                1 if e.source == 'email_guess' and 'транслит' not in e.profile_name else
                2
            ),
        )

        # Deduplicate emails for checking
        seen = set()
        to_check = []
        for e in prioritized:
            if e.email.lower() not in seen:
                seen.add(e.email.lower())
                to_check.append(e.email.lower())
            if len(to_check) >= MAX_HOLEHE_EMAILS:
                break

        if not to_check:
            return

        # Build a map of email -> list of DiscoveredEmail entries
        email_map = {}
        for e in self.found_emails:
            email_map.setdefault(e.email.lower(), []).append(e)

        try:
            from app.services.phase2.email_discovery import verify_emails_with_holehe
        except ImportError:
            logger.warning("Holehe verification module not available")
            return

        logger.info(f"Verifying {len(to_check)} emails with Holehe...")
        results = verify_emails_with_holehe(to_check, max_emails=MAX_HOLEHE_EMAILS)

        holehe_score = _get_score('holehe_verified')
        for result in results:
            email_lower = result['email'].lower()
            if result.get('verified') and result.get('services'):
                services = result['services']
                # Upgrade all matching entries
                if email_lower in email_map:
                    for entry in email_map[email_lower]:
                        entry.confidence = _score_to_label(holehe_score)
                        entry.confidence_score = max(entry.confidence_score, holehe_score)
                        entry.verified = True
                        entry.source = 'holehe_verified'
                        entry.services = services[:5]
                        if 'holehe_verified' not in entry.sources:
                            entry.sources.append('holehe_verified')
                else:
                    # Add as new verified email
                    self.found_emails.append(DiscoveredEmail(
                        email=email_lower,
                        source='holehe_verified',
                        confidence=_score_to_label(holehe_score),
                        verified=True,
                        profile_name='Holehe',
                        services=services[:5],
                        confidence_score=holehe_score,
                        sources=['holehe_verified'],
                    ))

    # ── Step 8: Forgot-Password Oracle ───────────────────────────────

    def _run_forgot_password_oracle(self, check):
        """Run forgot-password hint extraction across Russian services."""
        try:
            from app.services.phase2.forgot_password_oracle import ForgotPasswordOracle
        except ImportError:
            logger.debug("Forgot password oracle module not available")
            return

        oracle = ForgotPasswordOracle()

        # Collect known emails and phones to check
        emails_to_check = list({e.email for e in self.found_emails
                                if e.source in ('input', 'vk_profile', 'telegram')})[:3]
        phones_to_check = list({p.number for p in self.found_phones
                                if p.source in ('input', 'vk_profile', 'telegram')})[:2]

        if not emails_to_check and not phones_to_check:
            if check.email:
                emails_to_check = [check.email.lower().strip()]
            if check.phone:
                phones_to_check = [normalize_phone(check.phone)]

        if not emails_to_check and not phones_to_check:
            return

        all_results = []
        for email in emails_to_check:
            try:
                results = oracle.check_email(email)
                all_results.extend(results)
            except Exception as e:
                logger.warning(f"Oracle email check error for {email}: {e}")

        for phone in phones_to_check:
            try:
                results = oracle.check_phone(phone)
                all_results.extend(results)
            except Exception as e:
                logger.warning(f"Oracle phone check error for {phone}: {e}")

        # Count how many services confirmed existence
        confirmed_services = sum(1 for r in all_results if r.get('exists'))
        score_key = 'forgot_password_multi' if confirmed_services >= 2 else 'forgot_password_single'

        for result in all_results:
            if not result.get('exists') or not result.get('masked_hint'):
                continue

            hint = result['masked_hint']
            hint_type = result.get('hint_type', '')
            score = _get_score(score_key)

            if hint_type == 'phone':
                # Try to extract digits from masked hint
                digits = re.sub(r'[^\d]', '', hint)
                if len(digits) >= 7:
                    normalized = normalize_phone(hint)
                    if normalized:
                        self.found_phones.append(DiscoveredPhone(
                            number=normalized,
                            source='forgot_password',
                            confidence=_score_to_label(score),
                            profile_name=f"Восстановление ({result['service']})",
                            raw_value=hint,
                            confidence_score=score,
                            sources=[f"forgot_password_{result['service']}"],
                        ))
            elif hint_type == 'email':
                # Masked emails like "i***v@mail.ru" — store as-is
                if '@' in hint:
                    self.found_emails.append(DiscoveredEmail(
                        email=hint.lower(),
                        source='forgot_password',
                        confidence=_score_to_label(score),
                        verified=True,
                        profile_name=f"Восстановление ({result['service']})",
                        confidence_score=score,
                        sources=[f"forgot_password_{result['service']}"],
                    ))

        if all_results:
            logger.info(
                f"Forgot-password oracle: {len(all_results)} results, "
                f"{confirmed_services} services confirmed existence"
            )

    # ── Step 9: Marketplace Mining ────────────────────────────────────

    def _run_marketplace_scan(self, check):
        """Mine Russian marketplaces (Avito, Youla, CIAN, Auto.ru) for contacts."""
        try:
            from app.services.phase2.marketplace_scanner import MarketplaceOracle
        except ImportError:
            logger.debug("Marketplace scanner module not available")
            return

        oracle = MarketplaceOracle(city=None)

        # Get city from behavioral data if available
        geo = check.geo_data if hasattr(check, 'geo_data') and check.geo_data else {}
        if isinstance(geo, dict):
            cities = geo.get('cities', [])
            if cities and isinstance(cities, list) and isinstance(cities[0], dict):
                oracle.city = cities[0].get('name')

        try:
            known_phone = None
            for p in self.found_phones:
                if p.confidence_score >= 0.80:
                    known_phone = p.number
                    break

            results = oracle.search_all(
                full_name=check.full_name,
                phone=known_phone,
                city=oracle.city,
            )
        except Exception as e:
            logger.warning(f"Marketplace scan error: {e}")
            return

        mkt_score = _get_score('marketplace')

        for phone_data in results.get('phones', []):
            number = phone_data.get('number', '')
            if number and not any(p.number == number for p in self.found_phones):
                self.found_phones.append(DiscoveredPhone(
                    number=number,
                    source='marketplace',
                    confidence=_score_to_label(mkt_score),
                    profile_name=phone_data.get('source', 'marketplace'),
                    raw_value=number,
                    confidence_score=mkt_score,
                    sources=[f"marketplace_{phone_data.get('source', 'unknown')}"],
                ))

        for email_data in results.get('emails', []):
            email = email_data.get('email', '').lower()
            if email and not any(e.email == email for e in self.found_emails):
                self.found_emails.append(DiscoveredEmail(
                    email=email,
                    source='marketplace',
                    confidence=_score_to_label(mkt_score),
                    verified=False,
                    profile_name=email_data.get('source', 'marketplace'),
                    confidence_score=mkt_score,
                    sources=[f"marketplace_{email_data.get('source', 'unknown')}"],
                ))

        total = len(results.get('phones', [])) + len(results.get('emails', []))
        if total:
            logger.info(f"Marketplace scan: {total} contacts found")

    # ── Step 11: Deduplication + Source Merging + Scoring ─────────────

    def _deduplicate_contacts(self):
        """Deduplicate, merge sources, apply cross-source boost, and re-score."""
        # ── Phones: normalize → merge sources → pick best ──
        phone_map: Dict[str, DiscoveredPhone] = {}
        phone_sources_map: Dict[str, List[str]] = {}

        for phone in self.found_phones:
            normalized = normalize_phone(phone.number)
            if not normalized:
                continue
            phone.number = normalized  # ensure consistent format

            if normalized not in phone_map:
                phone_map[normalized] = phone
                phone_sources_map[normalized] = list(phone.sources or [phone.source])
            else:
                existing = phone_map[normalized]
                # Merge sources
                for src in (phone.sources or [phone.source]):
                    if src not in phone_sources_map[normalized]:
                        phone_sources_map[normalized].append(src)
                # Keep higher confidence version as base
                if phone.confidence_score > existing.confidence_score:
                    phone.sources = phone_sources_map[normalized]
                    phone_map[normalized] = phone

        # Apply cross-source boost and finalize
        for normalized, phone in phone_map.items():
            phone.sources = phone_sources_map.get(normalized, [phone.source])
            source_count = len(set(phone.sources))
            if source_count >= CROSS_SOURCE_THRESHOLD:
                phone.confidence_score = min(
                    MAX_CONFIDENCE,
                    phone.confidence_score + CROSS_SOURCE_BOOST,
                )
            phone.confidence = _score_to_label(phone.confidence_score)

        self.found_phones = list(phone_map.values())

        # ── Emails: normalize → merge sources → pick best ──
        email_map: Dict[str, DiscoveredEmail] = {}
        email_sources_map: Dict[str, List[str]] = {}

        for email in self.found_emails:
            lower = email.email.lower()
            email.email = lower

            if lower not in email_map:
                email_map[lower] = email
                email_sources_map[lower] = list(email.sources or [email.source])
            else:
                existing = email_map[lower]
                # Merge sources
                for src in (email.sources or [email.source]):
                    if src not in email_sources_map[lower]:
                        email_sources_map[lower].append(src)
                # Prefer verified, then higher confidence
                if email.verified and not existing.verified:
                    email.sources = email_sources_map[lower]
                    email_map[lower] = email
                elif email.confidence_score > existing.confidence_score and not existing.verified:
                    email.sources = email_sources_map[lower]
                    email_map[lower] = email
                # Merge services from Holehe
                if email.services:
                    for svc in email.services:
                        if svc not in email_map[lower].services:
                            email_map[lower].services.append(svc)

        # Apply cross-source boost and finalize
        for lower, email in email_map.items():
            email.sources = email_sources_map.get(lower, [email.source])
            source_count = len(set(email.sources))
            if source_count >= CROSS_SOURCE_THRESHOLD:
                email.confidence_score = min(
                    MAX_CONFIDENCE,
                    email.confidence_score + CROSS_SOURCE_BOOST,
                )
            email.confidence = _score_to_label(email.confidence_score)

        self.found_emails = list(email_map.values())

        # Sort: verified first, then by confidence score descending
        self.found_emails.sort(
            key=lambda e: (not e.verified, -e.confidence_score),
        )
        self.found_phones.sort(
            key=lambda p: -p.confidence_score,
        )

    # ── Supplementary Discovery (Stage 5 feedback) ───────────────────

    def discover_supplementary(self, new_accounts: list, existing_contacts: dict) -> dict:
        """
        Run mini contact discovery on newly discovered accounts from Stage 5.

        When Snoop/YaSeeker/face search finds new social accounts, this method
        extracts contacts from those accounts (email patterns, breach checks)
        and returns only NEW discoveries not already in existing_contacts.

        Args:
            new_accounts: List of dicts with keys: url, username, platform, source
            existing_contacts: Current check.contact_discoveries dict

        Returns:
            {"phones": [...], "emails": [...]} with only new discoveries
        """
        if not new_accounts:
            return {'phones': [], 'emails': []}

        # Check for demo data (accounts from demo response)
        is_demo = any(
            'demo' in (a.get('username') or '').lower()
            for a in new_accounts
        )
        if is_demo:
            return self._demo_supplementary()

        new_phones = []
        new_emails = []

        # Collect existing contacts for dedup
        existing_email_set = set()
        existing_phone_set = set()
        for email_item in (existing_contacts.get('emails') or []):
            addr = email_item.get('email', '') if isinstance(email_item, dict) else str(email_item)
            existing_email_set.add(addr.lower())
        for phone_item in (existing_contacts.get('phones') or []):
            num = phone_item.get('number', '') if isinstance(phone_item, dict) else str(phone_item)
            existing_phone_set.add(num)

        # Step 1: Extract usernames from new accounts
        usernames = set()
        for account in new_accounts:
            username = (account.get('username') or '').strip()
            if username and len(username) >= 3:
                if not (username.startswith('id') and username[2:].isdigit()):
                    usernames.add(username.lower())

        # Step 2: Generate email patterns from usernames
        generated_emails = []
        for username in list(usernames)[:10]:
            clean = re.sub(r'[^a-z0-9._-]', '', username)
            if len(clean) < 3:
                continue
            for domain in GUESS_DOMAINS[:4]:  # Top 4 domains only for speed
                email = f'{clean}@{domain}'
                if email not in existing_email_set:
                    generated_emails.append(email)
                    existing_email_set.add(email)

        # Step 3: Holehe verification on generated emails (max 10)
        verified_emails = []
        if generated_emails:
            emails_to_check = generated_emails[:10]
            try:
                from app.services.phase2.email_discovery import verify_emails_with_holehe
                logger.info(f"Supplementary: verifying {len(emails_to_check)} emails with Holehe")
                results = verify_emails_with_holehe(emails_to_check, max_emails=10)
                for r in results:
                    if r.get('verified') and r.get('services'):
                        verified_emails.append({
                            'address': r['email'].lower(),
                            'source': 'holehe_supplementary',
                            'confidence': 'высокая',
                            'services': r['services'][:3],
                        })
            except ImportError:
                logger.debug("Holehe not available for supplementary verification")
            except Exception as e:
                logger.warning(f"Supplementary Holehe error: {e}")

        # Also add unverified guesses with low confidence
        for email in generated_emails[:5]:
            if not any(v['address'] == email for v in verified_emails):
                new_emails.append({
                    'address': email,
                    'source': 'email_guess_supplementary',
                    'confidence': 'низкая',
                })

        new_emails = verified_emails + new_emails

        # Step 4: Breach API check on new emails
        if generated_emails:
            try:
                from app.services.phase2.sources.breach_api import (
                    HudsonRockSource, LeakCheckSource,
                )
                for src_cls in [HudsonRockSource, LeakCheckSource]:
                    try:
                        src = src_cls()
                        results = src.query(
                            email=generated_emails[0] if generated_emails else None
                        )
                        for r in (results or []):
                            if r.data_type == 'phone' and r.value:
                                normalized = normalize_phone(r.value)
                                if normalized and normalized not in existing_phone_set:
                                    new_phones.append({
                                        'number': normalized,
                                        'source': f'breach_supplementary_{r.source_name}',
                                        'confidence': 'средняя',
                                    })
                                    existing_phone_set.add(normalized)
                            elif r.data_type == 'email' and r.value:
                                email_lower = r.value.lower()
                                if email_lower not in existing_email_set:
                                    new_emails.append({
                                        'address': email_lower,
                                        'source': f'breach_supplementary_{r.source_name}',
                                        'confidence': 'средняя',
                                    })
                                    existing_email_set.add(email_lower)
                    except Exception as e:
                        logger.warning(f"Supplementary breach query error: {e}")
            except ImportError:
                logger.debug("Breach API sources not available")

        return {
            'phones': new_phones,
            'emails': new_emails,
        }

    @staticmethod
    def _demo_supplementary() -> dict:
        """Return demo supplementary discovery results."""
        return {
            'phones': [
                {'number': '+79161234599', 'source': 'breach_supplementary_demo', 'confidence': 'средняя'},
            ],
            'emails': [
                {'address': 'ivanov.demo@gmail.com', 'source': 'holehe_supplementary', 'confidence': 'высокая'},
                {'address': 'ivanov.demo@mail.ru', 'source': 'email_guess_supplementary', 'confidence': 'низкая'},
            ],
        }
