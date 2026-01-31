"""
VK People Search - Search VK.com by name
==========================================
Real people search by name using VK web search, not just username guessing.

Features:
- Search VK by full name (Cyrillic and Latin)
- Filter by city, age
- Extract profile data (photo, location, friends count)
- Return top 20 most likely matches with confidence scores

Based on Буратино research Section 4.1 - Name → Profile Discovery
"""

import requests
import logging
import re
import time
from typing import List, Dict, Optional
from urllib.parse import quote, urlencode
from bs4 import BeautifulSoup
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


class VKPeopleSearch:
    """
    Search VKontakte for people by name.

    Unlike username search (which checks if vk.com/username exists),
    this searches VK's people search for matching profiles by name.

    VK characteristics:
    - Most popular social network in Russia (97M+ users)
    - Good for ages 18-45
    - Often has phone/email visible
    - Rich profile data (location, education, work)
    """

    BASE_URL = "https://vk.com"
    SEARCH_URL = "https://vk.com/search"

    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
    }

    # Major Russian cities for filtering
    RUSSIAN_CITIES = {
        'москва': 1, 'санкт-петербург': 2, 'новосибирск': 99,
        'екатеринбург': 158, 'казань': 60, 'нижний новгород': 95,
        'челябинск': 158, 'самара': 119, 'уфа': 151, 'ростов-на-дону': 119,
        'краснодар': 72, 'воронеж': 36, 'пермь': 110, 'волгоград': 10,
        'красноярск': 73, 'саратов': 128, 'тюмень': 140, 'тольятти': 141,
    }

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
        Search VK for people by name.

        Args:
            name: Full name to search (Russian or Latin)
            city: City filter (Russian name)
            age_from: Minimum age
            age_to: Maximum age
            limit: Max results to return
            target_name: Original target name for similarity scoring

        Returns:
            List of profile dicts with confidence scores
        """
        logger.info(f"VK People Search: '{name}' city={city} age={age_from}-{age_to}")

        profiles = []

        try:
            self._rate_limit(1.0)

            # Build search URL
            # VK format: /search?c[q]=NAME&c[section]=people
            params = {
                'c[q]': name,
                'c[section]': 'people',
            }

            # Add city filter
            if city:
                city_id = self._get_city_id(city)
                if city_id:
                    params['c[city]'] = city_id

            # Add age filter
            if age_from:
                params['c[age_from]'] = age_from
            if age_to:
                params['c[age_to]'] = age_to

            url = f"{self.SEARCH_URL}?{urlencode(params)}"
            logger.debug(f"VK search URL: {url}")

            response = self.session.get(url, timeout=15)

            if response.status_code != 200:
                logger.warning(f"VK search returned {response.status_code}")
                return []

            # Check for login/captcha redirect
            if '/login' in response.url or 'captcha' in response.text.lower():
                logger.warning("VK requires login or captcha")
                # Fallback to simpler method
                return self._search_via_simple(name, limit, target_name)

            profiles = self._parse_search_results(response.text, limit)

            # Calculate name similarity
            ref_name = target_name or name
            for p in profiles:
                p['name_similarity'] = self._calculate_name_similarity(ref_name, p.get('display_name', ''))
                p['name_match'] = p['name_similarity'] > 50

            # Sort by name similarity
            profiles.sort(key=lambda x: x.get('name_similarity', 0), reverse=True)

            logger.info(f"VK people search found {len(profiles)} profiles")
            return profiles[:limit]

        except Exception as e:
            logger.error(f"VK people search failed: {e}")
            # Try fallback method
            return self._search_via_simple(name, limit, target_name)

    def _search_via_simple(self, name: str, limit: int, target_name: str = None) -> List[Dict]:
        """
        Simple fallback search using VK's public search.

        This uses the /id/search endpoint which doesn't require login.
        """
        try:
            self._rate_limit(1.0)

            # Try the search friends/people suggestion API
            encoded_name = quote(name)
            url = f"https://vk.com/hints.php?act=a_search_global&al=1&from=&q={encoded_name}&section=people"

            response = self.session.get(url, timeout=10)

            if response.status_code != 200:
                return []

            profiles = self._parse_hints_response(response.text, limit)

            # Add similarity scores
            ref_name = target_name or name
            for p in profiles:
                p['name_similarity'] = self._calculate_name_similarity(ref_name, p.get('display_name', ''))
                p['name_match'] = p['name_similarity'] > 50

            return profiles

        except Exception as e:
            logger.error(f"VK simple search failed: {e}")
            return []

    def _get_city_id(self, city: str) -> Optional[int]:
        """Get VK city ID from city name."""
        city_lower = city.lower().strip()
        return self.RUSSIAN_CITIES.get(city_lower)

    def _parse_search_results(self, html: str, limit: int) -> List[Dict]:
        """Parse VK search results page."""
        profiles = []
        soup = BeautifulSoup(html, 'html.parser')

        # Try multiple selectors for VK search results
        selectors = [
            '.people_row',
            '.search_row',
            '.user_row',
            '[data-id]',
            '.page_search_row',
        ]

        items = []
        for selector in selectors:
            items = soup.select(selector)
            if items:
                logger.debug(f"Found {len(items)} items with selector: {selector}")
                break

        # Fallback: look for profile links in general
        if not items:
            items = soup.select('a[href*="/id"]')
            logger.debug(f"Fallback: found {len(items)} profile links")

        for item in items[:limit * 2]:
            try:
                profile = self._parse_profile_row(item)
                if profile and profile.get('url'):
                    profiles.append(profile)
                    if len(profiles) >= limit:
                        break
            except Exception as e:
                logger.debug(f"Failed to parse VK row: {e}")
                continue

        return profiles

    def _parse_hints_response(self, response_text: str, limit: int) -> List[Dict]:
        """Parse VK hints/suggestions response."""
        profiles = []

        # VK hints response is a weird format - try to extract data
        try:
            # Look for user IDs and names in response
            id_pattern = r'"id":(\d+)'
            name_pattern = r'"name":"([^"]+)"'
            photo_pattern = r'"photo":"([^"]+)"'

            ids = re.findall(id_pattern, response_text)
            names = re.findall(name_pattern, response_text)
            photos = re.findall(photo_pattern, response_text)

            for i, uid in enumerate(ids[:limit]):
                profile = {
                    'platform': 'VK',
                    'url': f'https://vk.com/id{uid}',
                    'username': f'id{uid}',
                    'display_name': names[i] if i < len(names) else '',
                    'photo_url': photos[i].replace('\\/', '/') if i < len(photos) else None,
                    'exists': True,
                    'source': 'vk_people_search',
                    'city': '',
                    'age': None,
                    'friends_count': None,
                    'confidence': 0.6,
                }
                profiles.append(profile)

        except Exception as e:
            logger.debug(f"Failed to parse hints response: {e}")

        return profiles

    def _parse_profile_row(self, row) -> Optional[Dict]:
        """Parse a single profile row from search results."""
        profile = {
            'platform': 'VK',
            'url': '',
            'username': '',
            'display_name': '',
            'photo_url': None,
            'city': '',
            'age': None,
            'friends_count': None,
            'exists': True,
            'source': 'vk_people_search',
            'confidence': 0.6,
        }

        # Extract URL
        if row.name == 'a':
            href = row.get('href', '')
        else:
            link = row.select_one('a[href*="/id"]')
            if not link:
                link = row.select_one('a[href^="/"]')
            href = link.get('href', '') if link else ''

        if href:
            if href.startswith('/'):
                href = f"https://vk.com{href}"
            profile['url'] = href

            # Extract username/id
            match = re.search(r'vk\.com/(?:id)?(\d+|[a-zA-Z0-9_.]+)', href)
            if match:
                profile['username'] = match.group(1)

        # Extract name
        name_selectors = [
            '.people_row_name a',
            '.search_row_name',
            '.title',
            '.name',
            '.a_link'
        ]
        for sel in name_selectors:
            name_elem = row.select_one(sel)
            if name_elem:
                text = name_elem.get_text(strip=True)
                if text and len(text) > 1 and len(text) < 100:
                    profile['display_name'] = text
                    break

        # If row is a link itself
        if not profile['display_name'] and row.name == 'a':
            text = row.get_text(strip=True)
            if text and len(text) > 1 and len(text) < 100:
                profile['display_name'] = text

        # Extract photo
        img = row.select_one('img')
        if img:
            src = img.get('src', '') or img.get('data-src', '')
            if src and 'camera' not in src and 'deactivated' not in src:
                profile['photo_url'] = src

        # Extract additional info
        info_selectors = ['.people_row_info', '.info', '.subtitle']
        for sel in info_selectors:
            info_elem = row.select_one(sel)
            if info_elem:
                info_text = info_elem.get_text(strip=True).lower()

                # Extract age
                age_match = re.search(r'(\d{1,2})\s*(лет|год|года)', info_text)
                if age_match:
                    profile['age'] = int(age_match.group(1))

                # Extract city
                for city in self.RUSSIAN_CITIES.keys():
                    if city in info_text:
                        profile['city'] = city.title()
                        break

                break

        # Only return if meaningful data
        if profile['url'] and (profile['display_name'] or profile['username']):
            return profile
        return None

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


def search_vk_people(
    name: str,
    city: str = None,
    limit: int = 20,
    target_name: str = None
) -> List[Dict]:
    """
    Convenience function to search VK people.

    Args:
        name: Full name to search
        city: Optional city filter
        limit: Max results
        target_name: Original target name for similarity scoring

    Returns:
        List of profile dicts
    """
    searcher = VKPeopleSearch()
    return searcher.search_people(name, city=city, limit=limit, target_name=target_name)


# Singleton instance
vk_people_search = VKPeopleSearch()
