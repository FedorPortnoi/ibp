"""
Business Registry Search - Russian ЕГРЮЛ/ЕГРИП
===============================================
Search for company affiliations via official sources.

Sources (in priority order):
1. egrul.nalog.ru (official FNS, free, 2-step token-based API)
2. Rusprofile.ru (scraping fallback)
3. List-org.com (scraping fallback)
"""

import logging
import re
import time
from typing import List, Dict, Optional
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import quote
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


@dataclass
class BusinessRecord:
    """A business record from Russian registries."""
    company_name: str
    inn: str = ""  # Tax ID
    ogrn: str = ""  # Registration number
    role: str = ""  # Директор, Учредитель, ИП
    status: str = ""  # Действующее, Ликвидировано, etc.
    registration_date: str = ""
    address: str = ""
    capital: str = ""
    source: str = ""
    url: str = ""
    confidence: str = "medium"
    company_type: str = ""  # ООО, ИП, ЗАО, etc.
    okved: str = ""  # Primary activity code
    okved_name: str = ""  # Activity description

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
            'confidence': self.confidence,
            'company_type': self.company_type,
            'okved': self.okved,
            'okved_name': self.okved_name,
        }


class BusinessRegistrySearch:
    """
    Search Russian business registries for person's company affiliations.

    Sources (tried in order):
    1. egrul.nalog.ru — Official FNS EGRUL/EGRIP (free, reliable)
    2. Rusprofile.ru — Scraping fallback
    3. List-org.com — Scraping fallback
    """

    NALOG_BASE = "https://egrul.nalog.ru"
    RUSPROFILE_BASE = "https://www.rusprofile.ru"
    LISTORG_BASE = "https://www.list-org.com"

    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/html, */*;q=0.8',
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

        Tries nalog.ru EGRUL first (official), then Rusprofile/List-org as fallbacks.
        """
        results = []
        name = full_name.strip()
        if not name:
            return results

        logger.info(f"Searching business records for: {name}")

        # Source 1: nalog.ru EGRUL (primary — official, reliable)
        try:
            nalog_results = self._search_nalog_egrul(name, limit)
            results.extend(nalog_results)
            logger.info(f"nalog.ru EGRUL found {len(nalog_results)} records")
        except Exception as e:
            logger.warning(f"nalog.ru EGRUL search failed: {e}")

        # Source 2: Rusprofile (fallback)
        if len(results) < 3:
            time.sleep(0.5)
            try:
                rp_results = self._search_rusprofile(name, search_directors, search_founders, limit)
                results.extend(rp_results)
                logger.info(f"Rusprofile found {len(rp_results)} records")
            except Exception as e:
                logger.warning(f"Rusprofile search failed: {e}")

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

    # ===== nalog.ru EGRUL (Primary Source) =====

    def _search_nalog_egrul(self, name: str, limit: int) -> List[BusinessRecord]:
        """
        Search egrul.nalog.ru — official FNS registry.

        2-step process:
        1. POST name → get search token
        2. GET search-result/{token} → get JSON results
        """
        results = []

        # Step 1: Get search token
        try:
            resp = self.session.post(
                f"{self.NALOG_BASE}/",
                data={'query': name},
                headers={
                    **self.HEADERS,
                    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                    'Origin': self.NALOG_BASE,
                    'Referer': f"{self.NALOG_BASE}/",
                    'X-Requested-With': 'XMLHttpRequest',
                },
                timeout=self.timeout
            )

            if resp.status_code != 200:
                logger.warning(f"nalog.ru step 1 returned {resp.status_code}")
                return results

            data = resp.json()
            token = data.get('t', '')
            captcha_required = data.get('captchaRequired', False)

            if not token:
                logger.warning("nalog.ru returned no token")
                return results

            if captcha_required:
                logger.warning("nalog.ru requires CAPTCHA — skipping")
                return results

        except Exception as e:
            logger.warning(f"nalog.ru step 1 error: {e}")
            return results

        # Step 2: Fetch results (with retry — sometimes needs a moment)
        time.sleep(1.5)

        for attempt in range(3):
            try:
                resp2 = self.session.get(
                    f"{self.NALOG_BASE}/search-result/{token}",
                    headers={
                        **self.HEADERS,
                        'Referer': f"{self.NALOG_BASE}/",
                        'X-Requested-With': 'XMLHttpRequest',
                    },
                    timeout=self.timeout
                )

                if resp2.status_code != 200:
                    logger.warning(f"nalog.ru step 2 returned {resp2.status_code}")
                    time.sleep(1)
                    continue

                data2 = resp2.json()
                rows = data2.get('rows', [])

                if not rows and attempt < 2:
                    # Results may not be ready yet
                    time.sleep(2)
                    continue

                for row in rows[:limit]:
                    record = self._parse_nalog_row(row, name)
                    if record:
                        results.append(record)

                break  # Success

            except Exception as e:
                logger.warning(f"nalog.ru step 2 attempt {attempt+1} error: {e}")
                if attempt < 2:
                    time.sleep(1)

        return results

    def _parse_nalog_row(self, row: dict, search_name: str) -> Optional[BusinessRecord]:
        """Parse a nalog.ru EGRUL search result row."""
        try:
            # Row fields: n=name, i=INN, o=OGRN, a=address, c=company_name,
            # r=region, e=end_date, p=IP_name, k=KPP, g=registration_date
            company_name = row.get('c', '') or row.get('n', '')
            inn = row.get('i', '')
            ogrn = row.get('o', '')
            address = row.get('a', '')
            reg_date = row.get('g', '')
            end_date = row.get('e', '')
            kpp = row.get('k', '')
            ip_name = row.get('p', '')  # For individual entrepreneurs

            if not company_name and not ip_name:
                return None

            # Determine if this is an IP (individual entrepreneur) or company
            if ip_name and not company_name:
                company_name = f"ИП {ip_name}"
                company_type = "ИП"
            elif company_name:
                company_type = self._detect_company_type(company_name)
            else:
                company_type = ""

            # Determine status
            if end_date:
                status = "Ликвидировано"
            else:
                status = "Действующее"

            # Determine role
            # nalog.ru doesn't tell us the role directly,
            # but if it's an IP with the same name, they're the entrepreneur
            name_parts = search_name.lower().split()
            full_text = (company_name + ' ' + (ip_name or '')).lower()

            if ip_name and any(p in ip_name.lower() for p in name_parts if len(p) > 2):
                role = "ИП"
            elif any(p in full_text for p in name_parts if len(p) > 2):
                role = "Связан"
            else:
                role = "Связан"

            # Build URL to nalog.ru EGRUL page
            url = ""
            if ogrn:
                url = f"https://egrul.nalog.ru/index.html"

            return BusinessRecord(
                company_name=company_name,
                inn=inn,
                ogrn=ogrn,
                role=role,
                status=status,
                registration_date=reg_date,
                address=address,
                source="egrul.nalog.ru",
                url=url,
                confidence="high",
                company_type=company_type,
            )

        except Exception as e:
            logger.debug(f"Parse nalog row error: {e}")
            return None

    def _detect_company_type(self, name: str) -> str:
        """Detect company type from its name."""
        name_upper = name.upper()
        if 'ООО' in name_upper:
            return 'ООО'
        elif 'ИП' in name_upper:
            return 'ИП'
        elif 'ЗАО' in name_upper:
            return 'ЗАО'
        elif 'ОАО' in name_upper or 'ПАО' in name_upper:
            return 'ПАО' if 'ПАО' in name_upper else 'ОАО'
        elif 'АО' in name_upper:
            return 'АО'
        elif 'НКО' in name_upper:
            return 'НКО'
        return ''

    # ===== Rusprofile (Fallback) =====

    def _search_rusprofile(
        self,
        name: str,
        search_directors: bool,
        search_founders: bool,
        limit: int
    ) -> List[BusinessRecord]:
        """Search Rusprofile.ru for person's company affiliations."""
        results = []

        search_url = f"{self.RUSPROFILE_BASE}/search?query={quote(name)}&type=person"

        try:
            response = self.session.get(search_url, timeout=self.timeout)

            if response.status_code != 200:
                logger.warning(f"Rusprofile returned status {response.status_code}")
                return results

            soup = BeautifulSoup(response.text, 'lxml')

            person_cards = soup.select('.search-result-item, .company-item, .search-result')

            for card in person_cards[:limit]:
                try:
                    record = self._parse_rusprofile_card(card)
                    if record:
                        results.append(record)
                except Exception as e:
                    logger.debug(f"Failed to parse Rusprofile card: {e}")
                    continue

        except requests.RequestException as e:
            logger.warning(f"Rusprofile request failed: {e}")

        return results

    def _parse_rusprofile_card(self, card) -> Optional[BusinessRecord]:
        """Parse a Rusprofile search result card."""
        try:
            name_elem = card.select_one('.company-name, .title, a.company-name')
            company_name = name_elem.get_text(strip=True) if name_elem else ""

            if not company_name:
                return None

            inn_match = re.search(r'ИНН[:\s]*(\d{10,12})', card.get_text())
            inn = inn_match.group(1) if inn_match else ""

            ogrn_match = re.search(r'ОГРН[:\s]*(\d{13,15})', card.get_text())
            ogrn = ogrn_match.group(1) if ogrn_match else ""

            status_elem = card.select_one('.status, .company-status')
            status = status_elem.get_text(strip=True) if status_elem else "Действующее"

            role_text = card.get_text().lower()
            if 'руководитель' in role_text or 'директор' in role_text:
                role = "Директор"
            elif 'учредитель' in role_text or 'участник' in role_text:
                role = "Учредитель"
            else:
                role = "Связан"

            link = card.select_one('a[href*="/id/"]')
            url = f"{self.RUSPROFILE_BASE}{link['href']}" if link and link.get('href') else ""

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
                confidence="medium"
            )

        except Exception as e:
            logger.debug(f"Parse error: {e}")
            return None

    # ===== INN Search =====

    def search_by_inn(self, inn: str) -> Optional[BusinessRecord]:
        """Search for company details by INN via nalog.ru."""
        if not inn or not inn.isdigit():
            return None

        try:
            results = self._search_nalog_egrul(inn, limit=1)
            if results:
                return results[0]
        except Exception as e:
            logger.warning(f"INN search failed: {e}")

        return None

    @staticmethod
    def get_manual_search_urls(name: str) -> List[Dict[str, str]]:
        """Generate manual search URLs for the user."""
        encoded = quote(name)
        return [
            {
                'name': 'ЕГРЮЛ (ФНС)',
                'url': f'https://egrul.nalog.ru/',
                'description': 'Официальный реестр юридических лиц и ИП'
            },
            {
                'name': 'Rusprofile.ru',
                'url': f'https://www.rusprofile.ru/search?query={encoded}&type=person',
                'description': 'Поиск компаний и руководителей'
            },
            {
                'name': 'List-org.com',
                'url': f'https://www.list-org.com/search?val={encoded}&type=person',
                'description': 'Каталог организаций России'
            },
        ]


# Singleton instance
business_registry_search = BusinessRegistrySearch()
