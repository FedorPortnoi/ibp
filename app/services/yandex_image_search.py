"""Yandex reverse image search service.

Searches Yandex Images for social media profiles containing the uploaded photo.
"""

import os
import re
import requests
from bs4 import BeautifulSoup


YANDEX_UPLOAD_URL = 'https://yandex.com/images/search'

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9,ru;q=0.8',
}

# Social media domains to extract from results
SOCIAL_DOMAINS = ['vk.com', 'ok.ru', 'instagram.com', 'facebook.com', 't.me', 'twitter.com', 'x.com']


def _detect_platform(url: str) -> str:
    """Map URL domain to platform name."""
    url_lower = url.lower()

    platform_map = {
        'vk.com': 'VK',
        'ok.ru': 'OK',
        'instagram.com': 'Instagram',
        'facebook.com': 'Facebook',
        't.me': 'Telegram',
        'telegram.org': 'Telegram',
        'twitter.com': 'Twitter',
        'x.com': 'X',
    }

    for domain, platform in platform_map.items():
        if domain in url_lower:
            return platform

    return 'Web'


def yandex_reverse_image_search(image_path: str) -> list:
    """Search Yandex Images with uploaded photo and extract social media profile URLs.

    Args:
        image_path: Path to the image file to search

    Returns:
        List of dicts with platform, url, source, title for each found social profile.
        Returns empty list on any error (graceful degradation).
    """
    # Validate image path
    if not image_path or not os.path.exists(image_path):
        return []

    results = []

    try:
        with open(image_path, 'rb') as file_handle:
            files = {'upfile': ('image.jpg', file_handle, 'image/jpeg')}
            data = {'rpt': 'imageview'}

            response = requests.post(
                YANDEX_UPLOAD_URL,
                files=files,
                data=data,
                headers=HEADERS,
                timeout=30,
                allow_redirects=True
            )

            # Check for CAPTCHA
            if 'captcha' in response.text.lower() or 'SmartCaptcha' in response.text:
                print("DEBUG: Yandex returned CAPTCHA, skipping")
                return []

            # Parse response
            soup = BeautifulSoup(response.text, 'html.parser')

            # Extract all links
            for link in soup.find_all('a', href=True):
                href = link.get('href', '')

                # Check if link contains any social domain
                for domain in SOCIAL_DOMAINS:
                    if domain in href.lower():
                        # Extract link text for title
                        title = link.get_text(strip=True)
                        if not title:
                            # Try parent element
                            parent = link.parent
                            if parent:
                                title = parent.get_text(strip=True)

                        # Truncate title
                        if title and len(title) > 100:
                            title = title[:100] + '...'

                        results.append({
                            'platform': _detect_platform(href),
                            'url': href,
                            'source': 'yandex_image',
                            'title': title or '',
                        })
                        break  # Don't add same link multiple times

    except requests.exceptions.Timeout:
        print("DEBUG: Yandex request timed out")
        return []
    except requests.exceptions.RequestException as e:
        print(f"DEBUG: Yandex request error: {e}")
        return []
    except Exception as e:
        print(f"DEBUG: Yandex search error: {e}")
        return []

    return results
