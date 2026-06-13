"""
kad.arbitr.ru — Картотека арбитражных дел (person search)
==========================================================
Official arbitration court cardfile. JSON POST API at /Kad/SearchInstances.

Geo: requires a Russian IP — returns HTTP 451 from abroad (DDoS Guard).
Works in production (Russian VM). From non-Russian dev machines every
request gets 451 and the search reports status='blocked' — callers must
surface this as "source unavailable", NOT as "no cases found".

Why arbitration matters for a candidate (физлицо) check:
- personal bankruptcy of individuals is heard by arbitration courts
  (court-side complement to the ЕФРСБ bankruptcy check)
- ИП commercial disputes
- subsidiary liability claims against directors/founders

Request/response schema mirrors the deployed company-side client
(app/services/company/company_court_service.py::_search_kad_arbitr),
which is production-proven from the Russian VM. Person adaptations:
12-digit INN gate, side matching by full-ФИО token subset (rejects
namesakes with a different patronymic) or surname+initials, side-INN
cross-check.
"""

import logging
import re
import time
from typing import Dict, List, Optional, Tuple

import requests

logger = logging.getLogger(__name__)

KAD_BASE = 'https://kad.arbitr.ru'
SEARCH_URL = f'{KAD_BASE}/Kad/SearchInstances'

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
    'Origin': KAD_BASE,
    'Referer': f'{KAD_BASE}/',
}

_SIDE_TYPES = {1: 'ответчик', 2: 'истец', 3: 'заявитель', 4: 'третье лицо'}

# parser-api.com participant array name -> role (used by the proxied path)
_PARSER_ROLE_BY_ARRAY = {
    'Plaintiffs': 'истец',
    'Respondents': 'ответчик',
    'Thirds': 'третье лицо',
    'Others': 'иное лицо',
}

# Statuses returned alongside results. 'blocked' means geo-block (HTTP 451) —
# the source was NOT consulted and absence of records proves nothing.
_TERMINAL_STATUSES = ('blocked', 'rate_limited', 'timeout', 'http_error', 'error')


def _is_person_inn(inn: str) -> bool:
    """Personal/ИП INN is exactly 12 digits (companies have 10)."""
    return bool(inn) and len(inn) == 12 and inn.isdigit()


def _name_tokens(text: str) -> List[str]:
    """Lowercase letter-only tokens, in order."""
    return re.findall(r'[а-яёa-z]+', (text or '').lower())


def _match_side_to_person(side_name: str, full_name: str) -> Optional[str]:
    """Match a kad side name against the candidate's ФИО.

    Returns 'full' (all candidate name parts present in the side name),
    'initials' (surname + matching initials, e.g. "Иванов И.И."), or None.

    Token-subset matching deliberately rejects namesakes that differ in
    patronymic ("Иванов Иван Петрович" for candidate "Иванов Иван Иванович"),
    which plain similarity scores would accept.
    """
    if not side_name or not full_name:
        return None

    # Strip parenthesized segments (addresses, regions, ИНН annotations)
    side = re.sub(r'\([^)]*\)', ' ', side_name.lower())

    cand_parts = [p for p in _name_tokens(full_name) if len(p) > 1]
    if len(cand_parts) < 2:
        return None  # single-word query is too weak to attribute a case

    side_tokens = set(_name_tokens(side))
    if all(p in side_tokens for p in cand_parts):
        return 'full'

    # Initials form: "иванов и.и." / "иванов и. и."
    surname = cand_parts[0]
    initials = [p[0] for p in cand_parts[1:]]
    if surname in side_tokens:
        m = re.search(re.escape(surname) + r'\s+((?:[а-яёa-z]\s*\.\s*)+)', side)
        if m:
            found = re.findall(r'[а-яёa-z]', m.group(1))
            if len(found) >= len(initials) and found[:len(initials)] == initials:
                return 'initials'

    return None


def _role_from_side(side: dict) -> str:
    st = side.get('SideType')
    if isinstance(st, dict):
        return _SIDE_TYPES.get(st.get('Id'), st.get('Name') or '')
    if isinstance(st, int):
        return _SIDE_TYPES.get(st, '')
    return ''


def _pick_person_side(
    sides: list, full_name: str, inn: str,
) -> Tuple[Optional[str], Optional[str]]:
    """Find the candidate among case sides.

    Returns (role, matched_by) where matched_by is 'inn' | 'full' | 'initials',
    or (None, None) if no side can be attributed to the candidate.

    A side whose name matches but whose INN is present and DIFFERENT from the
    candidate's is a namesake — it is skipped, never attributed.
    """
    best: Optional[Tuple[int, str, str]] = None  # (rank, role, matched_by)
    for side in sides or []:
        if not isinstance(side, dict):
            continue
        s_name = side.get('Name') or side.get('name') or ''
        s_inn = (side.get('Inn') or side.get('inn') or '').strip()

        if inn and s_inn == inn:
            return _role_from_side(side), 'inn'

        strength = _match_side_to_person(s_name, full_name)
        if not strength:
            continue
        if inn and s_inn and s_inn != inn:
            continue  # namesake with a different INN

        if strength == 'full' and (best is None or best[0] > 1):
            best = (1, _role_from_side(side), 'full')
        elif strength == 'initials' and best is None:
            best = (2, _role_from_side(side), 'initials')

    if best:
        return best[1], best[2]
    return None, None


def _convert_iso_date(raw: str) -> str:
    """'2024-03-15T00:00:00' → '15.03.2024'; empty string if unparseable."""
    if raw and len(raw) >= 10:
        parts = raw[:10].split('-')
        if len(parts) == 3 and all(parts):
            return f'{parts[2]}.{parts[1]}.{parts[0]}'
    return ''


def _item_to_record(
    item: dict, full_name: str, inn: str, query_kind: str,
) -> Optional[Dict]:
    """Convert one kad search item to a record dict, or None to drop it.

    For name queries the candidate MUST be found among the sides.
    For INN queries kad itself matched the INN — items are kept even if the
    response sides don't echo the INN back (matched_by stays 'inn').
    """
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
        return None  # name query — refuse to attribute an unmatched case

    subject = item.get('Subject') or item.get('subject') or ''
    case_type = 'банкротное' if 'банкрот' in subject.lower() else 'арбитражное'
    case_id = item.get('CaseId') or item.get('caseId') or ''

    return {
        'case_number': case_number,
        'court_name': item.get('CourtName') or item.get('courtName') or '',
        'case_type': case_type,
        'date': _convert_iso_date(item.get('DateTime') or item.get('dateTime') or ''),
        'role': role or '',
        'subject': subject,
        'url': f'{KAD_BASE}/Card/{case_id}' if case_id else '',
        'source': 'kad.arbitr.ru',
        'matched_by': matched_by,
    }


def _fetch_page(
    session: requests.Session, side: dict, page: int, timeout: int,
) -> Tuple[Optional[list], int, Optional[str]]:
    """POST one search page. Returns (items, total_count, terminal_status).

    terminal_status is one of _TERMINAL_STATUSES, or None on success.
    Payload mirrors the production-proven company client exactly.
    """
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
        logger.warning('kad.arbitr.ru: timeout on page %d', page)
        return None, 0, 'timeout'
    except requests.RequestException as exc:
        logger.warning('kad.arbitr.ru: request failed on page %d: %s', page, exc)
        return None, 0, 'error'

    if resp.status_code == 451:
        logger.info('kad.arbitr.ru: HTTP 451 — not a Russian IP, source blocked')
        return None, 0, 'blocked'
    if resp.status_code == 429:
        logger.warning('kad.arbitr.ru: rate-limited (429) on page %d', page)
        return None, 0, 'rate_limited'
    if resp.status_code != 200:
        logger.warning('kad.arbitr.ru: HTTP %d on page %d', resp.status_code, page)
        return None, 0, 'http_error'

    try:
        data = resp.json()
    except ValueError as exc:
        logger.warning('kad.arbitr.ru: bad JSON on page %d: %s', page, exc)
        return None, 0, 'error'

    result_block = data.get('Result') or data.get('result') or {}
    items = result_block.get('Items') or result_block.get('items') or []
    total = result_block.get('TotalCount') or result_block.get('totalCount') or 0
    return items, total, None


def _record_from_parser_case(
    case: dict, full_name: str, inn: str, query_kind: str,
) -> Optional[Dict]:
    """Map one parser-api.com arbitr case to a record dict, or None to drop it.

    The candidate's role comes from which participant array (Plaintiffs/
    Respondents/Thirds/Others) holds their INN or matching name. A participant
    whose INN is present and DIFFERENT from the candidate's is a namesake and
    is skipped. For name queries the candidate MUST be found among participants.
    """
    case_number = case.get('CaseNumber') or ''
    if not case_number:
        return None

    role: Optional[str] = None
    matched_by: Optional[str] = None
    for arr_key, role_label in _PARSER_ROLE_BY_ARRAY.items():
        for party in case.get(arr_key) or []:
            if not isinstance(party, dict):
                continue
            p_name = party.get('Name') or ''
            p_inn = (party.get('Inn') or '').strip()
            if inn and p_inn == inn:
                role, matched_by = role_label, 'inn'
                break
            strength = _match_side_to_person(p_name, full_name)
            if not strength:
                continue
            if inn and p_inn and p_inn != inn:
                continue  # namesake with a different INN
            if matched_by is None or (strength == 'full' and matched_by == 'initials'):
                role, matched_by = role_label, strength
        if matched_by == 'inn':
            break

    if query_kind == 'inn':
        matched_by = 'inn'
        role = role or ''
    elif matched_by is None:
        return None  # name query — candidate not among participants

    case_type = 'банкротное' if str(case.get('CaseType', '')).upper() == 'Б' else 'арбитражное'
    case_id = case.get('CaseId') or ''
    return {
        'case_number': case_number,
        'court_name': case.get('Court') or '',
        'case_type': case_type,
        'date': _convert_iso_date(case.get('StartDate') or ''),
        'role': role or '',
        'subject': '',
        'url': f'{KAD_BASE}/Card/{case_id}' if case_id else '',
        'source': 'kad.arbitr.ru',
        'matched_by': matched_by,
    }


def _search_via_parser_api(name: str, inn: str) -> Tuple[List[Dict], str]:
    """Primary path: kad.arbitr.ru via parser-api.com (works from any IP).

    INN-first (an INN hit is exact, so the name query is skipped), then name.
    """
    from app.services import parser_api

    records: List[Dict] = []
    seen: set = set()
    failure = ''

    def _ingest(raw_cases, query_kind):
        for case in raw_cases:
            if not isinstance(case, dict):
                continue
            rec = _record_from_parser_case(case, name, inn, query_kind)
            if rec and rec['case_number'] not in seen:
                seen.add(rec['case_number'])
                records.append(rec)

    if _is_person_inn(inn):
        raw, status = parser_api.arbitr_search(inn, inn_type='Any')
        if status in ('rate_limited', 'blocked', 'timeout', 'http_error', 'error', 'not_configured'):
            failure = status
        else:
            _ingest(raw, 'inn')
        if records:
            return records, 'ok'  # INN hit is exact — skip the name query

    if name:
        raw, status = parser_api.arbitr_search(name, inn_type='Any')
        if status in ('rate_limited', 'blocked', 'timeout', 'http_error', 'error', 'not_configured'):
            failure = failure or status
        else:
            _ingest(raw, 'name')

    if records:
        return records, 'ok'
    return [], (failure or 'empty')


def search_kad_arbitr_person(
    full_name: str,
    inn: str = '',
    timeout: int = 25,
    max_pages: int = 3,
) -> Tuple[List[Dict], str]:
    """Search kad.arbitr.ru for arbitration cases involving a person.

    Args:
        full_name: ФИО, e.g. "Иванов Иван Иванович".
        inn: personal/ИП INN (12 digits). Queried first when present —
             an INN hit is exact, so name queries are then skipped.
        timeout: per-request timeout in seconds.
        max_pages: pages of 25 per query.

    Returns:
        (records, status) where records are dicts with keys
        case_number, court_name, case_type, date, role, subject, url,
        source, matched_by ('inn'|'full'|'initials'), and status is
        'ok' | 'empty' | 'blocked' | 'rate_limited' | 'timeout' |
        'http_error' | 'error' | 'skipped'.

        'blocked' (HTTP 451 geo-block) means the source was not consulted:
        zero records is NOT evidence of a clean record.

    Provider order: when PARSER_API_KEY is configured, parser-api.com is used
    first (it proxies kad server-side and works from ANY IP, avoiding the
    451 geo-block). The direct kad.arbitr.ru client is the fallback (and the
    only path that works from a Russian IP without the key).
    """
    name = (full_name or '').strip()
    inn = (inn or '').strip()
    use_inn = _is_person_inn(inn)

    if not name and not use_inn:
        return [], 'skipped'

    # Primary: parser-api.com proxy (any IP) when configured.
    try:
        from app.services import parser_api
        if parser_api.is_available():
            records, status = _search_via_parser_api(name, inn)
            if status == 'ok' or records:
                logger.info("kad.arbitr.ru (parser-api): %d cases (status=%s)", len(records), status)
                return records, status
            # parser-api returned empty/failed — fall through to direct kad,
            # which may still work from a Russian IP.
            logger.info("kad.arbitr.ru: parser-api status=%s, trying direct", status)
    except Exception as exc:
        logger.warning("kad.arbitr.ru: parser-api path error: %s", exc)

    queries: List[Tuple[str, dict]] = []
    if use_inn:
        queries.append(('inn', {'Inn': inn, 'Name': '', 'Type': -1}))
    if name:
        queries.append(('name', {'Inn': '', 'Name': name, 'Type': -1}))

    records: List[Dict] = []
    seen_numbers: set = set()
    failure_status = ''  # first terminal failure seen, reported if 0 records

    session = requests.Session()
    session.headers.update(HEADERS)
    try:
        for query_kind, side in queries:
            added_before = len(records)
            for page in range(1, max_pages + 1):
                items, total, terminal = _fetch_page(session, side, page, timeout)

                if terminal == 'blocked':
                    # Every further request would 451 too — stop everything.
                    return records, ('ok' if records else 'blocked')
                if terminal:
                    failure_status = failure_status or terminal
                    break  # stop this query, try the next one

                for item in items:
                    if not isinstance(item, dict):
                        continue
                    record = _item_to_record(item, name, inn, query_kind)
                    if record and record['case_number'] not in seen_numbers:
                        seen_numbers.add(record['case_number'])
                        records.append(record)

                if not items or page * 25 >= total:
                    break
                time.sleep(0.3)  # politeness between pages

            if query_kind == 'inn' and len(records) > added_before:
                # INN hit is exact — name query would only add duplicates
                # plus namesake noise.
                logger.info(
                    'kad.arbitr.ru: INN query found %d cases, skipping name query',
                    len(records),
                )
                break
    except Exception as exc:
        logger.error('kad.arbitr.ru: unexpected error: %s', exc)
        failure_status = failure_status or 'error'
    finally:
        session.close()

    if records:
        status = 'ok'
    else:
        status = failure_status or 'empty'
    logger.info(
        "kad.arbitr.ru: %d cases for '%s' (status=%s)", len(records), name, status,
    )
    return records, status


# ── legal-form prefixes that identify a company ───────────────────────────
_LEGAL_FORM_PREFIXES = (
    'ООО', 'ОАО', 'ЗАО', 'ПАО', 'АО', 'НКО', 'АНО',
)


def _normalize_name(text: str) -> str:
    """Lowercase, ё→е, collapse whitespace — for candidate exclusion."""
    if not text:
        return ''
    return re.sub(r'\s+', ' ', text.lower().replace('ё', 'е')).strip()


def _party_kind(inn: str, name: str) -> str:
    """Return 'company' or 'person' for a case participant."""
    inn_clean = (inn or '').strip()
    if inn_clean and len(inn_clean) == 10 and inn_clean.isdigit():
        return 'company'
    name_upper = (name or '').strip().upper()
    for prefix in _LEGAL_FORM_PREFIXES:
        if name_upper.startswith(prefix):
            return 'company'
    return 'person'


def extract_court_coparties(
    cases: list,
    candidate_inn: str = '',
    candidate_name: str = '',
) -> list:
    """Extract co-party connection edges from arbitration cases.

    For each party in each case (across Plaintiffs, Respondents, Thirds, Others),
    emit one edge dict — EXCEPT the candidate themselves.  The candidate is
    identified by INN match (when both present) or by normalised name match.

    Args:
        cases: raw list returned by parser_api.arbitr_search() — each element
               is a dict with CaseNumber, Court, Plaintiffs, Respondents,
               Thirds, Others keys (arrays may be missing or None).
        candidate_inn:  INN of the candidate (may be empty).
        candidate_name: Full name of the candidate (may be empty).

    Returns:
        List of edge dicts conforming to the Axis-2 edge contract.
        Never raises; returns [] on bad/empty input.
    """
    if not cases or not isinstance(cases, list):
        return []

    cand_inn = (candidate_inn or '').strip()
    cand_name_norm = _normalize_name(candidate_name)

    edges: List[Dict] = []

    for case in cases:
        if not isinstance(case, dict):
            continue

        case_number = (case.get('CaseNumber') or '').strip()
        if not case_number:
            continue

        court = (case.get('Court') or '').strip()
        via = f'дело {case_number}, {court}' if court else f'дело {case_number}'

        for arr_key, role_ru in _PARSER_ROLE_BY_ARRAY.items():
            for party in case.get(arr_key) or []:
                if not isinstance(party, dict):
                    continue

                p_name = (party.get('Name') or '').strip()
                if not p_name:
                    continue

                p_inn = (party.get('Inn') or '').strip()

                # Exclude the candidate
                if cand_inn and p_inn and p_inn == cand_inn:
                    continue
                if cand_name_norm and _normalize_name(p_name) == cand_name_norm:
                    continue

                kind = _party_kind(p_inn, p_name)
                label = f'{role_ru.capitalize()} по делу {case_number}'
                confidence = 'strong' if p_inn else 'weak'

                edges.append({
                    'kind':       kind,
                    'name':       p_name,
                    'inn':        p_inn,
                    'ogrn':       '',
                    'relation':   'co_litigant',
                    'label':      label,
                    'via':        via,
                    'source':     'kad.arbitr.ru',
                    'confidence': confidence,
                })

    return edges
