"""
Free Government API Services
=============================
Direct integrations with official Russian government open data sources.
No paid API key required — all endpoints are publicly accessible.

Sources:
  - bankrot.fedresurs.ru  — ЕФРСБ bankruptcy registry
  - zakupki.gov.ru        — ЕИС government contracts
  - service.nalog.ru      — FNS blocked bank accounts
  - proverki.gov.ru       — Генпрокуратура government inspections
  - api.fssp.gov.ru       — Official FSSP enforcement proceedings
"""

import logging
import os
import re

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_TIMEOUT = 20
_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/122.0.0.0 Safari/537.36'
    ),
    'Accept': 'application/json, text/html, */*',
    'Accept-Language': 'ru-RU,ru;q=0.9',
}


# ── Bankruptcy — bankrot.fedresurs.ru ─────────────────────────────────────────

def fetch_bankruptcy(inn: str) -> dict:
    """
    Check ЕФРСБ (Федресурс) for bankruptcy proceedings.
    Uses the public JSON search API — no auth required.
    Returns dict matching the format used by datanewton_service.lookup_bankruptcy().
    """
    empty = {
        'found': False, 'unavailable': False,
        'active': False, 'stage': '',
        'source': 'bankrot.fedresurs.ru',
    }
    if not inn:
        return empty

    try:
        resp = requests.get(
            'https://bankrot.fedresurs.ru/ms/api/companies',
            params={'searchString': inn, 'size': 10},
            headers=_HEADERS,
            timeout=_TIMEOUT,
        )
        if resp.status_code == 404:
            return empty
        if resp.status_code != 200:
            logger.warning("fedresurs: HTTP %d for INN %s", resp.status_code, inn)
            return {**empty, 'unavailable': True}

        data = resp.json()
        items = (
            data.get('content') or data.get('items') or
            data.get('data') or (data if isinstance(data, list) else [])
        )

        for item in items:
            item_inn = str(item.get('inn') or item.get('INN') or '')
            if item_inn and item_inn != inn:
                continue
            stage = (
                item.get('procedureName') or item.get('procedure') or
                item.get('stage') or item.get('status') or ''
            )
            active = bool(
                item.get('active') or item.get('isActive') or
                item.get('has_active_procedure') or
                (stage and 'завершен' not in stage.lower() and 'прекращ' not in stage.lower())
            )
            logger.info("fedresurs: INN %s → active=%s stage=%s", inn, active, stage)
            return {
                'found': True, 'unavailable': False,
                'active': active, 'stage': stage,
                'source': 'bankrot.fedresurs.ru',
            }

        return empty

    except requests.Timeout:
        logger.warning("fedresurs: timeout for INN %s", inn)
        return {**empty, 'unavailable': True}
    except Exception as exc:
        logger.warning("fedresurs: error for INN %s: %s", inn, exc)
        return {**empty, 'unavailable': True}


# ── Government Contracts — zakupki.gov.ru ─────────────────────────────────────

def fetch_gov_contracts(inn: str) -> dict:
    """
    Search ЕИС (zakupki.gov.ru) for government contracts by INN.
    Uses the public search API — no auth required.
    Returns dict matching the format used by datanewton_service.lookup_gov_contracts().
    """
    empty = {
        'found': False, 'unavailable': False,
        'contracts': [], 'total_count': 0,
        'source': 'zakupki.gov.ru',
    }
    if not inn:
        return empty

    try:
        resp = requests.get(
            'https://api.zakupki.gov.ru/epz/contract/search/results/',
            params={
                'searchString': inn,
                'morphology': 'on',
                'sortBy': 'UPDATE_DATE',
                'pageNumber': '1',
                'sortDirection': 'false',
                'recordsPerPage': '_10',
                'showLotsInfoHidden': 'false',
                'fz44': 'on',
                'fz223': 'on',
            },
            headers={**_HEADERS, 'Accept': 'application/json'},
            timeout=_TIMEOUT,
        )
        if resp.status_code != 200:
            logger.warning("zakupki.gov.ru: HTTP %d for INN %s", resp.status_code, inn)
            return {**empty, 'unavailable': True}

        data = resp.json()
        items = data.get('data') or data.get('contracts') or data.get('items') or []
        total = data.get('totalCount') or data.get('total') or len(items)

        if not items:
            return empty

        contracts = []
        for item in items[:10]:
            contracts.append({
                'number':    item.get('number') or item.get('contractNumber') or '',
                'subject':   item.get('name') or item.get('subject') or '',
                'amount':    item.get('price') or item.get('amount') or 0,
                'customer':  item.get('customer', {}).get('name') if isinstance(item.get('customer'), dict) else (item.get('customerName') or ''),
                'sign_date': item.get('signDate') or item.get('conclusionDate') or '',
                'status':    item.get('stage') or item.get('status') or '',
            })

        logger.info("zakupki.gov.ru: INN %s → %d contracts", inn, total)
        return {
            'found': True, 'unavailable': False,
            'contracts': contracts, 'total_count': total,
            'source': 'zakupki.gov.ru',
        }

    except requests.Timeout:
        logger.warning("zakupki.gov.ru: timeout for INN %s", inn)
        return {**empty, 'unavailable': True}
    except Exception as exc:
        logger.warning("zakupki.gov.ru: error for INN %s: %s", inn, exc)
        return {**empty, 'unavailable': True}


# ── Blocked Accounts — service.nalog.ru ───────────────────────────────────────

def fetch_blocked_accounts(inn: str) -> dict:
    """
    Check FNS blocked bank accounts via service.nalog.ru public service.
    Returns dict matching the format used by datanewton_service.lookup_blocked_accounts().
    """
    empty = {
        'found': False, 'unavailable': False,
        'blocks': [], 'total_count': 0,
        'source': 'service.nalog.ru (ФНС)',
    }
    if not inn:
        return empty

    try:
        session = requests.Session()
        session.headers.update(_HEADERS)

        # Step 1: POST to search
        resp = session.post(
            'https://service.nalog.ru/bi2.do',
            data={'inn': inn, 'bik': '', 'date': '', 'nameFl': ''},
            timeout=_TIMEOUT,
        )
        if resp.status_code != 200:
            logger.warning("nalog.ru blocked: HTTP %d for INN %s", resp.status_code, inn)
            return {**empty, 'unavailable': True}

        # Try JSON first
        try:
            data = resp.json()
            rows = data.get('rows') or data.get('data') or data.get('result') or []
            if isinstance(rows, list) and rows:
                blocks = []
                for row in rows:
                    blocks.append({
                        'bank_name':  row.get('nameBankList') or row.get('bank') or '',
                        'bik':        row.get('bikBankList') or row.get('bik') or '',
                        'decision_number': row.get('numDecision') or '',
                        'decision_date':   row.get('dateDecision') or '',
                        'amount':          row.get('sum') or row.get('amount') or 0,
                    })
                logger.info("nalog.ru blocked: INN %s → %d blocks", inn, len(blocks))
                return {
                    'found': True, 'unavailable': False,
                    'blocks': blocks, 'total_count': len(blocks),
                    'source': 'service.nalog.ru (ФНС)',
                }
        except ValueError:
            pass

        # Parse HTML fallback
        soup = BeautifulSoup(resp.text, 'lxml')
        table = soup.select_one('table#tbl, table.table, table')
        if not table:
            return empty

        blocks = []
        rows = table.select('tr')[1:]  # skip header
        for row in rows:
            cells = [td.get_text(strip=True) for td in row.select('td')]
            if len(cells) >= 2 and any(cells):
                blocks.append({
                    'bank_name':       cells[0] if len(cells) > 0 else '',
                    'bik':             cells[1] if len(cells) > 1 else '',
                    'decision_number': cells[2] if len(cells) > 2 else '',
                    'decision_date':   cells[3] if len(cells) > 3 else '',
                    'amount':          0,
                })

        if not blocks:
            return empty

        logger.info("nalog.ru blocked: INN %s → %d blocks (HTML)", inn, len(blocks))
        return {
            'found': True, 'unavailable': False,
            'blocks': blocks, 'total_count': len(blocks),
            'source': 'service.nalog.ru (ФНС)',
        }

    except requests.Timeout:
        logger.warning("nalog.ru blocked: timeout for INN %s", inn)
        return {**empty, 'unavailable': True}
    except Exception as exc:
        logger.warning("nalog.ru blocked: error for INN %s: %s", inn, exc)
        return {**empty, 'unavailable': True}


# ── Government Inspections — proverki.gov.ru ──────────────────────────────────

def fetch_inspections(inn: str) -> dict:
    """
    Fetch government inspections from proverki.gov.ru (Генпрокуратура).
    Returns dict matching the format used by datanewton_service.lookup_inspections().
    """
    empty = {
        'found': False, 'unavailable': False,
        'inspections': [], 'total': 0,
        'source': 'proverki.gov.ru (Генпрокуратура)',
    }
    if not inn:
        return empty

    try:
        resp = requests.get(
            'https://proverki.gov.ru/portal/public-open-endpoint-list/getFromPlan',
            params={'inn': inn, 'page': 1, 'size': 20},
            headers=_HEADERS,
            timeout=_TIMEOUT,
        )
        if resp.status_code != 200:
            logger.warning("proverki.gov.ru: HTTP %d for INN %s", resp.status_code, inn)
            return {**empty, 'unavailable': True}

        data = resp.json()
        items = (
            data.get('content') or data.get('data') or
            data.get('items') or (data if isinstance(data, list) else [])
        )
        total = data.get('totalElements') or data.get('total') or len(items)

        if not items:
            return empty

        inspections = []
        for item in items[:20]:
            inspections.append({
                'number':       item.get('number') or item.get('id') or '',
                'authority':    item.get('inspectionAuthorityName') or item.get('authority') or '',
                'start_date':   item.get('dateBegin') or item.get('startDate') or item.get('date') or '',
                'end_date':     item.get('dateEnd') or item.get('endDate') or '',
                'type':         item.get('kindName') or item.get('type') or '',
                'subject':      item.get('subjectName') or item.get('subject') or '',
                'result':       item.get('result') or '',
            })

        logger.info("proverki.gov.ru: INN %s → %d inspections", inn, total)
        return {
            'found': True, 'unavailable': False,
            'inspections': inspections, 'total': total,
            'source': 'proverki.gov.ru (Генпрокуратура)',
        }

    except requests.Timeout:
        logger.warning("proverki.gov.ru: timeout for INN %s", inn)
        return {**empty, 'unavailable': True}
    except Exception as exc:
        logger.warning("proverki.gov.ru: error for INN %s: %s", inn, exc)
        return {**empty, 'unavailable': True}


# ── FSSP — api.fssp.gov.ru ────────────────────────────────────────────────────

def fetch_fssp_company(inn: str) -> dict:
    """
    Fetch FSSP enforcement proceedings via the official api.fssp.gov.ru API.
    Requires FSSP_API_TOKEN env var (free registration at fssp.gov.ru/api/).
    Falls back gracefully if token not configured.
    """
    empty = {
        'found': False, 'unavailable': False,
        'proceedings': [], 'active_count': 0, 'total_count': 0,
        'source': 'fssp.gov.ru',
    }
    if not inn:
        return empty

    token = (os.environ.get('FSSP_API_TOKEN') or '').strip()
    if not token:
        return {**empty, 'unavailable': True}

    try:
        resp = requests.get(
            'https://api.fssp.gov.ru/api/v1.0/search/ip',
            params={'token': token, 'inn': inn},
            headers=_HEADERS,
            timeout=_TIMEOUT,
        )
        if resp.status_code == 401:
            logger.warning("fssp.gov.ru: invalid token")
            return {**empty, 'unavailable': True}
        if resp.status_code != 200:
            logger.warning("fssp.gov.ru: HTTP %d for INN %s", resp.status_code, inn)
            return {**empty, 'unavailable': True}

        data = resp.json()
        items = (
            data.get('response', {}).get('Item') or
            data.get('items') or data.get('data') or
            (data if isinstance(data, list) else [])
        )
        if not items:
            return empty

        proceedings = []
        active_count = 0
        for item in items:
            is_active = not item.get('ip_end') and not item.get('end_date')
            if is_active:
                active_count += 1
            proceedings.append({
                'number':     item.get('ip_id') or item.get('number') or '',
                'subject':    item.get('subject') or item.get('exe_production') or '',
                'amount':     item.get('sum') or item.get('amount') or 0,
                'department': item.get('department') or item.get('bailiff_name') or '',
                'start_date': item.get('ip_date') or item.get('start_date') or '',
                'end_date':   item.get('ip_end') or item.get('end_date') or '',
                'end_reason': item.get('end_reason') or '',
                'is_active':  is_active,
            })

        logger.info("fssp.gov.ru: INN %s → %d proceedings (%d active)", inn, len(proceedings), active_count)
        return {
            'found': True, 'unavailable': False,
            'proceedings': proceedings,
            'active_count': active_count,
            'total_count': len(proceedings),
            'source': 'fssp.gov.ru',
        }

    except requests.Timeout:
        logger.warning("fssp.gov.ru: timeout for INN %s", inn)
        return {**empty, 'unavailable': True}
    except Exception as exc:
        logger.warning("fssp.gov.ru: error for INN %s: %s", inn, exc)
        return {**empty, 'unavailable': True}
