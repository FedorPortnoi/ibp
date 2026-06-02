"""
Court Record Search - Russian Court Cases
==========================================
Search multiple court databases for case history.

Sources:
- sudact.ru: JS-rendered, requires Playwright for results
- судебныерешения.рф: PHP site, session-based search (plain requests)
- reputation.su: Nuxt 3 SSR, 58M+ cases (plain requests)
- kad.arbitr.ru: Geo-blocked (HTTP 451) for non-Russian IPs.
  The site uses DDoS Guard with IP-based geo-restriction.
  Even Playwright with full browser sessions returns 451 on the
  /Kad/SearchInstances POST endpoint from outside Russia.
  Attempts made: session cookies, X-Requested-With, pr_fp cookie,
  Playwright in-page fetch with credentials:include — all blocked.
  Manual fallback URL is provided so users can open it directly.
- All provide manual search URL fallbacks
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

# --- Role classification keywords ---
_PLAINTIFF_KEYWORDS = ['истец', 'заявитель', 'взыскатель']
_DEFENDANT_KEYWORDS = ['ответчик', 'должник', 'обвиняемый', 'подсудимый']


def classify_court_role(case_text: str, full_name: str) -> str:
    """Classify the candidate's role in a court case.

    Looks for the candidate's name in the case text and checks a window
    of 100 characters before and after for plaintiff/defendant keywords.
    Falls back to a global keyword scan if the name is not found in text.

    Returns: 'plaintiff', 'defendant', or 'unknown'
    """
    if not case_text or not full_name:
        return 'unknown'

    text_lower = case_text.lower()
    name_lower = full_name.lower().strip()

    # Build name variants to search for (full name and last+first)
    name_parts = name_lower.split()
    name_variants = [name_lower]
    if len(name_parts) >= 2:
        # "Фамилия Имя" without patronymic
        name_variants.append(f"{name_parts[0]} {name_parts[1]}")

    # Try proximity-based detection: find name in text, check surrounding context
    for variant in name_variants:
        pos = text_lower.find(variant)
        if pos != -1:
            # Extract window around the name
            window_start = max(0, pos - 100)
            window_end = min(len(text_lower), pos + len(variant) + 100)
            window = text_lower[window_start:window_end]

            plaintiff_score = sum(1 for kw in _PLAINTIFF_KEYWORDS if kw in window)
            defendant_score = sum(1 for kw in _DEFENDANT_KEYWORDS if kw in window)

            if plaintiff_score > defendant_score:
                return 'plaintiff'
            elif defendant_score > plaintiff_score:
                return 'defendant'

    # Fallback: global keyword scan (no name proximity)
    plaintiff_found = any(kw in text_lower for kw in _PLAINTIFF_KEYWORDS)
    defendant_found = any(kw in text_lower for kw in _DEFENDANT_KEYWORDS)

    if plaintiff_found and not defendant_found:
        return 'plaintiff'
    elif defendant_found and not plaintiff_found:
        return 'defendant'

    return 'unknown'


def get_frequent_plaintiff_flag(court_records: list) -> dict | None:
    """Return a risk flag dict if the candidate is plaintiff in 3+ cases.

    Args:
        court_records: list of court record dicts (with 'role' field).

    Returns:
        A risk flag dict or None.
    """
    plaintiff_count = sum(
        1 for r in court_records
        if r.get('role') in ('plaintiff', 'истец')
    )
    if plaintiff_count >= 3:
        return {
            'type': 'fact',
            'code': 'frequent_plaintiff',
            'description': 'Часто инициирует судебные разбирательства (3+ дел как истец)',
            'severity': 'low',
        }
    return None


# Check Playwright availability
PLAYWRIGHT_AVAILABLE = False
try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError as exc:
    logger.info("Playwright unavailable; court scraper disabled: %s", exc)


# Criminal article category mapping
ARTICLE_CATEGORIES = {
    "105": "убийство", "106": "убийство", "107": "убийство",
    "111": "тяжкий вред здоровью", "112": "вред здоровью", "115": "вред здоровью",
    "158": "кража", "159": "мошенничество", "160": "присвоение",
    "161": "грабёж", "162": "разбой", "163": "вымогательство",
    "204": "коммерческий подкуп", "290": "взятка", "291": "взятка",
    "222": "оружие", "223": "оружие",
    "228": "наркотики", "229": "наркотики", "230": "наркотики",
    "264": "ДТП", "318": "насилие над сотрудником", "319": "оскорбление сотрудника",
}


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
    raw_text: str = ""
    criminal_articles: list = None
    verdict: str = ""

    def __post_init__(self):
        if self.criminal_articles is None:
            self.criminal_articles = []

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
            'confidence': self.confidence,
            'raw_text': self.raw_text,
            'criminal_articles': self.criminal_articles,
            'verdict': self.verdict,
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

        Sources (in order):
        1. sudact.ru — Playwright, then basic requests fallback
        2. судебныерешения.рф — session-based PHP search (plain requests)
        3. reputation.su — Nuxt 3 SSR search (plain requests)
        """
        results = []
        name = full_name.strip()
        if not name:
            return results

        logger.info(f"Court search: starting for '{name}' (Playwright={'available' if PLAYWRIGHT_AVAILABLE else 'unavailable'})")

        # --- Source 1: sudact.ru (Playwright + basic fallback) ---
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

        # --- Source 2: судебныерешения.рф ---
        try:
            sr_results = self._search_sudebnye_resheniya(name, limit)
            results.extend(sr_results)
        except Exception as e:
            logger.warning(f"Court search: судебныерешения.рф failed: {e}")

        # --- Source 3: reputation.su ---
        try:
            from app.services.phase3.reputation_su_service import search_reputation_su
            rep_cases = search_reputation_su(name)
            for rc in rep_cases:
                case = CourtCase(
                    case_number=rc.get('case_number', ''),
                    court_name=rc.get('court_name', ''),
                    case_type=rc.get('case_type', ''),
                    date=rc.get('date', ''),
                    role=rc.get('role', ''),
                    url=rc.get('url', ''),
                    source='reputation.su',
                    confidence='medium',
                )
                if case.case_number:
                    results.append(case)
            logger.info(f"Court search: reputation.su returned {len(rep_cases)} cases")
        except Exception as e:
            logger.warning(f"Court search: reputation.su failed: {e}")

        # Deduplicate by case number
        seen = set()
        unique = []
        for case in results:
            key = case.case_number
            if key and key not in seen:
                seen.add(key)
                unique.append(case)
            elif not key:
                # Keep cases without a number (rare edge case)
                unique.append(case)

        logger.info(f"Court search: total {len(unique)} unique cases for '{name}'")
        return unique[:limit]

    def _search_sudebnye_resheniya(self, name: str, limit: int = 20) -> List[CourtCase]:
        """Search судебныерешения.рф (xn--90afdbaav0bd1afy6eub5d.xn--p1ai).

        Two-step session flow:
        1. GET form page -> extract CSRF _token
        2. POST /simple_filter with person name -> follow redirect to /search
        3. Parse HTML table results
        """
        base = 'https://xn--90afdbaav0bd1afy6eub5d.xn--p1ai'
        results = []

        try:
            session = requests.Session()
            session.headers.update(self.HEADERS)

            # Step 1: GET form page to obtain CSRF token + session cookie
            logger.info(f"судебныерешения.рф: fetching form page")
            resp = session.get(base + '/', timeout=self.timeout)
            if resp.status_code != 200:
                logger.warning(f"судебныерешения.рф: form page HTTP {resp.status_code}")
                return results

            # Extract CSRF token — name and value may be separated by other attrs
            token_match = re.search(
                r'<input[^>]+name="simpleSearch\[_token\]"[^>]+value="([^"]+)"',
                resp.text,
            )
            if not token_match:
                # Reverse order: value before name
                token_match = re.search(
                    r'<input[^>]+value="([^"]+)"[^>]+name="simpleSearch\[_token\]"',
                    resp.text,
                )
            if not token_match:
                # Broadest fallback: find by id
                token_match = re.search(
                    r'id="simpleSearch__token"[^>]+value="([^"]+)"', resp.text
                )
            if not token_match:
                logger.warning("судебныерешения.рф: CSRF token not found")
                return results

            token = token_match.group(1)
            logger.debug(f"судебныерешения.рф: got CSRF token ({len(token)} chars)")

            # Step 2: POST search with person name
            form_data = {
                'simpleSearch[person_info][0][person]': name,
                'simpleSearch[person_info][0][person_status]': '',
                'simpleSearch[content]': '',
                'simpleSearch[case_number]': '',
                'simpleSearch[case_vid]': '',
                'simpleSearch[case_stage]': '',
                'simpleSearch[_token]': token,
                'simpleSearch[search]': '',
            }

            logger.info(f"судебныерешения.рф: POSTing search for '{name}'")
            resp = session.post(
                base + '/simple_filter',
                data=form_data,
                timeout=self.timeout,
                allow_redirects=True,
            )

            if resp.status_code != 200:
                logger.warning(f"судебныерешения.рф: search HTTP {resp.status_code}")
                return results

            # Step 3: Parse results table
            soup = BeautifulSoup(resp.text, 'lxml')

            # Count info
            count_el = soup.select_one('div.count')
            if count_el:
                logger.info(f"судебныерешения.рф: {count_el.get_text(strip=True)}")

            # Each result is a separate <table class="table table-bordered">
            # inside div#list. Each table has 2 <tr>:
            #   Row 1 (class="active"): court name + case number link
            #   Row 2: dates + participants
            list_div = soup.select_one('#list')
            if not list_div:
                page_text = soup.get_text().lower()
                if 'не найдено' in page_text or 'ничего не найдено' in page_text:
                    logger.info(f"судебныерешения.рф: no results for '{name}'")
                else:
                    logger.debug("судебныерешения.рф: #list div not found")
                return results

            tables = list_div.select('table.table-bordered')
            if not tables:
                logger.debug("судебныерешения.рф: no result tables in #list")
                return results

            for table in tables[:limit]:
                try:
                    rows = table.select('tr')
                    if len(rows) < 2:
                        continue

                    row1, row2 = rows[0], rows[1]

                    # Row 1: court name (td[0]) + case number link (td[1])
                    tds1 = row1.select('td')
                    if len(tds1) < 2:
                        continue

                    court_name = tds1[0].get_text(strip=True)
                    link = tds1[1].select_one('a')
                    if not link:
                        continue

                    case_number_text = link.get_text(strip=True)
                    href = link.get('href', '')
                    url = f"{base}{href}" if href.startswith('/') else href

                    case_match = re.search(
                        r'(\d{1,2}[А-Яа-я]{0,3}-\d+/\d{4})', case_number_text
                    )
                    case_number = case_match.group(1) if case_match else case_number_text

                    # Row 2: dates (td[0]) + participants (td[1])
                    date = ''
                    role = ''
                    tds2 = row2.select('td')
                    if tds2:
                        date_text = tds2[0].get_text(strip=True)
                        date_match = re.search(r'(\d{2}\.\d{2}\.\d{4})', date_text)
                        if date_match:
                            date = date_match.group(1)
                    if len(tds2) > 1:
                        part_text = tds2[1].get_text()
                        role = self._detect_role(part_text, name)

                    case_type = self._detect_case_type(
                        case_number_text + ' ' + court_name
                    )

                    results.append(CourtCase(
                        case_number=case_number,
                        court_name=court_name,
                        case_type=case_type,
                        date=date,
                        role=role,
                        url=url,
                        source='судебныерешения.рф',
                        confidence='high',
                    ))
                except Exception as e:
                    logger.debug(f"судебныерешения.рф: parse table error: {e}")

            logger.info(f"судебныерешения.рф: parsed {len(results)} cases for '{name}'")

        except requests.Timeout:
            logger.warning(f"судебныерешения.рф: timeout for '{name}'")
        except requests.RequestException as e:
            logger.warning(f"судебныерешения.рф: request failed: {e}")
        except Exception as e:
            logger.error(f"судебныерешения.рф: unexpected error: {e}")

        return results

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
                    browser = p.chromium.launch(headless=True, timeout=15000)
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
                    logger.info(f"Sudact Playwright: found {len(results)} cases on attempt {attempt}, fetching details")
                    # Second pass: fetch full text for each case with a URL
                    # Reuse a single browser + page for all detail fetches
                    try:
                        with sync_playwright() as p2:
                            browser2 = p2.chromium.launch(headless=True, timeout=15000)
                            try:
                                detail_page = browser2.new_page()
                                for case in results:
                                    if case.url:
                                        case.raw_text = self._fetch_case_details(detail_page, case.url)
                                        if case.raw_text:
                                            case.criminal_articles = self._extract_criminal_articles(case.raw_text)
                                            case.verdict = self._extract_verdict(case.raw_text)
                                        time.sleep(1)
                            finally:
                                browser2.close()
                    except Exception as e:
                        logger.warning(f"Sudact detail fetch pass failed: {e}")
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
                role=self._detect_role(title, search_name),
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

    def _fetch_case_details(self, page, url: str) -> str:
        """Fetch full text of a court case page.

        Tries Playwright first (25s timeout each for goto + selector wait),
        then falls back to plain requests if Playwright times out — this
        recovers cases even when sudact.ru renders slowly behind anti-bot.

        Args:
            page: An already-open Playwright page object (reused across cases).
            url: The URL of the case detail page.

        Returns:
            The full body text of the page (truncated to 8000 chars), or
            empty string if both methods fail.
        """
        if not url:
            return ""

        # Attempt 1: Playwright with 25s timeouts
        try:
            logger.info(f"Fetching case details: {url}")
            page.goto(url, wait_until='domcontentloaded', timeout=25000)
            page.wait_for_selector(
                '.documenttext, .doc-content, #documenttext', timeout=25000
            )
            content = page.inner_text('body')
            if content and len(content) > 100:
                logger.debug(f"[COURT DETAIL] Playwright OK: {url[:60]}")
                return content[:8000]
        except Exception as e:
            logger.debug(
                f"[COURT DETAIL] Playwright failed ({e}), trying requests: {url[:60]}"
            )

        # Attempt 2: plain requests fallback (no JS, no anti-bot workaround)
        try:
            resp = self.session.get(url, timeout=15)
            if resp.status_code == 200:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(resp.text, 'lxml')
                for tag in soup(['script', 'style', 'nav', 'header', 'footer']):
                    tag.decompose()
                text = soup.get_text(separator=' ', strip=True)
                if text and len(text) > 100:
                    logger.debug(f"[COURT DETAIL] requests OK: {url[:60]}")
                    return text[:8000]
            else:
                logger.debug(
                    f"[COURT DETAIL] requests HTTP {resp.status_code}: {url[:60]}"
                )
        except Exception as e:
            logger.debug(f"[COURT DETAIL] requests also failed: {e}")

        logger.warning(f"[COURT DETAIL] Both methods failed for {url[:60]}")
        return ""

    def _extract_criminal_articles(self, text: str) -> List[Dict]:
        """Extract criminal code articles (УК РФ) from court case text.

        Applies multiple regex patterns and deduplicates results.

        Returns:
            List of dicts with keys: article, part, paragraph, full_text, category.
        """
        if not text:
            return []

        results = []
        seen = set()

        patterns = [
            # п.в ч.2 ст.158 УК РФ (must be before the ч. pattern to capture paragraph)
            (r'п\.\s*([а-яё])\s*ч(?:асть|\.)\s*(\d+)\s*ст(?:атьи|атья|\.)\s*(\d+(?:\.\d+)?)\s*УК\s*РФ',
             'paragraph_part_article'),
            # ч.2 ст.228 УК РФ / ч. 2 ст. 228 УК РФ / часть 2 статьи 228 УК РФ
            (r'ч(?:асть|\.)\s*(\d+)\s*ст(?:атьи|атья|\.)\s*(\d+(?:\.\d+)?)\s*УК\s*РФ',
             'part_article'),
            # ст.228 УК РФ / ст. 228 УК РФ / статьи 228 УК РФ
            (r'ст(?:атьи|атья|\.)\s*(\d+(?:\.\d+)?)\s*УК\s*РФ',
             'article_only'),
            # осуждён/осуждена по статье 228
            (r'осуждён[а]?\s+по\s+ст(?:атье|\.)\s*(\d+(?:\.\d+)?)',
             'convicted_article'),
            # признан виновным по ч.1 ст.228
            (r'признан[а]?\s+виновн(?:ым|ой)\s+по\s+ч\.\s*(\d+)\s*ст\.\s*(\d+(?:\.\d+)?)',
             'guilty_part_article'),
        ]

        for pattern, kind in patterns:
            for m in re.finditer(pattern, text, re.IGNORECASE):
                article = ""
                part = ""
                paragraph = ""

                if kind == 'paragraph_part_article':
                    paragraph = m.group(1)
                    part = m.group(2)
                    article = m.group(3)
                elif kind == 'part_article':
                    part = m.group(1)
                    article = m.group(2)
                elif kind == 'article_only':
                    article = m.group(1)
                elif kind == 'convicted_article':
                    article = m.group(1)
                elif kind == 'guilty_part_article':
                    part = m.group(1)
                    article = m.group(2)

                # Deduplicate by (article, part, paragraph)
                key = (article, part, paragraph)
                if key in seen:
                    continue
                seen.add(key)

                # Look up base article number for category
                base_article = article.split('.')[0]
                category = ARTICLE_CATEGORIES.get(base_article, "")

                results.append({
                    "article": article,
                    "part": part,
                    "paragraph": paragraph,
                    "full_text": m.group(0).strip(),
                    "category": category,
                })

        return results

    def _extract_verdict(self, text: str) -> str:
        """Extract verdict/sentence information from court case text.

        Returns:
            A string describing the verdict, or empty string if not found.
        """
        if not text:
            return ""

        verdict_parts = []

        # Conditional sentence: "условно на срок X лет"
        m = re.search(r'условно\s+(?:на\s+срок\s+)?([\d]+\s*(?:год|лет|года|месяц\w*))', text, re.IGNORECASE)
        if m:
            verdict_parts.append(f"условно {m.group(1)}")

        # Prison sentence: "лишения свободы ... X лет"
        if not verdict_parts:
            m = re.search(r'лишени[яе]\s+свободы\s+(?:на\s+срок\s+)?([\d]+\s*(?:год|лет|года|месяц\w*))', text, re.IGNORECASE)
            if m:
                verdict_parts.append(f"лишение свободы {m.group(1)}")

        # Fine
        m = re.search(r'штраф\w*\s+(?:в\s+размере\s+)?(\d[\d\s]*?)\s*(?:руб|рублей)', text, re.IGNORECASE)
        if m:
            verdict_parts.append(f"штраф {m.group(1).strip()} рублей")

        # Community service
        m = re.search(r'обязательных\s+работ(?:\s+(?:на\s+срок|в\s+количестве)\s+(\d+)\s+часов)?', text, re.IGNORECASE)
        if m:
            hours = m.group(1) if m.group(1) else ""
            verdict_parts.append(f"обязательные работы {hours} часов".strip())

        # Correctional labor
        m = re.search(r'исправительных\s+работ\s+(?:на\s+срок\s+)?([\d]+\s*(?:год|лет|года|месяц\w*))', text, re.IGNORECASE)
        if m:
            verdict_parts.append(f"исправительные работы {m.group(1)}")

        return "; ".join(verdict_parts)

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
        """Detect person's role in court case.

        Uses classify_court_role() for proximity-based detection, then
        maps the result to a Russian-language label. Falls back to legacy
        keyword scan for 'третье лицо' which classify_court_role does not
        handle.
        """
        role = classify_court_role(text, search_name)
        if role == 'plaintiff':
            return "истец"
        elif role == 'defendant':
            return "ответчик"

        # Additional roles not covered by classify_court_role
        text_lower = text.lower()
        if 'третье лицо' in text_lower:
            return "третье лицо"

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
                'name': 'Судебные решения РФ (судебныерешения.рф)',
                'url': f'https://xn--90afdbaav0bd1afy6eub5d.xn--p1ai/',
                'description': 'База судебных решений — 94M+ документов, поиск по ФИО участника'
            },
            {
                'name': 'Reputation.su',
                'url': f'https://reputation.su/search?q={encoded}',
                'description': 'Агрегатор судебных дел — 58M+ дел из ГАС Правосудие'
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
