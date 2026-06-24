"""
DataNewton API Client — Russian Legal Entity Data
==================================================
datanewton.ru provides 60+ endpoints for Russian legal entities:
EGRUL/EGRIP, Rosstat financials (multi-year), FNS tax data,
enforcement (FSSP), courts, government contracts, and more.

Free tier: 200 requests/month after registration.
Requires DATANEWTON_API_KEY in .env. Use test key mi76aFMdgvml for dev.

Endpoint base: https://api.datanewton.ru
Authentication: ?key= query param (demo key: mi76aFMdgvml)
"""

import logging
import os
from typing import Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

_BASE = 'https://api.datanewton.ru'
_TIMEOUT = 20

_HEADERS = {
    'Accept': 'application/json',
    'User-Agent': 'Stirlitz/1.0 (+https://shtirlitz.ru)',
}


def _get_key() -> str:
    return (os.environ.get('DATANEWTON_API_KEY') or '').strip()


def is_available() -> bool:
    return bool(_get_key())


def _get(endpoint: str, params: dict, timeout: int = _TIMEOUT) -> tuple:
    """GET a DataNewton endpoint. Returns (data, status).

    status: None on success, 'not_configured'/'rate_limited'/'blocked'/'error'/'timeout' on failure.
    """
    key = _get_key()
    if not key:
        return None, 'not_configured'

    try:
        resp = requests.get(
            f'{_BASE}/{endpoint.lstrip("/")}',
            params={**params, 'key': key},
            headers=_HEADERS,
            timeout=timeout,
        )
    except requests.Timeout:
        logger.warning('DataNewton: timeout for %s', endpoint)
        return None, 'timeout'
    except requests.RequestException as exc:
        logger.warning('DataNewton: request failed for %s: %s', endpoint, exc)
        return None, 'error'

    if resp.status_code == 429:
        logger.warning('DataNewton: quota exhausted (429)')
        return None, 'rate_limited'
    if resp.status_code in (401, 403):
        logger.warning('DataNewton: auth failed (%d)', resp.status_code)
        return None, 'blocked'
    if resp.status_code == 404:
        return None, 'not_found'
    try:
        data = resp.json()
    except ValueError:
        if resp.status_code != 200:
            return None, 'http_error'
        return None, 'error'
    if resp.status_code >= 500:
        return None, 'http_error'
    return data, None


# ── FSSP enforcement for legal entities ─────────────────────────────────────

def lookup_fssp(inn: str) -> Dict:
    """Get FSSP enforcement proceedings for a legal entity by INN.

    Returns dict:
      found        — True if active or past proceedings found
      unavailable  — True if API unreachable / key missing
      active_count — number of active proceedings
      total_count  — total including closed
      proceedings  — list of proceeding dicts
      source       — 'datanewton'
    """
    empty = {
        'found': False, 'unavailable': False,
        'active_count': 0, 'total_count': 0,
        'proceedings': [], 'source': 'datanewton',
    }

    if not inn:
        return empty

    data, err = _get('v1/enforcement/', {'inn': inn})
    if err == 'not_configured':
        return {**empty, 'unavailable': True}
    if err:
        logger.info('DataNewton FSSP: %s for INN %s', err, inn)
        return {**empty, 'unavailable': True}

    items = data if isinstance(data, list) else (data.get('results') or data.get('data') or [])
    if not items:
        return empty

    proceedings = []
    active_count = 0
    for item in items:
        is_active = not item.get('end_date') and not item.get('stop_date')
        if is_active:
            active_count += 1
        proceedings.append({
            'number': item.get('number') or item.get('id') or '',
            'subject': item.get('subject') or item.get('description') or '',
            'amount': item.get('amount') or item.get('sum') or 0,
            'department': item.get('department') or item.get('bailiff_dept') or '',
            'start_date': item.get('start_date') or item.get('date') or '',
            'end_date': item.get('end_date') or item.get('stop_date') or '',
            'end_reason': item.get('end_reason') or item.get('stop_reason') or '',
            'is_active': is_active,
        })

    logger.info('DataNewton FSSP: INN %s → %d proceedings (%d active)', inn, len(proceedings), active_count)
    return {
        'found': True,
        'unavailable': False,
        'active_count': active_count,
        'total_count': len(proceedings),
        'proceedings': proceedings,
        'source': 'datanewton',
    }


# ── FNS tax data ─────────────────────────────────────────────────────────────

def lookup_fns(inn: str) -> Dict:
    """Get FNS tax data (debts, regime, status) for a legal entity.

    Returns dict:
      found           — True if data returned
      unavailable     — True if API unreachable / key missing
      tax_debt        — tax debt amount (RUB) or None
      tax_regime      — tax system string (ОСН/УСН/etc.)
      employee_count  — headcount from Rosstat
      source          — 'datanewton'
    """
    empty = {
        'found': False, 'unavailable': False,
        'tax_debt': None, 'tax_regime': '', 'employee_count': '',
        'source': 'datanewton',
    }

    if not inn:
        return empty

    data, err = _get('v1/tax/', {'inn': inn})
    if err == 'not_configured':
        return {**empty, 'unavailable': True}
    if err:
        logger.info('DataNewton FNS: %s for INN %s', err, inn)
        return {**empty, 'unavailable': True}

    if not data:
        return empty

    payload = data if isinstance(data, dict) else (data[0] if data else {})
    result = {
        'found': True,
        'unavailable': False,
        'tax_debt': payload.get('tax_debt') or payload.get('debt') or None,
        'tax_regime': payload.get('tax_regime') or payload.get('tax_system') or '',
        'employee_count': str(payload.get('employee_count') or payload.get('employees') or ''),
        'source': 'datanewton',
    }
    logger.info('DataNewton FNS: INN %s → debt=%s regime=%s', inn, result['tax_debt'], result['tax_regime'])
    return result


# ── Multi-year financial statements ──────────────────────────────────────────

def lookup_financials(inn: str, years: int = 3) -> List[Dict]:
    """Get multi-year financial statements (BFO — бухгалтерская отчётность).

    Returns list of year dicts (most recent first), each matching the format
    used by PlaywrightFinancialService._enrich_item():
      year, revenue, net_profit, assets, equity, lt_liabilities, st_liabilities,
      cost_of_sales, gross_profit, operating_profit, pretax_profit, income_tax
      (all in RUB; None if not reported)
    Returns [] on failure / key missing.
    """
    if not inn:
        return []

    data, err = _get('v1/finance/', {'inn': inn, 'years': years})
    if err:
        logger.info('DataNewton financials: %s for INN %s', err, inn)
        return []

    def _parse_val(v):
        if v is None:
            return None
        try:
            return int(float(str(v).replace(' ', '').replace(',', '.')))
        except (ValueError, TypeError):
            return None

    # Response shape: {fin_results: {year: {fields}}, balances: {year: {fields}}, ...}
    fin_results = data.get('fin_results') or {}
    balances    = data.get('balances') or {}

    all_years = set(fin_results.keys()) | set(balances.keys())
    if not all_years:
        return []

    history = []
    for year_key in all_years:
        try:
            year_int = int(str(year_key)[:4])
        except (ValueError, TypeError):
            continue

        fr = fin_results.get(year_key) or {}
        bl = balances.get(year_key) or {}

        history.append({
            'year':             year_int,
            'revenue':          _parse_val(fr.get('revenue') or fr.get('income') or fr.get('выручка')),
            'cost_of_sales':    _parse_val(fr.get('cost_of_sales') or fr.get('costs')),
            'gross_profit':     _parse_val(fr.get('gross_profit')),
            'operating_profit': _parse_val(fr.get('operating_profit')),
            'pretax_profit':    _parse_val(fr.get('pretax_profit') or fr.get('profit_before_tax')),
            'income_tax':       _parse_val(fr.get('income_tax') or fr.get('tax')),
            'net_profit':       _parse_val(fr.get('net_profit') or fr.get('profit')),
            'assets':           _parse_val(bl.get('assets') or bl.get('total_assets')),
            'equity':           _parse_val(bl.get('equity') or bl.get('capital')),
            'lt_liabilities':   _parse_val(bl.get('lt_liabilities') or bl.get('long_term_liabilities')),
            'st_liabilities':   _parse_val(bl.get('st_liabilities') or bl.get('short_term_liabilities')),
        })

    history.sort(key=lambda x: x.get('year') or 0, reverse=True)
    logger.info('DataNewton financials: INN %s → %d years', inn, len(history))
    return history
