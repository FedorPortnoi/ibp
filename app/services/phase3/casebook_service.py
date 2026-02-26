"""
Casebook.ru Service — Arbitration Court Records
=================================================
Global alternative to kad.arbitr.ru (geo-blocked, HTTP 451).
Casebook.ru is a free court case aggregator accessible globally.

Covers:
- Arbitration court cases (арбитражные дела)
- General jurisdiction courts
- Court rulings and decisions

Usage:
    from app.services.phase3.casebook_service import CasebookService
    svc = CasebookService()
    records = svc.search_person("Иванов Иван Иванович")
"""

import logging
import re
from dataclasses import dataclass
from typing import List, Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/122.0.0.0 Safari/537.36'
    ),
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
}


@dataclass
class CasebookRecord:
    """A court case from casebook.ru."""
    case_number: str = ''
    court_name: str = ''
    case_type: str = ''
    date: str = ''
    parties: str = ''
    subject: str = ''
    result: str = ''
    url: str = ''
    source: str = 'casebook.ru'

    def to_dict(self) -> dict:
        return {
            'case_number': self.case_number,
            'court_name': self.court_name,
            'case_type': self.case_type,
            'date': self.date,
            'parties': self.parties,
            'subject': self.subject,
            'result': self.result,
            'url': self.url,
            'source': self.source,
        }

    def to_court_dict(self) -> dict:
        """Convert to court record format compatible with pipeline."""
        return {
            'case_number': self.case_number,
            'court_name': self.court_name,
            'case_type': self.case_type or 'Арбитражное дело',
            'article': '',
            'role': '',
            'date': self.date,
            'result': self.result,
            'source': 'casebook.ru',
        }


class CasebookService:
    """
    Search casebook.ru for court cases.

    Casebook.ru is a free aggregator that indexes Russian court cases
    including arbitration courts (replacing geo-blocked kad.arbitr.ru).

    Usage:
        svc = CasebookService()
        records = svc.search_person("Иванов Иван Иванович")
    """

    SEARCH_URL = 'https://casebook.ru/search'
    API_SEARCH_URL = 'https://casebook.ru/api/Search/Cases'
    TIMEOUT = 25

    def __init__(self, timeout: int = 25):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def search_person(
        self, full_name: str, case_type: str = 'arbitration',
    ) -> List[CasebookRecord]:
        """
        Search casebook.ru for court cases involving a person.

        Args:
            full_name: Full name in Russian
            case_type: 'arbitration' or 'all'

        Returns:
            List of CasebookRecord objects.
        """
        # Try API first, then HTML scraping fallback
        records = self._search_api(full_name, case_type)
        if records is not None:
            return records

        return self._search_html(full_name)

    def _search_api(
        self, full_name: str, case_type: str,
    ) -> Optional[List[CasebookRecord]]:
        """Try casebook.ru internal API for search."""
        try:
            payload = {
                'query': full_name,
                'page': 1,
                'count': 20,
            }

            resp = self.session.post(
                self.API_SEARCH_URL,
                json=payload,
                timeout=self.timeout,
                headers={
                    **HEADERS,
                    'Content-Type': 'application/json',
                    'Accept': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest',
                },
            )

            if resp.status_code in (403, 429):
                logger.warning(f"Casebook API returned {resp.status_code}")
                return None

            if resp.status_code != 200:
                return None

            data = resp.json()
            records = []

            items = data.get('items', data.get('result', data.get('cases', [])))
            if not isinstance(items, list):
                return None

            for item in items[:20]:
                records.append(CasebookRecord(
                    case_number=item.get('caseNumber', item.get('number', '')),
                    court_name=item.get('courtName', item.get('court', '')),
                    case_type=item.get('caseType', 'Арбитражное дело'),
                    date=item.get('date', item.get('registerDate', '')),
                    parties=item.get('parties', ''),
                    subject=item.get('subject', item.get('description', '')),
                    result=item.get('result', item.get('lastEvent', '')),
                    url=item.get('url', ''),
                ))

            return records

        except Exception as e:
            logger.warning(f"Casebook API error: {e}")
            return None

    def _search_html(self, full_name: str) -> List[CasebookRecord]:
        """Fallback: scrape casebook.ru search results HTML."""
        try:
            resp = self.session.get(
                self.SEARCH_URL,
                params={'query': full_name},
                timeout=self.timeout,
            )

            if resp.status_code in (403, 429):
                logger.warning(f"Casebook HTML returned {resp.status_code}")
                return []

            resp.raise_for_status()
            resp.encoding = resp.apparent_encoding or 'utf-8'

            return self._parse_html_results(resp.text)

        except requests.Timeout:
            logger.warning("Casebook.ru timeout")
            return []
        except requests.ConnectionError:
            logger.warning("Casebook.ru connection error")
            return []
        except Exception as e:
            logger.error(f"Casebook.ru search error: {e}")
            return []

    def _parse_html_results(self, html: str) -> List[CasebookRecord]:
        """Parse court case records from casebook.ru HTML."""
        records = []
        try:
            soup = BeautifulSoup(html, 'html.parser')

            # Look for case number patterns: А40-12345/2023
            for element in soup.find_all(
                text=re.compile(r'[АA]\d{2}-\d+/\d{4}'),
            ):
                parent = element.parent
                if not parent:
                    continue

                # Get the containing block
                block = parent
                for _ in range(5):
                    if block.parent and block.parent.name in ('div', 'tr', 'li', 'article'):
                        block = block.parent
                    else:
                        break

                block_text = block.get_text(separator='\n')

                # Extract case number
                case_match = re.search(r'([АA]\d{2}-\d+/\d{4})', block_text)
                if not case_match:
                    continue

                case_number = case_match.group(1)

                # Avoid duplicates
                if any(r.case_number == case_number for r in records):
                    continue

                # Extract court name
                court = ''
                court_match = re.search(
                    r'((?:Арбитражный|Районный|Городской|Областной|Верховный|Мировой)'
                    r'[^\n]{0,100}суд[^\n]{0,100})',
                    block_text, re.IGNORECASE,
                )
                if court_match:
                    court = court_match.group(1).strip()[:200]

                # Extract date
                date = ''
                date_match = re.search(r'(\d{2}\.\d{2}\.\d{4})', block_text)
                if date_match:
                    date = date_match.group(1)

                records.append(CasebookRecord(
                    case_number=case_number,
                    court_name=court,
                    case_type='Арбитражное дело',
                    date=date,
                    subject='',
                ))

        except Exception as e:
            logger.error(f"Casebook HTML parse error: {e}")

        return records
