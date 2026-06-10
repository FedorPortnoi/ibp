"""
RNPService — Реестр недобросовестных поставщиков (zakupki.gov.ru)
==================================================================
Scrapes the official RNP section of the EIS procurement portal.
Companies are blacklisted for 2 years for evading or breaching a
government contract under 44-ФЗ, 223-ФЗ, or 615-ПП.

Source: zakupki.gov.ru/epz/dishonestsupplier/
        Geo-blocked from non-Russian IPs.
        Works from Yandex Cloud VM (same as GovContractsService).

Returns:
    found          — True if at least one RNP entry was found
    unavailable    — True if geo-blocked / unreachable
    active         — True if at least one entry is still within the 2-year ban
    entries        — list of RNP entry dicts
    source_url     — direct link to search results
"""

import logging
import re
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

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

_BASE = 'https://zakupki.gov.ru'
_SEARCH_PATH = '/epz/dishonestsupplier/search/results.html'


def _parse_date(text: str) -> Optional[date]:
    """Parse DD.MM.YYYY → date, or None."""
    if not text:
        return None
    m = re.search(r'(\d{2})\.(\d{2})\.(\d{4})', text.strip())
    if not m:
        return None
    try:
        return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    except ValueError:
        return None


def _fmt_date(d: Optional[date]) -> str:
    return d.strftime('%d.%m.%Y') if d else ''


class RNPService:
    """Check company INN against the Registry of Unfair Suppliers."""

    def __init__(self, timeout: int = 20):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(_HEADERS)

    def lookup(self, inn: str) -> Dict:
        empty: Dict = {
            'found': False,
            'unavailable': False,
            'active': False,
            'entries': [],
            'source_url': '',
        }

        if not inn:
            return empty

        search_url = (
            f'{_BASE}{_SEARCH_PATH}'
            f'?searchString={quote(inn)}'
            f'&morphology=on&pageNumber=1'
            f'&sortDirection=false&recordsPerPage=_10'
            f'&showLoading=false&fz44=on&fz223=on&ppRf615=on'
        )
        empty['source_url'] = search_url

        try:
            resp = self.session.get(search_url, timeout=self.timeout, allow_redirects=True)

            if resp.status_code != 200:
                logger.warning("РНП: HTTP %d for INN %s", resp.status_code, inn)
                return {**empty, 'unavailable': True}

            entries = self._parse(resp.text, inn)
            active = any(e.get('is_active') for e in entries)

            logger.info("РНП: INN %s → %d entries (active=%s)", inn, len(entries), active)
            return {
                'found': bool(entries),
                'unavailable': False,
                'active': active,
                'entries': entries,
                'source_url': search_url,
            }

        except requests.Timeout:
            logger.info("РНП: timeout for INN %s — geo-blocked (non-RU IP)", inn)
            return {**empty, 'unavailable': True}
        except Exception as exc:
            logger.warning("РНП: error for INN %s: %s", inn, exc)
            return {**empty, 'unavailable': True}

    def _parse(self, html: str, inn: str) -> List[Dict]:
        soup = BeautifulSoup(html, 'lxml')
        entries: List[Dict] = []

        # Each RNP entry is wrapped in div.registry-entry__form
        cards = soup.select('div.registry-entry__form')
        if not cards:
            # Fallback — broader selector
            cards = soup.select('[class*="registry-entry"]')

        for card in cards:
            entry = self._parse_card(card)
            if entry:
                entries.append(entry)

        # Cross-check: filter to entries that actually match the queried INN
        # (search may return partial-name matches)
        if inn:
            matched = [e for e in entries if e.get('inn') == inn or not e.get('inn')]
            if matched:
                entries = matched

        return entries

    def _parse_card(self, card) -> Optional[Dict]:
        text = card.get_text(' ', strip=True)

        # ── Registry number ────────────────────────────────────────────────
        num_el = card.select_one('[class*="header-mid__number"]')
        registry_number = num_el.get_text(strip=True) if num_el else ''
        if not registry_number:
            m = re.search(r'РНП[\.\-]\s*[\d\-]+', text, re.IGNORECASE)
            registry_number = m.group(0).strip() if m else ''

        # ── Law basis (44-ФЗ / 223-ФЗ / 615-ПП) ──────────────────────────
        basis_el = card.select_one('[class*="header-top__title"]')
        basis = basis_el.get_text(strip=True) if basis_el else ''
        if not basis:
            m = re.search(r'(?:44|223)[-‑]ФЗ|615[-‑]ПП', text)
            basis = m.group(0) if m else ''

        # ── Company name and INN from body blocks ──────────────────────────
        company_name = ''
        company_inn  = ''
        body_blocks = card.select('[class*="body-block"]')
        for block in body_blocks:
            block_text = block.get_text(' ', strip=True)
            # INN
            if not company_inn:
                m = re.search(r'ИНН[:\s]*(\d{10,12})', block_text, re.IGNORECASE)
                if m:
                    company_inn = m.group(1)
            # Name — long Cyrillic phrase
            if not company_name:
                m = re.search(
                    r'(?:наименование|участник)[:\s]+([А-ЯЁа-яёA-Za-z][^\n]{5,150})',
                    block_text, re.IGNORECASE,
                )
                if m:
                    company_name = m.group(1).strip()[:200]

        # Fallback INN from full card text
        if not company_inn:
            m = re.search(r'\b(\d{10,12})\b', text)
            if m:
                company_inn = m.group(1)

        # ── Dates from right block ─────────────────────────────────────────
        right = card.select_one('[class*="right-block"]')
        right_text = right.get_text(' ', strip=True) if right else text

        # Try labelled dates first
        inc_date: Optional[date] = None
        exp_date: Optional[date] = None

        inc_m = re.search(r'(?:включ|добавл|внесен)[^\d]*(\d{2}\.\d{2}\.\d{4})',
                          right_text, re.IGNORECASE)
        if inc_m:
            inc_date = _parse_date(inc_m.group(1))

        exp_m = re.search(r'(?:исключ|оконч|действ)[^\d]*(\d{2}\.\d{2}\.\d{4})',
                          right_text, re.IGNORECASE)
        if exp_m:
            exp_date = _parse_date(exp_m.group(1))

        # If only one date found, derive the other (RNP ban = 2 years)
        if inc_date and not exp_date:
            exp_date = date(inc_date.year + 2, inc_date.month, inc_date.day)
        elif exp_date and not inc_date:
            inc_date = date(exp_date.year - 2, exp_date.month, exp_date.day)

        # Fallback — grab any two dates from the card
        if not inc_date:
            all_dates = [_parse_date(d) for d in re.findall(r'\d{2}\.\d{2}\.\d{4}', text)]
            all_dates = sorted([d for d in all_dates if d], reverse=False)
            if all_dates:
                inc_date = all_dates[0]
                exp_date = (
                    all_dates[-1]
                    if len(all_dates) > 1
                    else date(inc_date.year + 2, inc_date.month, inc_date.day)
                )

        # ── Active flag ────────────────────────────────────────────────────
        is_active = bool(exp_date and exp_date >= date.today())

        # ── Detail URL ────────────────────────────────────────────────────
        detail_url = ''
        link = card.select_one('a[href*="dishonestsupplier"]')
        if link:
            href = link.get('href', '')
            detail_url = href if href.startswith('http') else f'{_BASE}{href}'

        # Skip cards with no meaningful data
        if not registry_number and not company_inn and not inc_date:
            return None

        return {
            'registry_number': registry_number,
            'company_name':    company_name,
            'inn':             company_inn,
            'basis':           basis,
            'inclusion_date':  _fmt_date(inc_date),
            'expiry_date':     _fmt_date(exp_date),
            'is_active':       is_active,
            'detail_url':      detail_url,
        }
