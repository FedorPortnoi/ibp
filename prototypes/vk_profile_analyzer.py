#!/usr/bin/env python3
"""
VK Profile Deep Analyzer Prototype for IBP
==========================================

Extracts comprehensive data from a VK user profile including:
- Full profile information
- Friends list
- Groups/communities
- Wall posts
- Photos

Usage:
    python vk_profile_analyzer.py --vk-id 123456789
    python vk_profile_analyzer.py --vk-id 123456789 --output profile_data.json
    python vk_profile_analyzer.py --demo  # Run with mock data

Environment:
    VK_SERVICE_TOKEN: VK API service token

Author: IBP Project
License: MIT
"""

import argparse
import json
import logging
import os
import sys
import time
from dataclasses import dataclass, asdict, field
from datetime import datetime
from typing import List, Optional, Dict, Any

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
class VKEducation:
    """VK Education entry."""
    university_id: Optional[int] = None
    university_name: Optional[str] = None
    faculty_id: Optional[int] = None
    faculty_name: Optional[str] = None
    graduation: Optional[int] = None
    education_form: Optional[str] = None
    education_status: Optional[str] = None


@dataclass
class VKCareer:
    """VK Career entry."""
    company: Optional[str] = None
    group_id: Optional[int] = None
    country_id: Optional[int] = None
    city_id: Optional[int] = None
    city_name: Optional[str] = None
    position: Optional[str] = None
    from_year: Optional[int] = None
    until_year: Optional[int] = None


@dataclass
class VKGroup:
    """VK Group/Community."""
    id: int
    name: str
    screen_name: Optional[str] = None
    type: Optional[str] = None  # group, page, event
    is_closed: bool = False
    members_count: Optional[int] = None
    photo_url: Optional[str] = None
    description: Optional[str] = None


@dataclass
class VKWallPost:
    """VK Wall post."""
    id: int
    from_id: int
    owner_id: int
    date: int
    text: str
    likes_count: int = 0
    comments_count: int = 0
    reposts_count: int = 0
    views_count: int = 0
    post_type: Optional[str] = None
    is_pinned: bool = False
    attachments: List[Dict] = field(default_factory=list)


@dataclass
class VKPhoto:
    """VK Photo."""
    id: int
    owner_id: int
    album_id: int
    date: int
    text: Optional[str] = None
    url: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None


@dataclass
class VKFriend:
    """VK Friend."""
    id: int
    first_name: str
    last_name: str
    photo_url: Optional[str] = None
    city: Optional[str] = None
    is_closed: bool = False


@dataclass
class VKFullProfile:
    """Complete VK Profile data."""
    # Basic info
    vk_id: int
    first_name: str
    last_name: str
    maiden_name: Optional[str] = None
    screen_name: Optional[str] = None
    sex: Optional[int] = None  # 1=female, 2=male, 0=unknown
    bdate: Optional[str] = None
    age: Optional[int] = None

    # Location
    city: Optional[str] = None
    city_id: Optional[int] = None
    country: Optional[str] = None
    country_id: Optional[int] = None
    home_town: Optional[str] = None

    # Photos
    photo_url: Optional[str] = None
    photo_id: Optional[str] = None

    # Status
    status: Optional[str] = None
    last_seen: Optional[Dict] = None
    online: bool = False

    # Privacy
    is_closed: bool = False
    can_access_closed: bool = True

    # Contacts
    mobile_phone: Optional[str] = None
    home_phone: Optional[str] = None
    site: Optional[str] = None
    skype: Optional[str] = None
    twitter: Optional[str] = None
    instagram: Optional[str] = None
    facebook: Optional[str] = None

    # Personal
    relation: Optional[int] = None  # 1-8 (single, dating, engaged, married, etc.)
    relation_partner: Optional[Dict] = None

    # Counters
    friends_count: int = 0
    followers_count: int = 0
    photos_count: int = 0
    videos_count: int = 0
    audios_count: int = 0
    notes_count: int = 0
    groups_count: int = 0

    # Education & Career
    education: List[VKEducation] = field(default_factory=list)
    career: List[VKCareer] = field(default_factory=list)

    # Related data (populated separately)
    friends: List[VKFriend] = field(default_factory=list)
    groups: List[VKGroup] = field(default_factory=list)
    wall_posts: List[VKWallPost] = field(default_factory=list)
    photos: List[VKPhoto] = field(default_factory=list)

    # Metadata
    profile_url: str = ""
    fetched_at: Optional[str] = None
    access_restrictions: Dict[str, bool] = field(default_factory=dict)

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


class VKProfileAnalyzer:
    """
    VK Profile Deep Analyzer.

    Extracts comprehensive profile data including friends, groups, posts, photos.
    """

    API_VERSION = "5.199"
    API_BASE_URL = "https://api.vk.com/method"
    RPS_DELAY = 0.34

    # Profile fields to request
    PROFILE_FIELDS = [
        "photo_max_orig", "photo_id", "verified", "sex", "bdate",
        "city", "country", "home_town", "domain", "contacts",
        "site", "education", "universities", "schools", "status",
        "last_seen", "followers_count", "counters", "occupation",
        "nickname", "relatives", "relation", "personal", "connections",
        "exports", "activities", "interests", "music", "movies",
        "tv", "books", "games", "about", "quotes", "career",
        "military", "maiden_name", "screen_name"
    ]

    def __init__(self, service_token: Optional[str] = None):
        self.token = service_token or os.environ.get("VK_SERVICE_TOKEN")
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        self.last_request_time = 0.0

    def _rate_limit(self):
        elapsed = time.time() - self.last_request_time
        if elapsed < self.RPS_DELAY:
            time.sleep(self.RPS_DELAY - elapsed)
        self.last_request_time = time.time()

    def _api_call(self, method: str, params: Dict[str, Any],
                  max_retries: int = 3) -> Dict[str, Any]:
        if not self.token:
            raise VKAPIError(0, "No VK API token. Set VK_SERVICE_TOKEN env var.")

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

                    if code in (6, 29):  # Rate limit
                        wait_time = 0.5 * (2 ** attempt)
                        logger.warning(f"Rate limited. Waiting {wait_time}s...")
                        time.sleep(wait_time)
                        continue

                    # Log but don't raise for access denied (return empty)
                    if code in (15, 18, 30):
                        logger.warning(f"Access denied for {method}: {message}")
                        return {}

                    raise VKAPIError(code, message)

                return data.get("response", {})

            except requests.RequestException as e:
                logger.error(f"Request failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(1)
                    continue
                raise VKAPIError(0, f"Network error: {e}")

        raise VKAPIError(29, "Max retries exceeded")

    def _calculate_age(self, bdate: Optional[str]) -> Optional[int]:
        if not bdate:
            return None
        parts = bdate.split(".")
        if len(parts) != 3:
            return None
        try:
            birth_year = int(parts[2])
            today = datetime.now()
            return today.year - birth_year
        except (ValueError, IndexError):
            return None

    def get_profile(self, vk_id: int) -> Optional[Dict]:
        """Get basic profile information."""
        logger.info(f"Fetching profile for VK ID: {vk_id}")

        result = self._api_call("users.get", {
            "user_ids": vk_id,
            "fields": ",".join(self.PROFILE_FIELDS)
        })

        if isinstance(result, list) and result:
            return result[0]
        return None

    def get_friends(self, vk_id: int, count: int = 5000) -> List[Dict]:
        """Get user's friends list."""
        logger.info(f"Fetching friends for VK ID: {vk_id}")

        try:
            result = self._api_call("friends.get", {
                "user_id": vk_id,
                "count": min(count, 5000),
                "fields": "photo_100,city,last_seen"
            })
            return result.get("items", [])
        except VKAPIError:
            return []

    def get_groups(self, vk_id: int, count: int = 1000) -> List[Dict]:
        """Get user's groups/communities."""
        logger.info(f"Fetching groups for VK ID: {vk_id}")

        try:
            result = self._api_call("groups.get", {
                "user_id": vk_id,
                "extended": 1,
                "count": min(count, 1000),
                "fields": "members_count,description"
            })
            return result.get("items", [])
        except VKAPIError:
            return []

    def get_wall_posts(self, vk_id: int, count: int = 100) -> List[Dict]:
        """Get user's wall posts."""
        logger.info(f"Fetching wall posts for VK ID: {vk_id}")

        all_posts = []
        offset = 0

        while len(all_posts) < count:
            try:
                result = self._api_call("wall.get", {
                    "owner_id": vk_id,
                    "count": min(100, count - len(all_posts)),
                    "offset": offset
                })

                items = result.get("items", [])
                if not items:
                    break

                all_posts.extend(items)
                offset += len(items)

            except VKAPIError:
                break

        return all_posts[:count]

    def get_photos(self, vk_id: int, count: int = 50) -> List[Dict]:
        """Get user's photos."""
        logger.info(f"Fetching photos for VK ID: {vk_id}")

        try:
            result = self._api_call("photos.getAll", {
                "owner_id": vk_id,
                "count": min(count, 200),
                "photo_sizes": 1,
                "extended": 1
            })
            return result.get("items", [])
        except VKAPIError:
            return []

    def analyze(self, vk_id: int,
                include_friends: bool = True,
                include_groups: bool = True,
                include_wall: bool = True,
                include_photos: bool = True,
                friends_limit: int = 500,
                wall_limit: int = 100,
                photos_limit: int = 50) -> VKFullProfile:
        """
        Perform full profile analysis.

        Args:
            vk_id: VK user ID
            include_friends: Include friends list
            include_groups: Include group memberships
            include_wall: Include wall posts
            include_photos: Include photos
            friends_limit: Max friends to fetch
            wall_limit: Max wall posts to fetch
            photos_limit: Max photos to fetch

        Returns:
            VKFullProfile with all available data
        """
        logger.info(f"Starting full analysis for VK ID: {vk_id}")

        # Get basic profile
        profile_data = self.get_profile(vk_id)
        if not profile_data:
            raise VKAPIError(18, f"Profile {vk_id} not found or inaccessible")

        # Track what we can access
        access_restrictions = {
            "profile": True,
            "friends": False,
            "groups": False,
            "wall": False,
            "photos": False
        }

        # Parse profile data
        city_data = profile_data.get("city", {})
        country_data = profile_data.get("country", {})
        counters = profile_data.get("counters", {})

        # Parse education
        education = []
        if profile_data.get("university"):
            education.append(VKEducation(
                university_id=profile_data.get("university"),
                university_name=profile_data.get("university_name"),
                faculty_id=profile_data.get("faculty"),
                faculty_name=profile_data.get("faculty_name"),
                graduation=profile_data.get("graduation")
            ))

        # Parse universities array if present
        for uni in profile_data.get("universities", []):
            education.append(VKEducation(
                university_id=uni.get("id"),
                university_name=uni.get("name"),
                faculty_id=uni.get("faculty"),
                faculty_name=uni.get("faculty_name"),
                graduation=uni.get("graduation"),
                education_form=uni.get("education_form"),
                education_status=uni.get("education_status")
            ))

        # Parse career
        career = []
        for job in profile_data.get("career", []):
            career.append(VKCareer(
                company=job.get("company"),
                group_id=job.get("group_id"),
                country_id=job.get("country_id"),
                city_id=job.get("city_id"),
                city_name=job.get("city_name"),
                position=job.get("position"),
                from_year=job.get("from"),
                until_year=job.get("until")
            ))

        # Get photo URL
        photo_url = (
            profile_data.get("photo_max_orig") or
            profile_data.get("photo_400_orig") or
            profile_data.get("photo_200")
        )

        # Contacts
        connections = profile_data.get("connections", {})

        # Create profile object
        profile = VKFullProfile(
            vk_id=profile_data["id"],
            first_name=profile_data.get("first_name", ""),
            last_name=profile_data.get("last_name", ""),
            maiden_name=profile_data.get("maiden_name"),
            screen_name=profile_data.get("domain") or profile_data.get("screen_name"),
            sex=profile_data.get("sex"),
            bdate=profile_data.get("bdate"),
            age=self._calculate_age(profile_data.get("bdate")),
            city=city_data.get("title"),
            city_id=city_data.get("id"),
            country=country_data.get("title"),
            country_id=country_data.get("id"),
            home_town=profile_data.get("home_town"),
            photo_url=photo_url,
            photo_id=profile_data.get("photo_id"),
            status=profile_data.get("status"),
            last_seen=profile_data.get("last_seen"),
            online=profile_data.get("online", 0) == 1,
            is_closed=profile_data.get("is_closed", False),
            can_access_closed=profile_data.get("can_access_closed", True),
            mobile_phone=profile_data.get("mobile_phone"),
            home_phone=profile_data.get("home_phone"),
            site=profile_data.get("site"),
            skype=connections.get("skype"),
            twitter=connections.get("twitter"),
            instagram=connections.get("instagram"),
            facebook=connections.get("facebook"),
            relation=profile_data.get("relation"),
            relation_partner=profile_data.get("relation_partner"),
            friends_count=counters.get("friends", 0),
            followers_count=profile_data.get("followers_count", counters.get("followers", 0)),
            photos_count=counters.get("photos", 0),
            videos_count=counters.get("videos", 0),
            audios_count=counters.get("audios", 0),
            notes_count=counters.get("notes", 0),
            groups_count=counters.get("groups", 0),
            education=education,
            career=career,
            fetched_at=datetime.now().isoformat()
        )

        # Fetch additional data
        if include_friends:
            friends_data = self.get_friends(vk_id, friends_limit)
            if friends_data:
                access_restrictions["friends"] = True
                for f in friends_data:
                    profile.friends.append(VKFriend(
                        id=f["id"],
                        first_name=f.get("first_name", ""),
                        last_name=f.get("last_name", ""),
                        photo_url=f.get("photo_100"),
                        city=f.get("city", {}).get("title"),
                        is_closed=f.get("is_closed", False)
                    ))

        if include_groups:
            groups_data = self.get_groups(vk_id)
            if groups_data:
                access_restrictions["groups"] = True
                for g in groups_data:
                    profile.groups.append(VKGroup(
                        id=g["id"],
                        name=g.get("name", ""),
                        screen_name=g.get("screen_name"),
                        type=g.get("type"),
                        is_closed=g.get("is_closed", 0) != 0,
                        members_count=g.get("members_count"),
                        photo_url=g.get("photo_200") or g.get("photo_100"),
                        description=g.get("description")
                    ))

        if include_wall:
            posts_data = self.get_wall_posts(vk_id, wall_limit)
            if posts_data:
                access_restrictions["wall"] = True
                for p in posts_data:
                    likes = p.get("likes", {})
                    comments = p.get("comments", {})
                    reposts = p.get("reposts", {})
                    views = p.get("views", {})

                    profile.wall_posts.append(VKWallPost(
                        id=p["id"],
                        from_id=p.get("from_id", vk_id),
                        owner_id=p.get("owner_id", vk_id),
                        date=p.get("date", 0),
                        text=p.get("text", ""),
                        likes_count=likes.get("count", 0),
                        comments_count=comments.get("count", 0),
                        reposts_count=reposts.get("count", 0),
                        views_count=views.get("count", 0),
                        post_type=p.get("post_type"),
                        is_pinned=p.get("is_pinned", False),
                        attachments=p.get("attachments", [])
                    ))

        if include_photos:
            photos_data = self.get_photos(vk_id, photos_limit)
            if photos_data:
                access_restrictions["photos"] = True
                for ph in photos_data:
                    # Get largest size
                    sizes = ph.get("sizes", [])
                    largest = max(sizes, key=lambda x: x.get("width", 0) * x.get("height", 0)) if sizes else {}

                    profile.photos.append(VKPhoto(
                        id=ph["id"],
                        owner_id=ph.get("owner_id", vk_id),
                        album_id=ph.get("album_id", 0),
                        date=ph.get("date", 0),
                        text=ph.get("text"),
                        url=largest.get("url"),
                        width=largest.get("width"),
                        height=largest.get("height")
                    ))

        profile.access_restrictions = access_restrictions

        logger.info(f"Analysis complete. Friends: {len(profile.friends)}, "
                   f"Groups: {len(profile.groups)}, Posts: {len(profile.wall_posts)}, "
                   f"Photos: {len(profile.photos)}")

        return profile


# ============================================================================
# Demo Mode
# ============================================================================

DEMO_PROFILE = {
    "id": 123456789,
    "first_name": "Иван",
    "last_name": "Иванов",
    "domain": "ivanov_ivan",
    "sex": 2,
    "bdate": "15.5.1990",
    "city": {"id": 1, "title": "Москва"},
    "country": {"id": 1, "title": "Россия"},
    "photo_max_orig": "https://vk.com/images/camera_200.png",
    "status": "Работаю над интересными проектами!",
    "last_seen": {"time": 1706745600, "platform": 7},
    "online": 0,
    "is_closed": False,
    "can_access_closed": True,
    "university": 1,
    "university_name": "МГУ им. М.В. Ломоносова",
    "faculty": 15,
    "faculty_name": "ВМК",
    "graduation": 2012,
    "career": [
        {"company": "Яндекс", "position": "Разработчик", "from": 2015, "until": 0}
    ],
    "counters": {
        "friends": 352,
        "followers": 48,
        "photos": 127,
        "videos": 23,
        "groups": 45
    },
    "connections": {
        "twitter": "ivanov_dev",
        "instagram": "ivan.ivanov"
    }
}

DEMO_FRIENDS = [
    {"id": 111, "first_name": "Петр", "last_name": "Петров", "city": {"title": "Москва"}},
    {"id": 222, "first_name": "Мария", "last_name": "Сидорова", "city": {"title": "Москва"}},
    {"id": 333, "first_name": "Алексей", "last_name": "Козлов", "city": {"title": "Санкт-Петербург"}}
]

DEMO_GROUPS = [
    {"id": 1, "name": "Python Developers", "type": "group", "members_count": 50000},
    {"id": 2, "name": "Habr", "type": "page", "members_count": 200000}
]

DEMO_POSTS = [
    {
        "id": 1001, "from_id": 123456789, "owner_id": 123456789,
        "date": 1706745600, "text": "Отличный день для программирования!",
        "likes": {"count": 15}, "comments": {"count": 3}, "reposts": {"count": 1}
    }
]


def run_demo():
    """Run demo mode with mock data."""
    print("\n" + "="*70)
    print("VK PROFILE ANALYZER - DEMO MODE")
    print("="*70)

    analyzer = VKProfileAnalyzer(service_token="demo_mode")

    # Manually construct profile for demo
    profile = VKFullProfile(
        vk_id=DEMO_PROFILE["id"],
        first_name=DEMO_PROFILE["first_name"],
        last_name=DEMO_PROFILE["last_name"],
        screen_name=DEMO_PROFILE["domain"],
        sex=DEMO_PROFILE["sex"],
        bdate=DEMO_PROFILE["bdate"],
        age=analyzer._calculate_age(DEMO_PROFILE["bdate"]),
        city=DEMO_PROFILE["city"]["title"],
        country=DEMO_PROFILE["country"]["title"],
        photo_url=DEMO_PROFILE["photo_max_orig"],
        status=DEMO_PROFILE["status"],
        last_seen=DEMO_PROFILE["last_seen"],
        is_closed=DEMO_PROFILE["is_closed"],
        friends_count=DEMO_PROFILE["counters"]["friends"],
        followers_count=DEMO_PROFILE["counters"]["followers"],
        photos_count=DEMO_PROFILE["counters"]["photos"],
        groups_count=DEMO_PROFILE["counters"]["groups"],
        education=[VKEducation(
            university_name=DEMO_PROFILE["university_name"],
            faculty_name=DEMO_PROFILE["faculty_name"],
            graduation=DEMO_PROFILE["graduation"]
        )],
        career=[VKCareer(
            company=DEMO_PROFILE["career"][0]["company"],
            position=DEMO_PROFILE["career"][0]["position"],
            from_year=DEMO_PROFILE["career"][0]["from"]
        )],
        twitter=DEMO_PROFILE["connections"]["twitter"],
        instagram=DEMO_PROFILE["connections"]["instagram"],
        fetched_at=datetime.now().isoformat()
    )

    # Add demo friends
    for f in DEMO_FRIENDS:
        profile.friends.append(VKFriend(
            id=f["id"],
            first_name=f["first_name"],
            last_name=f["last_name"],
            city=f.get("city", {}).get("title")
        ))

    # Add demo groups
    for g in DEMO_GROUPS:
        profile.groups.append(VKGroup(
            id=g["id"],
            name=g["name"],
            type=g["type"],
            members_count=g["members_count"]
        ))

    # Add demo posts
    for p in DEMO_POSTS:
        profile.wall_posts.append(VKWallPost(
            id=p["id"],
            from_id=p["from_id"],
            owner_id=p["owner_id"],
            date=p["date"],
            text=p["text"],
            likes_count=p["likes"]["count"],
            comments_count=p["comments"]["count"],
            reposts_count=p["reposts"]["count"]
        ))

    # Display results
    print(f"\n{'='*70}")
    print("PROFILE SUMMARY")
    print("="*70)
    print(f"Name:        {profile.first_name} {profile.last_name}")
    print(f"VK ID:       {profile.vk_id}")
    print(f"Profile URL: {profile.profile_url}")
    print(f"City:        {profile.city}")
    print(f"Age:         {profile.age}")
    print(f"Status:      {profile.status}")
    print(f"Friends:     {profile.friends_count}")
    print(f"Followers:   {profile.followers_count}")
    print(f"Photos:      {profile.photos_count}")
    print(f"Groups:      {profile.groups_count}")

    if profile.education:
        print(f"\n--- Education ---")
        for edu in profile.education:
            print(f"  {edu.university_name} - {edu.faculty_name} ({edu.graduation})")

    if profile.career:
        print(f"\n--- Career ---")
        for job in profile.career:
            until = "present" if not job.until_year else job.until_year
            print(f"  {job.company} - {job.position} ({job.from_year}-{until})")

    print(f"\n--- Social Links ---")
    if profile.twitter:
        print(f"  Twitter: @{profile.twitter}")
    if profile.instagram:
        print(f"  Instagram: @{profile.instagram}")

    print(f"\n--- Friends ({len(profile.friends)}) ---")
    for friend in profile.friends[:5]:
        print(f"  {friend.first_name} {friend.last_name} ({friend.city or 'N/A'})")

    print(f"\n--- Groups ({len(profile.groups)}) ---")
    for group in profile.groups[:5]:
        print(f"  {group.name} ({group.members_count:,} members)")

    print(f"\n--- Recent Posts ({len(profile.wall_posts)}) ---")
    for post in profile.wall_posts[:3]:
        text_preview = post.text[:50] + "..." if len(post.text) > 50 else post.text
        print(f"  [{post.likes_count} likes] {text_preview}")

    # Convert to dict for JSON output
    def profile_to_dict(p):
        d = asdict(p)
        # Convert nested dataclasses
        d["education"] = [asdict(e) for e in p.education]
        d["career"] = [asdict(c) for c in p.career]
        d["friends"] = [asdict(f) for f in p.friends]
        d["groups"] = [asdict(g) for g in p.groups]
        d["wall_posts"] = [asdict(w) for w in p.wall_posts]
        d["photos"] = [asdict(ph) for ph in p.photos]
        return d

    output = profile_to_dict(profile)

    print(f"\n{'='*70}")
    print("JSON OUTPUT (truncated):")
    print("="*70)
    print(json.dumps(output, ensure_ascii=False, indent=2)[:2000] + "...")

    return output


def main():
    parser = argparse.ArgumentParser(
        description="Deep analyze a VK user profile",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --vk-id 123456789
  %(prog)s --vk-id 123456789 --output profile.json
  %(prog)s --vk-id 123456789 --no-friends --no-groups
  %(prog)s --demo

Environment:
  VK_SERVICE_TOKEN  VK API service token
        """
    )

    parser.add_argument("--vk-id", type=int, help="VK user ID to analyze")
    parser.add_argument("--output", "-o", help="Output JSON file")
    parser.add_argument("--no-friends", action="store_true", help="Skip friends list")
    parser.add_argument("--no-groups", action="store_true", help="Skip groups")
    parser.add_argument("--no-wall", action="store_true", help="Skip wall posts")
    parser.add_argument("--no-photos", action="store_true", help="Skip photos")
    parser.add_argument("--friends-limit", type=int, default=500, help="Max friends (default: 500)")
    parser.add_argument("--wall-limit", type=int, default=100, help="Max wall posts (default: 100)")
    parser.add_argument("--photos-limit", type=int, default=50, help="Max photos (default: 50)")
    parser.add_argument("--demo", action="store_true", help="Run demo mode")
    parser.add_argument("--verbose", "-v", action="store_true")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.demo:
        output = run_demo()
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(output, f, ensure_ascii=False, indent=2)
            print(f"\nSaved to: {args.output}")
        return

    if not args.vk_id:
        parser.error("--vk-id is required (or use --demo)")

    try:
        analyzer = VKProfileAnalyzer()
        profile = analyzer.analyze(
            vk_id=args.vk_id,
            include_friends=not args.no_friends,
            include_groups=not args.no_groups,
            include_wall=not args.no_wall,
            include_photos=not args.no_photos,
            friends_limit=args.friends_limit,
            wall_limit=args.wall_limit,
            photos_limit=args.photos_limit
        )

        # Convert to dict
        def profile_to_dict(p):
            d = asdict(p)
            d["education"] = [asdict(e) for e in p.education]
            d["career"] = [asdict(c) for c in p.career]
            d["friends"] = [asdict(f) for f in p.friends]
            d["groups"] = [asdict(g) for g in p.groups]
            d["wall_posts"] = [asdict(w) for w in p.wall_posts]
            d["photos"] = [asdict(ph) for ph in p.photos]
            return d

        output = profile_to_dict(profile)

        # Print summary
        print(f"\n{'='*70}")
        print(f"PROFILE: {profile.first_name} {profile.last_name}")
        print("="*70)
        print(f"VK ID:       {profile.vk_id}")
        print(f"Profile URL: {profile.profile_url}")
        print(f"City:        {profile.city or 'N/A'}")
        print(f"Age:         {profile.age or 'N/A'}")
        print(f"Friends:     {len(profile.friends)} fetched / {profile.friends_count} total")
        print(f"Groups:      {len(profile.groups)} fetched / {profile.groups_count} total")
        print(f"Wall posts:  {len(profile.wall_posts)}")
        print(f"Photos:      {len(profile.photos)} fetched / {profile.photos_count} total")
        print(f"Private:     {'Yes' if profile.is_closed else 'No'}")

        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(output, f, ensure_ascii=False, indent=2)
            print(f"\nFull data saved to: {args.output}")
        else:
            print("\nUse --output to save full JSON data")

    except VKAPIError as e:
        logger.error(f"VK API Error: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(0)


if __name__ == "__main__":
    main()
