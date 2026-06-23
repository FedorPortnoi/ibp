"""
PlaywrightFinancialService — bo.nalog.ru (ГИР БО) Financial Scraper
=====================================================================
Uses Playwright/Chromium to scrape the official FNS accounting reports
portal (bo.nalog.ru). Requires a Russian IP — runs on Yandex Cloud VM.

Returns full financial statements for up to 3 years:
  revenue      — Выручка (line 2110)
  net_profit   — Чистая прибыль/убыток (line 2400)
  assets       — Активы/Баланс (line 1600)
  equity       — Капитал и резервы (line 1300)

Setup on Yandex Cloud (one-time):
  pip install playwright
  playwright install chromium --with-deps

Geo-block handling: connect timeout → unavailable=True (same as kad.arbitr.ru).
"""

import logging
import re
from typing import Dict, List, Optional

from app.services.shared.money_utils import fmt_rub, parse_accounting_cell

logger = logging.getLogger(__name__)

# Accounting line numbers — Отчёт о фин. результатах + Бухгалтерский баланс
_LINES = {
    '2110': 'revenue',           # Выручка
    '2120': 'cost_of_sales',     # Себестоимость продаж
    '2100': 'gross_profit',      # Валовая прибыль
    '2200': 'operating_profit',  # Прибыль/убыток от продаж
    '2300': 'pretax_profit',     # Прибыль до налогообложения
    '2410': 'income_tax',        # Налог на прибыль
    '2400': 'net_profit',        # Чистая прибыль (убыток)
    '1600': 'assets',            # Баланс (активы)
    '1300': 'equity',            # Капитал и резервы
    '1400': 'lt_liabilities',    # Долгосрочные обязательства
    '1500': 'st_liabilities',    # Краткосрочные обязательства
}

# All numeric fields that get a _fmt companion in history items
_NUMERIC_FIELDS = (
    'revenue', 'cost_of_sales', 'gross_profit', 'operating_profit',
    'pretax_profit', 'net_profit', 'income_tax',
    'assets', 'equity', 'lt_liabilities', 'st_liabilities',
)

_DEFAULT_TIMEOUT_SEC = 45



def _enrich_item(item: Dict) -> Dict:
    """Stamp _fmt formatted strings onto every numeric field in a history year dict."""
    enriched = dict(item)
    for key in _NUMERIC_FIELDS:
        val = item.get(key)
        enriched[f'{key}_fmt'] = fmt_rub(val) if val is not None else ''
    return enriched


class PlaywrightFinancialService:
    """
    Scrape bo.nalog.ru for company financial statements.
    Requires Playwright + Chromium + Russian IP.
    """

    def __init__(self, timeout_sec: int = _DEFAULT_TIMEOUT_SEC, headless: bool = True):
        self.timeout_sec = timeout_sec
        self.timeout_ms = timeout_sec * 1000
        self.headless = headless

    def lookup(self, inn: str) -> Dict:
        """
        Scrape bo.nalog.ru for the given INN.

        Returns dict compatible with FinancialService.lookup() format plus
        additional multi-year data in 'history' list.
        """
        empty = {
            'found': False, 'unavailable': False, 'no_key': False,
            'income': None, 'expense': None, 'profit': None,
            'is_loss': False, 'income_fmt': '', 'expense_fmt': '',
            'profit_fmt': '', 'year': None, 'tax_system': '',
            'debts': None, 'debts_fmt': '', 'employee_count': '',
            'revenue': None, 'net_profit': None, 'assets': None,
            'equity': None, 'history': [], 'source': 'bo.nalog.ru',
        }

        try:
            from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
        except ImportError:
            logger.warning(
                "Playwright not installed. "
                "Run: pip install playwright && playwright install chromium --with-deps"
            )
            return {**empty, 'unavailable': True}

        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(
                    headless=self.headless,
                    args=['--no-sandbox', '--disable-dev-shm-usage'],
                )
                ctx = browser.new_context(
                    locale='ru-RU',
                    user_agent=(
                        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                        'AppleWebKit/537.36 (KHTML, like Gecko) '
                        'Chrome/122.0.0.0 Safari/537.36'
                    ),
                )
                page = ctx.new_page()
                try:
                    result = self._scrape(page, inn)
                    return {**empty, **result}
                except Exception as exc:
                    logger.warning("bo.nalog.ru scrape error for %s: %s", inn, exc)
                    return {**empty, 'unavailable': True}
                finally:
                    ctx.close()
                    browser.close()

        except Exception as exc:
            err = str(exc)
            if 'Timeout' in err or 'timeout' in err or 'ERR_CONNECTION' in err:
                logger.info(
                    "bo.nalog.ru: connection timeout for INN %s "
                    "— likely geo-blocked (non-Russian IP)", inn
                )
            else:
                logger.warning("bo.nalog.ru: browser error for %s: %s", inn, exc)
            return {**empty, 'unavailable': True}

    # ── Core scraping flow ───────────────────────────────────────────────────

    def _scrape(self, page, inn: str) -> Dict:
        from playwright.sync_api import TimeoutError as PWTimeout

        # Step 1: load main page
        page.goto('https://bo.nalog.ru/', wait_until='domcontentloaded',
                  timeout=self.timeout_ms)
        page.wait_for_timeout(2000)

        # Step 2: find search input and type INN
        search_input = self._find_search_input(page)
        if not search_input:
            raise RuntimeError("bo.nalog.ru: search input not found")

        search_input.click()
        search_input.fill(inn)
        page.keyboard.press('Enter')

        # Step 3: wait for results and click first match
        company_link = self._wait_for_first_result(page)
        if not company_link:
            logger.info("bo.nalog.ru: no results for INN %s", inn)
            return {'found': False}

        company_link.click()
        page.wait_for_load_state('domcontentloaded', timeout=self.timeout_ms)
        page.wait_for_timeout(2000)

        # Step 4: navigate to accounting/financial tab
        self._open_accounting_tab(page)
        page.wait_for_timeout(2000)

        # Step 5: extract data
        return self._extract(page, inn)

    def _find_search_input(self, page):
        """Try multiple selector strategies to find the search box."""
        selectors = [
            'input[placeholder*="ИНН"]',
            'input[placeholder*="ОГРН"]',
            'input[placeholder*="наименован"]',
            'input[placeholder*="организац"]',
            'input.mat-input-element',
            'input[type="search"]',
            'input[type="text"]',
            'input',
        ]
        for sel in selectors:
            try:
                el = page.wait_for_selector(sel, timeout=3000, state='visible')
                if el:
                    return el
            except Exception:
                continue
        return None

    def _wait_for_first_result(self, page):
        """Wait for search results and return first clickable item."""
        result_selectors = [
            'mat-list-item',
            '.search-result',
            '.company-item',
            '.result-item',
            'li.result',
            'a[href*="/companies/"]',
            'a[href*="/organization"]',
            '.list-item',
        ]
        page.wait_for_timeout(2500)
        for sel in result_selectors:
            try:
                el = page.wait_for_selector(sel, timeout=4000, state='visible')
                if el:
                    return el
            except Exception:
                continue

        # Last resort: find any link that appeared after search
        try:
            els = page.query_selector_all('a')
            for el in els:
                href = el.get_attribute('href') or ''
                if '/companies/' in href or '/organization' in href or '/bfo/' in href:
                    return el
        except Exception:
            pass
        return None

    def _open_accounting_tab(self, page):
        """Find and click the financial statements tab."""
        tab_texts = [
            'Бухгалтерская отчётность',
            'Бухгалтерская',
            'Отчётность',
            'Финансовая',
            'BFO',
        ]
        for text in tab_texts:
            try:
                tab = page.get_by_text(text, exact=False).first
                if tab and tab.is_visible():
                    tab.click()
                    return
            except Exception:
                continue

        # Try tab index selectors
        for sel in ['mat-tab-label', '.tab-label', '[role="tab"]']:
            try:
                tabs = page.query_selector_all(sel)
                for tab in tabs:
                    if any(t in (tab.inner_text() or '') for t in tab_texts):
                        tab.click()
                        return
            except Exception:
                continue

    # ── Data extraction ──────────────────────────────────────────────────────

    def _extract(self, page, inn: str) -> Dict:
        """Extract financial data from the loaded page."""
        html = page.content()
        text = page.inner_text('body')

        # Try structured table extraction first
        history = self._extract_from_tables(page)
        if not history:
            # Fallback: regex over page text
            history = self._extract_from_text(text)

        if not history:
            logger.info("bo.nalog.ru: no financial data found for %s", inn)
            return {'found': False}

        # Enrich each year with _fmt companions, then sort most-recent first
        history = [_enrich_item(yr) for yr in history]
        history.sort(key=lambda x: x.get('year', 0), reverse=True)
        latest = history[0]

        revenue    = latest.get('revenue')
        net_profit = latest.get('net_profit')
        assets     = latest.get('assets')

        # FinancialService-compatible shim fields
        income  = revenue
        expense = (revenue - net_profit) if revenue and net_profit else None

        logger.info(
            "bo.nalog.ru: %s → year=%s revenue=%s net_profit=%s assets=%s",
            inn, latest.get('year'), _fmt(revenue), _fmt(net_profit), _fmt(assets),
        )

        return {
            'found': True,
            'year': latest.get('year'),
            'income': income,
            'expense': expense,
            'profit': net_profit,
            'is_loss': (net_profit is not None and net_profit < 0),
            'income_fmt': _fmt(income),
            'expense_fmt': _fmt(expense),
            'profit_fmt': (('-' if net_profit < 0 else '+') + _fmt(abs(net_profit))
                           if net_profit is not None else ''),
            # Full P&L fields from latest year
            'revenue':              revenue,
            'revenue_fmt':          latest.get('revenue_fmt', ''),
            'cost_of_sales':        latest.get('cost_of_sales'),
            'cost_of_sales_fmt':    latest.get('cost_of_sales_fmt', ''),
            'gross_profit':         latest.get('gross_profit'),
            'gross_profit_fmt':     latest.get('gross_profit_fmt', ''),
            'operating_profit':     latest.get('operating_profit'),
            'operating_profit_fmt': latest.get('operating_profit_fmt', ''),
            'pretax_profit':        latest.get('pretax_profit'),
            'pretax_profit_fmt':    latest.get('pretax_profit_fmt', ''),
            'net_profit':           net_profit,
            'net_profit_fmt':       latest.get('net_profit_fmt', ''),
            'income_tax':           latest.get('income_tax'),
            'income_tax_fmt':       latest.get('income_tax_fmt', ''),
            # Balance sheet fields from latest year
            'assets':               assets,
            'assets_fmt':           latest.get('assets_fmt', ''),
            'equity':               latest.get('equity'),
            'equity_fmt':           latest.get('equity_fmt', ''),
            'lt_liabilities':       latest.get('lt_liabilities'),
            'lt_liabilities_fmt':   latest.get('lt_liabilities_fmt', ''),
            'st_liabilities':       latest.get('st_liabilities'),
            'st_liabilities_fmt':   latest.get('st_liabilities_fmt', ''),
            'history': history,
            'source': 'bo.nalog.ru',
        }

    def _extract_from_tables(self, page) -> List[Dict]:
        """Extract financial data from HTML tables using line number matching."""
        try:
            rows = page.evaluate("""
                () => {
                    const results = [];
                    const tables = document.querySelectorAll('table');
                    tables.forEach(table => {
                        const trs = table.querySelectorAll('tr');
                        trs.forEach(tr => {
                            const cells = Array.from(tr.querySelectorAll('td, th'))
                                              .map(c => c.innerText.trim());
                            results.push(cells);
                        });
                    });
                    return results;
                }
            """)
        except Exception:
            return []

        if not rows:
            return []

        # Find year headers from the first rows
        years = self._detect_years(rows)
        if not years:
            return []

        data_by_year = {y: {} for y in years}

        for row in rows:
            if len(row) < 2:
                continue
            # Look for line number in any cell
            line_num = None
            for cell in row:
                m = re.match(r'^(\d{4})$', cell.strip())
                if m and m.group(1) in _LINES:
                    line_num = m.group(1)
                    break

            if not line_num:
                continue

            field = _LINES[line_num]
            # Extract amounts from cells that look like numbers
            amounts = []
            for cell in row:
                val = parse_accounting_cell(cell)
                if val is not None:
                    amounts.append(val)

            # Map amounts to years (in order)
            for i, year in enumerate(years):
                if i < len(amounts):
                    data_by_year[year][field] = amounts[i]

        return [{'year': y, **vals} for y, vals in data_by_year.items() if vals]

    def _detect_years(self, rows: list) -> List[int]:
        """Find reporting years from table headers."""
        years = []
        for row in rows[:10]:
            for cell in row:
                m = re.search(r'20(1[5-9]|2[0-9])', cell)
                if m:
                    year = int(m.group(0))
                    if year not in years:
                        years.append(year)
        return sorted(set(years), reverse=True)[:4]

    def _extract_from_text(self, text: str) -> List[Dict]:
        """Fallback: parse financial data from plain text content."""
        results: Dict[int, Dict] = {}

        # Find year sections
        year_sections = re.split(r'(?=20(?:1[5-9]|2[0-9])\b)', text)

        for section in year_sections:
            year_m = re.match(r'(20\d{2})', section)
            if not year_m:
                continue
            year = int(year_m.group(1))
            data = {}

            # Revenue / Выручка (2110)
            m = re.search(r'(?:Выручка|2110)[^\d\-]*(-?[\d\s]+)', section, re.I)
            if m:
                val = parse_accounting_cell(m.group(1))
                if val:
                    data['revenue'] = val

            # Cost of sales / Себестоимость продаж (2120)
            m = re.search(r'(?:Себестоимость продаж|Себестоимость|2120)[^\d\-]*(-?[\d\s]+)', section, re.I)
            if m:
                val = parse_accounting_cell(m.group(1))
                if val is not None:
                    data['cost_of_sales'] = val

            # Gross profit / Валовая прибыль (2100)
            m = re.search(r'(?:Валовая прибыль|2100)[^\d\-]*(-?[\d\s]+)', section, re.I)
            if m:
                val = parse_accounting_cell(m.group(1))
                if val is not None:
                    data['gross_profit'] = val

            # Operating profit / Прибыль от продаж (2200)
            m = re.search(r'(?:Прибыль.*?от продаж|2200)[^\d\-]*(-?[\d\s]+)', section, re.I)
            if m:
                val = parse_accounting_cell(m.group(1))
                if val is not None:
                    data['operating_profit'] = val

            # Pre-tax profit / Прибыль до налогообложения (2300)
            m = re.search(r'(?:Прибыль до налог|2300)[^\d\-]*(-?[\d\s]+)', section, re.I)
            if m:
                val = parse_accounting_cell(m.group(1))
                if val is not None:
                    data['pretax_profit'] = val

            # Income tax / Налог на прибыль (2410)
            m = re.search(r'(?:Налог на прибыль|2410)[^\d\-]*(-?[\d\s]+)', section, re.I)
            if m:
                val = parse_accounting_cell(m.group(1))
                if val is not None:
                    data['income_tax'] = val

            # Net profit / Чистая прибыль (2400)
            m = re.search(r'(?:Чистая прибыль|убыток|2400)[^\d\-]*(-?[\d\s]+)', section, re.I)
            if m:
                val = parse_accounting_cell(m.group(1))
                if val is not None:
                    data['net_profit'] = val

            # Total assets / Баланс (1600)
            m = re.search(r'(?:Баланс|Активы|1600)[^\d\-]*(-?[\d\s]+)', section, re.I)
            if m:
                val = parse_accounting_cell(m.group(1))
                if val:
                    data['assets'] = val

            # Equity / Капитал и резервы (1300)
            m = re.search(r'(?:Капитал и резервы|1300)[^\d\-]*(-?[\d\s]+)', section, re.I)
            if m:
                val = parse_accounting_cell(m.group(1))
                if val is not None:
                    data['equity'] = val

            # LT liabilities / Долгосрочные обязательства (1400)
            m = re.search(r'(?:Долгосрочные обязательства|1400)[^\d\-]*(-?[\d\s]+)', section, re.I)
            if m:
                val = parse_accounting_cell(m.group(1))
                if val is not None:
                    data['lt_liabilities'] = val

            # ST liabilities / Краткосрочные обязательства (1500)
            m = re.search(r'(?:Краткосрочные обязательства|1500)[^\d\-]*(-?[\d\s]+)', section, re.I)
            if m:
                val = parse_accounting_cell(m.group(1))
                if val is not None:
                    data['st_liabilities'] = val

            if data:
                results[year] = {**results.get(year, {}), **data, 'year': year}

        return list(results.values())
