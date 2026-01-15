"""
Deduplication Utility
=====================
Ensures no duplicate accounts appear in results.
Handles URL normalization and matching.

Author: IBP Project
"""

import re
from typing import List, Dict, Set, Tuple
from urllib.parse import urlparse, unquote


def normalize_url(url: str) -> str:
    """
    Normalize URL for comparison.
    
    Handles:
    - Remove trailing slashes
    - Lowercase domain
    - Remove www.
    - Remove tracking parameters
    - Decode URL encoding
    
    Args:
        url: Raw URL
        
    Returns:
        Normalized URL for comparison
    """
    if not url:
        return ""
    
    try:
        # Decode URL encoding
        url = unquote(url)
        
        # Parse URL
        parsed = urlparse(url.lower().strip())
        
        # Get domain without www
        domain = parsed.netloc
        if domain.startswith('www.'):
            domain = domain[4:]
        
        # Get path without trailing slash
        path = parsed.path.rstrip('/')
        
        # Remove common tracking parameters
        # Keep the base path only
        path = re.sub(r'\?.*$', '', path)
        path = re.sub(r'#.*$', '', path)
        
        # Reconstruct normalized URL
        normalized = f"{domain}{path}"
        
        return normalized
        
    except Exception:
        return url.lower().strip().rstrip('/')


def extract_username_from_url(url: str) -> Tuple[str, str]:
    """
    Extract platform and username from URL.
    
    Args:
        url: Profile URL
        
    Returns:
        Tuple of (platform, username)
    """
    url_lower = url.lower()
    
    patterns = {
        'vk': [
            r'vk\.com/([a-zA-Z0-9_.]+)',
            r'vkontakte\.ru/([a-zA-Z0-9_.]+)',
        ],
        'ok': [
            r'ok\.ru/profile/(\d+)',
            r'ok\.ru/([a-zA-Z0-9_.]+)',
            r'odnoklassniki\.ru/([a-zA-Z0-9_.]+)',
        ],
        'telegram': [
            r't\.me/([a-zA-Z0-9_]+)',
            r'telegram\.me/([a-zA-Z0-9_]+)',
        ],
        'instagram': [
            r'instagram\.com/([a-zA-Z0-9_.]+)',
        ],
        'twitter': [
            r'twitter\.com/([a-zA-Z0-9_]+)',
            r'x\.com/([a-zA-Z0-9_]+)',
        ],
        'github': [
            r'github\.com/([a-zA-Z0-9-]+)',
        ],
        'youtube': [
            r'youtube\.com/@([a-zA-Z0-9_]+)',
            r'youtube\.com/user/([a-zA-Z0-9_]+)',
            r'youtube\.com/c/([a-zA-Z0-9_]+)',
            r'youtube\.com/channel/([a-zA-Z0-9_-]+)',
        ],
        'tiktok': [
            r'tiktok\.com/@([a-zA-Z0-9_.]+)',
        ],
        'facebook': [
            r'facebook\.com/([a-zA-Z0-9_.]+)',
            r'fb\.com/([a-zA-Z0-9_.]+)',
        ],
        'linkedin': [
            r'linkedin\.com/in/([a-zA-Z0-9_-]+)',
        ],
    }
    
    for platform, platform_patterns in patterns.items():
        for pattern in platform_patterns:
            match = re.search(pattern, url_lower)
            if match:
                username = match.group(1)
                return platform, username
    
    return 'unknown', ''


def deduplicate_accounts(accounts: List[Dict]) -> List[Dict]:
    """
    Remove duplicate accounts from list.
    
    Keeps the account with most information (highest score).
    Merges sources if same account found by multiple tools.
    
    Args:
        accounts: List of account dictionaries
        
    Returns:
        Deduplicated list with merged information
    """
    # Track unique accounts by normalized URL
    unique_accounts: Dict[str, Dict] = {}
    
    for account in accounts:
        url = account.get('url', '')
        if not url:
            continue
        
        # Normalize URL for comparison
        normalized = normalize_url(url)
        
        if not normalized:
            continue
        
        if normalized in unique_accounts:
            # Merge with existing account
            existing = unique_accounts[normalized]
            
            # Merge sources
            existing_sources = existing.get('sources', [existing.get('source', 'unknown')])
            new_source = account.get('source', 'unknown')
            
            if isinstance(existing_sources, str):
                existing_sources = [existing_sources]
            
            if new_source not in existing_sources:
                existing_sources.append(new_source)
            
            existing['sources'] = existing_sources
            existing['found_by_multiple'] = len(existing_sources) > 1
            
            # Keep higher confidence score
            if account.get('confidence_score', 0) > existing.get('confidence_score', 0):
                existing['confidence_score'] = account.get('confidence_score', 0)
            
            # Keep face match info if found
            if account.get('face_match') and not existing.get('face_match'):
                existing['face_match'] = True
                existing['face_similarity'] = account.get('face_similarity', 0)
            
            # Merge any additional fields
            for key in ['platform', 'category', 'icon', 'display_name']:
                if account.get(key) and not existing.get(key):
                    existing[key] = account[key]
        else:
            # New unique account
            account_copy = account.copy()
            
            # Ensure sources is a list
            source = account_copy.get('source', 'unknown')
            account_copy['sources'] = [source] if isinstance(source, str) else source
            account_copy['found_by_multiple'] = False
            
            unique_accounts[normalized] = account_copy
    
    # Convert back to list
    result = list(unique_accounts.values())
    
    # Sort: face matches first, then by confidence, then by multiple sources
    result.sort(key=lambda x: (
        x.get('face_match', False),           # Face matches first
        x.get('face_similarity', 0),          # Higher similarity first
        x.get('found_by_multiple', False),    # Multiple sources = more confident
        x.get('confidence_score', 0)          # Then by general confidence
    ), reverse=True)
    
    return result


def count_duplicates(accounts: List[Dict]) -> Dict:
    """
    Count how many duplicates exist before deduplication.
    
    Args:
        accounts: List of accounts
        
    Returns:
        Statistics about duplicates
    """
    url_counts: Dict[str, int] = {}
    
    for account in accounts:
        url = account.get('url', '')
        normalized = normalize_url(url)
        
        if normalized:
            url_counts[normalized] = url_counts.get(normalized, 0) + 1
    
    total = len(accounts)
    unique = len(url_counts)
    duplicates = total - unique
    
    # Find most duplicated URLs
    most_duplicated = sorted(
        [(url, count) for url, count in url_counts.items() if count > 1],
        key=lambda x: x[1],
        reverse=True
    )[:5]
    
    return {
        'total_before': total,
        'unique_count': unique,
        'duplicates_removed': duplicates,
        'duplicate_percentage': (duplicates / total * 100) if total > 0 else 0,
        'most_duplicated': most_duplicated
    }


# =============================================================================
# TESTING
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Deduplication Utility Test")
    print("=" * 60)
    
    # Test data with duplicates
    test_accounts = [
        {'url': 'https://vk.com/ivan_petrov', 'source': 'maigret', 'confidence_score': 50},
        {'url': 'https://VK.com/ivan_petrov/', 'source': 'sherlock', 'confidence_score': 60},  # Duplicate!
        {'url': 'https://www.vk.com/ivan_petrov', 'source': 'facial', 'face_match': True, 'face_similarity': 85},  # Duplicate!
        {'url': 'https://ok.ru/ivan123', 'source': 'maigret', 'confidence_score': 40},
        {'url': 'https://github.com/ivanp', 'source': 'sherlock', 'confidence_score': 30},
        {'url': 'https://github.com/ivanp/', 'source': 'maigret', 'confidence_score': 35},  # Duplicate!
    ]
    
    print(f"\nBefore deduplication: {len(test_accounts)} accounts")
    
    # Count duplicates
    stats = count_duplicates(test_accounts)
    print(f"Duplicates found: {stats['duplicates_removed']}")
    
    # Deduplicate
    unique = deduplicate_accounts(test_accounts)
    print(f"After deduplication: {len(unique)} accounts")
    
    print("\n--- Unique Accounts ---")
    for acc in unique:
        url = acc['url']
        sources = acc.get('sources', [])
        face = "👤 FACE MATCH" if acc.get('face_match') else ""
        multi = "🔗 Multi-source" if acc.get('found_by_multiple') else ""
        print(f"  {url}")
        print(f"    Sources: {sources} {face} {multi}")
