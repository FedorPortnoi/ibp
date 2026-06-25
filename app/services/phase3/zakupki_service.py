"""
Госзакупки (EIS Zakupki) — contact phone/email lookup by INN
=============================================================
Searches zakupki.gov.ru for government contracts by supplier INN,
then extracts the supplier's contact phone and email from each
contract card (public filing, no auth required).

This is the primary free path to a candidate's phone number when
they are an ИП or company director who participated in госзакупки.
The contact person's phone/email are mandatory fields in contract
filing — they appear publicly in the "Сведения о поставщике" section.
"""

import logging
import re
import time
from typing import Dict, List

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_BASE = 'https://zakupki.gov.ru'
_SEARCH_URL = f'{_BASE}/epz/contract/search/results.html'
_CARD_URL = f'{_BASE}/epz/contract/contractCard/commonInfo.html'

_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
    ),
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'ru-RU,ru;q=0.9',
    'Referer': _BASE,
}

_PHONE_RE = re.compile(
    r'(?:\+7|8)[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}'
)
_EMAIL_RE = re.compile(
    r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}'
)
_REESTR_RE = re.compile(r'\b\d{19,20}\b')

_TIMEOUT = 15
_MAX_CONTRACTS = 3


def _normalize_phone(raw: str) -> str:
    digits = re.sub(r'\D', '', raw)
    if len(digits) == 11 and digits[0] in ('7', '8'):
        return '+7' + digits[1:]
    if len(digits) == 10:
        return '+7' + digits
    return raw


def _get_contract_numbers(inn: str, session: requests.Session) -> List[str]:
    try:
        resp = session.get(
            _SEARCH_URL,
            params={
                'supplierInn': inn,
                'morphology': 'on',
                'fz44': 'on',
                'fz223': 'on',
                'search-filter': 'Дата+заключения',
            },
            timeout=_TIMEOUT,
        )
        if resp.status_code != 200:
            logger.warning('zakupki: search HTTP %d for INN %s', resp.status_code, inn)
            return []

        numbers: List[str] = []
        # Primary: links with reestrNumber= in href
        soup = BeautifulSoup(resp.text, 'lxml')
        for link in soup.select('a[href*="reestrNumber="]'):
            m = re.search(r'reestrNumber=(\d+)', link.get('href', ''))
            if m and m.group(1) not in numbers:
                numbers.append(m.group(1))
        # Fallback: 19-20 digit strings anywhere on the page
        if not numbers:
            for m in _REESTR_RE.finditer(resp.text):
                if m.group() not in numbers:
                    numbers.append(m.group())

        logger.info('zakupki: INN %s → %d contract numbers found', inn, len(numbers))
        return numbers
    except Exception as exc:
        logger.warning('zakupki: search error for INN %s: %s', inn, exc)
        return []


def _extract_contacts_from_card(reestr_number: str, session: requests.Session) -> Dict:
    try:
        resp = session.get(
            _CARD_URL,
            params={'reestrNumber': reestr_number},
            timeout=_TIMEOUT,
        )
        if resp.status_code != 200:
            return {}
        html = resp.text
        phones = list({
            _normalize_phone(m) for m in _PHONE_RE.findall(html)
        })
        emails = list({
            m.lower() for m in _EMAIL_RE.findall(html)
            if not m.lower().endswith(('.png', '.jpg', '.gif', '.svg', '.ico'))
            and 'zakupki.gov.ru' not in m.lower()
            and 'gosuslugi' not in m.lower()
        })
        return {'phones': phones, 'emails': emails}
    except Exception as exc:
        logger.warning('zakupki: card error for %s: %s', reestr_number, exc)
        return {}


def lookup_contacts_by_inn(inn: str) -> Dict:
    """
    Find phone/email for a supplier by INN via госзакупки contract filings.

    Returns:
        {
            'phones': ['+79161234567', ...],
            'emails': ['person@company.ru', ...],
            'contracts_checked': N,
            'source': 'zakupki.gov.ru',
            'status': 'ok' | 'empty' | 'error' | 'skipped',
        }
    """
    empty = {
        'phones': [], 'emails': [], 'contracts_checked': 0,
        'source': 'zakupki.gov.ru', 'status': 'empty',
    }
    if not inn:
        return {**empty, 'status': 'skipped'}

    session = requests.Session()
    session.headers.update(_HEADERS)
    try:
        all_numbers = _get_contract_numbers(inn, session)
        total_found = len(all_numbers)
        numbers = all_numbers[:_MAX_CONTRACTS]
        if not numbers:
            return {**empty, 'contracts_found': 0}

        all_phones: set = set()
        all_emails: set = set()
        for i, number in enumerate(numbers):
            contacts = _extract_contacts_from_card(number, session)
            all_phones.update(contacts.get('phones', []))
            all_emails.update(contacts.get('emails', []))
            if i < len(numbers) - 1:
                time.sleep(0.5)

        phones = sorted(all_phones)
        emails = sorted(all_emails)
        logger.info(
            'zakupki: INN %s → %d phones, %d emails (checked %d contracts)',
            inn, len(phones), len(emails), len(numbers),
        )
        return {
            'phones': phones,
            'emails': emails,
            'contracts_checked': len(numbers),
            'contracts_found': total_found,
            'source': 'zakupki.gov.ru',
            'status': 'ok' if (phones or emails) else 'empty',
        }
    except Exception as exc:
        logger.error('zakupki: unexpected error for INN %s: %s', inn, exc)
        return {**empty, 'status': 'error'}
    finally:
        session.close()
