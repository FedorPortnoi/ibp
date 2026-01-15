"""
IBP Services Package
====================
Central import point for all IBP services.
"""

# Username generation
try:
    from app.services.username_generator import EnhancedUsernameGenerator
except ImportError:
    try:
        from app.services.username_generator_v2 import EnhancedUsernameGenerator
    except ImportError:
        EnhancedUsernameGenerator = None

# Platform filtering
try:
    from app.services.strict_platform_filter import StrictPlatformFilter, RUSSIA_PLATFORMS
except ImportError:
    StrictPlatformFilter = None
    RUSSIA_PLATFORMS = []

# URL validation
try:
    from app.services.url_validator import ProfileValidator
except ImportError:
    ProfileValidator = None

# Face matching (Ultimate version)
try:
    from app.services.ultimate_face_matcher import UltimateFaceMatcher
except ImportError:
    UltimateFaceMatcher = None

try:
    from app.services.face_matching_integration import FaceMatchingService
except ImportError:
    FaceMatchingService = None

# Combined search
try:
    from app.services.combined_search import CombinedSearchService
except ImportError:
    CombinedSearchService = None

# Legacy components (if they exist)
try:
    from app.services.face_comparator import FaceComparator
except ImportError:
    FaceComparator = None

try:
    from app.services.profile_scraper import ProfilePhotoScraper
except ImportError:
    ProfilePhotoScraper = None

# Export all
__all__ = [
    'EnhancedUsernameGenerator',
    'StrictPlatformFilter',
    'RUSSIA_PLATFORMS',
    'ProfileValidator',
    'UltimateFaceMatcher',
    'FaceMatchingService',
    'CombinedSearchService',
    'FaceComparator',
    'ProfilePhotoScraper',
]
