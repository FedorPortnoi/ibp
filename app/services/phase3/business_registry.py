"""
Business Registry Search - Russian ЕГРЮЛ/ЕГРИП
===============================================
Search for company affiliations via Rusprofile.ru and List-org.com.
"""

import logging
import re
import time
from typing import List, Dict, Optional
from dataclasses import dataclass, field
from datetime import datetime
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


@dataclass
class BusinessRecord:
    """A business record from Russian registries."""
    company_name: str
    inn: str = ""  # Tax ID
    ogrn: str = ""  # Registration number
    role: str = ""  # director, founder, etc.
    status: str = ""  # active, liquidated, etc.
    registration_date: str = ""
    address: str = ""
    capital: str = ""
    source: str = ""
    url: str = ""
    confidence: str = "medium"

    def to_dict(self) -> Dict:
        return {
            'company_name': self.company_name,
            'inn': self.inn,
            'ogrn': self.ogrn,
            'role': self.role,
            'status': self.status,
            'registration_date': self.registration_date,
            'address': self.address,
            'capital': self.capital,
            'source': self.source,
            'url': self.url,
            'confidence': self.confidence
        }


class BusinessRegistrySearch:
    """
    Search Russian business registries for person's company affiliations.

    Sources:
    - Rusprofile.ru (primary)
    - List-org.com (backup)
    - EGRUL.nalog.ru (official, but limited scraping)
    """

    RUSPROFILE_BASE = "https://www.rusprofile.ru"
    LISTORG_BASE = "https://www.list-org.com"

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
        search_directors: bool = True,
        search_founders: bool = True,
        limit: int = 50
    ) -> List[BusinessRecord]:
        """
        Search for companies where person is director or founder.

        Args:
            full_name: Full name in Russian (e.g., "Иванов Иван Иванович")
            search_directors: Search for director positions
            search_founders: Search for founder positions
            limit: Max results to return

        Returns:
            List of BusinessRecord objects
        """
        results = []

        # Clean name
        name = full_name.strip()
        if not name:
            return results

        logger.info(f"Searching business records for: {name}")

        # Try Rusprofile first
        try:
            rusprofile_results = self._search_rusprofile(
                name, search_directors, search_founders, limit
            )
            results.extend(rusprofile_results)
            logger.info(f"Rusprofile found {len(rusprofile_results)} records")
        except Exception as e:
            logger.warning(f"Rusprofile search failed: {e}")

        time.sleep(1)  # Rate limiting

        # Try List-org as backup
        if len(results) < limit:
            try:
                listorg_results = self._search_listorg(
                    name, search_directors, search_founders, limit - len(results)
                )
                results.extend(listorg_results)
                logger.info(f"List-org found {len(listorg_results)} records")
            except Exception as e:
                logger.warning(f"List-org search failed: {e}")

        # Deduplicate by INN
        seen_inn = set()
        unique_results = []
        for r in results:
            if r.inn and r.inn in seen_inn:
                continue
            if r.inn:
                seen_inn.add(r.inn)
            unique_results.append(r)

        return unique_results[:limit]

    def _search_rusprofile(
        self,
        name: str,
        search_directors: bool,
        search_founders: bool,
        limit: int
    ) -> List[BusinessRecord]:
        """Search Rusprofile.ru for person's company affiliations."""
        results = []

        # Search URL
        search_url = f"{self.RUSPROFILE_BASE}/search?query={requests.utils.quote(name)}&type=person"

        try:
            response = self.session.get(search_url, timeout=self.timeout)

            if response.status_code != 200:
                logger.warning(f"Rusprofile returned status {response.status_code}")
                return results

            soup = BeautifulSoup(response.text, 'lxml')

            # Find person cards
            person_cards = soup.select('.search-result-item, .company-item, .search-result')

            for card in person_cards[:limit]:
                try:
                    record = self._parse_rusprofile_card(card)
                    if record:
                        results.append(record)
                except Exception as e:
                    logger.debug(f"Failed to parse Rusprofile card: {e}")
                    continue

            # If direct search found nothing, try parsing company search results
            if not results:
                company_items = soup.select('.company-item, .search-item')
                for item in company_items[:limit]:
                    try:
                        record = self._parse_rusprofile_company(item, name)
                        if record:
                            results.append(record)
                    except Exception as e:
                        continue

        except requests.RequestException as e:
            logger.warning(f"Rusprofile request failed: {e}")

        return results

    def _parse_rusprofile_card(self, card) -> Optional[BusinessRecord]:
        """Parse a Rusprofile search result card."""
        try:
            # Company name
            name_elem = card.select_one('.company-name, .title, a.company-name')
            company_name = name_elem.get_text(strip=True) if name_elem else ""

            if not company_name:
                return None

            # INN
            inn_match = re.search(r'ИНН[:\s]*(\d{10,12})', card.get_text())
            inn = inn_match.group(1) if inn_match else ""

            # OGRN
            ogrn_match = re.search(r'ОГРН[:\s]*(\d{13,15})', card.get_text())
            ogrn = ogrn_match.group(1) if ogrn_match else ""

            # Status
            status_elem = card.select_one('.status, .company-status')
            status = status_elem.get_text(strip=True) if status_elem else "Действующее"

            # Role
            role_text = card.get_text()
            if 'руководитель' in role_text.lower() or 'директор' in role_text.lower():
                role = "Директор"
            elif 'учредитель' in role_text.lower() or 'участник' in role_text.lower():
                role = "Учредитель"
            else:
                role = "Связан"

            # URL
            link = card.select_one('a[href*="/id/"]')
            url = f"{self.RUSPROFILE_BASE}{link['href']}" if link and link.get('href') else ""

            # Address
            addr_elem = card.select_one('.address, .company-address')
            address = addr_elem.get_text(strip=True) if addr_elem else ""

            return BusinessRecord(
                company_name=company_name,
                inn=inn,
                ogrn=ogrn,
                role=role,
                status=status,
                address=address,
                source="Rusprofile.ru",
                url=url,
                confidence="high"
            )

        except Exception as e:
            logger.debug(f"Parse error: {e}")
            return None

    def _parse_rusprofile_company(self, item, search_name: str) -> Optional[BusinessRecord]:
        """Parse a Rusprofile company item."""
        try:
            # Company name
            name_elem = item.select_one('.company-name, h4, .title')
            company_name = name_elem.get_text(strip=True) if name_elem else ""

            if not company_name:
                return None

            # Check if search name appears in company details
            full_text = item.get_text().lower()
            if search_name.lower().split()[0] not in full_text:
                return None

            # INN
            inn_match = re.search(r'ИНН[:\s]*(\d{10,12})', item.get_text())
            inn = inn_match.group(1) if inn_match else ""

            # Role - determine from context
            role = "Связан"
            if 'директор' in full_text or 'руководитель' in full_text:
                role = "Директор"
            elif 'учредитель' in full_text:
                role = "Учредитель"

            # URL
            link = item.select_one('a')
            url = ""
            if link and link.get('href'):
                href = link['href']
                if href.startswith('/'):
                    url = f"{self.RUSPROFILE_BASE}{href}"
                elif href.startswith('http'):
                    url = href

            return BusinessRecord(
                company_name=company_name,
                inn=inn,
                role=role,
                status="Не определен",
                source="Rusprofile.ru",
                url=url,
                confidence="medium"
            )

        except Exception as e:
            return None

    def _search_listorg(
        self,
        name: str,
        search_directors: bool,
        search_founders: bool,
        limit: int
    ) -> List[BusinessRecord]:
        """Search List-org.com for business records."""
        results = []

        # Search URL
        search_url = f"{self.LISTORG_BASE}/search"

        try:
            response = self.session.get(
                search_url,
                params={'val': name, 'type': 'person'},
                timeout=self.timeout
            )

            if response.status_code != 200:
                return results

            soup = BeautifulSoup(response.text, 'lxml')

            # Find result items
            items = soup.select('.org_list tr, .search-result, .company-row')

            for item in items[:limit]:
                try:
                    # Company name
                    name_elem = item.select_one('a, .org_name, td:first-child')
                    company_name = name_elem.get_text(strip=True) if name_elem else ""

                    if not company_name or len(company_name) < 3:
                        continue

                    # INN
                    inn_match = re.search(r'(\d{10,12})', item.get_text())
                    inn = inn_match.group(1) if inn_match else ""

                    # URL
                    link = item.select_one('a')
                    url = ""
                    if link and link.get('href'):
                        href = link['href']
                        if href.startswith('/'):
                            url = f"{self.LISTORG_BASE}{href}"
                        elif href.startswith('http'):
                            url = href

                    results.append(BusinessRecord(
                        company_name=company_name,
                        inn=inn,
                        role="Связан",
                        status="Не определен",
                        source="List-org.com",
                        url=url,
                        confidence="medium"
                    ))

                except Exception:
                    continue

        except requests.RequestException as e:
            logger.warning(f"List-org request failed: {e}")

        return results

    def search_by_inn(self, inn: str) -> Optional[BusinessRecord]:
        """Search for company details by INN."""
        if not inn or not inn.isdigit():
            return None

        try:
            url = f"{self.RUSPROFILE_BASE}/search?query={inn}&type=company"
            response = self.session.get(url, timeout=self.timeout)

            if response.status_code != 200:
                return None

            soup = BeautifulSoup(response.text, 'lxml')

            # Find first company card
            card = soup.select_one('.company-item, .search-result-item')
            if card:
                return self._parse_rusprofile_card(card)

        except Exception as e:
            logger.warning(f"INN search failed: {e}")

        return None

    def get_company_details(self, company_url: str) -> Optional[Dict]:
        """Get detailed company information from URL."""
        try:
            response = self.session.get(company_url, timeout=self.timeout)

            if response.status_code != 200:
                return None

            soup = BeautifulSoup(response.text, 'lxml')

            details = {
                'name': '',
                'inn': '',
                'ogrn': '',
                'status': '',
                'registration_date': '',
                'address': '',
                'capital': '',
                'director': '',
                'founders': [],
                'activities': []
            }

            # Extract company name
            name_elem = soup.select_one('h1, .company-name')
            details['name'] = name_elem.get_text(strip=True) if name_elem else ""

            # Extract INN, OGRN from page
            text = soup.get_text()

            inn_match = re.search(r'ИНН[:\s]*(\d{10,12})', text)
            if inn_match:
                details['inn'] = inn_match.group(1)

            ogrn_match = re.search(r'ОГРН[:\s]*(\d{13,15})', text)
            if ogrn_match:
                details['ogrn'] = ogrn_match.group(1)

            # Status
            status_elem = soup.select_one('.company-status, .status')
            details['status'] = status_elem.get_text(strip=True) if status_elem else ""

            # Address
            addr_elem = soup.select_one('.address, [data-qa="address"]')
            details['address'] = addr_elem.get_text(strip=True) if addr_elem else ""

            # Director
            director_elem = soup.select_one('.director, [data-qa="director"]')
            details['director'] = director_elem.get_text(strip=True) if director_elem else ""

            return details

        except Exception as e:
            logger.warning(f"Failed to get company details: {e}")
            return None


# Singleton instance
business_registry_search = BusinessRegistrySearch()
