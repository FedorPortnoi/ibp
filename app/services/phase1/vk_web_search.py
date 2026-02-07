"""
VK Web Search — Multi-Strategy People Search
=============================================
Discovers VK profiles by name using auto-managed browser session.

Strategy (combined, all results merged):
1. Web token users.search — Playwright auto-login saves browser session,
   captures web token, calls users.search (up to 1000 results per query)
2. Screen name guessing — transliterate name → generate common VK username
   patterns → resolve via utils.resolveScreenName (service token)
3. newsfeed.search fallback — finds posts mentioning the name (service token)

Auto-login flow (zero maintenance):
- First run: Playwright logs in using VK_LOGIN + VK_PASSWORD from .env
- Saves browser session to vk_session/ (cookies last 6+ months)
- Captures web token from VK, caches to vk_session/web_token.json
- Subsequent runs: reuse cached token (no Playwright needed!)
- Token expired? Auto-refresh from saved session
- Session expired? Auto re-login

Required .env vars: VK_LOGIN (phone), VK_PASSWORD, VK_SERVICE_TOKEN
Optional: VK_LOGIN_EMAIL (fallback if phone login fails)

Usage:
    searcher = VKWebSearch(service_token="...")
    results = searcher.search("Даниил Глазков")
    # Returns (profiles_list, total_count)
"""

import logging
import os
import re
import time
from difflib import SequenceMatcher
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


STATE_FILE = os.path.join(SESSION_DIR, 'state.json')
TOKEN_FILE = os.path.join(SESSION_DIR, 'web_token.json')

# Screen name match threshold: 40% average first+last similarity.
# Generous enough for diminutives (Ольга→Оля), strict enough to reject
# completely different names (e.g. "Егор Гусев" for search "Ольга Ахтинас").
SCREEN_NAME_MATCH_THRESHOLD = 0.4


def verify_profile_name_matches_query(profile: dict, search_first: str, search_last: str) -> bool:
    """
    Check if a VK profile's actual name matches the search query.
    Returns True if it's a genuine match, False if it's a coincidental screen name.

    Uses fuzzy matching with transliteration and diminutive support.
    """
    profile_first = (profile.get('first_name') or '').strip().lower()
    profile_last = (profile.get('last_name') or '').strip().lower()
    search_first = (search_first or '').strip().lower()
    search_last = (search_last or '').strip().lower()

    if not profile_first and not profile_last:
        return False

    # Direct fuzzy comparison
    first_sim = SequenceMatcher(None, search_first, profile_first).ratio()
    last_sim = SequenceMatcher(None, search_last, profile_last).ratio()

    # Cross-script comparison via transliteration
    try:
        from transliterate import translit

        def _to_latin(text):
            try:
                return translit(text, 'ru', reversed=True).lower()
            except Exception:
                return text
    except ImportError:
        _table = {
            'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e',
            'ё': 'yo', 'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'j', 'к': 'k',
            'л': 'l', 'м': 'm', 'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r',
            'с': 's', 'т': 't', 'у': 'u', 'ф': 'f', 'х': 'kh', 'ц': 'ts',
            'ч': 'ch', 'ш': 'sh', 'щ': 'shch', 'ъ': '', 'ы': 'y', 'ь': '',
            'э': 'e', 'ю': 'yu', 'я': 'ya',
        }

        def _to_latin(text):
            return ''.join(_table.get(ch, ch) for ch in text)

    sf_lat = _to_latin(search_first)
    sl_lat = _to_latin(search_last)
    pf_lat = _to_latin(profile_first)
    pl_lat = _to_latin(profile_last)

    first_sim = max(first_sim,
                    SequenceMatcher(None, sf_lat, pf_lat).ratio(),
                    SequenceMatcher(None, sf_lat, profile_first).ratio(),
                    SequenceMatcher(None, search_first, pf_lat).ratio())
    last_sim = max(last_sim,
                   SequenceMatcher(None, sl_lat, pl_lat).ratio(),
                   SequenceMatcher(None, sl_lat, profile_last).ratio(),
                   SequenceMatcher(None, search_last, pl_lat).ratio())

    # Diminutive matching for first names
    try:
        from app.services.phase1.russian_diminutives import get_all_name_variants
        search_variants = [v.lower() for v in get_all_name_variants(search_first)]
        profile_variants = [v.lower() for v in get_all_name_variants(profile_first)]
        for sv in search_variants:
            for pv in profile_variants:
                first_sim = max(first_sim, SequenceMatcher(None, sv, pv).ratio())
    except ImportError:
        pass

    overall = (first_sim + last_sim) / 2
    return overall >= SCREEN_NAME_MATCH_THRESHOLD


def _has_session() -> bool:
    """Check if a saved VK browser session exists."""
    return os.path.isfile(STATE_FILE)


def _get_cached_token() -> Optional[str]:
    """Load cached web token if still valid (not expired)."""
    try:
        if not os.path.isfile(TOKEN_FILE):
            return None
        import json as _json
        with open(TOKEN_FILE, 'r') as f:
            data = _json.load(f)
        expires = data.get('expires', 0)
        token = data.get('access_token', '')
        if token and time.time() < expires - 60:  # 60s safety margin
            return token
    except Exception:
        pass
    return None


def _save_token(access_token: str, expires: int, user_id: int = 0) -> None:
    """Cache web token to disk."""
    import json as _json
    os.makedirs(SESSION_DIR, exist_ok=True)
    with open(TOKEN_FILE, 'w') as f:
        _json.dump({
            'access_token': access_token,
            'expires': expires,
            'user_id': user_id,
        }, f)


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

        Strategy (ordered by accuracy, screen name guessing is conditional):
        1. People search via web token users.search (most accurate)
        2. newsfeed.search (supplementary — finds post authors)
        3. Screen name guessing (ONLY if steps 1-2 found < 5 results,
           with name verification from verify_profile_name_matches_query)

        Each profile is a dict with VK API user fields (same format as users.get).
        """
        all_user_ids = []
        seen_ids = set()
        id_methods = {}  # Track discovery method per user ID

        def _add_ids(ids: List[int], method: str = 'unknown'):
            for uid in ids:
                if uid not in seen_ids:
                    seen_ids.add(uid)
                    all_user_ids.append(uid)
                    id_methods[uid] = method

        # Step 1: People search (most accurate — searches real name fields)
        web_search_ids = self._playwright_search(query, count)
        _add_ids(web_search_ids, 'people_search')

        # Step 2: Newsfeed search (supplementary — finds post authors)
        newsfeed_ids = self._newsfeed_search(query)
        _add_ids(newsfeed_ids, 'newsfeed')

        # Step 3: Screen name guessing (only if few results from accurate strategies)
        if len(seen_ids) < 5:
            logger.info(
                f"VKWebSearch: only {len(seen_ids)} results from people/newsfeed search, "
                f"trying screen name guessing..."
            )
            guessed_ids = self._guess_screen_names(query)
            _add_ids(guessed_ids, 'screen_name')
        else:
            logger.info(
                f"VKWebSearch: got {len(seen_ids)} results from people/newsfeed search, "
                f"skipping screen name guessing"
            )

        if not all_user_ids:
            logger.info(f"VKWebSearch: no results for '{query}'")
            return [], 0

        # Step 4: Enrich discovered IDs with users.get (service token)
        profiles = self._enrich_profiles(all_user_ids, query)

        # Tag each profile with its discovery method
        for p in profiles:
            p['discovery_method'] = id_methods.get(p.get('id'), 'unknown')

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

    # ── Web token search (Playwright session → users.search API) ──

    def _playwright_search(self, query: str, count: int = 50) -> List[int]:
        """
        Search VK using the web token obtained from the browser session.

        Flow:
        1. Check cached web token (no Playwright needed if valid)
        2. If expired/missing: start Playwright, load session, capture web token
        3. If no session exists: auto-login first
        4. Call users.search with the web token (full user-level access)

        Returns list of VK user IDs.
        """
        # Step 1: Try cached web token
        web_token = _get_cached_token()

        # Step 2: If no cached token, get a fresh one via Playwright
        if not web_token:
            web_token = self._refresh_web_token()

        if not web_token:
            return []

        # Step 3: Call users.search with the web token
        return self._users_search_with_token(web_token, query, count)

    def _refresh_web_token(self) -> Optional[str]:
        """
        Start Playwright with saved session cookies, navigate to VK,
        capture the web token from login.vk.com/?act=web_token response.
        Auto-logs in if no session exists or session expired.
        """
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            logger.debug("VKWebSearch: playwright not installed")
            return None

        # Ensure session exists (auto-login if needed)
        if not _has_session():
            if not self._auto_login():
                return None

        token = self._extract_web_token()

        # If token extraction failed, session might be expired → re-login
        if not token:
            logger.warning("VKWebSearch: session may be expired, attempting re-login")
            if self._auto_login():
                token = self._extract_web_token()

        return token

    def _extract_web_token(self) -> Optional[str]:
        """Load browser session and capture the web token VK issues on page load."""
        from playwright.sync_api import sync_playwright
        import json as _json

        token_result = {}

        def _capture(response):
            if 'act=web_token' in response.url:
                try:
                    body = response.text()
                    data = _json.loads(body)
                    inner = data.get('data', data)
                    if inner.get('access_token'):
                        token_result['token'] = inner['access_token']
                        token_result['expires'] = inner.get('expires', 0)
                        token_result['user_id'] = inner.get('user_id', 0)
                except Exception:
                    pass

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    storage_state=STATE_FILE,
                    locale='ru-RU',
                    user_agent=USER_AGENTS[0],
                )
                page = context.new_page()
                page.on('response', _capture)

                # Navigate to any VK page — VK issues a web token on load
                page.goto('https://vk.com/feed', wait_until='domcontentloaded', timeout=20000)
                page.wait_for_timeout(5000)
                browser.close()

        except Exception as e:
            logger.warning(f"VKWebSearch: web token extraction error: {e}")

        if token_result.get('token'):
            _save_token(
                token_result['token'],
                token_result.get('expires', 0),
                token_result.get('user_id', 0),
            )
            logger.info("VKWebSearch: web token captured and cached")
            return token_result['token']

        return None

    def _users_search_with_token(
        self, token: str, query: str, count: int
    ) -> List[int]:
        """Call VK API users.search with a web token. Returns user IDs."""
        if not self._session:
            return []

        try:
            resp = self._session.post(
                f"{self.VK_API_BASE}/users.search",
                data={
                    'q': query,
                    'count': min(count, 1000),
                    'fields': ','.join(self.PROFILE_FIELDS),
                    'access_token': token,
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
                    # Token expired — clear cache, next call will refresh
                    logger.warning(f"VKWebSearch: web token expired, will refresh")
                    try:
                        os.remove(TOKEN_FILE)
                    except OSError:
                        pass
                else:
                    logger.warning(f"VKWebSearch users.search error {code}: {msg}")
                return []

            response = data.get('response', {})
            items = response.get('items', [])
            total = response.get('count', 0)

            user_ids = [item['id'] for item in items if 'id' in item]
            logger.info(f"VKWebSearch users.search: {total} total, got {len(user_ids)} IDs for '{query}'")
            return user_ids

        except Exception as e:
            logger.warning(f"VKWebSearch users.search error: {e}")
            return []

    # ── Auto-login ────────────────────────────────────────────

    def _auto_login(self) -> bool:
        """
        Log in to VK automatically using credentials from .env.
        Saves browser state to vk_session/state.json for future runs.

        Tries VK_LOGIN (phone) first, then VK_LOGIN_EMAIL as fallback.
        Returns True on success. Handles captcha gracefully (returns False).
        """
        vk_login = os.environ.get('VK_LOGIN', '').strip()
        vk_email = os.environ.get('VK_LOGIN_EMAIL', '').strip()
        vk_password = os.environ.get('VK_PASSWORD', '').strip()

        if not vk_password or not (vk_login or vk_email):
            logger.debug("VKWebSearch: VK_LOGIN/VK_PASSWORD not set, skipping auto-login")
            return False

        try:
            from playwright.sync_api import sync_playwright  # noqa: already checked
        except ImportError:
            return False

        os.makedirs(SESSION_DIR, exist_ok=True)

        # Try phone first, then email
        logins_to_try = []
        if vk_login:
            logins_to_try.append(vk_login)
        if vk_email and vk_email != vk_login:
            logins_to_try.append(vk_email)

        for login_value in logins_to_try:
            masked = login_value[:4] + '***'
            logger.info(f"VKWebSearch: attempting auto-login with {masked}")
            try:
                if self._try_vk_login(login_value, vk_password):
                    logger.info("VKWebSearch: auto-login successful, session saved")
                    return True
                logger.warning(f"VKWebSearch: login with {masked} did not succeed")
            except Exception as e:
                logger.warning(f"VKWebSearch: login with {masked} error: {e}")

        return False

    def _try_vk_login(self, login: str, password: str) -> bool:
        """
        Attempt a single VK login via Playwright headless browser.
        Navigates to vk.com, fills credentials, saves session on success.
        Returns True if logged in successfully.
        """
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                locale='ru-RU',
                user_agent=USER_AGENTS[0],
                viewport={'width': 1280, 'height': 720},
            )
            page = context.new_page()

            try:
                # ── Step 1: Navigate to VK ──
                page.goto('https://vk.com', wait_until='domcontentloaded', timeout=25000)
                page.wait_for_timeout(3000)

                # Already logged in? (unlikely on fresh context but check)
                if 'feed' in page.url or 'im' in page.url:
                    context.storage_state(path=STATE_FILE)
                    browser.close()
                    return True

                # ── Step 2: Find and click "Sign in" if on landing page ──
                self._click_sign_in(page)
                page.wait_for_timeout(2000)

                # ── Step 3: Fill login (phone/email) ──
                login_filled = self._fill_login_field(page, login)
                if not login_filled:
                    logger.warning("VKWebSearch: could not find login input field")
                    browser.close()
                    return False

                # Submit the login step
                self._submit_form(page)
                page.wait_for_timeout(3000)

                # ── Step 4: Check for captcha / errors ──
                if self._has_captcha(page):
                    logger.warning("VKWebSearch: CAPTCHA detected, cannot auto-login")
                    browser.close()
                    return False

                # ── Step 5: Fill password ──
                pw_filled = self._fill_password_field(page, password)
                if not pw_filled:
                    logger.warning("VKWebSearch: could not find password field")
                    browser.close()
                    return False

                # Submit password
                self._submit_form(page)
                page.wait_for_timeout(5000)

                # ── Step 6: Check for captcha after password ──
                if self._has_captcha(page):
                    logger.warning("VKWebSearch: CAPTCHA after password, cannot auto-login")
                    browser.close()
                    return False

                # ── Step 7: Verify login success ──
                url = page.url
                content = page.content()
                logged_in = (
                    'feed' in url
                    or '/im' in url
                    or 'al_page.php' in content
                    or 'TopNavBtn' in content
                    or '"loc":"feed"' in content
                    or 'data-task-click="ProfileAction"' in content
                    or not self._page_needs_login(content)
                )

                if logged_in and self._page_needs_login(content):
                    logged_in = False

                if logged_in:
                    context.storage_state(path=STATE_FILE)
                    browser.close()
                    return True

                logger.debug(f"VKWebSearch: login check — url={url[:60]}")
                browser.close()
                return False

            except Exception as e:
                try:
                    browser.close()
                except Exception:
                    pass
                raise

    @staticmethod
    def _has_captcha(page) -> bool:
        """Check if page shows an actual CAPTCHA challenge (not just JS strings)."""
        # Look for visible captcha-related elements, not just text in JS bundles
        captcha_selectors = [
            'img[src*="captcha"]',
            '[class*="captcha" i]',
            '[id*="captcha" i]',
            'iframe[src*="recaptcha"]',
            'iframe[src*="captcha"]',
            '.g-recaptcha',
            '#recaptcha',
        ]
        for sel in captcha_selectors:
            try:
                el = page.locator(sel).first
                if el.is_visible(timeout=500):
                    return True
            except Exception:
                continue
        return False

    @staticmethod
    def _click_sign_in(page) -> None:
        """Click 'Sign in another way' / 'Войти другим способом' on VK landing."""
        # VK shows QR code by default — need to click "Sign in another way"
        selectors = [
            'button:has-text("Войти другим способом")',
            'a:has-text("Войти другим способом")',
            'button:has-text("Sign in by another method")',
            'button:has-text("Sign in")',
            'a:has-text("Sign in")',
            'button:has-text("Войти")',
            'a:has-text("Войти")',
            'a[href*="login"]',
            '.VkIdForm__signInButton',
        ]
        for sel in selectors:
            try:
                el = page.locator(sel).first
                if el.is_visible(timeout=1500):
                    el.click()
                    return
            except Exception:
                continue

    @staticmethod
    def _fill_login_field(page, login_value: str) -> bool:
        """Find and fill the phone/email input field."""
        selectors = [
            'input[name="login"]',
            'input[type="tel"]',
            'input[type="email"]',
            'input[name="phone"]',
            'input[name="email"]',
        ]
        for sel in selectors:
            try:
                el = page.locator(sel).first
                if el.is_visible(timeout=2000):
                    el.click()
                    el.fill(login_value)
                    return True
            except Exception:
                continue

        # Fallback: try any visible text input that isn't password/hidden
        try:
            inputs = page.locator('input:visible:not([type="password"]):not([type="hidden"]):not([type="submit"]):not([type="checkbox"])')
            if inputs.count() > 0:
                inputs.first.click()
                inputs.first.fill(login_value)
                return True
        except Exception:
            pass

        return False

    @staticmethod
    def _fill_password_field(page, password: str) -> bool:
        """Find and fill the password input field."""
        try:
            pw = page.locator('input[type="password"]').first
            pw.wait_for(state='visible', timeout=5000)
            pw.click()
            pw.fill(password)
            return True
        except Exception:
            return False

    @staticmethod
    def _submit_form(page) -> None:
        """Submit the current form — try button click, fall back to Enter."""
        selectors = [
            'button[type="submit"]',
            'button:has-text("Continue")',
            'button:has-text("Продолжить")',
            'button:has-text("Sign in")',
            'button:has-text("Войти")',
            'input[type="submit"]',
            'button:has-text("Next")',
            'button:has-text("Далее")',
        ]
        for sel in selectors:
            try:
                btn = page.locator(sel).first
                if btn.is_visible(timeout=1000):
                    btn.click()
                    return
            except Exception:
                continue

        # Fallback: press Enter on the focused element
        try:
            page.keyboard.press('Enter')
        except Exception:
            pass

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

        # Filter: verify each profile's actual name matches the search query
        # Uses fuzzy matching with transliteration + diminutive support
        query_parts = query.lower().split()
        if len(query_parts) >= 2:
            search_first = query_parts[0]
            search_last = query_parts[1]

            filtered = []
            for p in profiles:
                fn = p.get('first_name', '')
                ln = p.get('last_name', '')
                if verify_profile_name_matches_query(p, search_first, search_last):
                    logger.info(f"  \u2713 Verified: {fn} {ln} (id{p.get('id', '?')})")
                    filtered.append(p)
                else:
                    logger.warning(
                        f"  \u2717 REJECTED fake match: '{fn} {ln}' (id{p.get('id', '?')}) "
                        f"doesn't match search '{query}'"
                    )
            profiles = filtered

        logger.info(f"VKWebSearch: enriched {len(profiles)} profiles matching '{query}'")
        return profiles


def save_vk_session():
    """
    Interactive fallback: open a browser window, let user log in to VK,
    then save the session cookies. Use this if auto-login fails (e.g., 2FA).

    Run: python -m app.services.phase1.vk_web_search --login
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("ERROR: playwright not installed. Run: pip install playwright && playwright install chromium")
        return

    os.makedirs(SESSION_DIR, exist_ok=True)

    print("=" * 60)
    print("VK SESSION SETUP (manual)")
    print("=" * 60)
    print()
    print("A browser window will open. Log in to VK normally.")
    print("After logging in and seeing your feed, close the browser.")
    print("Your session will be saved for automated searches.")
    print()
    print("This is a fallback for when auto-login can't work (2FA, etc.)")
    print("=" * 60)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(locale='ru-RU')
        page = context.new_page()

        page.goto('https://vk.com', wait_until='domcontentloaded')

        print("\nWaiting for you to log in... (close browser when done)")

        try:
            page.wait_for_event('close', timeout=600000)
        except Exception:
            pass

        context.storage_state(path=STATE_FILE)
        print(f"\nSession saved to: {STATE_FILE}")
        print("VK search will now work automatically!")

        try:
            browser.close()
        except Exception:
            pass


if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8')

    if '--login' in sys.argv:
        save_vk_session()
    else:
        from dotenv import load_dotenv
        load_dotenv()

        logging.basicConfig(level=logging.INFO, format='%(name)s: %(message)s')

        searcher = VKWebSearch()
        query = ' '.join(sys.argv[1:]) if len(sys.argv) > 1 else 'Даниил Глазков'
        profiles, total = searcher.search(query)

        print(f"\nResults for '{query}': {total} profiles")
        for i, p in enumerate(profiles[:20]):
            name = f"{p.get('first_name', '')} {p.get('last_name', '')}"
            city = p.get('city', {}).get('title', '') if p.get('city') else ''
            photo = 'photo' if p.get('photo_200') else 'no_photo'
            print(f"  {i+1}. id{p['id']} {name} ({city}) [{photo}]")
