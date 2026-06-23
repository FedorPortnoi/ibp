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

            # ── Financial fields ──
            fin = company.get('finance') or {}

            income  = fin.get('income')
            expense = fin.get('expense')
            year    = fin.get('year')
            debts   = fin.get('debts')
            tax_sys = fin.get('tax_system') or ''
            employees = company.get('employee_count') or ''

            profit = None
            is_loss = False
            if income is not None and expense is not None:
                profit = income - expense
                is_loss = profit < 0

            profit_fmt = (
                ('-' if is_loss else '+') + fmt_rub(abs(profit))
                if profit is not None else ''
            )
            result = {
                'found': income is not None or expense is not None,
                'no_key': False,
                'unavailable': False,
                'income': income,
                'expense': expense,
                'profit': profit,
                'is_loss': is_loss,
                'income_fmt': fmt_rub(income),
                'expense_fmt': fmt_rub(expense),
                'profit_fmt': profit_fmt,
                'year': year,
                'tax_system': _TAX_SYSTEM_RU.get(tax_sys, tax_sys),
                'debts': debts,
                'debts_fmt': fmt_rub(debts) if debts else '',
                'employee_count': employees,
                'source': 'dadata.ru',
                **identity,
            }

            # Single-year history for unified template rendering
            if result['found']:
                result['history'] = [{
                    'year': year,
                    'revenue': income,
                    'revenue_fmt': fmt_rub(income) if income else '',
                    'net_profit': profit,
                    'net_profit_fmt': profit_fmt,
                    'cost_of_sales': None, 'cost_of_sales_fmt': '',
                    'gross_profit': None, 'gross_profit_fmt': '',
                    'operating_profit': None, 'operating_profit_fmt': '',
                    'pretax_profit': None, 'pretax_profit_fmt': '',
                    'income_tax': None, 'income_tax_fmt': '',
                    'assets': None, 'assets_fmt': '',
                    'equity': None, 'equity_fmt': '',
                    'lt_liabilities': None, 'lt_liabilities_fmt': '',
                    'st_liabilities': None, 'st_liabilities_fmt': '',
                }]

            if result['found']:
                logger.info(
                    "dadata.ru: INN %s → income=%s expense=%s year=%s employees=%s party_status=%s",
                    inn, fmt_rub(income), fmt_rub(expense), year, employees,
                    identity['party_status'],
                )
                self._cache[inn] = (result, time.time() + _CACHE_TTL)
                return result

            # dadata returned no financial data (large PAO, or not in FNS open data).
            # Try Playwright fallback for financials, but keep identity fields from dadata.
            logger.info("dadata.ru: no financial data for %s — trying bo.nalog.ru", inn)
            playwright_result = self._playwright_fallback(inn)
            merged = {**playwright_result, **identity}
            self._cache[inn] = (merged, time.time() + _CACHE_TTL)
            return merged

        except requests.Timeout:
            logger.warning("dadata.ru: timeout for INN %s — trying bo.nalog.ru", inn)
            return self._playwright_fallback(inn)
        except Exception as exc:
            logger.warning("dadata.ru: error for INN %s: %s", inn, exc)
            return self._playwright_fallback(inn)

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
