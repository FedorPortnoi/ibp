#!/usr/bin/env python3
"""
VK People Search Prototype for IBP
==================================

Searches VKontakte for people by name and optional filters.
Uses VK API users.search method with service token.

Usage:
    python vk_people_search.py --name "Иванов Иван" --city "Москва"
    python vk_people_search.py --name "Петрова Мария" --age-from 25 --age-to 35
    python vk_people_search.py --demo  # Run with mock data (no API key needed)

Environment:
    VK_SERVICE_TOKEN: VK API service token (get from https://dev.vk.com/)

Author: IBP Project
License: MIT
"""

import argparse
import json
import logging
import os
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import List, Optional, Dict, Any

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

try:
    import requests
except ImportError:
    logger.error("requests not installed. Run: pip install requests")
    sys.exit(1)


@dataclass
class VKProfile:
    """VK Profile data structure."""
    vk_id: int
    first_name: str
    last_name: str
    screen_name: Optional[str] = None
    photo_url: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    bdate: Optional[str] = None
    age: Optional[int] = None
    university: Optional[str] = None
    faculty: Optional[str] = None
    graduation: Optional[int] = None
    career: Optional[List[Dict]] = None
    is_closed: bool = False
    can_access_closed: bool = True
    profile_url: str = ""

    def __post_init__(self):
        self.profile_url = f"https://vk.com/id{self.vk_id}"
        if self.screen_name:
            self.profile_url = f"https://vk.com/{self.screen_name}"


class VKAPIError(Exception):
    """VK API Error."""
    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(f"VK API Error {code}: {message}")


class VKPeopleSearch:
    """
    VK People Search using VK API.

    Searches VKontakte users by real name and filters.
    Supports city, age range, education, and more.
    """

    API_VERSION = "5.199"
    API_BASE_URL = "https://api.vk.com/method"
    RPS_DELAY = 0.34  # ~3 requests per second

    # VK API Error Codes
    TOO_MANY_REQUESTS = 6
    ACCESS_DENIED = 15
    USER_DELETED = 18
    RATE_LIMIT = 29
    PRIVATE_PROFILE = 30

    def __init__(self, service_token: Optional[str] = None):
        """
        Initialize VK People Search.

        Args:
            service_token: VK API service token. If not provided,
                          will try to get from VK_SERVICE_TOKEN env var.
        """
        self.token = service_token or os.environ.get("VK_SERVICE_TOKEN")
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        self.last_request_time = 0.0
        self._city_cache: Dict[str, int] = {}

    def _rate_limit(self):
        """Enforce rate limiting (~3 requests/second)."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.RPS_DELAY:
            time.sleep(self.RPS_DELAY - elapsed)
        self.last_request_time = time.time()

    def _api_call(self, method: str, params: Dict[str, Any],
                  max_retries: int = 3) -> Dict[str, Any]:
        """
        Make VK API call with rate limiting and error handling.

        Args:
            method: VK API method name (e.g., "users.search")
            params: Method parameters
            max_retries: Maximum retry attempts for rate limit errors

        Returns:
            API response dict

        Raises:
            VKAPIError: On API errors
        """
        if not self.token:
            raise VKAPIError(0, "No VK API token provided. Set VK_SERVICE_TOKEN env var.")

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

                    # Handle non-retryable errors
                    if code in (self.ACCESS_DENIED, self.USER_DELETED, self.PRIVATE_PROFILE):
                        raise VKAPIError(code, message)

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
        """
        Get VK city ID by name.

        Args:
            city_name: City name in Russian (e.g., "Москва", "Санкт-Петербург")
            country_id: Country ID (1 = Russia, 2 = Ukraine, etc.)

        Returns:
            City ID or None if not found
        """
        cache_key = f"{country_id}:{city_name.lower()}"
        if cache_key in self._city_cache:
            return self._city_cache[cache_key]

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

            # Adjust if birthday hasn't occurred yet this year
            birth_month = int(parts[1])
            birth_day = int(parts[0])
            if (today.month, today.day) < (birth_month, birth_day):
                age -= 1

            return age if 0 < age < 150 else None
        except (ValueError, IndexError):
            return None

    def _parse_profile(self, data: Dict[str, Any]) -> VKProfile:
        """Parse VK API user data into VKProfile."""
        # Extract city
        city = None
        city_data = data.get("city")
        if city_data:
            city = city_data.get("title")

        # Extract country
        country = None
        country_data = data.get("country")
        if country_data:
            country = country_data.get("title")

        # Extract education
        university = data.get("university_name")
        faculty = data.get("faculty_name")
        graduation = data.get("graduation")

        # Extract career
        career = data.get("career", [])

        # Get largest available photo
        photo_url = (
            data.get("photo_max_orig") or
            data.get("photo_400_orig") or
            data.get("photo_200") or
            data.get("photo_100") or
            data.get("photo_50")
        )

        bdate = data.get("bdate")
        age = self._calculate_age(bdate)

        return VKProfile(
            vk_id=data["id"],
            first_name=data.get("first_name", ""),
            last_name=data.get("last_name", ""),
            screen_name=data.get("domain") or data.get("screen_name"),
            photo_url=photo_url,
            city=city,
            country=country,
            bdate=bdate,
            age=age,
            university=university,
            faculty=faculty,
            graduation=graduation,
            career=career if career else None,
            is_closed=data.get("is_closed", False),
            can_access_closed=data.get("can_access_closed", True)
        )

    def search(
        self,
        query: str,
        city: Optional[str] = None,
        city_id: Optional[int] = None,
        country_id: Optional[int] = None,
        age_from: Optional[int] = None,
        age_to: Optional[int] = None,
        birth_day: Optional[int] = None,
        birth_month: Optional[int] = None,
        birth_year: Optional[int] = None,
        sex: Optional[int] = None,  # 0=any, 1=female, 2=male
        status: Optional[int] = None,  # 1-8 (single, dating, etc.)
        university: Optional[int] = None,
        university_country: Optional[int] = None,
        university_faculty: Optional[int] = None,
        university_year: Optional[int] = None,
        school: Optional[int] = None,
        school_year: Optional[int] = None,
        group_id: Optional[int] = None,  # Search within group
        count: int = 100,
        offset: int = 0
    ) -> tuple[List[VKProfile], int]:
        """
        Search VKontakte for people.

        Args:
            query: Search query (name, e.g., "Иванов Иван")
            city: City name (will be converted to ID)
            city_id: VK city ID (if known)
            country_id: VK country ID
            age_from: Minimum age
            age_to: Maximum age
            birth_day: Day of birth
            birth_month: Month of birth
            birth_year: Year of birth
            sex: Gender (0=any, 1=female, 2=male)
            status: Relationship status (1-8)
            university: University ID
            university_country: University country ID
            university_faculty: Faculty ID
            university_year: Graduation year
            school: School ID
            school_year: School graduation year
            group_id: Search only in this group
            count: Results per page (max 1000)
            offset: Pagination offset

        Returns:
            Tuple of (list of profiles, total count)
        """
        # Build params
        params = {
            "q": query,
            "count": min(count, 1000),
            "offset": offset,
            "fields": ",".join([
                "photo_max_orig", "photo_400_orig", "photo_200", "photo_100",
                "city", "country", "bdate", "domain", "screen_name",
                "education", "universities", "schools",
                "career", "is_closed", "can_access_closed"
            ])
        }

        # Resolve city name to ID if needed
        if city and not city_id:
            city_id = self.get_city_id(city, country_id or 1)
            if city_id:
                logger.info(f"Resolved city '{city}' to ID {city_id}")

        # Add optional filters
        if city_id:
            params["city"] = city_id
        if country_id:
            params["country"] = country_id
        if age_from:
            params["age_from"] = age_from
        if age_to:
            params["age_to"] = age_to
        if birth_day:
            params["birth_day"] = birth_day
        if birth_month:
            params["birth_month"] = birth_month
        if birth_year:
            params["birth_year"] = birth_year
        if sex:
            params["sex"] = sex
        if status:
            params["status"] = status
        if university:
            params["university"] = university
        if university_country:
            params["university_country"] = university_country
        if university_faculty:
            params["university_faculty"] = university_faculty
        if university_year:
            params["university_year"] = university_year
        if school:
            params["school"] = school
        if school_year:
            params["school_year"] = school_year
        if group_id:
            params["group_id"] = group_id

        logger.info(f"Searching VK for: '{query}' with filters: {params}")

        result = self._api_call("users.search", params)

        total_count = result.get("count", 0)
        items = result.get("items", [])

        profiles = [self._parse_profile(item) for item in items]

        logger.info(f"Found {total_count} total results, returning {len(profiles)}")

        return profiles, total_count

    def search_all(
        self,
        query: str,
        max_results: int = 500,
        **kwargs
    ) -> List[VKProfile]:
        """
        Search with automatic pagination to get all results.

        Args:
            query: Search query
            max_results: Maximum number of results to return
            **kwargs: Additional search parameters

        Returns:
            List of all profiles found (up to max_results)
        """
        all_profiles = []
        offset = 0
        count_per_page = min(1000, max_results)

        while len(all_profiles) < max_results:
            profiles, total = self.search(
                query=query,
                count=count_per_page,
                offset=offset,
                **kwargs
            )

            if not profiles:
                break

            all_profiles.extend(profiles)
            offset += len(profiles)

            if offset >= total:
                break

            logger.info(f"Progress: {len(all_profiles)}/{min(total, max_results)}")

        return all_profiles[:max_results]


# ============================================================================
# Demo Mode (works without API key)
# ============================================================================

DEMO_DATA = [
    {
        "id": 123456789,
        "first_name": "Иван",
        "last_name": "Иванов",
        "domain": "ivanov_ivan",
        "photo_max_orig": "https://vk.com/images/camera_200.png",
        "city": {"id": 1, "title": "Москва"},
        "country": {"id": 1, "title": "Россия"},
        "bdate": "15.5.1990",
        "university_name": "МГУ им. М.В. Ломоносова",
        "faculty_name": "Факультет вычислительной математики и кибернетики",
        "graduation": 2012,
        "is_closed": False,
        "can_access_closed": True
    },
    {
        "id": 987654321,
        "first_name": "Иван",
        "last_name": "Иванов",
        "domain": "ivan_ivanov_spb",
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
        "first_name": "Иван",
        "last_name": "Иванов",
        "domain": "id111222333",
        "photo_max_orig": "https://vk.com/images/camera_200.png",
        "city": {"id": 73, "title": "Казань"},
        "country": {"id": 1, "title": "Россия"},
        "bdate": "1.1",  # No year
        "is_closed": True,
        "can_access_closed": False
    }
]


def run_demo():
    """Run demo mode with mock data."""
    print("\n" + "="*60)
    print("VK PEOPLE SEARCH - DEMO MODE")
    print("="*60)
    print("\nSearching for: 'Иванов Иван' (mock data)\n")

    searcher = VKPeopleSearch(service_token="demo_mode")

    # Parse demo data as if from API
    profiles = [searcher._parse_profile(d) for d in DEMO_DATA]

    print(f"Found {len(profiles)} results:\n")

    for i, p in enumerate(profiles, 1):
        print(f"--- Result #{i} ---")
        print(f"  Name:       {p.first_name} {p.last_name}")
        print(f"  VK ID:      {p.vk_id}")
        print(f"  Profile:    {p.profile_url}")
        print(f"  City:       {p.city or 'N/A'}")
        print(f"  Age:        {p.age or 'N/A'}")
        print(f"  University: {p.university or 'N/A'}")
        print(f"  Private:    {'Yes' if p.is_closed else 'No'}")
        print()

    # Output JSON
    print("\n" + "="*60)
    print("JSON OUTPUT:")
    print("="*60)
    output = {
        "query": "Иванов Иван",
        "total_found": len(profiles),
        "results": [asdict(p) for p in profiles]
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))

    return output


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Search VKontakte for people by name and filters",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --name "Иванов Иван"
  %(prog)s --name "Петрова Мария" --city "Москва"
  %(prog)s --name "Сидоров" --age-from 25 --age-to 35
  %(prog)s --demo  # Run with mock data

Environment:
  VK_SERVICE_TOKEN  VK API service token (required for real searches)

Getting a VK Service Token:
  1. Go to https://dev.vk.com/
  2. Create a standalone application
  3. Copy the service token from app settings
  4. Set: export VK_SERVICE_TOKEN="your_token_here"
        """
    )

    parser.add_argument("--name", "-n", help="Name to search for (Cyrillic)")
    parser.add_argument("--city", "-c", help="City name (e.g., 'Москва')")
    parser.add_argument("--age-from", type=int, help="Minimum age")
    parser.add_argument("--age-to", type=int, help="Maximum age")
    parser.add_argument("--sex", type=int, choices=[0, 1, 2],
                        help="Gender: 0=any, 1=female, 2=male")
    parser.add_argument("--count", type=int, default=50,
                        help="Number of results (default: 50, max: 1000)")
    parser.add_argument("--output", "-o", help="Output JSON file")
    parser.add_argument("--demo", action="store_true",
                        help="Run in demo mode with mock data")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Verbose output")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Demo mode
    if args.demo:
        output = run_demo()
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(output, f, ensure_ascii=False, indent=2)
            print(f"\nSaved to: {args.output}")
        return

    # Real search mode
    if not args.name:
        parser.error("--name is required (or use --demo)")

    try:
        searcher = VKPeopleSearch()

        profiles, total = searcher.search(
            query=args.name,
            city=args.city,
            age_from=args.age_from,
            age_to=args.age_to,
            sex=args.sex,
            count=args.count
        )

        print(f"\n{'='*60}")
        print(f"VK PEOPLE SEARCH RESULTS")
        print(f"{'='*60}")
        print(f"Query: {args.name}")
        if args.city:
            print(f"City: {args.city}")
        print(f"Total found: {total}")
        print(f"Showing: {len(profiles)}")
        print()

        for i, p in enumerate(profiles, 1):
            print(f"--- Result #{i} ---")
            print(f"  Name:       {p.first_name} {p.last_name}")
            print(f"  VK ID:      {p.vk_id}")
            print(f"  Profile:    {p.profile_url}")
            print(f"  City:       {p.city or 'N/A'}")
            print(f"  Age:        {p.age or 'N/A'}")
            print(f"  University: {p.university or 'N/A'}")
            print(f"  Private:    {'Yes' if p.is_closed else 'No'}")
            print()

        # Output JSON
        output = {
            "query": args.name,
            "filters": {
                "city": args.city,
                "age_from": args.age_from,
                "age_to": args.age_to,
                "sex": args.sex
            },
            "total_found": total,
            "returned": len(profiles),
            "results": [asdict(p) for p in profiles]
        }

        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(output, f, ensure_ascii=False, indent=2)
            print(f"Results saved to: {args.output}")
        else:
            print("\nJSON Output:")
            print(json.dumps(output, ensure_ascii=False, indent=2))

    except VKAPIError as e:
        logger.error(f"VK API Error: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(0)


if __name__ == "__main__":
    main()
