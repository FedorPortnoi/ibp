"""
Court Record Search - Russian Court Cases
==========================================
Search sudact.ru and arbitration courts for case history.
"""

import logging
import re
import time
from typing import List, Dict, Optional
from dataclasses import dataclass, field
from datetime import datetime
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote

logger = logging.getLogger(__name__)


@dataclass
class CourtCase:
    """A court case record."""
    case_number: str
    court_name: str
    case_type: str = ""  # civil, criminal, administrative, arbitration
    date: str = ""
    role: str = ""  # plaintiff, defendant, third party
    category: str = ""  # Категория дела
    result: str = ""  # Решение
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
    - sudact.ru - General courts database
    - ras.arbitr.ru - Arbitration courts (commercial disputes)
    - sudrf.ru - Official court portal
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

        Args:
            full_name: Full name in Russian
            search_plaintiff: Include cases as plaintiff
            search_defendant: Include cases as defendant
            limit: Max results

        Returns:
            List of CourtCase objects
        """
        results = []

        name = full_name.strip()
        if not name:
            return results

        logger.info(f"Searching court records for: {name}")

        # Search Sudact.ru (general courts)
        try:
            sudact_results = self._search_sudact(name, limit)
            results.extend(sudact_results)
            logger.info(f"Sudact found {len(sudact_results)} cases")
        except Exception as e:
            logger.warning(f"Sudact search failed: {e}")

        time.sleep(1)  # Rate limiting

        # Search Arbitration courts
        if len(results) < limit:
            try:
                arbitr_results = self._search_arbitr(name, limit - len(results))
                results.extend(arbitr_results)
                logger.info(f"Arbitr found {len(arbitr_results)} cases")
            except Exception as e:
                logger.warning(f"Arbitr search failed: {e}")

        # Deduplicate by case number
        seen = set()
        unique = []
        for case in results:
            key = f"{case.case_number}_{case.court_name}"
            if key not in seen:
                seen.add(key)
                unique.append(case)

        return unique[:limit]

    def _search_sudact(self, name: str, limit: int) -> List[CourtCase]:
        """Search sudact.ru for court decisions."""
        results = []

        # Sudact search URL
        search_url = f"{self.SUDACT_BASE}/regular/doc"

        try:
            # First, try to get a search page
            params = {
                'regular-txt': name,
                'regular-case_doc': '',
                'regular-doc_type': '',
                'regular-date_from': '',
                'regular-date_to': '',
                'regular-court': '',
                'regular-region': '',
            }

            response = self.session.get(search_url, params=params, timeout=self.timeout)

            if response.status_code != 200:
                logger.warning(f"Sudact returned status {response.status_code}")
                return results

            soup = BeautifulSoup(response.text, 'lxml')

            # Find document items
            doc_items = soup.select('.doc-item, .result-item, .search-result')

            for item in doc_items[:limit]:
                try:
                    case = self._parse_sudact_item(item, name)
                    if case:
                        results.append(case)
                except Exception as e:
                    logger.debug(f"Failed to parse Sudact item: {e}")
                    continue

            # Alternative: parse table rows if present
            if not results:
                rows = soup.select('table tr, .doc-row')
                for row in rows[:limit]:
                    try:
                        case = self._parse_sudact_row(row, name)
                        if case:
                            results.append(case)
                    except Exception:
                        continue

        except requests.RequestException as e:
            logger.warning(f"Sudact request failed: {e}")

        return results

    def _parse_sudact_item(self, item, search_name: str) -> Optional[CourtCase]:
        """Parse a Sudact search result item."""
        try:
            text = item.get_text()

            # Case number
            case_num_match = re.search(r'(?:Дело|№)[:\s]*([0-9А-Яа-я\-/]+)', text)
            case_number = case_num_match.group(1) if case_num_match else ""

            if not case_number:
                # Try alternative patterns
                case_num_match = re.search(r'(\d{1,2}-\d+/\d{4})', text)
                case_number = case_num_match.group(1) if case_num_match else "Не указан"

            # Court name
            court_elem = item.select_one('.court-name, .court, h3')
            court_name = court_elem.get_text(strip=True) if court_elem else ""

            if not court_name:
                court_match = re.search(r'([\w\s]+(?:суд|СОЮ|районный)[\w\s]*)', text, re.IGNORECASE)
                court_name = court_match.group(1).strip() if court_match else "Не указан"

            # Date
            date_match = re.search(r'(\d{2}[./]\d{2}[./]\d{4})', text)
            date = date_match.group(1) if date_match else ""

            # Case type
            case_type = "гражданское"
            text_lower = text.lower()
            if 'уголовн' in text_lower:
                case_type = "уголовное"
            elif 'административн' in text_lower:
                case_type = "административное"
            elif 'арбитраж' in text_lower:
                case_type = "арбитражное"

            # Role
            role = "участник"
            name_lower = search_name.lower()
            if 'истец' in text_lower or f'{name_lower}.*истец' in text_lower:
                role = "истец"
            elif 'ответчик' in text_lower:
                role = "ответчик"
            elif 'третье лицо' in text_lower:
                role = "третье лицо"

            # URL
            link = item.select_one('a[href]')
            url = ""
            if link and link.get('href'):
                href = link['href']
                if href.startswith('/'):
                    url = f"{self.SUDACT_BASE}{href}"
                elif href.startswith('http'):
                    url = href

            # Category
            category_match = re.search(r'Категория[:\s]*([^.]+)', text)
            category = category_match.group(1).strip() if category_match else ""

            return CourtCase(
                case_number=case_number,
                court_name=court_name,
                case_type=case_type,
                date=date,
                role=role,
                category=category,
                url=url,
                source="sudact.ru",
                confidence="high" if case_number != "Не указан" else "medium"
            )

        except Exception as e:
            logger.debug(f"Parse error: {e}")
            return None

    def _parse_sudact_row(self, row, search_name: str) -> Optional[CourtCase]:
        """Parse a Sudact table row."""
        try:
            cells = row.select('td')
            if len(cells) < 2:
                return None

            text = row.get_text()

            # Verify name appears in row
            if search_name.split()[0].lower() not in text.lower():
                return None

            # Extract data from cells
            case_number = cells[0].get_text(strip=True) if cells else ""
            court_name = cells[1].get_text(strip=True) if len(cells) > 1 else ""

            if not case_number:
                return None

            # URL
            link = row.select_one('a')
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
                case_type="гражданское",
                role="участник",
                source="sudact.ru",
                url=url,
                confidence="medium"
            )

        except Exception:
            return None

    def _search_arbitr(self, name: str, limit: int) -> List[CourtCase]:
        """Search kad.arbitr.ru for arbitration cases."""
        results = []

        # Arbitr.ru requires specific API calls
        # Using the main search endpoint
        search_url = f"{self.ARBITR_BASE}/Kad/SearchInstances"

        try:
            # Search params for arbitration
            params = {
                'Sides[0].Name': name,
                'Page': 1,
                'Count': min(limit, 25),
                'WithVKSInstances': False,
            }

            response = self.session.get(
                search_url,
                params=params,
                timeout=self.timeout
            )

            if response.status_code == 200:
                try:
                    data = response.json()
                    items = data.get('Result', {}).get('Items', [])

                    for item in items[:limit]:
                        case = self._parse_arbitr_item(item, name)
                        if case:
                            results.append(case)
                except Exception:
                    # JSON parsing failed, try HTML parsing
                    pass

            # Fallback: parse HTML response
            if not results:
                soup = BeautifulSoup(response.text, 'lxml')
                rows = soup.select('.b-cases tr, .case-item')

                for row in rows[:limit]:
                    try:
                        case = self._parse_arbitr_html(row, name)
                        if case:
                            results.append(case)
                    except Exception:
                        continue

        except requests.RequestException as e:
            logger.warning(f"Arbitr request failed: {e}")

        return results

    def _parse_arbitr_item(self, item: Dict, search_name: str) -> Optional[CourtCase]:
        """Parse an arbitration API result item."""
        try:
            case_number = item.get('CaseNumber', '') or item.get('Number', '')
            court_name = item.get('CourtName', '') or item.get('Court', {}).get('Name', '')
            date = item.get('Date', '') or item.get('AcceptanceDate', '')

            if not case_number:
                return None

            # Determine role
            role = "участник"
            plaintiffs = item.get('Plaintiffs', []) or item.get('Sides', [])
            defendants = item.get('Defendants', [])

            for p in plaintiffs:
                if isinstance(p, dict):
                    pname = p.get('Name', '').lower()
                else:
                    pname = str(p).lower()
                if search_name.lower().split()[0] in pname:
                    role = "истец"
                    break

            for d in defendants:
                if isinstance(d, dict):
                    dname = d.get('Name', '').lower()
                else:
                    dname = str(d).lower()
                if search_name.lower().split()[0] in dname:
                    role = "ответчик"
                    break

            # URL
            url = f"{self.ARBITR_BASE}/Card?number={quote(case_number)}"

            return CourtCase(
                case_number=case_number,
                court_name=court_name,
                case_type="арбитражное",
                date=date,
                role=role,
                category="Экономические споры",
                url=url,
                source="kad.arbitr.ru",
                confidence="high"
            )

        except Exception as e:
            logger.debug(f"Parse arbitr item error: {e}")
            return None

    def _parse_arbitr_html(self, row, search_name: str) -> Optional[CourtCase]:
        """Parse arbitration HTML row."""
        try:
            text = row.get_text()

            # Case number
            case_match = re.search(r'А\d{2}-\d+/\d{4}', text)
            case_number = case_match.group(0) if case_match else ""

            if not case_number:
                return None

            # Court
            court_elem = row.select_one('.court, td:nth-child(2)')
            court_name = court_elem.get_text(strip=True) if court_elem else "Арбитражный суд"

            # URL
            link = row.select_one('a')
            url = ""
            if link and link.get('href'):
                href = link['href']
                if 'arbitr' in href or href.startswith('/'):
                    if href.startswith('/'):
                        url = f"{self.ARBITR_BASE}{href}"
                    else:
                        url = href

            return CourtCase(
                case_number=case_number,
                court_name=court_name,
                case_type="арбитражное",
                role="участник",
                source="kad.arbitr.ru",
                url=url,
                confidence="medium"
            )

        except Exception:
            return None

    def get_case_details(self, case_url: str) -> Optional[Dict]:
        """Get detailed information about a court case."""
        try:
            response = self.session.get(case_url, timeout=self.timeout)

            if response.status_code != 200:
                return None

            soup = BeautifulSoup(response.text, 'lxml')

            details = {
                'case_number': '',
                'court': '',
                'date': '',
                'category': '',
                'plaintiffs': [],
                'defendants': [],
                'result': '',
                'documents': []
            }

            # Extract from page
            text = soup.get_text()

            # Case number
            case_match = re.search(r'(?:Дело|№)[:\s]*([^\s]+)', text)
            details['case_number'] = case_match.group(1) if case_match else ""

            # Date
            date_match = re.search(r'(\d{2}[./]\d{2}[./]\d{4})', text)
            details['date'] = date_match.group(1) if date_match else ""

            # Result
            result_elem = soup.select_one('.result, .decision, .verdict')
            details['result'] = result_elem.get_text(strip=True) if result_elem else ""

            return details

        except Exception as e:
            logger.warning(f"Failed to get case details: {e}")
            return None


# Singleton instance
court_search = CourtRecordSearch()
