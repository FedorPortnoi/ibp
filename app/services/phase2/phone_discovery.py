"""
Phone Discovery Service - Fast Implementation
==============================================
Discovers and verifies phone numbers using multiple methods in parallel.

Methods:
1. VK API search by name - extracts phones from matching profiles
2. Username analysis - extracts phone patterns from usernames
3. Profile page deep scraping - enhanced regex for phone extraction
4. Phone verification via known services
5. Pattern generation from email addresses (some use phone as email prefix)
"""

import asyncio
import aiohttp
import logging
import re
import time
import json
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


@dataclass
class PhoneDiscoveryResults:
    """Complete results from phone discovery."""
    phones: List[DiscoveredPhone] = field(default_factory=list)
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
            # Method 1: Extract phones from usernames
            username_phones = self._extract_from_usernames(usernames)
            for phone in username_phones:
                key = phone.number
                if key not in all_phones:
                    all_phones[key] = phone

            # Method 2: Search VK by name
            vk_phones = self._search_vk_by_name(first_name, last_name)
            for phone in vk_phones:
                key = phone.number
                if key not in all_phones:
                    all_phones[key] = phone

            # Method 2b: Search OK.ru by name
            ok_phones = self._search_ok_by_name(first_name, last_name)
            for phone in ok_phones:
                key = phone.number
                if key not in all_phones:
                    all_phones[key] = phone

            # Method 3: Deep scrape profiles
            if profile_urls:
                scrape_phones = self._deep_scrape_profiles(profile_urls[:5])
                for phone in scrape_phones:
                    key = phone.number
                    if key not in all_phones:
                        all_phones[key] = phone

            # Method 4: Extract from emails (some Russian emails use phone as local part)
            if emails:
                email_phones = self._extract_from_emails(emails)
                for phone in email_phones:
                    key = phone.number
                    if key not in all_phones:
                        all_phones[key] = phone

            # Method 5: Check Telegram for phone (public channels sometimes show)
            tg_phones = self._check_telegram_usernames(usernames[:5])
            for phone in tg_phones:
                key = phone.number
                if key not in all_phones:
                    all_phones[key] = phone

            # Method 6: Generate phone candidates from usernames containing digits
            generated_phones = self._generate_phone_candidates(usernames, first_name, last_name)
            for phone in generated_phones:
                key = phone.number
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

    def _transliterate_to_cyrillic(self, text: str) -> str:
        """Transliterate Latin text to Cyrillic (Russian)."""
        # Reverse transliteration map
        latin_to_cyrillic = {
            'a': 'a', 'b': 'b', 'v': 'v', 'g': 'g', 'd': 'd', 'e': 'e',
            'zh': 'zh', 'z': 'z', 'i': 'i', 'y': 'j', 'k': 'k', 'l': 'l',
            'm': 'm', 'n': 'n', 'o': 'o', 'p': 'p', 'r': 'r', 's': 's',
            't': 't', 'u': 'u', 'f': 'f', 'kh': 'h', 'ts': 'c', 'ch': 'ch',
            'sh': 'sh', 'sch': 'sch',
        }
        # Common Russian first names in Cyrillic
        russian_names = {
            'svetlana': 'Cветлана',
            'tikhon': 'Тихон',
            'daniil': 'Даниил',
            'daniel': 'Даниил',
            'pavel': 'Павел',
            'alexander': 'Александр',
            'sergey': 'Сергей',
            'dmitry': 'Дмитрий',
            'ivan': 'Иван',
            'nikolay': 'Николай',
            'mikhail': 'Михаил',
            'andrey': 'Андрей',
            'alexey': 'Алексей',
            'vladimir': 'Владимир',
            'viktor': 'Виктор',
            'maria': 'Мария',
            'anna': 'Анна',
            'elena': 'Елена',
            'olga': 'Ольга',
            'natalia': 'Наталья',
            'tatiana': 'Татьяна',
            'irina': 'Ирина',
            'ekaterina': 'Екатерина',
        }
        text_lower = text.lower().strip()
        return russian_names.get(text_lower, text)

    def _search_vk_by_name(self, first_name: str, last_name: str) -> List[DiscoveredPhone]:
        """Search VK for users by name and extract phones from profiles."""
        phones = []

        # Try Cyrillic versions
        first_cyrillic = self._transliterate_to_cyrillic(first_name)
        last_cyrillic = self._transliterate_to_cyrillic(last_name)

        try:
            # Try multiple VK search approaches - both Latin and Cyrillic
            search_queries = [
                f"{first_name} {last_name}",
                f"{last_name} {first_name}",
                f"{first_cyrillic} {last_cyrillic}",
                f"{last_cyrillic} {first_cyrillic}",
                # Fallback: first name only (common Russian names)
                first_name,
                first_cyrillic,
            ]
            # Remove duplicates while preserving order
            search_queries = list(dict.fromkeys(search_queries))[:4]  # Limit to 4 queries

            for query in search_queries:
                # VK search URL
                search_url = f"https://vk.com/search?c[name]=1&c[q]={query.replace(' ', '%20')}&c[section]=people"

                logger.debug(f"VK search: {search_url}")

                response = self.session.get(search_url, timeout=15)
                if response.status_code != 200:
                    continue

                soup = BeautifulSoup(response.text, 'html.parser')

                # Find profile links in search results - try multiple selectors
                profile_links = (
                    soup.select('.people_row a.simple_fit_item') or
                    soup.select('.search_result a[href^="/"]') or
                    soup.select('.users_list_row a[href^="/"]') or
                    soup.select('a[href^="/id"]')
                )[:5]

                for link in profile_links:
                    href = link.get('href', '')
                    if not href:
                        continue

                    # Skip non-profile links
                    if any(x in href.lower() for x in ['search', 'settings', 'login', 'away', 'feed']):
                        continue

                    profile_url = f"https://vk.com{href}" if href.startswith('/') else href

                    logger.debug(f"Scraping VK profile: {profile_url}")
                    profile_phones = self._scrape_vk_profile(profile_url)
                    phones.extend(profile_phones)

                    if len(phones) >= 5:
                        break

                    time.sleep(0.5)  # Rate limiting

                if phones:
                    break  # Found phones, stop searching

        except Exception as e:
            logger.debug(f"VK name search error: {e}")

        logger.info(f"VK name search found {len(phones)} phones for '{first_name} {last_name}'")
        return phones

    def _search_ok_by_name(self, first_name: str, last_name: str) -> List[DiscoveredPhone]:
        """Search OK.ru (Odnoklassniki) for users by name and extract phones."""
        phones = []

        try:
            # Try Cyrillic version
            first_cyrillic = self._transliterate_to_cyrillic(first_name)
            last_cyrillic = self._transliterate_to_cyrillic(last_name)

            search_queries = [
                f"{first_name} {last_name}",
                f"{first_cyrillic} {last_cyrillic}",
            ]
            search_queries = list(dict.fromkeys(search_queries))

            for query in search_queries[:2]:
                # OK.ru search URL
                search_url = f"https://ok.ru/search/profiles/{query.replace(' ', '%20')}"

                logger.debug(f"OK search: {search_url}")

                response = self.session.get(search_url, timeout=15)
                if response.status_code != 200:
                    continue

                soup = BeautifulSoup(response.text, 'html.parser')

                # Find profile links
                profile_links = (
                    soup.select('.ucard-v__link') or
                    soup.select('.card-v__link') or
                    soup.select('a[href*="/profile/"]')
                )[:5]

                for link in profile_links:
                    href = link.get('href', '')
                    if not href:
                        continue

                    profile_url = f"https://ok.ru{href}" if href.startswith('/') else href

                    profile_phones = self._scrape_ok_profile(profile_url)
                    phones.extend(profile_phones)

                    if len(phones) >= 3:
                        break

                    time.sleep(0.5)

                if phones:
                    break

        except Exception as e:
            logger.debug(f"OK name search error: {e}")

        logger.info(f"OK name search found {len(phones)} phones")
        return phones

    def _scrape_ok_profile(self, url: str) -> List[DiscoveredPhone]:
        """Scrape an OK.ru profile for phone numbers."""
        phones = []

        try:
            response = self.session.get(url, timeout=10)
            if response.status_code != 200:
                return phones

            text = response.text

            # Extract phones from page content
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
                            phones.append(DiscoveredPhone(
                                number=info.display_format,
                                source=f"OK.ru profile ({url})",
                                confidence="high"
                            ))

        except Exception as e:
            logger.debug(f"OK profile scrape error: {e}")

        return phones

    def _scrape_vk_profile(self, url: str) -> List[DiscoveredPhone]:
        """Scrape a VK profile for phone numbers."""
        phones = []

        try:
            response = self.session.get(url, timeout=10)
            if response.status_code != 200:
                return phones

            text = response.text

            # Extract phones from page content
            for pattern in PHONE_PATTERNS:
                matches = re.findall(pattern, text, re.IGNORECASE)
                for match in matches:
                    if isinstance(match, tuple):
                        # Pattern with groups
                        digits = ''.join(match)
                    else:
                        digits = re.sub(r'\D', '', str(match))

                    if len(digits) >= 10:
                        normalized = '+7' + digits[-10:]
                        phones.append(DiscoveredPhone(
                            number=normalized,
                            source=f"VK profile ({url})",
                            confidence="high"
                        ))

            # Also check meta tags and JSON data
            soup = BeautifulSoup(text, 'html.parser')

            # Look in meta description
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            if meta_desc:
                desc_text = meta_desc.get('content', '')
                desc_phones = self.validator.extract_phones(desc_text)
                for info in desc_phones:
                    phones.append(DiscoveredPhone(
                        number=info.display_format,
                        source=f"VK profile meta ({url})",
                        confidence="high"
                    ))

            # Look in script tags for phone data
            for script in soup.find_all('script'):
                script_text = script.string or ''
                if 'mobile_phone' in script_text or 'phone' in script_text.lower():
                    # Try to extract phone from JSON-like data
                    phone_match = re.search(r'"(?:mobile_phone|phone|tel)":\s*"([^"]+)"', script_text)
                    if phone_match:
                        phone_val = phone_match.group(1)
                        if phone_val:
                            info = self.validator.validate(phone_val)
                            if info.is_valid:
                                phones.append(DiscoveredPhone(
                                    number=info.display_format,
                                    source=f"VK profile data ({url})",
                                    confidence="high"
                                ))

        except Exception as e:
            logger.debug(f"VK profile scrape error for {url}: {e}")

        return phones

    def _deep_scrape_profiles(self, profiles: List[Dict]) -> List[DiscoveredPhone]:
        """Deep scrape profile pages for phone numbers."""
        phones = []

        for profile in profiles:
            url = profile.get('url', '')
            platform = profile.get('platform', '')

            if not url:
                continue

            try:
                response = self.session.get(url, timeout=10)
                if response.status_code != 200:
                    continue

                text = response.text

                # Extract all phone patterns
                for pattern in PHONE_PATTERNS:
                    matches = re.findall(pattern, text, re.IGNORECASE)
                    for match in matches:
                        if isinstance(match, tuple):
                            digits = ''.join(match)
                        else:
                            digits = re.sub(r'\D', '', str(match))

                        if len(digits) >= 10:
                            normalized = '+7' + digits[-10:]

                            # Verify it looks valid
                            info = self.validator.validate(normalized)
                            if info.is_valid:
                                phones.append(DiscoveredPhone(
                                    number=info.display_format,
                                    source=f"{platform.upper()} profile deep scan",
                                    confidence="high" if 'contact' in text.lower() else "medium"
                                ))

                time.sleep(0.3)

            except Exception as e:
                logger.debug(f"Deep scrape error for {url}: {e}")

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

    def _check_telegram_usernames(self, usernames: List[str]) -> List[DiscoveredPhone]:
        """Check Telegram public profiles for phone hints."""
        phones = []

        for username in usernames:
            try:
                url = f"https://t.me/{username}"
                response = self.session.get(url, timeout=10)

                if response.status_code != 200:
                    continue

                text = response.text

                # Look for phone patterns in Telegram preview page
                soup = BeautifulSoup(text, 'html.parser')

                # Check page description
                desc = soup.select_one('.tgme_page_description')
                if desc:
                    desc_text = desc.get_text()
                    found_phones = self.validator.extract_phones(desc_text)
                    for info in found_phones:
                        phones.append(DiscoveredPhone(
                            number=info.display_format,
                            source=f"Telegram bio (@{username})",
                            confidence="high"
                        ))

                time.sleep(0.3)

            except Exception as e:
                logger.debug(f"Telegram check error for {username}: {e}")

        return phones

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
