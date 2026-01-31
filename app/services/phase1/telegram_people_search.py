"""
Telegram People Search - Search Telegram by name
=================================================
Enhanced Telegram search with name matching and confidence scoring.

Features:
- Username existence check via t.me
- Username generation from names (Cyrillic/Latin)
- Name similarity scoring
- Profile data extraction
- Bio parsing for contacts

Based on Буратино research Section 4.1 - Name → Profile Discovery
"""

import requests
import logging
import re
import time
from typing import List, Dict, Optional
from bs4 import BeautifulSoup
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


class TelegramPeopleSearch:
    """
    Enhanced Telegram search with name matching.

    Unlike basic username check, this:
    1. Generates username candidates from names
    2. Checks each candidate
    3. Verifies display name matches target
    4. Returns results with confidence scores
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

    def _rate_limit(self, delay: float = 0.3):
        """Enforce rate limiting between requests."""
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < delay:
            time.sleep(delay - elapsed)
        self._last_request_time = time.time()
        self._request_count += 1

    def search_people(
        self,
        name: str,
        limit: int = 10,
        target_name: str = None
    ) -> List[Dict]:
        """
        Search Telegram by generating and checking possible usernames.

        Args:
            name: Full name to search for
            limit: Maximum results to return
            target_name: Original target name for similarity scoring

        Returns:
            List of profile dicts with confidence scores
        """
        logger.info(f"Telegram People Search: '{name}'")

        # Split name into parts
        parts = name.strip().split()
        first_name = parts[0] if parts else name
        last_name = parts[-1] if len(parts) > 1 else ''

        # Generate username candidates
        candidates = self.generate_usernames(first_name, last_name)
        logger.debug(f"Generated {len(candidates)} username candidates")

        found = []
        ref_name = target_name or name

        for username in candidates:
            if len(found) >= limit:
                break

            profile = self.check_username(username)
            if profile:
                # Calculate name similarity
                display_name = profile.get('display_name', '')
                profile['name_similarity'] = self._calculate_name_similarity(ref_name, display_name)
                profile['name_match'] = profile['name_similarity'] > 40
                profile['source'] = 'telegram_people_search'

                # Only include if there's some name relevance
                if profile['name_match'] or profile['name_similarity'] > 20:
                    found.append(profile)
                    logger.info(f"Found: @{username} - {display_name} (similarity: {profile['name_similarity']:.1f}%)")

        # Sort by name similarity
        found.sort(key=lambda x: x.get('name_similarity', 0), reverse=True)

        logger.info(f"Telegram People Search complete: {len(found)} found")
        return found[:limit]

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
            return None

        url = f"{self.BASE_URL}/{username}"

        try:
            self._rate_limit(0.3)

            response = self.session.get(url, timeout=10, allow_redirects=True)

            if response.status_code == 404:
                return None

            if response.status_code != 200:
                return None

            html = response.text

            # Check for valid profile indicators
            valid_indicators = [
                'tgme_page_title',
                'tgme_page_photo',
            ]

            not_found_indicators = [
                'tgme_page_icon_deleted',
                "doesn't exist",
            ]

            has_valid = any(ind in html for ind in valid_indicators)
            has_not_found = any(ind in html for ind in not_found_indicators)

            if has_not_found or not has_valid:
                return None

            return self._parse_profile_page(html, username)

        except Exception as e:
            logger.debug(f"Telegram check failed for {username}: {e}")
            return None

    def _parse_profile_page(self, html: str, username: str) -> Dict:
        """Parse Telegram profile page."""
        soup = BeautifulSoup(html, 'html.parser')

        profile = {
            'platform': 'Telegram',
            'url': f"https://t.me/{username}",
            'username': username,
            'display_name': '',
            'photo_url': None,
            'bio': '',
            'exists': True,
            'source': 'telegram_people_search',
            'type': 'user',
            'confidence': 0.6,
        }

        # Extract name
        name_elem = soup.select_one('.tgme_page_title span')
        if name_elem:
            profile['display_name'] = name_elem.get_text(strip=True)
        else:
            title = soup.select_one('.tgme_page_title')
            if title:
                profile['display_name'] = title.get_text(strip=True)

        # Extract photo
        photo_elem = soup.select_one('.tgme_page_photo_image img')
        if photo_elem:
            profile['photo_url'] = photo_elem.get('src', '')
        else:
            photo_elem = soup.select_one('img.tgme_page_photo_image')
            if photo_elem:
                profile['photo_url'] = photo_elem.get('src', '')

        # Extract bio/description
        desc_elem = soup.select_one('.tgme_page_description')
        if desc_elem:
            profile['bio'] = desc_elem.get_text(strip=True)

        # Detect bots
        if username.lower().endswith('bot'):
            profile['type'] = 'bot'

        return profile

    def generate_usernames(self, first_name: str, last_name: str = '') -> List[str]:
        """
        Generate possible Telegram usernames from name.

        Args:
            first_name: First name (Russian or English)
            last_name: Last name

        Returns:
            List of username candidates
        """
        candidates = []

        # Transliterate Cyrillic
        first = self._transliterate(first_name.lower().strip())
        last = self._transliterate(last_name.lower().strip()) if last_name else ''

        if not first or len(first) < 2:
            return []

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
        suffixes = ['_', '1', '2', '01', '02', '00']
        years = ['90', '91', '92', '93', '94', '95', '96', '97', '98', '99', '00', '01', '02', '03']

        for suffix in suffixes:
            if len(first + suffix) >= 5:
                candidates.append(f"{first}{suffix}")

        for year in years:
            candidates.append(f"{first}{year}")
            candidates.append(f"{first}_{year}")

        # Filter and dedupe
        seen = set()
        valid = []
        for c in candidates:
            c = re.sub(r'[^a-zA-Z0-9_]', '', c)
            if c and len(c) >= 5 and len(c) <= 32 and c[0].isalpha() and c not in seen:
                seen.add(c)
                valid.append(c)

        return valid[:25]

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

    def _calculate_name_similarity(self, target: str, found: str) -> float:
        """Calculate name similarity score (0-100)."""
        if not target or not found:
            return 0.0

        target_lower = target.lower().strip()
        found_lower = found.lower().strip()

        # Also try transliterated comparison
        target_trans = self._transliterate(target_lower)
        found_trans = self._transliterate(found_lower)

        # Direct sequence matching
        direct = SequenceMatcher(None, target_lower, found_lower).ratio() * 100
        trans = SequenceMatcher(None, target_trans, found_trans).ratio() * 100

        # Part-based matching
        target_parts = target_lower.split()
        found_parts = found_lower.split()

        matches = 0
        for tp in target_parts:
            tp_trans = self._transliterate(tp)
            for fp in found_parts:
                fp_trans = self._transliterate(fp)
                if tp in fp or fp in tp or tp_trans in fp_trans or fp_trans in tp_trans:
                    matches += 1
                    break

        part_score = (matches / len(target_parts)) * 100 if target_parts else 0

        return max(direct, trans, part_score)


def search_telegram_people(
    name: str,
    limit: int = 10,
    target_name: str = None
) -> List[Dict]:
    """
    Convenience function to search Telegram people.

    Args:
        name: Full name to search
        limit: Max results
        target_name: Original target name for similarity scoring

    Returns:
        List of profile dicts
    """
    searcher = TelegramPeopleSearch()
    return searcher.search_people(name, limit=limit, target_name=target_name)


# Singleton instance
telegram_people_search = TelegramPeopleSearch()
