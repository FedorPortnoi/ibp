"""
Phase 2 Services - Contact Information Discovery
================================================
Services for discovering phone numbers, emails, and additional profiles.

NEW in v2.0:
- Russian Phone Validator: Validates format, identifies carrier
- Mailcat Email Discovery: Verifies emails actually exist
- VK API Extractor: API-based contact extraction from VK
"""

from app.services.phase1.transliteration import transliterate
from .email_generator import generate_email_candidates, generate_from_username
from .profile_scraper import scrape_profile, ExtractedContacts
from .gravatar_lookup import check_gravatar, GravatarProfile
from .search4faces_service import search_by_photo, search_all_databases, FaceMatch, Search4FacesResults
from .yaseeker_service import YandexAccount, YaSeekerService, get_verified_yandex_accounts
from .url_validator import (
    is_valid_profile_url,
    is_reserved_username,
    is_garbage_url,
    extract_username_from_url,
    detect_platform_from_url,
    validate_and_clean_profiles,
    RESERVED_USERNAMES,
    URL_BLACKLIST_PATTERNS,
    PROFILE_URL_PATTERNS,
)

# NEW: Enhanced services from Phase 2 research
from app.utils.phone import normalize_phone
from .russian_phone_validator import (
    RussianPhoneValidator,
    PhoneInfo,
)
from .mailcat_discovery import (
    MailcatEmailDiscovery,
    EmailDiscoveryResult,
    discover_emails_for_username,
)
from .vk_api_extractor import (
    VKAPIExtractor,
    VKContact,
    extract_vk_contacts,
    extract_vk_contacts_batch,
)

# NEW: Deep dive research services (Part 2)
from .ok_checker import (
    OKChecker,
    OKAccountInfo,
    check_ok_account,
)
from .username_intelligence import (
    UsernameIntelligence,
    UsernameAnalysis,
    analyze_username,
    get_emails_from_username,
    correlate_usernames,
)
from .breach_checker import (
    BreachChecker,
    BreachCheckResult,
    BreachInfo,
    check_email_breaches,
)
from .vk_wall_extractor import (
    VKWallExtractor,
    WallExtractionResult,
    ExtractedContact,
    extract_vk_wall_contacts,
    extract_multiple_vk_wall_contacts,
)

# NEW: Fast async email discovery
from .email_discovery import (
    EmailDiscoveryService,
    EmailDiscoveryResults,
    discover_emails,
    discover_emails_async,
    DiscoveredEmail as EmailDiscoveryEmail,
)


# NEW: Social Graph Builder for vis.js visualization
from .social_graph import (
    SocialGraphBuilder,
    SocialGraphData,
    GraphNode,
    GraphEdge,
    GraphCluster,
    build_social_graph,
    get_demo_social_graph,
    social_graph_builder,
)

__all__ = [
    # Email generation
    'generate_email_candidates',
    'transliterate',
    'generate_from_username',
    # Profile scraping
    'scrape_profile',
    'ExtractedContacts',
    # Gravatar
    'check_gravatar',
    'GravatarProfile',
    # Search4faces
    'search_by_photo',
    'search_all_databases',
    'FaceMatch',
    'Search4FacesResults',
    # YaSeeker
    'YandexAccount',
    'YaSeekerService',
    'get_verified_yandex_accounts',
    # URL Validator
    'is_valid_profile_url',
    'is_reserved_username',
    'is_garbage_url',
    'extract_username_from_url',
    'detect_platform_from_url',
    'validate_and_clean_profiles',
    'RESERVED_USERNAMES',
    'URL_BLACKLIST_PATTERNS',
    'PROFILE_URL_PATTERNS',
    # NEW: Russian Phone Validator
    'RussianPhoneValidator',
    'PhoneInfo',
    'normalize_phone',
    # NEW: Mailcat Email Discovery
    'MailcatEmailDiscovery',
    'EmailDiscoveryResult',
    'discover_emails_for_username',
    # NEW: VK API Extractor
    'VKAPIExtractor',
    'VKContact',
    'extract_vk_contacts',
    'extract_vk_contacts_batch',
    # NEW: OK Checker (Deep Dive Part 2)
    'OKChecker',
    'OKAccountInfo',
    'check_ok_account',
    # NEW: Username Intelligence (Deep Dive Part 2)
    'UsernameIntelligence',
    'UsernameAnalysis',
    'analyze_username',
    'get_emails_from_username',
    'correlate_usernames',
    # NEW: Breach Checker (Deep Dive Part 2)
    'BreachChecker',
    'BreachCheckResult',
    'BreachInfo',
    'check_email_breaches',
    # NEW: VK Wall Extractor (Deep Dive Part 2)
    'VKWallExtractor',
    'WallExtractionResult',
    'ExtractedContact',
    'extract_vk_wall_contacts',
    'extract_multiple_vk_wall_contacts',
    # NEW: Fast Async Email Discovery
    'EmailDiscoveryService',
    'EmailDiscoveryResults',
    'discover_emails',
    'discover_emails_async',
    'EmailDiscoveryEmail',
]
