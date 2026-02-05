"""
Odnoklassniki (OK.ru) People Search - IBP Prototype B.7
Search and extract profiles from OK.ru social network

Features:
- People search by name, city, age, education
- Profile data extraction
- HTML parsing with BeautifulSoup
- API interaction (where available)
- Pagination support
- Rate limiting and session management

Requirements:
    pip install requests beautifulsoup4 lxml

Usage:
    search = OKPeopleSearch()
    results = search.search("Иван Петров", city="Москва", age_from=25, age_to=35)
    for profile in results:
        print(f"{profile.name} - {profile.city}")
"""

import os
import sys
import re
import json
import time
import logging
import hashlib
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple, Generator
from datetime import datetime
from urllib.parse import urlencode, quote_plus
from enum import Enum

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Optional imports
HAS_REQUESTS = False
HAS_BS4 = False

try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    HAS_REQUESTS = True
except ImportError:
    logger.warning("requests not installed - using DEMO mode")

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    logger.warning("beautifulsoup4 not installed - parsing limited")


class Gender(Enum):
    """Gender filter options"""
    ANY = ""
    MALE = "male"
    FEMALE = "female"


class SearchScope(Enum):
    """Search scope options"""
    ALL = "all"
    ONLINE = "online"
    WITH_PHOTO = "with_photo"


@dataclass
class OKEducation:
    """Education record from OK.ru"""
    institution: str
    faculty: Optional[str] = None
    graduation_year: Optional[int] = None
    city: Optional[str] = None


@dataclass
class OKWorkplace:
    """Workplace record from OK.ru"""
    company: str
    position: Optional[str] = None
    city: Optional[str] = None


@dataclass
class OKProfile:
    """OK.ru user profile"""
    profile_id: str
    name: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None

    # Location
    city: Optional[str] = None
    country: Optional[str] = None

    # Demographics
    age: Optional[int] = None
    birth_date: Optional[str] = None
    gender: Optional[str] = None

    # Photos
    photo_url: Optional[str] = None
    has_photo: bool = False

    # Social
    friends_count: Optional[int] = None
    groups_count: Optional[int] = None
    photos_count: Optional[int] = None

    # Status
    is_online: bool = False
    last_online: Optional[str] = None

    # Education & Work
    education: List[OKEducation] = field(default_factory=list)
    workplaces: List[OKWorkplace] = field(default_factory=list)

    # Additional
    interests: List[str] = field(default_factory=list)
    marital_status: Optional[str] = None
    profile_url: Optional[str] = None

    # Raw data
    raw_data: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.profile_url and self.profile_id:
            self.profile_url = f"https://ok.ru/profile/{self.profile_id}"

    @property
    def full_name(self) -> str:
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.name

    def to_dict(self) -> Dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "name": self.name,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "full_name": self.full_name,
            "city": self.city,
            "country": self.country,
            "age": self.age,
            "birth_date": self.birth_date,
            "gender": self.gender,
            "photo_url": self.photo_url,
            "has_photo": self.has_photo,
            "friends_count": self.friends_count,
            "groups_count": self.groups_count,
            "is_online": self.is_online,
            "education": [
                {"institution": e.institution, "faculty": e.faculty, "year": e.graduation_year}
                for e in self.education
            ],
            "workplaces": [
                {"company": w.company, "position": w.position}
                for w in self.workplaces
            ],
            "interests": self.interests,
            "profile_url": self.profile_url
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)


@dataclass
class SearchResult:
    """Search results container"""
    query: str
    total_found: int
    profiles: List[OKProfile] = field(default_factory=list)
    page: int = 1
    has_more: bool = False
    search_time_ms: float = 0.0
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "total_found": self.total_found,
            "returned": len(self.profiles),
            "page": self.page,
            "has_more": self.has_more,
            "search_time_ms": round(self.search_time_ms, 2),
            "profiles": [p.to_dict() for p in self.profiles],
            "error": self.error
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)


class OKPeopleSearch:
    """
    OK.ru (Odnoklassniki) people search service

    Provides search and profile extraction from OK.ru social network.
    Uses combination of web scraping and API endpoints.
    """

    BASE_URL = "https://ok.ru"
    SEARCH_URL = "https://ok.ru/search"
    API_URL = "https://api.ok.ru/fb.do"

    # Rate limiting
    MIN_REQUEST_INTERVAL = 1.0
    MAX_RESULTS_PER_PAGE = 20

    # User agent rotation
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15"
    ]

    def __init__(
        self,
        session_cookies: Optional[Dict[str, str]] = None,
        demo_mode: bool = False
    ):
        """
        Initialize OK.ru search client

        Args:
            session_cookies: Optional cookies from authenticated session
            demo_mode: Force demo mode (simulated responses)
        """
        self.demo_mode = demo_mode or not HAS_REQUESTS
        self.session_cookies = session_cookies or {}
        self.session: Optional['requests.Session'] = None
        self._last_request_time = 0.0
        self._request_count = 0

        if self.demo_mode:
            logger.info("Running in DEMO mode - responses will be simulated")
        else:
            self._init_session()

    def _init_session(self):
        """Initialize requests session with retry logic"""
        if not HAS_REQUESTS:
            return

        self.session = requests.Session()

        # Configure retries
        retry = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504]
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        # Set default headers
        self.session.headers.update({
            "User-Agent": self.USER_AGENTS[0],
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive"
        })

        # Set cookies if provided
        if self.session_cookies:
            self.session.cookies.update(self.session_cookies)

    def _rate_limit(self):
        """Apply rate limiting between requests"""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.MIN_REQUEST_INTERVAL:
            time.sleep(self.MIN_REQUEST_INTERVAL - elapsed)
        self._last_request_time = time.time()
        self._request_count += 1

        # Rotate user agent periodically
        if self._request_count % 10 == 0 and self.session:
            ua_idx = (self._request_count // 10) % len(self.USER_AGENTS)
            self.session.headers["User-Agent"] = self.USER_AGENTS[ua_idx]

    def search(
        self,
        query: str,
        city: Optional[str] = None,
        country: Optional[str] = None,
        age_from: Optional[int] = None,
        age_to: Optional[int] = None,
        gender: Gender = Gender.ANY,
        scope: SearchScope = SearchScope.ALL,
        page: int = 1,
        limit: int = 20
    ) -> SearchResult:
        """
        Search for people on OK.ru

        Args:
            query: Name to search for
            city: City filter
            country: Country filter
            age_from: Minimum age
            age_to: Maximum age
            gender: Gender filter
            scope: Search scope (all, online, with_photo)
            page: Page number (1-based)
            limit: Results per page (max 20)

        Returns:
            SearchResult with matching profiles
        """
        start_time = time.time()

        if self.demo_mode:
            return self._demo_search(
                query, city, country, age_from, age_to,
                gender, scope, page, limit
            )

        self._rate_limit()

        try:
            # Build search URL
            params = self._build_search_params(
                query, city, country, age_from, age_to,
                gender, scope, page
            )

            url = f"{self.SEARCH_URL}/people?{urlencode(params, quote_via=quote_plus)}"

            response = self.session.get(url, timeout=30)
            response.raise_for_status()

            # Parse results
            profiles, total, has_more = self._parse_search_results(response.text)

            return SearchResult(
                query=query,
                total_found=total,
                profiles=profiles[:limit],
                page=page,
                has_more=has_more,
                search_time_ms=(time.time() - start_time) * 1000
            )

        except requests.RequestException as e:
            logger.error(f"Search request failed: {e}")
            return SearchResult(
                query=query,
                total_found=0,
                error=str(e),
                search_time_ms=(time.time() - start_time) * 1000
            )

        except Exception as e:
            logger.error(f"Search error: {e}")
            return SearchResult(
                query=query,
                total_found=0,
                error=str(e),
                search_time_ms=(time.time() - start_time) * 1000
            )

    def _build_search_params(
        self,
        query: str,
        city: Optional[str],
        country: Optional[str],
        age_from: Optional[int],
        age_to: Optional[int],
        gender: Gender,
        scope: SearchScope,
        page: int
    ) -> Dict[str, str]:
        """Build search query parameters"""
        params = {
            "st.query": query,
            "st.mode": "People",
            "st.grmode": "Groups"
        }

        if city:
            params["st.city"] = city

        if country:
            params["st.country"] = country

        if age_from:
            params["st.age_from"] = str(age_from)

        if age_to:
            params["st.age_to"] = str(age_to)

        if gender != Gender.ANY:
            params["st.gender"] = gender.value

        if scope == SearchScope.ONLINE:
            params["st.online"] = "on"
        elif scope == SearchScope.WITH_PHOTO:
            params["st.hasPhoto"] = "on"

        if page > 1:
            params["st.page"] = str(page)

        return params

    def _parse_search_results(self, html: str) -> Tuple[List[OKProfile], int, bool]:
        """Parse search results HTML"""
        profiles = []
        total = 0
        has_more = False

        if not HAS_BS4:
            logger.warning("BeautifulSoup not available - returning empty results")
            return profiles, total, has_more

        soup = BeautifulSoup(html, "lxml" if "lxml" in sys.modules else "html.parser")

        # Try to get total count
        count_elem = soup.select_one(".search-result-count, .total-count, .results-count")
        if count_elem:
            count_text = count_elem.get_text()
            numbers = re.findall(r'\d+', count_text.replace(" ", ""))
            if numbers:
                total = int(numbers[0])

        # Parse profile cards
        profile_selectors = [
            ".user-card",
            ".search-card",
            ".user-info-card",
            "[data-l='userCard']",
            ".entity-card"
        ]

        cards = []
        for selector in profile_selectors:
            cards = soup.select(selector)
            if cards:
                break

        for card in cards:
            try:
                profile = self._parse_profile_card(card)
                if profile:
                    profiles.append(profile)
            except Exception as e:
                logger.debug(f"Failed to parse card: {e}")

        # Check for pagination
        next_btn = soup.select_one(".paging-next, .next-page, [data-l='nextPage']")
        has_more = next_btn is not None

        return profiles, total, has_more

    def _parse_profile_card(self, card: 'BeautifulSoup') -> Optional[OKProfile]:
        """Parse a single profile card"""
        # Extract profile ID from link
        link = card.select_one("a[href*='/profile/']")
        if not link:
            return None

        href = link.get("href", "")
        profile_id_match = re.search(r'/profile/(\d+)', href)
        if not profile_id_match:
            return None

        profile_id = profile_id_match.group(1)

        # Extract name
        name_elem = card.select_one(".user-name, .profile-name, .card-name, h3, h4")
        name = name_elem.get_text(strip=True) if name_elem else "Unknown"

        # Parse first/last name
        name_parts = name.split(maxsplit=1)
        first_name = name_parts[0] if name_parts else None
        last_name = name_parts[1] if len(name_parts) > 1 else None

        # Extract photo
        photo_elem = card.select_one("img.photo, img.avatar, .user-photo img")
        photo_url = None
        has_photo = False
        if photo_elem:
            photo_url = photo_elem.get("src") or photo_elem.get("data-src")
            has_photo = photo_url and "stub" not in photo_url.lower()

        # Extract city
        city_elem = card.select_one(".user-city, .location, .geo")
        city = city_elem.get_text(strip=True) if city_elem else None

        # Extract age
        age = None
        age_elem = card.select_one(".user-age, .age")
        if age_elem:
            age_text = age_elem.get_text()
            age_match = re.search(r'(\d+)', age_text)
            if age_match:
                age = int(age_match.group(1))

        # Extract online status
        is_online = bool(card.select_one(".online, .status-online, .is-online"))

        # Extract friends count
        friends_count = None
        friends_elem = card.select_one(".friends-count, .friend-count")
        if friends_elem:
            friends_text = friends_elem.get_text()
            friends_match = re.search(r'(\d+)', friends_text.replace(" ", ""))
            if friends_match:
                friends_count = int(friends_match.group(1))

        return OKProfile(
            profile_id=profile_id,
            name=name,
            first_name=first_name,
            last_name=last_name,
            city=city,
            age=age,
            photo_url=photo_url,
            has_photo=has_photo,
            is_online=is_online,
            friends_count=friends_count
        )

    def get_profile(self, profile_id: str) -> Optional[OKProfile]:
        """
        Get detailed profile information

        Args:
            profile_id: OK.ru profile ID

        Returns:
            OKProfile with full details, or None if not found
        """
        if self.demo_mode:
            return self._demo_get_profile(profile_id)

        self._rate_limit()

        try:
            url = f"{self.BASE_URL}/profile/{profile_id}"
            response = self.session.get(url, timeout=30)
            response.raise_for_status()

            return self._parse_full_profile(response.text, profile_id)

        except Exception as e:
            logger.error(f"Profile fetch error: {e}")
            return None

    def _parse_full_profile(self, html: str, profile_id: str) -> Optional[OKProfile]:
        """Parse full profile page"""
        if not HAS_BS4:
            return None

        soup = BeautifulSoup(html, "lxml" if "lxml" in sys.modules else "html.parser")

        # Extract name
        name_elem = soup.select_one(".profile-user-name, h1.name, .user-name")
        name = name_elem.get_text(strip=True) if name_elem else "Unknown"

        profile = OKProfile(
            profile_id=profile_id,
            name=name
        )

        # Extract photo
        photo_elem = soup.select_one(".profile-photo img, .main-photo img")
        if photo_elem:
            profile.photo_url = photo_elem.get("src")
            profile.has_photo = True

        # Extract info fields
        info_items = soup.select(".profile-info-item, .user-info-item")
        for item in info_items:
            label = item.select_one(".label, .info-label")
            value = item.select_one(".value, .info-value")
            if not label or not value:
                continue

            label_text = label.get_text(strip=True).lower()
            value_text = value.get_text(strip=True)

            if "город" in label_text or "city" in label_text:
                profile.city = value_text
            elif "возраст" in label_text or "age" in label_text:
                age_match = re.search(r'(\d+)', value_text)
                if age_match:
                    profile.age = int(age_match.group(1))
            elif "день рождения" in label_text or "birthday" in label_text:
                profile.birth_date = value_text

        # Extract education
        edu_items = soup.select(".education-item, .edu-block")
        for edu in edu_items:
            inst_elem = edu.select_one(".institution, .edu-name")
            if inst_elem:
                education = OKEducation(institution=inst_elem.get_text(strip=True))

                faculty_elem = edu.select_one(".faculty, .edu-faculty")
                if faculty_elem:
                    education.faculty = faculty_elem.get_text(strip=True)

                year_elem = edu.select_one(".year, .edu-year")
                if year_elem:
                    year_match = re.search(r'(\d{4})', year_elem.get_text())
                    if year_match:
                        education.graduation_year = int(year_match.group(1))

                profile.education.append(education)

        # Extract friends count
        friends_elem = soup.select_one(".friends-count, [data-l='friendsCount']")
        if friends_elem:
            count_text = friends_elem.get_text()
            count_match = re.search(r'(\d+)', count_text.replace(" ", ""))
            if count_match:
                profile.friends_count = int(count_match.group(1))

        return profile

    def search_all(
        self,
        query: str,
        max_results: int = 100,
        **kwargs
    ) -> Generator[OKProfile, None, None]:
        """
        Search with automatic pagination

        Args:
            query: Search query
            max_results: Maximum total results to return
            **kwargs: Additional search parameters

        Yields:
            OKProfile objects
        """
        page = 1
        returned = 0

        while returned < max_results:
            result = self.search(query, page=page, **kwargs)

            if result.error or not result.profiles:
                break

            for profile in result.profiles:
                if returned >= max_results:
                    return
                yield profile
                returned += 1

            if not result.has_more:
                break

            page += 1

    # Demo mode implementations
    def _demo_search(
        self,
        query: str,
        city: Optional[str],
        country: Optional[str],
        age_from: Optional[int],
        age_to: Optional[int],
        gender: Gender,
        scope: SearchScope,
        page: int,
        limit: int
    ) -> SearchResult:
        """Simulated search for demo mode"""
        time.sleep(0.1)  # Simulate network delay

        # Generate deterministic results based on query
        query_hash = hashlib.md5(query.encode()).hexdigest()

        # Demo names
        demo_profiles = [
            ("Иванов Иван", "Москва", 28),
            ("Петров Петр", "Санкт-Петербург", 35),
            ("Сидорова Мария", "Казань", 24),
            ("Козлов Алексей", "Новосибирск", 31),
            ("Волкова Елена", "Екатеринбург", 27),
            ("Соколов Дмитрий", "Нижний Новгород", 42),
            ("Морозова Анна", "Самара", 29),
            ("Новиков Сергей", "Ростов-на-Дону", 33),
            ("Федорова Ольга", "Уфа", 26),
            ("Михайлов Андрей", "Краснодар", 38)
        ]

        # Filter and generate profiles
        profiles = []
        total_found = int(query_hash[:2], 16) + 10  # 10-265 results

        start_idx = (page - 1) * limit
        for i in range(min(limit, total_found - start_idx)):
            idx = (start_idx + i) % len(demo_profiles)
            name, default_city, default_age = demo_profiles[idx]

            # Apply filters
            profile_city = city or default_city
            profile_age = default_age
            if age_from and profile_age < age_from:
                profile_age = age_from + (i % 5)
            if age_to and profile_age > age_to:
                profile_age = age_to - (i % 5)

            profile_id = f"{int(query_hash[(i*2):(i*2+4)], 16) + 100000000}"

            profile = OKProfile(
                profile_id=profile_id,
                name=name,
                first_name=name.split()[0],
                last_name=name.split()[-1] if len(name.split()) > 1 else None,
                city=profile_city,
                age=profile_age,
                has_photo=int(query_hash[i], 16) > 4,
                photo_url=f"https://ok.ru/i/stub_{profile_id}.jpg" if int(query_hash[i], 16) > 4 else None,
                is_online=int(query_hash[i+1], 16) > 12,
                friends_count=int(query_hash[i:i+3], 16) % 500 + 10
            )
            profiles.append(profile)

        return SearchResult(
            query=query,
            total_found=total_found,
            profiles=profiles,
            page=page,
            has_more=page * limit < total_found,
            search_time_ms=100.0
        )

    def _demo_get_profile(self, profile_id: str) -> OKProfile:
        """Simulated profile fetch for demo mode"""
        time.sleep(0.1)

        id_hash = hashlib.md5(profile_id.encode()).hexdigest()

        demo_names = ["Иван Петров", "Мария Иванова", "Алексей Сидоров", "Елена Козлова"]
        demo_cities = ["Москва", "Санкт-Петербург", "Казань", "Новосибирск"]

        name = demo_names[int(id_hash[0], 16) % len(demo_names)]

        profile = OKProfile(
            profile_id=profile_id,
            name=name,
            first_name=name.split()[0],
            last_name=name.split()[-1],
            city=demo_cities[int(id_hash[1], 16) % len(demo_cities)],
            age=20 + int(id_hash[2:4], 16) % 40,
            has_photo=True,
            photo_url=f"https://ok.ru/i/photo_{profile_id}.jpg",
            friends_count=int(id_hash[4:7], 16) % 1000,
            is_online=int(id_hash[7], 16) > 10
        )

        # Add education
        if int(id_hash[8], 16) > 6:
            profile.education.append(OKEducation(
                institution="МГУ им. Ломоносова",
                faculty="Экономический факультет",
                graduation_year=2015 + int(id_hash[9], 16) % 8
            ))

        # Add workplace
        if int(id_hash[10], 16) > 5:
            profile.workplaces.append(OKWorkplace(
                company="Газпром",
                position="Менеджер"
            ))

        return profile


def demo():
    """Demonstrate OK.ru search capabilities"""
    print("=" * 60)
    print("OK.ru People Search - IBP Prototype B.7")
    print("=" * 60)
    print()

    # Initialize in demo mode
    search = OKPeopleSearch(demo_mode=True)

    print("Demo Mode - Simulated OK.ru Search")
    print("-" * 40)

    # Test search
    test_queries = [
        ("Иван Петров", "Москва", None, None),
        ("Мария", None, 25, 35),
        ("Сидоров", "Санкт-Петербург", None, None)
    ]

    for query, city, age_from, age_to in test_queries:
        print(f"\nSearch: '{query}'" + (f", city={city}" if city else "") +
              (f", age={age_from}-{age_to}" if age_from else ""))

        result = search.search(query, city=city, age_from=age_from, age_to=age_to, limit=5)

        print(f"  Found: {result.total_found} total, showing {len(result.profiles)}")

        for profile in result.profiles[:3]:
            print(f"    - {profile.name}, {profile.city}, {profile.age} лет")
            print(f"      ID: {profile.profile_id}, Friends: {profile.friends_count}")

    # Test profile fetch
    print("\n\nProfile Details:")
    print("-" * 40)

    profile = search.get_profile("123456789")
    if profile:
        print(f"  Name: {profile.full_name}")
        print(f"  City: {profile.city}")
        print(f"  Age: {profile.age}")
        print(f"  Friends: {profile.friends_count}")
        if profile.education:
            print(f"  Education: {profile.education[0].institution}")

    print("\n" + "=" * 60)
    print("Usage Example:")
    print("-" * 40)
    print("""
from ok_people_search import OKPeopleSearch, Gender

# Initialize search client
search = OKPeopleSearch()

# Search for people
result = search.search(
    query="Иван Петров",
    city="Москва",
    age_from=25,
    age_to=40,
    gender=Gender.MALE
)

print(f"Found {result.total_found} profiles")

for profile in result.profiles:
    print(f"{profile.name} ({profile.age}), {profile.city}")
    print(f"  URL: {profile.profile_url}")
    print(f"  Friends: {profile.friends_count}")

# Get full profile details
profile = search.get_profile("123456789")
if profile:
    print(f"Bio: {profile.bio}")
    for edu in profile.education:
        print(f"Education: {edu.institution}")

# Search with pagination
for profile in search.search_all("Петров", max_results=50, city="Москва"):
    print(f"Found: {profile.name}")
""")

    print("\n" + "=" * 60)
    print("\nJSON Output Example:")
    print("-" * 40)

    result = search.search("Тест", limit=2)
    print(result.to_json())


if __name__ == "__main__":
    demo()
