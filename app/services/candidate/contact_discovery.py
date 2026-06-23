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
 8.5. Cross-reference partial phones (breach DB + GetContact completion)
 9. Marketplace mining (Avito, Youla, CIAN, Auto.ru, Yandex, VK Market)
10. Verify emails with Holehe
11. Deduplicate, merge sources, and score
"""

import logging
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
TELEGRAM_PATTERN = re.compile(r'(?:t\.me/|@)([a-zA-Z][a-zA-Z0-9_]{4,31})')

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
VK_API_VERSION = '5.199'

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
    'vk_forgot_password':       0.85,  # VK recovery via username → masked phone
    'vk_forgot_password_email': 0.75,  # VK recovery via username → masked email
    'hunter_verified':          0.80,  # Hunter.io confirms email deliverable
    'holehe_verified':          0.80,  # Holehe confirms email exists
    'vk_wall_by_others':        0.70,  # VK wall post comment by others
    'leak_db':                  0.65,  # local leak database
    'breach_api':               0.60,  # free breach API (HudsonRock, LeakCheck)
    'egrul':                    0.50,  # business registry (company phone, not personal)
    'fssp':                     0.45,  # FSSP enforcement records
    'email_guess':              0.40,  # pattern-generated (unverified)
    'leak_db_xref':             0.55,  # cross-referenced from leak DB
    'partial_phone_breach':     0.95,  # partial phone completed via breach DB match
    'partial_phone_getcontact': 0.90,  # partial phone completed via GetContact name match
}

# Graduated cross-source boost by number of independent sources
CROSS_SOURCE_BOOST_MAP = {1: 0, 2: 0.10, 3: 0.15}  # 4+ → 0.20
CROSS_SOURCE_BOOST_DEFAULT = 0.20  # 4+ sources
MAX_CONFIDENCE = 0.98


def _score_to_label(score: float) -> str:
    """Convert numeric confidence to Russian label for backward compat."""
    if score >= 0.75:
        return 'высокая'
    elif score >= 0.50:
        return 'средняя'
    return 'низкая'


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


def _get_score(source_key: str) -> float:
    """Get numeric confidence for a source key."""
    return CONFIDENCE_SCORES.get(source_key, 0.50)


class ContactDiscoveryService:
    """Discovers phones and emails from existing check data."""

    def __init__(self):
        from app.utils.vk_token_manager import get_vk_user_token, get_vk_service_token
        # User token for private methods (wall.get, etc.), service token for search
        self.vk_user_token = get_vk_user_token()
        self.vk_token = self.vk_user_token or get_vk_service_token()
        self.found_phones: List[DiscoveredPhone] = []
        self.found_emails: List[DiscoveredEmail] = []
        self._oracle_results: list = []  # raw forgot-password oracle results for cross-ref

    # Overall time budget for discover() — pipeline enforces 60s via ThreadPoolExecutor,
    # but we also track internally so we can skip slow steps gracefully.
    STAGE_TIMEOUT = 60  # seconds

    def _time_left(self) -> float:
        """Seconds remaining in the time budget."""
        return max(0, self.STAGE_TIMEOUT - (time.time() - self._start_time))

    def _has_time(self, min_seconds: float = 2.0) -> bool:
        """Check if enough time remains for another step."""
        return self._time_left() > min_seconds

    def _run_step(self, name: str, func, *args, **kwargs):
        """Run a discovery step with 5s hard timeout via thread. Log and continue on timeout."""
        if not self._has_time():
            logger.info(f"Contact discovery: skipping {name} (time budget exhausted, {self._time_left():.1f}s left)")
            return None

        timeout = min(5.0, self._time_left())
        try:
            pool = ThreadPoolExecutor(max_workers=1)
            future = pool.submit(func, *args, **kwargs)
            try:
                return future.result(timeout=timeout)
            except Exception as e:
                logger.warning(f"{name}: timeout/error after {timeout:.0f}s — {e}")
                return None
            finally:
                pool.shutdown(wait=False, cancel_futures=True)
        except Exception as e:
            logger.warning(f"{name}: failed to start — {e}")
            return None

    def _run_wave(self, wave_name: str, tasks: list, max_workers: int) -> dict:
        """Run a list of (name, func, args, kwargs) tasks in parallel within the time budget.

        Returns:
            dict mapping task name -> result (or None on error/timeout)
        """
        if not self._has_time():
            logger.info(f"Contact discovery: skipping wave '{wave_name}' (time budget exhausted)")
            return {}

        results = {}
        timeout = self._time_left()
        logger.info(f"Contact discovery wave '{wave_name}': {len(tasks)} tasks, "
                     f"max_workers={max_workers}, timeout={timeout:.1f}s")

        pool = ThreadPoolExecutor(max_workers=max_workers)
        try:
            future_to_name = {}
            for name, func, args, kwargs in tasks:
                future = pool.submit(func, *args, **kwargs)
                future_to_name[future] = name

            for future in as_completed(future_to_name, timeout=timeout):
                name = future_to_name[future]
                try:
                    results[name] = future.result()
                except Exception as e:
                    logger.warning(f"Wave '{wave_name}' task '{name}' error: {e}")
                    results[name] = None
        except TimeoutError:
            logger.warning(f"Wave '{wave_name}' timed out after {timeout:.1f}s "
                           f"(completed {len(results)}/{len(tasks)} tasks)")
        except Exception as e:
            logger.warning(f"Wave '{wave_name}' error: {e}")
        finally:
            pool.shutdown(wait=False, cancel_futures=True)

        return results

    def discover(self, check) -> dict:
        """
        Main entry point. Runs discovery steps in parallel waves.
        Overall 60s time budget — waves are skipped when time runs out.

        Wave 1 (Group A — no dependencies): VK, TG, Business/FSSP, email guessing, Hunter.io
        Wave 2 (Group B — needs emails/phones from Wave 1): LeakDB, Breach APIs, breach intel
        Wave 3 (Group C — needs Wave 2): LeakDB xref, Oracle, Marketplace, partial phones
        Wave 4 (Group D — needs all emails): Holehe

        Args:
            check: CandidateCheck model instance

        Returns:
            {"phones": [...], "emails": [...]} with serialized results
        """
        self._start_time = time.time()

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

        # Use confirmed_name (from Stage 0 EGRUL) if available, else fall back to input
        effective_name = getattr(check, 'confirmed_name', None) or check.full_name
        birth_year_str = str(check.date_of_birth.year) if check.date_of_birth else None

        # ── Wave 1: Independent sources (no cross-dependencies) ──────
        def _wave1_business_fssp():
            self._extract_from_business(check.business_records or [])
            self._extract_from_fssp(check.fssp_records or [])

        def _wave1_email_guess():
            self._guess_emails(social_profiles, effective_name, birth_year=birth_year_str)

        wave1_tasks = [
            ('VK contact extraction',     self._extract_from_vk,          [social_profiles], {}),
            ('Deep VK wall extraction',    self._deep_vk_wall_extraction,  [social_profiles], {}),
            ('Telegram contact extraction', self._extract_from_telegram,   [social_profiles], {}),
            ('Business/FSSP extraction',   _wave1_business_fssp,           [], {}),
            ('Email guessing',             _wave1_email_guess,             [], {}),
            ('Hunter.io corporate search', self._hunter_corporate_search,  [social_profiles, effective_name], {}),
        ]
        self._run_wave('Wave 1 (independent sources)', wave1_tasks, max_workers=6)

        # ── Wave 2: Needs emails/phones from Wave 1 ─────────────────
        if self._has_time():
            wave2_tasks = [
                ('LeakDB name lookup',          self._query_leakdb_by_name,      [effective_name], {}),
                ('Breach API enrichment',        self._query_breach_apis,          [social_profiles], {}),
                ('Breach intelligence analysis', self._analyze_breach_intelligence, [], {}),
            ]
            wave2_results = self._run_wave('Wave 2 (breach/leak enrichment)', wave2_tasks, max_workers=3)
            breach_intelligence = wave2_results.get('Breach intelligence analysis') or {}
        else:
            breach_intelligence = {}

        # ── Wave 3: Needs Wave 2 results ─────────────────────────────
        if self._has_time():
            wave3_tasks = [
                ('LeakDB cross-reference',    self._cross_lookup_leakdb,           [], {}),
                ('Forgot-password oracle',    self._run_forgot_password_oracle,     [check], {}),
                ('Partial phone cross-ref',   self._cross_reference_partial_phones, [check], {}),
            ]
            self._run_wave('Wave 3 (cross-reference & oracle)', wave3_tasks, max_workers=4)

        # ── Wave 4: Holehe verification (needs all emails discovered) ─
        if self._has_time():
            wave4_tasks = [
                ('Holehe verification', self._verify_with_holehe, [], {}),
            ]
            self._run_wave('Wave 4 (email verification)', wave4_tasks, max_workers=1)

        elapsed = time.time() - self._start_time
        logger.info(f"Contact discovery completed in {elapsed:.1f}s "
                     f"({len(self.found_phones)} phones, {len(self.found_emails)} emails)")

        # Final: Deduplicate, merge sources, score
        self._deduplicate_contacts()

        result = {
            'phones': [p.to_dict() for p in self.found_phones],
            'emails': [e.to_dict() for e in self.found_emails],
        }

        # Include enrichment hints from deep VK wall mining
        if getattr(self, '_telegram_hints', None):
            result['telegram_hints'] = self._telegram_hints
        if getattr(self, '_instagram_hints', None):
            result['instagram_hints'] = self._instagram_hints

        # Include breach intelligence and risk flags
        if breach_intelligence:
            result['breach_intelligence'] = breach_intelligence

            # Build risk flags from breach intelligence
            flags = []
            bc = breach_intelligence.get('breach_count', 0)
            if bc >= 5:
                flags.append({
                    'type': 'fact',
                    'code': 'high_breach_exposure',
                    'description': f'Данные присутствуют в {bc} утечках',
                    'severity': 'medium',
                })
            if breach_intelligence.get('has_financial_services'):
                flags.append({
                    'type': 'fact',
                    'code': 'financial_services_exposed',
                    'description': 'Обнаружена регистрация в финансовых сервисах (банки/крипто)',
                    'severity': 'medium',
                })
            if flags:
                result['breach_flags'] = flags

        return result

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

                # Direct 'phone' field (sometimes present)
                raw_phone = (user.get('phone') or '').strip()
                if raw_phone and PHONE_PATTERN.search(raw_phone):
                    normalized = normalize_phone(PHONE_PATTERN.search(raw_phone).group())
                    score = _get_score('vk_profile_contacts')
                    self.found_phones.append(DiscoveredPhone(
                        number=normalized,
                        source='vk_profile',
                        confidence=_score_to_label(score),
                        profile_name=display_name,
                        raw_value=raw_phone,
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

                # Social links from VK fields
                for social_field, social_type in [
                    ('twitter', 'twitter'), ('instagram', 'instagram'),
                    ('facebook', 'facebook'), ('skype', 'skype'),
                ]:
                    val = (user.get(social_field) or '').strip()
                    if val:
                        # Check for email in social fields
                        email_match = EMAIL_PATTERN.search(val)
                        if email_match:
                            email = email_match.group().lower()
                            score = _get_score('vk_profile_contacts')
                            self.found_emails.append(DiscoveredEmail(
                                email=email,
                                source='vk_profile',
                                confidence=_score_to_label(score),
                                verified=False,
                                profile_name=f'{display_name} ({social_type})',
                                confidence_score=score,
                                sources=['vk_profile'],
                            ))

                # Personal section (education, occupation -> may contain employer email)
                personal = user.get('personal') or {}
                if isinstance(personal, dict):
                    for key, val in personal.items():
                        if isinstance(val, str):
                            for match in EMAIL_PATTERN.finditer(val):
                                email = match.group().lower()
                                score = _get_score('vk_profile_contacts')
                                self.found_emails.append(DiscoveredEmail(
                                    email=email,
                                    source='vk_profile',
                                    confidence=_score_to_label(score),
                                    verified=False,
                                    profile_name=f'{display_name} (personal)',
                                    confidence_score=score,
                                    sources=['vk_profile'],
                                ))

                # Telegram handles in text fields
                for text_field in ('about', 'status', 'site'):
                    text = (user.get(text_field) or '').strip()
                    if text:
                        for tg_match in TELEGRAM_PATTERN.finditer(text):
                            handle = tg_match.group(1)
                            if not hasattr(self, '_telegram_hints'):
                                self._telegram_hints = []
                            self._telegram_hints.append({
                                'username': handle,
                                'source': 'vk_profile_field',
                                'profile_url': f'https://vk.com/{vk_id}',
                            })

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
                    'fields': 'contacts,phone,mobile_phone,home_phone,site,about,status,twitter,facebook,instagram,skype,occupation,personal,universities,schools,relatives,domain',
                    'access_token': self.vk_token,
                    'v': VK_API_VERSION,
                },
                timeout=5,
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

    # ── Step 1b: Deep VK Wall Mining ────────────────────────────────

    def _deep_vk_wall_extraction(self, social_profiles: list):
        """Run VKWallExtractor for deep wall mining: posts, comments, tagged posts,
        photo comments, mentions. Feeds discovered Telegram usernames back as
        enrichment hints for later stages."""
        vk_profiles = [p for p in social_profiles if p.get('platform') == 'vk']
        if not vk_profiles or not self.vk_token:
            return

        try:
            from app.services.phase2.vk_wall_extractor import VKWallExtractor
        except ImportError:
            logger.debug("VKWallExtractor not available")
            return

        # wall.get requires user token (not service token)
        wall_token = self.vk_user_token or self.vk_token
        extractor = VKWallExtractor(access_token=wall_token)

        for profile in vk_profiles[:2]:  # max 2 profiles to limit API calls
            url = profile.get('url', '')
            if not url:
                continue

            display_name = profile.get('display_name', '')

            try:
                wall_result = extractor.extract_from_profile(url, max_posts=200)
            except Exception as e:
                logger.warning(f"VK wall extraction error for {url}: {e}")
                continue

            # Import phones found in wall posts/comments
            for phone_contact in wall_result.phones:
                normalized = normalize_phone(phone_contact.value)
                if not normalized:
                    continue
                # Determine source confidence
                source_key = 'vk_wall_by_subject'
                if 'by others' in phone_contact.source or 'tagged' in phone_contact.source:
                    source_key = 'vk_wall_by_others'
                score = _get_score(source_key)
                self.found_phones.append(DiscoveredPhone(
                    number=normalized,
                    source=source_key,
                    confidence=_score_to_label(score),
                    profile_name=display_name,
                    raw_value=phone_contact.value,
                    confidence_score=score,
                    sources=[source_key],
                ))

            # Import emails found in wall posts/comments
            for email_contact in wall_result.emails:
                email = email_contact.value.lower()
                source_key = 'vk_wall_by_subject'
                if 'by others' in email_contact.source or 'tagged' in email_contact.source:
                    source_key = 'vk_wall_by_others'
                score = _get_score(source_key)
                self.found_emails.append(DiscoveredEmail(
                    email=email,
                    source=source_key,
                    confidence=_score_to_label(score),
                    verified=False,
                    profile_name=display_name,
                    confidence_score=score,
                    sources=[source_key],
                ))

            # Store Telegram usernames as enrichment hints for later processing
            if wall_result.telegram_usernames:
                if not hasattr(self, '_telegram_hints'):
                    self._telegram_hints = []
                for tg_user in wall_result.telegram_usernames:
                    self._telegram_hints.append({
                        'username': tg_user,
                        'source': 'vk_wall_extraction',
                        'profile_url': url,
                    })
                logger.info(
                    f"VK wall extraction: found {len(wall_result.telegram_usernames)} "
                    f"Telegram usernames from {url}"
                )

            # Store Instagram usernames as enrichment hints
            if wall_result.instagram_usernames:
                if not hasattr(self, '_instagram_hints'):
                    self._instagram_hints = []
                for ig_user in wall_result.instagram_usernames:
                    self._instagram_hints.append({
                        'username': ig_user,
                        'source': 'vk_wall_extraction',
                        'profile_url': url,
                    })

            logger.info(
                f"Deep VK wall: {wall_result.posts_analyzed} posts, "
                f"{wall_result.comments_analyzed} comments, "
                f"{len(wall_result.phones)} phones, "
                f"{len(wall_result.emails)} emails"
            )

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

    def _guess_emails(self, social_profiles: list, full_name: str, birth_year: str = None):
        """Generate email guesses from usernames and name transliteration.

        Args:
            social_profiles: list of social profile dicts
            full_name: candidate's full name (confirmed_name preferred)
            birth_year: optional birth year string (e.g. "1990") for year-based patterns
        """
        usernames = set()
        for profile in social_profiles:
            username = (profile.get('username') or '').strip()
            if username and len(username) >= 3:
                # Skip default VK IDs like "id123456"
                if not (username.startswith('id') and username[2:].isdigit()):
                    usernames.add(username.lower())

        # Username-based guesses (with birth year patterns)
        for username in usernames:
            clean = re.sub(r'[^a-z0-9._-]', '', username)
            if len(clean) < 3:
                continue
            score = _get_score('email_guess')
            patterns = [clean]
            if birth_year:
                patterns.append(f'{clean}{birth_year[-2:]}')
                patterns.append(f'{clean}{birth_year}')
            for pat in patterns:
                for domain in GUESS_DOMAINS:
                    self.found_emails.append(DiscoveredEmail(
                        email=f'{pat}@{domain}',
                        source='email_guess',
                        confidence=_score_to_label(score),
                        verified=False,
                        profile_name=f'@{username}',
                        confidence_score=score,
                        sources=['email_guess'],
                    ))

        # Name-based guesses (transliterated + birth year)
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
                            base_patterns = [
                                f'{first_clean}.{last_clean}',
                                f'{last_clean}.{first_clean}',
                                f'{first_clean}{last_clean}',
                                f'{last_clean}{first_clean}',
                            ]
                            # Add birth year variants
                            year_patterns = []
                            if birth_year:
                                y2 = birth_year[-2:]
                                for bp in base_patterns:
                                    year_patterns.append(f'{bp}{y2}')
                                    year_patterns.append(f'{bp}{birth_year}')
                            all_patterns = base_patterns + year_patterns
                            for domain in NAME_GUESS_DOMAINS:
                                for pattern in all_patterns:
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

    # ── Step 4b: Hunter.io Corporate Email Search ──────────────────

    def _hunter_corporate_search(self, social_profiles: list, full_name: str):
        """Use Hunter.io to find corporate email if VK career employer is known.
        Requires HUNTER_API_KEY env var (free tier: 25/month)."""
        import os
        if not os.environ.get('HUNTER_API_KEY'):
            return

        # Collect employer names from VK profile career data
        employers = []
        for profile in social_profiles:
            if profile.get('platform') != 'vk':
                continue
            career = profile.get('career', [])
            if isinstance(career, list):
                for job in career:
                    company = job.get('company', '')
                    if company:
                        employers.append(company)

        # Also check other_contacts for employer hints from deep VK extraction
        # (stored by VKWallExtractor's _scan_profile_fields as type='employer')
        # These won't be in social_profiles directly, but we can check the hints

        if not employers:
            return

        try:
            from app.services.phase2.email_generator import (
                hunter_verify_email, hunter_domain_search,
                generate_corporate_emails, is_cyrillic,
            )
            from app.services.phase1.transliteration import transliterate
        except ImportError:
            logger.debug("Hunter.io/email_generator not available")
            return

        parts = (full_name or '').strip().split()
        first_name = parts[1] if len(parts) > 1 else ''
        last_name = parts[0] if parts else ''

        for employer in employers[:2]:  # Max 2 employers
            # Generate corporate email patterns
            corp_emails = generate_corporate_emails(first_name, last_name, employer)
            if not corp_emails:
                continue

            # Try Hunter.io verification on top corporate patterns
            for candidate in corp_emails[:3]:
                email = candidate.get('email', '')
                if not email:
                    continue

                result = hunter_verify_email(email)
                if result and result.get('result') == 'deliverable':
                    score = 0.80  # Hunter.io verified corporate email
                    self.found_emails.append(DiscoveredEmail(
                        email=email,
                        source='hunter_verified',
                        confidence=_score_to_label(score),
                        verified=True,
                        profile_name=f'Hunter.io ({employer})',
                        confidence_score=score,
                        sources=['hunter_verified'],
                    ))
                    logger.info(f"Hunter.io verified: {email} for {employer}")
                    break  # One verified is enough per employer

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

        executor = ThreadPoolExecutor(max_workers=3)
        try:
            futures = []
            for src in sources:
                futures.append(executor.submit(
                    src.query,
                    email=emails_to_check[0] if emails_to_check else None,
                    username=usernames[0] if usernames else None,
                    email_candidates=[{'email': e} for e in emails_to_check[1:]],
                ))

            try:
                for future in as_completed(futures, timeout=10):
                    try:
                        results = future.result(timeout=5)
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
                        logger.warning("Breach API query error: %s", e)
            except TimeoutError:
                logger.warning("Breach API: some queries timed out (30s)")
                for f in futures:
                    f.cancel()
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

    # ── Step 6.5: Breach Intelligence Analysis ──────────────────────────

    def _analyze_breach_intelligence(self) -> dict:
        """
        Analyze breach data to extract service registrations, old emails/phones,
        and financial exposure. Feeds newly discovered old emails and phones
        back into the contact discovery pipeline for deduplication.

        Returns breach intelligence dict (stored in result['breach_intelligence']).
        """
        # Collect unique emails and phones discovered so far
        emails = list({e.email for e in self.found_emails
                       if '@' in e.email and '*' not in e.email})[:10]
        phones = list({p.number for p in self.found_phones})[:10]

        if not emails and not phones:
            return {}

        from app.services.phase2.breach_checker import analyze_breach_intelligence

        logger.info(
            f"Breach intelligence: analyzing {len(emails)} emails, "
            f"{len(phones)} phones"
        )

        intel = analyze_breach_intelligence(emails=emails, phones=phones)

        if not intel:
            return {}

        # Feed old emails back into the discovery pipeline
        breach_score = _get_score('breach_api')
        for old_email in intel.get('old_emails', []):
            old_lower = old_email.lower()
            if not any(e.email == old_lower for e in self.found_emails):
                self.found_emails.append(DiscoveredEmail(
                    email=old_lower,
                    source='breach_api',
                    confidence=_score_to_label(breach_score),
                    verified=False,
                    profile_name='Breach Intelligence',
                    confidence_score=breach_score,
                    sources=['breach_intelligence'],
                ))

        # Feed old phones back into the discovery pipeline
        for old_phone in intel.get('old_phones', []):
            normalized = normalize_phone(old_phone)
            if normalized and not any(p.number == normalized for p in self.found_phones):
                self.found_phones.append(DiscoveredPhone(
                    number=normalized,
                    source='breach_api',
                    confidence=_score_to_label(breach_score),
                    profile_name='Breach Intelligence',
                    raw_value=old_phone,
                    confidence_score=breach_score,
                    sources=['breach_intelligence'],
                ))

        new_emails = len(intel.get('old_emails', []))
        new_phones = len(intel.get('old_phones', []))
        if new_emails or new_phones:
            logger.info(
                f"Breach intelligence: +{new_emails} old emails, "
                f"+{new_phones} old phones fed back into pipeline"
            )

        services = intel.get('services_used', [])
        if services:
            logger.info(
                f"Breach intelligence: {len(services)} services detected, "
                f"financial={intel.get('has_financial_services', False)}"
            )

        return intel

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

        # Step 8a: VK username oracle — removed (Feb 2026).
        # VK patched id.vk.com: masked hints no longer returned, only existence
        # confirmation — which Stage 3 already provides. No Chrome overhead needed.

        # Step 8b: Email/phone oracle (existing checkers)
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

        self._oracle_results.extend(all_results)

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

    # ── Step 8.5: Cross-Reference Partial Phones ─────────────────────

    def _cross_reference_partial_phones(self, check):
        """
        Attempt to complete partial/masked phones from the forgot-password oracle
        by cross-referencing against breach data and GetContact.

        Masked phone hints like "+7 916 ***-**-67" contain a prefix (area code)
        and suffix (last digits). We try to find the full number by:
        1. Querying LeakDB for records linked to the subject's known emails,
           then filtering for phones that match the visible pattern.
        2. Querying GetContact (if configured) with candidate phones to check
           if the returned name matches the subject.
        """
        if not self._oracle_results:
            return

        # Collect masked phone hints from oracle results
        partial_hints = []
        for result in self._oracle_results:
            if (result.get('exists') and
                    result.get('hint_type') == 'phone' and
                    result.get('masked_hint') and
                    '*' in result.get('masked_hint', '')):
                partial_hints.append(result['masked_hint'])

        if not partial_hints:
            return

        # Merge hints to get the best partial reconstruction
        try:
            from app.services.phase2.forgot_password_oracle import (
                cross_correlate_hints, _count_known_digits,
            )
        except ImportError:
            logger.debug("cross_correlate_hints not available")
            return

        correlated = cross_correlate_hints(self._oracle_results)
        merged_phone = correlated.get('merged_phone')
        known_digits = correlated.get('known_digits', 0)

        if not merged_phone:
            return

        if '*' not in merged_phone or known_digits >= 11:
            # All digits known — just normalize and add
            full = normalize_phone(merged_phone)
            if full and full.startswith('+7') and len(re.sub(r'\D', '', full)) == 11:
                self._add_completed_phone(
                    full, merged_phone, 'partial_phone_breach',
                    'Восстановление (объединение масок)',
                )
            return

        logger.info(
            f"Partial phone cross-ref: merged={merged_phone}, "
            f"known_digits={known_digits}/11, trying breach DB + GetContact"
        )

        # Build a regex pattern from the merged masked phone
        pattern = self._build_phone_pattern(merged_phone)
        if not pattern:
            return

        # ── 1. Breach DB cross-reference ──
        # Query LeakDB by email for linked phone records that match the pattern
        completed_phone = self._breach_db_phone_match(check, pattern, merged_phone)

        # ── 2. GetContact cross-reference (if no breach match) ──
        if not completed_phone:
            completed_phone = self._getcontact_phone_match(
                check, pattern, merged_phone,
            )

        # ── 3. Store partial if still unresolved ──
        if not completed_phone:
            # Keep the best merged partial — already added by oracle step,
            # but log that cross-ref didn't resolve it
            logger.info(
                f"Partial phone cross-ref: could not complete {merged_phone}, "
                f"storing as partial (requires verification)"
            )

    @staticmethod
    def _build_phone_pattern(merged_phone: str) -> Optional[re.Pattern]:
        """
        Build a regex pattern from a merged masked phone string.

        E.g., "+7 916 ***-45-67" → regex matching +7916XXXX4567
        where X is any digit.
        """
        # Extract digit/star sequence
        chars = []
        for ch in merged_phone:
            if ch.isdigit():
                chars.append(ch)
            elif ch == '*':
                chars.append(r'\d')
        if len(chars) < 7:
            return None

        # Pad to 11 digits if shorter (left-pad with \d)
        while len(chars) < 11:
            chars.insert(0, r'\d')

        regex_str = r'^\+?' + ''.join(chars) + '$'
        try:
            return re.compile(regex_str)
        except re.error:
            return None

    def _breach_db_phone_match(
        self, check, pattern: re.Pattern, merged_phone: str,
    ) -> Optional[str]:
        """Query LeakDB by subject's known emails; filter linked phones by pattern."""
        from app.services.phase2.sources.leak_sources import LeakDB

        db = LeakDB.get_instance()

        # Collect known emails (high-confidence only)
        emails_to_check = list({
            e.email for e in self.found_emails
            if e.confidence_score >= 0.50 and '@' in e.email and '*' not in e.email
        })[:10]

        # Also try subject's name in LeakDB
        candidates: list = []
        for email in emails_to_check:
            for rec in db.query_email(email):
                phone = rec.get('phone', '')
                if phone:
                    normalized = normalize_phone(phone)
                    if normalized and pattern.match(re.sub(r'\D', '', normalized)):
                        candidates.append(normalized)

        # Name-based lookup as well
        if check.full_name:
            for rec in db.query_name(check.full_name):
                phone = rec.get('phone', '')
                if phone:
                    normalized = normalize_phone(phone)
                    if normalized and pattern.match(re.sub(r'\D', '', normalized)):
                        candidates.append(normalized)

        # Deduplicate
        candidates = list(dict.fromkeys(candidates))

        if candidates:
            # Use the first match (breach DB is authoritative)
            completed = candidates[0]
            logger.info(
                f"Partial phone completed via breach DB: "
                f"{merged_phone} → {completed}"
            )
            self._add_completed_phone(
                completed, merged_phone, 'partial_phone_breach',
                f"LeakDB ({len(candidates)} совпадений)",
            )
            return completed

        return None

    def _getcontact_phone_match(
        self, check, pattern: re.Pattern, merged_phone: str,
    ) -> Optional[str]:
        """
        Try completing a partial phone via GetContact reverse lookup.

        Strategy: generate candidate full phone numbers from the pattern,
        query GetContact for each, and check if the returned name matches
        the investigation subject.
        """
        try:
            from app.services.phase2.sources.getcontact import GetContactSource
        except ImportError:
            return None

        gc = GetContactSource()
        credentials = gc._get_credentials()
        if not credentials:
            logger.debug("GetContact not configured — skipping partial phone cross-ref")
            return None

        # Generate candidate phone numbers from the masked pattern
        # Only feasible if few digits are unknown (≤3 unknowns → max 1000 combos)
        candidates = self._generate_phone_candidates(merged_phone, max_candidates=50)
        if not candidates:
            logger.debug(
                f"Too many unknown digits in {merged_phone} for GetContact brute-force"
            )
            return None

        subject_name = (check.full_name or '').lower().strip()
        if not subject_name:
            return None
        subject_parts = set(subject_name.split())

        logger.info(
            f"GetContact cross-ref: trying {len(candidates)} candidate phones "
            f"for pattern {merged_phone}"
        )

        from app.services.phase2.sources.getcontact import GetContactAPI

        token, aes_key, device_id = credentials
        try:
            api = GetContactAPI(token=token, aes_key=aes_key, device_id=device_id or '14130e29cebe9c39')
        except Exception as e:
            logger.warning(f"[ContactDiscovery] GetContact API init failed: {e}")
            return None

        for candidate in candidates:
            try:
                result = api.search_phone(candidate)
                if not result:
                    continue

                profile = result.get('result', {}).get('profile', {})
                if not profile:
                    profile = result.get('profile', {})
                display_name = (profile.get('displayName') or '').lower().strip()

                if not display_name:
                    continue

                # Check name overlap: at least one word from the subject name
                # matches a word in the GetContact display name
                gc_parts = set(display_name.split())
                overlap = subject_parts & gc_parts
                if overlap:
                    logger.info(
                        f"GetContact confirmed: {candidate} → "
                        f"'{display_name}' (matched: {overlap})"
                    )
                    self._add_completed_phone(
                        candidate, merged_phone, 'partial_phone_getcontact',
                        f"GetContact ({display_name})",
                    )
                    return candidate

            except Exception as e:
                logger.debug(f"GetContact query error for {candidate}: {e}")
                continue

        return None

    @staticmethod
    def _generate_phone_candidates(merged_phone: str, max_candidates: int = 50) -> list:
        """
        Generate all possible full phone numbers from a masked pattern.

        Only feasible when the number of unknown digits is small (≤2).
        Returns empty list if too many unknowns.
        """
        # Extract digit/star sequence
        chars = []
        for ch in merged_phone:
            if ch.isdigit():
                chars.append(ch)
            elif ch == '*':
                chars.append('*')

        # Pad to 11 if needed
        while len(chars) < 11:
            chars.insert(0, '*')

        unknown_positions = [i for i, c in enumerate(chars) if c == '*']
        num_unknowns = len(unknown_positions)

        # Only brute-force if ≤2 unknowns (max 100 candidates)
        if num_unknowns > 2 or num_unknowns == 0:
            return []

        candidates = []

        def _recurse(pos_idx: int, current: list):
            if len(candidates) >= max_candidates:
                return
            if pos_idx >= len(unknown_positions):
                phone = '+' + ''.join(current)
                candidates.append(phone)
                return
            p = unknown_positions[pos_idx]
            for d in '0123456789':
                current[p] = d
                _recurse(pos_idx + 1, current)
            current[p] = '*'  # restore

        _recurse(0, list(chars))
        return candidates

    def _add_completed_phone(
        self,
        full_number: str,
        original_hint: str,
        source_key: str,
        profile_name: str,
    ):
        """Add a completed phone number, avoiding duplicates."""
        normalized = normalize_phone(full_number)
        if not normalized or not normalized.startswith('+7'):
            return

        # Check if already known
        if any(p.number == normalized for p in self.found_phones):
            # Upgrade existing entry's confidence if our source is better
            for p in self.found_phones:
                if p.number == normalized:
                    new_score = _get_score(source_key)
                    if new_score > p.confidence_score:
                        p.confidence_score = new_score
                        p.confidence = _score_to_label(new_score)
                    if source_key not in p.sources:
                        p.sources.append(source_key)
                    break
            return

        score = _get_score(source_key)
        self.found_phones.append(DiscoveredPhone(
            number=normalized,
            source=source_key,
            confidence=_score_to_label(score),
            profile_name=profile_name,
            raw_value=original_hint,
            confidence_score=score,
            sources=[source_key],
        ))

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

        # Apply graduated cross-source boost and finalize
        for normalized, phone in phone_map.items():
            phone.sources = phone_sources_map.get(normalized, [phone.source])
            source_count = len(set(phone.sources))
            boost = CROSS_SOURCE_BOOST_MAP.get(source_count, CROSS_SOURCE_BOOST_DEFAULT)
            if boost > 0:
                phone.confidence_score = min(
                    MAX_CONFIDENCE,
                    phone.confidence_score + boost,
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

        # Apply graduated cross-source boost and finalize
        for lower, email in email_map.items():
            email.sources = email_sources_map.get(lower, [email.source])
            source_count = len(set(email.sources))
            boost = CROSS_SOURCE_BOOST_MAP.get(source_count, CROSS_SOURCE_BOOST_DEFAULT)
            if boost > 0:
                email.confidence_score = min(
                    MAX_CONFIDENCE,
                    email.confidence_score + boost,
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
