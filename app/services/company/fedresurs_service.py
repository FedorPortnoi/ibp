"""
FedresursService — ЕФРСБ Bankruptcy Registry
=============================================
Queries bankrot.fedresurs.ru for active/historical bankruptcy proceedings.

Source: Единый федеральный реестр сведений о банкротстве (ЕФРСБ)
        bankrot.fedresurs.ru — official public registry, globally accessible.

Returns structured data: stage, arbitration manager, court, case number, start date.
"""

import logging
import re
from typing import Dict

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
}

# Canonical stage names matching ЕФРСБ terminology, ordered by search priority
_STAGE_KEYWORDS = [
    ('конкурсное производство',     'Конкурсное производство'),
    ('наблюдение',                  'Наблюдение'),
    ('внешнее управление',          'Внешнее управление'),
    ('финансовое оздоровление',     'Финансовое оздоровление'),
    ('реализация имущества',        'Реализация имущества гражданина'),
    ('реструктуризация долгов',     'Реструктуризация долгов гражданина'),
    ('мировое соглашение',          'Мировое соглашение'),
    ('прекращено',                  'Прекращено'),
    ('завершено',                   'Завершено'),
]

# Stages that indicate ongoing (not completed) proceedings
_ACTIVE_STAGES = {
    'Конкурсное производство',
    'Наблюдение',
    'Внешнее управление',
    'Финансовое оздоровление',
    'Реализация имущества гражданина',
    'Реструктуризация долгов гражданина',
}


def _normalize_stage(text: str) -> str:
    tl = text.lower()
    for kw, canonical in _STAGE_KEYWORDS:
        if kw in tl:
            return canonical
    return ''


class FedresursService:
    """Look up bankruptcy proceedings in ЕФРСБ by INN."""

    _BASE = 'https://bankrot.fedresurs.ru'
    _SEARCH = f'{_BASE}/DebtorsSearch.aspx'

    def __init__(self, timeout: int = 20):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(_HEADERS)

    def lookup(self, inn: str, company_name: str = '') -> Dict:
        """
        Check ЕФРСБ for bankruptcy proceedings matching the given INN.

        Returns dict:
          found       — True if a bankruptcy record was found
          active      — True if proceedings are still ongoing (not completed)
          unavailable — True if ЕФРСБ was unreachable (timeout / geo-block)
          stage       — current stage in Russian (e.g. "Конкурсное производство")
          manager_name — arbitration manager (арбитражный управляющий)
          court_name  — court handling the case
          case_number — arbitration case number (А12-34567/2023 format)
          start_date  — date proceedings started (DD.MM.YYYY)
          source_url  — direct link to ЕФРСБ debtor page
        """
        empty: Dict = {
            'found': False,
            'active': False,
            'unavailable': False,
            'stage': '',
            'manager_name': '',
            'court_name': '',
            'case_number': '',
            'start_date': '',
            'source_url': '',
        }

        if not inn:
            return empty

        try:
            url = f'{self._SEARCH}?SearchString={quote(inn.strip())}'
            resp = self.session.get(url, timeout=self.timeout, allow_redirects=True)
            if resp.status_code != 200:
                logger.warning("ЕФРСБ: HTTP %d for INN %s", resp.status_code, inn)
                return {**empty, 'unavailable': True}

            href, stage, manager = self._parse_search_page(resp.text, inn)
            if not href:
                logger.info("ЕФРСБ: %s not found (not in bankruptcy)", inn)
                return empty  # unavailable=False, found=False → confirmed clean

            full_url = href if href.startswith('http') else f'{self._BASE}{href}'
            result: Dict = {
                **empty,
                'found': True,
                'stage': stage,
                'manager_name': manager,
                'source_url': full_url,
                'active': stage in _ACTIVE_STAGES,
            }

            # Fetch debtor card for court name, case number, start date
            try:
                card_resp = self.session.get(full_url, timeout=self.timeout, allow_redirects=True)
                if card_resp.status_code == 200:
                    extra = self._parse_debtor_card(card_resp.text)
                    for k, v in extra.items():
                        if v:
                            result[k] = v
                    # Card stage overrides search page (more detailed)
                    if extra.get('stage'):
                        result['stage'] = extra['stage']
                        result['active'] = extra['stage'] in _ACTIVE_STAGES
            except Exception as exc:
                logger.debug("ЕФРСБ debtor card error: %s", exc)

            logger.info(
                "ЕФРСБ: %s → found=True stage=%s manager=%s",
                inn, result['stage'], result['manager_name'],
            )
            return result

        except requests.Timeout:
            # bankrot.fedresurs.ru and fedresurs.ru are geo-blocked outside Russia.
            # Timeouts are expected from non-Russian IPs — same situation as kad.arbitr.ru.
            # Works from Yandex Cloud VM.
            logger.info("ЕФРСБ: timeout for INN %s — likely geo-blocked (non-Russian IP)", inn)
            return {**empty, 'unavailable': True}
        except Exception as exc:
            logger.warning("ЕФРСБ: lookup failed for %s: %s", inn, exc)
            return {**empty, 'unavailable': True}

    def _parse_search_page(self, html: str, inn: str) -> tuple:
        """
        Parse DebtorsSearch.aspx result table.

        Strategy: scan every <tr> for one that contains the target INN,
        then extract the /Debtors/ link, stage, and manager from that row.
        Tolerates any GridView column ordering.

        Returns (href, stage, manager_name).  All empty strings if not found.
        """
        soup = BeautifulSoup(html, 'lxml')

        for row in soup.find_all('tr'):
            row_text = row.get_text(' ', strip=True)
            if inn not in row_text:
                continue

            link = row.find('a', href=re.compile(r'/Debtors/', re.IGNORECASE))
            if not link:
                continue

            cells = row.find_all('td')
            stage = ''
            manager = ''

            for i, cell in enumerate(cells):
                cell_lower = cell.get_text(strip=True).lower()
                for kw, canonical in _STAGE_KEYWORDS:
                    if kw in cell_lower:
                        stage = canonical
                        # Manager name is typically in the adjacent cell
                        if i + 1 < len(cells):
                            manager_text = cells[i + 1].get_text(strip=True)
                            # Sanity check: manager should look like a full name
                            if re.search(r'[А-ЯЁ][а-яё]+\s+[А-ЯЁ]', manager_text):
                                manager = manager_text[:255]
                        break
                if stage:
                    break

            href = link.get('href', '')
            return href, stage, manager

        return '', '', ''

    def _parse_debtor_card(self, html: str) -> Dict:
        """
        Parse the /Debtors/Card page for detailed fields.

        Uses both label-based extraction and full-text regex fallbacks.
        """
        soup = BeautifulSoup(html, 'lxml')
        full_text = soup.get_text(' ')
        result: Dict = {
            'stage': '',
            'manager_name': '',
            'court_name': '',
            'case_number': '',
            'start_date': '',
        }

        # Stage — scan all text
        result['stage'] = _normalize_stage(full_text)

        # Case number (А12-34567/2023 or A12-34567/2023 with latin A)
        m = re.search(r'[АAАа]\d{2}-\d+/\d{4}', full_text)
        if m:
            result['case_number'] = m.group(0)

        # Start date — near keywords дата/введен/открыт
        date_m = re.search(
            r'(?:дата|введен|открыт|начал)[^\n]{0,50}?(\d{2}[./]\d{2}[./]\d{4})',
            full_text, re.IGNORECASE,
        )
        if date_m:
            result['start_date'] = date_m.group(1).replace('/', '.')

        # Arbitration manager — label-based first
        mgr_label = soup.find(string=re.compile(
            r'арбитражный\s+управляющий|арб\.\s*управляющий', re.IGNORECASE
        ))
        if mgr_label:
            container = mgr_label.find_parent()
            if container:
                sibling = container.find_next_sibling()
                if sibling:
                    candidate = sibling.get_text(strip=True)
                    if re.search(r'[А-ЯЁ][а-яё]+\s+[А-ЯЁ]', candidate):
                        result['manager_name'] = candidate[:255]

        if not result['manager_name']:
            mgr_m = re.search(
                r'(?:арбитражный\s+управляющий|управляющий)[:\s]+([А-ЯЁ][а-яёА-ЯЁ\s\-]{5,60})',
                full_text, re.IGNORECASE,
            )
            if mgr_m:
                result['manager_name'] = mgr_m.group(1).strip()[:255]

        # Court name — label-based first
        court_label = soup.find(string=re.compile(r'наименование суда|суд\b', re.IGNORECASE))
        if court_label:
            container = court_label.find_parent()
            if container:
                sibling = container.find_next_sibling()
                if sibling:
                    result['court_name'] = sibling.get_text(strip=True)[:300]

        if not result['court_name']:
            court_m = re.search(
                r'([А-ЯЁ][а-яёА-ЯЁ\s\-]{3,60}арбитражный\s+суд[а-яёА-ЯЁ\s\-]{0,60})',
                full_text, re.IGNORECASE,
            )
            if court_m:
                result['court_name'] = court_m.group(1).strip()[:300]

        return result
