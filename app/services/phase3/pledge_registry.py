"""
Pledge Registry Search — reestr-zalogov.ru (Реестр залогов ФНП)
===============================================================
Searches the Federal Notary Chamber's pledge registry for pledged assets.

The site uses Google reCAPTCHA, so automated search is limited.
Primary strategy: Playwright-based search with fallback to manual URL.

Usage:
    from app.services.phase3.pledge_registry import PledgeRegistrySearch
    svc = PledgeRegistrySearch()
    results = svc.search_by_name("Иванов Иван Иванович")
"""

import logging
import re
from dataclasses import dataclass
from typing import List, Optional
from urllib.parse import quote

logger = logging.getLogger(__name__)

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/122.0.0.0 Safari/537.36'
    ),
    'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
}


@dataclass
class PledgeRecord:
    """A record from the pledge registry."""
    registration_number: str = ''
    pledgor_name: str = ''
    pledgor_inn: str = ''
    pledgee_name: str = ''
    subject: str = ''
    registration_date: str = ''
    status: str = ''
    source: str = 'reestr-zalogov.ru'

    def to_dict(self) -> dict:
        return {
            'registration_number': self.registration_number,
            'pledgor_name': self.pledgor_name,
            'pledgor_inn': self.pledgor_inn,
            'pledgee_name': self.pledgee_name,
            'subject': self.subject,
            'registration_date': self.registration_date,
            'status': self.status,
            'source': self.source,
        }


class PledgeRegistrySearch:
    """
    Search reestr-zalogov.ru for pledged assets.

    Strategy:
    1. Try Playwright-based search (handles JS rendering)
    2. If Playwright unavailable or reCAPTCHA blocks — return manual URL
    """

    BASE_URL = 'https://www.reestr-zalogov.ru'
    SEARCH_URL = 'https://www.reestr-zalogov.ru/search/index'

    def __init__(self, timeout: int = 30):
        self.timeout = timeout

    def search_by_name(self, full_name: str) -> List[PledgeRecord]:
        """Search pledge registry by person name."""
        if not full_name or not full_name.strip():
            return []

        logger.info(f"Pledge registry: searching for '{full_name}'")

        # Try Playwright search
        try:
            results = self._search_playwright(full_name)
            if results:
                logger.info(f"Pledge registry: found {len(results)} records via Playwright")
                return results
        except Exception as e:
            logger.warning(f"Pledge registry Playwright search failed: {e}")

        # Return empty — manual URL provided separately
        logger.info("Pledge registry: no automated results (reCAPTCHA likely)")
        return []

    def _search_playwright(self, full_name: str) -> List[PledgeRecord]:
        """Search using Playwright for JS-rendered content."""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            logger.debug("Playwright not available for pledge search")
            return []

        results = []
        browser = None

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.set_default_timeout(self.timeout * 1000)

                page.goto(self.SEARCH_URL, wait_until='networkidle', timeout=30000)
                page.wait_for_timeout(2000)

                # Look for pledgor name input field
                name_input = page.query_selector(
                    'input[name*="Name"], input[placeholder*="ФИО"], '
                    'input[placeholder*="залогодатель"], input#Name'
                )
                if not name_input:
                    # Try filling any visible text input in the search form
                    name_input = page.query_selector(
                        'form input[type="text"], input.form-control'
                    )

                if name_input:
                    name_input.fill(full_name)
                    page.wait_for_timeout(500)

                    # Submit form
                    submit_btn = page.query_selector(
                        'button[type="submit"], input[type="submit"], '
                        '.btn-search, button.btn-primary'
                    )
                    if submit_btn:
                        submit_btn.click()
                        page.wait_for_timeout(3000)

                    # Check for reCAPTCHA challenge
                    captcha = page.query_selector(
                        'iframe[src*="recaptcha"], .g-recaptcha, #recaptcha'
                    )
                    if captcha:
                        logger.info("Pledge registry: reCAPTCHA detected, cannot proceed")
                        return []

                    # Parse results
                    results = self._parse_playwright_results(page)

        except Exception as e:
            logger.warning(f"Pledge registry Playwright error: {e}")
        finally:
            if browser:
                try:
                    browser.close()
                except Exception:
                    pass

        return results

    def _parse_playwright_results(self, page) -> List[PledgeRecord]:
        """Parse search results from Playwright page."""
        records = []

        try:
            # Look for result rows/cards
            items = page.query_selector_all(
                '.search-result, .result-item, table.table tbody tr, '
                '.notification-item, [class*="result"]'
            )

            for item in items[:20]:
                try:
                    text = item.inner_text()
                    if not text or len(text.strip()) < 10:
                        continue

                    record = self._parse_result_text(text)
                    if record:
                        records.append(record)
                except Exception:
                    continue

        except Exception as e:
            logger.debug(f"Parse pledge results error: {e}")

        return records

    def _parse_result_text(self, text: str) -> Optional[PledgeRecord]:
        """Parse a pledge record from result text."""
        if not text:
            return None

        # Registration number pattern: digits (14+ digits typical)
        reg_num_m = re.search(r'(?:№|номер)\s*(\d{10,20})', text, re.IGNORECASE)
        reg_num = reg_num_m.group(1) if reg_num_m else ''

        # Date
        date_m = re.search(r'(\d{2}\.\d{2}\.\d{4})', text)
        reg_date = date_m.group(1) if date_m else ''

        # Status
        status = 'Действующий'
        if re.search(r'прекращ|удовлетвор|исключ', text, re.IGNORECASE):
            status = 'Прекращён'

        # Subject of pledge
        subject_m = re.search(
            r'(?:предмет[^:]*:|имущество[^:]*:)\s*(.+?)(?:\n|$)',
            text, re.IGNORECASE,
        )
        subject = subject_m.group(1).strip()[:200] if subject_m else text.strip()[:150]

        return PledgeRecord(
            registration_number=reg_num,
            subject=subject,
            registration_date=reg_date,
            status=status,
        )

    @staticmethod
    def get_manual_search_url(full_name: str) -> str:
        """Generate manual search URL for pledge registry."""
        return 'https://www.reestr-zalogov.ru/search/index'
