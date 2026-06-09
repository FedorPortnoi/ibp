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
from typing import Dict, Optional

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


def _fmt_rub(value: Optional[float]) -> str:
    if not value or value <= 0:
        return ''
    if value >= 1_000_000_000_000:
        return f'{value / 1_000_000_000_000:.1f} трлн ₽'
    if value >= 1_000_000_000:
        return f'{value / 1_000_000_000:.1f} млрд ₽'
    if value >= 1_000_000:
        return f'{value / 1_000_000:.1f} млн ₽'
    return f'{value:,.0f} ₽'.replace(',', ' ')


class FinancialService:
    """Fetch company financial snapshot from dadata.ru."""

    def __init__(self, timeout: int = 15):
        self.timeout = timeout
        self._api_key = (
            os.getenv('DADATA_API_KEY') or
            os.getenv('DADATA_TOKEN') or ''
        ).strip()

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
        }

        if not self.has_key:
            logger.info("FinancialService: DADATA_API_KEY not configured")
            return {**empty, 'no_key': True}

        if not inn:
            return empty

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
            fin = company.get('finance') or {}

            income  = fin.get('income')
            expense = fin.get('expense')
            year    = fin.get('year')
            debts   = fin.get('debts')
            tax_sys = fin.get('tax_system') or ''
            employees = company.get('employee_count') or ''

            # Derive profit
            profit = None
            is_loss = False
            if income is not None and expense is not None:
                profit = income - expense
                is_loss = profit < 0

            result = {
                'found': income is not None or expense is not None,
                'no_key': False,
                'unavailable': False,
                'income': income,
                'expense': expense,
                'profit': profit,
                'is_loss': is_loss,
                'income_fmt': _fmt_rub(income),
                'expense_fmt': _fmt_rub(expense),
                'profit_fmt': (
                    ('-' if is_loss else '+') + _fmt_rub(abs(profit))
                    if profit is not None else ''
                ),
                'year': year,
                'tax_system': _TAX_SYSTEM_RU.get(tax_sys, tax_sys),
                'debts': debts,
                'debts_fmt': _fmt_rub(debts) if debts else '',
                'employee_count': employees,
            }

            if result['found']:
                logger.info(
                    "dadata.ru: INN %s → income=%s expense=%s year=%s employees=%s",
                    inn, _fmt_rub(income), _fmt_rub(expense), year, employees,
                )
                return result

            # dadata returned empty (large PAO, or data not in FNS open data)
            # Fall back to Playwright bo.nalog.ru scraper
            logger.info("dadata.ru: no financial data for %s — trying bo.nalog.ru", inn)
            return self._playwright_fallback(inn)

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
            }
