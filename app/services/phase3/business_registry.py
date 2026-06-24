"""
Business Registry Search - Russian ЕГРЮЛ/ЕГРИП
===============================================
Search for company affiliations via official sources.

Sources (in priority order):
1. egrul.org       — free JSON API, same FNS source as Контур.Фокус (100 req/day)
2. egrul.nalog.ru  — official FNS search fallback (basic data + 1 director)
3. Rusprofile.ru   — person profile page by INN (/person/p-INN), returns roles

Additional checks:
- check_ip_status() — ИП (individual entrepreneur) registration lookup
- check_fns_tax_debt() — ФНС tax debt check via service.nalog.ru
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
    2. Rusprofile.ru — INN-based person profile fallback (/person/p-{INN})
    """

    EGRUL_ORG_BASE = "https://egrul.org"
    NALOG_BASE = "https://egrul.nalog.ru"
    RUSPROFILE_BASE = "https://www.rusprofile.ru"

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
        limit: int = 50,
        egrul_cache: dict = None,
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

        # Source 1: nalog.ru EGRUL (name search — egrul.org has no name search endpoint)
        try:
            nalog_results = self._search_nalog_egrul(name, limit)
            results.extend(nalog_results)
            logger.info(f"nalog.ru EGRUL: {len(nalog_results)} records")
            for r in nalog_results[:3]:
                logger.info(f"  nalog.ru: {r.company_name} | INN: {r.inn} | {r.role}")
        except Exception as e:
            logger.warning(f"nalog.ru EGRUL search failed: {e}")

        # Enrich nalog.ru results via egrul.org (fills capital, OKVED, full address).
        # Raw JSON is cached by company INN for the role resolution pass below.
        if egrul_cache is None:
            egrul_cache = {}
        if results:
            for record in results[:10]:  # cap at 10 to stay within 100/day limit
                try:
                    self._enrich_record_from_egrul_org(record, egrul_cache)
                except Exception as e:
                    logger.debug(f"egrul.org enrichment for {record.inn}: {e}")

        # Role resolution pass — no extra HTTP calls, uses cached JSON
        if egrul_cache:
            try:
                self._resolve_roles_from_cache(results, name, egrul_cache)
            except Exception as e:
                logger.debug(f"egrul.org role resolution pass: {e}")

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

    # ===== egrul.org (Primary Source) =====

    def _fetch_egrul_org_raw(self, query: str) -> Optional[dict]:
        """Fetch raw egrul.org JSON for an INN/OGRN. Returns None on failure."""
        url = f"{self.EGRUL_ORG_BASE}/{query}.json"
        try:
            resp = self.session.get(url, timeout=self.timeout)
            if resp.status_code == 404:
                return None
            if resp.status_code != 200:
                logger.warning("egrul.org: HTTP %s for %s", resp.status_code, query)
                return None
            return resp.json()
        except Exception as exc:
            logger.warning("egrul.org fetch failed: %s", exc)
            return None

    def _search_egrul_org(self, query: str) -> List[BusinessRecord]:
        """
        GET https://egrul.org/{INN_or_OGRN}.json
        Returns full FNS data — same source as Контур.Фокус. Free, 100 req/day.

        Works for:
          - 10-digit company INN  → legal entity record
          - 12-digit personal INN → ИП record (if the person has registered as ИП)
          - 13-digit OGRN         → legal entity record
          - 15-digit ОГРНИП       → ИП record
        """
        data = self._fetch_egrul_org_raw(query)
        if data is None:
            return []
        return self._parse_egrul_org_to_records(data, query)

    def _parse_egrul_org_to_records(self, data: dict, query: str) -> List[BusinessRecord]:
        """Parse egrul.org JSON into BusinessRecord(s)."""
        from app.services.company.egrul_service import (
            _attrs, _as_list, _fio, _parse_address, _parse_okveds,
            _normalize_status,
        )
        from app.services.shared.court_utils import detect_company_type

        ul_data = data.get('СвЮЛ')
        ip_data = data.get('СвИП')
        root    = ul_data or ip_data or data
        is_ip   = ip_data is not None and ul_data is None

        if not root or not isinstance(root, dict):
            return []

        a    = _attrs(root)
        inn  = a.get('ИНН', '')
        ogrn = a.get('ОГРН', a.get('ОГРНИП', ''))
        kpp  = a.get('КПП', '')

        if not inn and not ogrn:
            return []

        # Name
        if is_ip:
            fio      = a.get('ФИОПолн', '')
            name     = f"ИП {fio}" if fio else f"ИП (ИНН {inn})"
            ctype    = 'ИП'
            role     = 'ИП'
        else:
            nb    = root.get('СвНаимЮЛ', {})
            na    = _attrs(nb)
            name  = na.get('НаимЮЛСокр', '') or na.get('НаимЮЛПолн', '') or a.get('НаимЮЛСокр', '')
            ctype = detect_company_type(name)
            # Determine role: director or founder — left as 'Связан' since
            # role context comes from the candidate's name matching,
            # which happens in the pipeline layer, not here.
            role = 'Связан'

        end_date = a.get('ДатаПрекрЮЛ', a.get('ДатаПрекрИП', ''))
        reg_date = a.get('ДатаОГРН', a.get('ДатаОГРНИП', ''))
        status   = _normalize_status(_attrs(root.get('СвСтатус', {})).get('НаимСтатусЮЛ', ''))
        if end_date:
            status = 'Ликвидировано'

        address, _ = _parse_address(root.get('СвАдресЮЛ', root.get('СвМНЖ', {})))

        cap_raw = _attrs(root.get('СвУстКап', {})).get('СумКап', '')
        capital = f"{cap_raw} руб." if cap_raw else ''

        okved, okved_name, _ = _parse_okveds(root.get('СвОКВЭД', {}))

        return [BusinessRecord(
            company_name=name,
            inn=inn,
            ogrn=ogrn,
            role=role,
            status=status,
            registration_date=reg_date,
            address=address,
            capital=capital,
            source='egrul.org',
            url=f"{self.EGRUL_ORG_BASE}/{query}.json",
            confidence='high',
            company_type=ctype,
            okved=okved,
            okved_name=okved_name,
        )]

    def _enrich_record_from_egrul_org(
        self, record: BusinessRecord, egrul_cache: dict
    ) -> None:
        """
        Fill gaps in a BusinessRecord that came from nalog.ru or rusprofile
        by fetching the full data from egrul.org using the record's company INN.
        Stores raw JSON in egrul_cache keyed by company INN for later role resolution.
        """
        company_inn = record.inn
        if not company_inn or len(company_inn) != 10:
            return

        raw = egrul_cache.get(company_inn)
        if raw is None:
            if record.capital and record.okved:
                return  # Already rich enough, skip fetch
            raw = self._fetch_egrul_org_raw(company_inn)
            if raw is not None:
                egrul_cache[company_inn] = raw

        if raw is None:
            return

        enriched = self._parse_egrul_org_to_records(raw, company_inn)
        if not enriched:
            return

        src = enriched[0]
        if not record.address and src.address:
            record.address = src.address
        if not record.capital and src.capital:
            record.capital = src.capital
        if not record.okved and src.okved:
            record.okved = src.okved
            record.okved_name = src.okved_name
        if not record.ogrn and src.ogrn:
            record.ogrn = src.ogrn

    def _resolve_roles_from_cache(
        self, records: List[BusinessRecord], candidate_name: str, egrul_cache: dict
    ) -> None:
        """
        For records still marked 'Связан', check the cached egrul.org JSON to see
        if the candidate appears in the directors or founders list, and update role.
        No HTTP calls — uses egrul_cache populated during enrichment.
        """
        if not candidate_name or not egrul_cache:
            return

        from app.services.company.egrul_service import _attrs, _as_list, _fio
        from app.utils.name_similarity import calculate_name_similarity

        for record in records:
            if record.role != 'Связан':
                continue
            raw = egrul_cache.get(record.inn)
            if not raw:
                continue

            root = raw.get('СвЮЛ') or raw.get('СвИП') or raw
            if not isinstance(root, dict):
                continue

            # Check directors
            for entry in _as_list(root.get('СведДолжнФЛ')):
                if not isinstance(entry, dict):
                    continue
                if _attrs(entry).get('ОгрДосСв') == '1':
                    continue
                name = _fio(entry.get('СвФЛ', {}))
                if name and calculate_name_similarity(candidate_name, name) >= 0.8:
                    role_raw = _attrs(entry.get('СвДолжн', {})).get(
                        'НаимДолжн', _attrs(entry.get('СвДолжн', {})).get('НаимВидДолжн', '')
                    )
                    record.role = role_raw.strip().capitalize() if role_raw else 'Директор'
                    logger.info(
                        "Role resolved via egrul.org cache: %s → %s (matched '%s')",
                        record.company_name, record.role, name,
                    )
                    break

            if record.role != 'Связан':
                continue

            # Check founders
            учредит = root.get('СвУчредит', {})
            if not isinstance(учредит, dict):
                continue
            for entry in _as_list(учредит.get('УчрФЛ')):
                if not isinstance(entry, dict):
                    continue
                if _attrs(entry).get('ОгрДосСв') == '1':
                    continue
                name = _fio(entry.get('СвФЛ', {}))
                if name and calculate_name_similarity(candidate_name, name) >= 0.8:
                    record.role = 'Учредитель'
                    logger.info(
                        "Role resolved via egrul.org cache: %s → Учредитель (matched '%s')",
                        record.company_name, name,
                    )
                    break

    # ===== nalog.ru EGRUL (Fallback) =====

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
        - g: executive/body text (UL only, e.g. "ГЕНЕРАЛЬНЫЙ ДИРЕКТОР: ...")
        - p: КПП (UL only)
        - e: end/liquidation date (if liquidated)
        - rn: registration region
        - t: detail token
        - cnt/tot/pg: pagination
        """
        try:
            record_type = row.get('k', '')  # "fl" or "ul"
            name = row.get('n', '')
            inn = row.get('i', '')
            ogrn = row.get('o', '')
            reg_date = row.get('r', '')
            end_date = row.get('e', '')

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
                address = row.get('a', '') or row.get('rn', '')
                director = row.get('g', '')
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

        logger.info(f"[EGRUL] Запрос: query='{inn}'")

        results = []

        # Primary: egrul.org — same FNS source as Контур.Фокус
        try:
            org_results = self._search_egrul_org(inn)
            if org_results:
                results = org_results
                logger.info(f"INN search: egrul.org returned {len(results)} records")
        except Exception as e:
            logger.warning(f"INN search egrul.org failed: {e}")

        # Fallback: nalog.ru EGRUL
        if not results:
            logger.info(f"INN search: falling back to nalog.ru for INN {inn[:4]}***")
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
        """
        Fetch the candidate's person profile page on rusprofile.ru by INN.

        URL pattern: /person/p-{INN}
        The INN suffix is the lookup key; the prefix before the dash is SEO-only
        and ignored by the server. No search endpoint needed — no bot detection.

        Returns company affiliations with actual roles from data-track-click.
        """
        if not inn or not inn.isdigit() or len(inn) != 12:
            return []

        url = f"{self.RUSPROFILE_BASE}/person/p-{inn}"
        try:
            resp = self.session.get(url, timeout=self.timeout)
            if resp.status_code in (403, 429):
                logger.warning("Rusprofile person page blocked (HTTP %s) for INN %s***", resp.status_code, inn[:4])
                return []
            if resp.status_code != 200:
                logger.debug("Rusprofile person page: HTTP %s for INN %s***", resp.status_code, inn[:4])
                return []

            soup = BeautifulSoup(resp.text, 'lxml')
            items = soup.select('.list-element')
            results = []
            for item in items:
                record = self._parse_rusprofile_profile_item(item)
                if record:
                    results.append(record)

            logger.info("Rusprofile /person/p-%s***: %d records", inn[:4], len(results))
            return results

        except Exception as exc:
            logger.warning("Rusprofile INN lookup failed: %s", exc)
            return []

    def _parse_rusprofile_profile_item(self, item) -> Optional[BusinessRecord]:
        """Parse a .list-element from a rusprofile.ru person profile page.

        Role is read from data-track-click on the title link:
          fl_dash_ceo_company / ceo_company  → Директор
          fl_dash_founder_company            → Учредитель
          fl_dash_ip / to_ip                 → ИП
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

            track = link.get('data-track-click', '')
            if 'fl_dash_ceo' in track or 'ceo_company' in track:
                role = 'Директор'
            elif 'fl_dash_founder' in track or 'founder_company' in track:
                role = 'Учредитель'
            elif 'fl_dash_ip' in track or 'to_ip' in track:
                role = 'ИП'
            else:
                role = 'Связан'

            status_el = item.select_one('.list-element__text.danger')
            if status_el and 'ликвидир' in status_el.get_text(strip=True).lower():
                status = 'Ликвидировано'
            else:
                status = 'Действующее'

            okved_name = ''
            for span in item.select('.list-element__text'):
                if 'danger' not in (span.get('class') or []):
                    okved_name = span.get_text(strip=True)
                    if okved_name:
                        break

            addr_el = item.select_one('.list-element__address')
            address = addr_el.get_text(strip=True) if addr_el else ''

            row = item.select_one('.list-element__row-info')
            inn = ogrn = reg_date = ''
            if row:
                t = row.get_text()
                m = re.search(r'ИНН[:\s]*(\d{10,12})', t)
                inn = m.group(1) if m else ''
                m = re.search(r'ОГРН(?:ИП)?[:\s]*(\d{13,15})', t)
                ogrn = m.group(1) if m else ''
                m = re.search(r'Дата регистрации[:\s]*([\d.]+)', t)
                reg_date = m.group(1) if m else ''

            return BusinessRecord(
                company_name=company_name,
                inn=inn,
                ogrn=ogrn,
                role=role,
                status=status,
                registration_date=reg_date,
                address=address,
                source='Rusprofile.ru',
                url=url,
                confidence='medium',
                company_type=self._detect_company_type(company_name),
                okved_name=okved_name,
            )
        except Exception as exc:
            logger.debug('Parse rusprofile profile item: %s', exc)
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

        result['has_ip'] = len(result['ip_records']) > 0
        result['ip_count'] = len(result['ip_records'])
        logger.info(
            f"IP check complete: has_ip={result['has_ip']}, count={result['ip_count']}"
        )
        return result

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


# ─────────────────────────────────────────
# Axis 2 connection graph helpers
# ─────────────────────────────────────────

def _normalize_name(name: str) -> str:
    """Lowercase, collapse spaces, replace ё→е for fuzzy matching."""
    return re.sub(r'\s+', ' ', name.lower().replace('ё', 'е')).strip()


def extract_egrul_coparties(
    raw: dict,
    company_name: str,
    company_inn: str,
    candidate_inn: str = '',
    candidate_name: str = '',
) -> list:
    """
    Extract co-directors and co-founders (people OTHER than the candidate)
    from a raw egrul.org FNS JSON for one company.

    Returns a list of edge dicts conforming to the Axis 2 connection-graph
    edge contract:
        {
            'kind':       'person',
            'name':       str,
            'inn':        str,   # '' if unknown
            'ogrn':       '',
            'relation':   'co_director' | 'co_owner',
            'label':      str,   # human-readable Russian
            'via':        str,   # bridge company string
            'source':     'ЕГРЮЛ',
            'confidence': 'strong' | 'weak',
        }

    Args:
        raw:            Parsed egrul.org JSON for one company (root-level dict).
        company_name:   Display name of the bridge company.
        company_inn:    INN of the bridge company.
        candidate_inn:  INN of the subject — used to exclude them from results.
        candidate_name: Full name of the subject — fallback exclusion by name.
    """
    try:
        from app.services.company.egrul_service import _attrs, _as_list, _fio
    except Exception:
        return []

    edges: list = []

    # Resolve the real root node (СвЮЛ / СвИП / raw itself)
    root = raw.get('СвЮЛ') or raw.get('СвИП') or raw
    if not isinstance(root, dict):
        return []

    via = f'{company_name} (ИНН {company_inn})' if company_inn else company_name
    norm_candidate = _normalize_name(candidate_name) if candidate_name else ''

    def _is_candidate(inn_fl: str, full_name: str) -> bool:
        """Return True if this person IS the candidate (should be excluded)."""
        if candidate_inn and inn_fl and inn_fl == candidate_inn:
            return True
        if norm_candidate and full_name and _normalize_name(full_name) == norm_candidate:
            return True
        return False

    # ── Officers (СведДолжнФЛ) ────────────────────────────────────────────
    try:
        for entry in _as_list(root.get('СведДолжнФЛ')):
            if not isinstance(entry, dict):
                continue
            # Skip restricted entries
            if _attrs(entry).get('ОгрДосСв') == '1':
                continue

            fl_node = entry.get('СвФЛ', {})
            name = _fio(fl_node)
            if not name:
                continue

            inn_fl = _attrs(fl_node).get('ИННФЛ', '')
            if _is_candidate(inn_fl, name):
                continue

            role_raw = _attrs(entry.get('СвДолжн', {})).get(
                'НаимДолжн',
                _attrs(entry.get('СвДолжн', {})).get('НаимВидДолжн', ''),
            )

            label = f'Соруководитель «{company_name}»'
            if role_raw:
                label = f'{role_raw.strip().capitalize()}, {company_name}'

            edges.append({
                'kind':       'person',
                'name':       name,
                'inn':        inn_fl,
                'ogrn':       '',
                'relation':   'co_director',
                'label':      label,
                'via':        via,
                'source':     'ЕГРЮЛ',
                'confidence': 'strong' if inn_fl else 'weak',
            })
    except Exception:
        pass  # Never raise — defensive

    # ── Physical founders (СвУчредит → УчрФЛ) ────────────────────────────
    try:
        учредит = root.get('СвУчредит')
        if isinstance(учредит, dict):
            for entry in _as_list(учредит.get('УчрФЛ')):
                if not isinstance(entry, dict):
                    continue
                if _attrs(entry).get('ОгрДосСв') == '1':
                    continue

                fl_node = entry.get('СвФЛ', {})
                name = _fio(fl_node)
                if not name:
                    continue

                inn_fl = _attrs(fl_node).get('ИННФЛ', '')
                if _is_candidate(inn_fl, name):
                    continue

                share_pct = _attrs(entry.get('ДолУстКап', {})).get('Процент', '')

                label = f'Соучредитель «{company_name}»'
                if share_pct:
                    label = f'Соучредитель «{company_name}» ({share_pct}%)'

                edges.append({
                    'kind':       'person',
                    'name':       name,
                    'inn':        inn_fl,
                    'ogrn':       '',
                    'relation':   'co_owner',
                    'label':      label,
                    'via':        via,
                    'source':     'ЕГРЮЛ',
                    'confidence': 'strong' if inn_fl else 'weak',
                })
    except Exception:
        pass  # Never raise — defensive

    return edges
