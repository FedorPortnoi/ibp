"""
FSSP Search - Federal Bailiff Service (Enforcement Proceedings)
===============================================================
Search for active enforcement proceedings (исполнительные производства).

API Status (as of Feb 2026):
- api-ip.fssp.gov.ru: SHUT DOWN - all endpoints return 404
  (Official statement: "В целях предотвращения кибератак доступ к API остановлен.")
- is-go.fssp.gov.ru/ajax_search: AJAX endpoint, reachable but CAPTCHA-gated
- fssp.gov.ru/iss/ip: Website works (HTTP 200) from outside Russia

Search flow discovered via browser inspection:
  POST https://is-go.fssp.gov.ru/ajax_search
  Params (CP1251-encoded): is[variant]=1, is[last_name], is[first_name], is[date], is[region_id][0]
  Response: JSONP wrapper ({ "data": "<html>", "err": "", "e": "" });
  Always returns CAPTCHA for programmatic requests.
  CAPTCHA: 5-digit image + code_id token.
  After solving: GET same URL + &code=XXXXX&code_id=TOKEN

This module provides:
1. Playwright-based search attempt (fills form, detects CAPTCHA, extracts image)
2. requests-based AJAX probe (fast detection of site availability)
3. Manual search URL generation (always available, pre-filled params in URL)
"""

import asyncio
import base64
import json
import logging
import os
import re
import time
from html import unescape
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from urllib.parse import quote, urlencode

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)


@dataclass
class EnforcementProceeding:
    """An enforcement proceeding from FSSP."""
    debtor_name: str
    proceeding_number: str = ""
    debt_type: str = ""  # алименты, штраф, кредит, госпошлина, etc.
    amount: str = ""     # sum in rubles
    department: str = "" # bailiff department
    bailiff: str = ""    # bailiff name + phone
    date: str = ""
    status: str = ""     # на исполнении, окончено, etc.
    source: str = "ФССП"
    url: str = ""
    details: str = ""

    def to_dict(self) -> Dict:
        return {
            'debtor_name': self.debtor_name,
            'proceeding_number': self.proceeding_number,
            'debt_type': self.debt_type,
            'amount': self.amount,
            'department': self.department,
            'bailiff': self.bailiff,
            'date': self.date,
            'status': self.status,
            'source': self.source,
            'url': self.url,
            'details': self.details,
        }


class FSSPSearch:
    """
    Search FSSP (Federal Bailiff Service) for enforcement proceedings.

    Strategy (in order):
    1. Playwright scraper: loads fssp.gov.ru/iss/ip, fills form, submits.
       - If results found: parse and return them.
       - If CAPTCHA found: extract image and code_id, log for manual resolution.
    2. Direct AJAX probe: fast check of is-go.fssp.gov.ru availability.
    3. Manual URL fallback: always returns a clickable FSSP search URL (safety net).

    The official API (api-ip.fssp.gov.ru) was shut down in 2024/2025.
    """

    # Search page and AJAX endpoint (discovered via browser network inspection)
    SEARCH_PAGE = "https://fssp.gov.ru/iss/ip"
    AJAX_HOST = "https://is-go.fssp.gov.ru"
    AJAX_PATH = "/ajax_search"

    HEADERS = {
        'User-Agent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/120.0.0.0 Safari/537.36'
        ),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
        'Referer': 'https://fssp.gov.ru/iss/ip',
    }

    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        # api_token kept for backward compatibility, but API is shut down
        self.api_token = os.environ.get('FSSP_API_TOKEN', '')

    # -------------------------------------------------------------------------
    # Public search interface
    # -------------------------------------------------------------------------

    def search_by_name(
        self,
        lastname: str,
        firstname: str = "",
        patronymic: str = "",
        region: str = "",
        birthdate: str = "",
        limit: int = 50,
    ) -> List[EnforcementProceeding]:
        """
        Search for enforcement proceedings by person name.

        Args:
            lastname:   Фамилия
            firstname:  Имя
            patronymic: Отчество
            region:     Region code (77=Moscow) or empty for all
            birthdate:  Date of birth DD.MM.YYYY (required by FSSP for individual search)
            limit:      Max results

        Returns:
            List of EnforcementProceeding (empty if CAPTCHA or site down).
        """
        if not lastname:
            return []

        logger.info(f"FSSP search: {lastname} {firstname} {patronymic}")

        # Step 1: Quick availability probe via requests (cheap, fast)
        available = self._probe_site_availability()
        if not available:
            logger.warning("FSSP website unreachable — skipping search")
            return []

        # FSSP website is reachable but CAPTCHA-gated — no automated path available.
        # Pipeline primary is CheckoService; this fallback returns empty so the
        # pipeline continues without blocking on a CAPTCHA solve.
        logger.info("FSSP: no automated search path available (CAPTCHA-gated)")
        return []

    def search_by_full_name(
        self,
        full_name: str,
        region: str = "",
        limit: int = 50,
    ) -> List[EnforcementProceeding]:
        """Convenience method: search by full name string."""
        parts = self.parse_full_name(full_name)
        return self.search_by_name(
            lastname=parts['lastname'],
            firstname=parts['firstname'],
            patronymic=parts['patronymic'],
            region=region,
            limit=limit,
        )

    # -------------------------------------------------------------------------
    # Site probe (requests, fast)
    # -------------------------------------------------------------------------

    def _probe_site_availability(self) -> bool:
        """
        Quick HTTP probe to confirm fssp.gov.ru/iss/ip is reachable.

        Returns True if site returns HTTP 200 (confirmed reachable from outside Russia).
        """
        try:
            r = self.session.get(
                self.SEARCH_PAGE,
                timeout=10,
                verify=False,
                allow_redirects=True,
            )
            available = r.status_code == 200
            if available:
                logger.debug("FSSP site probe: 200 OK")
            else:
                logger.warning(f"FSSP site probe: HTTP {r.status_code}")
            return available
        except requests.Timeout:
            logger.warning("FSSP site probe: timeout — likely geo-blocked or down")
            return False
        except requests.ConnectionError as e:
            logger.warning(f"FSSP site probe: connection error — {e}")
            return False
        except Exception as e:
            logger.warning(f"FSSP site probe error: {e}")
            return False

    # -------------------------------------------------------------------------
    # Playwright-based scraper
    # -------------------------------------------------------------------------

    def _search_playwright(
        self,
        lastname: str,
        firstname: str,
        patronymic: str,
        birthdate: str,
        limit: int,
    ) -> Optional[List[EnforcementProceeding]]:
        """
        Use Playwright to load the FSSP search page, fill the form, and extract results.

        Returns:
            List of results if found.
            Empty list if CAPTCHA encountered (with CAPTCHA details logged).
            None if Playwright unavailable or hard error.
        """
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            logger.warning("Playwright not installed — skipping browser-based FSSP search")
            return None

        try:
            return self._run_playwright_search(
                lastname, firstname, patronymic, birthdate, limit
            )
        except Exception as e:
            logger.warning(f"FSSP Playwright search error: {type(e).__name__}: {e}")
            return None

    def _run_playwright_search(
        self,
        lastname: str,
        firstname: str,
        patronymic: str,
        birthdate: str,
        limit: int,
    ) -> Optional[List[EnforcementProceeding]]:
        """Internal: run Playwright synchronously."""
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-dev-shm-usage'],
                timeout=15000,
            )
            context = browser.new_context(
                user_agent=self.HEADERS['User-Agent'],
                locale='ru-RU',
                extra_http_headers={'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8'},
            )
            page = context.new_page()

            # Capture AJAX response
            ajax_responses: list = []

            def on_response(response):
                if 'ajax_search' in response.url and 'is-go.fssp' in response.url:
                    try:
                        body = response.body()
                        ajax_responses.append({
                            'url': response.url,
                            'body': body.decode('utf-8', errors='replace'),
                        })
                    except Exception as e:
                        logger.debug(f"[FSSPSearch] AJAX response parse failed: {e}")

            page.on('response', on_response)

            try:
                logger.debug("FSSP Playwright: loading search page")
                page.goto(self.SEARCH_PAGE, wait_until='domcontentloaded', timeout=30_000)

                # Wait for search form
                page.wait_for_selector('input[name="is[last_name]"]', timeout=10_000)

                # Fill form fields
                page.fill('input[name="is[last_name]"]', lastname, timeout=10000)
                if firstname:
                    page.fill('input[name="is[first_name]"]', firstname, timeout=10000)
                if patronymic:
                    page.fill('input[name="is[patronymic]"]', patronymic, timeout=10000)

                # Date of birth (required for individual search)
                date_input = page.locator('input[name="is[date]"]')
                if date_input.count() > 0:
                    if birthdate:
                        date_input.fill(birthdate, timeout=10000)
                    else:
                        # Without DOB, the server still accepts the request
                        # but may return more/fewer results
                        pass

                # Submit
                logger.debug("FSSP Playwright: submitting form")
                page.click('#btn-sbm', timeout=10000)

                # Wait for AJAX response (either results or CAPTCHA)
                page.wait_for_timeout(6000)

                if not ajax_responses:
                    logger.warning("FSSP Playwright: no AJAX response captured")
                    return None

                # Parse the AJAX response
                return self._parse_ajax_response(ajax_responses[0], limit, lastname)

            finally:
                page.close()
                context.close()
                browser.close()

    def _parse_ajax_response(
        self,
        ajax_resp: dict,
        limit: int,
        search_name: str,
    ) -> List[EnforcementProceeding]:
        """
        Parse the JSONP-wrapped AJAX response from is-go.fssp.gov.ru/ajax_search.

        Response format:  ({"data": "<html>...", "err": "", "e": ""});

        Returns empty list on CAPTCHA (with CAPTCHA details logged).
        """
        body = ajax_resp.get('body', '')
        stripped = body.strip()

        # Unwrap JSONP: (JSON);  →  JSON
        if stripped.startswith('(') and stripped.endswith(');'):
            stripped = stripped[1:-2]
        elif stripped.startswith('(') and stripped.endswith(')'):
            stripped = stripped[1:-1]

        try:
            obj = json.loads(stripped)
        except json.JSONDecodeError as e:
            logger.warning(f"FSSP AJAX response JSON parse error: {e}")
            return []

        html_data = unescape(obj.get('data', ''))

        # Check for CAPTCHA
        if 'captcha' in html_data.lower():
            self._log_captcha_details(html_data, ajax_resp.get('url', ''))
            return []

        # Parse results table
        results = self._parse_results_html(html_data, limit)
        logger.info(f"FSSP parsed {len(results)} proceedings from HTML")
        return results

    def _log_captcha_details(self, html_data: str, ajax_url: str) -> None:
        """Extract and log CAPTCHA details for diagnostics."""
        code_id_match = re.search(r'name=["\']code_id["\'] value=["\']([^"\']+)["\']', html_data)
        code_id = code_id_match.group(1) if code_id_match else 'unknown'

        # Extract CAPTCHA image and save for inspection
        img_match = re.search(r'src=["\']data:image/png;base64,([^"\']+)["\']', html_data)
        captcha_saved = False
        if img_match:
            try:
                b64 = img_match.group(1)
                # Fix missing padding
                b64 += '=' * (-len(b64) % 4)
                img_bytes = base64.b64decode(b64)
                captcha_path = os.path.join(
                    os.environ.get('TEMP', '/tmp'), 'fssp_captcha.png'
                )
                with open(captcha_path, 'wb') as f:
                    f.write(img_bytes)
                captcha_saved = True
                logger.info(f"FSSP CAPTCHA image saved to {captcha_path}")
            except Exception as e:
                logger.debug(f"Could not save CAPTCHA image: {e}")

        # Extract the retry URL (for manual resolution if needed)
        form_url_match = re.search(r'url=["\'](/ajax_search[^"\']+)["\']', html_data)
        retry_url = ''
        if form_url_match:
            retry_url = self.AJAX_HOST + form_url_match.group(1)

        logger.warning(
            f"FSSP returned CAPTCHA (code_id={code_id}). "
            f"Image saved: {captcha_saved}. "
            f"Retry URL: {retry_url[:100] if retry_url else 'n/a'}"
        )

    def _parse_results_html(
        self, html: str, limit: int
    ) -> List[EnforcementProceeding]:
        """
        Parse FSSP results HTML table.

        The results table uses class 'results-frame' with rows containing:
        - Debtor name + details
        - Enforcement proceeding number
        - Debt type
        - Amount
        - Bailiff department + name
        - Status
        """
        results = []

        # Look for result rows — FSSP uses a table with class 'results-frame'
        # Each result is a <tr> with specific cell layout
        rows = re.findall(
            r'<tr[^>]*class=["\'][^"\']*border[^"\']*["\'][^>]*>([\s\S]*?)</tr>',
            html,
        )

        for row_html in rows[:limit]:
            try:
                proc = self._parse_result_row(row_html)
                if proc:
                    results.append(proc)
            except Exception as e:
                logger.debug(f"Error parsing FSSP row: {e}")

        # Alternative: look for structured result blocks
        if not results:
            results = self._parse_result_blocks(html, limit)

        return results

    def _parse_result_row(self, row_html: str) -> Optional[EnforcementProceeding]:
        """Parse a single FSSP result table row."""
        cells = re.findall(r'<td[^>]*>([\s\S]*?)</td>', row_html)
        if len(cells) < 3:
            return None

        def clean(s):
            return re.sub(r'<[^>]+>', '', s).strip()

        name = clean(cells[0]) if cells else ''
        if not name:
            return None

        return EnforcementProceeding(
            debtor_name=name,
            proceeding_number=clean(cells[1]) if len(cells) > 1 else '',
            debt_type=clean(cells[2]) if len(cells) > 2 else '',
            amount=clean(cells[3]) if len(cells) > 3 else '',
            department=clean(cells[4]) if len(cells) > 4 else '',
            bailiff=clean(cells[5]) if len(cells) > 5 else '',
            date=clean(cells[6]) if len(cells) > 6 else '',
            status='На исполнении',
            source='ФССП',
        )

    def _parse_result_blocks(
        self, html: str, limit: int
    ) -> List[EnforcementProceeding]:
        """
        Alternative parser for FSSP result blocks (used when table format differs).
        Looks for divs with class 'results-body' or 'b-result'.
        """
        results = []
        blocks = re.findall(
            r'class=["\'][^"\']*(?:results-body|b-result)[^"\']*["\'][^>]*>([\s\S]*?)</div>',
            html,
        )
        for block in blocks[:limit]:
            name_match = re.search(r'class=["\'][^"\']*name[^"\']*["\'][^>]*>([^<]+)', block)
            if not name_match:
                continue
            name = name_match.group(1).strip()
            amount_match = re.search(r'(\d[\d\s.,]+)\s*руб', block)
            dept_match = re.search(r'Подразделение[^:]*:\s*([^\n<]+)', block)
            results.append(EnforcementProceeding(
                debtor_name=name,
                amount=amount_match.group(1).strip() if amount_match else '',
                department=dept_match.group(1).strip() if dept_match else '',
                status='На исполнении',
                source='ФССП',
            ))
        return results

    # -------------------------------------------------------------------------
    # Utility methods
    # -------------------------------------------------------------------------

    @staticmethod
    def parse_full_name(full_name: str) -> dict:
        """Parse a full Russian name into parts."""
        parts = full_name.strip().split()
        result = {'lastname': '', 'firstname': '', 'patronymic': ''}
        if len(parts) >= 1:
            result['lastname'] = parts[0]
        if len(parts) >= 2:
            result['firstname'] = parts[1]
        if len(parts) >= 3:
            result['patronymic'] = parts[2]
        return result

    @staticmethod
    def get_manual_search_url(full_name: str) -> Dict[str, str]:
        """
        Generate manual FSSP search URL for the user.

        The FSSP website (fssp.gov.ru/iss/ip) is reachable from outside Russia.
        This URL opens the search page directly — the user fills in the form manually.
        A deep-link with pre-filled params is included as a comment since FSSP
        uses POST + CAPTCHA, not direct GET links.
        """
        parts = FSSPSearch.parse_full_name(full_name)
        return {
            'name': 'ФССП (Исполнительные производства)',
            'url': 'https://fssp.gov.ru/iss/ip',
            'description': f'Поиск по ФИО: {full_name}',
            'instructions': (
                f'Введите: Фамилия={parts["lastname"]}, '
                f'Имя={parts["firstname"]}, '
                f'Отчество={parts["patronymic"]}'
            ),
        }

    @staticmethod
    def get_status_info() -> Dict[str, str]:
        """Return current FSSP service status for display in the UI."""
        return {
            'api_status': 'shutdown',
            'api_note': 'Официальный API api-ip.fssp.gov.ru отключён (все пути возвращают 404)',
            'website_status': 'captcha_gated',
            'website_note': 'fssp.gov.ru/iss/ip доступен снаружи РФ, но всегда показывает CAPTCHA при автоматических запросах',
            'search_url': 'https://fssp.gov.ru/iss/ip',
        }


# ---------------------------------------------------------------------------
# Singleton instance
# ---------------------------------------------------------------------------
fssp_search = FSSPSearch()
