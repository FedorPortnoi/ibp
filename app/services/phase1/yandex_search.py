"""
Yandex Name Search — Phase 1
==============================
Searches yandex.ru for social media profiles matching a name.
Extracts links to VK, Telegram, WhatsApp, Max, OK.

Handles SmartCaptcha gracefully — returns empty results if blocked.
"""

import logging
import re
import time
from typing import List, Dict, Optional
from urllib.parse import urlparse, parse_qs, unquote

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

YANDEX_SEARCH_URL = 'https://yandex.ru/search/'

TARGET_DOMAINS = {
    'vk.com': 'vk',
    't.me': 'telegram',
    'wa.me': 'whatsapp',
    'max.ru': 'max',
    'ok.ru': 'ok',
}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
    'Accept-Encoding': 'gzip, deflate',
    'DNT': '1',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
}

# Reserved URL paths that aren't user profiles
RESERVED_PATHS = {
    'search', 'login', 'feed', 'groups', 'public', 'about', 'help',
    'terms', 'privacy', 'faq', 'support', 'settings', 'menu', 'share',
    'away', 'wall', 'photo', 'video', 'audio', 'board', 'market',
    'friends', 'groups_list', 'apps', 'docs', 'im', 'mail',
}

# Max queries per search
MAX_QUERIES = 4
QUERY_DELAY = 2.5  # seconds between Yandex queries


class YandexNameSearch:
    """
    Searches Yandex for social media profiles matching a name.

    Usage:
        svc = YandexNameSearch()
        results = svc.search('Артём', 'Козлов')
    """

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self._captcha_hit = False

    def search(
        self,
        first_name: str,
        last_name: str,
        city: str = '',
    ) -> List[Dict]:
        """
        Search Yandex for social media profiles matching the name.

        Returns list of profile dicts in the standard search response format.
        """
        full_name = f"{first_name} {last_name}"

        queries = [
            f'"{full_name}"',
            f'"{full_name}" site:vk.com',
            f'"{full_name}" site:t.me',
        ]
        if city:
            queries.append(f'"{full_name}" {city}')

        all_profiles = []
        seen_urls = set()

        for i, query in enumerate(queries[:MAX_QUERIES]):
            if self._captcha_hit:
                logger.warning("Yandex CAPTCHA detected, stopping further queries")
                break

            try:
                html = self._fetch_yandex(query)
                if not html:
                    continue

                if self._is_captcha_page(html):
                    self._captcha_hit = True
                    logger.warning(f"Yandex SmartCaptcha detected for query: {query}")
                    break

                profiles = self._extract_social_links(html, full_name)
                for p in profiles:
                    url = p.get('url', '').lower().rstrip('/')
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        all_profiles.append(p)

            except Exception as e:
                logger.warning(f"Yandex search error for '{query}': {e}")

            # Rate limit between queries
            if i < len(queries) - 1:
                time.sleep(QUERY_DELAY)

        logger.info(f"Yandex search: found {len(all_profiles)} profiles for {full_name}")
        return all_profiles

    def _fetch_yandex(self, query: str) -> Optional[str]:
        """Fetch Yandex search results page."""
        try:
            resp = self.session.get(
                YANDEX_SEARCH_URL,
                params={
                    'text': query,
                    'lr': 213,  # Moscow region
                },
                timeout=15,
                allow_redirects=True,
            )

            if resp.status_code != 200:
                logger.warning(f"Yandex returned HTTP {resp.status_code}")
                return None

            return resp.text

        except requests.Timeout:
            logger.warning("Yandex request timeout")
            return None
        except requests.RequestException as e:
            logger.warning(f"Yandex request error: {e}")
            return None

    @staticmethod
    def _is_captcha_page(html: str) -> bool:
        """Detect Yandex SmartCaptcha or CAPTCHA challenge."""
        captcha_signals = [
            'captcha', 'SmartCaptcha', 'showcaptcha', 'CheckboxCaptcha',
            'captcha-image', '/captcha/',
        ]
        html_lower = html.lower()
        # Check if it's actually a captcha page, not just a mention in JS
        captcha_count = sum(1 for s in captcha_signals if s.lower() in html_lower)
        return captcha_count >= 2

    def _extract_social_links(self, html: str, full_name: str) -> List[Dict]:
        """Extract social media profile links from Yandex search results."""
        soup = BeautifulSoup(html, 'html.parser')
        profiles = []

        # Find all links in the page
        for link in soup.find_all('a', href=True):
            href = link['href']
            clean_url = self._extract_real_url(href)
            if not clean_url:
                continue

            # Check if URL matches target domains
            for domain, platform in TARGET_DOMAINS.items():
                if domain in clean_url:
                    username = self._extract_username(clean_url, platform)
                    if not username:
                        continue

                    # Get surrounding text for name hints
                    snippet = self._get_parent_text(link)

                    profiles.append({
                        'platform': platform,
                        'id': '',
                        'url': clean_url,
                        'first_name': full_name.split()[0] if full_name else '',
                        'last_name': ' '.join(full_name.split()[1:]) if full_name else '',
                        'photo_url': None,
                        'city': '',
                        'age': None,
                        'username': username,
                        'bio': snippet[:200] if snippet else '',
                        'confidence': None,
                        'source': 'Яндекс поиск',
                    })
                    break

        return profiles

    @staticmethod
    def _extract_real_url(href: str) -> Optional[str]:
        """
        Extract the real URL from Yandex redirect wrappers.
        Yandex wraps links in redirectors like /clck/... or //yandex.ru/clck/...
        """
        if not href:
            return None

        # Direct URL
        if href.startswith('http') and 'yandex' not in href.split('/')[2]:
            return href

        # Yandex redirect wrapper — extract from query param
        if '/clck/' in href or 'yandex.ru' in href:
            parsed = urlparse(href)
            params = parse_qs(parsed.query)
            # Common redirect param names
            for param in ['url', 'text', 'to']:
                if param in params:
                    return unquote(params[param][0])

        # Try extracting URL from data attributes
        if href.startswith('//'):
            return 'https:' + href

        return None

    @staticmethod
    def _extract_username(url: str, platform: str) -> Optional[str]:
        """Extract username from social media profile URLs."""
        patterns = {
            'vk': r'vk\.com/([a-zA-Z][a-zA-Z0-9_.]+)',
            'telegram': r't\.me/([a-zA-Z][a-zA-Z0-9_]{3,})',
            'whatsapp': r'wa\.me/(\d+)',
            'max': r'max\.ru/([a-zA-Z][a-zA-Z0-9_.]+)',
            'ok': r'ok\.ru/(?:profile/)?([a-zA-Z0-9_.]+)',
        }
        pattern = patterns.get(platform)
        if not pattern:
            return None

        match = re.search(pattern, url)
        if match:
            username = match.group(1)
            if username.lower() not in RESERVED_PATHS:
                return username

        return None

    @staticmethod
    def _get_parent_text(link_element, max_chars: int = 200) -> str:
        """Get surrounding text from the link's parent element."""
        try:
            parent = link_element.parent
            if parent:
                # Go up 2 levels to get snippet context
                grandparent = parent.parent
                if grandparent:
                    text = grandparent.get_text(separator=' ', strip=True)
                    return text[:max_chars] if text else ''
            return ''
        except Exception:
            return ''

    @property
    def captcha_blocked(self) -> bool:
        """Whether a CAPTCHA was hit during the last search."""
        return self._captcha_hit

    def close(self):
        """Clean up resources."""
        self.session.close()


if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    logging.basicConfig(level=logging.INFO, format='%(name)s: %(message)s')

    svc = YandexNameSearch()
    args = sys.argv[1:] if len(sys.argv) > 1 else ['Артём', 'Козлов']
    first = args[0] if args else 'Артём'
    last = args[1] if len(args) > 1 else 'Козлов'

    results = svc.search(first, last)
    print(f"\nFound {len(results)} profiles via Yandex for {first} {last}")
    for r in results:
        print(f"  [{r['platform']}] @{r['username']} — {r['url']}")

    if svc.captcha_blocked:
        print("\n  WARNING: Yandex CAPTCHA was triggered")
