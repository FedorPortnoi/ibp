"""
Court Record Search - Russian Court Cases
==========================================
Search sudact.ru and arbitration courts for case history.

Source status (as of Feb 2026):
- sudact.ru: JS-rendered, requires Playwright for results
- kad.arbitr.ru: Geo-blocked (HTTP 451) for non-Russian IPs.
  The site uses DDoS Guard with IP-based geo-restriction.
  Even Playwright with full browser sessions returns 451 on the
  /Kad/SearchInstances POST endpoint from outside Russia.
  Attempts made: session cookies, X-Requested-With, pr_fp cookie,
  Playwright in-page fetch with credentials:include — all blocked.
  Manual fallback URL is provided so users can open it directly.
- Both provide manual search URL fallbacks
"""

import logging
import re
import time
from typing import List, Dict, Optional
from dataclasses import dataclass
from urllib.parse import quote, urlencode
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Check Playwright availability
PLAYWRIGHT_AVAILABLE = False
try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    pass


@dataclass
class CourtCase:
    """A court case record."""
    case_number: str
    court_name: str
    case_type: str = ""  # гражданское, уголовное, административное, арбитражное
    date: str = ""
    role: str = ""  # истец, ответчик, третье лицо, участник
    category: str = ""
    result: str = ""
    url: str = ""
    source: str = ""
    confidence: str = "medium"

    def to_dict(self) -> Dict:
        return {
            'case_number': self.case_number,
            'court_name': self.court_name,
            'case_type': self.case_type,
            'date': self.date,
            'role': self.role,
            'category': self.category,
            'result': self.result,
            'url': self.url,
            'source': self.source,
            'confidence': self.confidence
        }


class CourtRecordSearch:
    """
    Search Russian court records.

    Sources:
    - sudact.ru - General courts database (JS-rendered, needs Playwright)
    - kad.arbitr.ru - Arbitration courts (blocked, manual URL only)
    """

    SUDACT_BASE = "https://sudact.ru"
    ARBITR_BASE = "https://kad.arbitr.ru"

    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
    }

    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)

    def search_by_name(
        self,
        full_name: str,
        search_plaintiff: bool = True,
        search_defendant: bool = True,
        limit: int = 50
    ) -> List[CourtCase]:
        """
        Search for court cases involving a person.

        Tries Playwright-based sudact.ru scraping first, falls back to
        basic requests if Playwright unavailable.
        """
        results = []
        name = full_name.strip()
        if not name:
            return results

        logger.info(f"Court search: starting for '{name}' (Playwright={'available' if PLAYWRIGHT_AVAILABLE else 'unavailable'})")

        # Try sudact.ru with Playwright (JS-rendered)
        if PLAYWRIGHT_AVAILABLE:
            try:
                sudact_results = self._search_sudact_playwright(name, limit)
                results.extend(sudact_results)
                logger.info(f"Court search: Sudact Playwright returned {len(sudact_results)} cases")
            except Exception as e:
                logger.warning(f"Court search: Sudact Playwright failed with error: {e}")
        else:
            logger.info("Court search: Playwright not available — sudact.ru requires JS rendering, skipping")

        # Try basic requests as secondary/fallback approach
        if not results:
            logger.info("Court search: trying basic requests fallback for sudact.ru")
            try:
                sudact_basic = self._search_sudact_basic(name, limit)
                results.extend(sudact_basic)
                logger.info(f"Court search: Sudact basic returned {len(sudact_basic)} cases")
            except Exception as e:
                logger.warning(f"Court search: Sudact basic failed with error: {e}")

        # Deduplicate by case number
        seen = set()
        unique = []
        for case in results:
            key = f"{case.case_number}_{case.court_name}"
            if key not in seen:
                seen.add(key)
                unique.append(case)

        logger.info(f"Court search: total {len(unique)} unique cases for '{name}'")
        return unique[:limit]

    def _search_sudact_playwright(self, name: str, limit: int, max_retries: int = 2) -> List[CourtCase]:
        """Search sudact.ru using Playwright for JS rendering."""
        results = []

        # Build the full search URL with all required parameters
        params = {
            'regular-txt': name,
            'regular-case_doc': '',
            'regular-lawchunkinfo': '',
            'regular-date_from': '',
            'regular-date_to': '',
            'regular-workflow_stage': '',
            'regular-area': '',
            'regular-court': '',
            'regular-judge': '',
            '_': '',
        }
        url = f"{self.SUDACT_BASE}/regular/doc/?{urlencode(params)}"
        logger.info(f"Sudact Playwright: fetching URL: {url}")

        for attempt in range(1, max_retries + 1):
            try:
                with sync_playwright() as p:
                    browser = p.chromium.launch(headless=True)
                    try:
                        page = browser.new_page()
                        page.set_default_timeout(self.timeout * 1000)

                        page.goto(url, wait_until='domcontentloaded', timeout=self.timeout * 1000)

                        # Wait for results to render — try multiple selectors
                        # sudact.ru may use different result structures
                        result_selectors = [
                            'ul.results li a[href*="/doc/"]',
                            '.bsr-item',
                            '#resultTable tr',
                            '.result-item',
                            'a[href*="/regular/doc/"]',
                            '.search-results',
                        ]

                        found_selector = None
                        for sel in result_selectors:
                            try:
                                page.wait_for_selector(sel, timeout=8000)
                                found_selector = sel
                                logger.debug(f"Sudact Playwright: matched selector '{sel}' on attempt {attempt}")
                                break
                            except Exception as e:
                                logger.debug(f"[CourtSearch] Selector '{sel}' not found: {e}")
                                continue

                        if not found_selector:
                            # No selector matched — wait a bit for late-loading JS content
                            logger.debug(f"Sudact Playwright: no result selector matched on attempt {attempt}, waiting 5s for JS")
                            page.wait_for_timeout(5000)

                        # Get rendered HTML
                        html = page.content()
                    finally:
                        browser.close()

                soup = BeautifulSoup(html, 'lxml')

                # Parse result list items — try multiple selectors in priority order
                # 1. Standard ul.results > li
                items = soup.select('ul.results > li')
                if items:
                    logger.debug(f"Sudact Playwright: found {len(items)} items via 'ul.results > li'")
                    for item in items[:limit]:
                        case = self._parse_sudact_list_item(item, name)
                        if case:
                            results.append(case)

                # 2. BSR items (alternative layout)
                if not results:
                    items = soup.select('.bsr-item')
                    if items:
                        logger.debug(f"Sudact Playwright: found {len(items)} items via '.bsr-item'")
                        for item in items[:limit]:
                            case = self._parse_sudact_list_item(item, name)
                            if case:
                                results.append(case)

                # 3. Result table rows
                if not results:
                    items = soup.select('#resultTable tr')
                    if items:
                        logger.debug(f"Sudact Playwright: found {len(items)} rows via '#resultTable tr'")
                        for item in items[:limit]:
                            case = self._parse_sudact_item(item, name)
                            if case:
                                results.append(case)

                # 4. Fallback: try document links directly
                if not results:
                    doc_links = soup.select('a[href*="/doc/"]')
                    if doc_links:
                        logger.debug(f"Sudact Playwright: found {len(doc_links)} doc links via 'a[href*=\"/doc/\"]'")
                        for link in doc_links[:limit]:
                            case = self._parse_sudact_doc_link(link, name)
                            if case:
                                results.append(case)

                # 5. Broad fallback: any link to /regular/doc/
                if not results:
                    doc_links = soup.select('a[href*="/regular/doc/"]')
                    if doc_links:
                        logger.debug(f"Sudact Playwright: found {len(doc_links)} links via 'a[href*=\"/regular/doc/\"]'")
                        for link in doc_links[:limit]:
                            case = self._parse_sudact_doc_link(link, name)
                            if case:
                                results.append(case)

                if results:
                    logger.info(f"Sudact Playwright: found {len(results)} cases on attempt {attempt}")
                    return results

                # Log page content size for debugging if no results
                page_text = soup.get_text(strip=True)
                logger.debug(
                    f"Sudact Playwright attempt {attempt}/{max_retries}: "
                    f"no results parsed from {len(html)} bytes HTML, "
                    f"{len(page_text)} chars text content"
                )

                if attempt < max_retries:
                    logger.info(f"Sudact Playwright: retrying in 3s (attempt {attempt}/{max_retries})")
                    time.sleep(3)

            except Exception as e:
                logger.warning(f"Sudact Playwright error (attempt {attempt}/{max_retries}): {e}")
                if attempt < max_retries:
                    time.sleep(3)

        logger.info(f"Sudact Playwright: returning {len(results)} results after {max_retries} attempts")
        return results

    def _parse_sudact_list_item(self, item, search_name: str) -> Optional[CourtCase]:
        """Parse a sudact.ru result list item (ul.results > li)."""
        try:
            link = item.select_one('a[href*="/doc/"]')
            if not link:
                return None

            title = link.get_text(strip=True)
            text = item.get_text()

            # Extract case number from title (e.g. "Решение № 2-6851/2025 от ... по делу № 2-985/2025")
            # Try "по делу №" first (most specific)
            case_match = re.search(r'по делу\s*№?\s*(\d{1,2}[А-Яа-я]{0,3}-\d+/\d{4})', title)
            if not case_match:
                case_match = re.search(r'№\s*(\d{1,2}[А-Яа-я]{0,3}-\d+/\d{4})', title)
            if not case_match:
                case_match = re.search(r'(\d{1,2}[А-Яа-я]{0,3}-\d+/\d{4})', title)
            case_number = case_match.group(1) if case_match else ""

            if not case_number:
                return None

            # Extract court name (appears after the link text in the li)
            court_match = re.search(r'([А-Яа-яёЁ][\w\s\-\.]+(?:суд|СОЮ)[а-яА-Я\w\s\-\.]*?)(?:\s*[-–]\s*|\s*\()', text)
            if court_match:
                court_name = court_match.group(1).strip()
            else:
                # Try to find court name as text after title
                remaining = text.replace(title, '').strip()
                # Remove leading number + dot
                remaining = re.sub(r'^\d+\.', '', remaining).strip()
                # Court name is usually the first significant text
                court_parts = remaining.split(' - ')
                court_name = court_parts[0].strip() if court_parts else "Не указан"
                # Clean up: remove region in parentheses for display
                court_name = re.sub(r'\s*\(.*?\)\s*$', '', court_name).strip()

            if len(court_name) < 5:
                court_name = "Не указан"

            # Extract date from title
            date_match = re.search(r'от\s+(\d{1,2}\s+\w+\s+\d{4})\s+г\.', title)
            date = date_match.group(1) if date_match else ""

            # Case type
            case_type = self._detect_case_type(text)

            # URL
            href = link.get('href', '')
            url = ""
            if href.startswith('/'):
                # Strip query params for cleaner URL
                url = f"{self.SUDACT_BASE}{href.split('?')[0]}"
            elif href.startswith('http'):
                url = href.split('?')[0]

            return CourtCase(
                case_number=case_number,
                court_name=court_name,
                case_type=case_type,
                date=date,
                role=self._detect_role(text, search_name),
                source="sudact.ru",
                url=url,
                confidence="high"
            )
        except Exception as e:
            logger.debug(f"Parse sudact list item error: {e}")
            return None

    def _parse_sudact_doc_link(self, link, search_name: str) -> Optional[CourtCase]:
        """Parse a sudact.ru document link as fallback."""
        try:
            title = link.get_text(strip=True)
            case_match = re.search(r'(\d{1,2}[А-Яа-я]{0,3}-\d+/\d{4})', title)
            if not case_match:
                return None

            href = link.get('href', '')
            url = f"{self.SUDACT_BASE}{href.split('?')[0]}" if href.startswith('/') else href

            date_match = re.search(r'от\s+(\d{1,2}\s+\w+\s+\d{4})', title)
            date = date_match.group(1) if date_match else ""

            return CourtCase(
                case_number=case_match.group(1),
                court_name="Не указан",
                case_type=self._detect_case_type(title),
                date=date,
                role="участник",
                source="sudact.ru",
                url=url,
                confidence="medium"
            )
        except Exception as e:
            logger.debug(f"[CourtSearch] Failed to parse sudact list item: {e}")
            return None

    def _search_sudact_basic(self, name: str, limit: int) -> List[CourtCase]:
        """Search sudact.ru with basic requests (limited — JS-rendered content)."""
        results = []

        # Use the same parameter set as the Playwright method
        params = {
            'regular-txt': name,
            'regular-case_doc': '',
            'regular-lawchunkinfo': '',
            'regular-date_from': '',
            'regular-date_to': '',
            'regular-workflow_stage': '',
            'regular-area': '',
            'regular-court': '',
            'regular-judge': '',
            '_': '',
        }

        url = f"{self.SUDACT_BASE}/regular/doc/"
        logger.info(f"Sudact basic: fetching {url} with name='{name}'")

        try:
            response = self.session.get(
                url,
                params=params,
                timeout=self.timeout
            )

            logger.debug(f"Sudact basic: HTTP {response.status_code}, {len(response.text)} bytes")

            if response.status_code != 200:
                logger.warning(f"Sudact basic: unexpected status {response.status_code}")
                return results

            soup = BeautifulSoup(response.text, 'lxml')

            # Try multiple selectors — sudact.ru may use different structures
            selector_groups = [
                ('ul.results > li', 'list items'),
                ('#resultTable tr', 'table rows'),
                ('.bsr-item', 'BSR items'),
                ('.result-item', 'result items'),
                ('.doc-item', 'doc items'),
            ]

            for selector, label in selector_groups:
                items = soup.select(selector)
                if items:
                    logger.debug(f"Sudact basic: found {len(items)} {label} via '{selector}'")
                    for item in items[:limit]:
                        case = self._parse_sudact_item(item, name)
                        if not case:
                            case = self._parse_sudact_list_item(item, name)
                        if case:
                            results.append(case)
                    if results:
                        break

            # Fallback: doc links
            if not results:
                doc_links = soup.select('a[href*="/doc/"]')
                if doc_links:
                    logger.debug(f"Sudact basic: found {len(doc_links)} doc links as fallback")
                    for link in doc_links[:limit]:
                        case = self._parse_sudact_doc_link(link, name)
                        if case:
                            results.append(case)

            logger.info(f"Sudact basic: parsed {len(results)} cases (note: JS-rendered content may be missing)")

        except requests.RequestException as e:
            logger.warning(f"Sudact basic request failed: {e}")

        return results

    def _parse_sudact_item(self, item, search_name: str) -> Optional[CourtCase]:
        """Parse a Sudact search result item."""
        try:
            text = item.get_text()
            if len(text) < 10:
                return None

            # Case number
            case_match = re.search(r'(\d{1,2}[А-Яа-я]{0,3}-\d+/\d{4})', text)
            if not case_match:
                case_match = re.search(r'(?:Дело|№)[:\s]*([0-9А-Яа-я\-/]+)', text)
            case_number = case_match.group(1) if case_match else ""

            if not case_number:
                return None

            # Court name
            court_elem = item.select_one('.court-name, .court, h3')
            court_name = court_elem.get_text(strip=True) if court_elem else ""
            if not court_name:
                court_match = re.search(r'([\w\s]+(?:суд|СОЮ|районный)[\w\s]*)', text, re.IGNORECASE)
                court_name = court_match.group(1).strip() if court_match else "Не указан"

            # Date
            date_match = re.search(r'(\d{2}[./]\d{2}[./]\d{4})', text)
            date = date_match.group(1) if date_match else ""

            # Case type and role
            case_type = self._detect_case_type(text)
            role = self._detect_role(text, search_name)

            # URL
            link = item.select_one('a[href]')
            url = ""
            if link and link.get('href'):
                href = link['href']
                if href.startswith('/'):
                    url = f"{self.SUDACT_BASE}{href}"
                elif href.startswith('http'):
                    url = href

            return CourtCase(
                case_number=case_number,
                court_name=court_name,
                case_type=case_type,
                date=date,
                role=role,
                url=url,
                source="sudact.ru",
                confidence="high" if case_number else "medium"
            )

        except Exception as e:
            logger.debug(f"Parse error: {e}")
            return None

    def _detect_case_type(self, text: str) -> str:
        """Detect court case type from text."""
        text_lower = text.lower()
        if 'уголовн' in text_lower:
            return "уголовное"
        elif 'административн' in text_lower:
            return "административное"
        elif 'арбитраж' in text_lower:
            return "арбитражное"
        return "гражданское"

    def _detect_role(self, text: str, search_name: str) -> str:
        """Detect person's role in court case."""
        text_lower = text.lower()
        if 'истец' in text_lower:
            return "истец"
        elif 'ответчик' in text_lower:
            return "ответчик"
        elif 'третье лицо' in text_lower:
            return "третье лицо"
        elif 'обвиняем' in text_lower or 'подсудим' in text_lower:
            return "обвиняемый"
        return "участник"

    @staticmethod
    def get_manual_search_urls(name: str) -> List[Dict[str, str]]:
        """
        Generate manual court search URLs for the user.

        Note on kad.arbitr.ru: The automated /Kad/SearchInstances endpoint
        returns HTTP 451 (geo-blocked) for non-Russian IP addresses.
        DDoS Guard IP-blocks the API even with full browser sessions.
        The homepage itself loads fine, so we link directly to it and
        instruct the user to search manually. If you have a Russian VPN,
        you can re-enable automated search — the API accepts:
            POST /Kad/SearchInstances
            Content-Type: application/json
            X-Requested-With: XMLHttpRequest
            x-date-format: iso
            Body: {"Sides":[{"Name":"<name>","Type":-1}],"Page":1,"Count":25,...}
        """
        encoded = quote(name)
        # kad.arbitr.ru: the SPA doesn't support name pre-fill in the URL,
        # but we can pass the name as a fragment hint for user convenience.
        kad_name_hint = quote(name, safe='')
        return [
            {
                'name': 'Судебные акты (sudact.ru)',
                'url': f'https://sudact.ru/regular/doc/?regular-txt={encoded}',
                'description': 'Суды общей юрисдикции — введите имя в поле поиска'
            },
            {
                'name': 'Арбитражные суды (kad.arbitr.ru)',
                'url': f'https://kad.arbitr.ru/',
                'description': (
                    f'Арбитражные (экономические) дела — введите «{name}» в поле «Участники» и нажмите Найти. '
                    'Автоматический поиск недоступен: сайт блокирует запросы с не-российских IP (HTTP 451).'
                )
            },
            {
                'name': 'Портал ГАС Правосудие (sudrf.ru)',
                'url': f'https://bsr.sudrf.ru/bigs/portal.html',
                'description': 'Суды общей юрисдикции — полнотекстовый поиск по всем регионам'
            },
            {
                'name': 'Апелляционные арбитражные суды (ras.arbitr.ru)',
                'url': f'https://ras.arbitr.ru/',
                'description': 'Апелляционные арбитражные суды — поиск по участникам дела'
            },
        ]


# Singleton instance
court_search = CourtRecordSearch()
