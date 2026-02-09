"""
Court Record Search - Russian Court Cases
==========================================
Search sudact.ru and arbitration courts for case history.

Source status (as of Feb 2026):
- sudact.ru: JS-rendered, requires Playwright for results
- kad.arbitr.ru: Blocks automated requests (451)
- Both provide manual search URL fallbacks
"""

import logging
import re
import time
from typing import List, Dict, Optional
from dataclasses import dataclass
from urllib.parse import quote
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

        logger.info(f"Searching court records for: {name}")

        # Try sudact.ru with Playwright (JS-rendered)
        if PLAYWRIGHT_AVAILABLE:
            try:
                sudact_results = self._search_sudact_playwright(name, limit)
                results.extend(sudact_results)
                logger.info(f"Sudact (Playwright) found {len(sudact_results)} cases")
            except Exception as e:
                logger.warning(f"Sudact Playwright search failed: {e}")
        else:
            logger.info("Playwright not available — sudact.ru requires JS rendering, skipping")

        # Try basic requests as secondary approach
        if not results:
            try:
                sudact_basic = self._search_sudact_basic(name, limit)
                results.extend(sudact_basic)
                if sudact_basic:
                    logger.info(f"Sudact (basic) found {len(sudact_basic)} cases")
            except Exception as e:
                logger.warning(f"Sudact basic search failed: {e}")

        # Deduplicate by case number
        seen = set()
        unique = []
        for case in results:
            key = f"{case.case_number}_{case.court_name}"
            if key not in seen:
                seen.add(key)
                unique.append(case)

        return unique[:limit]

    def _search_sudact_playwright(self, name: str, limit: int) -> List[CourtCase]:
        """Search sudact.ru using Playwright for JS rendering."""
        results = []

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.set_default_timeout(self.timeout * 1000)

                url = f"{self.SUDACT_BASE}/regular/doc/?regular-txt={quote(name)}"
                page.goto(url)

                # Wait for results to render
                try:
                    page.wait_for_selector('#resultTable tr, .resultTable tr, .result-item', timeout=15000)
                except Exception:
                    # No results or timeout
                    browser.close()
                    return results

                # Get rendered HTML
                html = page.content()
                browser.close()

            soup = BeautifulSoup(html, 'lxml')

            # Parse result rows
            rows = soup.select('#resultTable tr, .resultTable tr')
            for row in rows[:limit]:
                case = self._parse_sudact_row_pw(row, name)
                if case:
                    results.append(case)

            # Also try result items
            if not results:
                items = soup.select('.result-item, .bsr-item')
                for item in items[:limit]:
                    case = self._parse_sudact_item(item, name)
                    if case:
                        results.append(case)

        except Exception as e:
            logger.warning(f"Sudact Playwright error: {e}")

        return results

    def _parse_sudact_row_pw(self, row, search_name: str) -> Optional[CourtCase]:
        """Parse a Playwright-rendered sudact row."""
        try:
            cells = row.select('td')
            if len(cells) < 2:
                return None

            text = row.get_text()

            # Case number
            case_match = re.search(r'(\d{1,2}-\d+/\d{4})', text)
            if not case_match:
                case_match = re.search(r'(?:Дело|№)[:\s]*([^\s,]+)', text)
            case_number = case_match.group(1) if case_match else ""

            if not case_number or case_number == "Не указан":
                return None

            # Court name
            court_name = cells[0].get_text(strip=True) if cells else ""
            if not court_name or len(court_name) < 3:
                court_name = cells[1].get_text(strip=True) if len(cells) > 1 else "Не указан"

            # Date
            date_match = re.search(r'(\d{2}[./]\d{2}[./]\d{4})', text)
            date = date_match.group(1) if date_match else ""

            # Case type
            case_type = self._detect_case_type(text)

            # URL
            link = row.select_one('a[href]')
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
                role="участник",
                source="sudact.ru",
                url=url,
                confidence="high"
            )
        except Exception:
            return None

    def _search_sudact_basic(self, name: str, limit: int) -> List[CourtCase]:
        """Search sudact.ru with basic requests (limited — JS-rendered content)."""
        results = []

        try:
            params = {
                'regular-txt': name,
                'regular-case_doc': '',
                'regular-doc_type': '',
                'regular-date_from': '',
                'regular-date_to': '',
                'regular-court': '',
                'regular-region': '',
            }

            response = self.session.get(
                f"{self.SUDACT_BASE}/regular/doc",
                params=params,
                timeout=self.timeout
            )

            if response.status_code != 200:
                return results

            soup = BeautifulSoup(response.text, 'lxml')

            # Try to find any result elements
            items = soup.select('#resultTable tr, .result-item, .bsr-item, .doc-item')
            for item in items[:limit]:
                case = self._parse_sudact_item(item, name)
                if case:
                    results.append(case)

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
            case_match = re.search(r'(\d{1,2}-\d+/\d{4})', text)
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
        """Generate manual court search URLs for the user."""
        encoded = quote(name)
        return [
            {
                'name': 'Судебные акты (sudact.ru)',
                'url': f'https://sudact.ru/regular/doc/?regular-txt={encoded}',
                'description': 'Суды общей юрисдикции'
            },
            {
                'name': 'Арбитражные суды (kad.arbitr.ru)',
                'url': f'https://kad.arbitr.ru/',
                'description': 'Арбитражные (экономические) дела'
            },
            {
                'name': 'Судебное делопроизводство (sudrf.ru)',
                'url': f'https://bsr.sudrf.ru/bigs/portal.html',
                'description': 'Портал ГАС Правосудие'
            },
        ]


# Singleton instance
court_search = CourtRecordSearch()
