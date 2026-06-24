"""
FinancialService — Company Financial Data via dadata.ru
=========================================================
Uses dadata.ru "Организация по ИНН" endpoint which returns financial
data from FNS declarations alongside company registration details.

Returns for a given INN:
  income        — Доходы (RUB, from FNS tax return)
  expense       — Расходы (RUB)
  profit        — Derived: income - expense
  year          — Reporting year
  tax_system    — ОСН / УСН / ЕСХН / ПСН etc.
  debts         — Tax debts (if published)
  employee_count — Headcount range string ("100-249", "1000-4999", etc.)

Requires DADATA_API_KEY in .env (free tier: 500 req/day).
Register at: https://dadata.ru/profile/
"""

import logging
import os
import time
from typing import Dict, Optional

from app.services.shared.money_utils import fmt_rub

import requests

logger = logging.getLogger(__name__)

_BASE_URL = 'https://suggestions.dadata.ru/suggestions/api/4_1/rs/findById/party'

_HEADERS = {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
}

_TAX_SYSTEM_RU = {
    'OSN':  'ОСН',
    'USN':  'УСН',
    'ESHN': 'ЕСХН',
    'PSN':  'ПСН',
    'ENVD': 'ЕНВД',
    'NPD':  'НПД (самозанятый)',
}

_STATUS_RU = {
    'ACTIVE':        'Действующее',
    'LIQUIDATING':   'В стадии ликвидации',
    'LIQUIDATED':    'Ликвидировано',
    'REORGANIZING':  'В стадии реорганизации',
    'BANKRUPT':      'Банкротство',
}

# ИП cessation comes through as LIQUIDATED in dadata but the FNS wording is different
_IP_STATUS_RU = {
    'ACTIVE':        'Действующее',
    'LIQUIDATING':   'В стадии прекращения',
    'LIQUIDATED':    'Прекратил деятельность',
    'REORGANIZING':  'В стадии реорганизации',
    'BANKRUPT':      'Банкротство',
}


_CACHE_TTL = 3600  # seconds — reuse dadata result for same INN within 1 hour


class FinancialService:
    """Fetch company financial snapshot from dadata.ru."""

    def __init__(self, timeout: int = 15):
        self.timeout = timeout
        self._api_key = (
            os.getenv('DADATA_API_KEY') or
            os.getenv('DADATA_TOKEN') or ''
        ).strip()
        self._cache: Dict[str, tuple] = {}  # inn → (result_dict, expires_at)

    @property
    def has_key(self) -> bool:
        return bool(self._api_key)

    def lookup(self, inn: str) -> Dict:
        """
        Fetch financial data for a company by INN.

        Returns dict:
          found          — True if financial data was returned
          no_key         — True if DADATA_API_KEY is not configured
          unavailable    — True if API call failed
          income         — Доходы (float, RUB)
          expense        — Расходы (float, RUB)
          profit         — income - expense (float)
          is_loss        — True if expense > income
          profit_fmt     — Human-readable profit/loss string
          income_fmt     — Human-readable income string
          expense_fmt    — Human-readable expense string
          year           — Reporting year (int)
          tax_system     — Tax regime display string
          debts          — Tax debts (float, RUB) or None
          debts_fmt      — Human-readable debts string
          employee_count — Headcount range string
        """
        empty: Dict = {
            'found': False,
            'no_key': False,
            'unavailable': False,
            'income': None,
            'expense': None,
            'profit': None,
            'is_loss': False,
            'profit_fmt': '',
            'income_fmt': '',
            'expense_fmt': '',
            'year': None,
            'tax_system': '',
            'debts': None,
            'debts_fmt': '',
            'employee_count': '',
            # Identity fields — populated from dadata even when financial data is absent
            'party_name': '',
            'party_short_name': '',
            'party_status': '',
            'party_liquidation_date': '',
        }

        if not self.has_key:
            logger.info("FinancialService: DADATA_API_KEY not configured")
            return {**empty, 'no_key': True}

        if not inn:
            return empty

        # Return cached result if still fresh — avoids burning quota on repeat checks
        cached, expires_at = self._cache.get(inn, (None, 0))
        if cached is not None and time.time() < expires_at:
            logger.debug("dadata.ru: cache hit for INN %s", inn)
            return cached

        try:
            resp = requests.post(
                _BASE_URL,
                json={'query': inn.strip(), 'count': 1},
                headers={**_HEADERS, 'Authorization': f'Token {self._api_key}'},
                timeout=self.timeout,
            )

            if resp.status_code == 403:
                logger.warning("dadata.ru: 403 — invalid or expired API key")
                return {**empty, 'unavailable': True}

            if resp.status_code == 429:
                logger.warning("dadata.ru: 429 — daily quota exceeded")
                return {**empty, 'unavailable': True}

            if resp.status_code != 200:
                logger.warning("dadata.ru: HTTP %d for INN %s", resp.status_code, inn)
                return {**empty, 'unavailable': True}

            data = resp.json()
            suggestions = data.get('suggestions') or []
            if not suggestions:
                logger.info("dadata.ru: no results for INN %s", inn)
                return empty

            company = suggestions[0].get('data') or {}

            # ── Identity fields (always extracted, used to patch ИП name/status) ──
            name_block  = company.get('name') or {}
            state_block = company.get('state') or {}
            status_code = state_block.get('status') or ''
            is_ip = len(inn.strip()) == 12
            status_map = _IP_STATUS_RU if is_ip else _STATUS_RU

            liq_date = ''
            liq_ms = state_block.get('liquidation_date')
            if liq_ms:
                try:
                    from datetime import datetime, timezone
                    dt = datetime.fromtimestamp(liq_ms / 1000, tz=timezone.utc)
                    liq_date = dt.strftime('%d.%m.%Y')
                except Exception:
                    pass

            identity = {
                'party_name':             name_block.get('full_with_opf') or name_block.get('full') or '',
                'party_short_name':       name_block.get('short_with_opf') or name_block.get('short') or '',
                'party_status':           status_map.get(status_code, ''),
                'party_liquidation_date': liq_date,
            }

            # ── Financial fields: always from DataNewton (FNS/Rosstat) ──
            dn_result = self._datanewton_financials(inn, identity)
            self._cache[inn] = (dn_result, time.time() + _CACHE_TTL)
            return dn_result

        except requests.Timeout:
            logger.warning("dadata.ru: timeout for INN %s", inn)
            return self._datanewton_financials(inn, {})
        except Exception as exc:
            logger.warning("dadata.ru: error for INN %s: %s", inn, exc)
            return self._datanewton_financials(inn, {})

    def _datanewton_financials(self, inn: str, identity: Dict) -> Dict:
        """Fetch financial data from DataNewton (FNS/Rosstat) — primary financial source."""
        empty = {
            'found': False, 'no_key': False, 'unavailable': False, 'blocked': False,
            'income': None, 'expense': None, 'profit': None,
            'is_loss': False, 'income_fmt': '', 'expense_fmt': '',
            'profit_fmt': '', 'year': None, 'tax_system': '',
            'debts': None, 'debts_fmt': '', 'employee_count': '',
            'party_name': '', 'party_short_name': '',
            'party_status': '', 'party_liquidation_date': '',
        }
        try:
            from app.services.company.datanewton_service import _get, _get_key
            if not _get_key():
                return {**empty, **identity, 'no_key': True}
            _raw, _err = _get('v1/finance/', {'inn': inn, 'years': 3})
            if _err == 'blocked':
                logger.info("DataNewton finance: paid tier required for INN %s — purchase needed", inn)
                return {**empty, **identity, 'blocked': True, 'source': 'DataNewton'}
            if _err or not _raw:
                return {**empty, **identity}

            # Parse response directly — avoids a second HTTP request
            def _pv(v):
                if v is None:
                    return None
                try:
                    return int(float(str(v).replace(' ', '').replace(',', '.')))
                except (ValueError, TypeError):
                    return None
            fin_results = _raw.get('fin_results') or {}
            balances    = _raw.get('balances') or {}
            all_years   = set(fin_results.keys()) | set(balances.keys())
            if not all_years:
                return {**empty, **identity}
            history_raw = []
            for yk in sorted(all_years, reverse=True):
                try:
                    yi = int(str(yk)[:4])
                except (ValueError, TypeError):
                    continue
                fr = fin_results.get(yk) or {}
                bl = balances.get(yk) or {}
                history_raw.append({
                    'year':             yi,
                    'revenue':          _pv(fr.get('revenue') or fr.get('income') or fr.get('выручка')),
                    'cost_of_sales':    _pv(fr.get('cost_of_sales') or fr.get('costs')),
                    'gross_profit':     _pv(fr.get('gross_profit')),
                    'operating_profit': _pv(fr.get('operating_profit')),
                    'pretax_profit':    _pv(fr.get('pretax_profit') or fr.get('profit_before_tax')),
                    'income_tax':       _pv(fr.get('income_tax') or fr.get('tax')),
                    'net_profit':       _pv(fr.get('net_profit') or fr.get('profit')),
                    'assets':           _pv(bl.get('assets') or bl.get('total_assets')),
                    'equity':           _pv(bl.get('equity') or bl.get('capital')),
                    'lt_liabilities':   _pv(bl.get('lt_liabilities') or bl.get('long_term_liabilities')),
                    'st_liabilities':   _pv(bl.get('st_liabilities') or bl.get('short_term_liabilities')),
                })
            history = history_raw
            if not history:
                return {**empty, **identity}
            from app.services.company.playwright_financial_service import _enrich_item
            history = [_enrich_item(yr) for yr in history]
            latest = history[0]
            revenue = latest.get('revenue')
            net_profit = latest.get('net_profit')
            profit_fmt = (
                ('-' if net_profit < 0 else '+') + fmt_rub(abs(net_profit))
                if net_profit is not None else ''
            )
            return {
                **empty, **identity,
                'found': True,
                'source': 'datanewton (FNS)',
                'year': latest.get('year'),
                'income': revenue,
                'income_fmt': fmt_rub(revenue) if revenue is not None else '',
                'expense': None, 'expense_fmt': '',
                'profit': net_profit,
                'profit_fmt': profit_fmt,
                'is_loss': (net_profit is not None and net_profit < 0),
                'revenue': revenue,
                'revenue_fmt': latest.get('revenue_fmt', ''),
                'net_profit': net_profit,
                'net_profit_fmt': latest.get('net_profit_fmt', ''),
                'assets': latest.get('assets'),
                'assets_fmt': latest.get('assets_fmt', ''),
                'equity': latest.get('equity'),
                'equity_fmt': latest.get('equity_fmt', ''),
                'history': history,
            }
        except Exception as exc:
            logger.warning("DataNewton fallback failed for %s: %s", inn, exc)
            return {**empty, **identity}

    def _playwright_fallback(self, inn: str) -> Dict:
        """Fall back to bo.nalog.ru via Playwright when dadata has no data."""
        try:
            from app.services.company.playwright_financial_service import (
                PlaywrightFinancialService,
            )
            svc = PlaywrightFinancialService(timeout_sec=45)
            return svc.lookup(inn)
        except Exception as exc:
            logger.warning("Playwright fallback failed for %s: %s", inn, exc)
            return {
                'found': False, 'no_key': False, 'unavailable': True,
                'income': None, 'expense': None, 'profit': None,
                'is_loss': False, 'income_fmt': '', 'expense_fmt': '',
                'profit_fmt': '', 'year': None, 'tax_system': '',
                'debts': None, 'debts_fmt': '', 'employee_count': '',
                'party_name': '', 'party_short_name': '',
                'party_status': '', 'party_liquidation_date': '',
            }
