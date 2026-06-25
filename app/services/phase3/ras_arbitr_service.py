"""
ras.arbitr.ru — Апелляционная картотека арбитражных дел (person search)
=======================================================================
Appellate arbitration court cardfile. JSON POST API at /Appeal/SearchInstances,
parallel in structure to kad.arbitr.ru's /Kad/SearchInstances.

Geo: requires a Russian IP — returns HTTP 451 from non-Russian IPs (same
DDoS Guard policy as kad.arbitr.ru). Works reliably from the production VM.

Covers cases heard by the 21 appellate arbitration courts (1 ААС–21 ААС):
any person who lost at the first instance (kad.arbitr.ru) and had their
case appealed appears here even if they don't appear in kad results.

No parser-api.com proxy available for this source — direct call only.
"""

import logging
import time
from typing import Dict, List, Optional, Tuple

import requests

from app.services.phase3.kad_arbitr_service import (
    _convert_iso_date,
    _pick_person_side,
)

logger = logging.getLogger(__name__)

RAS_BASE = 'https://ras.arbitr.ru'
SEARCH_URL = f'{RAS_BASE}/Appeal/SearchInstances'

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/122.0.0.0 Safari/537.36'
    ),
    'Content-Type': 'application/json',
    'Accept': 'application/json, text/javascript, */*; q=0.01',
    'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
    'X-Requested-With': 'XMLHttpRequest',
    'x-date-format': 'iso',
    'Origin': RAS_BASE,
    'Referer': f'{RAS_BASE}/',
}


def _item_to_record(item: dict, full_name: str, inn: str, query_kind: str) -> Optional[Dict]:
    """Convert one ras.arbitr.ru search item to a record dict, or None to drop it."""
    case_number = item.get('CaseNumber') or item.get('caseNumber') or ''
    if not case_number:
        return None

    role, matched_by = _pick_person_side(
        item.get('Sides') or item.get('sides') or [], full_name, inn,
    )
    if query_kind == 'inn':
        matched_by = 'inn'
        role = role or ''
    elif matched_by is None:
        return None  # name query — candidate not among sides

    subject = item.get('Subject') or item.get('subject') or ''
    case_id = item.get('CaseId') or item.get('caseId') or ''

    return {
        'case_number': case_number,
        'court_name': item.get('CourtName') or item.get('courtName') or '',
        'case_type': 'арбитражное (апелляция)',
        'date': _convert_iso_date(item.get('DateTime') or item.get('dateTime') or ''),
        'role': role or '',
        'subject': subject,
        'url': f'{RAS_BASE}/Card/{case_id}' if case_id else '',
        'source': 'ras.arbitr.ru',
        'matched_by': matched_by,
    }


def _fetch_page(
    session: requests.Session, side: dict, page: int, timeout: int,
) -> Tuple[Optional[list], int, Optional[str]]:
    """POST one search page. Returns (items, total_count, terminal_status)."""
    payload = {
        'Sides': [side],
        'Page': page,
        'Count': 25,
        'DateFrom': None,
        'DateTo': None,
        'CaseType': 0,
        'CourtType': -1,
        'Courts': [],
        'Judges': [],
        'CaseNumbers': [],
        'OrderBy': 'Data',
        'OrderDirection': 'Desc',
    }
    try:
        resp = session.post(SEARCH_URL, json=payload, timeout=timeout)
    except requests.Timeout:
        logger.warning('ras.arbitr.ru: timeout on page %d', page)
        return None, 0, 'timeout'
    except requests.RequestException as exc:
        logger.warning('ras.arbitr.ru: request failed on page %d: %s', page, exc)
        return None, 0, 'error'

    if resp.status_code == 451:
        logger.info('ras.arbitr.ru: HTTP 451 — not a Russian IP, source blocked')
        return None, 0, 'blocked'
    if resp.status_code == 429:
        logger.warning('ras.arbitr.ru: rate-limited (429) on page %d', page)
        return None, 0, 'rate_limited'
    if resp.status_code != 200:
        logger.warning('ras.arbitr.ru: HTTP %d on page %d', resp.status_code, page)
        return None, 0, 'http_error'

    try:
        data = resp.json()
    except ValueError as exc:
        logger.warning('ras.arbitr.ru: bad JSON on page %d: %s', page, exc)
        return None, 0, 'error'

    result_block = data.get('Result') or data.get('result') or {}
    items = result_block.get('Items') or result_block.get('items') or []
    total = result_block.get('TotalCount') or result_block.get('totalCount') or 0
    return items, total, None


def search_ras_arbitr_person(
    full_name: str,
    inn: str = '',
    timeout: int = 12,
    max_pages: int = 3,
) -> Tuple[List[Dict], str]:
    """Search ras.arbitr.ru for appellate arbitration cases involving a person.

    Args:
        full_name: ФИО, e.g. "Иванов Иван Иванович".
        inn: personal/ИП INN (12 digits). Queried first when present.
        timeout: per-request timeout in seconds.
        max_pages: pages of 25 per query.

    Returns:
        (records, status) where status is one of:
        'ok' | 'empty' | 'blocked' | 'rate_limited' | 'timeout' |
        'http_error' | 'error' | 'skipped'.

        'blocked' (HTTP 451 geo-block) means the source was not consulted:
        zero records is NOT evidence of a clean record.
    """
    name = (full_name or '').strip()
    inn = (inn or '').strip()
    use_inn = bool(inn) and len(inn) == 12 and inn.isdigit()

    if not name and not use_inn:
        return [], 'skipped'

    queries: List[Tuple[str, dict]] = []
    if use_inn:
        queries.append(('inn', {'Inn': inn, 'Name': '', 'Type': -1}))
    if name:
        queries.append(('name', {'Inn': '', 'Name': name, 'Type': -1}))

    records: List[Dict] = []
    seen_numbers: set = set()
    failure_status = ''

    session = requests.Session()
    session.headers.update(HEADERS)
    try:
        for query_kind, side in queries:
            added_before = len(records)
            for page in range(1, max_pages + 1):
                items, total, terminal = _fetch_page(session, side, page, timeout)

                if terminal == 'blocked':
                    return records, ('ok' if records else 'blocked')
                if terminal:
                    failure_status = failure_status or terminal
                    break

                for item in items:
                    if not isinstance(item, dict):
                        continue
                    record = _item_to_record(item, name, inn, query_kind)
                    if record and record['case_number'] not in seen_numbers:
                        seen_numbers.add(record['case_number'])
                        records.append(record)

                if not items or page * 25 >= total:
                    break
                time.sleep(0.3)

            if query_kind == 'inn' and len(records) > added_before:
                logger.info(
                    'ras.arbitr.ru: INN query found %d cases, skipping name query',
                    len(records),
                )
                break
    except Exception as exc:
        logger.error('ras.arbitr.ru: unexpected error: %s', exc)
        failure_status = failure_status or 'error'
    finally:
        session.close()

    status = 'ok' if records else (failure_status or 'empty')
    logger.info("ras.arbitr.ru: %d cases for '%s' (status=%s)", len(records), name, status)
    return records, status
