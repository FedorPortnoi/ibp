"""
Business Registry Search - Russian ЕГРЮЛ/ЕГРИП
===============================================
Search for company affiliations via official sources.

Sources (in priority order):
1. egrul.nalog.ru (official FNS, free, 2-step token-based API)
2. Rusprofile.ru (scraping fallback)
3. zachestnyibiznes.ru (scraping fallback)

Additional checks:
- check_ip_status() — ИП (individual entrepreneur) registration lookup
- check_fns_tax_debt() — ФНС tax debt check via service.nalog.ru
"""

import json
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
    validation_warning: str = ""

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
            'validation_warning': self.validation_warning,
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
    ZACHESTNYIBIZNES_BASE = "https://zachestnyibiznes.ru"

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

        # Source 3: zachestnyibiznes.ru (fallback if still few results)
        if len(results) < 3:
            time.sleep(0.5)
            try:
                zb_results = self._search_zachestnyibiznes(name, limit)
                results.extend(zb_results)
                logger.info(f"zachestnyibiznes.ru found {len(zb_results)} records")
            except Exception as e:
                logger.warning(f"zachestnyibiznes.ru search failed: {e}")

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

    # ===== zachestnyibiznes.ru (Fallback) =====

    def _search_zachestnyibiznes(self, query: str, limit: int = 50) -> List[BusinessRecord]:
        """Search zachestnyibiznes.ru for company/IP affiliations.

        Works for both name and INN queries.
        URL: https://zachestnyibiznes.ru/search?query=NAME_OR_INN
        """
        results = []
        search_url = f"{self.ZACHESTNYIBIZNES_BASE}/search?query={quote(query)}"

        try:
            response = self.session.get(search_url, timeout=self.timeout)

            if response.status_code in (403, 429):
                logger.warning(f"zachestnyibiznes.ru blocked (HTTP {response.status_code})")
                return results
            if response.status_code != 200:
                logger.warning(f"zachestnyibiznes.ru returned {response.status_code}")
                return results

            soup = BeautifulSoup(response.text, 'lxml')

            # Company/IP links follow pattern: /company/ul/OGRN_INN_SLUG or /company/ip/OGRNIP_INN_SLUG
            company_links = soup.find_all(
                'a', href=lambda h: h and '/company/' in h and h != '/company/select?code=all'
            )

            for link in company_links[:limit]:
                try:
                    record = self._parse_zachestnyibiznes_item(link)
                    if record:
                        results.append(record)
                except Exception as e:
                    logger.debug(f"Parse zachestnyibiznes item error: {e}")

        except requests.RequestException as e:
            logger.warning(f"zachestnyibiznes.ru search failed: {e}")

        return results

    def _parse_zachestnyibiznes_item(self, link) -> Optional[BusinessRecord]:
        """Parse a single zachestnyibiznes.ru search result."""
        try:
            company_name = link.get_text(strip=True)
            if not company_name:
                return None

            href = link.get('href', '')
            url = f"{self.ZACHESTNYIBIZNES_BASE}{href}" if href else ""

            # Extract INN and OGRN from surrounding context
            parent = link.parent
            grandparent = parent.parent if parent else None
            context = grandparent.get_text(separator='|', strip=True) if grandparent else ''

            inn_m = re.search(r'ИНН\|(\d{10,12})', context)
            inn = inn_m.group(1) if inn_m else ''

            ogrn_m = re.search(r'ОГРН(?:ИП)?\|(\d{13,15})', context)
            ogrn = ogrn_m.group(1) if ogrn_m else ''

            # Status
            status = 'Действующее'
            if re.search(r'Ликвидирован|Прекращ', context, re.IGNORECASE):
                status = 'Ликвидировано'

            # Registration date
            date_m = re.search(r'Дата регистрации\|(\d{2}\.\d{2}\.\d{4})', context)
            reg_date = date_m.group(1) if date_m else ''

            # Region/address
            address = ''
            addr_m = re.search(r'(?:область|край|республика|город)[^|]*', context, re.IGNORECASE)
            if addr_m:
                address = addr_m.group().strip()

            # Determine type from href
            is_ip = '/ip/' in href
            company_type = 'ИП' if is_ip else self._detect_company_type(company_name)
            role = 'ИП' if is_ip else 'Связан'

            return BusinessRecord(
                company_name=company_name,
                inn=inn,
                ogrn=ogrn,
                role=role,
                status=status,
                registration_date=reg_date,
                address=address,
                source="zachestnyibiznes.ru",
                url=url,
                confidence="medium",
                company_type=company_type,
            )
        except Exception as e:
            logger.debug(f"Parse zachestnyibiznes item error: {e}")
            return None

    # ===== INN Search =====

    def _validate_business_record_owner(
        self,
        record: BusinessRecord,
        candidate_full_name: str
    ) -> tuple:
        """Validate that a business record belongs to the candidate, not a namesake.

        For ИП records, checks that the candidate's surname appears in the ИП name.
        For legal entities (ООО, ЗАО, etc.), surname check is not applicable.

        Returns:
            (is_valid, reason) tuple.
        """
        if not candidate_full_name or not candidate_full_name.strip():
            return (True, "Имя кандидата не указано — проверка невозможна")

        candidate_last = candidate_full_name.strip().split()[0].lower()

        if record.company_type == "ИП":
            # Strip organizational prefix from name
            normalized = re.sub(
                r'^(ИП|ООО|ЗАО|ОАО|ПАО|АО)\s+', '', record.company_name, flags=re.IGNORECASE
            ).strip().lower()

            if candidate_last in normalized:
                return (True, "Фамилия совпадает")
            else:
                return (
                    False,
                    f"Фамилия кандидата '{candidate_last}' не найдена в названии ИП '{record.company_name}'"
                )

        # Legal entities — can't validate by surname
        return (True, "Юрлицо — проверка по фамилии неприменима")

    def search_by_inn(self, inn: str, candidate_name: str = "") -> List[BusinessRecord]:
        """Search for all companies linked to an INN via nalog.ru.

        A personal INN (12 digits) can be linked to multiple ИП/companies.
        Returns all matches, not just the first.
        Falls back to Rusprofile if nalog.ru is unreachable.

        Args:
            inn: Tax identification number.
            candidate_name: Full name of the candidate for owner validation.
        """
        if not inn or not inn.isdigit():
            return []

        logger.info(f"[EGRUL] Запрос: query='{inn}', тип={'ИНН' if inn.isdigit() else 'имя'}")

        results = []

        # Primary: nalog.ru EGRUL
        try:
            nalog_results = self._search_nalog_egrul(inn, limit=50)
            if nalog_results:
                results = nalog_results
                logger.info(f"INN search: nalog.ru returned {len(results)} records")
        except Exception as e:
            logger.warning(f"INN search nalog.ru failed: {e}")

        # Fallback: Rusprofile by INN
        if not results:
            logger.info(f"INN search: falling back to Rusprofile for INN {inn[:4]}***")
            try:
                rp_results = self._search_rusprofile_by_inn(inn)
                if rp_results:
                    results = rp_results
                    logger.info(f"INN search: Rusprofile returned {len(results)} records")
            except Exception as e:
                logger.warning(f"INN search Rusprofile fallback failed: {e}")

        # Fallback: zachestnyibiznes.ru by INN
        if not results:
            logger.info(f"INN search: falling back to zachestnyibiznes.ru for INN {inn[:4]}***")
            try:
                zb_results = self._search_zachestnyibiznes(inn)
                if zb_results:
                    results = zb_results
                    logger.info(f"INN search: zachestnyibiznes.ru returned {len(results)} records")
            except Exception as e:
                logger.warning(f"INN search zachestnyibiznes.ru fallback failed: {e}")

        # Validate ownership and set confidence
        for r in results:
            if candidate_name:
                is_valid, reason = self._validate_business_record_owner(r, candidate_name)
                if not is_valid:
                    r.confidence = "low"
                    r.validation_warning = reason
                    r.status = "\u26a0\ufe0f Требует проверки (несоответствие имени)"
                    logger.warning(f"[EGRUL] \u26a0\ufe0f Отклонена: {r.company_name} — {reason}")
                else:
                    r.confidence = "high"
                    logger.info(f"[EGRUL] \u2705 Валидна: {r.company_name}")
            else:
                r.confidence = "high"

            logger.info(
                f"[EGRUL] Запись: company='{r.company_name}', "
                f"inn='{r.inn}', type='{r.company_type}', "
                f"status='{r.status}', confidence='{r.confidence}', "
                f"validation_warning='{r.validation_warning}'"
            )

        valid_count = sum(1 for r in results if r.confidence == 'high')
        logger.info(f"[EGRUL] Итого: {len(results)} записей (из них валидных: {valid_count})")

        return results

    def search_by_inn_extended(self, inn: str, full_name: str = '') -> dict:
        """Extended INN search: EGRUL + ИП status + ФНС tax debt.

        Returns dict with 'records' (BusinessRecord list) + 'ip_status' + 'fns_tax_debt'.
        Called automatically by pipeline when extended business intel is needed.
        """
        records = self.search_by_inn(inn)

        ip_data = {}
        fns_data = {}

        # ИП check (most useful for 12-digit individual INNs)
        try:
            ip_data = self.check_ip_status(full_name, inn)
            if ip_data.get('has_ip'):
                logger.info(f"ИП check: found {ip_data.get('ip_count', 0)} active ИП records")
        except Exception as e:
            logger.warning(f"ИП status check failed: {e}")

        # ФНС tax debt check
        try:
            fns_data = self.check_fns_tax_debt(inn)
            if fns_data.get('has_debt'):
                logger.info(f"ФНС tax debt: debt found for INN {inn[:4]}***")
        except Exception as e:
            logger.warning(f"ФНС tax debt check failed: {e}")

        return {
            'records': records,
            'ip_status': ip_data,
            'fns_tax_debt': fns_data,
        }

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

    # ===== ИП Status Check =====

    def check_ip_status(self, full_name: str, inn: str = None) -> dict:
        """
        Check for ИП (individual entrepreneur) registrations.

        Searches nalog.ru EGRUL for ИП records, plus Rusprofile with type=ip.
        A 12-digit INN (individual) can have ИП registered against it.

        Args:
            full_name: Person's full name (Cyrillic)
            inn: Optional INN (12-digit individual preferred)

        Returns:
            {
                'has_ip': bool,
                'ip_records': [{'name': str, 'inn': str, 'ogrn': str,
                                'status': str, 'registration_date': str, 'source': str}],
                'ip_count': int
            }
        """
        result = {
            'has_ip': False,
            'ip_records': [],
            'ip_count': 0,
        }

        # Strategy 1: nalog.ru EGRUL — search by INN (12-digit = individual, may have ИП)
        if inn and inn.isdigit() and len(inn) == 12:
            try:
                logger.info(f"IP check: searching nalog.ru EGRUL by INN {inn[:4]}***")
                nalog_results = self._search_nalog_egrul(inn, limit=50)
                for record in nalog_results:
                    if record.company_type == 'ИП' or record.role == 'ИП':
                        result['ip_records'].append({
                            'name': record.company_name,
                            'inn': record.inn,
                            'ogrn': record.ogrn,
                            'status': record.status,
                            'registration_date': record.registration_date,
                            'source': 'egrul.nalog.ru',
                        })
                if result['ip_records']:
                    logger.info(
                        f"IP check: nalog.ru found {len(result['ip_records'])} ИП records"
                    )
            except Exception as e:
                logger.warning(f"IP check nalog.ru failed: {e}")

        # Strategy 2: nalog.ru EGRUL — search by name (catches ИП even without INN)
        if not result['ip_records'] and full_name:
            try:
                logger.info(f"IP check: searching nalog.ru EGRUL by name '{full_name}'")
                name_results = self._search_nalog_egrul(full_name, limit=50)
                seen_ogrns = {r['ogrn'] for r in result['ip_records'] if r.get('ogrn')}
                for record in name_results:
                    if record.company_type == 'ИП' or record.role == 'ИП':
                        if record.ogrn and record.ogrn in seen_ogrns:
                            continue
                        result['ip_records'].append({
                            'name': record.company_name,
                            'inn': record.inn,
                            'ogrn': record.ogrn,
                            'status': record.status,
                            'registration_date': record.registration_date,
                            'source': 'egrul.nalog.ru',
                        })
                        if record.ogrn:
                            seen_ogrns.add(record.ogrn)
                if result['ip_records']:
                    logger.info(
                        f"IP check: nalog.ru by name found {len(result['ip_records'])} ИП records"
                    )
            except Exception as e:
                logger.warning(f"IP check nalog.ru by name failed: {e}")

        # Strategy 3: Rusprofile with type=ip (fallback)
        if not result['ip_records'] and full_name:
            time.sleep(0.3)
            try:
                logger.info(f"IP check: searching Rusprofile type=ip for '{full_name}'")
                rp_ip_records = self._search_rusprofile_ip(full_name)
                seen_ogrns = {r['ogrn'] for r in result['ip_records'] if r.get('ogrn')}
                for rp in rp_ip_records:
                    if rp.ogrn and rp.ogrn in seen_ogrns:
                        continue
                    result['ip_records'].append({
                        'name': rp.company_name,
                        'inn': rp.inn,
                        'ogrn': rp.ogrn,
                        'status': rp.status,
                        'registration_date': rp.registration_date,
                        'source': 'Rusprofile.ru',
                    })
                    if rp.ogrn:
                        seen_ogrns.add(rp.ogrn)
            except Exception as e:
                logger.warning(f"IP check Rusprofile failed: {e}")

        result['has_ip'] = len(result['ip_records']) > 0
        result['ip_count'] = len(result['ip_records'])
        logger.info(
            f"IP check complete: has_ip={result['has_ip']}, count={result['ip_count']}"
        )
        return result

    def _search_rusprofile_ip(self, full_name: str) -> List[BusinessRecord]:
        """Search Rusprofile for ИП registrations (type=ip).

        URL: /search?query=NAME&type=ip
        Returns BusinessRecord list with ИП entries.
        """
        results = []
        search_url = f"{self.RUSPROFILE_BASE}/search?query={quote(full_name)}&type=ip"

        try:
            response = self.session.get(search_url, timeout=self.timeout)

            if response.status_code in (403, 429):
                logger.warning(
                    f"Rusprofile IP search blocked (HTTP {response.status_code})"
                )
                return results
            if response.status_code == 404:
                logger.warning("Rusprofile IP search returned 404")
                return results
            if response.status_code != 200:
                logger.warning(f"Rusprofile IP search returned {response.status_code}")
                return results

            soup = BeautifulSoup(response.text, 'lxml')
            items = soup.select('.company-item, .list-element')

            for item in items[:10]:
                try:
                    record = self._parse_rusprofile_ip_item(item)
                    if record:
                        results.append(record)
                except Exception as e:
                    logger.debug(f"Parse Rusprofile IP item error: {e}")

        except requests.RequestException as e:
            logger.warning(f"Rusprofile IP search failed: {e}")

        logger.debug(f"Rusprofile IP search: {len(results)} records")
        return results

    def _parse_rusprofile_ip_item(self, item) -> Optional[BusinessRecord]:
        """Parse a Rusprofile ИП search result item."""
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
            status_elem = item.select_one(
                '.company-item__status.is_red, .list-element__text.danger'
            )
            if status_elem and 'ликвидир' in status_elem.get_text(strip=True).lower():
                status = "Ликвидировано"
            elif status_elem and 'прекращ' in status_elem.get_text(strip=True).lower():
                status = "Прекращено"
            else:
                status = "Действующее"

            # INN, OGRNIP from info row
            info_text = item.get_text()
            inn_m = re.search(r'ИНН[:\s]*(\d{10,12})', info_text)
            inn = inn_m.group(1) if inn_m else ""
            ogrn_m = re.search(r'ОГРНИП[:\s]*(\d{15})', info_text)
            if not ogrn_m:
                ogrn_m = re.search(r'ОГРН[:\s]*(\d{13,15})', info_text)
            ogrn = ogrn_m.group(1) if ogrn_m else ""
            date_m = re.search(
                r'(?:Дата регистрации|Зарегистрирован)[:\s]*([\d.]+)', info_text
            )
            reg_date = date_m.group(1) if date_m else ""

            # Address
            addr_elem = item.select_one('.company-item__text, .list-element__address')
            address = addr_elem.get_text(strip=True) if addr_elem else ""

            return BusinessRecord(
                company_name=company_name,
                inn=inn,
                ogrn=ogrn,
                role="ИП",
                status=status,
                registration_date=reg_date,
                address=address,
                source="Rusprofile.ru",
                url=url,
                confidence="medium",
                company_type="ИП",
            )
        except Exception as e:
            logger.debug(f"Parse Rusprofile IP item error: {e}")
            return None

    # ===== ФНС Tax Debt Check =====

    def check_fns_tax_debt(self, inn: str) -> dict:
        """
        Check for tax debts via service.nalog.ru.

        Uses the ФНС public tax debt service (service.nalog.ru/zd.do).
        This service may require CAPTCHA or may be unreliable.
        Failures are handled gracefully — never crashes.

        Args:
            inn: Tax identification number (10 or 12 digits)

        Returns:
            {
                'checked': bool,       # True if check completed
                'has_debt': bool|None,  # True/False/None if couldn't determine
                'source': str,
                'details': str,        # Brief description of result
                'error': str|None      # Error message if check failed
            }
        """
        result = {
            'checked': False,
            'has_debt': None,
            'source': 'service.nalog.ru',
            'details': '',
            'error': None,
        }

        if not inn or not inn.isdigit() or len(inn) not in (10, 12):
            result['error'] = f'Некорректный ИНН: {inn}'
            return result

        logger.info(f"FNS tax debt check: INN {inn[:4]}***")

        # Method 1: service.nalog.ru/zd.do — public tax debt checker
        # This service accepts INN and returns debt status via AJAX
        try:
            # Step 1: Initialize session with the service page
            init_url = "https://service.nalog.ru/zd.do"
            try:
                init_resp = self.session.get(
                    init_url,
                    headers={
                        **self.HEADERS,
                        'Accept': 'text/html,application/xhtml+xml,*/*;q=0.8',
                    },
                    timeout=self.timeout,
                )
                if init_resp.status_code != 200:
                    logger.warning(
                        f"FNS tax debt: init page returned {init_resp.status_code}"
                    )
                    result['error'] = f'Сервис ФНС недоступен (HTTP {init_resp.status_code})'
                    return result
            except requests.RequestException as e:
                logger.warning(f"FNS tax debt: init page failed: {e}")
                result['error'] = f'Сервис ФНС недоступен: {e}'
                return result

            # Check for CAPTCHA requirement
            if 'captcha' in init_resp.text.lower():
                logger.warning("FNS tax debt: CAPTCHA required — skipping")
                result['error'] = 'Требуется CAPTCHA на service.nalog.ru'
                result['details'] = 'Автоматическая проверка заблокирована CAPTCHA'
                return result

            # Step 2: Submit INN for debt check via AJAX
            time.sleep(0.5)
            check_url = "https://service.nalog.ru/zd-json.do"
            try:
                check_resp = self.session.post(
                    check_url,
                    data={
                        'inn': inn,
                        'captcha': '',
                        'captchaToken': '',
                    },
                    headers={
                        **self.HEADERS,
                        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                        'Origin': 'https://service.nalog.ru',
                        'Referer': init_url,
                        'X-Requested-With': 'XMLHttpRequest',
                    },
                    timeout=self.timeout,
                )
            except requests.RequestException as e:
                logger.warning(f"FNS tax debt: AJAX check failed: {e}")
                result['error'] = f'Запрос к ФНС не выполнен: {e}'
                return result

            if check_resp.status_code != 200:
                logger.warning(
                    f"FNS tax debt: check returned {check_resp.status_code}"
                )
                result['error'] = (
                    f'Сервис ФНС вернул HTTP {check_resp.status_code}'
                )
                return result

            # Debug: log raw response for troubleshooting
            content_type = check_resp.headers.get('Content-Type', '')
            logger.info(f"FNS response status: {check_resp.status_code}")
            logger.info(f"FNS response Content-Type: {content_type}")
            logger.info(
                f"FNS response text (first 500): {check_resp.text[:500]}"
            )

            # Step 3: Parse response — JSON or HTML
            if 'json' in content_type or check_resp.text.strip().startswith('{'):
                try:
                    data = check_resp.json()
                    logger.info(f"FNS JSON keys: {list(data.keys())}")
                    logger.info(f"FNS JSON data: {data}")

                    # CAPTCHA check (multiple field name variants)
                    captcha_val = (
                        data.get('captchaRequired')
                        or data.get('CAPTCHA_REQUIRED')
                    )
                    captcha_text = str(
                        data.get('CAPTCHA', data.get('captcha', ''))
                    )
                    if captcha_val or captcha_text.lower() in ('true', '1'):
                        result['checked'] = False
                        result['error'] = 'Требуется CAPTCHA'
                        result['details'] = 'Повторите проверку вручную'
                        return result

                    result['checked'] = True

                    # Parse errors field
                    errors = str(data.get('ERRORS', data.get('errors', '')))
                    if errors and errors.lower() not in ('', 'none'):
                        result['error'] = errors
                        result['details'] = errors
                        logger.warning(f"FNS tax debt: service error: {errors}")
                        return result

                    # ФНС zd-json.do response format:
                    # {"ERRORS":"","CAPTCHA":"","COMPLETED":true,
                    #  "TOTAL":0, "RECORDS":[...]}
                    # RECORDS is a list of debt entries; empty = no debt
                    records = data.get('RECORDS', data.get('records', None))
                    total = data.get('TOTAL', data.get('total', None))

                    if records is not None or total is not None:
                        # FNS standard format with RECORDS/TOTAL
                        if records is not None:
                            has_records = (
                                len(records) > 0
                                if isinstance(records, list)
                                else bool(records)
                            )
                        else:
                            has_records = (
                                total is not None and int(total) > 0
                            )

                        if has_records:
                            result['has_debt'] = True
                            if isinstance(records, list) and records:
                                # Extract debt amounts from records
                                debts = []
                                for rec in records:
                                    amt = rec.get(
                                        'DEBT', rec.get(
                                            'debt', rec.get(
                                                'SUM', rec.get('sum', '')
                                            )
                                        )
                                    )
                                    if amt:
                                        debts.append(str(amt))
                                if debts:
                                    result['details'] = (
                                        f'Обнаружена задолженность: '
                                        f'{", ".join(debts)} руб.'
                                    )
                                else:
                                    result['details'] = (
                                        'Обнаружена задолженность по налогам'
                                    )
                                result['raw_text'] = str(records)[:500]
                            else:
                                result['details'] = (
                                    'Обнаружена задолженность по налогам'
                                )
                        else:
                            result['has_debt'] = False
                            result['details'] = (
                                'Задолженность по налогам не обнаружена'
                            )
                    else:
                        # Legacy format: code/message fields
                        code = data.get('code')
                        message = data.get('message', '')

                        if code == 0 or 'не обнаружен' in message.lower():
                            result['has_debt'] = False
                            result['details'] = (
                                'Задолженность по налогам не обнаружена'
                            )
                        elif code == 1 or 'обнаружен' in message.lower():
                            result['has_debt'] = True
                            debt_amount = data.get(
                                'debt', data.get('sum', '')
                            )
                            if debt_amount:
                                result['details'] = (
                                    f'Обнаружена задолженность: {debt_amount}'
                                )
                            else:
                                result['details'] = (
                                    'Обнаружена задолженность по налогам'
                                )
                        else:
                            # Check full JSON text for debt keywords
                            json_text = str(data).lower()
                            if ('не имеет' in json_text
                                    or 'отсутствует' in json_text
                                    or 'не обнаружен' in json_text):
                                result['has_debt'] = False
                                result['details'] = (
                                    'Задолженность по налогам не обнаружена'
                                )
                            elif ('задолженность' in json_text
                                    and ('имеет' in json_text
                                         or 'обнаружен' in json_text)):
                                result['has_debt'] = True
                                result['details'] = (
                                    'Обнаружена задолженность по налогам'
                                )
                            else:
                                result['details'] = (
                                    message
                                    or f'Код ответа: {code}'
                                )

                    logger.info(
                        f"FNS tax debt: checked=True, "
                        f"has_debt={result['has_debt']}, "
                        f"details='{result['details']}'"
                    )
                    return result

                except (ValueError, KeyError) as e:
                    logger.warning(f"FNS tax debt: JSON parse error: {e}")
                    # Fall through to HTML parsing

            # HTML response — parse with BeautifulSoup
            try:
                soup = BeautifulSoup(check_resp.text, 'lxml')
                result['checked'] = True

                page_text = soup.get_text(separator=' ', strip=True).lower()
                logger.info(
                    f"FNS parsed text (first 300): {page_text[:300]}"
                )

                if ('не обнаружен' in page_text
                        or 'не имеет' in page_text
                        or 'отсутствует' in page_text):
                    result['has_debt'] = False
                    result['details'] = (
                        'Задолженность по налогам не обнаружена'
                    )
                elif 'задолженность' in page_text and (
                    'обнаружен' in page_text
                    or 'имеется' in page_text
                    or 'имеет' in page_text
                ):
                    result['has_debt'] = True
                    result['details'] = (
                        'Обнаружена задолженность по налогам'
                    )
                elif 'captcha' in page_text or 'капча' in page_text:
                    result['checked'] = False
                    result['has_debt'] = None
                    result['error'] = 'Требуется CAPTCHA'
                    result['details'] = 'Проверка заблокирована CAPTCHA'
                else:
                    result['has_debt'] = None
                    result['details'] = (
                        'Результат проверки неоднозначен — '
                        'рекомендуется ручная проверка на service.nalog.ru'
                    )
                    result['raw_text'] = page_text[:500]

                logger.info(
                    f"FNS tax debt (HTML): checked={result['checked']}, "
                    f"has_debt={result['has_debt']}"
                )
            except Exception as e:
                logger.warning(f"FNS tax debt: HTML parse error: {e}")
                result['error'] = f'Ошибка разбора ответа ФНС: {e}'

        except Exception as e:
            logger.error(f"FNS tax debt: unexpected error: {e}")
            result['error'] = f'Непредвиденная ошибка: {e}'

        return result

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
                'name': 'Zachestnyibiznes.ru',
                'url': f'https://zachestnyibiznes.ru/search?query={encoded}',
                'description': 'Проверка контрагентов, ИП и юридических лиц'
            },
            {
                'name': 'List-org.com',
                'url': f'https://www.list-org.com/search?val={encoded}&type=person',
                'description': 'Каталог организаций России'
            },
            {
                'name': 'ФНС Задолженность',
                'url': 'https://service.nalog.ru/zd.do',
                'description': 'Проверка налоговой задолженности по ИНН'
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


def check_ip_status(full_name: str, inn: str = None) -> dict:
    """
    Module-level convenience function: check for ИП registrations.

    Searches nalog.ru EGRUL and Rusprofile for ИП (individual entrepreneur)
    records associated with the given person.

    Called by the pipeline at Stage 0 (identity confirmation) or Stage 1
    (government registries). If not yet wired into pipeline.py, call manually:

        from app.services.phase3.business_registry import check_ip_status
        ip_data = check_ip_status('Иванов Иван Иванович', inn='123456789012')

    Args:
        full_name: Person's full name (Cyrillic)
        inn: Optional INN (12-digit individual preferred)

    Returns:
        {
            'has_ip': bool,
            'ip_records': [{'name', 'inn', 'ogrn', 'status',
                            'registration_date', 'source'}],
            'ip_count': int
        }
    """
    return business_registry_search.check_ip_status(full_name, inn)


def check_fns_tax_debt(inn: str) -> dict:
    """
    Module-level convenience function: check for ФНС tax debts.

    Queries service.nalog.ru/zd.do for tax debt status. May be blocked by
    CAPTCHA — failures are handled gracefully.

    Called by the pipeline at Stage 0 or Stage 1. If not yet wired, call:

        from app.services.phase3.business_registry import check_fns_tax_debt
        tax_data = check_fns_tax_debt('123456789012')

    Args:
        inn: Tax identification number (10 or 12 digits)

    Returns:
        {
            'checked': bool,
            'has_debt': bool|None,
            'source': str,
            'details': str,
            'error': str|None
        }
    """
    return business_registry_search.check_fns_tax_debt(inn)


def search_by_inn_extended(inn: str, full_name: str = '') -> dict:
    """Module-level convenience: EGRUL + ИП status + ФНС tax debt."""
    return business_registry_search.search_by_inn_extended(inn, full_name)
