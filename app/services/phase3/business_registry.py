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

        logger.info(f"Business registry search: name='{name}', limit={limit}")

        # Source 1: nalog.ru EGRUL (primary — official, reliable)
        try:
            nalog_results = self._search_nalog_egrul(name, limit)
            results.extend(nalog_results)
            logger.info(f"nalog.ru EGRUL: {len(nalog_results)} records")
            for r in nalog_results[:3]:
                logger.info(f"  nalog.ru: {r.company_name} | INN: {r.inn} | {r.role}")
        except Exception as e:
            logger.warning(f"nalog.ru EGRUL search failed: {e}")

        # Source 2: Rusprofile (fallback if nalog.ru returned few results)
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
        """Parse a nalog.ru EGRUL search result row.

        Actual API response fields:
        - k: type ("fl" = ИП/individual, "ul" = company)
        - n: name (person name for FL, company name for UL)
        - i: INN
        - o: OGRN / OGRNIP
        - r: registration date (DD.MM.YYYY)
        - c: company short name (UL only)
        - a: address (UL only)
        - g: end/liquidation date (if liquidated)
        - p: director name (UL only)
        - t: detail token
        - cnt/tot/pg: pagination
        """
        try:
            record_type = row.get('k', '')  # "fl" or "ul"
            name = row.get('n', '')
            inn = row.get('i', '')
            ogrn = row.get('o', '')
            reg_date = row.get('r', '')
            end_date = row.get('g', '')

            if not name and not inn:
                return None

            if record_type == 'fl':
                # Individual entrepreneur (ИП)
                company_name = f"ИП {name}"
                company_type = "ИП"
                role = "ИП"
                address = ''
                status = "Ликвидировано" if end_date else "Действующее"
            else:
                # Company (UL)
                company_name = row.get('c', '') or name
                company_type = self._detect_company_type(company_name)
                address = row.get('a', '')
                director = row.get('p', '')
                status = "Ликвидировано" if end_date else "Действующее"

                # Determine role based on whether director matches search name
                name_parts = search_name.lower().split()
                if director and any(p in director.lower() for p in name_parts if len(p) > 2):
                    role = "Директор"
                else:
                    role = "Связан"

            # Build URL to nalog.ru EGRUL page
            url = "https://egrul.nalog.ru/index.html"

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
        """Search Rusprofile.ru for person's company affiliations.

        Two-step process:
        1. Search with type=fl to find matching physical persons
        2. For the best match, fetch the person profile page and extract all companies

        URL structure (current as of 2026):
        - Person search: /search?query=NAME&type=fl
        - Person profile: /person/SLUG-INN  (e.g. /person/kuznecov-iyu-183511206113)
        - Company page:   /id/OGRN
        - ИП page:        /ip/OGRNIP
        """
        results = []

        # Step 1: Find matching person records
        search_url = f"{self.RUSPROFILE_BASE}/search?query={quote(name)}&type=fl"

        try:
            response = self.session.get(search_url, timeout=self.timeout)

            if response.status_code in (403, 429):
                logger.warning(
                    f"Rusprofile blocked (HTTP {response.status_code}) — "
                    "likely anti-bot protection. nalog.ru EGRUL is the primary source."
                )
                return results
            if response.status_code == 404:
                logger.warning(
                    "Rusprofile returned 404 — URL structure may have changed. "
                    "Falling back to nalog.ru EGRUL."
                )
                return results
            if response.status_code != 200:
                logger.warning(f"Rusprofile FL search returned status {response.status_code}")
                return results

            soup = BeautifulSoup(response.text, 'lxml')
            person_items = soup.select('.list-element')

            if not person_items:
                logger.debug("Rusprofile: no FL person items found in search")
                return results

            # Take the first matching person (best match by Rusprofile ranking)
            # and fetch their profile page for full company list
            first_item = person_items[0]
            link = first_item.select_one('a.list-element__title')
            if not link or not link.get('href'):
                logger.debug("Rusprofile: no link found for first FL result")
                return results

            person_href = link.get('href')
            person_url = f"{self.RUSPROFILE_BASE}{person_href}"
            logger.debug(f"Rusprofile: fetching person page {person_url}")

        except requests.RequestException as e:
            logger.warning(f"Rusprofile FL search failed: {e}")
            return results

        # Step 2: Fetch the person's profile page and extract all companies
        time.sleep(0.3)
        try:
            profile_resp = self.session.get(person_url, timeout=self.timeout)

            if profile_resp.status_code != 200:
                logger.warning(f"Rusprofile person page returned {profile_resp.status_code}")
                return results

            profile_soup = BeautifulSoup(profile_resp.text, 'lxml')
            company_items = profile_soup.select('.list-element')

            for item in company_items[:limit]:
                try:
                    record = self._parse_rusprofile_person_company(item)
                    if record:
                        results.append(record)
                except Exception as e:
                    logger.debug(f"Failed to parse Rusprofile company item: {e}")
                    continue

        except requests.RequestException as e:
            logger.warning(f"Rusprofile person profile fetch failed: {e}")

        logger.debug(f"Rusprofile: extracted {len(results)} records from {person_url}")
        return results

    def _parse_rusprofile_person_company(self, item) -> Optional[BusinessRecord]:
        """Parse a company list-element from a Rusprofile person profile page.

        The item structure:
        <div class="list-element">
          <a class="list-element__title"
             data-track-click="not_masked,fl_dash_ceo_company,to_ul,link"
             href="/id/11417314"> ООО "Калинка Комфорт" </a>
          <div class="list-element__text danger">Ликвидирован</div>  <!-- optional -->
          <span class="list-element__text">OKVED description</span>
          <div class="list-element__address">City/Region</div>
          <div class="list-element__row-info">
            <span>ИНН: 1831190000</span>
            <span>ОГРН: 1181832009523</span>
            <span>Дата регистрации: 20.04.2018</span>
          </div>
        </div>

        Role is encoded in data-track-click:
        - fl_dash_ceo_company  → Директор
        - fl_dash_founder_company → Учредитель
        - fl_dash_ip           → ИП
        """
        try:
            link = item.select_one('a.list-element__title')
            if not link:
                return None

            company_name = link.get_text(strip=True)
            if not company_name:
                return None

            href = link.get('href', '')
            url = f"{self.RUSPROFILE_BASE}{href}" if href else ""

            # Determine role from data-track-click attribute
            track = link.get('data-track-click', '')
            if 'fl_dash_ceo' in track or 'ceo_company' in track:
                role = "Директор"
            elif 'fl_dash_founder' in track or 'founder_company' in track:
                role = "Учредитель"
            elif 'fl_dash_ip' in track or 'to_ip' in track:
                role = "ИП"
            else:
                role = "Связан"

            # Status: look for danger-class text element (Ликвидирован, etc.)
            status_danger = item.select_one('.list-element__text.danger')
            if status_danger:
                status_text = status_danger.get_text(strip=True)
                if 'ликвидир' in status_text.lower():
                    status = "Ликвидировано"
                else:
                    status = status_text
            else:
                status = "Действующее"

            # OKVED description (non-danger text element)
            okved_name = ""
            for span in item.select('.list-element__text, span.list-element__text'):
                if 'danger' not in (span.get('class') or []):
                    okved_name = span.get_text(strip=True)
                    if okved_name:
                        break

            # Address
            addr_elem = item.select_one('.list-element__address')
            address = addr_elem.get_text(strip=True) if addr_elem else ""

            # INN, OGRN, registration date from row-info spans
            row_info = item.select_one('.list-element__row-info')
            inn = ""
            ogrn = ""
            reg_date = ""
            if row_info:
                info_text = row_info.get_text()
                inn_m = re.search(r'ИНН[:\s]*(\d{10,12})', info_text)
                inn = inn_m.group(1) if inn_m else ""
                # ОГРН (13 digits for UL) or ОГРНИП (15 digits for ИП)
                ogrn_m = re.search(r'ОГРН(?:ИП)?[:\s]*(\d{13,15})', info_text)
                ogrn = ogrn_m.group(1) if ogrn_m else ""
                date_m = re.search(r'Дата регистрации[:\s]*([\d.]+)', info_text)
                reg_date = date_m.group(1) if date_m else ""

            company_type = self._detect_company_type(company_name)

            return BusinessRecord(
                company_name=company_name,
                inn=inn,
                ogrn=ogrn,
                role=role,
                status=status,
                registration_date=reg_date,
                address=address,
                source="Rusprofile.ru",
                url=url,
                confidence="medium",
                company_type=company_type,
                okved_name=okved_name,
            )

        except Exception as e:
            logger.debug(f"Parse rusprofile company item error: {e}")
            return None

    # ===== INN Search =====

    def search_by_inn(self, inn: str) -> List[BusinessRecord]:
        """Search for all companies linked to an INN via nalog.ru.

        A personal INN (12 digits) can be linked to multiple ИП/companies.
        Returns all matches, not just the first.
        Falls back to Rusprofile if nalog.ru is unreachable.
        """
        if not inn or not inn.isdigit():
            return []

        logger.info(f"INN search: querying nalog.ru for INN {inn[:4]}***")

        # Primary: nalog.ru EGRUL
        try:
            results = self._search_nalog_egrul(inn, limit=50)
            if results:
                for r in results:
                    r.confidence = "high"
                logger.info(f"INN search: nalog.ru returned {len(results)} records")
                return results
            logger.info("INN search: nalog.ru returned 0 records")
        except Exception as e:
            logger.warning(f"INN search nalog.ru failed: {e}")

        # Fallback: Rusprofile by INN
        logger.info(f"INN search: falling back to Rusprofile for INN {inn[:4]}***")
        try:
            rp_results = self._search_rusprofile_by_inn(inn)
            if rp_results:
                for r in rp_results:
                    r.confidence = "high"
                logger.info(f"INN search: Rusprofile returned {len(rp_results)} records")
                return rp_results
            logger.info("INN search: Rusprofile returned 0 records")
        except Exception as e:
            logger.warning(f"INN search Rusprofile fallback failed: {e}")

        return []

    def _search_rusprofile_by_inn(self, inn: str) -> List[BusinessRecord]:
        """Search Rusprofile by INN — fallback when nalog.ru is unreachable."""
        results = []
        search_url = f"{self.RUSPROFILE_BASE}/search?query={inn}"

        try:
            response = self.session.get(search_url, timeout=self.timeout)
            if response.status_code in (403, 429):
                logger.warning(f"Rusprofile INN search blocked (HTTP {response.status_code})")
                return results
            if response.status_code != 200:
                return results

            soup = BeautifulSoup(response.text, 'lxml')

            # Rusprofile INN search returns company cards directly
            company_items = soup.select('.company-item, .list-element')
            for item in company_items[:10]:
                try:
                    record = self._parse_rusprofile_inn_result(item, inn)
                    if record:
                        results.append(record)
                except Exception as e:
                    logger.debug(f"Parse Rusprofile INN item error: {e}")

        except requests.RequestException as e:
            logger.warning(f"Rusprofile INN search failed: {e}")

        return results

    def _parse_rusprofile_inn_result(self, item, search_inn: str) -> Optional[BusinessRecord]:
        """Parse a Rusprofile search result item for INN-based search."""
        try:
            link = item.select_one('a.company-item__title, a.list-element__title')
            if not link:
                return None

            company_name = link.get_text(strip=True)
            if not company_name:
                return None

            href = link.get('href', '')
            url = f"{self.RUSPROFILE_BASE}{href}" if href else ""

            # Status
            status_elem = item.select_one('.company-item__status.is_red, .list-element__text.danger')
            if status_elem and 'ликвидир' in status_elem.get_text(strip=True).lower():
                status = "Ликвидировано"
            else:
                status = "Действующее"

            # INN, OGRN from info row
            info_text = item.get_text()
            inn_m = re.search(r'ИНН[:\s]*(\d{10,12})', info_text)
            inn = inn_m.group(1) if inn_m else search_inn
            ogrn_m = re.search(r'ОГРН(?:ИП)?[:\s]*(\d{13,15})', info_text)
            ogrn = ogrn_m.group(1) if ogrn_m else ""
            date_m = re.search(r'(?:Дата регистрации|Зарегистрирован)[:\s]*([\d.]+)', info_text)
            reg_date = date_m.group(1) if date_m else ""

            # Address
            addr_elem = item.select_one('.company-item__text, .list-element__address')
            address = addr_elem.get_text(strip=True) if addr_elem else ""

            company_type = self._detect_company_type(company_name)

            return BusinessRecord(
                company_name=company_name,
                inn=inn,
                ogrn=ogrn,
                role="Связан",
                status=status,
                registration_date=reg_date,
                address=address,
                source="Rusprofile.ru",
                url=url,
                confidence="high",
                company_type=company_type,
            )
        except Exception as e:
            logger.debug(f"Parse Rusprofile INN result error: {e}")
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
                'url': f'https://www.rusprofile.ru/search?query={encoded}&type=fl',
                'description': 'Поиск физических лиц, руководителей и учредителей'
            },
            {
                'name': 'List-org.com',
                'url': f'https://www.list-org.com/search?val={encoded}&type=person',
                'description': 'Каталог организаций России'
            },
        ]


def filter_business_records_by_inn(records: list, confirmed_inn: str) -> list:
    """
    Filter business records using INN as ground truth.

    1. Record INN matches confirmed_inn → keep (confidence=1.0, inn_verified=True)
    2. Record has DIFFERENT INN → keep only if name_similarity >= 0.85
    3. Record has NO INN → keep only if name_similarity >= 0.75

    Returns records with added 'confidence' and 'inn_verified' fields.
    """
    if not records or not confirmed_inn:
        return records

    confirmed_inn = confirmed_inn.strip()
    filtered = []

    for record in records:
        record_inn = (record.get('inn') or '').strip()
        name_sim = record.get('name_similarity',
                              record.get('similarity', 0.5))

        if record_inn and record_inn == confirmed_inn:
            # INN match — highest confidence
            record['confidence'] = 1.0
            record['inn_verified'] = True
            filtered.append(record)
        elif record_inn and record_inn != confirmed_inn:
            # Different INN — require high name similarity
            if name_sim >= 0.85:
                record['confidence'] = round(name_sim * 0.8, 2)
                record['inn_verified'] = False
                filtered.append(record)
            else:
                logger.debug(
                    f"INN filter: dropped '{record.get('company_name', '?')}' "
                    f"(INN mismatch, sim={name_sim:.2f})"
                )
        else:
            # No INN on record — require decent name similarity
            if name_sim >= 0.75:
                record['confidence'] = round(name_sim * 0.7, 2)
                record['inn_verified'] = False
                filtered.append(record)
            else:
                logger.debug(
                    f"INN filter: dropped '{record.get('company_name', '?')}' "
                    f"(no INN, sim={name_sim:.2f})"
                )

    logger.info(
        f"INN filter: {len(records)} → {len(filtered)} records "
        f"(confirmed_inn={confirmed_inn[:4]}***)"
    )
    return filtered


# Singleton instance
business_registry_search = BusinessRegistrySearch()
