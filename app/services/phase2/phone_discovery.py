"""
Phone Discovery Service - VK API Implementation
================================================
Discovers phone numbers using VK API methods that actually work.

Methods (ordered by effectiveness):
1. VK API users.get with contacts field - extract phone from profile
2. VK API wall.get - scan wall posts for phone patterns
3. Username analysis - extract phone patterns from usernames
4. Email-to-phone extraction - some Russians use phone@domain.ru
5. Telegram public bio scraping - check for phone in bio
"""

import logging
import os
import re
import time
from typing import List, Dict, Optional, Set
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor
import requests
from bs4 import BeautifulSoup

from .russian_phone_validator import RussianPhoneValidator, PhoneInfo

logger = logging.getLogger(__name__)


@dataclass
class DiscoveredPhone:
    """A phone discovered during investigation."""
    number: str
    source: str
    confidence: str  # "high", "medium", "low"
    verified: bool = False
    carrier: Optional[str] = None
    region: Optional[str] = None
    telegram_url: Optional[str] = None  # Link to Telegram profile if phone came from there


@dataclass
class PhoneDiscoveryResults:
    """Complete results from phone discovery."""
    phones: List[DiscoveredPhone] = field(default_factory=list)
    additional_profiles: List[Dict] = field(default_factory=list)  # Telegram profiles found via cross-ref
    candidates_generated: int = 0
    candidates_verified: int = 0
    discovery_time: float = 0
    errors: List[str] = field(default_factory=list)


# Common Russian phone patterns in various formats
PHONE_PATTERNS = [
    r'\+7[\s\-\(]?(\d{3})[\s\-\)]?(\d{3})[\s\-]?(\d{2})[\s\-]?(\d{2})',
    r'8[\s\-\(]?(\d{3})[\s\-\)]?(\d{3})[\s\-]?(\d{2})[\s\-]?(\d{2})',
    r'\+7\s*\d{10}',
    r'8\s*\d{10}',
    r'(?<!\d)9\d{9}(?!\d)',  # 10-digit starting with 9
    r'(?:tel|phone|mob|mobile|whatsapp|telegram|viber|tg)[\s:=\-]*\+?[78]?\s*[\(\-]?\d{3}[\)\-\s]?\d{3}[\-\s]?\d{2}[\-\s]?\d{2}',
]

# Usernames that might contain phone patterns
USERNAME_PHONE_PATTERNS = [
    r'^[78]?9\d{9}$',  # Pure phone number as username
    r'^id([78]9\d{9})$',  # id + phone
    r'(\d{10})(?:_|$)',  # 10 digits at end
]


class PhoneDiscoveryService:
    """
    Phone discovery service using multiple methods.
    Designed to find phones associated with a target.
    """

    def __init__(
        self,
        max_candidates: int = 50,
        verify_timeout: float = 10.0,
        max_concurrent: int = 5
    ):
        self.max_candidates = max_candidates
        self.verify_timeout = verify_timeout
        self.max_concurrent = max_concurrent
        self.validator = RussianPhoneValidator()
        self._executor = ThreadPoolExecutor(max_workers=5)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

    def discover_sync(
        self,
        first_name: str,
        last_name: str,
        usernames: List[str],
        profile_urls: List[Dict] = None,
        emails: List[str] = None
    ) -> PhoneDiscoveryResults:
        """
        Synchronous phone discovery.

        Args:
            first_name: Target's first name
            last_name: Target's last name
            usernames: Known usernames from Phase 1
            profile_urls: Profile URLs with platform info
            emails: Found emails (may contain phone patterns)

        Returns:
            PhoneDiscoveryResults with discovered phones
        """
        start_time = time.time()
        results = PhoneDiscoveryResults()
        all_phones: Dict[str, DiscoveredPhone] = {}

        logger.info(f"Starting phone discovery: {first_name} {last_name}")

        try:
            # Method 1: VK API users.get with contacts field (BEST method)
            if profile_urls:
                vk_urls = [p for p in profile_urls if p.get('platform', '').lower() == 'vk']
                for profile in vk_urls[:3]:
                    api_phones = self._extract_via_vk_api(profile.get('url', ''))
                    for phone in api_phones:
                        key = self._normalize_key(phone.number)
                        if key not in all_phones:
                            all_phones[key] = phone

            # Method 2: VK API wall.get - scan posts for phone numbers
            if profile_urls:
                vk_urls = [p for p in profile_urls if p.get('platform', '').lower() == 'vk']
                for profile in vk_urls[:2]:
                    wall_phones = self._extract_from_vk_wall(profile.get('url', ''))
                    for phone in wall_phones:
                        key = self._normalize_key(phone.number)
                        if key not in all_phones:
                            all_phones[key] = phone

            # Method 3: Extract phones from usernames
            username_phones = self._extract_from_usernames(usernames)
            for phone in username_phones:
                key = self._normalize_key(phone.number)
                if key not in all_phones:
                    all_phones[key] = phone

            # Method 4: Extract from emails (some Russian emails use phone as local part)
            if emails:
                email_phones = self._extract_from_emails(emails)
                for phone in email_phones:
                    key = self._normalize_key(phone.number)
                    if key not in all_phones:
                        all_phones[key] = phone

            # Method 5: VK→Telegram username cross-reference
            if profile_urls:
                vk_profiles = [p for p in profile_urls if p.get('platform', '').lower() == 'vk']
                tg_phones, tg_profiles = self._cross_reference_telegram(
                    vk_profiles, first_name, last_name
                )
                for phone in tg_phones:
                    key = self._normalize_key(phone.number)
                    if key not in all_phones:
                        all_phones[key] = phone
                results.additional_profiles.extend(tg_profiles)

            # Method 6: Generate phone candidates from usernames containing digits
            generated_phones = self._generate_phone_candidates(usernames, first_name, last_name)
            for phone in generated_phones:
                key = self._normalize_key(phone.number)
                if key not in all_phones:
                    all_phones[key] = phone

            results.candidates_generated = len(all_phones)

        except Exception as e:
            results.errors.append(f"Discovery error: {str(e)}")
            logger.error(f"Phone discovery error: {e}")

        # Validate and filter (only keep mobile numbers - prefix 9XX)
        valid_phones = []
        for phone in all_phones.values():
            info = self.validator.validate(phone.number)
            if info.is_valid and info.is_mobile:  # Only mobile numbers
                phone.number = info.display_format
                phone.carrier = info.carrier_hint
                phone.region = info.region
                valid_phones.append(phone)

        results.phones = valid_phones
        results.candidates_verified = len(valid_phones)
        results.discovery_time = time.time() - start_time

        logger.info(f"Phone discovery complete: {len(valid_phones)} phones in {results.discovery_time:.1f}s")

        return results

    def _extract_from_usernames(self, usernames: List[str]) -> List[DiscoveredPhone]:
        """Extract phone numbers hidden in usernames."""
        phones = []

        for username in usernames:
            # Check if username IS a phone number
            digits = re.sub(r'\D', '', username)

            if len(digits) == 10 and digits.startswith('9'):
                phones.append(DiscoveredPhone(
                    number='+7' + digits,
                    source=f"Username pattern ({username})",
                    confidence="medium"
                ))
            elif len(digits) == 11 and (digits.startswith('7') or digits.startswith('8')):
                normalized = '+7' + digits[1:]
                phones.append(DiscoveredPhone(
                    number=normalized,
                    source=f"Username pattern ({username})",
                    confidence="medium"
                ))

            # Check for phone patterns in username
            for pattern in USERNAME_PHONE_PATTERNS:
                match = re.search(pattern, username, re.IGNORECASE)
                if match:
                    found = match.group(1) if match.lastindex else match.group(0)
                    found_digits = re.sub(r'\D', '', found)
                    if len(found_digits) >= 10:
                        if len(found_digits) == 10:
                            normalized = '+7' + found_digits
                        else:
                            normalized = '+7' + found_digits[-10:]
                        phones.append(DiscoveredPhone(
                            number=normalized,
                            source=f"Username pattern ({username})",
                            confidence="low"
                        ))

        return phones

    @staticmethod
    def _normalize_key(phone: str) -> str:
        """Normalize phone to digits-only key for deduplication."""
        return re.sub(r'\D', '', phone)[-10:]

    def _extract_via_vk_api(self, profile_url: str) -> List[DiscoveredPhone]:
        """
        Extract phones from VK profile via API (users.get with contacts fields).
        This is the most reliable method — works with service token.
        """
        phones = []
        vk_token = os.environ.get('VK_SERVICE_TOKEN', '')
        if not vk_token:
            logger.debug("No VK_SERVICE_TOKEN, skipping VK API phone extraction")
            return phones

        # Extract user ID from URL
        user_id = None
        m = re.search(r'vk\.com/id(\d+)', profile_url)
        if m:
            user_id = m.group(1)
        else:
            m = re.search(r'vk\.com/([a-zA-Z0-9_.]+)', profile_url)
            if m:
                user_id = m.group(1)

        if not user_id:
            return phones

        try:
            resp = self.session.get(
                'https://api.vk.com/method/users.get',
                params={
                    'user_ids': user_id,
                    'fields': 'contacts,mobile_phone,home_phone,connections,site,status,about',
                    'access_token': vk_token,
                    'v': '5.199',
                },
                timeout=10,
            )
            data = resp.json()

            if 'error' in data:
                logger.warning(f"VK API error: {data['error'].get('error_msg', '')}")
                return phones

            users = data.get('response', [])
            if not users:
                return phones

            user = users[0]

            # Extract mobile_phone
            mobile = user.get('mobile_phone', '')
            if mobile and len(mobile) > 5:
                info = self.validator.validate(mobile)
                if info.is_valid:
                    phones.append(DiscoveredPhone(
                        number=info.display_format,
                        source='VK profile (mobile_phone)',
                        confidence='high',
                        carrier=info.carrier_hint,
                        region=info.region,
                    ))
                    logger.info(f"VK API: found mobile_phone: {info.display_format}")

            # Extract home_phone
            home = user.get('home_phone', '')
            if home and len(home) > 5:
                info = self.validator.validate(home)
                if info.is_valid:
                    phones.append(DiscoveredPhone(
                        number=info.display_format,
                        source='VK profile (home_phone)',
                        confidence='high',
                        carrier=info.carrier_hint,
                        region=info.region,
                    ))

            # Extract from contacts field (nested structure)
            contacts = user.get('contacts', {})
            if isinstance(contacts, dict):
                for field_name in ('mobile_phone', 'home_phone'):
                    val = contacts.get(field_name, '')
                    if val and len(val) > 5:
                        info = self.validator.validate(val)
                        if info.is_valid:
                            phones.append(DiscoveredPhone(
                                number=info.display_format,
                                source=f'VK contacts ({field_name})',
                                confidence='high',
                                carrier=info.carrier_hint,
                                region=info.region,
                            ))

            # Extract phones from about/status text
            for text_field in ('about', 'status', 'activities', 'interests'):
                text = user.get(text_field, '')
                if text:
                    found = self.validator.extract_phones(text)
                    for info in found:
                        phones.append(DiscoveredPhone(
                            number=info.display_format,
                            source=f'VK profile {text_field}',
                            confidence='medium',
                            carrier=info.carrier_hint,
                            region=info.region,
                        ))

            # Extract from site field (sometimes contains phone)
            site = user.get('site', '')
            if site:
                found = self.validator.extract_phones(site)
                for info in found:
                    phones.append(DiscoveredPhone(
                        number=info.display_format,
                        source='VK profile site field',
                        confidence='medium',
                        carrier=info.carrier_hint,
                        region=info.region,
                    ))

        except Exception as e:
            logger.warning(f"VK API phone extraction error: {e}")

        logger.info(f"VK API users.get found {len(phones)} phones for {profile_url}")
        return phones

    def _extract_from_vk_wall(self, profile_url: str) -> List[DiscoveredPhone]:
        """
        Scan VK wall posts for phone numbers via VK API wall.get.
        Works with service token for public profiles.
        """
        phones = []
        vk_token = os.environ.get('VK_SERVICE_TOKEN', '')
        if not vk_token:
            return phones

        # Extract user ID
        user_id = None
        m = re.search(r'vk\.com/id(\d+)', profile_url)
        if m:
            user_id = m.group(1)
        else:
            m = re.search(r'vk\.com/([a-zA-Z0-9_.]+)', profile_url)
            if m:
                user_id = m.group(1)

        if not user_id:
            return phones

        try:
            params = {
                'count': 100,
                'access_token': vk_token,
                'v': '5.199',
            }
            if user_id.isdigit():
                params['owner_id'] = user_id
            else:
                params['domain'] = user_id

            resp = self.session.get(
                'https://api.vk.com/method/wall.get',
                params=params,
                timeout=15,
            )
            data = resp.json()

            if 'error' in data:
                err = data['error']
                code = err.get('error_code', 0)
                if code == 15:
                    logger.debug(f"VK wall access denied for {user_id} (private profile)")
                else:
                    logger.debug(f"VK wall.get error {code}: {err.get('error_msg', '')}")
                return phones

            posts = data.get('response', {}).get('items', [])
            logger.info(f"VK wall.get: scanning {len(posts)} posts for {user_id}")

            for post in posts:
                text = post.get('text', '')
                if not text:
                    continue

                # Extract phones from post text
                for pattern in PHONE_PATTERNS:
                    matches = re.findall(pattern, text, re.IGNORECASE)
                    for match in matches:
                        if isinstance(match, tuple):
                            digits = ''.join(match)
                        else:
                            digits = re.sub(r'\D', '', str(match))

                        if len(digits) >= 10:
                            normalized = '+7' + digits[-10:]
                            info = self.validator.validate(normalized)
                            if info.is_valid and info.is_mobile:
                                post_id = post.get('id', '')
                                owner_id = post.get('owner_id', user_id)
                                # Get context around the phone number
                                context = text[:100] if len(text) > 100 else text
                                phones.append(DiscoveredPhone(
                                    number=info.display_format,
                                    source=f'VK wall post (wall{owner_id}_{post_id})',
                                    confidence='high' if any(kw in text.lower() for kw in
                                        ['тел', 'phone', 'звон', 'call', 'whatsapp', 'viber'])
                                        else 'medium',
                                    carrier=info.carrier_hint,
                                    region=info.region,
                                ))

        except Exception as e:
            logger.warning(f"VK wall extraction error: {e}")

        logger.info(f"VK wall.get found {len(phones)} phones in posts for {user_id}")
        return phones

    def _extract_from_emails(self, emails: List[str]) -> List[DiscoveredPhone]:
        """Extract phone numbers from email local parts (some Russians use phone@domain.ru)."""
        phones = []

        for email in emails:
            if '@' not in email:
                continue

            local_part = email.split('@')[0]

            # Check if local part is a phone number
            digits = re.sub(r'\D', '', local_part)

            if len(digits) == 10 and digits.startswith('9'):
                phones.append(DiscoveredPhone(
                    number='+7' + digits,
                    source=f"Email local part ({email})",
                    confidence="medium"
                ))
            elif len(digits) == 11 and digits.startswith(('7', '8')):
                phones.append(DiscoveredPhone(
                    number='+7' + digits[1:],
                    source=f"Email local part ({email})",
                    confidence="medium"
                ))

        return phones

    def _generate_phone_candidates(self, usernames: List[str], first_name: str, last_name: str) -> List[DiscoveredPhone]:
        """Generate potential phone numbers from username patterns."""
        phones = []
        seen = set()

        # Common Russian mobile prefixes (900-999 range)
        common_prefixes = ['926', '925', '916', '915', '903', '905', '909', '963', '965', '968', '977', '999']

        for username in usernames:
            # Extract all digit sequences from username
            digits_in_username = re.findall(r'\d+', username)

            for digits in digits_in_username:
                # If it looks like a 7-digit suffix (common in Russian usernames)
                if len(digits) == 7:
                    for prefix in common_prefixes[:3]:  # Try top 3 prefixes
                        candidate = f'+7{prefix}{digits}'
                        info = self.validator.validate(candidate)
                        if info.is_valid and info.is_mobile and candidate not in seen:
                            seen.add(candidate)
                            phones.append(DiscoveredPhone(
                                number=info.display_format,
                                source=f"Username digits pattern ({username})",
                                confidence="low"
                            ))

                # If it's exactly 10 digits starting with 9
                elif len(digits) == 10 and digits.startswith('9'):
                    candidate = f'+7{digits}'
                    info = self.validator.validate(candidate)
                    if info.is_valid and info.is_mobile and candidate not in seen:
                        seen.add(candidate)
                        phones.append(DiscoveredPhone(
                            number=info.display_format,
                            source=f"Username phone pattern ({username})",
                            confidence="medium"
                        ))

        return phones[:10]  # Limit to 10 candidates

    def _cross_reference_telegram(
        self,
        vk_profiles: List[Dict],
        first_name: str,
        last_name: str,
    ) -> tuple:
        """
        Cross-reference VK profiles against Telegram.
        Returns (phones, additional_profiles) tuple.
        """
        phones = []
        profiles = []

        try:
            from .telegram_crossref import TelegramCrossRef

            # Check VK connections for Telegram username first
            vk_connections_tg = self._get_vk_telegram_connection(vk_profiles)

            checker = TelegramCrossRef(request_delay=1.5)
            try:
                tg_results = checker.cross_reference_vk_profiles(
                    vk_profiles=vk_profiles,
                    first_name=first_name,
                    last_name=last_name,
                    vk_connections_telegram=vk_connections_tg,
                )

                for tg in tg_results:
                    tg_url = f'https://t.me/{tg.username}'

                    # Extract phones from bio
                    for phone_num in tg.phones_in_bio:
                        phones.append(DiscoveredPhone(
                            number=phone_num,
                            source=f'Telegram bio (@{tg.username})',
                            confidence='medium' if tg.name_match else 'low',
                            telegram_url=tg_url,
                        ))

                    # Always store the Telegram profile as additional profile
                    note = ''
                    if not tg.name_match and tg.display_name:
                        note = 'Совпадение username, но имя отличается — возможно другой человек'

                    profiles.append({
                        'platform': 'telegram',
                        'username': tg.username,
                        'url': tg_url,
                        'display_name': tg.display_name,
                        'bio': tg.bio[:200] if tg.bio else '',
                        'name_match': tg.name_match,
                        'confidence': tg.confidence,
                        'source': tg.source,
                        'note': note,
                    })

                    logger.info(
                        f"Telegram cross-ref: @{tg.username} — "
                        f"name_match={tg.name_match}, phones={len(tg.phones_in_bio)}, "
                        f"confidence={tg.confidence}"
                    )

            finally:
                checker.close()

        except ImportError:
            logger.warning("telegram_crossref module not available")
        except Exception as e:
            logger.warning(f"Telegram cross-reference error: {e}")

        return phones, profiles

    def _get_vk_telegram_connection(self, vk_profiles: List[Dict]) -> Optional[str]:
        """Check VK API connections field for linked Telegram username."""
        vk_token = os.environ.get('VK_SERVICE_TOKEN', '')
        if not vk_token:
            return None

        for profile in vk_profiles[:2]:
            url = profile.get('url', '')
            user_id = None
            m = re.search(r'vk\.com/id(\d+)', url)
            if m:
                user_id = m.group(1)
            else:
                m = re.search(r'vk\.com/([a-zA-Z0-9_.]+)', url)
                if m:
                    user_id = m.group(1)

            if not user_id:
                continue

            try:
                resp = self.session.get(
                    'https://api.vk.com/method/users.get',
                    params={
                        'user_ids': user_id,
                        'fields': 'connections',
                        'access_token': vk_token,
                        'v': '5.199',
                    },
                    timeout=10,
                )
                data = resp.json()
                users = data.get('response', [])
                if users:
                    tg_username = users[0].get('telegram')
                    if tg_username:
                        logger.info(f"VK connections: found Telegram username @{tg_username}")
                        return tg_username
            except Exception as e:
                logger.debug(f"VK connections check error: {e}")

        return None

    def close(self):
        """Clean up resources."""
        self._executor.shutdown(wait=False)
        self.session.close()


# Convenience functions
def discover_phones(
    first_name: str,
    last_name: str,
    usernames: List[str],
    profile_urls: List[Dict] = None,
    emails: List[str] = None
) -> PhoneDiscoveryResults:
    """Convenience function for phone discovery."""
    service = PhoneDiscoveryService()
    try:
        return service.discover_sync(first_name, last_name, usernames, profile_urls, emails)
    finally:
        service.close()
