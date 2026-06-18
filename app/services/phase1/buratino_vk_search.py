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

from app.services.phase1.transliteration import transliterate

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
        """Calculate name similarity score (0-100). Handles Cyrillic/Latin.

        Uses part-based matching: first name and last name are scored independently.
        Handles both name orders:
        - "Артем Судин" (First Last — VK/Western convention)
        - "Судин Артем Алексеевич" (Last First Patronymic — Russian convention)

        CRITICAL: first name must match for a high overall score — last-name-only
        matches are capped at 45% to prevent false positives like
        "Maxim Kozlov" matching search "Артём Козлов".
        """
        if not target or not found:
            return 0.0

        target_lower = target.lower().strip()
        found_lower = found.lower().strip()

        # Transliterate both to Latin for cross-script comparison
        target_lat = transliterate(target_lower)
        found_lat = transliterate(found_lower)

        target_parts_cyr = target_lower.split()
        found_parts_cyr = found_lower.split()
        target_parts = target_lat.split()
        found_parts = found_lat.split()

        # Single-word queries: use simple sequence matching
        if len(target_parts) < 2 or len(found_parts) < 2:
            return max(
                SequenceMatcher(None, target_lower, found_lower).ratio(),
                SequenceMatcher(None, target_lat, found_lat).ratio(),
            ) * 100

        # Detect name order for target.
        # Russian convention (3+ tokens): Last First Patronymic
        # VK/Western (2 tokens): First Last
        if len(target_parts) >= 3:
            # LFP: target[0]=last, target[1]=first, target[2]=patronymic
            target_first_lat = target_parts[1]
            target_last_lat = target_parts[0]
            target_first_cyr = target_parts_cyr[1]
            target_last_cyr = target_parts_cyr[0]
        else:
            # FL: target[0]=first, target[-1]=last
            target_first_lat = target_parts[0]
            target_last_lat = target_parts[-1]
            target_first_cyr = target_parts_cyr[0]
            target_last_cyr = target_parts_cyr[-1]

        # VK returns "First Last" always
        found_first_lat = found_parts[0]
        found_last_lat = found_parts[-1]
        found_first_cyr = found_parts_cyr[0]
        found_last_cyr = found_parts_cyr[-1]

        # -- Last name score (0.0 - 1.0) --
        last_score = max(
            SequenceMatcher(None, target_last_lat, found_last_lat).ratio(),
            SequenceMatcher(None, target_last_cyr, found_last_cyr).ratio(),
        )
        # Substring match bonus
        if (len(target_last_lat) >= 3 and len(found_last_lat) >= 3
                and (target_last_lat in found_last_lat or found_last_lat in target_last_lat)):
            last_score = max(last_score, 1.0)

        # -- First name score (0.0 - 1.0) --
        first_score = max(
            SequenceMatcher(None, target_first_lat, found_first_lat).ratio(),
            SequenceMatcher(None, target_first_cyr, found_first_cyr).ratio(),
        )
        # Substring match bonus
        if (len(target_first_lat) >= 3 and len(found_first_lat) >= 3
                and (target_first_lat in found_first_lat or found_first_lat in target_first_lat)):
            first_score = max(first_score, 1.0)

        # Diminutive matching: check if first names share a common formal root
        try:
            from app.services.phase1.russian_diminutives import get_all_name_variants
            search_variants = set(v.lower() for v in get_all_name_variants(target_first_cyr))
            profile_variants = set(v.lower() for v in get_all_name_variants(found_first_cyr))
            if search_variants & profile_variants:
                first_score = max(first_score, 0.90)
        except ImportError as exc:
            logger.debug("Diminutive matching unavailable: %s", exc)

        # CRITICAL: If first name doesn't match at all, cap the total score.
        # This prevents false positives like "Максим Козлов" matching "Марк Козлов"
        # or "Сергей Сидоров" matching "Андрей Сидоров".
        # Threshold 0.65 blocks coincidental SequenceMatcher overlap:
        #   Максим/Марк ≈ 0.60, Сергей/Андрей ≈ 0.50, Николай/Никита ≈ 0.62
        # Legitimate variants are safe: Ё/Е pairs score 1.0 via Latin transliteration,
        # and diminutive matches are already boosted to 0.90 above.
        if first_score < 0.65:
            return min(last_score * 50, 45)  # Last-name-only → max 45%

        if last_score < 0.65:
            return min(first_score * 50, 40)  # First-name-only → max 40%

        # Both names match: weighted combination (50/50)
        return (first_score * 50) + (last_score * 50)

    # VK API returns city names in profile language — map English↔Russian for top cities
    _CITY_ALIASES = {
        'москва': 'moscow', 'санкт-петербург': 'saint petersburg',
        'новосибирск': 'novosibirsk', 'екатеринбург': 'yekaterinburg',
        'казань': 'kazan', 'нижний новгород': 'nizhny novgorod',
        'челябинск': 'chelyabinsk', 'самара': 'samara', 'омск': 'omsk',
        'ростов-на-дону': 'rostov-on-don', 'уфа': 'ufa', 'красноярск': 'krasnoyarsk',
        'воронеж': 'voronezh', 'пермь': 'perm', 'волгоград': 'volgograd',
        'краснодар': 'krasnodar', 'тюмень': 'tyumen', 'саратов': 'saratov',
        'тольятти': 'tolyatti', 'ижевск': 'izhevsk', 'барнаул': 'barnaul',
        'иркутск': 'irkutsk', 'хабаровск': 'khabarovsk', 'владивосток': 'vladivostok',
        'ярославль': 'yaroslavl', 'махачкала': 'makhachkala', 'томск': 'tomsk',
        'оренбург': 'orenburg', 'кемерово': 'kemerovo', 'новокузнецк': 'novokuznetsk',
        'рязань': 'ryazan', 'астрахань': 'astrakhan', 'набережные челны': 'naberezhnye chelny',
        'пенза': 'penza', 'липецк': 'lipetsk', 'киров': 'kirov', 'тула': 'tula',
        'чебоксары': 'cheboksary', 'калининград': 'kaliningrad',
        'санкт петербург': 'saint petersburg', 'петербург': 'saint petersburg',
        'спб': 'saint petersburg', 'мск': 'moscow', 'питер': 'saint petersburg',
    }
    # Build reverse mapping (english → russian)
    _CITY_ALIASES_REV = {v: k for k, v in _CITY_ALIASES.items()}
    # Also handle 'st. petersburg' / 'st petersburg'
    _CITY_ALIASES_REV['st. petersburg'] = 'санкт-петербург'
    _CITY_ALIASES_REV['st petersburg'] = 'санкт-петербург'

    def _city_matches(self, search_city: str, profile_city: str) -> bool:
        """Check if cities match across Russian/English naming."""
        sc = search_city.lower().strip()
        pc = profile_city.lower().strip()

        # Direct substring match
        if sc in pc or pc in sc:
            return True

        # Transliteration match (Новосибирск → novosibirsk)
        sc_lat = transliterate(sc)
        pc_lat = transliterate(pc)
        if sc_lat in pc_lat or pc_lat in sc_lat:
            return True

        # Alias match (Москва ↔ Moscow)
        sc_alias = self._CITY_ALIASES.get(sc) or self._CITY_ALIASES_REV.get(sc)
        pc_alias = self._CITY_ALIASES.get(pc) or self._CITY_ALIASES_REV.get(pc)
        if sc_alias and (sc_alias in pc or sc_alias in pc_lat):
            return True
        if pc_alias and (pc_alias in sc or pc_alias in sc_lat):
            return True
        # Both aliased → compare aliases
        if sc_alias and pc_alias and (sc_alias == pc_alias):
            return True

        return False

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
        target_name: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        birth_day: Optional[int] = None,
        birth_month: Optional[int] = None,
        birth_year: Optional[int] = None,
        strict_mode: bool = True,
    ) -> Tuple[List[VKProfileResult], int]:
        """
        Search VKontakte for people by name.

        Strategy:
        1. VKWebSearch with web token (PRIMARY — calls users.search via cached
           web token obtained from Playwright auto-login; fast after first run)
        2. Demo mode (if no token at all)

        Note: users.search requires a user/web token; service tokens get Error 28.
        VKWebSearch handles web token lifecycle (auto-login, caching, refresh).
        """
        if not target_name:
            if first_name and last_name:
                target_name = f"{first_name} {last_name}"
            else:
                target_name = query

        # VK API users.search only handles first + last name.
        # Patronymic (3rd token in Russian LFP names) causes 0 results.
        # Strip it from the API query but keep full name for matching.
        vk_query = query
        query_tokens = query.strip().split()
        if first_name or last_name:
            vk_query = f"{(last_name or '').strip()} {(first_name or '').strip()}".strip() or query
            logger.info(
                "VK search: using explicit name fields first=%r last=%r for query %r",
                first_name, last_name, query,
            )
        elif len(query_tokens) >= 3:
            # Russian convention: Last First Patronymic → send "Last First" to VK
            vk_query = f"{query_tokens[0]} {query_tokens[1]}"
            logger.info(f"VK search: stripped patronymic: '{query}' -> '{vk_query}'")

        # ── Demo mode ──
        if self._demo_mode:
            demo_query = f"{first_name} {last_name}".strip() if first_name and last_name else vk_query
            return self._demo_search(demo_query, city, age_from, age_to, count, target_name)

        all_profiles_by_id: Dict[int, VKProfileResult] = {}

        # ── PRIMARY: VKWebSearch (web token users.search + newsfeed + screen name) ──
        # Pass FULL query (with patronymic) to VKWebSearch — it handles
        # patronymic stripping internally and uses the full name for
        # correct LFP name order detection in verification.
        try:
            from app.services.phase1.vk_web_search import VKWebSearch
            web_searcher = VKWebSearch(service_token=self.token)
            raw_profiles, _ = web_searcher.search(
                query,
                first_name=first_name,
                last_name=last_name,
                birth_day=birth_day,
                birth_month=birth_month,
                birth_year=birth_year,
                strict_mode=strict_mode,
            )
            for item in raw_profiles:
                vk_id = item.get('id')
                if vk_id and vk_id not in all_profiles_by_id:
                    profile = self._parse_profile(item, target_name)
                    if strict_mode and not profile.name_match:
                        continue
                    # People Search: skip verify but reject completely unrelated (< 30%)
                    # people_search results from VK API pass easily; this catches
                    # newsfeed/screen_name results that slipped through
                    if not strict_mode and profile.name_similarity < 30:
                        logger.info(
                            f"Filtered '{profile.full_name}' — similarity "
                            f"{profile.name_similarity:.0f}% < 30%"
                        )
                        continue
                    all_profiles_by_id[vk_id] = profile
            logger.info(f"VK search: {len(all_profiles_by_id)} profiles for '{query}' (strict={strict_mode})")
        except Exception as e:
            logger.warning(f"VK web search failed: {e}")

        # ── FALLBACK: Direct users.search with VK_USER_TOKEN ──
        # VKWebSearch may return 0 if the web token is expired/missing.
        # VK_USER_TOKEN (from OAuth) can also call users.search.
        if not all_profiles_by_id and self.session:
            user_token = os.environ.get("VK_USER_TOKEN") or os.environ.get("VK_TOKEN")
            if user_token:
                max_pages = 3 if not strict_mode else 1
                for page in range(max_pages):
                    try:
                        self._rate_limit()
                        params = {
                            'q': vk_query,
                            'count': 1000,
                            'offset': page * 1000,
                            'fields': ','.join(self.PROFILE_FIELDS),
                            'access_token': user_token,
                            'v': self.API_VERSION,
                        }
                        if birth_year:
                            params['birth_year'] = birth_year
                        resp = self.session.post(
                            f"{self.API_BASE_URL}/users.search",
                            data=params, timeout=15,
                        )
                        data = resp.json()
                        if 'error' in data:
                            err = data['error']
                            logger.warning(
                                f"VK users.search fallback error {err.get('error_code')}: "
                                f"{err.get('error_msg')}"
                            )
                            break
                        else:
                            items = data.get('response', {}).get('items', [])
                            for item in items:
                                vk_id = item.get('id')
                                if vk_id and vk_id not in all_profiles_by_id:
                                    profile = self._parse_profile(item, target_name)
                                    if strict_mode and not profile.name_match:
                                        continue
                                    all_profiles_by_id[vk_id] = profile
                            logger.info(
                                f"VK fallback users.search page {page+1}: {len(items)} raw, "
                                f"{len(all_profiles_by_id)} total for '{query}'"
                            )
                            # Stop if fewer than 1000 results (no more pages)
                            if len(items) < 1000:
                                break
                    except Exception as e:
                        logger.warning(f"VK users.search fallback error: {e}")
                        break

        # ── Apply filters ──
        if city or age_from or age_to:
            filtered = {}
            for vk_id, profile in all_profiles_by_id.items():
                if city and profile.city:
                    if not self._city_matches(city, profile.city):
                        continue
                if age_from and profile.age and profile.age < age_from:
                    continue
                if age_to and profile.age and profile.age > age_to:
                    continue
                filtered[vk_id] = profile
            logger.info(
                f"VK filter: {len(all_profiles_by_id)} -> {len(filtered)} "
                f"(city={city!r}, age={age_from}-{age_to})"
            )
            # Fallback: if city+age filter removed ALL results, retry with age-only
            if not filtered and all_profiles_by_id and city:
                logger.info("VK filter fallback: retrying without city filter")
                for vk_id, profile in all_profiles_by_id.items():
                    if age_from and profile.age and profile.age < age_from:
                        continue
                    if age_to and profile.age and profile.age > age_to:
                        continue
                    filtered[vk_id] = profile
                logger.info(f"VK filter fallback: {len(filtered)} profiles after age-only filter")
            all_profiles_by_id = filtered

        profiles = list(all_profiles_by_id.values())
        profiles.sort(key=lambda p: p.name_similarity, reverse=True)
        if strict_mode:
            return profiles[:count], len(all_profiles_by_id)
        return profiles, len(all_profiles_by_id)

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

    def search_expanded(
        self,
        query: str,
        city: Optional[str] = None,
        age_from: Optional[int] = None,
        age_to: Optional[int] = None,
        count: int = 50
    ) -> List[VKProfileResult]:
        """
        Expanded search: original name + diminutives + transliterations + first-name-only.
        Deduplicates by VK user ID. Returns all results with search_variant tags.

        Args:
            query: Full name (e.g. "Тихон Портной")
            city, age_from, age_to: Filters
            count: Max results per sub-search

        Returns:
            Combined, deduplicated list of VKProfileResult
        """
        all_profiles: Dict[int, VKProfileResult] = {}  # keyed by vk_id

        query_parts = query.strip().split()
        first_name = query_parts[0] if query_parts else query
        last_name = query_parts[1] if len(query_parts) > 1 else ""

        # ── Step 1: Original name search ──
        logger.info(f"Expanded search: original query '{query}'")
        profiles, _ = self.search(
            query=query, city=city, age_from=age_from,
            age_to=age_to, count=count, target_name=query
        )
        for p in profiles:
            if p.vk_id not in all_profiles:
                all_profiles[p.vk_id] = p

        # ── Step 2: Diminutive variants ──
        try:
            from app.services.phase1.russian_diminutives import get_all_name_variants
            name_variants = get_all_name_variants(first_name)
            # Skip the first one (it's the original name)
            for variant in name_variants[1:5]:  # Max 4 diminutive searches
                variant_query = f"{variant} {last_name}".strip() if last_name else variant
                logger.info(f"Expanded search: diminutive '{variant_query}'")
                try:
                    dim_profiles, _ = self.search(
                        query=variant_query, city=city, age_from=age_from,
                        age_to=age_to, count=20, target_name=query
                    )
                    for p in dim_profiles:
                        if p.vk_id not in all_profiles:
                            all_profiles[p.vk_id] = p
                except Exception as e:
                    logger.warning(f"Diminutive search '{variant_query}' failed: {e}")
                time.sleep(0.5)
        except ImportError:
            logger.warning("russian_diminutives module not available")

        # ── Step 3: Transliteration variants (screen name guessing) ──
        # Only run if we have few results from accurate strategies (steps 1-2)
        if len(all_profiles) < 5:
            logger.info(
                f"Expanded search: only {len(all_profiles)} results from people search, "
                f"trying screen name guessing..."
            )
            try:
                from app.services.phase1.transliteration import transliterate_name_part, generate_username_patterns
                first_variants = transliterate_name_part(first_name, max_variants=3)
                last_variants = transliterate_name_part(last_name, max_variants=3) if last_name else ['']

                screen_name_candidates = []
                for f_lat in first_variants:
                    for l_lat in last_variants:
                        if l_lat:
                            screen_name_candidates.extend(generate_username_patterns(f_lat, l_lat))

                # Deduplicate
                screen_name_candidates = list(dict.fromkeys(screen_name_candidates))[:20]

                if screen_name_candidates and self.token and self.session:
                    logger.info(f"Expanded search: resolving {len(screen_name_candidates)} transliterated screen names")
                    resolved_ids = []
                    for name in screen_name_candidates:
                        try:
                            resp = self.session.post(
                                f"{self.API_BASE_URL}/utils.resolveScreenName",
                                data={
                                    'screen_name': name,
                                    'access_token': self.token,
                                    'v': self.API_VERSION,
                                },
                                timeout=5,
                            )
                            data = resp.json()
                            result = data.get('response', {})
                            if result and result.get('type') == 'user':
                                uid = result['object_id']
                                if uid not in all_profiles:
                                    resolved_ids.append(uid)
                            time.sleep(0.35)
                        except Exception as e:
                            logger.debug(f"[VKSearch] resolveScreenName failed: {e}")

                    # Enrich resolved IDs (name verification applied inside _enrich_profiles)
                    if resolved_ids:
                        from app.services.phase1.vk_web_search import VKWebSearch
                        web = VKWebSearch(service_token=self.token)
                        enriched = web._enrich_profiles(resolved_ids, query)
                        for p_data in enriched:
                            p = self._parse_profile(p_data, query)
                            if p.vk_id not in all_profiles and p.name_similarity >= 30:
                                all_profiles[p.vk_id] = p
                            elif p.vk_id not in all_profiles:
                                logger.info(
                                    f"Filtered out screen_name match '{p.full_name}' "
                                    f"(similarity={p.name_similarity:.0f}%, too low)"
                                )
            except ImportError:
                logger.warning("transliteration module not available")
        else:
            logger.info(
                f"Expanded search: got {len(all_profiles)} results from people search, "
                f"skipping screen name guessing"
            )

        # ── Step 4: First-name-only search with fuzzy surname matching ──
        if last_name and self.token:
            try:
                from app.services.phase1.fuzzy_matching import surname_similarity
                logger.info(f"Expanded search: first-name-only '{first_name}'")
                fn_profiles, _ = self.search(
                    query=first_name, city=city, age_from=age_from,
                    age_to=age_to, count=30, target_name=query
                )
                for p in fn_profiles:
                    if p.vk_id not in all_profiles:
                        # Apply fuzzy surname filter
                        score = surname_similarity(last_name, p.last_name)
                        if score >= 0.6:
                            # Recalculate name_similarity with fuzzy bonus
                            p.name_similarity = max(p.name_similarity, score * 100)
                            p.name_match = p.name_similarity > 50
                            all_profiles[p.vk_id] = p
            except ImportError:
                logger.warning("fuzzy_matching module not available")

        result = list(all_profiles.values())
        result.sort(key=lambda p: p.name_similarity, reverse=True)
        logger.info(f"Expanded search: total {len(result)} unique profiles for '{query}'")
        return result

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
        Search VK (with expanded name variants) and save results to database.

        Runs diminutive, transliteration, and fuzzy searches in addition to exact name.
        Deduplicates by VK user ID.

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

        # Use expanded search (diminutives + transliterations + fuzzy)
        profiles = self.search_expanded(
            query=query,
            city=city,
            age_from=age_from,
            age_to=age_to,
            count=count
        )

        saved_profiles = []

        for vk_profile in profiles:
            # Skip profiles with very low name similarity (likely false matches)
            if vk_profile.name_similarity < 30:
                logger.info(
                    f"Skipping '{vk_profile.full_name}' — name_similarity={vk_profile.name_similarity:.0f}%"
                )
                continue

            # Check if profile already exists
            existing = SocialProfile.query.filter_by(
                investigation_id=investigation_id,
                platform='vk',
                platform_id=str(vk_profile.vk_id)
            ).first()

            if existing:
                # Update existing — keep highest similarity
                if vk_profile.name_similarity > (existing.name_similarity or 0):
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
