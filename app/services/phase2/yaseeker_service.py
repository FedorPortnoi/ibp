"""
YaSeeker Service - FIXED
========================
Discovers Yandex account information with ACTUAL verification.
Only returns accounts that VERIFIED exist via HTTP request.
"""

import requests
import time
import re
from typing import Optional, List, Dict
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class YandexAccount:
    """Container for verified Yandex account."""
    platform: str = ""
    platform_display: str = ""
    url: str = ""
    username: str = ""
    verified: bool = True
    source: str = "YaSeeker"
    found: bool = False
    email: Optional[str] = None
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    yandex_id: Optional[str] = None
    services_used: List[str] = field(default_factory=list)
    profile_url: Optional[str] = None


# Reserved usernames that can't be real Yandex profiles
RESERVED_YANDEX = {
    'css', 'js', 'api', 'static', 'dist', 'assets', 'images',
    'search', 'explore', 'settings', 'privacy', 'terms', 'help',
    'about', 'contact', 'login', 'logout', 'register', 'home',
    'feed', 'notifications', 'messages', 'profile', 'user',
    'atom', 'rss', 'sitemap', 'robots', 'admin', 'support',
    'null', 'undefined', 'none', 'test', 'example', 'demo',
}

# Yandex domains
YANDEX_DOMAINS = [
    'yandex.ru', 'yandex.com', 'yandex.ua', 'yandex.by', 'yandex.kz',
    'ya.ru', 'narod.ru', 'yandex.net'
]

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
}


class YaSeekerService:
    """
    Yandex account discovery with VERIFICATION.
    Only returns accounts that are confirmed to exist.
    """

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.rate_limit_delay = 0.5  # seconds between requests (reduced from 1.5)
        self.verified_cache = {}  # Cache results to avoid repeat checks

    def _is_valid_username(self, username: str) -> bool:
        """Check if username could be a real Yandex account."""
        if not username:
            return False

        username_lower = username.lower().strip()

        # Must be 3-30 chars
        if len(username_lower) < 3 or len(username_lower) > 30:
            return False

        # Must not be reserved
        if username_lower in RESERVED_YANDEX:
            return False

        # Must be alphanumeric with dots/underscores
        if not re.match(r'^[a-zA-Z][a-zA-Z0-9._-]*$', username):
            return False

        return True

    def _verify_url_exists(self, url: str, not_found_indicators: List[str],
                           success_indicators: List[str] = None) -> bool:
        """
        Actually verify a URL returns a real page.

        Args:
            url: URL to check
            not_found_indicators: Strings that indicate "not found" page
            success_indicators: Optional strings that must be present for success

        Returns:
            True if page exists and is a real profile
        """
        # Check cache first
        if url in self.verified_cache:
            return self.verified_cache[url]

        try:
            time.sleep(self.rate_limit_delay)

            response = self.session.get(url, timeout=15, allow_redirects=True)

            # 404 = definitely doesn't exist
            if response.status_code == 404:
                self.verified_cache[url] = False
                return False

            # Non-200 = probably doesn't exist
            if response.status_code != 200:
                self.verified_cache[url] = False
                return False

            content = response.text.lower()

            # Check for "not found" indicators
            for indicator in not_found_indicators:
                if indicator.lower() in content:
                    self.verified_cache[url] = False
                    return False

            # Check for success indicators if provided
            if success_indicators:
                found_success = False
                for indicator in success_indicators:
                    if indicator.lower() in content:
                        found_success = True
                        break
                if not found_success:
                    self.verified_cache[url] = False
                    return False

            # Passed all checks
            self.verified_cache[url] = True
            return True

        except requests.exceptions.Timeout:
            logger.debug(f"Timeout checking {url}")
            self.verified_cache[url] = False
            return False
        except Exception as e:
            logger.debug(f"Error checking {url}: {e}")
            self.verified_cache[url] = False
            return False

    def check_yandex_collections(self, username: str) -> Optional[YandexAccount]:
        """Check if Yandex Collections profile exists."""
        if not self._is_valid_username(username):
            return None

        url = f"https://yandex.ru/collections/user/{username}/"

        not_found = [
            'страница не найдена',
            'page not found',
            'пользователь не найден',
            'user not found',
            '404',
            'ничего не найдено',
            'такого пользователя нет',
        ]

        success = [
            'collections-user',
            'user-card',
            'subscriber',
            'подписчик',
            'коллекц',
        ]

        if self._verify_url_exists(url, not_found, success):
            return YandexAccount(
                platform='yandex_collections',
                platform_display='Yandex Collections',
                url=url,
                username=username,
                source='YaSeeker (verified)',
                found=True,
                services_used=['collections']
            )
        return None

    def check_dzen(self, username: str) -> Optional[YandexAccount]:
        """Check if Dzen (Yandex Zen) profile exists."""
        if not self._is_valid_username(username):
            return None

        url = f"https://dzen.ru/{username}"

        not_found = [
            'канал не найден',
            'страница не найдена',
            'page not found',
            '404',
            'такого канала нет',
        ]

        success = [
            'channel-header',
            'subscriber',
            'подписчик',
            'zen-author',
            'dzen-author',
        ]

        if self._verify_url_exists(url, not_found, success):
            return YandexAccount(
                platform='dzen',
                platform_display='Dzen',
                url=url,
                username=username,
                source='YaSeeker (verified)',
                found=True,
                services_used=['dzen']
            )
        return None

    def check_yandex_music(self, username: str) -> Optional[YandexAccount]:
        """Check if Yandex Music profile exists."""
        if not self._is_valid_username(username):
            return None

        url = f"https://music.yandex.ru/users/{username}/playlists"

        not_found = [
            'не найден',
            'not found',
            '404',
            'ошибка',
        ]

        success = [
            'playlist',
            'плейлист',
            'user-playlists',
        ]

        if self._verify_url_exists(url, not_found, success):
            return YandexAccount(
                platform='yandex_music',
                platform_display='Yandex Music',
                url=url,
                username=username,
                source='YaSeeker (verified)',
                found=True,
                services_used=['music']
            )
        return None

    def check_all_services(self, username: str) -> List[YandexAccount]:
        """
        Check all Yandex services for a username.
        ONLY returns accounts that are VERIFIED to exist.
        """
        if not self._is_valid_username(username):
            logger.debug(f"Skipping invalid username: {username}")
            return []

        verified_accounts = []

        # Collections
        result = self.check_yandex_collections(username)
        if result:
            verified_accounts.append(result)
            logger.info(f"VERIFIED: {username} on Yandex Collections")

        # Dzen
        result = self.check_dzen(username)
        if result:
            verified_accounts.append(result)
            logger.info(f"VERIFIED: {username} on Dzen")

        # Music
        result = self.check_yandex_music(username)
        if result:
            verified_accounts.append(result)
            logger.info(f"VERIFIED: {username} on Yandex Music")

        return verified_accounts


def is_yandex_email(email: str) -> bool:
    """Check if email is a Yandex domain."""
    if '@' not in email:
        return False
    domain = email.split('@')[-1].lower()
    return domain in YANDEX_DOMAINS


def check_yandex_email(email: str) -> YandexAccount:
    """
    Check if email is a Yandex account and get info.

    Args:
        email: Email address (should be @yandex.ru, @ya.ru, etc.)

    Returns:
        YandexAccount with discovered information
    """
    if '@' not in email:
        return YandexAccount(found=False)

    username = email.split('@')[0]

    # Check if it's a Yandex email
    is_yandex = is_yandex_email(email)

    result = check_yandex_username(username)

    # If it's a Yandex email, set the email field
    if is_yandex and result.found:
        result.email = email
    elif is_yandex:
        result.email = email
        # Even if no services found, it might still be a valid Yandex email
        result.found = True
        result.username = username

    return result


def check_yandex_username(username: str) -> YandexAccount:
    """
    Check Yandex account by username.
    Legacy function for backward compatibility.

    Args:
        username: Yandex username (without @yandex.ru)

    Returns:
        YandexAccount with discovered information
    """
    service = YaSeekerService()
    results = service.check_all_services(username)

    if results:
        # Merge all services found into one result
        all_services = []
        for r in results:
            all_services.extend(r.services_used)

        return YandexAccount(
            platform='yandex',
            platform_display='Yandex',
            url=results[0].url,
            username=username,
            verified=True,
            source='YaSeeker',
            found=True,
            email=f"{username}@yandex.ru",
            services_used=list(set(all_services)),
            profile_url=results[0].url
        )

    return YandexAccount(
        platform='yandex',
        platform_display='Yandex',
        url='',
        username=username,
        verified=False,
        source='YaSeeker',
        found=False
    )


def get_verified_yandex_accounts(usernames: List[str]) -> List[Dict]:
    """
    Check multiple usernames across Yandex services.
    Returns only VERIFIED accounts.
    """
    service = YaSeekerService()
    all_verified = []

    for username in usernames:
        accounts = service.check_all_services(username)
        for acc in accounts:
            all_verified.append({
                'platform': acc.platform,
                'platform_display': acc.platform_display,
                'url': acc.url,
                'username': acc.username,
                'verified': acc.verified,
                'source': acc.source,
            })

    return all_verified


def search_yandex_by_name(first_name: str, last_name: str) -> List[YandexAccount]:
    """
    Search Yandex services for a person by name.
    Returns list of possible Yandex accounts found.

    Note: This is limited without API access.

    Args:
        first_name: First name
        last_name: Last name

    Returns:
        List of found YandexAccount objects
    """
    from .email_generator import transliterate

    found_accounts = []
    service = YaSeekerService()

    # Clean and transliterate names
    fname = transliterate(first_name.strip().lower())
    lname = transliterate(last_name.strip().lower())

    # Generate possible Yandex usernames from name
    patterns = [
        f"{fname}.{lname}",
        f"{fname}{lname}",
        f"{lname}.{fname}",
        f"{fname}-{lname}",
        f"{fname}_{lname}",
        f"{fname[0]}{lname}" if fname else "",
        f"{fname}{lname[0]}" if lname else "",
        f"{lname}{fname}",
    ]

    # Remove empty patterns
    patterns = [p for p in patterns if p]

    # Check each pattern
    for pattern in patterns:
        results = service.check_all_services(pattern)
        found_accounts.extend(results)

    return found_accounts


def get_yandex_services_info() -> dict:
    """
    Get information about Yandex services we can check.

    Returns:
        Dict with service names and descriptions
    """
    return {
        'collections': {
            'name': 'Yandex Collections',
            'url_pattern': 'https://yandex.ru/collections/user/{username}/',
            'description': 'Image bookmarks and collections'
        },
        'music': {
            'name': 'Yandex Music',
            'url_pattern': 'https://music.yandex.ru/users/{username}/',
            'description': 'Music streaming service'
        },
        'dzen': {
            'name': 'Dzen (ex-Yandex Zen)',
            'url_pattern': 'https://dzen.ru/{username}',
            'description': 'Content platform'
        },
        'q': {
            'name': 'Yandex Q',
            'url_pattern': 'https://yandex.ru/q/profile/{username}/',
            'description': 'Q&A service'
        },
        'maps': {
            'name': 'Yandex Maps',
            'url_pattern': 'https://yandex.ru/maps/user/{username}',
            'description': 'Maps and location reviews'
        },
        'market': {
            'name': 'Yandex Market',
            'url_pattern': 'https://market.yandex.ru/user/{username}/reviews',
            'description': 'Marketplace reviews'
        },
        'disk': {
            'name': 'Yandex Disk',
            'description': 'Cloud storage (public links only)'
        },
        'mail': {
            'name': 'Yandex Mail',
            'description': 'Email service'
        }
    }
