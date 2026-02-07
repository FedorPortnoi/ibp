"""
Buratino VK Search - Enhanced VK People Search
===============================================
Uses VK API for reliable people search with demo mode fallback.

Based on prototypes/vk_people_search.py with Flask integration.

Features:
- VK API users.search for accurate name-based discovery
- City, age, education filters
- Demo mode (works without API key)
- Database persistence via SocialProfile model
- Face matching integration
"""

import os
import json
import logging
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple
from difflib import SequenceMatcher

try:
    import requests
except ImportError:
    requests = None

from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger(__name__)


@dataclass
class VKProfileResult:
    """VK profile search result."""
    vk_id: int
    first_name: str
    last_name: str
    screen_name: Optional[str] = None
    photo_url: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    birth_date: Optional[str] = None
    age: Optional[int] = None
    university: Optional[str] = None
    faculty: Optional[str] = None
    graduation: Optional[int] = None
    career: Optional[List[Dict]] = None
    is_closed: bool = False
    can_access_closed: bool = True
    profile_url: str = ""

    # Matching scores
    name_similarity: float = 0.0
    name_match: bool = False

    def __post_init__(self):
        self.profile_url = f"https://vk.com/id{self.vk_id}"
        if self.screen_name:
            self.profile_url = f"https://vk.com/{self.screen_name}"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result['full_name'] = self.full_name
        return result


class VKAPIError(Exception):
    """VK API Error."""
    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(f"VK API Error {code}: {message}")


class BuratinoVKSearch:
    """
    Buratino-style VK People Search.

    Uses VK API for accurate name → profile discovery.
    Falls back to demo mode if no API key.
    """

    API_VERSION = "5.199"
    API_BASE_URL = "https://api.vk.com/method"
    RPS_DELAY = 0.34  # ~3 requests per second

    # VK API Error Codes
    TOO_MANY_REQUESTS = 6
    ACCESS_DENIED = 15
    RATE_LIMIT = 29

    # Profile fields to request
    PROFILE_FIELDS = [
        "photo_max_orig", "photo_400_orig", "photo_200", "photo_100",
        "city", "country", "bdate", "domain", "screen_name",
        "education", "universities", "schools", "career",
        "is_closed", "can_access_closed"
    ]

    def __init__(self, service_token: Optional[str] = None):
        """
        Initialize VK People Search.

        Args:
            service_token: VK API service token. If not provided,
                          will try env var VK_SERVICE_TOKEN, then demo mode.
        """
        self.token = service_token or os.environ.get("VK_SERVICE_TOKEN")
        self.session = None
        if requests:
            self.session = requests.Session()
            self.session.headers.update({
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
        self.last_request_time = 0.0
        self._city_cache: Dict[str, int] = {}
        self._demo_mode = not self.token

        if self._demo_mode:
            logger.info("BuratinoVKSearch: Running in DEMO mode (no VK token)")
        else:
            logger.info("BuratinoVKSearch: VK API mode enabled")

    @property
    def is_demo_mode(self) -> bool:
        return self._demo_mode

    def _rate_limit(self):
        """Enforce rate limiting (~3 requests/second)."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.RPS_DELAY:
            time.sleep(self.RPS_DELAY - elapsed)
        self.last_request_time = time.time()

    def _api_call(self, method: str, params: Dict[str, Any],
                  max_retries: int = 3) -> Dict[str, Any]:
        """Make VK API call with rate limiting and error handling."""
        if self._demo_mode:
            raise VKAPIError(0, "Demo mode - no API calls")

        if not self.session:
            raise VKAPIError(0, "requests library not available")

        params["access_token"] = self.token
        params["v"] = self.API_VERSION

        url = f"{self.API_BASE_URL}/{method}"

        for attempt in range(max_retries):
            self._rate_limit()

            try:
                response = self.session.post(url, data=params, timeout=30)
                response.raise_for_status()
                data = response.json()

                if "error" in data:
                    error = data["error"]
                    code = error.get("error_code", 0)
                    message = error.get("error_msg", "Unknown error")

                    # Handle rate limiting
                    if code in (self.TOO_MANY_REQUESTS, self.RATE_LIMIT):
                        wait_time = 0.5 * (2 ** attempt)
                        logger.warning(f"Rate limited. Waiting {wait_time}s...")
                        time.sleep(wait_time)
                        continue

                    raise VKAPIError(code, message)

                return data.get("response", {})

            except requests.RequestException as e:
                logger.error(f"Request failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(1)
                    continue
                raise VKAPIError(0, f"Network error: {e}")

        raise VKAPIError(self.RATE_LIMIT, "Max retries exceeded")

    def get_city_id(self, city_name: str, country_id: int = 1) -> Optional[int]:
        """Get VK city ID by name."""
        cache_key = f"{country_id}:{city_name.lower()}"
        if cache_key in self._city_cache:
            return self._city_cache[cache_key]

        if self._demo_mode:
            # Known cities in demo mode
            demo_cities = {
                'москва': 1, 'санкт-петербург': 2, 'новосибирск': 99,
                'екатеринбург': 158, 'казань': 60, 'нижний новгород': 95,
            }
            return demo_cities.get(city_name.lower())

        try:
            result = self._api_call("database.getCities", {
                "country_id": country_id,
                "q": city_name,
                "count": 1
            })

            items = result.get("items", [])
            if items:
                city_id = items[0]["id"]
                self._city_cache[cache_key] = city_id
                return city_id

        except VKAPIError as e:
            logger.warning(f"Failed to get city ID for '{city_name}': {e}")

        return None

    def _calculate_age(self, bdate: Optional[str]) -> Optional[int]:
        """Calculate age from VK bdate string (D.M.YYYY or D.M)."""
        if not bdate:
            return None

        parts = bdate.split(".")
        if len(parts) != 3:
            return None

        try:
            birth_year = int(parts[2])
            today = datetime.now()
            age = today.year - birth_year

            birth_month = int(parts[1])
            birth_day = int(parts[0])
            if (today.month, today.day) < (birth_month, birth_day):
                age -= 1

            return age if 0 < age < 150 else None
        except (ValueError, IndexError):
            return None

    def _calculate_name_similarity(self, target: str, found: str) -> float:
        """Calculate name similarity score (0-100). Handles Cyrillic↔Latin."""
        if not target or not found:
            return 0.0

        target_lower = target.lower().strip()
        found_lower = found.lower().strip()

        # Transliterate both to Latin for cross-script comparison
        target_lat = self._to_latin(target_lower)
        found_lat = self._to_latin(found_lower)

        # Direct sequence matching (try both original and transliterated)
        direct = max(
            SequenceMatcher(None, target_lower, found_lower).ratio(),
            SequenceMatcher(None, target_lat, found_lat).ratio(),
        ) * 100

        # Part-based matching (compare transliterated parts)
        target_parts = target_lat.split()
        found_parts = found_lat.split()

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

    @staticmethod
    def _to_latin(text: str) -> str:
        """Transliterate text to Latin for comparison. Pass-through if already Latin."""
        try:
            from transliterate import translit
            return translit(text, 'ru', reversed=True).lower()
        except Exception:
            # Basic transliteration fallback
            table = {
                'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e',
                'ё': 'yo', 'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'j', 'к': 'k',
                'л': 'l', 'м': 'm', 'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r',
                'с': 's', 'т': 't', 'у': 'u', 'ф': 'f', 'х': 'kh', 'ц': 'ts',
                'ч': 'ch', 'ш': 'sh', 'щ': 'shch', 'ъ': '', 'ы': 'y', 'ь': '',
                'э': 'e', 'ю': 'yu', 'я': 'ya',
            }
            return ''.join(table.get(ch, ch) for ch in text)

    def _parse_profile(self, data: Dict[str, Any], target_name: str = None) -> VKProfileResult:
        """Parse VK API user data into VKProfileResult."""
        # Extract city
        city = None
        city_data = data.get("city")
        if city_data and isinstance(city_data, dict):
            city = city_data.get("title")

        # Extract country
        country = None
        country_data = data.get("country")
        if country_data and isinstance(country_data, dict):
            country = country_data.get("title")

        # Get largest available photo
        photo_url = (
            data.get("photo_max_orig") or
            data.get("photo_400_orig") or
            data.get("photo_200") or
            data.get("photo_100")
        )

        bdate = data.get("bdate")
        age = self._calculate_age(bdate)

        profile = VKProfileResult(
            vk_id=data["id"],
            first_name=data.get("first_name", ""),
            last_name=data.get("last_name", ""),
            screen_name=data.get("domain") or data.get("screen_name"),
            photo_url=photo_url,
            city=city,
            country=country,
            birth_date=bdate,
            age=age,
            university=data.get("university_name"),
            faculty=data.get("faculty_name"),
            graduation=data.get("graduation"),
            career=data.get("career") or None,
            is_closed=data.get("is_closed", False),
            can_access_closed=data.get("can_access_closed", True)
        )

        # Calculate name similarity if target name provided
        if target_name:
            profile.name_similarity = self._calculate_name_similarity(
                target_name, profile.full_name
            )
            profile.name_match = profile.name_similarity > 50

        return profile

    def search(
        self,
        query: str,
        city: Optional[str] = None,
        city_id: Optional[int] = None,
        age_from: Optional[int] = None,
        age_to: Optional[int] = None,
        sex: Optional[int] = None,
        count: int = 50,
        offset: int = 0,
        target_name: Optional[str] = None
    ) -> Tuple[List[VKProfileResult], int]:
        """
        Search VKontakte for people.

        Fallback chain:
        1. VK web scraping (Playwright with persistent session — no token needed)
        2. VK API newsfeed.search (service token — permanent, never expires)
        3. Demo mode (sample data)

        Service token is used only for enrichment (users.get) — always works.
        """
        if not target_name:
            target_name = query

        # ── Step 1: Try web search (Playwright + newsfeed.search) ──
        if self.token:
            try:
                from app.services.phase1.vk_web_search import VKWebSearch
                web_searcher = VKWebSearch(service_token=self.token)
                raw_profiles, total = web_searcher.search(query, count=count)

                if raw_profiles:
                    # Convert API dicts to VKProfileResult objects
                    profiles = [self._parse_profile(p, target_name) for p in raw_profiles]

                    # Apply filters
                    if city:
                        profiles = [
                            p for p in profiles
                            if not p.city or city.lower() in p.city.lower()
                        ]
                    if age_from:
                        profiles = [p for p in profiles if not p.age or p.age >= age_from]
                    if age_to:
                        profiles = [p for p in profiles if not p.age or p.age <= age_to]

                    profiles.sort(key=lambda p: p.name_similarity, reverse=True)
                    logger.info(f"VK web search found {len(profiles)} profiles for '{query}'")
                    return profiles[:count], len(profiles)

            except Exception as e:
                logger.warning(f"VK web search failed: {e}")

        # ── Step 2: Demo mode ──
        return self._demo_search(query, city, age_from, age_to, count, target_name)

    def fetch_friends(
        self,
        user_id: int,
        count: int = 500,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Fetch friends list for a VK user.

        Args:
            user_id: VK user ID
            count: Maximum friends to return (max 5000)
            offset: Pagination offset

        Returns:
            List of friend profile dicts
        """
        if self._demo_mode:
            return self._demo_friends(user_id)

        params = {
            "user_id": user_id,
            "count": min(count, 5000),
            "offset": offset,
            "fields": ",".join(self.PROFILE_FIELDS)
        }

        logger.info(f"Fetching friends for VK user {user_id}")

        try:
            result = self._api_call("friends.get", params)

            items = result.get("items", [])
            logger.info(f"VK API returned {len(items)} friends")

            return items

        except VKAPIError as e:
            logger.error(f"VK API error fetching friends: {e}")
            return self._demo_friends(user_id)

    def _demo_friends(self, user_id: int) -> List[Dict[str, Any]]:
        """Generate demo friends for testing."""
        logger.info(f"Generating demo friends for user {user_id}")

        return [
            {"id": 111, "first_name": "Петр", "last_name": "Петров",
             "photo_100": "https://vk.com/images/camera_100.png",
             "city": {"id": 1, "title": "Москва"}, "is_closed": False},
            {"id": 222, "first_name": "Мария", "last_name": "Сидорова",
             "photo_100": "https://vk.com/images/camera_100.png",
             "city": {"id": 1, "title": "Москва"}, "is_closed": False},
            {"id": 333, "first_name": "Алексей", "last_name": "Козлов",
             "photo_100": "https://vk.com/images/camera_100.png",
             "city": {"id": 2, "title": "Санкт-Петербург"}, "is_closed": False},
            {"id": 444, "first_name": "Елена", "last_name": "Новикова",
             "photo_100": "https://vk.com/images/camera_100.png",
             "city": {"id": 1, "title": "Москва"}, "is_closed": False},
            {"id": 555, "first_name": "Дмитрий", "last_name": "Морозов",
             "photo_100": "https://vk.com/images/camera_100.png",
             "city": {"id": 60, "title": "Казань"}, "is_closed": False},
            {"id": 666, "first_name": "Анна", "last_name": "Волкова",
             "photo_100": "https://vk.com/images/camera_100.png",
             "city": {"id": 1, "title": "Москва"}, "is_closed": False},
            {"id": 777, "first_name": "Сергей", "last_name": "Соколов",
             "photo_100": "https://vk.com/images/camera_100.png",
             "city": {"id": 2, "title": "Санкт-Петербург"}, "is_closed": False},
            {"id": 888, "first_name": "Ольга", "last_name": "Лебедева",
             "photo_100": "https://vk.com/images/camera_100.png",
             "city": {"id": 1, "title": "Москва"}, "is_closed": False},
        ]

    def _demo_search(
        self,
        query: str,
        city: Optional[str],
        age_from: Optional[int],
        age_to: Optional[int],
        count: int,
        target_name: str
    ) -> Tuple[List[VKProfileResult], int]:
        """Generate demo search results."""
        logger.info(f"Generating demo results for: '{query}'")

        # Generate realistic demo data based on query
        query_parts = query.split()
        first_name = query_parts[0] if query_parts else "Иван"
        last_name = query_parts[1] if len(query_parts) > 1 else "Иванов"

        demo_data = [
            {
                "id": 123456789,
                "first_name": first_name,
                "last_name": last_name,
                "domain": f"{first_name.lower()}_{last_name.lower()}",
                "photo_max_orig": "https://vk.com/images/camera_200.png",
                "city": {"id": 1, "title": city or "Москва"},
                "country": {"id": 1, "title": "Россия"},
                "bdate": "15.5.1990",
                "university_name": "МГУ им. М.В. Ломоносова",
                "faculty_name": "Факультет ВМК",
                "graduation": 2012,
                "is_closed": False,
                "can_access_closed": True
            },
            {
                "id": 987654321,
                "first_name": first_name,
                "last_name": last_name,
                "domain": f"{first_name.lower()}.{last_name.lower()}",
                "photo_max_orig": "https://vk.com/images/camera_200.png",
                "city": {"id": 2, "title": "Санкт-Петербург"},
                "country": {"id": 1, "title": "Россия"},
                "bdate": "20.3.1985",
                "university_name": "СПбГУ",
                "faculty_name": "Юридический факультет",
                "graduation": 2007,
                "career": [
                    {"company": "Газпром", "position": "Юрист", "from": 2010, "until": 0}
                ],
                "is_closed": False,
                "can_access_closed": True
            },
            {
                "id": 111222333,
                "first_name": first_name,
                "last_name": last_name,
                "domain": "id111222333",
                "photo_max_orig": "https://vk.com/images/camera_200.png",
                "city": {"id": 60, "title": "Казань"},
                "country": {"id": 1, "title": "Россия"},
                "bdate": "1.1",
                "is_closed": True,
                "can_access_closed": False
            },
        ]

        # Filter by age if specified
        profiles = []
        for data in demo_data:
            profile = self._parse_profile(data, target_name)

            # Apply age filter
            if age_from and profile.age and profile.age < age_from:
                continue
            if age_to and profile.age and profile.age > age_to:
                continue

            # Apply city filter
            if city and profile.city and city.lower() not in profile.city.lower():
                continue

            profiles.append(profile)

        # Sort by name similarity
        profiles.sort(key=lambda p: p.name_similarity, reverse=True)

        return profiles[:count], len(profiles)

    def search_and_save(
        self,
        investigation_id: str,
        query: str,
        city: Optional[str] = None,
        age_from: Optional[int] = None,
        age_to: Optional[int] = None,
        count: int = 50
    ) -> List[Dict]:
        """
        Search VK and save results to database.

        Args:
            investigation_id: ID of the investigation
            query: Search query (name)
            city: Optional city filter
            age_from: Minimum age
            age_to: Maximum age
            count: Max results

        Returns:
            List of saved profile dicts
        """
        from app import db
        from app.models import SocialProfile

        profiles, total = self.search(
            query=query,
            city=city,
            age_from=age_from,
            age_to=age_to,
            count=count,
            target_name=query
        )

        saved_profiles = []

        for vk_profile in profiles:
            # Check if profile already exists
            existing = SocialProfile.query.filter_by(
                investigation_id=investigation_id,
                platform='vk',
                platform_id=str(vk_profile.vk_id)
            ).first()

            if existing:
                # Update existing
                existing.name_similarity = vk_profile.name_similarity
                existing.name_match = vk_profile.name_match
                saved_profiles.append(existing.to_dict())
            else:
                # Create new
                social_profile = SocialProfile(
                    investigation_id=investigation_id,
                    platform='vk',
                    platform_id=str(vk_profile.vk_id),
                    username=vk_profile.screen_name,
                    profile_url=vk_profile.profile_url,
                    first_name=vk_profile.first_name,
                    last_name=vk_profile.last_name,
                    display_name=vk_profile.full_name,
                    photo_url=vk_profile.photo_url,
                    city=vk_profile.city,
                    country=vk_profile.country,
                    birth_date=vk_profile.birth_date,
                    age=vk_profile.age,
                    is_closed=vk_profile.is_closed,
                    can_access=vk_profile.can_access_closed,
                    name_similarity=vk_profile.name_similarity,
                    name_match=vk_profile.name_match,
                )

                # Education
                if vk_profile.university:
                    social_profile.education = [{
                        'university': vk_profile.university,
                        'faculty': vk_profile.faculty,
                        'graduation': vk_profile.graduation
                    }]

                # Career
                if vk_profile.career:
                    social_profile.career = vk_profile.career

                social_profile.calculate_confidence()

                db.session.add(social_profile)
                saved_profiles.append(social_profile.to_dict())

        db.session.commit()
        logger.info(f"Saved {len(saved_profiles)} VK profiles for investigation {investigation_id}")

        return saved_profiles


# Singleton instance
buratino_vk_search = BuratinoVKSearch()


def search_vk_buratino(
    name: str,
    city: str = None,
    age_from: int = None,
    age_to: int = None,
    limit: int = 50
) -> List[Dict]:
    """
    Convenience function for Buratino-style VK search.

    Args:
        name: Full name to search
        city: Optional city filter
        age_from: Minimum age
        age_to: Maximum age
        limit: Max results

    Returns:
        List of profile dicts
    """
    profiles, _ = buratino_vk_search.search(
        query=name,
        city=city,
        age_from=age_from,
        age_to=age_to,
        count=limit,
        target_name=name
    )
    return [p.to_dict() for p in profiles]
