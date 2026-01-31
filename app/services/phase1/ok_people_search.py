"""
OK (Odnoklassniki) People Search - Search OK.ru by name
========================================================
Real people search by name, not just username guessing.

Features:
- Search OK.ru by full name (Cyrillic and Latin)
- Filter by city, age
- Extract profile data (photo, location, age)
- Return matches with name similarity scores

Based on Буратино research Section 4.1 - Name → Profile Discovery

OK.ru characteristics:
- Popular with 30+ age demographic
- Often shows more personal info than VK
- Good for finding relatives/family
- Russian/CIS focused
"""

import requests
import logging
import re
import time
from typing import List, Dict, Optional
from urllib.parse import quote
from bs4 import BeautifulSoup
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


class OKPeopleSearch:
    """
    Search Odnoklassniki for people by name.

    Unlike username search (which checks if ok.ru/username exists),
    this searches OK's people search for matching profiles by name.
    """

    BASE_URL = "https://ok.ru"
    SEARCH_URL = "https://ok.ru/search"

    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
    }

    # Common Russian cities
    RUSSIAN_CITIES = [
        'москва', 'санкт-петербург', 'новосибирск', 'екатеринбург',
        'казань', 'нижний новгород', 'челябинск', 'самара', 'уфа',
        'ростов-на-дону', 'краснодар', 'воронеж', 'пермь', 'волгоград',
        'красноярск', 'саратов', 'тюмень', 'тольятти', 'ижевск',
        'барнаул', 'ульяновск', 'иркутск', 'хабаровск', 'ярославль',
        'владивосток', 'махачкала', 'томск', 'оренбург', 'кемерово',
    ]

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        self._request_count = 0
        self._last_request_time = 0

    def _rate_limit(self, delay: float = 1.0):
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
        city: str = None,
        age_from: int = None,
        age_to: int = None,
        limit: int = 20,
        target_name: str = None
    ) -> List[Dict]:
        """
        Search OK for people by name.

        Args:
            name: Full name (Russian preferred)
            city: City filter (Russian name)
            age_from: Minimum age
            age_to: Maximum age
            limit: Max results to return
            target_name: Original target name for similarity scoring

        Returns:
            List of profile dicts with confidence scores
        """
        logger.info(f"OK People Search: '{name}' city={city} age={age_from}-{age_to}")

        try:
            self._rate_limit(1.0)

            # Build search URL
            # OK format: /search?st.query=NAME&st.cmd=searchResult&st.mode=Users
            encoded_name = quote(name)
            url = f"{self.SEARCH_URL}?st.query={encoded_name}&st.cmd=searchResult&st.mode=Users"

            logger.debug(f"OK search URL: {url}")

            response = self.session.get(url, timeout=15)

            if response.status_code != 200:
                logger.warning(f"OK search returned {response.status_code}")
                return []

            # Check for login redirect
            if 'st.cmd=anonymMain' in response.url or 'login' in response.url:
                logger.warning("OK requires login for search")
                return []

            profiles = self._parse_search_results(response.text, limit)

            # Calculate name similarity for each profile
            ref_name = target_name or name
            for p in profiles:
                p['name_similarity'] = self._calculate_name_similarity(ref_name, p.get('display_name', ''))
                p['name_match'] = p['name_similarity'] > 50
                p['source'] = 'ok_people_search'

            # Post-filter by city
            if city and profiles:
                city_lower = city.lower()
                profiles = [p for p in profiles if city_lower in (p.get('city', '') or '').lower()]

            # Post-filter by age
            if (age_from or age_to) and profiles:
                profiles = self._filter_by_age(profiles, age_from, age_to)

            # Sort by name similarity
            profiles.sort(key=lambda x: x.get('name_similarity', 0), reverse=True)

            logger.info(f"OK people search found {len(profiles)} profiles")
            return profiles[:limit]

        except Exception as e:
            logger.error(f"OK people search failed: {e}")
            return []

    def _parse_search_results(self, html: str, limit: int) -> List[Dict]:
        """Parse OK search results HTML."""
        profiles = []
        soup = BeautifulSoup(html, 'html.parser')

        # Try multiple selectors for OK search results
        selectors = [
            '.ucard',
            '.user-card',
            '.search-result',
            '[data-module="UserCard"]',
            '.grid-card',
            '.item-card',
        ]

        items = []
        for selector in selectors:
            items = soup.select(selector)
            if items:
                logger.debug(f"Found {len(items)} items with selector: {selector}")
                break

        # Fallback: look for profile links
        if not items:
            items = soup.select('a[href*="/profile/"]')
            logger.debug(f"Fallback: found {len(items)} profile links")

        for item in items[:limit * 2]:
            try:
                profile = self._parse_profile_card(item)
                if profile and profile.get('url'):
                    profiles.append(profile)
            except Exception as e:
                logger.debug(f"Failed to parse OK card: {e}")
                continue

        return profiles[:limit]

    def _parse_profile_card(self, card) -> Optional[Dict]:
        """Parse a single profile card from search results."""
        profile = {
            'platform': 'OK',
            'url': '',
            'username': '',
            'display_name': '',
            'photo_url': None,
            'city': '',
            'age': None,
            'bio': '',
            'exists': True,
            'source': 'ok_people_search',
            'confidence': 0.6,
        }

        # Extract URL
        if card.name == 'a':
            href = card.get('href', '')
        else:
            link = card.select_one('a[href*="/profile/"]')
            if not link:
                link = card.select_one('a[href^="/"]')
            href = link.get('href', '') if link else ''

        if href:
            if href.startswith('/'):
                href = f"https://ok.ru{href}"
            profile['url'] = href

            # Extract profile ID
            match = re.search(r'/profile/(\d+)', href)
            if match:
                profile['username'] = match.group(1)

        # Extract name
        name_selectors = [
            '.ucard-v-info_cnt a',
            '.user-card__name',
            '.title',
            '.name',
            'span.emphased',
            'a.n-t'
        ]
        for sel in name_selectors:
            name_elem = card.select_one(sel)
            if name_elem:
                text = name_elem.get_text(strip=True)
                if text and len(text) > 1 and len(text) < 100:
                    profile['display_name'] = text
                    break

        # If card is a link itself
        if not profile['display_name'] and card.name == 'a':
            text = card.get_text(strip=True)
            if text and len(text) > 1 and len(text) < 100:
                profile['display_name'] = text

        # Extract photo
        img = card.select_one('img')
        if img:
            src = img.get('src', '') or img.get('data-src', '')
            if src and 'stub' not in src:  # Skip placeholder images
                profile['photo_url'] = src

        # Extract additional info
        info_selectors = ['.ucard-v-info_cnt', '.info', '.subtitle', '.user-card__info']
        for sel in info_selectors:
            info_elem = card.select_one(sel)
            if info_elem:
                info_text = info_elem.get_text(strip=True).lower()

                # Extract age
                age_match = re.search(r'(\d{1,2})\s*(лет|год|года)', info_text)
                if age_match:
                    profile['age'] = int(age_match.group(1))

                # Extract city
                for city in self.RUSSIAN_CITIES:
                    if city in info_text:
                        profile['city'] = city.title()
                        break
                break

        # Only return if meaningful data
        if profile['url'] and (profile['display_name'] or profile['username']):
            return profile
        return None

    def _filter_by_age(self, profiles: List[Dict], age_from: int, age_to: int) -> List[Dict]:
        """Filter profiles by age range."""
        filtered = []
        for p in profiles:
            age = p.get('age')
            if age is None:
                # Include profiles without age
                filtered.append(p)
                continue

            include = True
            if age_from and age < age_from:
                include = False
            if age_to and age > age_to:
                include = False

            if include:
                filtered.append(p)

        return filtered

    def _calculate_name_similarity(self, target: str, found: str) -> float:
        """Calculate name similarity score (0-100)."""
        if not target or not found:
            return 0.0

        target_lower = target.lower().strip()
        found_lower = found.lower().strip()

        # Direct sequence matching
        direct = SequenceMatcher(None, target_lower, found_lower).ratio() * 100

        # Part-based matching
        target_parts = target_lower.split()
        found_parts = found_lower.split()

        matches = 0
        for tp in target_parts:
            for fp in found_parts:
                if tp in fp or fp in tp:
                    matches += 1
                    break
                if len(tp) > 3 and len(fp) > 3:
                    if SequenceMatcher(None, tp, fp).ratio() > 0.8:
                        matches += 1
                        break

        part_score = (matches / len(target_parts)) * 100 if target_parts else 0

        return max(direct, part_score)

    def generate_search_variations(self, name: str) -> List[str]:
        """
        Generate search variations for a name.

        For Russian names, includes:
        - Original name
        - Reversed order (last name first)
        - Individual parts
        - Common diminutives
        """
        variations = [name]
        parts = name.split()

        if len(parts) >= 2:
            # Reverse order
            variations.append(' '.join(reversed(parts)))

            # First name only
            variations.append(parts[0])

            # Last name + first name initial
            variations.append(f"{parts[-1]} {parts[0][0]}.")

        # Common Russian diminutives
        diminutives = {
            'александр': ['саша', 'саня', 'шура'],
            'алексей': ['алёша', 'лёша', 'лёха'],
            'анастасия': ['настя', 'ася'],
            'андрей': ['андрюша', 'андрюха'],
            'анна': ['аня', 'анюта'],
            'дмитрий': ['дима', 'митя'],
            'екатерина': ['катя', 'катюша'],
            'елена': ['лена', 'леночка'],
            'иван': ['ваня', 'ванюша'],
            'мария': ['маша', 'маруся'],
            'михаил': ['миша', 'мишка'],
            'наталья': ['наташа', 'ната'],
            'николай': ['коля', 'николаша'],
            'ольга': ['оля', 'ольчик'],
            'павел': ['паша', 'пашка'],
            'сергей': ['серёжа', 'серёга'],
            'татьяна': ['таня', 'танюша'],
            'юлия': ['юля', 'юлечка'],
            'даниил': ['даня', 'данила', 'даниэль'],
            'тихон': ['тиша', 'тишка'],
            'ангелина': ['геля', 'лина', 'ангел'],
        }

        first_name = parts[0].lower() if parts else ''
        if first_name in diminutives:
            for dim in diminutives[first_name]:
                if len(parts) > 1:
                    variations.append(f"{dim.title()} {parts[-1]}")
                else:
                    variations.append(dim.title())

        return list(dict.fromkeys(variations))  # Remove duplicates while preserving order


def search_ok_people(
    name: str,
    city: str = None,
    limit: int = 20,
    target_name: str = None
) -> List[Dict]:
    """
    Convenience function to search OK people.

    Args:
        name: Full name to search
        city: Optional city filter
        limit: Max results
        target_name: Original target name for similarity scoring

    Returns:
        List of profile dicts
    """
    searcher = OKPeopleSearch()
    return searcher.search_people(name, city=city, limit=limit, target_name=target_name)


# Singleton instance
ok_people_search = OKPeopleSearch()
