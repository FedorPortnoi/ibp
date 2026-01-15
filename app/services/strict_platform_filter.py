"""
Strict Platform Filter for Russia/CIS OSINT
============================================
Filters search results to only Russia-relevant platforms.

Author: IBP Project
"""

from typing import List, Dict, Set


# Russia-focused platforms to keep
RUSSIA_PLATFORMS = {
    'vk', 'vkontakte', 'vk.com',
    'ok', 'odnoklassniki', 'ok.ru',
    'telegram', 't.me',
    'mail.ru', 'my.mail.ru',
    'yandex', 'yandex.ru',
    'rutube', 'rutube.ru',
    'pikabu', 'pikabu.ru',
    'habr', 'habr.com',
    'drive2', 'drive2.ru',
    'livejournal', 'lj',
    'instagram',
    'tiktok',
    'youtube',
    'facebook',
    'twitter', 'x.com',
    'linkedin',
    'github',
    'gitlab',
    'behance',
    'flickr',
    'snapchat',
    'discord',
    'twitch',
    'steam', 'steamcommunity',
    'reddit',
    'pinterest',
    'tumblr',
    'soundcloud',
    'spotify',
    'lastfm', 'last.fm',
    'ask.fm', 'askfm',
    '500px',
    'deviantart',
    'patreon',
    'medium',
    'quora',
    'threads',
    'mastodon',
    'clubhouse',
}

# Expanded whitelist with URL patterns
RUSSIA_URL_PATTERNS = [
    'vk.com',
    'vkontakte.ru',
    'ok.ru',
    'odnoklassniki.ru',
    't.me',
    'telegram.me',
    'telegram.org',
    'mail.ru',
    'my.mail.ru',
    'yandex.ru',
    'yandex.com',
    'rutube.ru',
    'pikabu.ru',
    'habr.com',
    'drive2.ru',
    'livejournal.com',
    'instagram.com',
    'facebook.com',
    'fb.com',
    'twitter.com',
    'x.com',
    'youtube.com',
    'youtu.be',
    'tiktok.com',
    'linkedin.com',
    'github.com',
    'gitlab.com',
    'behance.net',
    'flickr.com',
    'snapchat.com',
    'discord.com',
    'discord.gg',
    'twitch.tv',
    'steamcommunity.com',
    'reddit.com',
    'pinterest.com',
    'tumblr.com',
    'soundcloud.com',
    'spotify.com',
    'last.fm',
    'lastfm.com',
    'ask.fm',
    '500px.com',
    'deviantart.com',
    'patreon.com',
    'medium.com',
    'quora.com',
    'threads.net',
    'clubhouse.com',
]


class StrictPlatformFilter:
    """
    Filters OSINT search results to only Russia-relevant platforms.
    
    This is a STRICT filter - it only keeps platforms we explicitly whitelist.
    """
    
    def __init__(self, platforms: Set[str] = None, url_patterns: List[str] = None):
        """
        Initialize the filter.
        
        Args:
            platforms: Set of platform names to allow (uses default if None)
            url_patterns: List of URL patterns to allow (uses default if None)
        """
        self.platforms = platforms or RUSSIA_PLATFORMS
        self.url_patterns = url_patterns or RUSSIA_URL_PATTERNS
    
    def filter_results(self, results: List[Dict]) -> List[Dict]:
        """
        Filter a list of results to only Russia-relevant platforms.
        
        Args:
            results: List of result dicts with 'platform' and 'url' keys
            
        Returns:
            Filtered list containing only whitelisted platforms
        """
        filtered = []
        
        for result in results:
            if self._is_allowed(result):
                filtered.append(result)
        
        return filtered
    
    def _is_allowed(self, result: Dict) -> bool:
        """Check if a result is from an allowed platform."""
        platform = result.get('platform', '').lower()
        url = result.get('url', '').lower()
        
        # Check platform name
        for allowed in self.platforms:
            if allowed in platform:
                return True
        
        # Check URL patterns
        for pattern in self.url_patterns:
            if pattern in url:
                return True
        
        return False
    
    def get_platform_from_url(self, url: str) -> str:
        """Extract platform name from URL."""
        url_lower = url.lower()
        
        platform_mapping = {
            'vk.com': 'VK',
            'vkontakte': 'VK',
            'ok.ru': 'OK',
            'odnoklassniki': 'OK',
            't.me': 'Telegram',
            'telegram': 'Telegram',
            'mail.ru': 'Mail.ru',
            'my.mail.ru': 'Mail.ru',
            'instagram.com': 'Instagram',
            'facebook.com': 'Facebook',
            'twitter.com': 'Twitter',
            'x.com': 'X',
            'youtube.com': 'YouTube',
            'youtu.be': 'YouTube',
            'tiktok.com': 'TikTok',
            'linkedin.com': 'LinkedIn',
            'github.com': 'GitHub',
            'reddit.com': 'Reddit',
            'twitch.tv': 'Twitch',
            'discord': 'Discord',
            'steamcommunity': 'Steam',
        }
        
        for pattern, name in platform_mapping.items():
            if pattern in url_lower:
                return name
        
        return 'Unknown'


# =============================================================================
# TEST
# =============================================================================

if __name__ == "__main__":
    # Test the filter
    filter_obj = StrictPlatformFilter()
    
    test_results = [
        {'platform': 'VK', 'url': 'https://vk.com/user123'},
        {'platform': 'Instagram', 'url': 'https://instagram.com/user123'},
        {'platform': 'SomeObscureSite', 'url': 'https://obscure.site/user123'},
        {'platform': 'GitHub', 'url': 'https://github.com/user123'},
        {'platform': 'Telegram', 'url': 'https://t.me/user123'},
        {'platform': 'RandomForum', 'url': 'https://random-forum.net/profile/123'},
        {'platform': 'OK', 'url': 'https://ok.ru/profile/123456'},
    ]
    
    print("Original results:")
    for r in test_results:
        print(f"  {r['platform']}: {r['url']}")
    
    filtered = filter_obj.filter_results(test_results)
    
    print(f"\nFiltered results ({len(filtered)}/{len(test_results)}):")
    for r in filtered:
        print(f"  ✓ {r['platform']}: {r['url']}")
