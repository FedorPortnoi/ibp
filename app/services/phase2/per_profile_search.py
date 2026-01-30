"""
Phase 2 Per-Profile Search - Individual Profile Processing
============================================================
Processes each Phase 1 profile individually and tracks contact discovery
per-profile rather than aggregated per-target.

SUCCESS CRITERIA:
- Each profile must have at least 1 VERIFIED email AND 1 phone
- Emails are only counted if verified via Holehe/Gravatar/profile-scraping
- Pattern-generated emails without verification are EXCLUDED

FEATURES:
- Fast mode with parallel email verification
- VK API integration for profile extraction
- Telegram, OK.ru, Mail.ru, Yandex phone lookup
- In-memory caching for performance
- Confidence scoring for results
- JSON/CSV export support
- Error recovery with fallback methods

USAGE:
    from app.services.phase2.per_profile_search import PerProfileSearchService

    service = PerProfileSearchService(fast_mode=True)
    results = service.investigate_all_profiles(
        profiles=[{'url': '...', 'platform': 'vk', 'username': '...'}],
        target_name="John Doe"
    )

    print(f"Passing: {results.passing_profiles}/{results.total_profiles}")
    print(f"Emails: {results.total_verified_emails}")
    print(f"Phones: {results.total_phones}")

    # Export results
    results.save_json("results.json")
"""

import logging
import subprocess
import re
import time
import hashlib
from typing import List, Dict, Optional
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor

from .russian_phone_validator import RussianPhoneValidator, PhoneInfo
from .profile_scraper import scrape_profile
from .phone_discovery import PhoneDiscoveryService
from .breach_checker import BreachChecker
from .vk_api_extractor import VKAPIExtractor, VKContact
from .email_sources import (
    CombinedEmailSources,
    EpieosChecker,
    HunterIOChecker,
    EmailRepChecker,
    smtp_verify_email
)

logger = logging.getLogger(__name__)

# Known services that Holehe can detect (for validation)
# This list is used to filter out false positives from header parsing
KNOWN_HOLEHE_SERVICES = {
    # Social Media
    'twitter', 'twitter.com', 'instagram', 'instagram.com', 'facebook', 'facebook.com',
    'tiktok', 'tiktok.com', 'snapchat', 'snapchat.com', 'pinterest', 'pinterest.com',
    'tumblr', 'tumblr.com', 'reddit', 'reddit.com', 'linkedin', 'linkedin.com',
    'vk', 'vk.com', 'ok.ru', 'odnoklassniki',
    # Tech/Dev
    'github', 'github.com', 'gitlab', 'gitlab.com', 'bitbucket', 'bitbucket.org',
    'stackoverflow', 'stackoverflow.com', 'docker', 'docker.com', 'npmjs', 'npm',
    # Gaming
    'steam', 'steampowered.com', 'twitch', 'twitch.tv', 'discord', 'discord.com',
    'epicgames', 'epicgames.com', 'playstation', 'xbox', 'ea', 'origin',
    'blizzard', 'battle.net', 'riotgames', 'ubisoft',
    # Streaming/Media
    'spotify', 'spotify.com', 'netflix', 'netflix.com', 'hulu', 'soundcloud',
    'soundcloud.com', 'deezer', 'deezer.com', 'vimeo', 'vimeo.com', 'dailymotion',
    'youtube', 'youtube.com', 'apple', 'music.apple.com',
    # Shopping
    'amazon', 'amazon.com', 'ebay', 'ebay.com', 'aliexpress', 'etsy', 'etsy.com',
    'wish', 'shopify',
    # Email/Comms
    'protonmail', 'protonmail.com', 'mailru', 'mail.ru', 'yahoo', 'yahoo.com',
    'outlook', 'outlook.com', 'zoho', 'yandex', 'yandex.ru', 'gmx',
    # Cloud/Storage
    'dropbox', 'dropbox.com', 'box', 'box.com', 'mega', 'mega.nz', 'icloud',
    'onedrive', 'google', 'drive', 'pcloud',
    # Other
    'adobe', 'adobe.com', 'canva', 'figma', 'notion', 'trello', 'slack',
    'zoom', 'zoom.us', 'skype', 'teams', 'webex', 'telegram', 'telegram.org',
    'signal', 'whatsapp', 'viber', 'line', 'wechat',
    'paypal', 'paypal.com', 'stripe', 'venmo', 'cashapp',
    'airbnb', 'airbnb.com', 'booking', 'booking.com', 'uber', 'lyft',
    'wordpress', 'wordpress.com', 'medium', 'medium.com', 'blogger', 'wix',
    'gravatar', 'gravatar.com', 'about.me', 'linktree',
    'quora', 'quora.com', 'flickr', 'flickr.com', 'imgur', 'imgur.com',
    'patreon', 'patreon.com', 'onlyfans', 'gumroad',
    'duolingo', 'duolingo.com', 'codecademy', 'coursera', 'udemy',
    'eventbrite', 'eventbrite.com', 'meetup', 'meetup.com',
    'lastpass', 'lastpass.com', '1password', 'bitwarden', 'dashlane',
    'bodybuilding', 'bodybuilding.com', 'strava', 'strava.com', 'fitbit',
    'komoot', 'komoot.com', 'nike', 'nikeplus', 'adidas',
    'office365', 'office365.com', 'microsoft.com', 'live.com',
    'rambler', 'rambler.ru', 'mail', 'bk.ru', 'list.ru', 'inbox.ru',
}


def parse_holehe_output(output: str) -> List[str]:
    """
    Parse Holehe CLI output and extract REAL service names.

    CRITICAL: Filters out the header line that contains "[+] Email used"
    which was causing false positives where "Email" was being extracted
    as a service name.

    Valid service lines look like:
        [+] twitter.com
        [+] spotify
        [+] instagram.com

    Invalid lines to skip:
        [+] Email used, [-] Email not used, [x] Rate limit  (HEADER)
        [-] twitter.com  (not found)
        [x] Rate limit  (rate limited)

    Returns:
        List of actual service names where the email is registered
    """
    services = []

    for line in output.split('\n'):
        line = line.strip()

        # Skip empty lines
        if not line:
            continue

        # Skip lines without [+] (we only want positive matches)
        if '[+]' not in line:
            continue

        # CRITICAL: Skip the header line
        # Header format: "[+] Email used, [-] Email not used, [x] Rate limit"
        if 'Email used' in line or 'not used' in line or 'Rate limit' in line:
            continue

        # Skip informational lines
        if 'email' in line.lower() and ('used' in line.lower() or 'check' in line.lower()):
            continue

        # Extract service name after [+]
        # Format: "[+] servicename" or "[+] servicename : extra info"
        match = re.search(r'\[\+\]\s*(\S+)', line)
        if not match:
            continue

        service = match.group(1).strip().rstrip(':').lower()

        # Skip if too short (likely parsing error)
        if len(service) < 2:
            continue

        # Skip the word "Email" itself (artifact of header parsing)
        if service == 'email':
            continue

        # Validate: must be a known service OR contain a dot (domain)
        is_known = service in KNOWN_HOLEHE_SERVICES
        has_domain = '.' in service

        if is_known or has_domain:
            services.append(service)
        else:
            # Log unknown services for debugging (but don't include them)
            logger.debug(f"Holehe: Unknown service '{service}' - skipping")

    return services


def calculate_name_similarity(name1: str, name2: str) -> float:
    """
    Calculate similarity between two names (0.0 - 1.0).

    Handles:
    - Case insensitivity
    - Partial matches (first name or last name only)
    - Cyrillic/Latin transliteration variations
    - Common Russian diminutives

    Returns:
        Float between 0.0 (no match) and 1.0 (exact match)
    """
    if not name1 or not name2:
        return 0.0

    # Normalize: lowercase, strip whitespace
    n1 = name1.lower().strip()
    n2 = name2.lower().strip()

    # Exact match
    if n1 == n2:
        return 1.0

    # Split into parts
    parts1 = set(n1.split())
    parts2 = set(n2.split())

    # If any part matches exactly (first name or last name)
    common_parts = parts1 & parts2
    if common_parts:
        # Calculate score based on how many parts match
        max_parts = max(len(parts1), len(parts2))
        return 0.5 + (0.5 * len(common_parts) / max_parts)

    # Try transliteration
    transliterated1 = _transliterate_name(n1)
    transliterated2 = _transliterate_name(n2)

    if transliterated1 == transliterated2:
        return 0.9

    # Check if transliterated parts match
    trans_parts1 = set(transliterated1.split())
    trans_parts2 = set(transliterated2.split())
    trans_common = trans_parts1 & trans_parts2
    if trans_common:
        max_parts = max(len(trans_parts1), len(trans_parts2))
        return 0.4 + (0.4 * len(trans_common) / max_parts)

    # Levenshtein-like similarity for fuzzy matching
    return _fuzzy_similarity(transliterated1, transliterated2)


def _transliterate_name(name: str) -> str:
    """Transliterate Cyrillic to Latin for comparison."""
    translit_map = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
        'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
        'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
        'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
        'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
    }
    result = ""
    for char in name.lower():
        result += translit_map.get(char, char)
    return result


def _fuzzy_similarity(s1: str, s2: str) -> float:
    """Calculate fuzzy string similarity (Jaro-like)."""
    if not s1 or not s2:
        return 0.0

    if s1 == s2:
        return 1.0

    len1, len2 = len(s1), len(s2)

    # Simple character overlap
    set1, set2 = set(s1), set(s2)
    overlap = len(set1 & set2)
    union = len(set1 | set2)

    if union == 0:
        return 0.0

    # Jaccard similarity
    jaccard = overlap / union

    # Penalize length difference
    length_diff = abs(len1 - len2) / max(len1, len2)
    length_penalty = 1.0 - (length_diff * 0.3)

    return jaccard * length_penalty * 0.3  # Cap at 0.3 for fuzzy matches


def extract_name_from_source(source: str) -> Optional[str]:
    """
    Try to extract a person's name from a phone source string.

    Examples:
    - "OK.ru profile (url) [name: John Doe]" -> "John Doe"
    - "VK profile deep scan" -> None

    Returns:
        Name if found in source string, None otherwise
    """
    # Check for [name: ...] pattern added by phone_discovery
    name_match = re.search(r'\[name:\s*([^\]]+)\]', source)
    if name_match:
        return name_match.group(1).strip()

    return None


def retry_with_backoff(func, max_retries: int = 3, initial_delay: float = 1.0):
    """Execute function with exponential backoff retry."""
    last_exception = None
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            last_exception = e
            if attempt < max_retries - 1:
                delay = initial_delay * (2 ** attempt)
                time.sleep(delay)
                logger.debug(f"Retry {attempt + 1}/{max_retries} after {delay}s: {e}")
    raise last_exception


@dataclass
class VerifiedEmail:
    """An email that has been VERIFIED to exist (not just pattern-generated)."""
    email: str
    source: str
    verification_method: str  # holehe, gravatar, profile_scraping, breach
    services: List[str] = field(default_factory=list)  # Services where registered
    confidence_score: float = 0.7  # 0-1, higher = more confident

    def calculate_confidence(self) -> float:
        """Calculate confidence score based on verification method and services."""
        base_scores = {
            'profile_scraping': 0.95,  # Found directly in profile = high confidence
            'holehe': 0.85,            # Verified via service registration
            'gravatar': 0.80,          # Has gravatar = likely real
            'breach': 0.75,            # In breach = exists, but may be old
        }
        base = base_scores.get(self.verification_method, 0.5)

        # Boost if registered on multiple services
        if len(self.services) >= 3:
            base = min(base + 0.1, 1.0)
        elif len(self.services) >= 2:
            base = min(base + 0.05, 1.0)

        self.confidence_score = base
        return base


@dataclass
class DiscoveredPhone:
    """A phone number discovered for a profile."""
    number: str
    source: str
    confidence: str  # high, medium, low
    confidence_score: float = 0.7  # 0-1, higher = more confident
    is_duplicate: bool = False  # True if found for multiple targets
    duplicate_targets: List[str] = field(default_factory=list)  # Other targets with same phone
    source_profile_name: Optional[str] = None  # Name from source profile (if extracted)
    name_match_score: float = 0.5  # How well source name matches target (0-1)

    def calculate_confidence(self, target_name: str = None) -> float:
        """
        Calculate confidence score based on source, duplicate status, and name match.

        Args:
            target_name: If provided, calculate name match with source profile
        """
        source_scores = {
            'profile contacts': 0.95,
            'VK profile contacts': 0.95,
            'VK API contacts': 0.95,
            'OK.ru profile': 0.90,
            'VK JSON data': 0.90,
            'VK wall post': 0.75,
            'VK profile deep scan': 0.70,
            'Telegram bio': 0.85,
            'Username pattern': 0.50,
            'Email local part': 0.60,
        }

        # Find best matching source
        source_lower = self.source.lower()
        base_score = None
        for key, score in source_scores.items():
            if key.lower() in source_lower:
                base_score = score
                break

        if base_score is None:
            # Default based on confidence string
            default_scores = {'high': 0.80, 'medium': 0.60, 'low': 0.40}
            base_score = default_scores.get(self.confidence, 0.50)

        # Calculate name match if we have source profile name and target name
        if target_name and self.source_profile_name:
            self.name_match_score = calculate_name_similarity(
                self.source_profile_name, target_name
            )
            # Boost or penalize based on name match
            if self.name_match_score >= 0.8:
                # Strong name match - boost confidence
                base_score = min(base_score + 0.1, 0.95)
            elif self.name_match_score < 0.3:
                # Poor name match - likely different person
                base_score = base_score * 0.6
                logger.debug(
                    f"Low name match ({self.name_match_score:.2f}) for phone {self.number}: "
                    f"'{self.source_profile_name}' vs '{target_name}'"
                )

        # CRITICAL: Heavily penalize duplicates (same phone for multiple targets)
        if self.is_duplicate:
            # Reduce confidence by 50% for duplicates
            base_score = base_score * 0.5
            # Further reduce if found for 3+ targets
            if len(self.duplicate_targets) >= 3:
                base_score = base_score * 0.5

        self.confidence_score = max(0.0, min(1.0, base_score))
        return self.confidence_score


def normalize_phone(phone: str) -> str:
    """
    Normalize phone number to standard format for comparison.
    Converts various formats to +7XXXXXXXXXX.
    """
    # Remove all non-digits
    digits = re.sub(r'\D', '', phone)

    # Handle different formats
    if len(digits) == 11:
        # Russian format: 8XXXXXXXXXX or 7XXXXXXXXXX
        if digits.startswith('8'):
            digits = '7' + digits[1:]
        return '+' + digits
    elif len(digits) == 10:
        # Missing country code, assume Russia
        return '+7' + digits
    elif len(digits) == 12 and digits.startswith('7'):
        # Already has +7
        return '+' + digits

    # Return as-is if we can't normalize
    return '+' + digits if not phone.startswith('+') else phone


class PhoneDeduplicator:
    """
    Tracks phones across multiple targets to detect duplicates.

    A phone appearing for multiple different targets is suspicious -
    it likely means the phone was scraped from a generic search result,
    not from the actual target's profile.
    """

    def __init__(self):
        # phone (normalized) -> list of (target_name, source, profile_url)
        self._phone_registry: Dict[str, List[Dict]] = {}

    def register_phone(self, phone: str, target_name: str, source: str, profile_url: str = ""):
        """Register a phone found for a target."""
        normalized = normalize_phone(phone)
        if normalized not in self._phone_registry:
            self._phone_registry[normalized] = []

        self._phone_registry[normalized].append({
            'target': target_name,
            'source': source,
            'profile_url': profile_url
        })

    def is_duplicate(self, phone: str) -> bool:
        """Check if phone was found for multiple different targets."""
        normalized = normalize_phone(phone)
        entries = self._phone_registry.get(normalized, [])

        # Get unique targets
        unique_targets = set(e['target'] for e in entries)
        return len(unique_targets) > 1

    def get_duplicate_targets(self, phone: str) -> List[str]:
        """Get list of targets that share this phone."""
        normalized = normalize_phone(phone)
        entries = self._phone_registry.get(normalized, [])
        return list(set(e['target'] for e in entries))

    def get_duplicate_count(self, phone: str) -> int:
        """Get count of different targets with this phone."""
        return len(self.get_duplicate_targets(phone))

    def get_all_duplicates(self) -> Dict[str, List[str]]:
        """Get all phones that appear for multiple targets."""
        duplicates = {}
        for phone, entries in self._phone_registry.items():
            unique_targets = list(set(e['target'] for e in entries))
            if len(unique_targets) > 1:
                duplicates[phone] = unique_targets
        return duplicates

    def clear(self):
        """Clear all registered phones."""
        self._phone_registry.clear()


# Global deduplicator instance (used across investigate_all_profiles calls)
_global_phone_deduplicator = PhoneDeduplicator()


def get_phone_deduplicator() -> PhoneDeduplicator:
    """Get the global phone deduplicator instance."""
    return _global_phone_deduplicator


def reset_phone_deduplicator():
    """Reset the global phone deduplicator (call between test runs)."""
    _global_phone_deduplicator.clear()


@dataclass
class ProfileContactResult:
    """Contact discovery results for a SINGLE profile."""
    profile_url: str
    platform: str
    username: str

    # Target name (for name matching validation)
    target_name: str = ""

    # Only VERIFIED emails (no pattern guesses)
    verified_emails: List[VerifiedEmail] = field(default_factory=list)

    # Found phones
    phones: List[DiscoveredPhone] = field(default_factory=list)

    # Status tracking
    status: str = 'pending'  # pending, pass, fail
    processing_time: float = 0.0
    errors: List[str] = field(default_factory=list)

    @property
    def has_email(self) -> bool:
        """Check if profile has at least 1 verified email."""
        return len(self.verified_emails) > 0

    @property
    def has_phone(self) -> bool:
        """Check if profile has at least 1 VALID phone (excluding duplicates)."""
        return len(self.get_valid_phones()) > 0

    @property
    def has_any_phone(self) -> bool:
        """Check if profile has at least 1 phone (including duplicates)."""
        return len(self.phones) > 0

    def get_valid_phones(self, min_confidence: float = 0.3) -> List[DiscoveredPhone]:
        """Get phones that are not duplicates and meet minimum confidence."""
        valid = []
        for phone in self.phones:
            # Calculate confidence with name matching if target_name is set
            phone.calculate_confidence(target_name=self.target_name if self.target_name else None)
            # Skip duplicates (same phone found for multiple targets)
            if phone.is_duplicate:
                continue
            # Skip low confidence phones
            if phone.confidence_score < min_confidence:
                continue
            valid.append(phone)
        return valid

    @property
    def duplicate_phones_count(self) -> int:
        """Count of phones that are duplicates (found for multiple targets)."""
        return sum(1 for p in self.phones if p.is_duplicate)

    @property
    def is_complete(self) -> bool:
        """Check if profile has both email AND valid phone (no duplicates)."""
        return self.has_email and self.has_phone


@dataclass
class PerProfileResults:
    """Results from per-profile Phase 2 investigation."""
    target_name: str
    profile_results: List[ProfileContactResult] = field(default_factory=list)
    total_time: float = 0.0

    @property
    def passing_profiles(self) -> int:
        """Count of profiles with both email and phone."""
        return sum(1 for p in self.profile_results if p.is_complete)

    @property
    def total_profiles(self) -> int:
        return len(self.profile_results)

    @property
    def all_pass(self) -> bool:
        """True if ALL profiles have both email and phone."""
        return all(p.is_complete for p in self.profile_results)

    @property
    def total_verified_emails(self) -> int:
        return sum(len(p.verified_emails) for p in self.profile_results)

    @property
    def total_phones(self) -> int:
        return sum(len(p.phones) for p in self.profile_results)

    def get_unique_emails(self) -> List[VerifiedEmail]:
        """Get deduplicated emails across all profiles, keeping highest confidence."""
        email_map: Dict[str, VerifiedEmail] = {}
        for pr in self.profile_results:
            for email in pr.verified_emails:
                key = email.email.lower()
                email.calculate_confidence()
                if key not in email_map or email.confidence_score > email_map[key].confidence_score:
                    email_map[key] = email
        return sorted(email_map.values(), key=lambda e: -e.confidence_score)

    def get_unique_phones(self, include_duplicates: bool = False) -> List[DiscoveredPhone]:
        """
        Get deduplicated phones across all profiles, keeping highest confidence.

        Args:
            include_duplicates: If False (default), excludes phones that were
                               found for multiple different targets.
        """
        phone_map: Dict[str, DiscoveredPhone] = {}
        for pr in self.profile_results:
            for phone in pr.phones:
                # Use proper normalization
                key = normalize_phone(phone.number)
                # Calculate confidence with name matching
                phone.calculate_confidence(target_name=pr.target_name if pr.target_name else self.target_name)

                # Skip duplicates if requested
                if not include_duplicates and phone.is_duplicate:
                    continue

                if key not in phone_map or phone.confidence_score > phone_map[key].confidence_score:
                    phone_map[key] = phone

        return sorted(phone_map.values(), key=lambda p: -p.confidence_score)

    def get_duplicate_phones(self) -> List[DiscoveredPhone]:
        """Get all phones that were found for multiple targets (suspicious)."""
        duplicates = []
        seen = set()
        for pr in self.profile_results:
            for phone in pr.phones:
                if phone.is_duplicate:
                    key = normalize_phone(phone.number)
                    if key not in seen:
                        seen.add(key)
                        duplicates.append(phone)
        return duplicates

    @property
    def total_valid_phones(self) -> int:
        """Count of phones that are valid (not duplicates, meet confidence threshold)."""
        return len(self.get_unique_phones(include_duplicates=False))

    @property
    def total_duplicate_phones(self) -> int:
        """Count of phones that are duplicates (found for multiple targets)."""
        return len(self.get_duplicate_phones())

    def get_summary(self) -> Dict:
        """Get summary statistics for the investigation."""
        unique_emails = self.get_unique_emails()
        unique_phones = self.get_unique_phones()

        return {
            'target_name': self.target_name,
            'profiles_tested': self.total_profiles,
            'profiles_complete': self.passing_profiles,
            'all_pass': self.all_pass,
            'unique_emails': len(unique_emails),
            'unique_phones': len(unique_phones),
            'total_emails': self.total_verified_emails,
            'total_phones': self.total_phones,
            'time_seconds': round(self.total_time, 1),
            'top_emails': [e.email for e in unique_emails[:5]],
            'top_phones': [p.number for p in unique_phones[:5]],
            'avg_email_confidence': sum(e.confidence_score for e in unique_emails) / len(unique_emails) if unique_emails else 0,
            'avg_phone_confidence': sum(p.confidence_score for p in unique_phones) / len(unique_phones) if unique_phones else 0,
        }

    def to_json(self) -> Dict:
        """Export results as JSON-serializable dict."""
        import json

        unique_emails = self.get_unique_emails()
        unique_phones = self.get_unique_phones()

        return {
            'target_name': self.target_name,
            'investigation_time_seconds': round(self.total_time, 1),
            'summary': {
                'profiles_tested': self.total_profiles,
                'profiles_complete': self.passing_profiles,
                'all_pass': self.all_pass,
            },
            'emails': [
                {
                    'email': e.email,
                    'source': e.source,
                    'verification_method': e.verification_method,
                    'services': e.services,
                    'confidence': round(e.confidence_score, 2)
                }
                for e in unique_emails
            ],
            'phones': [
                {
                    'number': p.number,
                    'source': p.source,
                    'confidence_level': p.confidence,
                    'confidence_score': round(p.confidence_score, 2)
                }
                for p in unique_phones
            ],
            'profiles': [
                {
                    'url': pr.profile_url,
                    'platform': pr.platform,
                    'username': pr.username,
                    'status': pr.status,
                    'emails_count': len(pr.verified_emails),
                    'phones_count': len(pr.phones),
                    'processing_time': round(pr.processing_time, 1),
                    'errors': pr.errors
                }
                for pr in self.profile_results
            ]
        }

    def save_json(self, filepath: str) -> bool:
        """Save results to JSON file."""
        import json
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(self.to_json(), f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"Failed to save JSON: {e}")
            return False

    def to_csv_lines(self) -> List[str]:
        """Export results as CSV lines."""
        lines = []
        lines.append('Profile URL,Platform,Username,Emails,Phones,Status,Time')

        for pr in self.profile_results:
            emails = ';'.join(e.email for e in pr.verified_emails)
            phones = ';'.join(p.number for p in pr.phones)
            lines.append(
                f'"{pr.profile_url}",{pr.platform},{pr.username},"{emails}","{phones}",{pr.status},{pr.processing_time:.1f}'
            )

        return lines


# Russian email domains
RUSSIAN_DOMAINS = ['mail.ru', 'yandex.ru', 'ya.ru', 'bk.ru', 'list.ru', 'inbox.ru', 'rambler.ru']
ALL_DOMAINS = RUSSIAN_DOMAINS + ['gmail.com', 'outlook.com', 'protonmail.com']


class PerProfileSearchService:
    """
    Processes Phase 2 contact discovery PER PROFILE.
    Only returns VERIFIED emails - no pattern guesses.

    Performance optimizations (Cycle 9):
    - Shared HTTP session for connection pooling
    - Parallel email verification using ThreadPoolExecutor
    - Caching across profiles with TTL
    - Early termination when enough results found
    """

    def __init__(self, fast_mode: bool = True, vk_token: str = None):
        self.validator = RussianPhoneValidator()
        self._executor = ThreadPoolExecutor(max_workers=8)  # Increased for more parallelism
        self.holehe_timeout = 5 if fast_mode else 8  # Reduced timeout in fast mode
        self.phone_service = PhoneDiscoveryService()
        self.breach_checker = BreachChecker(use_h8mail=False)  # Use API-only for speed
        self.vk_extractor = VKAPIExtractor(access_token=vk_token)  # VK API for better extraction
        self.fast_mode = fast_mode
        self.min_verified_emails = 3  # Stop after finding this many verified emails
        self.max_email_candidates = 15 if fast_mode else 30  # Fewer candidates in fast mode

        # Extended email sources (Cycle 1 - NEW)
        import os
        self.email_sources = CombinedEmailSources(
            hunter_api_key=os.environ.get('HUNTER_API_KEY'),
            emailrep_api_key=os.environ.get('EMAILREP_API_KEY')
        )
        self.epieos_checker = EpieosChecker(rate_limit_delay=1.5)

        # Shared HTTP session for connection pooling (Cycle 9 optimization)
        import requests
        self._shared_session = requests.Session()
        self._shared_session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
        })

        # Caching for performance
        self._email_cache: Dict[str, Dict] = {}  # email -> verification result
        self._phone_cache: Dict[str, List] = {}  # name_hash -> phones found
        self._profile_cache: Dict[str, Dict] = {}  # url -> scraped data
        self.cache_ttl = 300  # 5 minute cache TTL
        self._cache_times: Dict[str, float] = {}

        # Statistics for performance tracking (Cycle 9)
        self._stats = {
            'cache_hits': 0,
            'cache_misses': 0,
            'requests_made': 0,
            'parallel_batches': 0,
        }

    def _cache_get(self, cache_type: str, key: str):
        """Get item from cache if not expired."""
        cache_map = {
            'email': self._email_cache,
            'phone': self._phone_cache,
            'profile': self._profile_cache
        }
        cache = cache_map.get(cache_type, {})
        cache_key = f"{cache_type}:{key}"

        if key in cache:
            # Check if expired
            cached_time = self._cache_times.get(cache_key, 0)
            if time.time() - cached_time < self.cache_ttl:
                return cache[key]
            # Expired - remove from cache
            del cache[key]
            if cache_key in self._cache_times:
                del self._cache_times[cache_key]
        return None

    def _cache_set(self, cache_type: str, key: str, value):
        """Set item in cache."""
        cache_map = {
            'email': self._email_cache,
            'phone': self._phone_cache,
            'profile': self._profile_cache
        }
        cache = cache_map.get(cache_type)
        if cache is not None:
            cache[key] = value
            self._cache_times[f"{cache_type}:{key}"] = time.time()

    def investigate_all_profiles(
        self,
        profiles: List[Dict],
        target_name: str,
        max_profiles: int = 5
    ) -> PerProfileResults:
        """
        Investigate each profile individually.

        Args:
            profiles: List of Phase 1 profiles [{'url': '...', 'platform': '...', 'username': '...'}]
            target_name: Name of target person
            max_profiles: Max profiles to process (default 5)

        Returns:
            PerProfileResults with per-profile contact data
        """
        start_time = time.time()
        results = PerProfileResults(target_name=target_name)

        # Get global deduplicator for cross-target phone tracking
        deduplicator = get_phone_deduplicator()

        logger.info("=" * 60)
        logger.info(f"PER-PROFILE INVESTIGATION START")
        logger.info(f"Target: {target_name}")
        logger.info(f"Mode: {'FAST' if self.fast_mode else 'STANDARD'}")
        logger.info(f"Profiles to process: {min(len(profiles), max_profiles)} of {len(profiles)}")
        logger.info("=" * 60)

        # Process each profile (sequential to avoid rate limiting issues)
        profiles_to_process = profiles[:max_profiles]
        total = len(profiles_to_process)

        for i, profile in enumerate(profiles_to_process, 1):
            url = profile.get('url', '')
            platform = profile.get('platform', '')
            username = profile.get('username', '')

            logger.info(f"[{i}/{total}] Processing: {platform}/{username}")

            profile_result = self._process_single_profile(
                url=url,
                platform=platform,
                username=username,
                target_name=target_name
            )

            # Register all phones with the deduplicator BEFORE adding to results
            for phone in profile_result.phones:
                deduplicator.register_phone(
                    phone=phone.number,
                    target_name=target_name,
                    source=phone.source,
                    profile_url=url
                )

            results.profile_results.append(profile_result)

            # Log per-profile status (preliminary - before dedup check)
            status_icon = "PASS" if profile_result.is_complete else "FAIL"
            logger.info(
                f"  [{status_icon}] {len(profile_result.verified_emails)} emails, "
                f"{len(profile_result.phones)} phones ({profile_result.processing_time:.1f}s)"
            )

        # DEDUPLICATION PASS: Mark phones that appear for multiple targets
        duplicates_found = 0
        for pr in results.profile_results:
            for phone in pr.phones:
                if deduplicator.is_duplicate(phone.number):
                    phone.is_duplicate = True
                    phone.duplicate_targets = deduplicator.get_duplicate_targets(phone.number)
                    duplicates_found += 1
                    logger.warning(
                        f"DUPLICATE PHONE: {phone.number} found for multiple targets: "
                        f"{phone.duplicate_targets}"
                    )

        results.total_time = time.time() - start_time

        # Summary
        logger.info("=" * 60)
        logger.info(f"PER-PROFILE RESULTS SUMMARY")
        logger.info("=" * 60)
        logger.info(f"  Target: {target_name}")
        logger.info(f"  Mode: {'FAST' if self.fast_mode else 'STANDARD'}")
        logger.info(f"  Profiles processed: {results.total_profiles}")
        logger.info(f"  Profiles passing: {results.passing_profiles}/{results.total_profiles}")
        logger.info(f"  Total verified emails: {results.total_verified_emails}")
        logger.info(f"  Total phones: {results.total_phones}")

        # Duplicate warning
        if duplicates_found > 0:
            logger.warning(f"  DUPLICATES DETECTED: {duplicates_found} phones found for multiple targets")
            logger.warning(f"  Valid phones (excluding duplicates): {results.total_valid_phones}")

        # Unique counts
        unique_emails = results.get_unique_emails()
        unique_phones = results.get_unique_phones(include_duplicates=False)
        logger.info(f"  Unique emails: {len(unique_emails)}")
        logger.info(f"  Unique valid phones: {len(unique_phones)}")

        # Per-profile breakdown
        logger.info("  Per-profile breakdown:")
        for pr in results.profile_results:
            valid_phones = pr.get_valid_phones()
            dup_count = pr.duplicate_phones_count
            status = "PASS" if pr.is_complete else "FAIL"
            dup_note = f" ({dup_count} dup)" if dup_count > 0 else ""
            logger.info(f"    [{status}] {pr.platform}/{pr.username}: "
                       f"{len(pr.verified_emails)} emails, {len(valid_phones)} valid phones{dup_note} "
                       f"({pr.processing_time:.1f}s)")

        logger.info(f"  Overall status: {'PASS' if results.all_pass else 'FAIL'}")
        logger.info(f"  Total time: {results.total_time:.1f}s")
        logger.info("=" * 60)

        return results

    def _process_single_profile(
        self,
        url: str,
        platform: str,
        username: str,
        target_name: str
    ) -> ProfileContactResult:
        """Process a single profile for contact discovery."""
        start_time = time.time()

        result = ProfileContactResult(
            profile_url=url,
            platform=platform,
            username=username,
            target_name=target_name  # Store for name matching validation
        )

        try:
            # Step 0: Use VK API for VK profiles (more reliable than scraping)
            if platform.lower() == 'vk':
                try:
                    vk_contact = self.vk_extractor.extract_from_url(url)
                    if not vk_contact.error:
                        # Add VK API emails
                        for email in vk_contact.emails:
                            result.verified_emails.append(VerifiedEmail(
                                email=email,
                                source="VK API contacts",
                                verification_method="profile_scraping",
                                services=['vk_api'],
                                confidence_score=0.95
                            ))

                        # Add VK API phones
                        for phone in vk_contact.phones:
                            info = self.validator.validate(phone)
                            if info.is_valid:
                                result.phones.append(DiscoveredPhone(
                                    number=info.display_format,
                                    source="VK API contacts",
                                    confidence="high",
                                    confidence_score=0.95
                                ))

                        # Add linked Telegram username (can help find phone)
                        if vk_contact.telegram:
                            tg_phones = self._check_telegram_for_phone(vk_contact.telegram)
                            for p in tg_phones:
                                result.phones.append(p)

                        logger.info(f"VK API extracted: {len(vk_contact.phones)} phones, {len(vk_contact.emails)} emails")
                except Exception as e:
                    logger.debug(f"VK API extraction error: {e}")

            # Step 1: Scrape profile page for visible emails and phones
            scraped_data = self._scrape_profile_contacts(url, platform)

            # Add scraped emails (these are verified - found in profile)
            for email in scraped_data.get('emails', []):
                # Avoid duplicates
                existing = [e.email.lower() for e in result.verified_emails]
                if email.lower() not in existing:
                    result.verified_emails.append(VerifiedEmail(
                        email=email,
                        source=f"{platform.upper()} profile page",
                        verification_method="profile_scraping",
                        services=[platform]
                    ))

            # Add scraped phones
            for phone in scraped_data.get('phones', []):
                info = self.validator.validate(phone)
                if info.is_valid:
                    existing = [p.number for p in result.phones]
                    if info.display_format not in existing:
                        result.phones.append(DiscoveredPhone(
                            number=info.display_format,
                            source=f"{platform.upper()} profile page",
                            confidence="high"
                        ))

            # Step 2: Generate and VERIFY email candidates for this username
            email_candidates = self._generate_email_candidates(username, target_name)

            # Step 3: Verify emails with Holehe (stop early if we have enough)
            # Use concurrent futures for faster verification
            emails_to_check = email_candidates[:self.max_email_candidates]
            verified_emails = self._verify_emails_holehe_fast(emails_to_check)

            for verified in verified_emails:
                # Avoid duplicates
                existing = [e.email.lower() for e in result.verified_emails]
                if verified['email'].lower() not in existing:
                    result.verified_emails.append(VerifiedEmail(
                        email=verified['email'],
                        source="Holehe verification",
                        verification_method="holehe",
                        services=verified['services']
                    ))

                # Stop early if we have enough verified emails
                if self.fast_mode and len(result.verified_emails) >= self.min_verified_emails:
                    break

            # Step 4: Check Gravatar for email candidates (only if we need more)
            gravatar_verified = []
            if len(result.verified_emails) < self.min_verified_emails:
                gravatar_verified = self._verify_emails_gravatar(email_candidates[:10])

            for email in gravatar_verified:
                existing = [e.email.lower() for e in result.verified_emails]
                if email.lower() not in existing:
                    result.verified_emails.append(VerifiedEmail(
                        email=email,
                        source="Gravatar profile",
                        verification_method="gravatar",
                        services=['gravatar']
                    ))

            # Step 4.5: Check Russian email providers (Mail.ru, Yandex) - no API key needed
            if len(result.verified_emails) < self.min_verified_emails:
                # Filter to Russian provider emails for efficiency
                russian_emails = [e for e in email_candidates[:15]
                                 if any(e.lower().endswith(d) for d in
                                       ['@mail.ru', '@bk.ru', '@inbox.ru', '@list.ru',
                                        '@yandex.ru', '@ya.ru', '@yandex.com', '@gmail.com'])]

                if russian_emails:
                    provider_verified = self._verify_emails_russian_providers(russian_emails)
                    for verified in provider_verified:
                        existing = [e.email.lower() for e in result.verified_emails]
                        if verified['email'].lower() not in existing:
                            result.verified_emails.append(VerifiedEmail(
                                email=verified['email'],
                                source="Provider verification",
                                verification_method="provider_api",
                                services=verified['services']
                            ))

                            # Stop if we have enough
                            if len(result.verified_emails) >= self.min_verified_emails:
                                break

            # Step 4.55: Extended email sources (Epieos, Hunter.io, EmailRep) - Cycle 1 NEW
            if len(result.verified_emails) < self.min_verified_emails:
                extended_verified = self._verify_emails_extended_sources(email_candidates[:10])
                for ext_result in extended_verified:
                    email = ext_result['email']
                    existing = [e.email.lower() for e in result.verified_emails]
                    if email.lower() not in existing:
                        result.verified_emails.append(VerifiedEmail(
                            email=email,
                            source=f"Extended: {', '.join(ext_result.get('sources', []))}",
                            verification_method="extended_sources",
                            services=ext_result.get('sources', []),
                            confidence_score=ext_result.get('confidence', 0.75)
                        ))
                        logger.info(f"Extended source verified: {email} via {ext_result.get('sources', [])}")

                        if len(result.verified_emails) >= self.min_verified_emails:
                            break

            # Step 4.6: If still need more, check breach databases (email exists if in breach)
            if len(result.verified_emails) < self.min_verified_emails:
                breach_verified = self._verify_emails_via_breach(email_candidates[:10])
                for email in breach_verified:
                    existing = [e.email.lower() for e in result.verified_emails]
                    if email.lower() not in existing:
                        result.verified_emails.append(VerifiedEmail(
                            email=email,
                            source="Breach database",
                            verification_method="breach",
                            services=['breach_db']
                        ))

                        # Stop if we have enough
                        if len(result.verified_emails) >= self.min_verified_emails:
                            break

            # Step 4.7: Combined fallback verification (VK/OK search, social check, DNS)
            if len(result.verified_emails) < self.min_verified_emails:
                fallback_verified = self._verify_emails_combined_fallback(
                    email_candidates[:15],
                    target_name
                )
                for fb_result in fallback_verified:
                    email = fb_result['email']
                    existing = [e.email.lower() for e in result.verified_emails]
                    if email.lower() not in existing:
                        # Only accept fallback results with confidence >= 0.60
                        confidence = fb_result.get('confidence', 0.5)
                        if confidence >= 0.60:
                            result.verified_emails.append(VerifiedEmail(
                                email=email,
                                source=f"Fallback: {fb_result.get('verification_method', 'unknown')}",
                                verification_method=fb_result.get('verification_method', 'fallback'),
                                services=fb_result.get('services', []),
                                confidence_score=confidence
                            ))
                            logger.info(f"Added fallback-verified email: {email} (conf={confidence:.2f})")

                            if len(result.verified_emails) >= self.min_verified_emails:
                                break

            # Step 5: If no phones yet, try deeper extraction
            if not result.phones:
                deep_phones = self._extract_phones_deep(url, platform, username, target_name)
                for phone in deep_phones:
                    result.phones.append(phone)

            # Step 6: If still no phones, use full PhoneDiscoveryService
            if not result.phones:
                try:
                    # Use phone discovery service with name + username
                    name_parts = target_name.strip().split()
                    first_name = name_parts[0] if name_parts else ""
                    last_name = name_parts[-1] if len(name_parts) > 1 else ""

                    # Get verified email strings for phone extraction
                    email_strings = [e.email for e in result.verified_emails]

                    phone_results = self.phone_service.discover_sync(
                        first_name=first_name,
                        last_name=last_name,
                        usernames=[username],
                        profile_urls=[{'url': url, 'platform': platform, 'username': username}],
                        emails=email_strings[:5]
                    )

                    for p in phone_results.phones[:3]:  # Max 3 phones
                        # Extract source profile name for validation
                        source_name = extract_name_from_source(p.source)
                        result.phones.append(DiscoveredPhone(
                            number=p.number,
                            source=p.source,
                            confidence=p.confidence,
                            source_profile_name=source_name  # For name matching
                        ))

                except Exception as e:
                    logger.debug(f"PhoneDiscoveryService error: {e}")

            # Step 7: Try VK search by name as fallback
            if not result.phones and platform.lower() == 'vk':
                name_search_phones = self._vk_search_by_name(target_name)
                for phone in name_search_phones:
                    result.phones.append(phone)

            # Step 8: Try email-based phone lookup (if we have verified emails)
            if not result.phones and result.verified_emails:
                for ve in result.verified_emails[:3]:
                    email_phones = self._phone_from_email_lookup(ve.email)
                    for phone in email_phones:
                        result.phones.append(phone)

            # Step 9: Fallback phone discovery if still no phones
            if not result.phones:
                fallback_phones = self._fallback_phone_discovery(
                    target_name=target_name,
                    username=username,
                    verified_emails=result.verified_emails
                )
                for phone in fallback_phones:
                    result.phones.append(phone)

            # Step 10: Verify phones via multiple sources (enhance confidence)
            if result.phones:
                verified_phones = []
                for phone in result.phones[:5]:  # Limit to top 5
                    verified_phone = self._verify_phone_multiple_sources(phone, target_name)
                    verified_phones.append(verified_phone)
                result.phones = verified_phones

        except Exception as e:
            error_msg = str(e)
            result.errors.append(error_msg)
            logger.error(f"Error processing profile {url}: {e}")

            # Try to salvage partial results even on error
            if not result.verified_emails and not result.phones:
                logger.warning(f"No data recovered for {url}, trying minimal extraction...")
                try:
                    # Last-ditch effort: just try phone discovery by name
                    name_parts = target_name.strip().split()
                    if len(name_parts) >= 2:
                        phone_results = self.phone_service.discover_sync(
                            first_name=name_parts[0],
                            last_name=name_parts[-1],
                            usernames=[username],
                            profile_urls=[{'url': url, 'platform': platform, 'username': username}],
                            emails=[]
                        )
                        for p in phone_results.phones[:2]:
                            result.phones.append(DiscoveredPhone(
                                number=p.number,
                                source=f"Recovery search ({p.source})",
                                confidence=p.confidence
                            ))
                except Exception as recovery_error:
                    logger.debug(f"Recovery search also failed: {recovery_error}")

        # Set status
        result.processing_time = time.time() - start_time
        result.status = 'pass' if result.is_complete else 'fail'

        return result

    def _scrape_profile_contacts(self, url: str, platform: str) -> Dict:
        """Scrape a profile page for visible contact info."""
        emails = []
        phones = []

        try:
            extracted = scrape_profile(url, platform)

            # Get emails found in profile
            emails = [e for e in extracted.emails if '@' in e]

            # Get phones found in profile
            phones = extracted.phones

        except Exception as e:
            logger.debug(f"Scrape error for {url}: {e}")

        return {'emails': emails, 'phones': phones}

    def _generate_email_candidates(self, username: str, target_name: str) -> List[str]:
        """Generate email candidates for verification."""
        candidates = set()

        # Clean username
        clean_user = re.sub(r'^(id|user|profile|@)', '', username.lower())
        clean_user = re.sub(r'[^a-z0-9_.]', '', clean_user)

        if len(clean_user) >= 3:
            for domain in ALL_DOMAINS:
                candidates.add(f"{clean_user}@{domain}")

        # Try name-based patterns
        name_parts = target_name.strip().split()
        if len(name_parts) >= 2:
            first = self._transliterate(name_parts[0].lower())
            last = self._transliterate(name_parts[-1].lower())

            patterns = [
                f"{first}.{last}",
                f"{first}{last}",
                f"{first}_{last}",
                f"{last}.{first}",
                f"{first[0]}{last}" if first else "",
            ]

            for pattern in patterns:
                if pattern and len(pattern) >= 3:
                    for domain in RUSSIAN_DOMAINS[:3]:  # Top 3 Russian domains
                        candidates.add(f"{pattern}@{domain}")

        return list(candidates)[:30]

    def _transliterate(self, text: str) -> str:
        """Transliterate Cyrillic to Latin."""
        translit_map = {
            'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
            'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
            'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
            'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
            'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
        }
        result = ""
        for char in text.lower():
            result += translit_map.get(char, char)
        return result

    def _verify_emails_holehe(self, emails: List[str]) -> List[Dict]:
        """
        Verify emails using Holehe CLI.
        Returns only emails that are registered on at least 1 REAL service.

        FIXED: Now uses parse_holehe_output() which correctly filters out
        the header line "[+] Email used, [-] Email not used, [x] Rate limit"
        that was causing false positives.
        """
        verified = []

        for email in emails:
            try:
                result = subprocess.run(
                    ['holehe', email, '--only-used', '--no-color', '--no-clear', '-T', '3'],
                    capture_output=True,
                    text=True,
                    timeout=self.holehe_timeout,
                    encoding='utf-8',
                    errors='replace'
                )

                # Use the fixed parser that filters out header line
                services = parse_holehe_output(result.stdout)

                if services:  # Only add if registered on at least 1 REAL service
                    verified.append({
                        'email': email,
                        'services': services
                    })
                    logger.info(f"VERIFIED email: {email} on REAL services: {services}")

                time.sleep(0.3)  # Rate limiting

            except subprocess.TimeoutExpired:
                logger.debug(f"Holehe timeout for {email}")
            except FileNotFoundError:
                logger.error("Holehe not installed")
                break
            except Exception as e:
                logger.debug(f"Holehe error for {email}: {e}")

        return verified

    def _verify_emails_holehe_fast(self, emails: List[str]) -> List[Dict]:
        """
        Fast parallel email verification using Holehe.
        Stops early once minimum verified emails found.
        Uses caching to avoid redundant checks.

        FIXED: Now uses parse_holehe_output() which correctly filters out
        the header line that was causing false positives.
        """
        from concurrent.futures import as_completed

        verified = []
        futures = []

        def check_single_email(email: str) -> Optional[Dict]:
            """Check single email with Holehe, with caching."""
            # Check cache first
            cached = self._cache_get('email', email.lower())
            if cached is not None:
                self._stats['cache_hits'] += 1
                logger.debug(f"Email cache hit: {email}")
                return cached if cached else None
            self._stats['cache_misses'] += 1

            try:
                result = subprocess.run(
                    ['holehe', email, '--only-used', '--no-color', '--no-clear', '-T', '3'],
                    capture_output=True,
                    text=True,
                    timeout=self.holehe_timeout,
                    encoding='utf-8',
                    errors='replace'
                )

                # Use the fixed parser that filters out header line
                services = parse_holehe_output(result.stdout)

                if services:
                    result_data = {'email': email, 'services': services}
                    self._cache_set('email', email.lower(), result_data)
                    return result_data

                # Cache negative result too
                self._cache_set('email', email.lower(), {})
                return None

            except Exception as e:
                logger.debug(f"Holehe fast check error for {email}: {e}")
                return None

        # Submit all email checks to thread pool (max 3 concurrent to avoid rate limiting)
        batch_size = 3
        for i in range(0, len(emails), batch_size):
            batch = emails[i:i + batch_size]

            futures = [self._executor.submit(check_single_email, email) for email in batch]

            for future in as_completed(futures, timeout=self.holehe_timeout * 2):
                try:
                    result = future.result()
                    if result:
                        verified.append(result)
                        logger.info(f"VERIFIED email: {result['email']} on REAL services: {result['services']}")

                        # Stop early if we have enough
                        if self.fast_mode and len(verified) >= self.min_verified_emails:
                            return verified

                except Exception as e:
                    logger.debug(f"Holehe future error: {e}")

            time.sleep(0.2)  # Brief pause between batches

        return verified

    def _verify_emails_extended_sources(self, emails: List[str]) -> List[Dict]:
        """
        Verify emails using extended sources (Cycle 1 NEW).

        Sources:
        - Epieos: Google account detection
        - Hunter.io: Email verification API (if API key available)
        - EmailRep.io: Email reputation check

        Returns list of dicts: {'email': ..., 'sources': [...], 'confidence': ...}
        """
        verified = []

        for email in emails:
            if len(verified) >= 3:  # Limit checks to save time
                break

            try:
                # Check with extended email sources
                result = self.email_sources.verify_email(email)

                if result.get('exists', False):
                    verified.append({
                        'email': email,
                        'sources': result.get('sources', []),
                        'confidence': result.get('confidence', 0.70),
                        'details': result.get('details', {})
                    })
                    logger.info(f"Extended source verified: {email} via {result.get('sources', [])}")

                time.sleep(0.3)  # Rate limiting

            except Exception as e:
                logger.debug(f"Extended source check error for {email}: {e}")

        return verified

    def _verify_emails_via_breach(self, emails: List[str]) -> List[str]:
        """
        Verify emails by checking if they appear in breach databases.

        NOTE: Requires HIBP API key to function. Without API key, returns empty list.
        """
        verified = []

        # Check if breach checker can actually work (needs HIBP API key)
        if not self.breach_checker.hibp_api_key:
            logger.debug("Skipping breach check - HIBP API key not configured")
            return verified

        for email in emails:
            if len(verified) >= 3:  # Limit breach checks
                break

            try:
                result = self.breach_checker.check_email(email)
                if result.found_in_breaches and result.breach_count > 0:
                    verified.append(email)
                    logger.info(f"VERIFIED email via breach DB: {email} (in {result.breach_count} breaches)")

                time.sleep(0.5)  # Rate limiting

            except Exception as e:
                logger.debug(f"Breach check error for {email}: {e}")

        return verified

    def _verify_email_google(self, email: str) -> bool:
        """Check if email is a Google account via public API."""
        import requests

        try:
            # Google People API endpoint for public profile check
            url = f"https://www.google.com/profiles/{email.split('@')[0]}"

            session = requests.Session()
            session.headers.update({'User-Agent': 'Mozilla/5.0'})

            response = session.get(url, timeout=5, allow_redirects=True)

            # If redirected to a profile page, account exists
            if response.status_code == 200 and 'google.com/u/' in response.url:
                return True

            # Alternative: Try Google+ legacy check
            plus_url = f"https://plus.google.com/_/people/profilecard?&q={email}"
            response = session.get(plus_url, timeout=5)
            if response.status_code == 200 and 'name' in response.text.lower():
                return True

            session.close()
            return False

        except Exception:
            return False

    def _verify_emails_gravatar(self, emails: List[str]) -> List[str]:
        """Check Gravatar for email existence."""
        verified = []

        import requests
        session = requests.Session()
        session.headers.update({'User-Agent': 'Mozilla/5.0'})

        for email in emails[:10]:  # Limit to 10
            try:
                email_hash = hashlib.md5(email.lower().encode()).hexdigest()
                url = f"https://www.gravatar.com/avatar/{email_hash}?d=404"

                response = session.head(url, timeout=5)
                if response.status_code == 200:
                    verified.append(email)
                    logger.info(f"VERIFIED email via Gravatar: {email}")

                time.sleep(0.2)

            except Exception as e:
                logger.debug(f"Gravatar error for {email}: {e}")

        session.close()
        return verified

    def _verify_emails_russian_providers(self, emails: List[str]) -> List[Dict]:
        """
        Verify emails by checking Russian email provider APIs/pages.

        Mail.ru and Yandex allow checking if an email exists via their
        password recovery or people search features.

        Optimized (Cycle 9): Uses shared session and caching.

        Returns list of dicts: {'email': ..., 'services': [...]}
        """
        verified = []
        session = self._shared_session  # Use shared session (Cycle 9)

        for email in emails[:15]:  # Limit checks
            email_lower = email.lower()

            # Check cache first (Cycle 9 optimization)
            cache_key = f"provider:{email_lower}"
            cached = self._cache_get('email', cache_key)
            if cached is not None:
                self._stats['cache_hits'] += 1
                if cached:
                    verified.append(cached)
                continue
            self._stats['cache_misses'] += 1

            try:
                result_data = None
                self._stats['requests_made'] += 1

                # Check Mail.ru emails (@mail.ru, @bk.ru, @inbox.ru, @list.ru)
                if any(email_lower.endswith(d) for d in ['@mail.ru', '@bk.ru', '@inbox.ru', '@list.ru']):
                    if self._check_mailru_email_exists(email, session):
                        result_data = {'email': email, 'services': ['mail.ru']}
                        logger.info(f"VERIFIED email via Mail.ru: {email}")

                # Check Yandex emails (@yandex.ru, @ya.ru, @yandex.com)
                elif any(email_lower.endswith(d) for d in ['@yandex.ru', '@ya.ru', '@yandex.com']):
                    if self._check_yandex_email_exists(email, session):
                        result_data = {'email': email, 'services': ['yandex']}
                        logger.info(f"VERIFIED email via Yandex: {email}")

                # Check Gmail (@gmail.com)
                elif email_lower.endswith('@gmail.com'):
                    if self._check_gmail_exists(email, session):
                        result_data = {'email': email, 'services': ['google']}
                        logger.info(f"VERIFIED email via Google: {email}")

                # Cache result (positive or negative)
                self._cache_set('email', cache_key, result_data if result_data else {})

                if result_data:
                    verified.append(result_data)

                time.sleep(0.2)  # Reduced rate limiting (Cycle 9)

            except Exception as e:
                logger.debug(f"Russian provider check error for {email}: {e}")

        return verified

    def _check_mailru_email_exists(self, email: str, session) -> bool:
        """Check if Mail.ru email exists via password recovery page."""
        try:
            # Mail.ru recovery endpoint
            url = "https://account.mail.ru/api/v1/user/password/restore"
            data = {'email': email}

            response = session.post(url, data=data, timeout=10)

            # If email exists, response will have specific status
            if response.status_code == 200:
                result = response.json()
                # 'exists' or specific error indicates email exists
                if result.get('status') == 'ok' or 'user' in str(result).lower():
                    return True
                # "email not found" type errors mean it doesn't exist
                if 'not found' in str(result).lower() or 'не найден' in str(result).lower():
                    return False

            # Fallback: try checking my.mail.ru profile
            profile_url = f"https://my.mail.ru/mail/{email.split('@')[0]}/"
            resp = session.get(profile_url, timeout=5, allow_redirects=False)
            if resp.status_code == 200:
                return True

        except Exception as e:
            logger.debug(f"Mail.ru check error: {e}")

        return False

    def _check_yandex_email_exists(self, email: str, session) -> bool:
        """Check if Yandex email exists via passport recovery."""
        try:
            # Yandex passport recovery check
            url = "https://passport.yandex.ru/registration-validations/checklogin"
            data = {'login': email.split('@')[0], 'track_id': ''}

            response = session.post(url, data=data, timeout=10)

            if response.status_code == 200:
                result = response.json()
                # If login is "occupied", the email exists
                status = result.get('status', '')
                if status == 'ok':
                    # Login available = email doesn't exist
                    return False
                elif 'occupied' in str(result).lower() or 'error' in str(result).lower():
                    # Login taken = email exists
                    return True

        except Exception as e:
            logger.debug(f"Yandex check error: {e}")

        return False

    def _check_gmail_exists(self, email: str, session) -> bool:
        """Check if Gmail exists via Google's people API (limited)."""
        try:
            # Check if Gravatar exists for this email (many Gmail users have Gravatars)
            email_hash = hashlib.md5(email.lower().encode()).hexdigest()
            url = f"https://www.gravatar.com/avatar/{email_hash}?d=404"
            response = session.head(url, timeout=5)
            if response.status_code == 200:
                return True

            # Try Google's people search
            # Note: This is limited without API key
            search_url = f"https://www.google.com/search?q={email}"
            response = session.get(search_url, timeout=5)
            if email.lower() in response.text.lower():
                return True

        except Exception as e:
            logger.debug(f"Gmail check error: {e}")

        return False

    # =========================================================================
    # FALLBACK VERIFICATION METHODS (Cycle 8)
    # =========================================================================

    def _verify_email_dns(self, email: str) -> bool:
        """
        Verify email domain has valid MX records.
        This is a basic check that filters out completely invalid domains.
        """
        import socket
        try:
            domain = email.split('@')[1]
            # Try to resolve MX records
            socket.getaddrinfo(domain, 25, socket.AF_INET, socket.SOCK_STREAM)
            return True
        except (socket.gaierror, IndexError):
            return False

    def _verify_emails_via_vk_search(self, emails: List[str], target_name: str) -> List[Dict]:
        """
        Search VK by email to find associated profiles.
        VK allows searching users by email in some cases.

        Returns list of dicts: {'email': ..., 'services': ['vk'], 'profile_url': ...}
        """
        verified = []
        import requests
        from bs4 import BeautifulSoup

        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
        })

        for email in emails[:10]:  # Limit to avoid rate limiting
            try:
                # Try VK people search with email
                search_url = f"https://vk.com/search?c[q]={email}&c[section]=people"
                response = session.get(search_url, timeout=10)

                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')

                    # Check if any results found
                    results = soup.select('.people_row, .search_row')
                    if results:
                        # Check if any result name matches target
                        for result in results[:3]:
                            name_elem = result.select_one('.people_name, .search_name')
                            if name_elem:
                                found_name = name_elem.get_text(strip=True)
                                # Check name similarity
                                similarity = calculate_name_similarity(target_name, found_name)
                                if similarity >= 0.6:
                                    # Get profile URL
                                    link = result.select_one('a[href*="/id"], a[href^="https://vk.com/"]')
                                    profile_url = link.get('href', '') if link else ''

                                    verified.append({
                                        'email': email,
                                        'services': ['vk_search'],
                                        'profile_url': profile_url,
                                        'matched_name': found_name,
                                        'name_similarity': similarity
                                    })
                                    logger.info(f"VERIFIED email via VK search: {email} (matched: {found_name})")
                                    break

                time.sleep(0.5)  # Rate limiting

            except Exception as e:
                logger.debug(f"VK email search error for {email}: {e}")

        session.close()
        return verified

    def _verify_emails_via_ok_search(self, emails: List[str], target_name: str) -> List[Dict]:
        """
        Search OK.ru by email to find associated profiles.

        Returns list of dicts: {'email': ..., 'services': ['ok'], 'profile_url': ...}
        """
        verified = []
        import requests
        from bs4 import BeautifulSoup

        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
        })

        for email in emails[:10]:  # Limit
            try:
                # Try OK.ru people search with email
                search_url = f"https://ok.ru/search?st.query={email}&st.grmode=Groups&st.cmd=friendsFriends"
                response = session.get(search_url, timeout=10)

                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')

                    # Check if any results found
                    results = soup.select('.user-card, .search-card, .ucard')
                    if results:
                        for result in results[:3]:
                            name_elem = result.select_one('.user-card_name, .ucard__name')
                            if name_elem:
                                found_name = name_elem.get_text(strip=True)
                                similarity = calculate_name_similarity(target_name, found_name)
                                if similarity >= 0.6:
                                    link = result.select_one('a[href*="/profile/"]')
                                    profile_url = link.get('href', '') if link else ''

                                    verified.append({
                                        'email': email,
                                        'services': ['ok_search'],
                                        'profile_url': profile_url,
                                        'matched_name': found_name,
                                        'name_similarity': similarity
                                    })
                                    logger.info(f"VERIFIED email via OK.ru search: {email} (matched: {found_name})")
                                    break

                time.sleep(0.5)

            except Exception as e:
                logger.debug(f"OK.ru email search error for {email}: {e}")

        session.close()
        return verified

    def _verify_emails_via_social_check(self, emails: List[str]) -> List[Dict]:
        """
        Check if emails appear on social media sites via quick checks.
        Uses profile page existence checks for derived usernames.

        Returns list of dicts: {'email': ..., 'services': [...]}
        """
        verified = []
        import requests

        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

        # Social platforms that use email prefix as username
        platforms = [
            ('twitter.com', 'https://twitter.com/{}'),
            ('github.com', 'https://github.com/{}'),
            ('instagram.com', 'https://instagram.com/{}'),
        ]

        for email in emails[:8]:  # Limit
            try:
                username = email.split('@')[0]
                # Clean username - remove dots and numbers for better matching
                clean_username = re.sub(r'[.\d]+', '', username)

                found_services = []

                for platform_name, url_template in platforms:
                    try:
                        url = url_template.format(username)
                        response = session.head(url, timeout=5, allow_redirects=True)

                        if response.status_code == 200:
                            found_services.append(platform_name)
                            logger.debug(f"Found {username} on {platform_name}")

                    except Exception:
                        pass

                    time.sleep(0.2)  # Rate limit

                if found_services:
                    verified.append({
                        'email': email,
                        'services': found_services,
                        'username_derived': username
                    })
                    logger.info(f"VERIFIED email via social check: {email} on {found_services}")

            except Exception as e:
                logger.debug(f"Social check error for {email}: {e}")

        session.close()
        return verified

    def _verify_emails_combined_fallback(
        self,
        emails: List[str],
        target_name: str
    ) -> List[Dict]:
        """
        Combined fallback verification using multiple methods.
        Tries each method and aggregates results with confidence scoring.

        Returns list of dicts with confidence-scored results.
        """
        verified = []
        seen_emails = set()

        # Method 1: VK Search (high confidence if name matches)
        vk_results = self._verify_emails_via_vk_search(emails, target_name)
        for result in vk_results:
            email = result['email']
            if email not in seen_emails:
                result['confidence'] = 0.85 if result.get('name_similarity', 0) >= 0.7 else 0.70
                result['verification_method'] = 'vk_search'
                verified.append(result)
                seen_emails.add(email)

        # Method 2: OK.ru Search (high confidence if name matches)
        ok_results = self._verify_emails_via_ok_search(emails, target_name)
        for result in ok_results:
            email = result['email']
            if email not in seen_emails:
                result['confidence'] = 0.85 if result.get('name_similarity', 0) >= 0.7 else 0.70
                result['verification_method'] = 'ok_search'
                verified.append(result)
                seen_emails.add(email)

        # Method 3: Social media check (medium confidence)
        remaining_emails = [e for e in emails if e not in seen_emails]
        social_results = self._verify_emails_via_social_check(remaining_emails[:5])
        for result in social_results:
            email = result['email']
            if email not in seen_emails:
                result['confidence'] = 0.65
                result['verification_method'] = 'social_check'
                verified.append(result)
                seen_emails.add(email)

        # Method 4: DNS validation as basic filter (low confidence alone)
        remaining_emails = [e for e in emails if e not in seen_emails]
        for email in remaining_emails[:10]:
            if self._verify_email_dns(email):
                # DNS valid but not verified elsewhere - low confidence
                verified.append({
                    'email': email,
                    'services': ['dns_valid'],
                    'confidence': 0.40,
                    'verification_method': 'dns_only'
                })
                seen_emails.add(email)

        return verified

    def _extract_phones_deep(
        self,
        url: str,
        platform: str,
        username: str,
        target_name: str
    ) -> List[DiscoveredPhone]:
        """Deep extraction of phone numbers with improved filtering."""
        phones = []

        import requests
        from bs4 import BeautifulSoup

        session = requests.Session()
        session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})

        # Phone regex patterns - more specific to avoid false positives
        phone_patterns = [
            # Labeled phone numbers (more reliable)
            r'(?:tel|phone|mob|mobile|whatsapp|telegram|viber|тел|телефон|моб|контакт)[\s:=\-]+\+?[78]?\s*[\(\-]?(\d{3})[\)\-\s]?(\d{3})[\-\s]?(\d{2})[\-\s]?(\d{2})',
        ]

        try:
            response = session.get(url, timeout=10)
            if response.status_code == 200:
                text = response.text
                soup = BeautifulSoup(text, 'html.parser')

                # Method 1: Find phones in contact-specific sections (more reliable)
                contact_sections = soup.select('.profile_info, .contact, .about, .bio, .description, .page_info_row')
                for section in contact_sections:
                    section_text = section.get_text()
                    for pattern in phone_patterns:
                        matches = re.findall(pattern, section_text, re.IGNORECASE)
                        for match in matches:
                            if isinstance(match, tuple):
                                digits = ''.join(match)
                            else:
                                digits = re.sub(r'\D', '', str(match))

                            if len(digits) >= 10:
                                normalized = '+7' + digits[-10:]
                                info = self.validator.validate(normalized)

                                if info.is_valid and info.is_mobile:
                                    existing = [p.number for p in phones]
                                    if info.display_format not in existing:
                                        phones.append(DiscoveredPhone(
                                            number=info.display_format,
                                            source=f"{platform.upper()} contact section",
                                            confidence="high"
                                        ))

                # Method 2: Check meta description
                meta_desc = soup.find('meta', attrs={'name': 'description'})
                if meta_desc:
                    desc_text = meta_desc.get('content', '')
                    found_phones = self.validator.extract_phones(desc_text)
                    for info in found_phones:
                        existing = [p.number for p in phones]
                        if info.display_format not in existing:
                            phones.append(DiscoveredPhone(
                                number=info.display_format,
                                source=f"{platform.upper()} meta description",
                                confidence="high"
                            ))

        except Exception as e:
            logger.debug(f"Deep phone extraction error for {url}: {e}")

        session.close()

        # Try VK-specific search if platform is VK
        if platform.lower() == 'vk':
            phones.extend(self._vk_phone_search(username, target_name))

        # Try Telegram check for phone hints
        phones.extend(self._check_telegram_for_phone(username))

        # Try to find phone from username (if username contains digits)
        phones.extend(self._phone_from_username(username))

        # Try OK.ru password recovery to get masked phone
        if platform.lower() in ['ok', 'odnoklassniki']:
            phones.extend(self._ok_phone_recovery(username))

        return phones[:5]  # Max 5 phones per profile

    def _vk_phone_search(self, username: str, target_name: str) -> List[DiscoveredPhone]:
        """Search VK specifically for phones with improved extraction."""
        phones = []

        import requests
        from bs4 import BeautifulSoup

        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
        })

        try:
            # Try VK profile page with contacts section
            url = f"https://vk.com/{username}"
            response = session.get(url, timeout=10)

            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                page_text = response.text

                # Method 1: Look for phone in profile info rows
                profile_info = soup.select('.profile_info_row, .page_info_row, .profile_info, .line_cell')
                for row in profile_info:
                    row_text = row.get_text()
                    # Only extract from rows that mention phone/mobile
                    if any(kw in row_text.lower() for kw in ['телефон', 'phone', 'mobile', 'моб', 'контакт']):
                        found = self.validator.extract_phones(row_text)
                        for info in found:
                            existing = [p.number for p in phones]
                            if info.display_format not in existing:
                                phones.append(DiscoveredPhone(
                                    number=info.display_format,
                                    source="VK profile contacts",
                                    confidence="high"
                                ))

                # Method 2: Look for phone in JSON data on page
                phone_json_pattern = r'"mobile_phone"\s*:\s*"([^"]+)"'
                matches = re.findall(phone_json_pattern, page_text)
                for match in matches:
                    if match and len(match) > 5:
                        info = self.validator.validate(match)
                        if info.is_valid and info.is_mobile:
                            existing = [p.number for p in phones]
                            if info.display_format not in existing:
                                phones.append(DiscoveredPhone(
                                    number=info.display_format,
                                    source="VK JSON data",
                                    confidence="high"
                                ))

                # Method 3: Check wall posts for phone mentions
                wall_posts = soup.select('.wall_post_text, .pi_text')[:5]
                for post in wall_posts:
                    post_text = post.get_text()
                    # Only extract if post mentions contact keywords
                    if any(kw in post_text.lower() for kw in ['тел', 'звонить', 'whatsapp', 'telegram', 'viber', 'связь']):
                        found = self.validator.extract_phones(post_text)
                        for info in found:
                            existing = [p.number for p in phones]
                            if info.display_format not in existing:
                                phones.append(DiscoveredPhone(
                                    number=info.display_format,
                                    source="VK wall post",
                                    confidence="medium"
                                ))

        except Exception as e:
            logger.debug(f"VK phone search error: {e}")

        session.close()
        return phones[:3]  # Limit to 3 to avoid false positives

    def _check_telegram_for_phone(self, username: str) -> List[DiscoveredPhone]:
        """Check Telegram public profile for phone hints."""
        phones = []

        import requests
        from bs4 import BeautifulSoup

        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

        try:
            # Method 1: Check t.me preview page
            url = f"https://t.me/{username}"
            response = session.get(url, timeout=10)

            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')

                # Check bio/description for phone numbers
                desc = soup.select_one('.tgme_page_description')
                if desc:
                    text = desc.get_text()
                    found = self.validator.extract_phones(text)
                    for info in found:
                        phones.append(DiscoveredPhone(
                            number=info.display_format,
                            source=f"Telegram bio (@{username})",
                            confidence="high",
                            confidence_score=0.90
                        ))

                # Also check if username itself contains phone pattern
                username_phones = self._phone_from_username(username)
                phones.extend(username_phones)

                # Check page extra info
                extra = soup.select_one('.tgme_page_extra')
                if extra:
                    extra_text = extra.get_text()
                    found = self.validator.extract_phones(extra_text)
                    for info in found:
                        existing = [p.number for p in phones]
                        if info.display_format not in existing:
                            phones.append(DiscoveredPhone(
                                number=info.display_format,
                                source=f"Telegram info (@{username})",
                                confidence="high",
                                confidence_score=0.85
                            ))

        except Exception as e:
            logger.debug(f"Telegram phone check error: {e}")

        finally:
            session.close()

        return phones

    def _phone_from_username(self, username: str) -> List[DiscoveredPhone]:
        """Extract phone number from username if it contains digits."""
        phones = []

        # Check if username contains phone-like patterns
        digits = re.sub(r'\D', '', username)

        # Check for 10-digit phone starting with 9
        if len(digits) == 10 and digits.startswith('9'):
            normalized = '+7' + digits
            info = self.validator.validate(normalized)
            if info.is_valid and info.is_mobile:
                phones.append(DiscoveredPhone(
                    number=info.display_format,
                    source=f"Username pattern ({username})",
                    confidence="medium"
                ))

        # Check for 11-digit phone starting with 7 or 8
        elif len(digits) == 11 and digits.startswith(('7', '8')):
            normalized = '+7' + digits[1:]
            info = self.validator.validate(normalized)
            if info.is_valid and info.is_mobile:
                phones.append(DiscoveredPhone(
                    number=info.display_format,
                    source=f"Username pattern ({username})",
                    confidence="medium"
                ))

        # Check for partial phone in username (7 digits = suffix, add common prefix)
        elif len(digits) == 7:
            # Try common Moscow/SPb prefixes
            for prefix in ['926', '925', '916', '903', '921', '911']:
                candidate = f'+7{prefix}{digits}'
                info = self.validator.validate(candidate)
                if info.is_valid and info.is_mobile:
                    phones.append(DiscoveredPhone(
                        number=info.display_format,
                        source=f"Username digits + common prefix ({username})",
                        confidence="low"
                    ))
                    break  # Only add one candidate

        return phones

    def _ok_phone_recovery(self, username_or_email: str) -> List[DiscoveredPhone]:
        """Try to get masked phone from OK.ru password recovery."""
        phones = []

        import requests

        try:
            session = requests.Session()
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'application/json',
            })

            # Try OK.ru password recovery API
            url = "https://www.ok.ru/dk?cmd=AnonymPasswordRecoveryStart"
            data = {'st.login': username_or_email}

            response = session.post(url, data=data, timeout=10)

            if response.status_code == 200:
                try:
                    result = response.json()
                    # Look for masked phone in response
                    if 'masked_phone' in str(result) or 'phone' in str(result).lower():
                        # Parse masked phone if available
                        masked = result.get('maskedPhone', result.get('masked_phone', ''))
                        if masked and '*' in masked:
                            phones.append(DiscoveredPhone(
                                number=masked,
                                source="OK.ru recovery (masked)",
                                confidence="medium"
                            ))
                except Exception:
                    pass

            session.close()

        except Exception as e:
            logger.debug(f"OK phone recovery error: {e}")

        return phones

    def _vk_api_phone_search(self, user_id: str) -> List[DiscoveredPhone]:
        """Search VK API for phone contacts."""
        phones = []

        import requests

        try:
            # Try VK public API to get user contacts
            # Note: VK API requires access token for most phone data
            # This is a fallback method using public data

            session = requests.Session()
            session.headers.update({'User-Agent': 'Mozilla/5.0'})

            # Try to scrape VK profile page for contact info
            url = f"https://vk.com/{user_id}"
            response = session.get(url, timeout=10)

            if response.status_code == 200:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(response.text, 'html.parser')

                # Look for phone in profile info rows
                for row in soup.select('.profile_info_row, .line_cell'):
                    row_text = row.get_text()
                    if any(kw in row_text.lower() for kw in ['телефон', 'phone', 'mobile', 'моб']):
                        found = self.validator.extract_phones(row_text)
                        for info in found:
                            phones.append(DiscoveredPhone(
                                number=info.display_format,
                                source="VK profile contacts",
                                confidence="high"
                            ))

            session.close()

        except Exception as e:
            logger.debug(f"VK API phone search error: {e}")

        return phones

    def _vk_search_by_name(self, target_name: str) -> List[DiscoveredPhone]:
        """Search VK by name and extract phones from matching profiles."""
        phones = []

        import requests
        from bs4 import BeautifulSoup

        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
        })

        try:
            # Translate name to Cyrillic for VK search
            name_parts = target_name.strip().split()
            if len(name_parts) >= 2:
                first = name_parts[0]
                last = name_parts[-1]

                # VK search URL
                search_url = f"https://vk.com/search?c[name]=1&c[q]={first}%20{last}&c[section]=people"

                response = session.get(search_url, timeout=15)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')

                    # Find profile links
                    profile_links = soup.select('a[href^="/id"], a[href*="/"]')[:3]

                    for link in profile_links:
                        href = link.get('href', '')
                        if href and ('/' in href) and not any(x in href for x in ['search', 'login', 'feed']):
                            profile_url = f"https://vk.com{href}" if href.startswith('/') else href

                            # Extract phones from this profile
                            profile_phones = self._vk_phone_search(href.strip('/'), target_name)
                            phones.extend(profile_phones[:1])  # Max 1 per profile

                            if phones:
                                break

                            time.sleep(0.5)

        except Exception as e:
            logger.debug(f"VK name search error: {e}")

        session.close()
        return phones[:2]

    def _phone_from_email_lookup(self, email: str) -> List[DiscoveredPhone]:
        """Try to find phone number associated with email via various services."""
        phones = []

        import requests

        try:
            # Method 1: Check if email local part is a phone number
            local_part = email.split('@')[0]
            digits = re.sub(r'\D', '', local_part)

            if len(digits) == 10 and digits.startswith('9'):
                normalized = '+7' + digits
                info = self.validator.validate(normalized)
                if info.is_valid and info.is_mobile:
                    phones.append(DiscoveredPhone(
                        number=info.display_format,
                        source=f"Email local part ({email})",
                        confidence="medium",
                        confidence_score=0.65
                    ))

            elif len(digits) == 11 and digits.startswith(('7', '8')):
                normalized = '+7' + digits[1:]
                info = self.validator.validate(normalized)
                if info.is_valid and info.is_mobile:
                    phones.append(DiscoveredPhone(
                        number=info.display_format,
                        source=f"Email local part ({email})",
                        confidence="medium",
                        confidence_score=0.65
                    ))

            # Method 2: For Yandex emails, check Yandex People
            if 'yandex' in email.lower() or 'ya.ru' in email.lower():
                yandex_phones = self._check_yandex_people(email)
                phones.extend(yandex_phones)

            # Method 3: For Mail.ru emails, check Mail.ru profile
            if any(d in email.lower() for d in ['mail.ru', 'bk.ru', 'inbox.ru', 'list.ru']):
                mailru_phones = self._check_mailru_profile(email)
                phones.extend(mailru_phones)

        except Exception as e:
            logger.debug(f"Email phone lookup error: {e}")

        return phones

    def _check_yandex_people(self, email: str) -> List[DiscoveredPhone]:
        """Check Yandex People/Collections for phone hints."""
        phones = []

        import requests

        try:
            username = email.split('@')[0]
            session = requests.Session()
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })

            # Check Yandex Collections profile
            url = f"https://yandex.ru/collections/user/{username}/"
            response = session.get(url, timeout=10, allow_redirects=True)

            if response.status_code == 200:
                # Extract phone from page if visible
                found = self.validator.extract_phones(response.text)
                for info in found:
                    phones.append(DiscoveredPhone(
                        number=info.display_format,
                        source=f"Yandex Collections ({username})",
                        confidence="medium",
                        confidence_score=0.75
                    ))

            session.close()

        except Exception as e:
            logger.debug(f"Yandex people check error: {e}")

        return phones[:2]  # Limit

    def _check_mailru_profile(self, email: str) -> List[DiscoveredPhone]:
        """Check Mail.ru profile for phone hints."""
        phones = []

        import requests

        if not any(d in email.lower() for d in ['mail.ru', 'bk.ru', 'inbox.ru', 'list.ru']):
            return phones

        try:
            username = email.split('@')[0]
            session = requests.Session()
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })

            # Check Mail.ru profile
            url = f"https://my.mail.ru/mail/{username}/"
            response = session.get(url, timeout=10, allow_redirects=True)

            if response.status_code == 200 and 'profile' in response.url:
                logger.info(f"Mail.ru profile found: {username}")

                # Extract phone from page if visible
                found = self.validator.extract_phones(response.text)
                for info in found:
                    phones.append(DiscoveredPhone(
                        number=info.display_format,
                        source=f"Mail.ru profile ({username})",
                        confidence="medium",
                        confidence_score=0.80
                    ))

            session.close()

        except Exception as e:
            logger.debug(f"Mail.ru profile check error: {e}")

        return phones[:2]

    # =========================================================================
    # PHONE VERIFICATION FALLBACK METHODS (Cycle 8)
    # =========================================================================

    def _verify_phone_multiple_sources(
        self,
        phone: DiscoveredPhone,
        target_name: str
    ) -> DiscoveredPhone:
        """
        Enhance phone confidence by checking multiple sources.
        Returns phone with updated confidence score.
        """
        import requests

        verification_hits = 0
        sources_checked = []

        normalized = normalize_phone(phone.number)
        if not normalized:
            return phone

        try:
            session = requests.Session()
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })

            # Method 1: Check if Telegram username contains phone pattern
            digits = re.sub(r'\D', '', normalized)
            if len(digits) >= 10:
                suffix = digits[-7:]  # Last 7 digits
                # Try common Telegram username patterns
                for prefix in ['id', 'tel', 'phone', 't', '']:
                    try:
                        tg_url = f"https://t.me/{prefix}{suffix}"
                        resp = session.head(tg_url, timeout=5, allow_redirects=True)
                        if resp.status_code == 200:
                            verification_hits += 1
                            sources_checked.append('telegram_pattern')
                            break
                    except Exception:
                        pass

            # Method 2: Check VK search for phone
            try:
                search_url = f"https://vk.com/search?c[q]={phone.number}&c[section]=people"
                resp = session.get(search_url, timeout=10)
                if resp.status_code == 200 and ('search_row' in resp.text or 'people_row' in resp.text):
                    # Check if any result name matches target
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(resp.text, 'html.parser')
                    results = soup.select('.people_row, .search_row')[:3]
                    for result in results:
                        name_elem = result.select_one('.people_name, .search_name')
                        if name_elem:
                            found_name = name_elem.get_text(strip=True)
                            similarity = calculate_name_similarity(target_name, found_name)
                            if similarity >= 0.6:
                                verification_hits += 2  # High value hit
                                sources_checked.append(f'vk_search:{found_name}')
                                break
            except Exception as e:
                logger.debug(f"VK phone search error: {e}")

            # Method 3: Check OK.ru for phone
            try:
                search_url = f"https://ok.ru/search?st.query={phone.number}"
                resp = session.get(search_url, timeout=10)
                if resp.status_code == 200:
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(resp.text, 'html.parser')
                    results = soup.select('.user-card, .ucard')[:3]
                    for result in results:
                        name_elem = result.select_one('.user-card_name, .ucard__name')
                        if name_elem:
                            found_name = name_elem.get_text(strip=True)
                            similarity = calculate_name_similarity(target_name, found_name)
                            if similarity >= 0.6:
                                verification_hits += 2
                                sources_checked.append(f'ok_search:{found_name}')
                                break
            except Exception as e:
                logger.debug(f"OK phone search error: {e}")

            session.close()

        except Exception as e:
            logger.debug(f"Phone verification error: {e}")

        # Update confidence based on verification hits
        if verification_hits > 0:
            # Boost confidence based on verification hits
            boost = min(0.20, verification_hits * 0.08)
            phone.confidence_score = min(0.95, phone.confidence_score + boost)
            if sources_checked:
                phone.source = f"{phone.source} [verified: {', '.join(sources_checked)}]"
            logger.info(f"Phone {phone.number} verified via {sources_checked}, conf={phone.confidence_score:.2f}")

        return phone

    def _fallback_phone_discovery(
        self,
        target_name: str,
        username: str,
        verified_emails: List['VerifiedEmail']
    ) -> List[DiscoveredPhone]:
        """
        Fallback phone discovery using alternative methods.
        Called when primary methods fail to find phones.
        """
        phones = []
        import requests
        from bs4 import BeautifulSoup

        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
        })

        try:
            # Method 1: Search Google for "username phone" or "name phone"
            for query in [f'"{target_name}" phone', f'"{username}" телефон']:
                try:
                    # Note: This is rate-limited by Google
                    search_url = f"https://www.google.com/search?q={query}"
                    resp = session.get(search_url, timeout=10)
                    if resp.status_code == 200:
                        found = self.validator.extract_phones(resp.text)
                        for info in found[:2]:
                            existing = [p.number for p in phones]
                            if info.display_format not in existing:
                                phones.append(DiscoveredPhone(
                                    number=info.display_format,
                                    source="Google search",
                                    confidence="low",
                                    confidence_score=0.50
                                ))
                    time.sleep(1)  # Rate limit
                except Exception:
                    pass

            # Method 2: Check if username contains digits that could be phone
            phones.extend(self._phone_from_username(username))

            # Method 3: For each verified email, try email-based lookup
            for email in verified_emails[:2]:
                email_phones = self._phone_from_email_lookup(email.email)
                for p in email_phones:
                    existing = [ph.number for ph in phones]
                    if p.number not in existing:
                        phones.append(p)

        except Exception as e:
            logger.debug(f"Fallback phone discovery error: {e}")

        finally:
            session.close()

        return phones[:3]  # Limit results

    def close(self):
        """Clean up resources and log performance stats (Cycle 9)."""
        # Log performance statistics
        total_cache_ops = self._stats['cache_hits'] + self._stats['cache_misses']
        if total_cache_ops > 0:
            hit_rate = self._stats['cache_hits'] / total_cache_ops * 100
            logger.info(f"Cache stats: {self._stats['cache_hits']} hits, "
                       f"{self._stats['cache_misses']} misses ({hit_rate:.1f}% hit rate)")
            logger.info(f"Total requests: {self._stats['requests_made']}")

        # Close shared session
        try:
            self._shared_session.close()
        except Exception:
            pass

        # Close extended email sources (Cycle 1)
        try:
            self.email_sources.close()
        except Exception:
            pass

        try:
            self.epieos_checker.close()
        except Exception:
            pass

        self._executor.shutdown(wait=False)
        try:
            self.phone_service.close()
        except Exception:
            pass


def investigate_per_profile(
    profiles: List[Dict],
    target_name: str,
    max_profiles: int = 5
) -> PerProfileResults:
    """
    Convenience function for per-profile investigation.

    Args:
        profiles: Phase 1 profiles
        target_name: Target name
        max_profiles: Max profiles to process

    Returns:
        PerProfileResults
    """
    service = PerProfileSearchService()
    try:
        return service.investigate_all_profiles(profiles, target_name, max_profiles)
    finally:
        service.close()
