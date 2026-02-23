"""
Contact Discovery Service (Stage 4)
====================================
Extracts phones and emails from VK/Telegram profiles, business records,
guesses emails from usernames, queries breach databases, and verifies
with Holehe.

Discovery chain (order matters — each step feeds the next):
1. Extract from VK profiles (API)
2. Extract from Telegram profiles (parse existing data)
3. Extract from business/FSSP records
4. Guess emails from usernames
5. LeakDB name lookup (local breach data)
6. Breach API enrichment (HudsonRock, LeakCheck, ProxyNova COMB)
7. LeakDB cross-reference (snowball: phone→email, email→phone)
8. Verify emails with Holehe
9. Deduplicate and score
"""

import logging
import os
import re
import time
from dataclasses import dataclass, field, asdict
from typing import List, Optional
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
]
NAME_GUESS_DOMAINS = ['gmail.com', 'mail.ru', 'yandex.ru']

# Max emails to verify with Holehe (expensive operation)
MAX_HOLEHE_EMAILS = 20

# VK API version
VK_API_VERSION = '5.131'


@dataclass
class DiscoveredPhone:
    number: str           # normalized +79161234567
    source: str           # "vk_profile", "telegram", "egrul", "fssp", "input"
    confidence: str       # "высокая", "средняя", "низкая"
    profile_name: str     # which profile it came from
    raw_value: str        # original before normalization

    def to_dict(self):
        return asdict(self)


@dataclass
class DiscoveredEmail:
    email: str            # normalized lowercase
    source: str           # "vk_profile", "email_guess", "holehe_verified", "egrul", "input"
    confidence: str       # "высокая", "средняя", "низкая"
    verified: bool        # True if Holehe confirmed
    profile_name: str     # which profile/method it came from
    services: List[str] = field(default_factory=list)  # Holehe services found on

    def to_dict(self):
        return asdict(self)


def _confidence_rank(confidence: str) -> int:
    return {'высокая': 3, 'средняя': 2, 'низкая': 1}.get(confidence, 0)


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
            ))

        if check.email:
            self.found_emails.append(DiscoveredEmail(
                email=check.email.lower().strip(),
                source='input',
                confidence='высокая',
                verified=False,
                profile_name='Форма ввода',
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

        # Step 8: Holehe verification
        try:
            self._verify_with_holehe()
        except Exception as e:
            logger.warning(f"Holehe verification error: {e}")

        # Step 9: Deduplicate
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
                        conf = 'высокая' if phone_field == 'mobile_phone' else 'средняя'
                        self.found_phones.append(DiscoveredPhone(
                            number=normalized,
                            source='vk_profile',
                            confidence=conf,
                            profile_name=display_name,
                            raw_value=raw,
                        ))

                # Check site, about, status for phones/emails
                for text_field in ('site', 'about', 'status'):
                    text = (user.get(text_field) or '').strip()
                    if not text:
                        continue

                    for match in PHONE_PATTERN.finditer(text):
                        normalized = normalize_phone(match.group())
                        self.found_phones.append(DiscoveredPhone(
                            number=normalized,
                            source='vk_profile',
                            confidence='средняя',
                            profile_name=display_name,
                            raw_value=match.group(),
                        ))

                    for match in EMAIL_PATTERN.finditer(text):
                        email = match.group().lower()
                        self.found_emails.append(DiscoveredEmail(
                            email=email,
                            source='vk_profile',
                            confidence='высокая',
                            verified=False,
                            profile_name=display_name,
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
                self.found_phones.append(DiscoveredPhone(
                    number=normalized,
                    source='telegram',
                    confidence='высокая',
                    profile_name=display_name,
                    raw_value=phone,
                ))

            # Check bio/about for contacts
            for text_field in ('bio', 'about'):
                text = (profile.get(text_field) or '').strip()
                if not text:
                    continue

                for match in PHONE_PATTERN.finditer(text):
                    normalized = normalize_phone(match.group())
                    self.found_phones.append(DiscoveredPhone(
                        number=normalized,
                        source='telegram',
                        confidence='средняя',
                        profile_name=display_name,
                        raw_value=match.group(),
                    ))

                for match in EMAIL_PATTERN.finditer(text):
                    email = match.group().lower()
                    self.found_emails.append(DiscoveredEmail(
                        email=email,
                        source='telegram',
                        confidence='высокая',
                        verified=False,
                        profile_name=display_name,
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
                    self.found_phones.append(DiscoveredPhone(
                        number=normalized,
                        source='egrul',
                        confidence='низкая',
                        profile_name=company_name,
                        raw_value=raw,
                    ))

            # Company email
            for email_field in ('email', 'contact_email'):
                raw = (biz.get(email_field) or '').strip()
                if raw and EMAIL_PATTERN.match(raw):
                    self.found_emails.append(DiscoveredEmail(
                        email=raw.lower(),
                        source='egrul',
                        confidence='низкая',
                        verified=False,
                        profile_name=company_name,
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
                    self.found_phones.append(DiscoveredPhone(
                        number=normalized,
                        source='fssp',
                        confidence='низкая',
                        profile_name='ФССП',
                        raw_value=raw,
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
            for domain in GUESS_DOMAINS:
                self.found_emails.append(DiscoveredEmail(
                    email=f'{clean}@{domain}',
                    source='email_guess',
                    confidence='низкая',
                    verified=False,
                    profile_name=f'@{username}',
                ))

        # Name-based guesses (transliterated)
        if full_name:
            parts = full_name.strip().split()
            if len(parts) >= 2:
                try:
                    from app.services.phase1.transliteration import transliterate_name_part
                    last_variants = transliterate_name_part(parts[0], max_variants=2)
                    first_variants = transliterate_name_part(parts[1], max_variants=2)

                    for last_lat in last_variants:
                        for first_lat in first_variants:
                            last_clean = re.sub(r"[^a-z]", '', last_lat.lower())
                            first_clean = re.sub(r"[^a-z]", '', first_lat.lower())
                            if not last_clean or not first_clean:
                                continue
                            for domain in NAME_GUESS_DOMAINS:
                                self.found_emails.append(DiscoveredEmail(
                                    email=f'{first_clean}.{last_clean}@{domain}',
                                    source='email_guess',
                                    confidence='низкая',
                                    verified=False,
                                    profile_name='Имя (транслит)',
                                ))
                                self.found_emails.append(DiscoveredEmail(
                                    email=f'{last_clean}.{first_clean}@{domain}',
                                    source='email_guess',
                                    confidence='низкая',
                                    verified=False,
                                    profile_name='Имя (транслит)',
                                ))
                                self.found_emails.append(DiscoveredEmail(
                                    email=f'{first_clean}{last_clean}@{domain}',
                                    source='email_guess',
                                    confidence='низкая',
                                    verified=False,
                                    profile_name='Имя (транслит)',
                                ))
                                self.found_emails.append(DiscoveredEmail(
                                    email=f'{last_clean}{first_clean}@{domain}',
                                    source='email_guess',
                                    confidence='низкая',
                                    verified=False,
                                    profile_name='Имя (транслит)',
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
                    self.found_phones.append(DiscoveredPhone(
                        number=normalized,
                        source='leak_db',
                        confidence='средняя',
                        profile_name=f"LeakDB ({rec.get('source', 'unknown')})",
                        raw_value=rec['phone'],
                    ))
            if rec.get('email'):
                self.found_emails.append(DiscoveredEmail(
                    email=rec['email'].lower(),
                    source='leak_db',
                    confidence='средняя',
                    verified=False,
                    profile_name=f"LeakDB ({rec.get('source', 'unknown')})",
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
                                self.found_emails.append(DiscoveredEmail(
                                    email=email_lower,
                                    source='breach_api',
                                    confidence='средняя' if r.confidence >= 0.8 else 'низкая',
                                    verified=r.verified,
                                    profile_name=r.source_name,
                                ))
                        elif r.data_type == 'phone' and r.value:
                            normalized = normalize_phone(r.value)
                            if normalized and not any(p.number == normalized for p in self.found_phones):
                                self.found_phones.append(DiscoveredPhone(
                                    number=normalized,
                                    source='breach_api',
                                    confidence='средняя',
                                    profile_name=r.source_name,
                                    raw_value=r.value,
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
                        self.found_emails.append(DiscoveredEmail(
                            email=email_lower,
                            source='leak_db_xref',
                            confidence='средняя',
                            verified=False,
                            profile_name=f"LeakDB \u2190 {phone.number}",
                        ))
                        new_emails += 1

        # For each discovered email, look up linked phones
        for email in list(self.found_emails):
            records = db.query_email(email.email)
            for rec in records:
                if rec.get('phone'):
                    normalized = normalize_phone(rec['phone'])
                    if normalized and not any(p.number == normalized for p in self.found_phones):
                        self.found_phones.append(DiscoveredPhone(
                            number=normalized,
                            source='leak_db_xref',
                            confidence='средняя',
                            profile_name=f"LeakDB \u2190 {email.email}",
                            raw_value=rec['phone'],
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

        for result in results:
            email_lower = result['email'].lower()
            if result.get('verified') and result.get('services'):
                services = result['services']
                # Upgrade all matching entries
                if email_lower in email_map:
                    for entry in email_map[email_lower]:
                        entry.confidence = 'высокая'
                        entry.verified = True
                        entry.source = 'holehe_verified'
                        entry.services = services[:5]
                else:
                    # Add as new verified email
                    self.found_emails.append(DiscoveredEmail(
                        email=email_lower,
                        source='holehe_verified',
                        confidence='высокая',
                        verified=True,
                        profile_name='Holehe',
                        services=services[:5],
                    ))

    # ── Step 9: Deduplication ────────────────────────────────────────

    def _deduplicate_contacts(self):
        """Remove duplicate phones/emails, keep highest confidence version."""
        # Phones
        seen_phones = {}
        for phone in self.found_phones:
            normalized = normalize_phone(phone.number)
            if not normalized:
                continue
            if (normalized not in seen_phones or
                    _confidence_rank(phone.confidence) > _confidence_rank(seen_phones[normalized].confidence)):
                seen_phones[normalized] = phone
        self.found_phones = list(seen_phones.values())

        # Emails
        seen_emails = {}
        for email in self.found_emails:
            lower = email.email.lower()
            existing = seen_emails.get(lower)
            if existing is None:
                seen_emails[lower] = email
            elif email.verified and not existing.verified:
                seen_emails[lower] = email
            elif (_confidence_rank(email.confidence) > _confidence_rank(existing.confidence)
                  and not existing.verified):
                seen_emails[lower] = email
        self.found_emails = list(seen_emails.values())

        # Sort: verified first, then by confidence
        self.found_emails.sort(
            key=lambda e: (not e.verified, -_confidence_rank(e.confidence)),
        )
        self.found_phones.sort(
            key=lambda p: -_confidence_rank(p.confidence),
        )
