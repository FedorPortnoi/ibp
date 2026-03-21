"""
Yandex People Search — Phase 1 (Playwright)
============================================
Searches yandex.ru/people for social media profiles matching a name.
Uses Playwright browser to bypass SmartCaptcha blocking.

Extracts links to VK, Telegram, WhatsApp, Max, OK from Yandex People cards.
Handles SmartCaptcha gracefully — returns empty results if blocked.
"""

import logging
import random
import re
import time
import traceback
from typing import List, Dict, Optional
from urllib.parse import urlparse, quote_plus

logger = logging.getLogger(__name__)

# Target social media domains to extract from Yandex People results
TARGET_DOMAINS = {
    'vk.com': 'vk',
    't.me': 'telegram',
    'wa.me': 'whatsapp',
    'max.ru': 'max',
    'ok.ru': 'ok',
    'instagram.com': 'instagram',
    'facebook.com': 'facebook',
}

# Reserved URL paths that aren't user profiles
RESERVED_PATHS = {
    'search', 'login', 'feed', 'groups', 'public', 'about', 'help',
    'terms', 'privacy', 'faq', 'support', 'settings', 'menu', 'share',
    'away', 'wall', 'photo', 'video', 'audio', 'board', 'market',
    'friends', 'groups_list', 'apps', 'docs', 'im', 'mail',
}

# User agent for browser context
USER_AGENT = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
    'AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/131.0.0.0 Safari/537.36'
)

# Yandex People URL patterns to try
YANDEX_PEOPLE_URLS = [
    'https://yandex.ru/people?query={query}',
    'https://yandex.ru/people/search?text={query}',
]

MAX_RESULTS = 100


class YandexNameSearch:
    """
    Searches Yandex People for social media profiles matching a name.
    Uses Playwright for browser-based rendering to avoid CAPTCHA blocking.

    Usage:
        svc = YandexNameSearch()
        results = svc.search('Артём', 'Козлов')
    """

    # Class-level singleton browser to reuse across searches
    _browser = None
    _playwright = None

    def __init__(self):
        self._captcha_hit = False

    def search(
        self,
        first_name: str,
        last_name: str,
        city: str = '',
    ) -> List[Dict]:
        """
        Search Yandex People for social media profiles matching the name.
        Returns list of profile dicts in the standard search response format.
        """
        self._captcha_hit = False
        full_name = f"{first_name} {last_name}".strip()

        if not full_name:
            return []

        # Build query with optional city filter
        query = full_name
        if city:
            query = f"{full_name} {city}"

        try:
            profiles = self._search_playwright(query, first_name, last_name)
            logger.info(f"Yandex search: found {len(profiles)} profiles for {full_name}")
            return profiles[:MAX_RESULTS]
        except Exception as e:
            logger.error(f"Yandex search error: {e}\n{traceback.format_exc()}")
            return []

    def _search_playwright(
        self,
        query: str,
        first_name: str,
        last_name: str,
    ) -> List[Dict]:
        """Execute Yandex People search via Playwright browser."""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            logger.error("Yandex Playwright: playwright not installed, returning empty")
            return []

        page = None
        try:
            browser = self._get_browser()
            if not browser:
                return []

            # Create new page with Russian locale
            context = browser.new_context(
                locale='ru-RU',
                user_agent=USER_AGENT,
                viewport={'width': 1280, 'height': 900},
            )
            page = context.new_page()

            # Stealth: remove webdriver flag
            page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            """)

            # Random human-like delay before navigation
            delay = random.uniform(1.0, 3.0)
            time.sleep(delay)

            # Try each Yandex People URL pattern
            profiles = []
            for url_template in YANDEX_PEOPLE_URLS:
                url = url_template.format(query=quote_plus(query))
                logger.info(f"Yandex Playwright: navigating to {url}")

                try:
                    page.goto(url, wait_until='domcontentloaded', timeout=15000)
                except Exception as nav_err:
                    logger.warning(f"Yandex Playwright: navigation error for {url}: {nav_err}")
                    continue

                # Wait for page to settle
                page.wait_for_timeout(2000)

                # Check for CAPTCHA
                if self._check_captcha(page):
                    self._captcha_hit = True
                    logger.warning(f"Yandex SmartCaptcha detected for query: \"{query}\"")
                    break

                # Scroll down to trigger lazy loading
                self._scroll_page(page)

                # Parse profile cards from rendered DOM
                raw_profiles = self._parse_people_cards(page, first_name, last_name)
                if raw_profiles:
                    logger.info(f"Yandex Playwright: URL pattern worked: {url_template}")
                    profiles = raw_profiles
                    break
                else:
                    logger.info(f"Yandex Playwright: no results from {url_template}, trying next")

            # Close context (not browser — keep singleton alive)
            try:
                context.close()
            except Exception as e:
                logger.debug(f"[YandexSearch] Context close failed: {e}")

            return profiles

        except Exception as e:
            logger.error(f"Yandex Playwright error: {e}\n{traceback.format_exc()}")
            if page:
                try:
                    page.context.close()
                except Exception as close_err:
                    logger.debug(f"[YandexSearch] Context close during error: {close_err}")
            return []

    @classmethod
    def _get_browser(cls):
        """Get or create the singleton Playwright browser instance."""
        if cls._browser and cls._browser.is_connected():
            return cls._browser

        try:
            from playwright.sync_api import sync_playwright

            # Close stale playwright instance if any
            if cls._playwright:
                try:
                    cls._playwright.stop()
                except Exception as e:
                    logger.debug(f"[YandexSearch] Playwright stop failed: {e}")

            cls._playwright = sync_playwright().start()
            cls._browser = cls._playwright.chromium.launch(
                headless=True,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                ],
            )
            logger.info("Yandex Playwright: browser launched")
            return cls._browser

        except Exception as e:
            logger.error(f"Yandex Playwright: browser launch failed: {e}")
            cls._browser = None
            cls._playwright = None
            return None

    @staticmethod
    def _check_captcha(page) -> bool:
        """Detect Yandex SmartCaptcha or CAPTCHA challenge on the page."""
        try:
            url = page.url.lower()
            if 'captcha' in url or 'showcaptcha' in url:
                return True
        except Exception as e:
            logger.debug(f"[YandexSearch] Captcha URL check failed: {e}")

        # Check for captcha-related elements in DOM
        captcha_selectors = [
            '[class*="Captcha"]',
            '[id*="captcha"]',
            'form[action*="captcha"]',
            'img[src*="captcha"]',
            '[class*="CheckboxCaptcha"]',
            '[class*="SmartCaptcha"]',
        ]
        for sel in captcha_selectors:
            try:
                el = page.locator(sel).first
                if el.is_visible(timeout=500):
                    return True
            except Exception as e:
                logger.debug(f"[YandexSearch] Captcha selector '{sel}' check failed: {e}")
                continue

        # Check page text for confirmation prompts
        try:
            body_text = page.locator('body').inner_text(timeout=1000)
            if any(s in body_text for s in ['Подтвердите', 'не робот', 'I\'m not a robot']):
                return True
        except Exception as e:
            logger.debug(f"[YandexSearch] Body text captcha check failed: {e}")

        return False

    @staticmethod
    def _scroll_page(page) -> None:
        """Scroll down 2-3 times to trigger lazy loading of profile cards."""
        try:
            for _ in range(3):
                page.evaluate('window.scrollBy(0, window.innerHeight * 0.8)')
                page.wait_for_timeout(random.randint(800, 1500))
        except Exception as e:
            logger.debug(f"[YandexSearch] Scroll failed: {e}")

    def _parse_people_cards(
        self,
        page,
        first_name: str,
        last_name: str,
    ) -> List[Dict]:
        """
        Parse Yandex People profile cards from the rendered DOM.
        Uses JavaScript evaluation for flexible extraction.
        """
        # Extract structured data from the page via JS
        raw_cards = page.evaluate("""
        () => {
            const results = [];

            // Strategy 1: Look for person card elements with data attributes
            const dataCards = document.querySelectorAll(
                '[data-testid*="person"], [data-testid*="card"], [data-testid*="result"]'
            );
            if (dataCards.length > 0) {
                dataCards.forEach(card => {
                    const links = [];
                    card.querySelectorAll('a[href]').forEach(a => {
                        links.push({href: a.href, text: a.textContent.trim()});
                    });
                    const imgs = [];
                    card.querySelectorAll('img[src]').forEach(img => {
                        imgs.push(img.src);
                    });
                    results.push({
                        text: card.textContent.trim().substring(0, 500),
                        links: links,
                        imgs: imgs,
                    });
                });
                return {strategy: 'data-testid', cards: results};
            }

            // Strategy 2: Look for repeated card-like structures
            // Yandex People typically wraps each person in a card div
            const allLinks = document.querySelectorAll('a[href]');
            const socialDomains = ['vk.com', 't.me', 'ok.ru', 'instagram.com',
                                   'facebook.com', 'wa.me', 'max.ru'];
            const cardMap = new Map();

            allLinks.forEach(link => {
                const href = link.href || '';
                const isSocial = socialDomains.some(d => href.includes(d));
                if (!isSocial) return;

                // Find the card container — walk up to find a reasonable parent
                let container = link.parentElement;
                for (let i = 0; i < 5 && container; i++) {
                    // Stop if we find a parent that looks like a card wrapper
                    const classes = (container.className || '').toLowerCase();
                    if (classes.includes('card') || classes.includes('item') ||
                        classes.includes('result') || classes.includes('person') ||
                        classes.includes('snippet')) {
                        break;
                    }
                    // Also stop if parent has multiple social links (= card boundary)
                    const parentSocialLinks = Array.from(
                        container.querySelectorAll('a[href]')
                    ).filter(a => socialDomains.some(d => (a.href||'').includes(d)));
                    if (parentSocialLinks.length > 1) break;
                    container = container.parentElement;
                }

                if (!container) return;

                // Use container as card key
                const key = container.outerHTML.substring(0, 100);
                if (!cardMap.has(key)) {
                    const links = [];
                    container.querySelectorAll('a[href]').forEach(a => {
                        links.push({href: a.href, text: a.textContent.trim()});
                    });
                    const imgs = [];
                    container.querySelectorAll('img[src]').forEach(img => {
                        if (img.src && !img.src.includes('data:') &&
                            img.width > 20 && img.height > 20) {
                            imgs.push(img.src);
                        }
                    });
                    cardMap.set(key, {
                        text: container.textContent.trim().substring(0, 500),
                        links: links,
                        imgs: imgs,
                    });
                }
            });

            if (cardMap.size > 0) {
                return {strategy: 'social-links', cards: Array.from(cardMap.values())};
            }

            // Strategy 3: Fallback — just collect all social media links on the page
            const fallbackLinks = [];
            allLinks.forEach(link => {
                const href = link.href || '';
                const isSocial = socialDomains.some(d => href.includes(d));
                if (isSocial) {
                    // Get surrounding text (up 3 levels)
                    let ctx = link.parentElement;
                    for (let i = 0; i < 2 && ctx && ctx.parentElement; i++) {
                        ctx = ctx.parentElement;
                    }
                    fallbackLinks.push({
                        href: href,
                        text: link.textContent.trim(),
                        context: ctx ? ctx.textContent.trim().substring(0, 300) : '',
                    });
                }
            });

            if (fallbackLinks.length > 0) {
                // Group by unique href
                const grouped = {};
                fallbackLinks.forEach(l => {
                    if (!grouped[l.href]) {
                        grouped[l.href] = l;
                    }
                });
                return {
                    strategy: 'fallback-links',
                    cards: Object.values(grouped).map(l => ({
                        text: l.context || l.text,
                        links: [{href: l.href, text: l.text}],
                        imgs: [],
                    }))
                };
            }

            return {strategy: 'none', cards: []};
        }
        """)

        strategy = raw_cards.get('strategy', 'none')
        cards = raw_cards.get('cards', [])
        logger.info(
            f"Yandex Playwright: DOM extraction strategy='{strategy}', "
            f"found {len(cards)} card(s)"
        )

        if not cards:
            return []

        # Process each card into profile dicts
        all_profiles = []
        seen_urls = set()

        for card in cards:
            text = card.get('text', '')
            links = card.get('links', [])
            imgs = card.get('imgs', [])
            photo_url = imgs[0] if imgs else None

            # Extract person name from card text (first line is usually the name)
            card_name = self._extract_name_from_text(text)

            for link_info in links:
                href = link_info.get('href', '')
                if not href:
                    continue

                # Match against target social media domains
                platform = None
                for domain, plat in TARGET_DOMAINS.items():
                    if domain in href:
                        platform = plat
                        break

                if not platform:
                    continue

                username = self._extract_username(href, platform)
                if not username:
                    continue

                # Deduplicate by URL
                url_key = href.lower().rstrip('/')
                if url_key in seen_urls:
                    continue
                seen_urls.add(url_key)

                # Extract city and age from card text
                city = self._extract_city(text)
                age = self._extract_age(text)

                # Determine name fields
                display_first = first_name
                display_last = last_name
                if card_name:
                    name_parts = card_name.split(None, 1)
                    if len(name_parts) >= 2:
                        display_first = name_parts[0]
                        display_last = name_parts[1]
                    elif name_parts:
                        display_first = name_parts[0]

                all_profiles.append({
                    'platform': platform,
                    'id': '',
                    'url': href,
                    'first_name': display_first,
                    'last_name': display_last,
                    'photo_url': photo_url,
                    'city': city,
                    'age': age,
                    'username': username,
                    'bio': text[:200] if text else '',
                    'confidence': None,
                    'source': 'Яндекс поиск',
                })

        # Name verification — only keep profiles matching the search name
        verified = self._verify_profiles(all_profiles, first_name, last_name)
        logger.info(
            f"Yandex Playwright: {len(verified)} profiles passed name verification "
            f"(out of {len(all_profiles)})"
        )

        return verified

    @staticmethod
    def _verify_profiles(
        profiles: List[Dict],
        first_name: str,
        last_name: str,
    ) -> List[Dict]:
        """Verify profile names match the search query using shared name matcher."""
        if not first_name and not last_name:
            return profiles

        try:
            from app.services.phase1.vk_web_search import verify_profile_name_matches_query
        except ImportError:
            # Fallback: basic case-insensitive match
            logger.warning("Yandex: could not import name verifier, using basic matching")
            verified = []
            fn_lower = first_name.lower()
            ln_lower = last_name.lower()
            for p in profiles:
                pf = (p.get('first_name') or '').lower()
                pl = (p.get('last_name') or '').lower()
                if fn_lower in pf or pf in fn_lower or ln_lower in pl or pl in ln_lower:
                    verified.append(p)
            return verified

        verified = []
        for p in profiles:
            if verify_profile_name_matches_query(p, first_name, last_name):
                p['confidence'] = 'высокая'
                verified.append(p)

        return verified

    @staticmethod
    def _extract_name_from_text(text: str) -> Optional[str]:
        """Extract a person's name from card text (usually the first line)."""
        if not text:
            return None
        lines = text.strip().split('\n')
        if not lines:
            return None
        first_line = lines[0].strip()
        # A name is typically 2-3 words, mostly Cyrillic
        if len(first_line) > 50:
            return None
        words = first_line.split()
        if 1 <= len(words) <= 4:
            # Check if mostly Cyrillic
            cyrillic_count = sum(1 for w in words if re.search(r'[а-яА-ЯёЁ]', w))
            if cyrillic_count >= len(words) * 0.5:
                return first_line
        return None

    @staticmethod
    def _extract_city(text: str) -> str:
        """Try to extract city from card text."""
        # Common Russian cities as quick check
        cities = [
            'Москва', 'Санкт-Петербург', 'Новосибирск', 'Екатеринбург',
            'Казань', 'Нижний Новгород', 'Челябинск', 'Самара', 'Омск',
            'Ростов-на-Дону', 'Уфа', 'Красноярск', 'Пермь', 'Воронеж',
            'Волгоград', 'Краснодар', 'Саратов', 'Тюмень', 'Тольятти',
        ]
        for city in cities:
            if city in text:
                return city
        return ''

    @staticmethod
    def _extract_age(text: str) -> Optional[str]:
        """Try to extract age from card text."""
        # Patterns like "25 лет", "32 года", "21 год"
        match = re.search(r'(\d{1,2})\s*(?:лет|год[а]?)', text)
        if match:
            age = int(match.group(1))
            if 14 <= age <= 99:
                return f"{age}"

        # Birth year pattern
        match = re.search(r'(?:р\.\s*)?(\d{4})\s*(?:г\.р\.|года рождения)?', text)
        if match:
            year = int(match.group(1))
            if 1930 <= year <= 2010:
                import datetime
                age = datetime.date.today().year - year
                return f"{age}"

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
            'instagram': r'instagram\.com/([a-zA-Z][a-zA-Z0-9_.]+)',
            'facebook': r'facebook\.com/([a-zA-Z][a-zA-Z0-9_.]+)',
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

    @property
    def captcha_blocked(self) -> bool:
        """Whether a CAPTCHA was hit during the last search."""
        return self._captcha_hit

    def close(self):
        """Clean up resources. Browser singleton stays alive for reuse."""
        pass

    @classmethod
    def shutdown_browser(cls):
        """Fully shut down the singleton browser (call on server shutdown)."""
        if cls._browser:
            try:
                cls._browser.close()
            except Exception as e:
                logger.debug(f"[YandexSearch] Browser close on shutdown: {e}")
            cls._browser = None
        if cls._playwright:
            try:
                cls._playwright.stop()
            except Exception as e:
                logger.debug(f"[YandexSearch] Playwright stop on shutdown: {e}")
            cls._playwright = None
        logger.info("Yandex Playwright: browser shut down")


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

    YandexNameSearch.shutdown_browser()
