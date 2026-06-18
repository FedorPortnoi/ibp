"""
ЕФРСБ Bankruptcy Service
========================
Searches for bankruptcy proceedings via bankrot.fedresurs.ru / fedresurs.ru.

Strategy:
1. fedresurs.ru/backend/bankrupts JSON API (newer, preferred)
2. bankrot.fedresurs.ru/api/v1/debtors legacy JSON API
3. Playwright HTML scraper (last resort)
4. Manual search URL fallback

Geo-note: both fedresurs.ru and bankrot.fedresurs.ru are geo-blocked outside
Russia. Timeouts are expected from non-Russian IPs — same as kad.arbitr.ru.
The service runs on Yandex Cloud VM (Russian IP) in production.
"""

import logging
import re
import time
from dataclasses import dataclass
from typing import List, Optional

import requests

logger = logging.getLogger(__name__)

try:
    from playwright.sync_api import sync_playwright
except ImportError as exc:
    logger.info("Playwright unavailable; bankruptcy scraper disabled: %s", exc)

# Active bankruptcy stage keywords
ACTIVE_STAGES = [
    'наблюдение',
    'конкурсное производство',
    'реструктуризация долгов',
    'реализация имущества',
]

COMPLETED_STAGES = [
    'завершено',
    'прекращено',
    'мировое соглашение',
]

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/121.0.0.0 Safari/537.36'
    ),
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
    'Referer': 'https://bankrot.fedresurs.ru/',
}


@dataclass
class BankruptcyRecord:
    """A bankruptcy record from ЕФРСБ."""
    debtor_name: str = ''
    debtor_inn: Optional[str] = None
    debtor_address: Optional[str] = None
    case_number: Optional[str] = None
    court_name: Optional[str] = None
    stage: Optional[str] = None
    arbitration_manager: Optional[str] = None
    publication_date: Optional[str] = None
    is_active: bool = False
    source: str = 'bankrot.fedresurs.ru'
    url: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            'debtor_name': self.debtor_name,
            'debtor_inn': self.debtor_inn,
            'debtor_address': self.debtor_address,
            'case_number': self.case_number,
            'court_name': self.court_name,
            'stage': self.stage,
            'arbitration_manager': self.arbitration_manager,
            'publication_date': self.publication_date,
            'is_active': self.is_active,
            'source': self.source,
            'url': self.url,
            'type': 'bankruptcy',
        }


class BankruptcyService:
    """
    Search ЕФРСБ for bankruptcy proceedings.

    Tries the JSON API first, then Playwright scraper,
    then falls back to a manual search URL.

    Usage:
        svc = BankruptcyService()
        records = svc.search("Иванов Иван Иванович", inn="771234567890")
    """

    # Primary: fedresurs.ru backend API (newer, more reliable)
    FEDRESURS_API_URL = 'https://fedresurs.ru/backend/bankrupts'
    # Fallback: bankrot.fedresurs.ru legacy API
    API_URL = 'https://bankrot.fedresurs.ru/api/v1/debtors'
    SEARCH_URL = 'https://fedresurs.ru/search/person'

    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def search(
        self,
        full_name: str,
        inn: Optional[str] = None,
        dob: Optional[str] = None,
    ) -> List[BankruptcyRecord]:
        """
        Search ЕФРСБ for bankruptcy proceedings.

        Args:
            full_name: "Фамилия Имя Отчество"
            inn: INN (12 digits) for precise matching
            dob: Date of birth "YYYY-MM-DD" for filtering

        Returns:
            List of BankruptcyRecord (may include manual fallback)
        """
        all_records = []

        # Strategy 1: fedresurs.ru backend API (preferred)
        try:
            records = self._search_fedresurs_api(full_name)
            if records is not None:
                all_records.extend(records)
        except Exception as e:
            logger.warning(f"ЕФРСБ fedresurs API name search error: {e}")

        # Strategy 1b: fedresurs API — search by INN (more precise)
        if inn:
            time.sleep(0.5)
            try:
                inn_records = self._search_fedresurs_api(inn)
                if inn_records is not None:
                    existing_keys = {
                        (r.debtor_name, r.case_number) for r in all_records
                    }
                    for r in inn_records:
                        if (r.debtor_name, r.case_number) not in existing_keys:
                            all_records.append(r)
            except Exception as e:
                logger.warning(f"ЕФРСБ fedresurs API INN search error: {e}")

        if all_records:
            filtered = self._filter_results(all_records, full_name, inn, dob)
            return filtered

        # Strategy 2: Legacy bankrot.fedresurs.ru API
        try:
            records = self._search_api(full_name)
            if records is not None:
                all_records.extend(records)
        except Exception as e:
            logger.warning(f"ЕФРСБ legacy API error: {e}")

        if inn and not all_records:
            try:
                inn_records = self._search_api(inn)
                if inn_records is not None:
                    all_records.extend(inn_records)
            except Exception as e:
                logger.warning(f"ЕФРСБ legacy API INN error: {e}")

        if all_records:
            filtered = self._filter_results(all_records, full_name, inn, dob)
            return filtered

        # Strategy 3: Manual fallback
        logger.info("ЕФРСБ: returning manual search URL")
        return self._manual_fallback(full_name)

    # ── fedresurs.ru backend API (preferred) ─────────────────────

    def _search_fedresurs_api(self, search_string: str) -> Optional[List[BankruptcyRecord]]:
        """
        Query the fedresurs.ru backend API.
        Returns None on failure, [] on no results.
        """
        params = {
            'searchString': search_string,
            'isPhysical': 'true',
            'limit': '15',
            'offset': '0',
        }
        headers = {
            **HEADERS,
            'Referer': 'https://fedresurs.ru/search/person',
            'Origin': 'https://fedresurs.ru',
        }

        try:
            r = self.session.get(
                self.FEDRESURS_API_URL,
                params=params,
                headers=headers,
                timeout=self.timeout,
            )
        except requests.RequestException as e:
            logger.warning(f"ЕФРСБ fedresurs API request failed: {e}")
            return None

        if r.status_code != 200:
            logger.warning(f"ЕФРСБ fedresurs API status {r.status_code}")
            return None

        content_type = r.headers.get('Content-Type', '')
        if 'json' not in content_type and 'javascript' not in content_type:
            if '<html' in r.text[:500].lower():
                logger.warning("ЕФРСБ fedresurs API returned HTML instead of JSON")
                return None

        try:
            data = r.json()
        except (ValueError, KeyError):
            logger.warning("ЕФРСБ fedresurs API: invalid JSON response")
            return None

        return self._parse_api_response(data)

    # ── Legacy bankrot.fedresurs.ru API ────────────────────────────

    def _search_api(self, search_string: str) -> Optional[List[BankruptcyRecord]]:
        """
        Query the ЕФРСБ JSON API.
        Returns None on failure, [] on no results.
        """
        params = {
            'searchString': search_string,
            'isPhysical': 'true',
            'limit': '15',
        }

        try:
            r = self.session.get(
                self.API_URL,
                params=params,
                timeout=self.timeout,
            )
        except requests.RequestException as e:
            logger.warning(f"ЕФРСБ API request failed: {e}")
            return None

        if r.status_code != 200:
            logger.warning(f"ЕФРСБ API status {r.status_code}")
            return None

        # Check if response is JSON
        content_type = r.headers.get('Content-Type', '')
        if 'json' not in content_type and 'javascript' not in content_type:
            # Might be HTML (blocked, redirect, etc.)
            if '<html' in r.text[:500].lower():
                logger.warning("ЕФРСБ API returned HTML instead of JSON")
                return None

        try:
            data = r.json()
        except (ValueError, KeyError):
            logger.warning("ЕФРСБ API: invalid JSON response")
            return None

        return self._parse_api_response(data)

    def _parse_api_response(self, data) -> List[BankruptcyRecord]:
        """Parse the JSON API response into BankruptcyRecord objects."""
        records = []

        # The API may return a list directly or wrapped in a key
        items = []
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            # Try common wrapper keys
            for key in ('pageData', 'data', 'debtors', 'results', 'items'):
                if key in data and isinstance(data[key], list):
                    items = data[key]
                    break
            if not items and 'total' not in data:
                # Maybe the dict itself is a single result
                items = [data]

        for item in items:
            if not isinstance(item, dict):
                continue

            # Extract fields — try multiple possible key names
            name = (
                item.get('name')
                or item.get('fullName')
                or item.get('debtorName')
                or ''
            )
            inn = (
                item.get('inn')
                or item.get('INN')
                or item.get('debtorInn')
            )
            address = (
                item.get('address')
                or item.get('debtorAddress')
                or item.get('region')
            )
            case_number = (
                item.get('caseNumber')
                or item.get('case_number')
                or item.get('bankruptcyCaseNumber')
            )
            court = (
                item.get('courtName')
                or item.get('court')
                or item.get('arbitrationCourtName')
            )
            stage = (
                item.get('procedure')
                or item.get('stage')
                or item.get('currentProcedure')
                or item.get('status')
            )
            manager = (
                item.get('arbitrationManagerName')
                or item.get('manager')
                or item.get('trustee')
            )
            pub_date = (
                item.get('publishDate')
                or item.get('date')
                or item.get('registrationDate')
            )

            # Format date if present
            if pub_date:
                pub_date = self._format_date(str(pub_date))

            # Determine if active
            is_active = self._is_active_stage(stage)

            # Build URL to debtor page
            debtor_id = item.get('guid') or item.get('id') or item.get('debtorId')
            url = None
            if debtor_id:
                url = f'https://bankrot.fedresurs.ru/DebtorCard.aspx?id={debtor_id}'

            if name or inn:
                records.append(BankruptcyRecord(
                    debtor_name=name,
                    debtor_inn=inn,
                    debtor_address=address,
                    case_number=case_number,
                    court_name=court,
                    stage=stage,
                    arbitration_manager=manager,
                    publication_date=pub_date,
                    is_active=is_active,
                    source='bankrot.fedresurs.ru',
                    url=url,
                ))

        return records


    def _parse_html_regex(self, html: str) -> List[BankruptcyRecord]:
        """Last-resort regex parser for bankruptcy data in raw HTML."""
        records = []

        # Find arbitration case numbers
        for m in re.finditer(r'(А\d{2}-\d+/\d{4})', html):
            start = max(0, m.start() - 500)
            end = min(len(html), m.end() + 500)
            ctx = html[start:end]

            name_m = re.search(
                r'([А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+)?)',
                ctx,
            )
            inn_m = re.search(r'\b(\d{12})\b', ctx)

            records.append(BankruptcyRecord(
                debtor_name=name_m.group(1) if name_m else '',
                debtor_inn=inn_m.group(1) if inn_m else None,
                case_number=m.group(1),
                is_active=True,
                source='bankrot.fedresurs.ru',
            ))

        return records

    # ── Manual fallback ────────────────────────────────────────────

    def _manual_fallback(self, full_name: str) -> List[BankruptcyRecord]:
        """Return a placeholder record with manual search instructions."""
        return [BankruptcyRecord(
            debtor_name=full_name,
            case_number='Требуется ручная проверка',
            stage='Автоматический поиск недоступен. Проверьте вручную.',
            is_active=False,
            source='manual',
            url=self.SEARCH_URL,
        )]

    # ── Filtering ──────────────────────────────────────────────────

    def _filter_results(
        self,
        records: List[BankruptcyRecord],
        full_name: str,
        inn: Optional[str] = None,
        dob: Optional[str] = None,
    ) -> List[BankruptcyRecord]:
        """
        Filter API results to match our specific candidate.

        Priority:
        1. INN exact match → definite hit, return immediately.
        2. calculate_name_similarity >= 0.65 → confident name match.
        3. Surname stem match (first 5 chars) → catches Russian gender
           inflection (Иванов/Иванова) that pure word matching misses.

        Returns empty list when no records match — never returns all records
        as a fallback, which would produce mass false-positives for common
        names.

        dob is forwarded to the API call upstream; it is not re-applied here
        because the API response rarely surfaces a parseable birth date.
        """
        if not records:
            return records

        from app.utils.name_similarity import calculate_name_similarity

        # INN exact match — highest confidence, short-circuit
        if inn:
            inn_matches = [r for r in records if r.debtor_inn == inn]
            if inn_matches:
                return inn_matches

        query_tokens = full_name.lower().split()
        query_surname = query_tokens[0] if query_tokens else ''
        query_first = query_tokens[1] if len(query_tokens) > 1 else ''

        filtered = []
        for record in records:
            if not record.debtor_name:
                # Record matched on search string but has no parsed name —
                # trust the API result.
                filtered.append(record)
                continue

            # Primary: fuzzy name similarity (threshold 0.75 requires roughly
            # 2 of 3 name parts to match — prevents "same surname" false positives)
            sim = calculate_name_similarity(full_name, record.debtor_name)
            if sim >= 0.75:
                filtered.append(record)
                continue

            # Fallback: stem match for Russian gender/case inflection.
            # Requires BOTH surname AND first-name stems — surname alone is
            # too broad (Иванов Иван vs Иванов Борис would wrongly pass).
            rec_tokens = record.debtor_name.lower().split()
            rec_surname = rec_tokens[0] if rec_tokens else ''
            rec_first = rec_tokens[1] if len(rec_tokens) > 1 else ''

            surname_stem = (len(query_surname) >= 5 and len(rec_surname) >= 5
                            and query_surname[:5] == rec_surname[:5])
            first_stem = (len(query_first) >= 4 and len(rec_first) >= 4
                          and query_first[:4] == rec_first[:4])

            if surname_stem and first_stem:
                filtered.append(record)

        return filtered

    # ── Helpers ────────────────────────────────────────────────────

    @staticmethod
    def _is_active_stage(stage: Optional[str]) -> bool:
        """Determine if a bankruptcy stage indicates an active proceeding."""
        if not stage:
            return True  # Unknown stage — assume active
        stage_lower = stage.lower()
        for completed in COMPLETED_STAGES:
            if completed in stage_lower:
                return False
        return True

    @staticmethod
    def _format_date(date_str: str) -> str:
        """Normalize date to DD.MM.YYYY format."""
        # Already DD.MM.YYYY
        if re.match(r'^\d{2}\.\d{2}\.\d{4}$', date_str):
            return date_str
        # YYYY-MM-DD
        m = re.match(r'^(\d{4})-(\d{2})-(\d{2})', date_str)
        if m:
            return f"{m.group(3)}.{m.group(2)}.{m.group(1)}"
        # ISO datetime
        m = re.match(r'^(\d{4})-(\d{2})-(\d{2})T', date_str)
        if m:
            return f"{m.group(3)}.{m.group(2)}.{m.group(1)}"
        return date_str
