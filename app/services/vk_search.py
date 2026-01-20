"""VK username search service."""

import requests
import re
import time


HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5,ru;q=0.3',
}


def check_vk_username(username: str) -> dict:
    """Check if VK account exists and get profile info."""
    url = f"https://vk.com/{username}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)

        # VK returns 404 for non-existent usernames
        if resp.status_code == 404:
            return {'exists': False}

        # For 200 responses, check for profile page indicators
        # Error/redirect pages are small (<50KB), valid profiles are large (>100KB)
        if len(resp.text) < 50000:
            # Small page - likely error or redirect, check for specific error patterns
            text_lower = resp.text.lower()
            # These patterns indicate actual error pages (not just text on valid pages)
            if 'message_page' in resp.text or 'error_page' in resp.text:
                return {'exists': False}
            # Check title for error indicators
            title_match = re.search(r'<title>([^<]+)</title>', resp.text)
            if title_match:
                title = title_match.group(1).lower()
                if 'error' in title or 'not found' in title:
                    return {'exists': False}

        original_text = resp.text

        # Extract display_name from <title> tag (strip " | VK" suffix)
        title_match = re.search(r'<title>([^<]+)</title>', original_text)
        display_name = None
        if title_match:
            display_name = title_match.group(1).strip()
            # Remove " | VK" or " | VKontakte" suffix
            display_name = re.sub(r'\s*\|\s*VK(ontakte)?\s*$', '', display_name).strip()

        # Skip if no meaningful display name (likely not a real profile)
        if not display_name or display_name.lower() in ['vk', 'vkontakte', 'error', '']:
            return {'exists': False}

        # Extract photo_url from og:image meta tag (most reliable)
        photo_match = re.search(r'<meta[^>]*property="og:image"[^>]*content="([^"]+)"', original_text)
        if not photo_match:
            photo_match = re.search(r'<meta[^>]*content="([^"]+)"[^>]*property="og:image"', original_text)
        if not photo_match:
            # Try page_avatar img src
            photo_match = re.search(r'<img[^>]*class="[^"]*page_avatar[^"]*"[^>]*src="([^"]+)"', original_text)

        photo_url = photo_match.group(1) if photo_match else None

        return {
            'platform': 'VK',
            'username': username,
            'url': url,
            'display_name': display_name,
            'photo_url': photo_url,
            'exists': True,
            'source': 'vk_direct'
        }

    except Exception:
        pass
    return {'exists': False}


def check_vk_usernames(usernames: list) -> list:
    """Check multiple VK usernames and return found profiles."""
    results = []
    for username in usernames:
        result = check_vk_username(username)
        if result.get('exists'):
            results.append(result)
        # Rate limiting - 0.5 second delay between requests
        time.sleep(0.5)
    return results
