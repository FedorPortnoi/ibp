"""
ЕФРСБ Bankruptcy Service
========================
Searches for bankruptcy proceedings via bankrot.fedresurs.ru.

Strategy:
1. Try the JSON API endpoint (no auth required)
2. Fall back to Playwright scraper
3. Fall back to manual search URL
"""

import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import List, Optional

import requests

logger = logging.getLogger(__name__)

# Check Playwright availability
PLAYWRIGHT_AVAILABLE = False
try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError as exc:
    logger.info("Playwright unavailable; bankruptcy scraper disabled: %s", exc)

# Active bankruptcy stage keywords
ACTIVE_STAGES = [
    'наблюдение',
    'конкурсное производство',
    'реструктуризация долгов',
    'реализация имущества',
]

COMPLETED_STAGES = [
    'завершено',
    'прекращено',
    'мировое соглашение',
]

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/121.0.0.0 Safari/537.36'
    ),
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
    'Referer': 'https://bankrot.fedresurs.ru/',
}


@dataclass
class BankruptcyRecord:
    """A bankruptcy record from ЕФРСБ."""
    debtor_name: str = ''
    debtor_inn: Optional[str] = None
    debtor_address: Optional[str] = None
    case_number: Optional[str] = None
    court_name: Optional[str] = None
    stage: Optional[str] = None
    arbitration_manager: Optional[str] = None
    publication_date: Optional[str] = None
    is_active: bool = False
    source: str = 'bankrot.fedresurs.ru'
    url: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            'debtor_name': self.debtor_name,
            'debtor_inn': self.debtor_inn,
            'debtor_address': self.debtor_address,
            'case_number': self.case_number,
            'court_name': self.court_name,
            'stage': self.stage,
            'arbitration_manager': self.arbitration_manager,
            'publication_date': self.publication_date,
            'is_active': self.is_active,
            'source': self.source,
            'url': self.url,
            'type': 'bankruptcy',
        }


class BankruptcyService:
    """
    Search ЕФРСБ for bankruptcy proceedings.

    Tries the JSON API first, then Playwright scraper,
    then falls back to a manual search URL.

    Usage:
        svc = BankruptcyService()
        records = svc.search("Иванов Иван Иванович", inn="771234567890")
    """

    # Primary: fedresurs.ru backend API (newer, more reliable)
    FEDRESURS_API_URL = 'https://fedresurs.ru/backend/bankrupts'
    # Fallback: bankrot.fedresurs.ru legacy API
    API_URL = 'https://bankrot.fedresurs.ru/api/v1/debtors'
    SEARCH_URL = 'https://fedresurs.ru/search/person'

    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def search(
        self,
        full_name: str,
        inn: Optional[str] = None,
        dob: Optional[str] = None,
    ) -> List[BankruptcyRecord]:
        """
        Search ЕФРСБ for bankruptcy proceedings.

        Args:
            full_name: "Фамилия Имя Отчество"
            inn: INN (12 digits) for precise matching
            dob: Date of birth "YYYY-MM-DD" for filtering

        Returns:
            List of BankruptcyRecord (may include manual fallback)
        """
        all_records = []

        # Strategy 1: fedresurs.ru backend API (preferred)
        try:
            records = self._search_fedresurs_api(full_name)
            if records is not None:
                all_records.extend(records)
        except Exception as e:
            logger.warning(f"ЕФРСБ fedresurs API name search error: {e}")

        # Strategy 1b: fedresurs API — search by INN (more precise)
        if inn:
            time.sleep(0.5)
            try:
                inn_records = self._search_fedresurs_api(inn)
                if inn_records is not None:
                    existing_keys = {
                        (r.debtor_name, r.case_number) for r in all_records
                    }
                    for r in inn_records:
                        if (r.debtor_name, r.case_number) not in existing_keys:
                            all_records.append(r)
            except Exception as e:
                logger.warning(f"ЕФРСБ fedresurs API INN search error: {e}")

        if all_records:
            filtered = self._filter_results(all_records, full_name, inn, dob)
            return filtered

        # Strategy 2: Legacy bankrot.fedresurs.ru API
        try:
            records = self._search_api(full_name)
            if records is not None:
                all_records.extend(records)
        except Exception as e:
            logger.warning(f"ЕФРСБ legacy API error: {e}")

        if inn and not all_records:
            try:
                inn_records = self._search_api(inn)
                if inn_records is not None:
                    all_records.extend(inn_records)
            except Exception as e:
                logger.warning(f"ЕФРСБ legacy API INN error: {e}")

        if all_records:
            filtered = self._filter_results(all_records, full_name, inn, dob)
            return filtered

        # Strategy 3: Playwright scraper
        if PLAYWRIGHT_AVAILABLE:
            try:
                records = self._search_playwright(full_name)
                if records is not None:
                    filtered = self._filter_results(records, full_name, inn, dob)
                    return filtered
            except Exception as e:
                logger.warning(f"ЕФРСБ Playwright error: {e}")
        else:
            logger.info("Playwright not available — skipping ЕФРСБ web scraper")

        # Strategy 4: Manual fallback
        logger.info("ЕФРСБ: returning manual search URL")
        return self._manual_fallback(full_name)

    # ── fedresurs.ru backend API (preferred) ─────────────────────

    def _search_fedresurs_api(self, search_string: str) -> Optional[List[BankruptcyRecord]]:
        """
        Query the fedresurs.ru backend API.
        Returns None on failure, [] on no results.
        """
        params = {
            'searchString': search_string,
            'isPhysical': 'true',
            'limit': '15',
            'offset': '0',
        }
        headers = {
            **HEADERS,
            'Referer': 'https://fedresurs.ru/search/person',
            'Origin': 'https://fedresurs.ru',
        }

        try:
            r = self.session.get(
                self.FEDRESURS_API_URL,
                params=params,
                headers=headers,
                timeout=self.timeout,
            )
        except requests.RequestException as e:
            logger.warning(f"ЕФРСБ fedresurs API request failed: {e}")
            return None

        if r.status_code != 200:
            logger.warning(f"ЕФРСБ fedresurs API status {r.status_code}")
            return None

        content_type = r.headers.get('Content-Type', '')
        if 'json' not in content_type and 'javascript' not in content_type:
            if '<html' in r.text[:500].lower():
                logger.warning("ЕФРСБ fedresurs API returned HTML instead of JSON")
                return None

        try:
            data = r.json()
        except (ValueError, KeyError):
            logger.warning("ЕФРСБ fedresurs API: invalid JSON response")
            return None

        return self._parse_api_response(data)

    # ── Legacy bankrot.fedresurs.ru API ────────────────────────────

    def _search_api(self, search_string: str) -> Optional[List[BankruptcyRecord]]:
        """
        Query the ЕФРСБ JSON API.
        Returns None on failure, [] on no results.
        """
        params = {
            'searchString': search_string,
            'isPhysical': 'true',
            'limit': '15',
        }

        try:
            r = self.session.get(
                self.API_URL,
                params=params,
                timeout=self.timeout,
            )
        except requests.RequestException as e:
            logger.warning(f"ЕФРСБ API request failed: {e}")
            return None

        if r.status_code != 200:
            logger.warning(f"ЕФРСБ API status {r.status_code}")
            return None

        # Check if response is JSON
        content_type = r.headers.get('Content-Type', '')
        if 'json' not in content_type and 'javascript' not in content_type:
            # Might be HTML (blocked, redirect, etc.)
            if '<html' in r.text[:500].lower():
                logger.warning("ЕФРСБ API returned HTML instead of JSON")
                return None

        try:
            data = r.json()
        except (ValueError, KeyError):
            logger.warning("ЕФРСБ API: invalid JSON response")
            return None

        return self._parse_api_response(data)

    def _parse_api_response(self, data) -> List[BankruptcyRecord]:
        """Parse the JSON API response into BankruptcyRecord objects."""
        records = []

        # The API may return a list directly or wrapped in a key
        items = []
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            # Try common wrapper keys
            for key in ('pageData', 'data', 'debtors', 'results', 'items'):
                if key in data and isinstance(data[key], list):
                    items = data[key]
                    break
            if not items and 'total' not in data:
                # Maybe the dict itself is a single result
                items = [data]

        for item in items:
            if not isinstance(item, dict):
                continue

            # Extract fields — try multiple possible key names
            name = (
                item.get('name')
                or item.get('fullName')
                or item.get('debtorName')
                or ''
            )
            inn = (
                item.get('inn')
                or item.get('INN')
                or item.get('debtorInn')
            )
            address = (
                item.get('address')
                or item.get('debtorAddress')
                or item.get('region')
            )
            case_number = (
                item.get('caseNumber')
                or item.get('case_number')
                or item.get('bankruptcyCaseNumber')
            )
            court = (
                item.get('courtName')
                or item.get('court')
                or item.get('arbitrationCourtName')
            )
            stage = (
                item.get('procedure')
                or item.get('stage')
                or item.get('currentProcedure')
                or item.get('status')
            )
            manager = (
                item.get('arbitrationManagerName')
                or item.get('manager')
                or item.get('trustee')
            )
            pub_date = (
                item.get('publishDate')
                or item.get('date')
                or item.get('registrationDate')
            )

            # Format date if present
            if pub_date:
                pub_date = self._format_date(str(pub_date))

            # Determine if active
            is_active = self._is_active_stage(stage)

            # Build URL to debtor page
            debtor_id = item.get('guid') or item.get('id') or item.get('debtorId')
            url = None
            if debtor_id:
                url = f'https://bankrot.fedresurs.ru/DebtorCard.aspx?id={debtor_id}'

            if name or inn:
                records.append(BankruptcyRecord(
                    debtor_name=name,
                    debtor_inn=inn,
                    debtor_address=address,
                    case_number=case_number,
                    court_name=court,
                    stage=stage,
                    arbitration_manager=manager,
                    publication_date=pub_date,
                    is_active=is_active,
                    source='bankrot.fedresurs.ru',
                    url=url,
                ))

        return records

    # ── Playwright approach ────────────────────────────────────────

    def _search_playwright(self, full_name: str) -> Optional[List[BankruptcyRecord]]:
        """
        Scrape fedresurs.ru search page using Playwright.
        Intercepts XHR API calls for structured JSON data.
        Falls back to HTML parsing.
        Returns None on failure, [] on no results.
        """
        logger.info("ЕФРСБ Playwright: starting web scraper")
        records = []
        api_data = []

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True, timeout=15000)
                try:
                    context = browser.new_context(
                        user_agent=HEADERS['User-Agent'],
                        locale='ru-RU',
                    )
                    page = context.new_page()
                    page.set_default_timeout(self.timeout * 1000)

                    # Intercept API responses to get structured JSON
                    def handle_response(response):
                        try:
                            if '/backend/bankrupts' in response.url and response.status == 200:
                                ct = response.headers.get('content-type', '')
                                if 'json' in ct:
                                    api_data.append(response.json())
                        except Exception:
                            pass

                    page.on('response', handle_response)

                    # Navigate to search page
                    try:
                        page.goto(
                            self.SEARCH_URL,
                            wait_until='networkidle',
                            timeout=self.timeout * 1000,
                        )
                    except Exception as e:
                        logger.debug(f"[BankruptcyService] networkidle timeout: {e}")
                        page.goto(
                            self.SEARCH_URL,
                            wait_until='domcontentloaded',
                            timeout=self.timeout * 1000,
                        )
                        page.wait_for_timeout(5000)

                    # Fill search field — try multiple selectors for both old and new UI
                    search_input = None
                    for sel in [
                        'input[placeholder*="ФИО"]',
                        'input[placeholder*="поиск"]',
                        'input[placeholder*="Поиск"]',
                        'input#SearchString',
                        'input[name="searchString"]',
                        'input[name*="tbSearch"]',
                        '#ctl00_cphBody_tbSearchByAll',
                        'input[type="text"][class*="search"]',
                        'input[type="search"]',
                        'input[type="text"]',
                    ]:
                        loc = page.locator(sel)
                        if loc.count() > 0:
                            search_input = loc.first
                            logger.debug(f"ЕФРСБ Playwright: found input with selector '{sel}'")
                            break

                    if not search_input:
                        logger.warning("ЕФРСБ Playwright: search input not found")
                        return None

                    search_input.fill(full_name)
                    page.wait_for_timeout(500)

                    # Submit search
                    submitted = False
                    for sel in [
                        'button:has-text("Поиск")',
                        'button:has-text("Найти")',
                        'button[type="submit"]',
                        'input[type="submit"]',
                        'input[value="Найти"]',
                        'a:has-text("Найти")',
                        'a:has-text("Поиск")',
                    ]:
                        btn = page.locator(sel)
                        if btn.count() > 0:
                            btn.first.click()
                            submitted = True
                            break

                    if not submitted:
                        search_input.press('Enter')

                    # Wait for results (API response or page render)
                    page.wait_for_timeout(5000)

                    # Prefer intercepted API data
                    if api_data:
                        for data in api_data:
                            records.extend(self._parse_api_response(data))
                    else:
                        # Parse results from page content
                        html = page.content()
                        records = self._parse_playwright_html(html)
                finally:
                    browser.close()

        except Exception as e:
            logger.warning(f"ЕФРСБ Playwright scraper error: {e}")
            return None

        logger.info(f"ЕФРСБ Playwright: found {len(records)} records")
        return records

    def _parse_playwright_html(self, html: str) -> List[BankruptcyRecord]:
        """Parse Playwright-rendered HTML for bankruptcy results."""
        records = []

        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, 'html.parser')
        except ImportError:
            return self._parse_html_regex(html)

        text_content = soup.get_text()
        if 'ничего не найдено' in text_content.lower():
            return []
        if 'По вашему запросу результатов не найдено' in text_content:
            return []

        # Parse results table
        for table in soup.find_all('table'):
            rows = table.find_all('tr')
            if len(rows) < 2:
                continue
            header_text = rows[0].get_text().lower()
            if any(kw in header_text for kw in ['должник', 'дело', 'суд', 'процедура']):
                for row in rows[1:]:
                    rec = self._parse_table_row(row)
                    if rec:
                        records.append(rec)
                if records:
                    return records

        # Parse div/list-based results
        for block in soup.select(
            '.result-item, .debtor-item, [class*="result"], '
            '[class*="debtor"], .search-results li'
        ):
            rec = self._parse_block(block)
            if rec:
                records.append(rec)

        # Last resort: regex
        if not records:
            records = self._parse_html_regex(html)

        return records

    def _parse_table_row(self, row) -> Optional[BankruptcyRecord]:
        """Parse a results table row."""
        cells = row.find_all('td')
        if len(cells) < 2:
            return None

        texts = [c.get_text(strip=True) for c in cells]
        full_text = ' '.join(texts)

        # Try to extract name (Cyrillic full name pattern)
        name = ''
        name_m = re.search(
            r'([А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+)?)',
            full_text,
        )
        if name_m:
            name = name_m.group(1)

        # INN
        inn = None
        inn_m = re.search(r'\b(\d{12})\b', full_text)
        if inn_m:
            inn = inn_m.group(1)

        # Case number (pattern: А##-#####/YYYY)
        case_number = None
        case_m = re.search(r'(А\d{2}-\d+/\d{4})', full_text)
        if case_m:
            case_number = case_m.group(1)

        # URL from links
        url = None
        for a in row.find_all('a', href=True):
            href = a['href']
            if 'DebtorCard' in href or 'debtor' in href.lower():
                if href.startswith('/'):
                    url = f'https://bankrot.fedresurs.ru{href}'
                elif href.startswith('http'):
                    url = href
                break

        # Stage
        stage = None
        for kw in ACTIVE_STAGES + COMPLETED_STAGES:
            if kw in full_text.lower():
                stage = kw.capitalize()
                break

        if not name and not inn:
            return None

        return BankruptcyRecord(
            debtor_name=name,
            debtor_inn=inn,
            case_number=case_number,
            stage=stage,
            is_active=self._is_active_stage(stage),
            source='bankrot.fedresurs.ru (Playwright)',
            url=url,
        )

    def _parse_block(self, block) -> Optional[BankruptcyRecord]:
        """Parse a div/list result block."""
        text = block.get_text(separator='\n')
        full_text = block.get_text(separator=' ')

        name = ''
        name_m = re.search(
            r'([А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+)?)',
            full_text,
        )
        if name_m:
            name = name_m.group(1)

        inn = None
        inn_m = re.search(r'\b(\d{12})\b', full_text)
        if inn_m:
            inn = inn_m.group(1)

        case_number = None
        case_m = re.search(r'(А\d{2}-\d+/\d{4})', full_text)
        if case_m:
            case_number = case_m.group(1)

        url = None
        for a in block.find_all('a', href=True):
            href = a['href']
            if 'DebtorCard' in href or 'debtor' in href.lower():
                if href.startswith('/'):
                    url = f'https://bankrot.fedresurs.ru{href}'
                elif href.startswith('http'):
                    url = href
                break

        stage = None
        for kw in ACTIVE_STAGES + COMPLETED_STAGES:
            if kw in full_text.lower():
                stage = kw.capitalize()
                break

        if not name and not inn:
            return None

        return BankruptcyRecord(
            debtor_name=name,
            debtor_inn=inn,
            case_number=case_number,
            stage=stage,
            is_active=self._is_active_stage(stage),
            source='bankrot.fedresurs.ru (Playwright)',
            url=url,
        )

    def _parse_html_regex(self, html: str) -> List[BankruptcyRecord]:
        """Last-resort regex parser for bankruptcy data in raw HTML."""
        records = []

        # Find arbitration case numbers
        for m in re.finditer(r'(А\d{2}-\d+/\d{4})', html):
            start = max(0, m.start() - 500)
            end = min(len(html), m.end() + 500)
            ctx = html[start:end]

            name_m = re.search(
                r'([А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+)?)',
                ctx,
            )
            inn_m = re.search(r'\b(\d{12})\b', ctx)

            records.append(BankruptcyRecord(
                debtor_name=name_m.group(1) if name_m else '',
                debtor_inn=inn_m.group(1) if inn_m else None,
                case_number=m.group(1),
                is_active=True,
                source='bankrot.fedresurs.ru',
            ))

        return records

    # ── Manual fallback ────────────────────────────────────────────

    def _manual_fallback(self, full_name: str) -> List[BankruptcyRecord]:
        """Return a placeholder record with manual search instructions."""
        return [BankruptcyRecord(
            debtor_name=full_name,
            case_number='Требуется ручная проверка',
            stage='Автоматический поиск недоступен. Проверьте вручную.',
            is_active=False,
            source='manual',
            url=self.SEARCH_URL,
        )]

    # ── Filtering ──────────────────────────────────────────────────

    def _filter_results(
        self,
        records: List[BankruptcyRecord],
        full_name: str,
        inn: Optional[str] = None,
        dob: Optional[str] = None,
    ) -> List[BankruptcyRecord]:
        """
        Filter results to match our candidate.
        INN match is exact. Name match is fuzzy.
        """
        if not records:
            return records

        # If we have INN, records matching INN are definite matches
        if inn:
            inn_matches = [r for r in records if r.debtor_inn == inn]
            if inn_matches:
                return inn_matches

        # Otherwise filter by name similarity
        query_parts = set(full_name.lower().split())

        filtered = []
        for record in records:
            if not record.debtor_name:
                # Keep records without a name (they matched on search query)
                filtered.append(record)
                continue

            record_parts = set(record.debtor_name.lower().split())

            # At least 2 parts must match (last name + first name)
            common = query_parts & record_parts
            if len(common) >= 2:
                filtered.append(record)
            elif len(query_parts) == 2 and len(common) >= 1:
                # If query has only 2 parts, 1 match is enough
                # but only if the matching part is the last name (first word)
                query_last = full_name.lower().split()[0]
                if query_last in record_parts:
                    filtered.append(record)

        return filtered if filtered else records

    # ── Helpers ────────────────────────────────────────────────────

    @staticmethod
    def _is_active_stage(stage: Optional[str]) -> bool:
        """Determine if a bankruptcy stage indicates an active proceeding."""
        if not stage:
            return True  # Unknown stage — assume active
        stage_lower = stage.lower()
        for completed in COMPLETED_STAGES:
            if completed in stage_lower:
                return False
        return True

    @staticmethod
    def _format_date(date_str: str) -> str:
        """Normalize date to DD.MM.YYYY format."""
        # Already DD.MM.YYYY
        if re.match(r'^\d{2}\.\d{2}\.\d{4}$', date_str):
            return date_str
        # YYYY-MM-DD
        m = re.match(r'^(\d{4})-(\d{2})-(\d{2})', date_str)
        if m:
            return f"{m.group(3)}.{m.group(2)}.{m.group(1)}"
        # ISO datetime
        m = re.match(r'^(\d{4})-(\d{2})-(\d{2})T', date_str)
        if m:
            return f"{m.group(3)}.{m.group(2)}.{m.group(1)}"
        return date_str
