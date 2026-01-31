"""
Profile Data Model
==================
Enhanced profile structure for Phase 1 output.
Implements Буратино-style confidence scoring and rich profile data.
"""

from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any, List
from enum import Enum
from datetime import datetime
import json


class Platform(Enum):
    """Supported social media platforms."""
    VK = "vk"
    OK = "ok"
    TELEGRAM = "telegram"
    INSTAGRAM = "instagram"
    FACEBOOK = "facebook"
    UNKNOWN = "unknown"


class ConfidenceLevel(Enum):
    """Confidence levels for profile matching."""
    HIGH = "high"        # Face match + name match
    MEDIUM = "medium"    # Face match only OR name match with photo
    LOW = "low"          # Name match only
    UNCERTAIN = "uncertain"  # Weak indicators


@dataclass
class ProfileMatch:
    """
    Enhanced profile data structure for Phase 1 results.

    Contains all scraped data plus confidence scoring for user confirmation.
    """
    # Core identification
    url: str
    platform: Platform
    username: str

    # Display info
    display_name: str
    photo_url: Optional[str] = None
    bio: Optional[str] = None

    # Location data
    location: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None

    # Profile metadata
    friends_count: Optional[int] = None
    followers_count: Optional[int] = None
    age: Optional[int] = None

    # Confidence scoring
    confidence_score: float = 0.0  # 0-100
    confidence_level: ConfidenceLevel = ConfidenceLevel.UNCERTAIN

    # Match indicators (what contributed to confidence)
    name_match: bool = False
    name_similarity: float = 0.0  # 0-100
    face_match: bool = False
    face_similarity: float = 0.0  # 0-100
    location_match: bool = False

    # Source tracking
    source: str = "unknown"  # vk_direct, ok_direct, telegram_direct, yandex_images, search4faces
    discovered_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    # Raw scraped data (for deep investigation)
    raw_data: Dict[str, Any] = field(default_factory=dict)

    # Status flags
    is_verified: bool = False  # User confirmed this is the target
    is_rejected: bool = False  # User rejected this profile
    photos_checked: int = 0

    def calculate_confidence(self) -> None:
        """
        Calculate confidence score based on match indicators.

        Scoring:
        - Face match (50 points max): If face_match, add face_similarity/2
        - Name match (30 points max): If name_match, add name_similarity * 0.3
        - Location match (10 points): If location_match
        - Has photo (5 points): If photo_url exists
        - Has bio (5 points): If bio exists
        """
        score = 0.0

        # Face matching is the strongest indicator
        if self.face_match:
            score += min(50.0, self.face_similarity / 2)

        # Name matching
        if self.name_match:
            score += min(30.0, self.name_similarity * 0.3)

        # Location matching
        if self.location_match:
            score += 10.0

        # Profile completeness bonuses
        if self.photo_url:
            score += 5.0
        if self.bio:
            score += 5.0

        self.confidence_score = min(100.0, score)

        # Set confidence level
        if self.confidence_score >= 70 or (self.face_match and self.name_match):
            self.confidence_level = ConfidenceLevel.HIGH
        elif self.confidence_score >= 40 or self.face_match:
            self.confidence_level = ConfidenceLevel.MEDIUM
        elif self.confidence_score >= 20 or self.name_match:
            self.confidence_level = ConfidenceLevel.LOW
        else:
            self.confidence_level = ConfidenceLevel.UNCERTAIN

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = asdict(self)
        # Convert enums to strings
        result['platform'] = self.platform.value
        result['confidence_level'] = self.confidence_level.value
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProfileMatch':
        """Create ProfileMatch from dictionary."""
        # Convert string to enum
        if 'platform' in data and isinstance(data['platform'], str):
            data['platform'] = Platform(data['platform'].lower())
        if 'confidence_level' in data and isinstance(data['confidence_level'], str):
            try:
                data['confidence_level'] = ConfidenceLevel(data['confidence_level'])
            except ValueError:
                data['confidence_level'] = ConfidenceLevel.UNCERTAIN
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    @classmethod
    def from_legacy_result(cls, result: Dict[str, Any]) -> 'ProfileMatch':
        """
        Convert legacy search result format to ProfileMatch.

        Legacy format: {platform, username, url, display_name, photo_url, exists, source, face_match, face_similarity}
        """
        # Determine platform
        platform_str = result.get('platform', 'unknown').lower()
        platform_map = {
            'vk': Platform.VK,
            'vkontakte': Platform.VK,
            'ok': Platform.OK,
            'odnoklassniki': Platform.OK,
            'telegram': Platform.TELEGRAM,
            'instagram': Platform.INSTAGRAM,
            'facebook': Platform.FACEBOOK,
        }
        platform = platform_map.get(platform_str, Platform.UNKNOWN)

        profile = cls(
            url=result.get('url', ''),
            platform=platform,
            username=result.get('username', ''),
            display_name=result.get('display_name', result.get('username', '')),
            photo_url=result.get('photo_url'),
            bio=result.get('bio'),
            source=result.get('source', 'unknown'),
            face_match=result.get('face_match', False),
            face_similarity=result.get('face_similarity', 0.0),
            photos_checked=result.get('photos_checked', 0),
            raw_data=result
        )

        # Set name match if display_name exists and is meaningful
        if profile.display_name and len(profile.display_name) > 2:
            profile.name_match = True
            profile.name_similarity = 50.0  # Default for legacy

        profile.calculate_confidence()
        return profile


@dataclass
class Phase1Result:
    """
    Complete Phase 1 search result.

    Contains all discovered profiles ready for user confirmation.
    """
    target_name: str
    target_photo_path: Optional[str]
    profiles: List[ProfileMatch] = field(default_factory=list)

    # Search metadata
    search_time_seconds: float = 0.0
    usernames_searched: int = 0
    total_raw_results: int = 0

    # Statistics by platform
    vk_found: int = 0
    ok_found: int = 0
    telegram_found: int = 0
    yandex_found: int = 0

    # Face matching stats
    face_matching_enabled: bool = False
    face_matches_found: int = 0
    photos_scanned: int = 0

    def get_high_confidence_profiles(self) -> List[ProfileMatch]:
        """Get profiles with HIGH confidence level."""
        return [p for p in self.profiles if p.confidence_level == ConfidenceLevel.HIGH]

    def get_profiles_sorted_by_confidence(self) -> List[ProfileMatch]:
        """Get all profiles sorted by confidence score (highest first)."""
        return sorted(self.profiles, key=lambda p: p.confidence_score, reverse=True)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'target_name': self.target_name,
            'target_photo_path': self.target_photo_path,
            'profiles': [p.to_dict() for p in self.profiles],
            'search_time_seconds': self.search_time_seconds,
            'usernames_searched': self.usernames_searched,
            'total_raw_results': self.total_raw_results,
            'vk_found': self.vk_found,
            'ok_found': self.ok_found,
            'telegram_found': self.telegram_found,
            'yandex_found': self.yandex_found,
            'face_matching_enabled': self.face_matching_enabled,
            'face_matches_found': self.face_matches_found,
            'photos_scanned': self.photos_scanned,
            'high_confidence_count': len(self.get_high_confidence_profiles()),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Phase1Result':
        """Create Phase1Result from dictionary."""
        profiles = [ProfileMatch.from_dict(p) for p in data.get('profiles', [])]
        return cls(
            target_name=data.get('target_name', ''),
            target_photo_path=data.get('target_photo_path'),
            profiles=profiles,
            search_time_seconds=data.get('search_time_seconds', 0.0),
            usernames_searched=data.get('usernames_searched', 0),
            total_raw_results=data.get('total_raw_results', 0),
            vk_found=data.get('vk_found', 0),
            ok_found=data.get('ok_found', 0),
            telegram_found=data.get('telegram_found', 0),
            yandex_found=data.get('yandex_found', 0),
            face_matching_enabled=data.get('face_matching_enabled', False),
            face_matches_found=data.get('face_matches_found', 0),
            photos_scanned=data.get('photos_scanned', 0),
        )


def convert_legacy_results_to_phase1(
    legacy_results: Dict[str, Any],
    target_name: str,
    target_photo_path: Optional[str] = None
) -> Phase1Result:
    """
    Convert legacy combined_search results to new Phase1Result format.

    Args:
        legacy_results: Results from CombinedSearchService.search()
        target_name: Target's name
        target_photo_path: Path to target's photo

    Returns:
        Phase1Result with ProfileMatch objects
    """
    accounts = legacy_results.get('accounts', legacy_results.get('results', []))
    stats = legacy_results.get('stats', {})

    profiles = []
    for acc in accounts:
        profile = ProfileMatch.from_legacy_result(acc)
        profiles.append(profile)

    # Sort by confidence
    profiles.sort(key=lambda p: p.confidence_score, reverse=True)

    # Parse search time (format: "Xm Ys")
    search_time_str = stats.get('search_time', '0m 0s')
    try:
        parts = search_time_str.replace('m', '').replace('s', '').split()
        minutes = int(parts[0]) if len(parts) > 0 else 0
        seconds = int(parts[1]) if len(parts) > 1 else 0
        search_time = minutes * 60 + seconds
    except (ValueError, IndexError):
        search_time = 0.0

    return Phase1Result(
        target_name=target_name,
        target_photo_path=target_photo_path,
        profiles=profiles,
        search_time_seconds=search_time,
        usernames_searched=stats.get('usernames_searched', stats.get('usernames_generated', 0)),
        total_raw_results=stats.get('raw_accounts', stats.get('accounts_found', 0)),
        vk_found=stats.get('vk_found', 0),
        ok_found=stats.get('ok_found', 0),
        telegram_found=stats.get('telegram_found', 0),
        yandex_found=stats.get('yandex_found', 0),
        face_matching_enabled=stats.get('face_matching_enabled', False),
        face_matches_found=stats.get('face_matches', 0),
        photos_scanned=stats.get('photos_scanned', 0),
    )
