"""
OK (Odnoklassniki) Search Integration - Phase 1
=================================================
Searches OK.ru for people profiles by name.

Since OK.ru does not provide a free public API, this module uses web scraping
with requests + BeautifulSoup. Falls back to demo mode when scraping fails
or when no OK_SESSION_TOKEN is configured.

Features:
- OK.ru people search via web scraping
- Demo mode fallback with realistic fake profiles
- Name similarity scoring (Cyrillic-aware)
- Database persistence via SocialProfile model
- Reproducible demo results (seeded RNG)
"""

import os
import hashlib
import logging
import random
from difflib import SequenceMatcher
from typing import List, Optional, Dict, Any

try:
    import requests
except ImportError:
    requests = None

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

logger = logging.getLogger(__name__)


# Common Russian first names and last names for demo data generation
_DEMO_FIRST_NAMES_MALE = [
    'Александр', 'Дмитрий', 'Сергей', 'Андрей', 'Михаил',
    'Иван', 'Николай', 'Артём', 'Владимир', 'Павел',
]
_DEMO_FIRST_NAMES_FEMALE = [
    'Елена', 'Ольга', 'Наталья', 'Анна', 'Мария',
    'Татьяна', 'Ирина', 'Светлана', 'Екатерина', 'Юлия',
]
_DEMO_LAST_NAMES = [
    'Иванов', 'Петров', 'Сидоров', 'Козлов', 'Смирнов',
    'Новиков', 'Морозов', 'Волков', 'Соколов', 'Лебедев',
]
_DEMO_CITIES = [
    'Москва', 'Санкт-Петербург', 'Новосибирск', 'Екатеринбург',
    'Казань', 'Нижний Новгород', 'Челябинск', 'Самара',
]


class OKSearchIntegration:
    """
    Odnoklassniki (OK.ru) People Search.

    Uses web scraping for real search, with demo mode fallback.
    Matches the pattern used by BuratinoVKSearch for VK.
    """

    SEARCH_URL = "https://ok.ru/search/people"
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )

    def __init__(self, session_token: Optional[str] = None):
        """
        Initialize OK search.

        Args:
            session_token: OK.ru session token for authenticated search.
                          If not provided, reads OK_SESSION_TOKEN from env.
                          Falls back to demo mode if unavailable.
        """
        self.token = session_token or os.environ.get("OK_SESSION_TOKEN")
        self._demo_mode = not self.token
        self.session = None

        if requests:
            self.session = requests.Session()
            self.session.headers.update({
                "User-Agent": self.USER_AGENT,
                "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.5",
            })
            if self.token:
                self.session.cookies.set("AUTHCODE", self.token)

        if self._demo_mode:
            logger.info("OKSearchIntegration: Running in DEMO mode (no OK token)")
        else:
            logger.info("OKSearchIntegration: Authenticated mode enabled")

    @property
    def is_demo_mode(self) -> bool:
        """Whether the searcher is running in demo mode."""
        return self._demo_mode

    def search(
        self,
        query: str,
        city: Optional[str] = None,
        age_from: Optional[int] = None,
        age_to: Optional[int] = None,
        count: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Search OK.ru for people by name.

        Args:
            query: Full name to search (e.g. 'Тихон Портной')
            city: Optional city filter
            age_from: Minimum age filter
            age_to: Maximum age filter
            count: Maximum number of results

        Returns:
            List of profile dicts with SocialProfile-compatible fields:
            platform, platform_id, username, profile_url,
            first_name, last_name, display_name,
            name_similarity, name_match
        """
        if self._demo_mode:
            return self._demo_search(query, city, age_from, age_to, count)

        # Try real web scraping
        try:
            return self._web_search(query, city, age_from, age_to, count)
        except Exception as e:
            logger.warning(f"OK.ru web search failed, falling back to demo: {e}")
            return self._demo_search(query, city, age_from, age_to, count)

    def search_and_save(
        self,
        investigation_id: str,
        query: str,
        city: Optional[str] = None,
        age_from: Optional[int] = None,
        age_to: Optional[int] = None,
        count: int = 20,
    ) -> List[Dict]:
        """
        Search OK.ru and save results to the database.

        Args:
            investigation_id: ID of the investigation to link profiles to
            query: Full name to search
            city: Optional city filter
            age_from: Minimum age filter
            age_to: Maximum age filter
            count: Maximum number of results

        Returns:
            List of saved profile dicts
        """
        from app import db
        from app.models import SocialProfile

        results = self.search(
            query=query,
            city=city,
            age_from=age_from,
            age_to=age_to,
            count=count,
        )

        saved_profiles = []

        for result in results:
            # Skip very low similarity
            if result.get('name_similarity', 0) < 20:
                continue

            # Check for existing profile
            existing = SocialProfile.query.filter_by(
                investigation_id=investigation_id,
                platform='ok',
                platform_id=str(result['platform_id']),
            ).first()

            if existing:
                # Update if higher similarity
                if result.get('name_similarity', 0) > (existing.name_similarity or 0):
                    existing.name_similarity = result['name_similarity']
                    existing.name_match = result.get('name_match', False)
                saved_profiles.append(existing.to_dict())
            else:
                profile = SocialProfile(
                    investigation_id=investigation_id,
                    platform='ok',
                    platform_id=str(result['platform_id']),
                    username=result.get('username'),
                    profile_url=result['profile_url'],
                    first_name=result.get('first_name', ''),
                    last_name=result.get('last_name', ''),
                    display_name=result['display_name'],
                    photo_url=result.get('photo_url'),
                    city=result.get('city'),
                    age=result.get('age'),
                    name_similarity=result.get('name_similarity', 0.0),
                    name_match=result.get('name_match', False),
                )
                profile.calculate_confidence()
                db.session.add(profile)
                saved_profiles.append(profile.to_dict())

        db.session.commit()
        logger.info(
            f"Saved {len(saved_profiles)} OK profiles for investigation {investigation_id}"
        )

        return saved_profiles

    def _web_search(
        self,
        query: str,
        city: Optional[str],
        age_from: Optional[int],
        age_to: Optional[int],
        count: int,
    ) -> List[Dict[str, Any]]:
        """
        Perform real web search on OK.ru.

        Uses requests + BeautifulSoup to scrape search results.
        Requires OK_SESSION_TOKEN for authenticated access.
        """
        if not self.session:
            raise RuntimeError("requests library not available")

        if not BeautifulSoup:
            raise RuntimeError("BeautifulSoup not available")

        params = {"st.query": query, "st.cmd": "searchResult", "st.mode": "People"}
        if city:
            params["st.city"] = city

        try:
            response = self.session.get(
                self.SEARCH_URL,
                params=params,
                timeout=15,
            )
            response.raise_for_status()
        except Exception as e:
            raise RuntimeError(f"OK.ru request failed: {e}")

        soup = BeautifulSoup(response.text, "html.parser")
        results = []

        # Parse search result cards
        cards = soup.select(".ucard, .user-card, .search-card, [data-module='UserCard']")
        if not cards:
            # Alternative selectors for different OK layouts
            cards = soup.select(".gs_result, .search_result_item, .compact-profile")

        for card in cards[:count]:
            try:
                profile = self._parse_search_card(card, query)
                if profile:
                    results.append(profile)
            except Exception as e:
                logger.debug(f"Failed to parse OK search card: {e}")
                continue

        # Sort by name similarity
        results.sort(key=lambda r: r.get('name_similarity', 0), reverse=True)
        return results[:count]

    def _parse_search_card(
        self, card, target_name: str
    ) -> Optional[Dict[str, Any]]:
        """Parse a single OK.ru search result card into a profile dict."""
        # Try to find profile link
        link = card.select_one("a[href*='/profile/']") or card.select_one("a.user-link")
        if not link:
            return None

        href = link.get("href", "")
        if not href.startswith("http"):
            href = f"https://ok.ru{href}"

        # Extract platform ID from URL
        platform_id = href.rstrip("/").split("/")[-1]

        # Extract name
        name_el = card.select_one(".user-name, .name, .shortcut-wrap, h2, h3")
        display_name = name_el.get_text(strip=True) if name_el else ""

        if not display_name:
            return None

        parts = display_name.split(maxsplit=1)
        first_name = parts[0] if parts else ""
        last_name = parts[1] if len(parts) > 1 else ""

        # Photo
        photo_el = card.select_one("img.photo, img.avatar, img[src*='photo']")
        photo_url = photo_el.get("src") if photo_el else None

        # City
        city_el = card.select_one(".user-city, .location, .subtitle")
        city = city_el.get_text(strip=True) if city_el else None

        # Age
        age_el = card.select_one(".age, .user-age")
        age = None
        if age_el:
            try:
                age_text = age_el.get_text(strip=True)
                age = int("".join(c for c in age_text if c.isdigit()))
            except (ValueError, TypeError):
                pass

        # Calculate similarity
        similarity = self._calculate_name_similarity(target_name, display_name)

        return {
            'platform': 'ok',
            'platform_id': str(platform_id),
            'username': f"profile/{platform_id}",
            'profile_url': href,
            'first_name': first_name,
            'last_name': last_name,
            'display_name': display_name,
            'photo_url': photo_url,
            'city': city,
            'age': age,
            'name_similarity': similarity,
            'name_match': similarity > 50,
        }

    def _demo_search(
        self,
        query: str,
        city: Optional[str],
        age_from: Optional[int],
        age_to: Optional[int],
        count: int,
    ) -> List[Dict[str, Any]]:
        """
        Generate demo OK search results.

        Uses a seeded RNG based on query hash for reproducible results.
        Returns 3 profiles: one near-exact match and two partial matches.
        """
        logger.info(f"OK demo search for: '{query}'")

        # Seed RNG from query for reproducibility
        seed = int(hashlib.md5(query.encode('utf-8'), usedforsecurity=False).hexdigest()[:8], 16)
        rng = random.Random(seed)

        query_parts = query.strip().split()
        first_name = query_parts[0] if query_parts else 'Иван'
        last_name = query_parts[1] if len(query_parts) > 1 else 'Иванов'

        # Generate 3 demo profiles
        demo_profiles = []

        # Profile 1: Near-exact match (same name)
        ok_id_1 = str(100000000 + rng.randint(0, 99999999))
        city_1 = city or rng.choice(_DEMO_CITIES)
        age_1 = rng.randint(22, 55)
        demo_profiles.append({
            'platform': 'ok',
            'platform_id': ok_id_1,
            'username': f"profile/{ok_id_1}",
            'profile_url': f"https://ok.ru/profile/{ok_id_1}",
            'first_name': first_name,
            'last_name': last_name,
            'display_name': f"{first_name} {last_name}",
            'photo_url': f"https://ok.ru/res/stub_photo_{ok_id_1}.jpg",
            'city': city_1,
            'age': age_1,
        })

        # Profile 2: Same last name, different first name
        ok_id_2 = str(100000000 + rng.randint(0, 99999999))
        alt_first = rng.choice(_DEMO_FIRST_NAMES_MALE + _DEMO_FIRST_NAMES_FEMALE)
        # Avoid picking the same first name
        while alt_first == first_name:
            alt_first = rng.choice(_DEMO_FIRST_NAMES_MALE + _DEMO_FIRST_NAMES_FEMALE)
        city_2 = rng.choice(_DEMO_CITIES)
        age_2 = rng.randint(20, 60)
        demo_profiles.append({
            'platform': 'ok',
            'platform_id': ok_id_2,
            'username': f"profile/{ok_id_2}",
            'profile_url': f"https://ok.ru/profile/{ok_id_2}",
            'first_name': alt_first,
            'last_name': last_name,
            'display_name': f"{alt_first} {last_name}",
            'photo_url': f"https://ok.ru/res/stub_photo_{ok_id_2}.jpg",
            'city': city_2,
            'age': age_2,
        })

        # Profile 3: Different last name, same first name
        ok_id_3 = str(100000000 + rng.randint(0, 99999999))
        alt_last = rng.choice(_DEMO_LAST_NAMES)
        while alt_last == last_name:
            alt_last = rng.choice(_DEMO_LAST_NAMES)
        city_3 = rng.choice(_DEMO_CITIES)
        age_3 = rng.randint(18, 65)
        demo_profiles.append({
            'platform': 'ok',
            'platform_id': ok_id_3,
            'username': f"profile/{ok_id_3}",
            'profile_url': f"https://ok.ru/profile/{ok_id_3}",
            'first_name': first_name,
            'last_name': alt_last,
            'display_name': f"{first_name} {alt_last}",
            'photo_url': f"https://ok.ru/res/stub_photo_{ok_id_3}.jpg",
            'city': city_3,
            'age': age_3,
        })

        # Calculate name similarity for each
        for profile in demo_profiles:
            similarity = self._calculate_name_similarity(query, profile['display_name'])
            profile['name_similarity'] = similarity
            profile['name_match'] = similarity > 50

        # Apply filters
        filtered = []
        for p in demo_profiles:
            if city and p.get('city') and city.lower() not in p['city'].lower():
                continue
            if age_from and p.get('age') and p['age'] < age_from:
                continue
            if age_to and p.get('age') and p['age'] > age_to:
                continue
            filtered.append(p)

        # Sort by similarity descending
        filtered.sort(key=lambda r: r.get('name_similarity', 0), reverse=True)
        return filtered[:count]

    def _calculate_name_similarity(self, target: str, found: str) -> float:
        """
        Calculate name similarity score (0-100).

        Handles Cyrillic names. Uses part-based matching for first/last names.

        Args:
            target: The name being searched for
            found: The name found in results

        Returns:
            Similarity score from 0.0 to 100.0
        """
        if not target or not found:
            return 0.0

        target_lower = target.lower().strip()
        found_lower = found.lower().strip()

        # Exact match
        if target_lower == found_lower:
            return 100.0

        target_parts = target_lower.split()
        found_parts = found_lower.split()

        # Single-word: use SequenceMatcher
        if len(target_parts) < 2 or len(found_parts) < 2:
            return SequenceMatcher(None, target_lower, found_lower).ratio() * 100

        # Two-part name: score first and last independently
        target_first = target_parts[0]
        target_last = target_parts[-1]
        found_first = found_parts[0]
        found_last = found_parts[-1]

        first_score = SequenceMatcher(None, target_first, found_first).ratio()
        last_score = SequenceMatcher(None, target_last, found_last).ratio()

        # If first name barely matches, cap total score
        if first_score < 0.5:
            return min(last_score * 50, 45)

        if last_score < 0.5:
            return min(first_score * 50, 40)

        # Both parts match: weighted combination (50/50)
        return (first_score * 50) + (last_score * 50)


# Module-level singleton instance
ok_search_integration = OKSearchIntegration()
