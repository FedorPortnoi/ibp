"""
Telegram Search - Search and check Telegram profiles/channels.
Agent 3 - Telegram Search Specialist

Features:
- Username existence check via t.me
- Profile/channel info extraction
- Username generation from names
- Bio parsing for contacts
"""
import requests
import logging
import re
import time
from typing import List, Dict, Optional
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class TelegramSearch:
    """
    Telegram OSINT search functionality.

    Methods:
    1. Username check via t.me/username
    2. Profile data extraction
    3. Username generation from name patterns
    """

    BASE_URL = "https://t.me"

    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
    }

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        self._request_count = 0
        self._last_request_time = 0

    def _rate_limit(self, delay: float = 0.5):
        """Enforce rate limiting."""
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < delay:
            time.sleep(delay - elapsed)
        self._last_request_time = time.time()
        self._request_count += 1

    def check_username(self, username: str) -> Optional[Dict]:
        """
        Check if Telegram username exists and get profile info.

        Args:
            username: Telegram username (without @)

        Returns:
            Profile dict if exists, None if not found
        """
        username = username.lstrip('@').strip()

        if not username or len(username) < 5:
            return None

        # Validate username format (5-32 chars, alphanumeric + underscore)
        if not re.match(r'^[a-zA-Z][a-zA-Z0-9_]{4,31}$', username):
            logger.debug(f"Invalid Telegram username format: {username}")
            return None

        url = f"{self.BASE_URL}/{username}"
        logger.debug(f"Checking Telegram: {url}")

        try:
            self._rate_limit(0.5)

            response = self.session.get(url, timeout=15, allow_redirects=True)

            if response.status_code == 404:
                return None

            if response.status_code != 200:
                logger.warning(f"Telegram returned {response.status_code} for {username}")
                return None

            html = response.text

            # Check for "user not found" or redirect indicators
            not_found_indicators = [
                'tgme_page_icon_deleted',
                "doesn't exist",
                'Preview channel',  # Some channels redirect here without valid content
            ]

            # Check if it's a valid profile/channel
            valid_indicators = [
                'tgme_page_title',
                'tgme_page_photo',
                'tgme_channel_info',
            ]

            has_valid = any(ind in html for ind in valid_indicators)
            has_not_found = any(ind in html for ind in not_found_indicators)

            if has_not_found and not has_valid:
                return None

            if not has_valid:
                # Check for the "contact" page which indicates a valid user
                if 'you can contact' not in html.lower() and 'tgme_page_description' not in html:
                    return None

            return self._parse_profile_page(html, username)

        except requests.exceptions.Timeout:
            logger.warning(f"Timeout checking {username}")
            return None
        except Exception as e:
            logger.error(f"Telegram check failed for {username}: {e}")
            return None

    def _parse_profile_page(self, html: str, username: str) -> Dict:
        """Parse Telegram profile/channel page."""
        soup = BeautifulSoup(html, 'html.parser')

        profile = {
            'platform': 'telegram',
            'url': f"https://t.me/{username}",
            'username': username,
            'display_name': '',
            'photo_url': '',
            'bio': '',
            'city': '',
            'age': None,
            'phones': [],
            'emails': [],
            'workplace': '',
            'friends': [],
            'groups': [],
            'type': 'user',  # user, channel, group, bot
            'members_count': None,
            'confidence': 0.7
        }

        # Extract name
        name_elem = soup.select_one('.tgme_page_title span')
        if name_elem:
            profile['display_name'] = name_elem.get_text(strip=True)
        else:
            # Fallback
            title = soup.select_one('.tgme_page_title')
            if title:
                profile['display_name'] = title.get_text(strip=True)

        # Extract photo
        photo_elem = soup.select_one('.tgme_page_photo_image img')
        if photo_elem:
            profile['photo_url'] = photo_elem.get('src', '')
        else:
            # Try alternative
            photo_elem = soup.select_one('img.tgme_page_photo_image')
            if photo_elem:
                profile['photo_url'] = photo_elem.get('src', '')

        # Extract bio/description
        desc_elem = soup.select_one('.tgme_page_description')
        if desc_elem:
            profile['bio'] = desc_elem.get_text(strip=True)

            # Extract phone from bio
            phone_patterns = [
                r'\+7[\s\-]?\d{3}[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}',
                r'\+7\s?\(\d{3}\)\s?\d{3}[\-\s]?\d{2}[\-\s]?\d{2}',
                r'8[\s\-]?\d{3}[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}',
            ]
            for pattern in phone_patterns:
                matches = re.findall(pattern, profile['bio'])
                profile['phones'].extend(matches)

            # Extract email from bio
            email_matches = re.findall(r'[\w\.\-]+@[\w\.\-]+\.\w+', profile['bio'])
            profile['emails'].extend(email_matches)

            # Extract Telegram username mentions in bio
            tg_mentions = re.findall(r'@([a-zA-Z][a-zA-Z0-9_]{4,31})', profile['bio'])
            # Could be useful for connection discovery

        # Extract extra info (subscribers/members)
        extra_elem = soup.select_one('.tgme_page_extra')
        if extra_elem:
            extra_text = extra_elem.get_text(strip=True)

            # Check for subscriber/member count
            count_match = re.search(r'([\d\s]+)\s*(subscriber|member|подписчик)', extra_text, re.I)
            if count_match:
                count_str = count_match.group(1).replace(' ', '').replace('\xa0', '')
                try:
                    profile['members_count'] = int(count_str)
                    profile['type'] = 'channel'
                except:
                    pass

        # Detect bots
        if username.lower().endswith('bot'):
            profile['type'] = 'bot'

        # Dedupe
        profile['phones'] = list(set(profile['phones']))
        profile['emails'] = list(set(e.lower() for e in profile['emails']))

        return profile

    def search_by_name(
        self,
        first_name: str,
        last_name: str = '',
        check_limit: int = 15
    ) -> List[Dict]:
        """
        Search Telegram by generating and checking possible usernames.

        Args:
            first_name: First name (Russian or English)
            last_name: Last name
            check_limit: Maximum usernames to check

        Returns:
            List of found profiles
        """
        logger.info(f"Telegram search for: {first_name} {last_name}")

        candidates = self.generate_usernames(first_name, last_name)
        found = []
        checked = 0

        for username in candidates:
            if checked >= check_limit:
                break

            profile = self.check_username(username)
            if profile:
                # Verify the name somewhat matches
                profile_name = profile.get('display_name', '').lower()
                search_first = first_name.lower()

                # Accept if name contains search term or vice versa
                if (search_first in profile_name or
                    profile_name in search_first or
                    self._transliterate(search_first) in profile_name.lower()):
                    found.append(profile)
                    logger.info(f"Found Telegram: @{username} - {profile.get('display_name')}")

            checked += 1

        logger.info(f"Telegram search complete: {len(found)} found, {checked} checked")
        return found

    def generate_usernames(self, first_name: str, last_name: str = '') -> List[str]:
        """Generate possible Telegram usernames from name."""
        candidates = []

        # Transliterate Cyrillic
        first = self._transliterate(first_name.lower().strip())
        last = self._transliterate(last_name.lower().strip()) if last_name else ''

        if not first or len(first) < 2:
            return []

        # Common patterns
        if first:
            # First name only variants
            if len(first) >= 5:
                candidates.append(first)

            if last:
                # Combined variants
                patterns = [
                    f"{first}_{last}",
                    f"{first}{last}",
                    f"{first}.{last}",
                    f"{last}_{first}",
                    f"{last}{first}",
                    f"{first[0]}{last}",
                    f"{first[0]}_{last}",
                    f"{first}{last[0]}",
                    f"{last}{first[0]}",
                    f"{first[:3]}{last}",
                ]
                candidates.extend(patterns)

            # With common suffixes/numbers
            suffixes = ['_', '1', '2', '01', '02', '00', '_official', '_real']
            year_suffixes = ['90', '91', '92', '93', '94', '95', '96', '97', '98', '99', '00', '01', '02', '03']

            for suffix in suffixes:
                if len(first + suffix) >= 5:
                    candidates.append(f"{first}{suffix}")

            for year in year_suffixes:
                candidates.append(f"{first}{year}")
                candidates.append(f"{first}_{year}")

        # Filter and dedupe
        seen = set()
        valid = []
        for c in candidates:
            # Telegram rules: 5-32 chars, start with letter, alphanumeric + underscore
            c = re.sub(r'[^a-zA-Z0-9_]', '', c)
            if c and len(c) >= 5 and len(c) <= 32 and c[0].isalpha() and c not in seen:
                seen.add(c)
                valid.append(c)

        return valid[:30]  # Limit total candidates

    def _transliterate(self, text: str) -> str:
        """Transliterate Cyrillic to Latin."""
        translit_map = {
            'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
            'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
            'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
            'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
            'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya'
        }
        result = ''
        for char in text.lower():
            result += translit_map.get(char, char)
        return result


# Singleton instance
telegram_search = TelegramSearch()
