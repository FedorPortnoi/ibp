"""
VK Web Search — Multi-Strategy People Search
=============================================
Discovers VK profiles by name WITHOUT a user token.

Strategy (combined, all results merged):
1. Screen name guessing — transliterate name → generate common VK username
   patterns → resolve via utils.resolveScreenName (service token)
2. Playwright with persistent browser session (cookies last 6+ months)
   - One-time login saves cookies to vk_session/ directory
   - Subsequent runs reuse saved session automatically
3. VK API newsfeed.search (service token) — finds names in posts

After discovering VK user IDs, enriches them via users.get (service token).
No tokens expire. No OAuth. No refresh flows.

Usage:
    # One-time login to save session cookies (optional, improves results):
    python -m app.services.phase1.vk_web_search --login

    # Search works automatically (screen name guessing always available):
    searcher = VKWebSearch(service_token="...")
    results = searcher.search("Даниил Глазков")
"""

import logging
import os
import re
import time
from pathlib import Path
from typing import List, Dict, Optional, Tuple

try:
    import requests
except ImportError:
    requests = None

logger = logging.getLogger(__name__)

# Directory for persistent Playwright browser state
SESSION_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', 'vk_session')

# User agents for rotation
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0',
]


def _has_session() -> bool:
    """Check if a saved VK browser session exists."""
    return os.path.isdir(SESSION_DIR) and os.listdir(SESSION_DIR)


class VKWebSearch:
    """
    Discovers VK profiles by name using web scraping + API enrichment.

    Flow:
    1. Playwright scrapes vk.com/search (using persistent session cookies)
    2. Extracts VK user IDs from search results HTML
    3. Enriches profiles via VK API users.get (service token, permanent)

    If no Playwright session exists, falls back to newsfeed.search or demo mode.
    """

    VK_API_BASE = "https://api.vk.com/method"
    VK_API_VERSION = "5.199"

    PROFILE_FIELDS = [
        "photo_max_orig", "photo_400_orig", "photo_200", "photo_100",
        "city", "country", "bdate", "domain", "screen_name",
        "education", "universities", "schools", "career",
        "is_closed", "can_access_closed"
    ]

    def __init__(self, service_token: Optional[str] = None):
        self.service_token = service_token or os.environ.get("VK_SERVICE_TOKEN")
        self._session = None
        if requests:
            self._session = requests.Session()

    def search(
        self,
        query: str,
        count: int = 50,
    ) -> Tuple[List[Dict], int]:
        """
        Search VK for people by name. Returns (profiles, total_count).

        Combines results from all strategies (deduped by user ID):
        1. Screen name guessing (transliterate → resolve)
        2. Playwright web scraping (if session exists)
        3. newsfeed.search (finds post authors)

        Each profile is a dict with VK API user fields (same format as users.get).
        """
        all_user_ids = []
        seen_ids = set()

        def _add_ids(ids: List[int]):
            for uid in ids:
                if uid not in seen_ids:
                    seen_ids.add(uid)
                    all_user_ids.append(uid)

        # Step 1: Screen name guessing (fastest, most reliable)
        guessed_ids = self._guess_screen_names(query)
        _add_ids(guessed_ids)

        # Step 2: Playwright web scraping (if session exists)
        playwright_ids = self._playwright_search(query, count)
        _add_ids(playwright_ids)

        # Step 3: newsfeed.search (post authors mentioning the name)
        newsfeed_ids = self._newsfeed_search(query)
        _add_ids(newsfeed_ids)

        if not all_user_ids:
            logger.info(f"VKWebSearch: no results for '{query}'")
            return [], 0

        # Step 4: Enrich discovered IDs with users.get (service token)
        profiles = self._enrich_profiles(all_user_ids, query)
        return profiles, len(profiles)

    def _guess_screen_names(self, query: str) -> List[int]:
        """
        Generate likely VK screen names from a Cyrillic name, then resolve them.

        Transliterates the name to Latin, generates common VK username patterns
        (first.last, last_first, f.last, etc.), and resolves each via
        utils.resolveScreenName (works with service token).

        Returns list of VK user IDs.
        """
        if not self.service_token or not self._session:
            return []

        query_parts = query.strip().split()
        if len(query_parts) < 2:
            return []

        first_name = query_parts[0]
        last_name = query_parts[1]

        # Transliterate Cyrillic → Latin
        try:
            from transliterate import translit
            first_lat = translit(first_name, 'ru', reversed=True).lower()
            last_lat = translit(last_name, 'ru', reversed=True).lower()
        except Exception:
            # Manual basic transliteration fallback
            first_lat = self._basic_translit(first_name)
            last_lat = self._basic_translit(last_name)

        if not first_lat or not last_lat:
            return []

        # Generate candidate screen names (most common VK patterns)
        f = first_lat       # e.g. "daniil"
        l = last_lat        # e.g. "glazkov"
        fi = f[0]           # e.g. "d"

        candidates = [
            f'{f}.{l}',      # daniil.glazkov
            f'{f}_{l}',      # daniil_glazkov
            f'{l}.{f}',      # glazkov.daniil
            f'{l}_{f}',      # glazkov_daniil
            f'{fi}.{l}',     # d.glazkov
            f'{fi}_{l}',     # d_glazkov
            f'{fi}{l}',      # dglazkov
            f'{f}{l}',       # daniilglazkov
            f'{l}{f}',       # glazkovdaniil
            f'{l}',          # glazkov
            f'{l}{fi}',      # glazkovd
        ]

        # Deduplicate while preserving order
        candidates = list(dict.fromkeys(candidates))

        user_ids = []
        for name in candidates:
            try:
                resp = self._session.post(
                    f"{self.VK_API_BASE}/utils.resolveScreenName",
                    data={
                        'screen_name': name,
                        'access_token': self.service_token,
                        'v': self.VK_API_VERSION,
                    },
                    timeout=5,
                )
                data = resp.json()
                result = data.get('response', {})
                if result and result.get('type') == 'user':
                    user_ids.append(result['object_id'])
                time.sleep(0.35)
            except Exception:
                pass

        logger.info(f"VKWebSearch screen names: resolved {len(user_ids)} user IDs from {len(candidates)} candidates for '{query}'")
        return user_ids

    @staticmethod
    def _basic_translit(text: str) -> str:
        """Basic Cyrillic→Latin transliteration fallback."""
        table = {
            'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e',
            'ё': 'yo', 'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'j', 'к': 'k',
            'л': 'l', 'м': 'm', 'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r',
            'с': 's', 'т': 't', 'у': 'u', 'ф': 'f', 'х': 'kh', 'ц': 'ts',
            'ч': 'ch', 'ш': 'sh', 'щ': 'shch', 'ъ': '', 'ы': 'y', 'ь': '',
            'э': 'e', 'ю': 'yu', 'я': 'ya',
        }
        result = []
        for ch in text.lower():
            result.append(table.get(ch, ch))
        return ''.join(result)

    def _playwright_search(self, query: str, count: int = 50) -> List[int]:
        """
        Scrape VK people search using Playwright with persistent session.
        Returns list of VK user IDs.
        """
        if not _has_session():
            logger.debug("VKWebSearch: no saved session, skipping Playwright search")
            return []

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            logger.debug("VKWebSearch: playwright not installed")
            return []

        user_ids = []
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    storage_state=os.path.join(SESSION_DIR, 'state.json'),
                    locale='ru-RU',
                    user_agent=USER_AGENTS[0],
                )
                page = context.new_page()

                # Navigate to VK people search
                search_url = f"https://vk.com/search?c%5Bq%5D={requests.utils.quote(query)}&c%5Bsection%5D=people&c%5Bper_page%5D={min(count, 40)}"
                page.goto(search_url, wait_until='domcontentloaded', timeout=20000)
                page.wait_for_timeout(4000)

                content = page.content()

                # Check if we're still logged in
                if 'login_form' in content and 'id="quick_login' in content:
                    logger.warning("VKWebSearch: session expired, need re-login")
                    browser.close()
                    return []

                # Extract user IDs from search results
                # VK search results contain links like /id123456 or /username
                # Also look for data attributes with user IDs
                id_matches = re.findall(r'href="/id(\d+)"', content)
                user_ids = list(dict.fromkeys(int(uid) for uid in id_matches))

                # Also extract screen names and resolve them
                screen_name_matches = re.findall(
                    r'href="/([a-z][a-z0-9_.]{2,30})"[^>]*class="[^"]*(?:search|people|user)',
                    content, re.IGNORECASE
                )
                if screen_name_matches and self.service_token:
                    resolved = self._resolve_screen_names(screen_name_matches)
                    for uid in resolved:
                        if uid not in user_ids:
                            user_ids.append(uid)

                logger.info(f"VKWebSearch Playwright: found {len(user_ids)} user IDs for '{query}'")
                browser.close()

        except Exception as e:
            logger.warning(f"VKWebSearch Playwright error: {e}")

        return user_ids[:count]

    def _newsfeed_search(self, query: str) -> List[int]:
        """
        Use VK API newsfeed.search (works with service token) to find
        user IDs from posts mentioning the target name.
        """
        if not self.service_token or not self._session:
            return []

        user_ids = []
        try:
            resp = self._session.post(
                f"{self.VK_API_BASE}/newsfeed.search",
                data={
                    'q': query,
                    'count': 100,
                    'access_token': self.service_token,
                    'v': self.VK_API_VERSION,
                },
                timeout=15,
            )
            data = resp.json()

            if 'error' in data:
                logger.warning(f"newsfeed.search error: {data['error'].get('error_msg', '')}")
                return []

            items = data.get('response', {}).get('items', [])

            # Extract user IDs (positive owner_id = users)
            seen = set()
            for item in items:
                owner_id = item.get('owner_id', 0)
                if owner_id > 0 and owner_id not in seen:
                    seen.add(owner_id)
                    user_ids.append(owner_id)

                # Also check signer_id (author if posted on behalf of community)
                signer = item.get('signer_id', 0)
                if signer > 0 and signer not in seen:
                    seen.add(signer)
                    user_ids.append(signer)

            logger.info(f"VKWebSearch newsfeed: found {len(user_ids)} user IDs from posts mentioning '{query}'")

        except Exception as e:
            logger.warning(f"newsfeed.search error: {e}")

        return user_ids

    def _resolve_screen_names(self, screen_names: List[str]) -> List[int]:
        """Resolve VK screen names to user IDs using utils.resolveScreenName."""
        user_ids = []
        if not self.service_token or not self._session:
            return user_ids

        for name in screen_names[:20]:
            try:
                resp = self._session.post(
                    f"{self.VK_API_BASE}/utils.resolveScreenName",
                    data={
                        'screen_name': name,
                        'access_token': self.service_token,
                        'v': self.VK_API_VERSION,
                    },
                    timeout=5,
                )
                data = resp.json()
                result = data.get('response', {})
                if result and result.get('type') == 'user':
                    user_ids.append(result['object_id'])
                time.sleep(0.35)
            except Exception:
                pass

        return user_ids

    def _enrich_profiles(self, user_ids: List[int], query: str) -> List[Dict]:
        """
        Enrich a list of VK user IDs with full profile data using users.get.
        Works with service token (permanent, never expires).

        Returns list of VK API user dicts filtered/sorted by name match.
        """
        if not self.service_token or not self._session:
            return []

        profiles = []
        # Process in batches of 100 (VK API limit)
        for i in range(0, len(user_ids), 100):
            batch = user_ids[i:i+100]
            try:
                resp = self._session.post(
                    f"{self.VK_API_BASE}/users.get",
                    data={
                        'user_ids': ','.join(str(uid) for uid in batch),
                        'fields': ','.join(self.PROFILE_FIELDS),
                        'access_token': self.service_token,
                        'v': self.VK_API_VERSION,
                    },
                    timeout=15,
                )
                data = resp.json()

                if 'error' in data:
                    err = data['error']
                    code = err.get('error_code', 0)
                    msg = err.get('error_msg', '')
                    if code == 5:
                        logger.error(f"VK Error 5: Token invalid. Check VK_SERVICE_TOKEN in .env. Message: {msg}")
                    elif code == 6:
                        time.sleep(1)
                        continue
                    else:
                        logger.error(f"VK API error {code}: {msg}")
                    continue

                users = data.get('response', [])
                profiles.extend(users)

                if i + 100 < len(user_ids):
                    time.sleep(0.35)

            except Exception as e:
                logger.warning(f"users.get enrichment error: {e}")

        # Filter: only keep profiles where name matches the query
        # Support both Cyrillic and Latin (VK may return names in either)
        query_parts = query.lower().split()
        if len(query_parts) >= 2:
            # Build search terms in both Cyrillic and Latin
            search_terms = list(query_parts)
            try:
                from transliterate import translit
                for part in query_parts:
                    search_terms.append(translit(part, 'ru', reversed=True).lower())
            except Exception:
                for part in query_parts:
                    search_terms.append(self._basic_translit(part))

            filtered = []
            for p in profiles:
                fn = p.get('first_name', '').lower()
                ln = p.get('last_name', '').lower()
                full = f"{fn} {ln}"
                # Check if any search term matches first or last name
                matches = sum(
                    1 for term in search_terms
                    if term in fn or term in ln or fn.startswith(term) or ln.startswith(term)
                )
                if matches >= 1:
                    filtered.append(p)
            profiles = filtered

        logger.info(f"VKWebSearch: enriched {len(profiles)} profiles matching '{query}'")
        return profiles


def save_vk_session():
    """
    Interactive: open a browser window, let user log in to VK,
    then save the session cookies for future automated searches.

    Run: python -m app.services.phase1.vk_web_search --login
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("ERROR: playwright not installed. Run: pip install playwright && playwright install chromium")
        return

    os.makedirs(SESSION_DIR, exist_ok=True)
    state_path = os.path.join(SESSION_DIR, 'state.json')

    print("=" * 60)
    print("VK SESSION SETUP")
    print("=" * 60)
    print()
    print("A browser window will open. Log in to VK normally.")
    print("After logging in and seeing your feed, close the browser.")
    print("Your session will be saved for automated searches.")
    print()
    print("This session lasts 6+ months. No token refresh needed.")
    print("=" * 60)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(locale='ru-RU')
        page = context.new_page()

        page.goto('https://vk.com', wait_until='domcontentloaded')

        print("\nWaiting for you to log in... (close browser when done)")

        try:
            # Wait for the user to close the browser (up to 10 minutes)
            page.wait_for_event('close', timeout=600000)
        except Exception:
            pass

        # Save session state
        context.storage_state(path=state_path)
        print(f"\nSession saved to: {state_path}")
        print("VK search will now work automatically!")

        try:
            browser.close()
        except Exception:
            pass


if __name__ == '__main__':
    import sys
    if '--login' in sys.argv:
        save_vk_session()
    else:
        # Quick test
        from dotenv import load_dotenv
        load_dotenv()

        logging.basicConfig(level=logging.INFO)

        searcher = VKWebSearch()
        query = ' '.join(sys.argv[1:]) if len(sys.argv) > 1 else 'Даниил Глазков'
        profiles, total = searcher.search(query)

        print(f"\nResults for '{query}': {total} profiles")
        for p in profiles[:10]:
            name = f"{p.get('first_name', '')} {p.get('last_name', '')}"
            city = p.get('city', {}).get('title', '') if p.get('city') else ''
            photo = 'photo' if p.get('photo_200') else 'no_photo'
            print(f"  id{p['id']} {name} ({city}) [{photo}]")
