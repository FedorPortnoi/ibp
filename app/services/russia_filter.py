"""
Russia/CIS Platform Filter
==========================
Filters OSINT results to only show Russia-relevant platforms.

This module contains:
- Whitelist of 60+ Russia/CIS platforms
- Exclusion list for blocked/irrelevant platforms
- Filtering functions for search results

Author: IBP Project
"""

import re
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass


# =============================================================================
# RUSSIA-RELEVANT PLATFORM WHITELIST
# =============================================================================

RUSSIA_PLATFORM_WHITELIST = {
    # === PRIMARY RUSSIAN SOCIAL NETWORKS ===
    "vk": {
        "display_name": "VK (ВКонтакте)",
        "category": "Social Network",
        "priority": 1,
        "url_patterns": ["vk.com", "vkontakte.ru"],
        "icon": "💙"
    },
    "ok": {
        "display_name": "Odnoklassniki (OK)",
        "category": "Social Network",
        "priority": 1,
        "url_patterns": ["ok.ru", "odnoklassniki.ru"],
        "icon": "🟠"
    },
    "telegram": {
        "display_name": "Telegram",
        "category": "Messenger",
        "priority": 1,
        "url_patterns": ["t.me", "telegram.me", "telegram.org"],
        "icon": "✈️"
    },
    "mailru": {
        "display_name": "Mail.ru",
        "category": "Email/Portal",
        "priority": 1,
        "url_patterns": ["mail.ru", "my.mail.ru"],
        "icon": "📧"
    },
    
    # === VIDEO PLATFORMS ===
    "youtube": {
        "display_name": "YouTube",
        "category": "Video",
        "priority": 2,
        "url_patterns": ["youtube.com", "youtu.be"],
        "icon": "▶️"
    },
    "rutube": {
        "display_name": "Rutube",
        "category": "Video",
        "priority": 1,
        "url_patterns": ["rutube.ru"],
        "icon": "🎬"
    },
    "dzen": {
        "display_name": "Yandex Dzen",
        "category": "Video/Blog",
        "priority": 1,
        "url_patterns": ["dzen.ru", "zen.yandex.ru"],
        "icon": "📰"
    },
    "boosty": {
        "display_name": "Boosty",
        "category": "Creator Platform",
        "priority": 2,
        "url_patterns": ["boosty.to"],
        "icon": "💰"
    },
    "donationalerts": {
        "display_name": "DonationAlerts",
        "category": "Streaming",
        "priority": 2,
        "url_patterns": ["donationalerts.com", "donationalerts.ru"],
        "icon": "🎁"
    },
    
    # === YANDEX SERVICES ===
    "yandex": {
        "display_name": "Yandex",
        "category": "Yandex Services",
        "priority": 1,
        "url_patterns": ["yandex.ru", "yandex.com", "ya.ru"],
        "icon": "🔍"
    },
    "kinopoisk": {
        "display_name": "Kinopoisk",
        "category": "Entertainment",
        "priority": 2,
        "url_patterns": ["kinopoisk.ru"],
        "icon": "🎬"
    },
    "yandexmusic": {
        "display_name": "Yandex Music",
        "category": "Music",
        "priority": 2,
        "url_patterns": ["music.yandex.ru", "music.yandex.com"],
        "icon": "🎵"
    },
    "yandexmarket": {
        "display_name": "Yandex Market",
        "category": "E-commerce",
        "priority": 3,
        "url_patterns": ["market.yandex.ru"],
        "icon": "🛒"
    },
    
    # === CLASSIFIEDS & MARKETPLACES ===
    "avito": {
        "display_name": "Avito",
        "category": "Classifieds",
        "priority": 1,
        "url_patterns": ["avito.ru"],
        "icon": "🏷️"
    },
    "youla": {
        "display_name": "Youla",
        "category": "Classifieds",
        "priority": 2,
        "url_patterns": ["youla.ru"],
        "icon": "🏷️"
    },
    "autoru": {
        "display_name": "Auto.ru",
        "category": "Auto",
        "priority": 2,
        "url_patterns": ["auto.ru"],
        "icon": "🚗"
    },
    "drom": {
        "display_name": "Drom.ru",
        "category": "Auto",
        "priority": 2,
        "url_patterns": ["drom.ru"],
        "icon": "🚗"
    },
    "cian": {
        "display_name": "CIAN",
        "category": "Real Estate",
        "priority": 2,
        "url_patterns": ["cian.ru"],
        "icon": "🏠"
    },
    "domclick": {
        "display_name": "DomClick",
        "category": "Real Estate",
        "priority": 3,
        "url_patterns": ["domclick.ru"],
        "icon": "🏠"
    },
    "wildberries": {
        "display_name": "Wildberries",
        "category": "E-commerce",
        "priority": 3,
        "url_patterns": ["wildberries.ru"],
        "icon": "🛒"
    },
    "ozon": {
        "display_name": "Ozon",
        "category": "E-commerce",
        "priority": 3,
        "url_patterns": ["ozon.ru"],
        "icon": "🛒"
    },
    
    # === PROFESSIONAL & TECH ===
    "habr": {
        "display_name": "Habr",
        "category": "Tech Community",
        "priority": 1,
        "url_patterns": ["habr.com", "habrahabr.ru"],
        "icon": "💻"
    },
    "headhunter": {
        "display_name": "HeadHunter (hh.ru)",
        "category": "Jobs",
        "priority": 1,
        "url_patterns": ["hh.ru", "headhunter.ru"],
        "icon": "💼"
    },
    "superjob": {
        "display_name": "SuperJob",
        "category": "Jobs",
        "priority": 2,
        "url_patterns": ["superjob.ru"],
        "icon": "💼"
    },
    "flru": {
        "display_name": "FL.ru",
        "category": "Freelance",
        "priority": 2,
        "url_patterns": ["fl.ru"],
        "icon": "💼"
    },
    "freelansim": {
        "display_name": "Freelansim",
        "category": "Freelance",
        "priority": 3,
        "url_patterns": ["freelansim.ru"],
        "icon": "💼"
    },
    "kwork": {
        "display_name": "Kwork",
        "category": "Freelance",
        "priority": 3,
        "url_patterns": ["kwork.ru"],
        "icon": "💼"
    },
    
    # === FORUMS & COMMUNITIES ===
    "pikabu": {
        "display_name": "Pikabu",
        "category": "Forum",
        "priority": 1,
        "url_patterns": ["pikabu.ru"],
        "icon": "📱"
    },
    "4pda": {
        "display_name": "4PDA",
        "category": "Tech Forum",
        "priority": 2,
        "url_patterns": ["4pda.ru", "4pda.to"],
        "icon": "📱"
    },
    "ixbt": {
        "display_name": "iXBT",
        "category": "Tech Forum",
        "priority": 3,
        "url_patterns": ["ixbt.com", "forum.ixbt.com"],
        "icon": "💻"
    },
    "drive2": {
        "display_name": "Drive2",
        "category": "Auto Community",
        "priority": 2,
        "url_patterns": ["drive2.ru", "drive2.com"],
        "icon": "🚗"
    },
    
    # === SPORTS ===
    "championat": {
        "display_name": "Championat",
        "category": "Sports",
        "priority": 2,
        "url_patterns": ["championat.com"],
        "icon": "⚽"
    },
    "sportsru": {
        "display_name": "Sports.ru",
        "category": "Sports",
        "priority": 2,
        "url_patterns": ["sports.ru"],
        "icon": "⚽"
    },
    
    # === GAMING ===
    "steam": {
        "display_name": "Steam",
        "category": "Gaming",
        "priority": 2,
        "url_patterns": ["steamcommunity.com", "store.steampowered.com"],
        "icon": "🎮"
    },
    "vkplay": {
        "display_name": "VK Play",
        "category": "Gaming",
        "priority": 2,
        "url_patterns": ["vkplay.ru", "vkplay.live"],
        "icon": "🎮"
    },
    "twitch": {
        "display_name": "Twitch",
        "category": "Streaming",
        "priority": 3,
        "url_patterns": ["twitch.tv"],
        "icon": "🎮"
    },
    "goodgame": {
        "display_name": "GoodGame",
        "category": "Streaming",
        "priority": 3,
        "url_patterns": ["goodgame.ru"],
        "icon": "🎮"
    },
    
    # === DEVELOPER PLATFORMS ===
    "github": {
        "display_name": "GitHub",
        "category": "Development",
        "priority": 2,
        "url_patterns": ["github.com"],
        "icon": "🐙"
    },
    "gitlab": {
        "display_name": "GitLab",
        "category": "Development",
        "priority": 3,
        "url_patterns": ["gitlab.com"],
        "icon": "🦊"
    },
    
    # === MUSIC ===
    "soundcloud": {
        "display_name": "SoundCloud",
        "category": "Music",
        "priority": 3,
        "url_patterns": ["soundcloud.com"],
        "icon": "🎵"
    },
    "lastfm": {
        "display_name": "Last.fm",
        "category": "Music",
        "priority": 3,
        "url_patterns": ["last.fm"],
        "icon": "🎵"
    },
    "spotify": {
        "display_name": "Spotify",
        "category": "Music",
        "priority": 3,
        "url_patterns": ["open.spotify.com"],
        "icon": "🎵"
    },
    
    # === BLOGS ===
    "livejournal": {
        "display_name": "LiveJournal",
        "category": "Blog",
        "priority": 2,
        "url_patterns": ["livejournal.com"],
        "icon": "📝"
    },
    "diary": {
        "display_name": "Diary.ru",
        "category": "Blog",
        "priority": 3,
        "url_patterns": ["diary.ru"],
        "icon": "📝"
    },
    "liveinternet": {
        "display_name": "LiveInternet",
        "category": "Blog",
        "priority": 3,
        "url_patterns": ["liveinternet.ru"],
        "icon": "📝"
    },
    
    # === REVIEWS ===
    "irecommend": {
        "display_name": "iRecommend",
        "category": "Reviews",
        "priority": 3,
        "url_patterns": ["irecommend.ru"],
        "icon": "⭐"
    },
    "otzovik": {
        "display_name": "Otzovik",
        "category": "Reviews",
        "priority": 3,
        "url_patterns": ["otzovik.com"],
        "icon": "⭐"
    },
    
    # === DATING ===
    "mamba": {
        "display_name": "Mamba",
        "category": "Dating",
        "priority": 3,
        "url_patterns": ["mamba.ru"],
        "icon": "💕"
    },
    "badoo": {
        "display_name": "Badoo",
        "category": "Dating",
        "priority": 3,
        "url_patterns": ["badoo.com"],
        "icon": "💕"
    },
    
    # === COMMUNICATION ===
    "discord": {
        "display_name": "Discord",
        "category": "Communication",
        "priority": 3,
        "url_patterns": ["discord.com", "discord.gg", "discordapp.com"],
        "icon": "💬"
    },
    "skype": {
        "display_name": "Skype",
        "category": "Communication",
        "priority": 3,
        "url_patterns": ["skype.com"],
        "icon": "💬"
    },
    
    # === CIS REGIONAL ===
    "nurkz": {
        "display_name": "Nur.kz (Kazakhstan)",
        "category": "CIS Regional",
        "priority": 3,
        "url_patterns": ["nur.kz"],
        "icon": "🇰🇿"
    },
    "olxua": {
        "display_name": "OLX Ukraine",
        "category": "CIS Regional",
        "priority": 3,
        "url_patterns": ["olx.ua"],
        "icon": "🇺🇦"
    },
    "kolesa": {
        "display_name": "Kolesa.kz",
        "category": "CIS Regional",
        "priority": 3,
        "url_patterns": ["kolesa.kz"],
        "icon": "🇰🇿"
    },
}


# =============================================================================
# EXCLUDED PLATFORMS
# =============================================================================

EXCLUDED_PLATFORMS = {
    # === BLOCKED IN RUSSIA ===
    "facebook.com", "fb.com", "facebook",
    "instagram.com", "instagram",
    "twitter.com", "x.com", "twitter",
    "linkedin.com", "linkedin",
    
    # === ADULT / INAPPROPRIATE ===
    "adultfriendfinder", "aff.com",
    "chaturbate", "chaturbate.com",
    "pornhub", "pornhub.com",
    "xvideos", "xvideos.com",
    "xnxx", "xnxx.com",
    "onlyfans", "onlyfans.com",
    "fansly", "fansly.com",
    "stripchat", "stripchat.com",
    "xhamster", "xhamster.com",
    "cam4", "cam4.com",
    "bongacams", "bongacams.com",
    "myfreecams", "myfreecams.com",
    
    # === KIDS/TEEN PLATFORMS (irrelevant for OSINT) ===
    "roblox", "roblox.com",
    "minecraft", "minecraft.net",
    "fortnite", "fortnite.com",
    "pokemon", "pokemonshowdown",
    "scratch", "scratch.mit.edu",
    "gaiaonline", "gaiaonline.com",
    "amino", "aminoapps.com",
    "moviestarplanet",
    
    # === FANDOM / WIKI (too generic) ===
    "fandom.com", "fandom",
    "wikia.com", "wikia",
    "wiki",  # Generic wiki matches
    "fimfiction",  # Brony stuff
    "archiveofourown", "ao3",  # Fanfiction
    "wattpad",
    
    # === US-ONLY / IRRELEVANT ===
    "nextdoor", "nextdoor.com",
    "yelp", "yelp.com",
    "craigslist", "craigslist.org",
    "indeed", "indeed.com",
    "glassdoor", "glassdoor.com",
    "zillow", "zillow.com",
    "venmo", "venmo.com",
    "cashapp",
    
    # === LINK AGGREGATORS (not real profiles) ===
    "about.me",
    "linktree", "linktr.ee",
    "carrd", "carrd.co",
    "bio.link",
    "beacons.ai",
    "allmylinks",
    
    # === CRYPTO/NFT (usually not useful) ===
    "opensea", "opensea.io",
    "rarible", "rarible.com",
    
    # === RANDOM IRRELEVANT ===
    "buzzfeed",
    "instructables",
    "slideshare",
    "scribd",
    "issuu",
    "trello",  # Work tool, not social
    "buymeacoffee",
    "ko-fi",
    "patreon",  # Usually anonymous
}


# =============================================================================
# CATEGORY PRIORITY (for sorting results)
# =============================================================================

CATEGORY_PRIORITY = [
    "Social Network",      # VK, OK - most important
    "Messenger",           # Telegram
    "Email/Portal",        # Mail.ru
    "Video",               # YouTube, Rutube
    "Tech Community",      # Habr
    "Jobs",                # HH, SuperJob
    "Forum",               # Pikabu, 4PDA
    "Gaming",              # Steam, VK Play
    "Auto",                # Auto.ru, Drive2
    "Classifieds",         # Avito
    "Development",         # GitHub
    "Streaming",           # Twitch
    "Music",               # Spotify, Yandex Music
    "Blog",                # LiveJournal
    "E-commerce",          # Wildberries, Ozon
    "Real Estate",         # CIAN
    "Entertainment",       # Kinopoisk
    "Reviews",             # Otzovik
    "Dating",              # Mamba
    "Communication",       # Discord
    "CIS Regional",        # Kazakhstan, Ukraine
    "Yandex Services",
    "Creator Platform",
    "Freelance",
    "Sports",
    "Other",
]


# =============================================================================
# FILTER FUNCTIONS
# =============================================================================

def detect_platform(url: str, site_name: str = "") -> Tuple[str, Dict]:
    """
    Detect which platform a URL belongs to.
    
    Args:
        url: The profile URL
        site_name: Optional site name from search tool
        
    Returns:
        Tuple of (platform_key, platform_info) or (None, None) if not found
    """
    url_lower = url.lower()
    
    # Check against whitelist patterns
    for platform_key, platform_info in RUSSIA_PLATFORM_WHITELIST.items():
        for pattern in platform_info["url_patterns"]:
            if pattern in url_lower:
                return (platform_key, platform_info)
    
    # Check for any .ru domain (auto-include)
    ru_match = re.search(r'(?:https?://)?(?:www\.)?([a-z0-9-]+\.ru)', url_lower)
    if ru_match:
        domain = ru_match.group(1)
        return ("ru_generic", {
            "display_name": domain,
            "category": "Russian Website",
            "priority": 4,
            "url_patterns": [domain],
            "icon": "🇷🇺"
        })
    
    # Check for other CIS domains
    for tld, country in [(".ua", "Ukraine"), (".by", "Belarus"), 
                         (".kz", "Kazakhstan"), (".uz", "Uzbekistan")]:
        if tld in url_lower:
            domain_match = re.search(rf'(?:https?://)?(?:www\.)?([a-z0-9-]+\{tld})', url_lower)
            if domain_match:
                domain = domain_match.group(1)
                return ("cis_generic", {
                    "display_name": f"{domain} ({country})",
                    "category": "CIS Regional",
                    "priority": 4,
                    "url_patterns": [domain],
                    "icon": "🌍"
                })
    
    return (None, None)


def is_excluded(url: str, site_name: str = "") -> bool:
    """
    Check if a URL/site should be excluded.
    
    Args:
        url: The profile URL
        site_name: Optional site name from search tool
        
    Returns:
        True if should be excluded, False otherwise
    """
    url_lower = url.lower()
    site_lower = site_name.lower() if site_name else ""
    
    for excluded in EXCLUDED_PLATFORMS:
        if excluded in url_lower or excluded in site_lower:
            return True
    
    return False


def is_russia_relevant(url: str, site_name: str = "") -> bool:
    """
    Check if a URL is Russia-relevant and should be included.
    
    Args:
        url: The profile URL
        site_name: Optional site name from search tool
        
    Returns:
        True if should be included, False if should be filtered out
    """
    # First check exclusions
    if is_excluded(url, site_name):
        return False
    
    # Then check if it matches whitelist or is a Russian domain
    platform_key, _ = detect_platform(url, site_name)
    return platform_key is not None


def filter_results(results: List[Dict]) -> List[Dict]:
    """
    Filter a list of search results to only Russia-relevant platforms.
    
    Args:
        results: List of result dicts with 'url' and optionally 'site_name'
        
    Returns:
        Filtered list with only Russia-relevant results
    """
    filtered = []
    seen_urls = set()
    
    for result in results:
        url = result.get('url', '')
        site_name = result.get('site_name', '')
        
        # Skip duplicates
        if url in seen_urls:
            continue
        
        # Check if Russia-relevant
        if not is_russia_relevant(url, site_name):
            continue
        
        seen_urls.add(url)
        
        # Enhance result with platform info
        platform_key, platform_info = detect_platform(url, site_name)
        
        if platform_info:
            result['platform'] = platform_info.get('display_name', site_name)
            result['category'] = platform_info.get('category', 'Other')
            result['priority'] = platform_info.get('priority', 5)
            result['icon'] = platform_info.get('icon', '🔗')
        else:
            result['platform'] = site_name or 'Unknown'
            result['category'] = 'Other'
            result['priority'] = 5
            result['icon'] = '🔗'
        
        filtered.append(result)
    
    return filtered


def sort_by_priority(results: List[Dict]) -> List[Dict]:
    """
    Sort results by category priority and then by platform priority.
    
    Args:
        results: List of result dicts with 'category' and 'priority'
        
    Returns:
        Sorted list with most important platforms first
    """
    def sort_key(result):
        category = result.get('category', 'Other')
        priority = result.get('priority', 5)
        
        # Get category index
        try:
            cat_index = CATEGORY_PRIORITY.index(category)
        except ValueError:
            cat_index = 999
        
        return (cat_index, priority, result.get('platform', ''))
    
    return sorted(results, key=sort_key)


def group_by_category(results: List[Dict]) -> Dict[str, List[Dict]]:
    """
    Group results by category.
    
    Args:
        results: List of result dicts with 'category'
        
    Returns:
        Dict mapping category names to lists of results
    """
    grouped = {}
    
    for result in results:
        category = result.get('category', 'Other')
        if category not in grouped:
            grouped[category] = []
        grouped[category].append(result)
    
    # Sort categories by priority
    sorted_grouped = {}
    for cat in CATEGORY_PRIORITY:
        if cat in grouped:
            sorted_grouped[cat] = grouped[cat]
    
    # Add any remaining categories
    for cat in grouped:
        if cat not in sorted_grouped:
            sorted_grouped[cat] = grouped[cat]
    
    return sorted_grouped


def get_stats(original_count: int, filtered_count: int) -> Dict:
    """
    Get filtering statistics.
    
    Args:
        original_count: Number of results before filtering
        filtered_count: Number of results after filtering
        
    Returns:
        Dict with statistics
    """
    removed = original_count - filtered_count
    removal_rate = (removed / original_count * 100) if original_count > 0 else 0
    
    return {
        'original_count': original_count,
        'filtered_count': filtered_count,
        'removed_count': removed,
        'removal_rate': round(removal_rate, 1),
        'platforms_in_whitelist': len(RUSSIA_PLATFORM_WHITELIST),
        'platforms_excluded': len(EXCLUDED_PLATFORMS)
    }


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_whitelist() -> Dict:
    """Return the full platform whitelist."""
    return RUSSIA_PLATFORM_WHITELIST.copy()


def get_excluded() -> set:
    """Return the exclusion set."""
    return EXCLUDED_PLATFORMS.copy()


def add_platform(key: str, display_name: str, category: str, 
                 url_patterns: List[str], priority: int = 3, icon: str = "🔗"):
    """
    Add a custom platform to the whitelist.
    
    Args:
        key: Unique key for the platform
        display_name: Human-readable name
        category: Category for grouping
        url_patterns: URL patterns to match
        priority: Priority level (1=highest)
        icon: Emoji icon for display
    """
    RUSSIA_PLATFORM_WHITELIST[key] = {
        "display_name": display_name,
        "category": category,
        "priority": priority,
        "url_patterns": url_patterns,
        "icon": icon
    }


def remove_platform(key: str):
    """Remove a platform from the whitelist."""
    if key in RUSSIA_PLATFORM_WHITELIST:
        del RUSSIA_PLATFORM_WHITELIST[key]


def add_exclusion(pattern: str):
    """Add a pattern to the exclusion list."""
    EXCLUDED_PLATFORMS.add(pattern)


# =============================================================================
# TESTING
# =============================================================================

if __name__ == "__main__":
    # Test URLs
    test_urls = [
        {"url": "https://vk.com/durov", "site_name": "VK"},
        {"url": "https://ok.ru/profile/123", "site_name": "Odnoklassniki"},
        {"url": "https://t.me/username", "site_name": "Telegram"},
        {"url": "https://facebook.com/user", "site_name": "Facebook"},
        {"url": "https://instagram.com/user", "site_name": "Instagram"},
        {"url": "https://github.com/user", "site_name": "GitHub"},
        {"url": "https://roblox.com/user", "site_name": "Roblox"},
        {"url": "https://chaturbate.com/user", "site_name": "Chaturbate"},
        {"url": "https://habr.com/users/user", "site_name": "Habr"},
        {"url": "https://pikabu.ru/user", "site_name": "Pikabu"},
        {"url": "https://random-site.ru/profile", "site_name": "RandomRu"},
        {"url": "https://nur.kz/user", "site_name": "Nur.kz"},
    ]
    
    print("=" * 60)
    print("Russia Filter Test")
    print("=" * 60)
    
    print(f"\nWhitelist platforms: {len(RUSSIA_PLATFORM_WHITELIST)}")
    print(f"Excluded patterns: {len(EXCLUDED_PLATFORMS)}")
    
    print("\n--- Testing URLs ---")
    for test in test_urls:
        url = test['url']
        is_relevant = is_russia_relevant(url, test['site_name'])
        platform_key, platform_info = detect_platform(url)
        
        status = "✅ INCLUDE" if is_relevant else "❌ EXCLUDE"
        platform_name = platform_info['display_name'] if platform_info else "N/A"
        
        print(f"{status} | {test['site_name']:15} | {platform_name}")
    
    print("\n--- Filter Test ---")
    filtered = filter_results(test_urls)
    print(f"Original: {len(test_urls)} | Filtered: {len(filtered)}")
    
    stats = get_stats(len(test_urls), len(filtered))
    print(f"Removed: {stats['removed_count']} ({stats['removal_rate']}%)")
    
    print("\n--- Filtered Results ---")
    for r in filtered:
        print(f"  {r.get('icon', '🔗')} {r['platform']} ({r['category']}): {r['url']}")
