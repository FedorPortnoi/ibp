"""
GovContractsService — ЕИС Закупки (zakupki.gov.ru)
====================================================
Scrapes the official Russian procurement register for contracts where
the target company appears as a supplier (поставщик/исполнитель).

Source: zakupki.gov.ru — Единая информационная система в сфере закупок.
        Geo-blocked from non-Russian IPs (same as kad.arbitr.ru).
        Works from Yandex Cloud VM.

Returns:
    found          — True if at least one contract was found
    unavailable    — True if ЕИС was unreachable (timeout / geo-block)
    total_count    — number of contracts found in search
    total_amount   — sum of all matching contracts (RUB)
    contracts      — list of recent contracts (up to 20)
    source_url     — direct link to ЕИС search results for this INN
"""

import logging
import re
from typing import Dict, List

import requests
from bs4 import BeautifulSoup
from urllib.parse import quote

logger = logging.getLogger(__name__)

_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/122.0.0.0 Safari/537.36'
    ),
    'Accept': 'text/html,application/xhtml+xml,*/*;q=0.8',
    'Accept-Language': 'ru-RU,ru;q=0.9',
    'Referer': 'https://zakupki.gov.ru/',
}


def _parse_amount(text: str) -> float:
    """Parse Russian money string like '1 234 567,89' → 1234567.89"""
    if not text:
        return 0.0
    cleaned = re.sub(r'[^\d,.]', '', text.replace(' ', '').replace('\xa0', ''))
    cleaned = cleaned.replace(',', '.')
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def _fmt_amount(value: float) -> str:
    if value <= 0:
        return ''
    if value >= 1_000_000_000:
        return f'{value / 1_000_000_000:.1f} млрд ₽'
    if value >= 1_000_000:
        return f'{value / 1_000_000:.1f} млн ₽'
    return f'{value:,.0f} ₽'.replace(',', ' ')


class GovContractsService:
    """Search ЕИС Закупки for company contracts by INN."""

    _BASE = 'https://zakupki.gov.ru'

    # Supplier search: contracts where INN appears as participant/supplier
    _SEARCH_PATH = '/epz/contract/search/results.html'

    def __init__(self, timeout: int = 20):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(_HEADERS)

    def lookup(self, inn: str, company_name: str = '') -> Dict:
        """
        Search ЕИС for government contracts where company is a supplier.

        Returns dict:
          found         — True if contracts found
          unavailable   — True if ЕИС was geo-blocked/unreachable
          total_count   — total matching contracts (from search result header)
          total_amount  — sum of displayed contract amounts (RUB)
          contracts     — list of contract dicts (up to 20)
          source_url    — link to search results in ЕИС
        """
        empty: Dict = {
            'found': False,
            'unavailable': False,
            'total_count': 0,
            'total_amount': 0.0,
            'total_amount_fmt': '',
            'contracts': [],
            'source_url': '',
        }

        if not inn:
            return empty

        # Build search URL — search by INN as text string, supplier role
        search_url = (
            f'{self._BASE}{self._SEARCH_PATH}'
            f'?searchString={quote(inn)}'
            f'&morphology=on&pageSize=20'
            f'&sortBy=PRICE&sortDirection=false'
            f'&recordsPerPage=_20'
        )
        empty['source_url'] = search_url

        try:
            resp = self.session.get(search_url, timeout=self.timeout, allow_redirects=True)

            if resp.status_code != 200:
                logger.warning("ЕИС Закупки: HTTP %d for INN %s", resp.status_code, inn)
                return {**empty, 'unavailable': True, 'source_url': search_url}

            contracts, total_count, total_amount = self._parse_results(resp.text)

            if not contracts and total_count == 0:
                logger.info("ЕИС Закупки: no contracts for INN %s", inn)
                return {**empty, 'source_url': search_url}

            result = {
                'found': bool(contracts) or total_count > 0,
                'unavailable': False,
                'total_count': total_count,
                'total_amount': total_amount,
                'total_amount_fmt': _fmt_amount(total_amount),
                'contracts': contracts,
                'source_url': search_url,
            }
            logger.info(
                "ЕИС Закупки: INN %s → %d contracts, total_count=%d",
                inn, len(contracts), total_count,
            )
            return result

        except requests.Timeout:
            # zakupki.gov.ru geo-blocks non-Russian IPs (connect timeout).
            # Works from Yandex Cloud VM. Same situation as kad.arbitr.ru.
            logger.info("ЕИС Закупки: timeout for INN %s — likely geo-blocked", inn)
            return {**empty, 'unavailable': True, 'source_url': search_url}
        except Exception as exc:
            logger.warning("ЕИС Закупки: error for INN %s: %s", inn, exc)
            return {**empty, 'unavailable': True, 'source_url': search_url}

    def _parse_results(self, html: str):
        """
        Parse zakupki.gov.ru contract search results page.

        Returns (contracts: list, total_count: int, total_amount: float).
        Tolerates HTML structure changes — uses multiple selector strategies.
        """
        soup = BeautifulSoup(html, 'lxml')
        contracts: List[Dict] = []
        total_count = 0
        total_amount = 0.0

        # ── Total count ────────────────────────────────────────────────────
        # Pattern: "Найдено записей: 123" or "Всего: 123"
        count_el = soup.find(string=re.compile(r'найдено|записей|всего', re.IGNORECASE))
        if count_el:
            m = re.search(r'(\d[\d\s]*)', count_el)
            if m:
                total_count = int(re.sub(r'\s', '', m.group(1)))

        # Also check the total amount header
        total_el = soup.find(string=re.compile(r'сумм[аы].*контракт|итого', re.IGNORECASE))
        if total_el:
            m = re.search(r'[\d\s,]+', total_el.find_parent().get_text())
            if m:
                total_amount = _parse_amount(m.group())

        # ── Contract rows ──────────────────────────────────────────────────
        # Strategy 1: registry-entry__form containers (modern ЕИС layout)
        entries = soup.select('div.registry-entry__form, div.registry-entry__body')

        # Strategy 2: table rows if it's a table layout
        if not entries:
            table = soup.find('table', class_=re.compile(r'contract|registry', re.IGNORECASE))
            if table:
                entries = table.find_all('tr')[1:]  # skip header

        # Strategy 3: any div containing a contract registration number
        if not entries:
            entries = soup.find_all(
                'div', attrs={'data-id': True}
            ) or soup.find_all(
                'div', class_=re.compile(r'contract|tender|purchase', re.IGNORECASE)
            )

        for entry in entries[:20]:
            contract = self._parse_contract_entry(entry)
            if contract and contract.get('reg_number'):
                contracts.append(contract)
                if contract.get('amount'):
                    total_amount += contract['amount']

        # If we got contracts but no total_count from the header, infer it
        if contracts and total_count == 0:
            total_count = len(contracts)

        return contracts, total_count, total_amount

    def _parse_contract_entry(self, entry) -> Dict:
        """Extract contract fields from a single result entry."""
        text = entry.get_text(' ', strip=True) if hasattr(entry, 'get_text') else str(entry)

        # Registration number — format: YYYYMMDD-NNNNNN or long numeric string
        reg_m = re.search(r'\d{8}-\d{7,}|\d{19,}', text)
        reg_number = reg_m.group(0) if reg_m else ''

        # Alternative: link text ending in contract number
        link = entry.find('a', href=re.compile(r'/epz/contract/', re.IGNORECASE)) if hasattr(entry, 'find') else None
        contract_url = ''
        if link:
            href = link.get('href', '')
            contract_url = href if href.startswith('http') else f'{self._BASE}{href}'
            if not reg_number:
                reg_number = link.get_text(strip=True)[:50]

        # Amount — look for РУБ or ₽ near a number
        amount_m = re.search(
            r'([\d\s]+[,.]?\d*)\s*(?:руб|₽|rub)', text, re.IGNORECASE
        )
        amount = _parse_amount(amount_m.group(1)) if amount_m else 0.0

        # Date — DD.MM.YYYY
        date_m = re.search(r'\d{2}\.\d{2}\.\d{4}', text)
        date = date_m.group(0) if date_m else ''

        # Customer name — heuristic: long Cyrillic phrase after keywords
        customer_m = re.search(
            r'(?:заказчик|покупатель)[:\s]+([А-ЯЁа-яё][^,\n]{5,100})',
            text, re.IGNORECASE,
        )
        customer = customer_m.group(1).strip()[:200] if customer_m else ''

        # Subject — longest text fragment that looks like a description
        subject_m = re.search(
            r'(?:предмет|наименование)[:\s]+([А-ЯЁа-яё][^,\n]{10,200})',
            text, re.IGNORECASE,
        )
        subject = subject_m.group(1).strip()[:300] if subject_m else ''

        # Status
        status_m = re.search(
            r'(исполнен|расторгнут|исполняется|заключён|завершён)',
            text, re.IGNORECASE,
        )
        status = status_m.group(1).lower() if status_m else ''

        return {
            'reg_number': reg_number,
            'subject': subject,
            'customer_name': customer,
            'amount': amount,
            'amount_fmt': _fmt_amount(amount),
            'date': date,
            'status': status,
            'url': contract_url,
        }
