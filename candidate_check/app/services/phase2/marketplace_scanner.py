"""
Russian Marketplace / Classifieds Scanner
==========================================
Mines contact info from Russian classifieds (Avito, Youla, CIAN, Auto.ru,
VK Market, Yandex Search). Russians post real phone numbers on every listing --
often the most reliable source of phone numbers for a target.
Uses requests with realistic headers, 2-5s delays, graceful error handling.
"""

import logging
import os
import random
import re
import time
from dataclasses import dataclass, field
from typing import List, Optional, Set
from urllib.parse import quote_plus, urljoin

import requests
from bs4 import BeautifulSoup

from app.utils.phone import normalize_phone

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

logger = logging.getLogger(__name__)

PHONE_PATTERN = re.compile(
    r'(?:\+7|8)[\s\-]*\(?\d{3}\)?[\s\-]*\d{3}[\s\-]?\d{2}[\s\-]?\d{2}'
)
EMAIL_PATTERN = re.compile(
    r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
)
EMAIL_BLACKLIST = {
    'support@avito.ru', 'noreply@avito.ru', 'help@avito.ru',
    'support@youla.ru', 'noreply@youla.ru', 'support@cian.ru',
    'noreply@cian.ru', 'support@auto.ru', 'noreply@auto.ru',
    'example@example.com', 'test@test.com',
}
DEFAULT_USER_AGENT = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
    'AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/122.0.0.0 Safari/537.36'
)


@dataclass
class MarketplaceListing:
    """A single classified listing found on a marketplace."""
    title: str = ""
    url: str = ""
    phone: str = ""
    email: str = ""
    seller_name: str = ""
    city: str = ""
    date: str = ""
    price: str = ""
    source: str = ""
    category: str = ""  # listing category (reveals interests/profession)


@dataclass
class ScannerResult:
    """Result from a single marketplace scanner."""
    source: str = ""
    listings: List[MarketplaceListing] = field(default_factory=list)
    phones_found: List[str] = field(default_factory=list)
    emails_found: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "listings": [{"title": l.title, "url": l.url, "phone": l.phone,
                          "email": l.email, "seller_name": l.seller_name,
                          "city": l.city, "date": l.date,
                          "category": l.category} for l in self.listings],
            "phones_found": self.phones_found,
            "emails_found": self.emails_found,
        }


class MarketplaceScanner:
    """Base class for all marketplace scanners."""
    name: str = "base"
    base_url: str = ""

    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': DEFAULT_USER_AGENT,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
        })

    def _random_delay(self):
        """Sleep 2-5 seconds between requests."""
        time.sleep(random.uniform(2.0, 5.0))

    def _safe_get(self, url: str, timeout: float = 15.0) -> Optional[requests.Response]:
        """GET with error handling."""
        try:
            resp = self.session.get(url, timeout=timeout, allow_redirects=True)
            if resp.status_code == 200:
                return resp
            self.logger.warning("%s HTTP %d for %s", self.name, resp.status_code, url)
        except requests.RequestException as exc:
            self.logger.warning("%s request error: %s", self.name, exc)
        return None

    def _extract_phones(self, text: str) -> List[str]:
        """Extract and normalize Russian phone numbers from text."""
        seen: Set[str] = set()
        phones: List[str] = []
        for raw in PHONE_PATTERN.findall(text):
            n = normalize_phone(raw)
            if n and len(n) == 12 and n not in seen:
                seen.add(n)
                phones.append(n)
        return phones

    def _extract_emails(self, text: str) -> List[str]:
        """Extract email addresses, filtering service emails."""
        seen: Set[str] = set()
        emails: List[str] = []
        for raw in EMAIL_PATTERN.findall(text):
            low = raw.lower()
            if low not in seen and low not in EMAIL_BLACKLIST:
                seen.add(low)
                emails.append(low)
        return emails

    def _fetch_and_parse(self, url: str, result: ScannerResult,
                         item_sel: str, title_sel: str, link_sel: str = None,
                         fallback_sels: List[str] = None):
        """Common fetch+parse: get URL, select items, extract contacts."""
        resp = self._safe_get(url)
        if not resp:
            result.errors.append(f"Failed to fetch {self.name} results")
            return
        soup = BeautifulSoup(resp.text, 'html.parser')
        items = soup.select(item_sel)
        if not items and fallback_sels:
            for fs in fallback_sels:
                items = soup.select(fs)
                if items:
                    break
        self.logger.info("%s: found %d items", self.name, len(items))
        for item in items[:10]:
            listing = MarketplaceListing(source=self.name)
            el = item.select_one(title_sel)
            if el:
                listing.title = el.get_text(strip=True)
                href = el.get('href')
                if href:
                    listing.url = urljoin(self.base_url, href)
            if link_sel and not listing.url:
                lnk = item.select_one(link_sel)
                if lnk and lnk.get('href'):
                    listing.url = urljoin(self.base_url, lnk['href'])
            txt = item.get_text()
            phones = self._extract_phones(txt)
            emails = self._extract_emails(txt)
            if phones:
                listing.phone = phones[0]
                result.phones_found.extend(phones)
            if emails:
                listing.email = emails[0]
                result.emails_found.extend(emails)
            if listing.title:
                result.listings.append(listing)
        result.phones_found = list(dict.fromkeys(result.phones_found))
        result.emails_found = list(dict.fromkeys(result.emails_found))

    def search_by_name(self, full_name: str, city: str = None) -> ScannerResult:
        return ScannerResult(source=self.name)

    def search_by_phone(self, phone: str) -> ScannerResult:
        return ScannerResult(source=self.name)


class AvitoScanner(MarketplaceScanner):
    """Avito.ru — largest Russian classifieds platform.

    Two extraction modes:
    1. HTTP (fast): Scrapes search results, extracts phones from listing text.
       Phones are rarely visible in search results since Avito hides them.
    2. Playwright (deep): Opens top listings, clicks "Показать номер" button
       to reveal the seller's actual phone. Much more reliable but slower.
    """
    name = "avito"
    base_url = "https://www.avito.ru"

    # Max listings to deep-extract phones from via Playwright
    MAX_DEEP_LISTINGS = 5

    USER_AGENTS = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) '
        'Gecko/20100101 Firefox/132.0',
    ]

    def search_by_name(self, full_name: str, city: str = None) -> ScannerResult:
        self.logger.info("Avito: searching name='%s' city=%s", full_name, city)
        result = ScannerResult(source=self.name)
        region = quote_plus(city.lower()) if city else "rossiya"
        url = f"{self.base_url}/{region}?q={quote_plus(full_name)}"

        # Try Playwright deep extraction first (clicks "Показать номер")
        if PLAYWRIGHT_AVAILABLE:
            try:
                self._search_with_playwright(url, full_name, result)
                if result.phones_found:
                    return result
            except Exception as exc:
                self.logger.warning("Avito Playwright search failed: %s", exc)

        # Fallback to HTTP scraping
        self._fetch_and_parse(
            url, result,
            item_sel='[data-marker="item"]',
            title_sel='[itemprop="name"]',
            link_sel='a[itemprop="url"]',
        )
        return result

    def search_by_phone(self, phone: str) -> ScannerResult:
        """Search Avito by phone — confirms phone belongs to subject if listing name matches."""
        self.logger.info("Avito: searching phone='%s'", phone)
        result = ScannerResult(source=self.name)
        url = f"{self.base_url}/rossiya?q={quote_plus(phone)}"

        if PLAYWRIGHT_AVAILABLE:
            try:
                self._search_with_playwright(url, phone, result)
                if result.listings:
                    return result
            except Exception as exc:
                self.logger.warning("Avito Playwright phone search failed: %s", exc)

        self._fetch_and_parse(
            url, result,
            item_sel='[data-marker="item"]',
            title_sel='[itemprop="name"]',
            link_sel='a[itemprop="url"]',
        )
        return result

    def _search_with_playwright(self, search_url: str, query: str,
                                result: ScannerResult):
        """Use Playwright to search Avito and extract phones by clicking 'Показать номер'.

        Flow:
        1. Navigate to search results page
        2. Collect listing URLs from search results
        3. For each listing (up to MAX_DEEP_LISTINGS):
           a. Navigate to listing page
           b. Click "Показать номер" button
           c. Extract revealed phone number
           d. Extract seller name, city, category
        """
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=['--disable-blink-features=AutomationControlled'],
            )
            try:
                context = browser.new_context(
                    user_agent=random.choice(self.USER_AGENTS),
                    locale='ru-RU',
                    viewport={'width': 1280, 'height': 720},
                )
                page = context.new_page()
                page.set_default_timeout(15000)

                # Anti-detection
                page.add_init_script(
                    'Object.defineProperty(navigator, "webdriver", '
                    '{get: () => undefined})'
                )

                # Navigate to search results
                page.goto(search_url, wait_until='domcontentloaded', timeout=30000)
                time.sleep(random.uniform(2.0, 4.0))

                # Check for anti-bot / CAPTCHA
                body_text = page.locator('body').inner_text()
                if 'captcha' in body_text.lower() or 'доступ ограничен' in body_text.lower():
                    self.logger.warning("Avito: anti-bot detected on search page")
                    result.errors.append("Avito anti-bot detected")
                    return

                # Collect listing URLs from search results
                listing_links = page.locator(
                    '[data-marker="item"] a[itemprop="url"], '
                    '[data-marker="item"] [itemprop="name"]'
                ).element_handles()

                listing_urls = []
                for link in listing_links[:self.MAX_DEEP_LISTINGS * 2]:
                    href = link.get_attribute('href')
                    if href and '/item/' in href:
                        full_url = urljoin(self.base_url, href)
                        if full_url not in listing_urls:
                            listing_urls.append(full_url)

                self.logger.info("Avito: found %d listing URLs", len(listing_urls))

                # Visit each listing and extract phone
                for listing_url in listing_urls[:self.MAX_DEEP_LISTINGS]:
                    try:
                        self._extract_listing_phone(
                            page, listing_url, result,
                        )
                    except Exception as exc:
                        self.logger.debug("Avito listing extraction error: %s", exc)

                    time.sleep(random.uniform(2.0, 5.0))

            finally:
                browser.close()

    def _extract_listing_phone(self, page, listing_url: str,
                               result: ScannerResult):
        """Navigate to a single Avito listing and extract the phone number."""
        page.goto(listing_url, wait_until='domcontentloaded', timeout=30000)
        time.sleep(random.uniform(1.5, 3.0))

        listing = MarketplaceListing(source=self.name, url=listing_url)

        # Extract title
        title_el = page.locator('h1[itemprop="name"], h1[data-marker="item-view/title-info"]')
        if title_el.count() > 0:
            listing.title = title_el.first.inner_text().strip()

        # Extract seller name
        seller_el = page.locator(
            '[data-marker="seller-info/name"], '
            '[class*="seller-info"] [class*="name"], '
            '[data-marker="item-view/seller-info"]'
        )
        if seller_el.count() > 0:
            listing.seller_name = seller_el.first.inner_text().strip()

        # Extract city from breadcrumbs or location
        city_el = page.locator(
            '[class*="geo-root"], '
            '[data-marker="item-address"], '
            '[class*="item-address"]'
        )
        if city_el.count() > 0:
            listing.city = city_el.first.inner_text().strip()

        # Extract price
        price_el = page.locator(
            '[itemprop="price"], '
            '[data-marker="item-view/item-price"]'
        )
        if price_el.count() > 0:
            listing.price = price_el.first.inner_text().strip()

        # Click "Показать номер" to reveal phone
        show_phone_btn = page.locator(
            '[data-marker="item-phone-button/phone-button"], '
            'button:has-text("Показать"), '
            '[class*="phone-button"]'
        )
        if show_phone_btn.count() > 0:
            try:
                show_phone_btn.first.click()
                time.sleep(random.uniform(1.0, 2.0))

                # After click, phone appears in a container
                phone_el = page.locator(
                    '[data-marker="item-phone-button/phone"], '
                    'a[href^="tel:"], '
                    '[class*="phone-number"]'
                )
                if phone_el.count() > 0:
                    raw_phone = phone_el.first.inner_text().strip()
                    phones = self._extract_phones(raw_phone)
                    if phones:
                        listing.phone = phones[0]
                        result.phones_found.extend(phones)
                        self.logger.info(
                            "Avito: extracted phone %s from '%s'",
                            phones[0], listing.title[:50],
                        )
                else:
                    # Try extracting from href="tel:..." links
                    tel_links = page.locator('a[href^="tel:"]')
                    if tel_links.count() > 0:
                        href = tel_links.first.get_attribute('href') or ''
                        raw_phone = href.replace('tel:', '')
                        phones = self._extract_phones(raw_phone)
                        if phones:
                            listing.phone = phones[0]
                            result.phones_found.extend(phones)
            except Exception as exc:
                self.logger.debug("Avito phone reveal failed: %s", exc)

        # Also extract email from page text
        page_text = page.locator('body').inner_text()
        emails = self._extract_emails(page_text)
        if emails:
            listing.email = emails[0]
            result.emails_found.extend(emails)

        if listing.title:
            result.listings.append(listing)

        result.phones_found = list(dict.fromkeys(result.phones_found))
        result.emails_found = list(dict.fromkeys(result.emails_found))


class YoulaScanner(MarketplaceScanner):
    """Youla.ru — second largest Russian classifieds."""
    name = "youla"
    base_url = "https://youla.ru"

    def search_by_name(self, full_name: str, city: str = None) -> ScannerResult:
        self.logger.info("Youla: searching name='%s' city=%s", full_name, city)
        result = ScannerResult(source=self.name)
        url = f"{self.base_url}/all?q={quote_plus(full_name)}"
        self._fetch_and_parse(
            url, result,
            item_sel='li[class*="product"]',
            title_sel='a[class*="title"], h3, [class*="name"]',
            fallback_sels=['[class*="card"]'],
        )
        return result

    def search_by_phone(self, phone: str) -> ScannerResult:
        self.logger.info("Youla: searching phone='%s'", phone)
        result = ScannerResult(source=self.name)
        url = f"{self.base_url}/all?q={quote_plus(phone)}"
        self._fetch_and_parse(
            url, result,
            item_sel='li[class*="product"]',
            title_sel='a[class*="title"], h3, [class*="name"]',
            fallback_sels=['[class*="card"]'],
        )
        return result


class CianScanner(MarketplaceScanner):
    """CIAN.ru — Russian real estate platform. Landlords always post phones."""
    name = "cian"
    base_url = "https://cian.ru"

    def _build_url(self, query: str) -> str:
        return (
            f"{self.base_url}/cat.php?deal_type=sale&engine_version=2"
            f"&offer_type=flat&region=1&text={quote_plus(query)}"
        )

    def search_by_name(self, full_name: str, city: str = None) -> ScannerResult:
        self.logger.info("CIAN: searching name='%s' city=%s", full_name, city)
        result = ScannerResult(source=self.name)
        self._fetch_and_parse(
            self._build_url(full_name), result,
            item_sel='[data-name="CardComponent"]',
            title_sel='[data-name="LinkArea"] a, a[class*="title"]',
            fallback_sels=['[class*="offer"]'],
        )
        return result

    def search_by_phone(self, phone: str) -> ScannerResult:
        self.logger.info("CIAN: searching phone='%s'", phone)
        result = ScannerResult(source=self.name)
        self._fetch_and_parse(
            self._build_url(phone), result,
            item_sel='[data-name="CardComponent"]',
            title_sel='[data-name="LinkArea"] a, a[class*="title"]',
            fallback_sels=['[class*="offer"]'],
        )
        return result


class AutoRuScanner(MarketplaceScanner):
    """Auto.ru — Russian car marketplace. Sellers always include phone."""
    name = "auto_ru"
    base_url = "https://auto.ru"

    def search_by_name(self, full_name: str, city: str = None) -> ScannerResult:
        self.logger.info("Auto.ru: searching name='%s' city=%s", full_name, city)
        result = ScannerResult(source=self.name)
        region = quote_plus(city.lower()) if city else "moskva"
        url = f"{self.base_url}/{region}/cars/all/?query={quote_plus(full_name)}"
        self._fetch_and_parse(
            url, result,
            item_sel='[class*="ListingItem"]',
            title_sel='a[class*="Link"], a[class*="title"]',
            fallback_sels=['[class*="listing-item"]', '[class*="OfferSnippet"]'],
        )
        return result

    def search_by_phone(self, phone: str) -> ScannerResult:
        self.logger.info("Auto.ru: searching phone='%s'", phone)
        result = ScannerResult(source=self.name)
        url = f"{self.base_url}/moskva/cars/all/?query={quote_plus(phone)}"
        self._fetch_and_parse(
            url, result,
            item_sel='[class*="ListingItem"]',
            title_sel='a[class*="Link"], a[class*="title"]',
            fallback_sels=['[class*="listing-item"]', '[class*="OfferSnippet"]'],
        )
        return result


class YandexSearchScanner(MarketplaceScanner):
    """Yandex Search — dork-style queries across marketplace domains."""
    name = "yandex_search"
    base_url = "https://yandex.ru"

    _NAME_QUERIES = ['"{name}" site:avito.ru OR site:youla.ru OR site:cian.ru',
                     '"{name}" {city} телефон', '"{name}" {city} контакты']
    _PHONE_QUERIES = ['"{phone}" site:avito.ru OR site:youla.ru OR site:cian.ru',
                      '"{phone}" site:auto.ru']

    def search_by_name(self, full_name: str, city: str = None) -> ScannerResult:
        self.logger.info("Yandex: searching name='%s' city=%s", full_name, city)
        result = ScannerResult(source=self.name)
        c = city or "Москва"
        for tpl in self._NAME_QUERIES:
            q = tpl.format(name=full_name, city=c)
            self._yandex_query(q, result)
            self._random_delay()
        return result

    def search_by_phone(self, phone: str) -> ScannerResult:
        self.logger.info("Yandex: searching phone='%s'", phone)
        result = ScannerResult(source=self.name)
        for tpl in self._PHONE_QUERIES:
            q = tpl.format(phone=phone)
            self._yandex_query(q, result)
            self._random_delay()
        return result

    def _yandex_query(self, query: str, result: ScannerResult):
        """Execute a single Yandex search and extract contacts from SERP."""
        url = f"{self.base_url}/search/?text={quote_plus(query)}&lr=213"
        resp = self._safe_get(url)
        if not resp:
            result.errors.append(f"Yandex failed: {query[:60]}")
            return
        try:
            soup = BeautifulSoup(resp.text, 'html.parser')
            items = soup.select('[class*="organic"]') or soup.select('[class*="serp-item"]')
            self.logger.info("Yandex: %d organic results", len(items))
            for item in items[:10]:
                listing = MarketplaceListing(source=self.name)
                el = item.select_one('h2 a, [class*="title"] a')
                if el:
                    listing.title = el.get_text(strip=True)
                    listing.url = el.get('href', '')
                snip = item.select_one('[class*="text-container"], [class*="snippet"]')
                txt = snip.get_text() if snip else item.get_text()
                phones = self._extract_phones(txt)
                emails = self._extract_emails(txt)
                if phones:
                    listing.phone = phones[0]
                    result.phones_found.extend(phones)
                if emails:
                    listing.email = emails[0]
                    result.emails_found.extend(emails)
                if listing.title:
                    result.listings.append(listing)
            result.phones_found = list(dict.fromkeys(result.phones_found))
            result.emails_found = list(dict.fromkeys(result.emails_found))
        except Exception as exc:
            self.logger.error("Yandex parse error: %s", exc, exc_info=True)
            result.errors.append(f"Parse error: {exc}")


class VKMarketScanner(MarketplaceScanner):
    """VK Market — marketplace inside VKontakte. Requires VK service token."""
    name = "vk_market"
    base_url = "https://api.vk.com/method"

    def __init__(self, vk_token: str = None):
        super().__init__()
        self.vk_token = vk_token or os.environ.get('VK_SERVICE_TOKEN', '')

    def is_available(self) -> bool:
        return bool(self.vk_token)

    def search_by_name(self, full_name: str, city: str = None) -> ScannerResult:
        self.logger.info("VK Market: searching name='%s'", full_name)
        return self._search_communities(full_name)

    def search_by_phone(self, phone: str) -> ScannerResult:
        self.logger.info("VK Market: searching phone='%s'", phone)
        return self._search_communities(phone)

    def _search_communities(self, query: str) -> ScannerResult:
        result = ScannerResult(source=self.name)
        if not self.is_available():
            result.errors.append("VK_SERVICE_TOKEN not configured")
            return result
        # Search popular marketplace communities
        for owner_id in [-170540544, -134118342]:
            self._search_one(owner_id, query, result)
            self._random_delay()
        return result

    def _search_one(self, owner_id: int, query: str, result: ScannerResult):
        try:
            resp = self.session.get(
                f"{self.base_url}/market.search",
                params={'owner_id': owner_id, 'q': query, 'count': 20,
                        'extended': 1, 'access_token': self.vk_token, 'v': '5.199'},
                timeout=10,
            )
            data = resp.json()
            if 'error' in data:
                msg = data['error'].get('error_msg', 'Unknown')
                self.logger.warning("VK Market API error: %s", msg)
                result.errors.append(f"VK API: {msg}")
                return
            items = data.get('response', {}).get('items', [])
            self.logger.info("VK Market: %d items from %d", len(items), owner_id)
            for item in items:
                listing = MarketplaceListing(source=self.name)
                listing.title = item.get('title', '')
                listing.url = f"https://vk.com/market{owner_id}?w=product{owner_id}_{item.get('id', '')}"
                listing.price = item.get('price', {}).get('text', '')
                desc = item.get('description', '')
                phones = self._extract_phones(desc)
                emails = self._extract_emails(desc)
                if phones:
                    listing.phone = phones[0]
                    result.phones_found.extend(phones)
                if emails:
                    listing.email = emails[0]
                    result.emails_found.extend(emails)
                if listing.title:
                    result.listings.append(listing)
            result.phones_found = list(dict.fromkeys(result.phones_found))
            result.emails_found = list(dict.fromkeys(result.emails_found))
        except Exception as exc:
            self.logger.error("VK Market error: %s", exc, exc_info=True)
            result.errors.append(f"VK Market: {exc}")


class MarketplaceOracle:
    """Orchestrator: runs all scanners, merges results, supports demo mode."""

    # Confidence scores per source
    _CONFIDENCE = {
        "avito": 0.90, "youla": 0.85, "cian": 0.88,
        "auto_ru": 0.85, "yandex_search": 0.70, "vk_market": 0.80,
    }

    def __init__(self, vk_token: str = None, city: str = None):
        self.vk_token = vk_token or os.environ.get('VK_SERVICE_TOKEN', '')
        self.city = city
        self.logger = logging.getLogger(f"{__name__}.MarketplaceOracle")
        self.scanners: List[MarketplaceScanner] = [
            AvitoScanner(), YoulaScanner(), CianScanner(),
            AutoRuScanner(), YandexSearchScanner(),
            VKMarketScanner(vk_token=self.vk_token),
        ]

    def _is_demo_mode(self) -> bool:
        return not os.environ.get('VK_SERVICE_TOKEN')

    def search_by_name(self, full_name: str, city: str = None) -> dict:
        """Search all marketplaces by full name."""
        city = city or self.city
        self.logger.info("Oracle: name='%s' city=%s demo=%s", full_name, city, self._is_demo_mode())
        if self._is_demo_mode():
            return self._demo_results(full_name)
        return self._run_scanners('name', full_name=full_name, city=city)

    def search_by_phone(self, phone: str) -> dict:
        """Search marketplaces by phone number to find associated listings."""
        self.logger.info("Oracle: phone='%s' demo=%s", phone, self._is_demo_mode())
        if self._is_demo_mode():
            return self._demo_phone_results(phone)
        return self._run_scanners('phone', phone=phone)

    def search_all(self, full_name: str = None, phone: str = None, city: str = None) -> dict:
        """Run all searches with available identifiers."""
        city = city or self.city
        self.logger.info("Oracle.search_all: name=%s phone=%s city=%s", full_name, phone, city)
        phones, emails, listings = [], [], []
        seen_p: Set[str] = set()
        seen_e: Set[str] = set()
        for sub in [
            self.search_by_name(full_name, city=city) if full_name else None,
            self.search_by_phone(phone) if phone else None,
        ]:
            if sub is None:
                continue
            for p in sub["phones"]:
                if p["number"] not in seen_p:
                    seen_p.add(p["number"])
                    phones.append(p)
            for e in sub["emails"]:
                if e["email"] not in seen_e:
                    seen_e.add(e["email"])
                    emails.append(e)
            listings.extend(sub["listings"])
        return {"phones": phones, "emails": emails, "listings": listings}

    def _run_scanners(self, mode: str, full_name: str = None,
                      phone: str = None, city: str = None) -> dict:
        """Execute all scanners in the given mode and merge results."""
        all_phones: List[dict] = []
        all_emails: List[dict] = []
        all_listings: List[dict] = []
        all_cities: List[str] = []  # city data for Stage 6 geo intelligence
        seen_p: Set[str] = set()
        seen_e: Set[str] = set()
        for scanner in self.scanners:
            try:
                self.logger.info("Running: %s", scanner.name)
                if mode == 'name':
                    sr = scanner.search_by_name(full_name, city=city)
                else:
                    sr = scanner.search_by_phone(phone)
                conf = self._CONFIDENCE.get(sr.source, 0.70)
                for p in sr.phones_found:
                    if p not in seen_p:
                        seen_p.add(p)
                        ctx = next((l.title for l in sr.listings if l.phone == p), "")
                        all_phones.append({"number": p, "source": sr.source,
                                           "confidence": conf, "context": ctx})
                for e in sr.emails_found:
                    if e not in seen_e:
                        seen_e.add(e)
                        all_emails.append({"email": e, "source": sr.source,
                                           "confidence": conf - 0.05})
                for l in sr.listings:
                    all_listings.append(l.__dict__)
                    # Collect city data for geo intelligence
                    if l.city and l.city.strip():
                        all_cities.append(l.city.strip())
            except Exception as exc:
                self.logger.error("Scanner %s failed: %s", scanner.name, exc, exc_info=True)
        return {
            "phones": all_phones, "emails": all_emails,
            "listings": all_listings, "cities": all_cities,
        }

    # --- Demo data ---

    def _demo_results(self, full_name: str) -> dict:
        """Return realistic demo data for marketplace search by name."""
        self.logger.info("Oracle: demo data for '%s'", full_name)
        first = full_name.strip().split()[0] if full_name.strip() else "Иван"
        return {
            "phones": [
                {"number": "+79161234567", "source": "avito", "confidence": 0.90,
                 "context": f"Продам iPhone 13 Pro Max — {first}"},
                {"number": "+79031112233", "source": "cian", "confidence": 0.88,
                 "context": "Сдам 2-комн. квартиру, Москва, ул. Тверская"},
            ],
            "emails": [
                {"email": "seller.demo@mail.ru", "source": "avito", "confidence": 0.85},
            ],
            "listings": [
                {"title": "Продам iPhone 13 Pro Max 256GB",
                 "url": "https://www.avito.ru/moskva/telefony/iphone_13_pro_max_123456789",
                 "phone": "+79161234567", "email": "seller.demo@mail.ru",
                 "seller_name": first, "city": "Москва", "date": "2024-12-15", "source": "avito"},
                {"title": "Сдам 2-комн. квартиру, 65 м², 15/22 эт.",
                 "url": "https://cian.ru/rent/flat/298765432/",
                 "phone": "+79031112233", "email": "",
                 "seller_name": full_name, "city": "Москва", "date": "2025-01-20", "source": "cian"},
                {"title": "Toyota Camry 3.5 AT, 2019, 45 000 км",
                 "url": "https://auto.ru/cars/used/sale/toyota/camry/1122334455-abcdef/",
                 "phone": "+79161234567", "email": "",
                 "seller_name": first, "city": "Москва", "date": "2025-02-01", "source": "auto_ru"},
            ],
        }

    def _demo_phone_results(self, phone: str) -> dict:
        """Return realistic demo data for marketplace search by phone."""
        self.logger.info("Oracle: demo phone data for '%s'", phone)
        n = normalize_phone(phone) or phone
        return {
            "phones": [
                {"number": n, "source": "yandex_search", "confidence": 0.70,
                 "context": "Найдено в объявлениях на Avito"},
            ],
            "emails": [
                {"email": "demo.user@yandex.ru", "source": "avito", "confidence": 0.80},
            ],
            "listings": [
                {"title": "Ремонт квартир под ключ",
                 "url": "https://www.avito.ru/moskva/predlozheniya_uslug/remont_987654321",
                 "phone": n, "email": "demo.user@yandex.ru",
                 "seller_name": "Мастер Иван", "city": "Москва", "date": "2025-01-10", "source": "avito"},
                {"title": "Продам диван IKEA, б/у",
                 "url": "https://youla.ru/moskva/dom-i-sad/mebel/divan-ikea-abc123",
                 "phone": n, "email": "", "seller_name": "",
                 "city": "Москва", "date": "2025-02-05", "source": "youla"},
            ],
        }
