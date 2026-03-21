"""
URL and Username Validator for Phase 2
======================================
Filters out garbage URLs, reserved usernames, and validates real social profiles.
"""

import logging
import re
from typing import Optional, Set, List, Dict
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# ============================================================================
# BLACKLISTS - These are NEVER real profiles/usernames
# ============================================================================

URL_BLACKLIST_PATTERNS = [
    # Asset/static files
    '/css/', '/js/', '/dist/', '/assets/', '/static/', '/img/', '/images/',
    '/fonts/', '/media/', '/scripts/', '/styles/', '/bundle/', '/chunks/',
    '/vendors/', '/node_modules/', '/build/', '/public/',

    # API/Technical endpoints
    '/api/', '/api.', '/iframe', '/embed/', '/widget/', '/oembed/',
    '/callback/', '/oauth/', '/auth/', '/webhook/', '/graphql/',

    # Auth pages
    '/login', '/logout', '/register', '/signup', '/signin', '/signout',
    '/password', '/reset', '/forgot', '/verify', '/confirm/',

    # Settings/Account pages
    '/settings', '/preferences', '/account/', '/profile/edit',
    '/notifications', '/messages/', '/inbox/', '/outbox/',

    # Legal/Info pages
    '/privacy', '/terms', '/policy', '/cookie', '/gdpr', '/regulations',
    '/legal/', '/tos/', '/eula/', '/disclaimer/', '/copyright/',
    '/help/', '/faq/', '/support/', '/contact/', '/about/',

    # Navigation pages
    '/search', '/explore', '/discover', '/feed', '/home/', '/main/',
    '/index', '/browse', '/trending', '/popular/', '/recommended/',

    # Advertising
    '/ad/', '/ads/', '/advert/', '/promo/', '/banner/', '/sponsor/',
    '/campaign/', '/marketing/',

    # Media files
    '.css', '.js', '.json', '.xml', '.png', '.jpg', '.jpeg', '.gif',
    '.svg', '.ico', '.woff', '.woff2', '.ttf', '.eot', '.map',
    '.webp', '.mp4', '.mp3', '.pdf', '.zip', '.rar',

    # Misc technical
    'iframe_api', 'player_api', 'sdk.js', 'analytics', 'tracking',
    'pixel', 'beacon', '.min.', '.bundle.', 'polyfill', 'vendor.',
]

RESERVED_USERNAMES = {
    # Technical/System
    'css', 'js', 'dist', 'api', 'static', 'assets', 'images', 'img',
    'fonts', 'media', 'scripts', 'styles', 'bundle', 'build', 'public',
    'src', 'lib', 'vendor', 'node_modules', 'packages',

    # Navigation
    'search', 'explore', 'discover', 'feed', 'home', 'main', 'index',
    'browse', 'trending', 'popular', 'recommended', 'featured',

    # Account/Auth
    'login', 'logout', 'register', 'signup', 'signin', 'signout',
    'settings', 'preferences', 'account', 'profile', 'edit', 'delete',
    'password', 'reset', 'forgot', 'verify', 'confirm', 'activate',

    # Communication
    'notifications', 'messages', 'inbox', 'outbox', 'chat', 'dm',
    'comments', 'replies', 'mentions', 'followers', 'following',

    # Legal/Info
    'privacy', 'terms', 'policy', 'cookie', 'cookiepolicy', 'gdpr',
    'regulations', 'legal', 'tos', 'eula', 'disclaimer', 'copyright',
    'help', 'faq', 'support', 'contact', 'about', 'info', 'docs',

    # Technical endpoints
    'api', 'oauth', 'auth', 'callback', 'webhook', 'graphql', 'rest',
    'iframe', 'embed', 'widget', 'oembed', 'share', 'export', 'import',
    'iframe_api', 'player_api', 'sdk',

    # Advertising/Marketing
    'ad', 'ads', 'advert', 'promo', 'banner', 'sponsor', 'campaign',
    'marketing', 'affiliate', 'partner', 'advertise',

    # Site structure
    'atom', 'rss', 'feed', 'sitemap', 'robots', 'manifest', 'sw',
    'serviceworker', 'workbox', 'offline', 'pwa',

    # VK/OK specific garbage
    'hobby', 'hobbies', 'interests', 'apps', 'games', 'music', 'video',
    'photos', 'albums', 'groups', 'communities', 'events', 'market',
    'stories', 'clips', 'reels', 'live', 'watch',

    # Generic
    'www', 'http', 'https', 'ftp', 'mailto', 'tel',
    'null', 'undefined', 'none', 'true', 'false', 'test', 'example',
    'admin', 'administrator', 'moderator', 'root', 'system', 'bot',
    'official', 'verified', 'support', 'team', 'staff', 'dev', 'developer',
}

# Valid social media profile URL patterns
PROFILE_URL_PATTERNS = {
    'vk': [
        r'^https?://(?:www\.)?vk\.com/([a-zA-Z][a-zA-Z0-9_.]{2,29})/?$',
        r'^https?://(?:www\.)?vk\.com/(id\d{1,15})/?$',
    ],
    'telegram': [
        r'^https?://(?:www\.)?t\.me/([a-zA-Z][a-zA-Z0-9_]{4,31})/?$',
        r'^https?://(?:www\.)?telegram\.me/([a-zA-Z][a-zA-Z0-9_]{4,31})/?$',
    ],
    'ok': [
        r'^https?://(?:www\.)?ok\.ru/profile/(\d+)/?$',
        r'^https?://(?:www\.)?ok\.ru/([a-zA-Z][a-zA-Z0-9_.]{2,29})/?$',
    ],
    'instagram': [
        r'^https?://(?:www\.)?instagram\.com/([a-zA-Z][a-zA-Z0-9_.]{0,29})/?$',
    ],
    'twitter': [
        r'^https?://(?:www\.)?(twitter|x)\.com/([a-zA-Z_][a-zA-Z0-9_]{0,14})/?$',
    ],
    'youtube': [
        r'^https?://(?:www\.)?youtube\.com/@([a-zA-Z0-9_.-]{3,30})/?$',
        r'^https?://(?:www\.)?youtube\.com/c/([a-zA-Z0-9_.-]{3,100})/?$',
        r'^https?://(?:www\.)?youtube\.com/channel/([a-zA-Z0-9_-]{24})/?$',
        r'^https?://(?:www\.)?youtube\.com/user/([a-zA-Z0-9_]{3,30})/?$',
    ],
    'tiktok': [
        r'^https?://(?:www\.)?tiktok\.com/@([a-zA-Z0-9_.]{2,24})/?$',
    ],
    'facebook': [
        r'^https?://(?:www\.)?facebook\.com/([a-zA-Z0-9.]{5,50})/?$',
        r'^https?://(?:www\.)?fb\.com/([a-zA-Z0-9.]{5,50})/?$',
    ],
    'linkedin': [
        r'^https?://(?:www\.)?linkedin\.com/in/([a-zA-Z0-9_-]{3,100})/?$',
    ],
}


def is_garbage_url(url: str) -> bool:
    """Check if URL contains garbage patterns (CSS, JS, navigation, etc.)."""
    if not url:
        return True

    url_lower = url.lower()

    for pattern in URL_BLACKLIST_PATTERNS:
        if pattern in url_lower:
            return True

    return False


def is_reserved_username(username: str) -> bool:
    """Check if username is a reserved/system word that can't be a real profile."""
    if not username:
        return True

    username_clean = username.lower().strip()

    # Direct match
    if username_clean in RESERVED_USERNAMES:
        return True

    # Check if starts with reserved patterns
    reserved_prefixes = ['id', 'user', 'u', 'profile', 'p']
    for prefix in reserved_prefixes:
        # "id12345" is OK (VK ID), but "id" alone is not
        if username_clean == prefix:
            return True

    return False


def extract_username_from_url(url: str, platform: str = None) -> Optional[str]:
    """Extract username portion from a social media profile URL."""
    if not url:
        return None

    url = url.strip()

    # Try platform-specific patterns first
    if platform and platform in PROFILE_URL_PATTERNS:
        for pattern in PROFILE_URL_PATTERNS[platform]:
            match = re.search(pattern, url, re.IGNORECASE)
            if match:
                # Return the last capture group (username)
                groups = match.groups()
                return groups[-1] if groups else None

    # Try all patterns
    for plat, patterns in PROFILE_URL_PATTERNS.items():
        for pattern in patterns:
            match = re.search(pattern, url, re.IGNORECASE)
            if match:
                groups = match.groups()
                return groups[-1] if groups else None

    # Fallback: simple extraction
    try:
        parsed = urlparse(url)
        path = parsed.path.strip('/')

        if '/' not in path and path:
            # Simple case: domain.com/username
            return path if len(path) >= 3 else None
        elif '/' in path:
            # Could be domain.com/profile/username
            parts = path.split('/')
            if len(parts) >= 1:
                candidate = parts[-1] or (parts[-2] if len(parts) > 1 else None)
                if candidate and len(candidate) >= 3:
                    return candidate
    except Exception as e:
        logger.debug(f"[URLValidator] Username extraction failed for '{url}': {e}")

    return None


def is_valid_profile_url(url: str, platform: str = None) -> bool:
    """
    Comprehensive check if URL is a valid social media profile.

    Returns True only if:
    1. URL is not garbage
    2. Username is not reserved
    3. URL matches known profile patterns
    4. Username length is valid (3-30 chars)
    """
    if not url:
        return False

    url = url.strip()

    # Check for garbage patterns
    if is_garbage_url(url):
        return False

    # Extract and validate username
    username = extract_username_from_url(url, platform)

    if not username:
        return False

    if is_reserved_username(username):
        return False

    # Username length check (most platforms: 3-30)
    if len(username) < 3 or len(username) > 50:
        return False

    # Must match at least one profile pattern
    for plat, patterns in PROFILE_URL_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, url, re.IGNORECASE):
                return True

    return False


def detect_platform_from_url(url: str) -> Optional[str]:
    """Detect which platform a URL belongs to."""
    if not url:
        return None

    url_lower = url.lower()

    if 'vk.com' in url_lower or 'vkontakte' in url_lower:
        return 'vk'
    elif 't.me' in url_lower or 'telegram' in url_lower:
        return 'telegram'
    elif 'ok.ru' in url_lower or 'odnoklassniki' in url_lower:
        return 'ok'
    elif 'instagram.com' in url_lower or 'instagr.am' in url_lower:
        return 'instagram'
    elif 'twitter.com' in url_lower or 'x.com' in url_lower:
        return 'twitter'
    elif 'youtube.com' in url_lower or 'youtu.be' in url_lower:
        return 'youtube'
    elif 'tiktok.com' in url_lower:
        return 'tiktok'
    elif 'facebook.com' in url_lower or 'fb.com' in url_lower:
        return 'facebook'
    elif 'linkedin.com' in url_lower:
        return 'linkedin'

    return None


def validate_and_clean_profiles(profiles: list, exclude_urls: set = None, exclude_usernames: dict = None) -> list:
    """
    Filter a list of profile dicts, removing garbage and duplicates.

    Args:
        profiles: List of {"platform": str, "url": str, "username": str, ...}
        exclude_urls: Set of URLs to exclude (e.g., Phase 1 selections)
        exclude_usernames: Dict of {platform: set(usernames)} to exclude

    Returns:
        Cleaned list with only valid, non-duplicate profiles
    """
    exclude_urls = exclude_urls or set()
    exclude_usernames = exclude_usernames or {}

    seen_urls = set()
    seen_usernames = {}  # {platform: set(usernames)}
    valid_profiles = []

    for profile in profiles:
        url = profile.get('url', '').strip()
        platform = profile.get('platform', '').lower()
        username = profile.get('username', '').strip()

        # Skip if no URL
        if not url:
            continue

        # Normalize URL for comparison
        url_normalized = url.lower().rstrip('/')

        # Skip if in exclusion set
        if url_normalized in exclude_urls:
            continue

        # Skip if already seen
        if url_normalized in seen_urls:
            continue

        # Skip if username excluded for this platform
        if platform and username:
            username_lower = username.lower()
            if platform in exclude_usernames and username_lower in exclude_usernames[platform]:
                continue
            if platform in seen_usernames and username_lower in seen_usernames[platform]:
                continue

        # Validate URL
        if not is_valid_profile_url(url, platform):
            continue

        # All checks passed - add to valid list
        valid_profiles.append(profile)

        # Track as seen
        seen_urls.add(url_normalized)
        if platform and username:
            if platform not in seen_usernames:
                seen_usernames[platform] = set()
            seen_usernames[platform].add(username.lower())

    return valid_profiles
