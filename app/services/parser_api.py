"""
parser-api.com client — proxied kad.arbitr.ru + ФССП access
=============================================================
parser-api.com proxies the geo-/captcha-blocked official sources
SERVER-SIDE, so these endpoints work from ANY IP (including non-Russian
dev machines and the production VM) — unlike direct kad.arbitr.ru (HTTP
451 abroad) and direct ФССП (CAPTCHA).

Auth: a single key passed as the ``key`` query param. It is read ONLY from
the ``PARSER_API_KEY`` environment variable — never hardcode it (the key is
a secret; store it in the server .env like DADATA_API_KEY).

Quota: 200 requests/month per service (arbitr, fssp) on the current plan, so
callers should use these as the PRIMARY provider when configured but keep the
existing direct sources as a fallback. Each call here costs one request.

Endpoints used:
- GET /parser/arbitr_api/search?Inn={inn|name}&InnType={Any|Plaintiff|...}&page=N
    -> {"Success": bool, "Cases": [...], "PagesCount": int}
    each case: {CaseId, CaseNumber, CaseType, Court, StartDate,
                Plaintiffs/Respondents/Thirds/Others: [{Name, Address, Inn}], ...}
- GET /parser/fssp_api/search_fiz?lastName=&firstName=&patronymic=&dob=&regionID=
    -> {"done": 0|1, "result": [...], "error": str, "error_code": ...}
- GET /parser/fssp_api/search_ur_by_inn?inn=
- GET /stat/?key=  -> per-service quota (does NOT cost a search request)
"""

import logging
import os
from typing import List, Optional, Tuple

import requests

logger = logging.getLogger(__name__)

BASE_URL = 'https://parser-api.com'
ARBITR_SEARCH_URL = f'{BASE_URL}/parser/arbitr_api/search'
FSSP_SEARCH_FIZ_URL = f'{BASE_URL}/parser/fssp_api/search_fiz'
FSSP_SEARCH_UR_INN_URL = f'{BASE_URL}/parser/fssp_api/search_ur_by_inn'

API_KEY_ENV = 'PARSER_API_KEY'

# Status set, consistent with the rest of the pipeline's source-status model.
# 'not_configured' = no key (caller should fall back to direct sources);
# 'rate_limited'   = monthly/daily quota exhausted (429);
# 'blocked'        = auth failure (401/403, bad key).
_TIMEOUT = 30


def get_api_key() -> str:
    return os.environ.get(API_KEY_ENV, '').strip()


def is_available() -> bool:
    """True if a parser-api.com key is configured."""
    return bool(get_api_key())


def _request(url: str, params: dict, timeout: int = _TIMEOUT) -> Tuple[Optional[dict], str]:
    """GET a parser-api endpoint. Returns (json, status).

    status is None on success, or one of rate_limited/blocked/http_error/
    timeout/error on failure (json is None then).
    """
    key = get_api_key()
    if not key:
        return None, 'not_configured'
    params = {**params, 'key': key}
    try:
        resp = requests.get(url, params=params, timeout=timeout)
    except requests.Timeout:
        logger.warning('parser-api: timeout for %s', url)
        return None, 'timeout'
    except requests.RequestException as exc:
        logger.warning('parser-api: request failed: %s', exc)
        return None, 'error'

    if resp.status_code == 429:
        logger.warning('parser-api: quota exhausted (429)')
        return None, 'rate_limited'
    if resp.status_code in (401, 403):
        logger.warning('parser-api: auth failed (%d) — check PARSER_API_KEY', resp.status_code)
        return None, 'blocked'
    # 400 with a JSON body is a per-query error (e.g. not found / bad params),
    # which the caller maps to 'empty'; only treat 5xx / non-JSON as http_error.
    try:
        data = resp.json()
    except ValueError:
        if resp.status_code != 200:
            return None, 'http_error'
        logger.warning('parser-api: non-JSON 200 response from %s', url)
        return None, 'error'

    if resp.status_code >= 500:
        return None, 'http_error'
    return data, None


# ── arbitr (kad.arbitr.ru) ────────────────────────────────────────────────

def arbitr_search(
    query: str,
    inn_type: str = 'Any',
    max_pages: int = 2,
) -> Tuple[List[dict], str]:
    """Search kad.arbitr.ru (via parser-api) by participant INN or name.

    Args:
        query: a 10/12-digit INN or a participant name (ФИО / company name).
        inn_type: Any | Plaintiff | Respondent | Third | Other.
        max_pages: pages of results to fetch (each page is one request).

    Returns:
        (raw_cases, status). raw_cases are the API's case objects (keys:
        CaseId, CaseNumber, CaseType, Court, StartDate, Plaintiffs,
        Respondents, Thirds, Others, ...). status is
        'ok'|'empty'|'not_configured'|'rate_limited'|'blocked'|'timeout'|
        'http_error'|'error'.
    """
    query = (query or '').strip()
    if not query:
        return [], 'skipped'

    cases: List[dict] = []
    seen_ids = set()
    for page in range(1, max_pages + 1):
        data, err = _request(ARBITR_SEARCH_URL, {
            'Inn': query, 'InnType': inn_type, 'page': page,
        })
        if err:
            # Return whatever we already have; report the failure only if empty.
            return (cases, 'ok') if cases else (cases, err)

        if not data.get('Success', True) and not data.get('Cases'):
            break
        page_cases = data.get('Cases') or []
        for case in page_cases:
            cid = case.get('CaseId') or case.get('CaseNumber')
            if cid and cid not in seen_ids:
                seen_ids.add(cid)
                cases.append(case)

        pages_count = data.get('PagesCount') or 1
        if page >= pages_count or not page_cases:
            break

    return cases, ('ok' if cases else 'empty')


# ── ФССП (enforcement) ────────────────────────────────────────────────────

def fssp_search_fiz(
    last_name: str,
    first_name: str,
    patronymic: str = '',
    dob: str = '',
    region_id: Optional[str] = None,
) -> Tuple[List[dict], str]:
    """Search ФССП enforcement proceedings for an individual.

    Args:
        last_name/first_name: required.
        patronymic: optional.
        dob: 'YYYY-MM-DD' (required by the API for individual search).
        region_id: optional ФССП region id.

    Returns:
        (proceedings, status). proceedings are the API's result objects (keys
        include debtor_name, debtor_dob, process_title, process_total,
        subjects[], department_title, officer_name, stop_date, stop_reason,
        document_*). status as in arbitr_search.
    """
    if not last_name or not first_name:
        return [], 'skipped'

    params = {'lastName': last_name, 'firstName': first_name}
    if patronymic:
        params['patronymic'] = patronymic
    if dob:
        params['dob'] = dob
    if region_id:
        params['regionID'] = region_id

    data, err = _request(FSSP_SEARCH_FIZ_URL, params)
    if err:
        return [], err

    # API-level error (e.g. error_code=40001 "Missing dob in input params").
    # The HTTP layer returns 400 with a JSON body, which _request() passes
    # through as (data, None). An explicit error field means the search never
    # ran — treat as 'skipped' so the pipeline falls through to checko/direct.
    if data.get('error') or data.get('error_code'):
        logger.warning('parser-api fssp: API error %r (code=%s)', data.get('error'), data.get('error_code'))
        return [], 'skipped'

    if data.get('done') == 1:
        result = data.get('result') or []
        return result, ('ok' if result else 'empty')
    # done != 1 with no error: "not found" — the search ran, found nothing.
    result = data.get('result') or []
    if result:
        return result, 'ok'
    logger.info('parser-api fssp: done=%s error=%s', data.get('done'), data.get('error'))
    return [], 'empty'


def fssp_search_ur(inn: str) -> Tuple[List[dict], str]:
    """Search ФССП enforcement proceedings for a legal entity by INN.

    Uses the search_ur_by_inn endpoint (юридические лица / ИП by INN).

    Returns:
        (proceedings, status). status as in fssp_search_fiz.
    """
    inn = (inn or '').strip()
    if not inn:
        return [], 'skipped'

    data, err = _request(FSSP_SEARCH_UR_INN_URL, {'inn': inn})
    if err:
        return [], err

    if data.get('error') or data.get('error_code'):
        logger.warning('parser-api fssp ur: API error %r (code=%s) inn=%s', data.get('error'), data.get('error_code'), inn)
        return [], 'skipped'

    if data.get('done') == 1:
        result = data.get('result') or []
        return result, ('ok' if result else 'empty')
    result = data.get('result') or []
    if result:
        return result, 'ok'
    logger.info('parser-api fssp ur: done=%s error=%s inn=%s', data.get('done'), data.get('error'), inn)
    return [], 'empty'


