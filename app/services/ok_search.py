"""OK (Odnoklassniki) username search service."""

import requests
import re
import time


HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5,ru;q=0.3',
}


def check_ok_username(username: str) -> dict:
    """Check if OK (Odnoklassniki) account exists and get profile info.

    OK URLs format: https://ok.ru/profile/{username} or https://ok.ru/{username}
    """
    # Try profile URL first (more common for usernames)
    urls_to_try = [
        f"https://ok.ru/profile/{username}",
        f"https://ok.ru/{username}"
    ]

    for url in urls_to_try:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=10, allow_redirects=True)

            # OK returns 404 for non-existent profiles
            if resp.status_code == 404:
                continue

            # Check for profile page indicators
            # OK profiles have specific markers in the HTML
            if resp.status_code == 200:
                text = resp.text

                # Check if it's a valid profile page (not an error page)
                # Error pages typically have "page not found" or redirect to main
                if 'userContentHeader' in text or 'profile-user' in text or 'user-profile' in text:
                    pass  # Looks like a profile
                elif 'pageNotFound' in text or 'error-page' in text:
                    continue  # Error page
                elif 'ok.ru/dk' in resp.url:  # Redirected to main page
                    continue

                # Extract display_name from title or og:title
                title_match = re.search(r'<title>([^<]+)</title>', text)
                display_name = None
                if title_match:
                    display_name = title_match.group(1).strip()
                    # Remove " - OK.RU" or similar suffixes
                    display_name = re.sub(r'\s*[-|]\s*(OK\.RU|Одноклассники|OK\.ru).*$', '', display_name, flags=re.IGNORECASE).strip()

                # Also try og:title
                if not display_name or len(display_name) < 2:
                    og_match = re.search(r'<meta[^>]*property="og:title"[^>]*content="([^"]+)"', text)
                    if og_match:
                        display_name = og_match.group(1).strip()
                        display_name = re.sub(r'\s*[-|]\s*(OK\.RU|Одноклассники).*$', '', display_name, flags=re.IGNORECASE).strip()

                # Skip if no meaningful display name
                if not display_name or display_name.lower() in ['ok.ru', 'одноклассники', 'ok', 'error', '']:
                    continue

                # Extract photo_url from og:image
                photo_match = re.search(r'<meta[^>]*property="og:image"[^>]*content="([^"]+)"', text)
                if not photo_match:
                    photo_match = re.search(r'<meta[^>]*content="([^"]+)"[^>]*property="og:image"', text)
                photo_url = photo_match.group(1) if photo_match else None

                return {
                    'platform': 'OK',
                    'username': username,
                    'url': resp.url,  # Use final URL after redirects
                    'display_name': display_name,
                    'photo_url': photo_url,
                    'exists': True,
                    'source': 'ok_direct'
                }

        except Exception:
            pass

    return {'exists': False}


def check_ok_usernames(usernames: list) -> list:
    """Check multiple OK usernames and return found profiles."""
    results = []
    for username in usernames:
        result = check_ok_username(username)
        if result.get('exists'):
            results.append(result)
        # Rate limiting - 0.5 second delay between requests
        time.sleep(0.5)
    return results
