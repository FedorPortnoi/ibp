"""
reputation.su — Russian court case aggregator (58M+ cases).
============================================================
SSR search page at /search?query={name} returns Nuxt 3 HTML
with court case cards (div.srch-card__affairs-box).

Key: use ``query=`` parameter (not ``q=``). ``q=`` returns
unfiltered results identical for every query.

No authentication required. No geo-blocking. Plain requests work.
"""

import logging
import re
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
}

# Category label -> case_type
_CATEGORY_MAP = {
    'гражданские': 'гражданское',
    'уголовные': 'уголовное',
    'административные': 'административное',
    'арбитражные': 'арбитражное',
}


def _get_li_value(card, label: str) -> str:
    """Extract the <p> text from a <li> whose <span> matches label."""
    for li in card.select('li'):
        span = li.select_one('span')
        if span and label in span.get_text(strip=True):
            p = li.select_one('p')
            return p.get_text(strip=True) if p else ''
    return ''


def _detect_role(card, search_name: str) -> str:
    """Determine the searched person's role from card participant lists."""
    name_lower = search_name.lower().strip()
    name_parts = name_lower.split()
    # Build match variants: full name, last+first
    variants = [name_lower]
    if len(name_parts) >= 2:
        variants.append(f"{name_parts[0]} {name_parts[1]}")

    role_map = {
        'Истцы': 'истец',
        'Ответчики': 'ответчик',
        'Другие участники': 'третье лицо',
    }

    for li in card.select('li'):
        span = li.select_one('span')
        if not span:
            continue
        span_text = span.get_text(strip=True)

        for label, role in role_map.items():
            if label in span_text:
                # Check if any participant name matches
                participants = li.select('p.srch-rp-card__company')
                li_text = li.get_text(' ', strip=True).lower()
                for variant in variants:
                    if variant in li_text:
                        return role
                    for p in participants:
                        if variant in p.get_text(strip=True).lower():
                            return role

    return 'участник'


def _parse_cards(html: str, search_name: str) -> list:
    """Parse srch-card__affairs-box elements from reputation.su HTML."""
    soup = BeautifulSoup(html, 'lxml')
    cases = []

    cards = soup.select('div.srch-card__affairs-box')
    if not cards:
        logger.debug("reputation.su: no srch-card__affairs-box found")
        return cases

    seen_numbers = set()
    for card in cards[:20]:
        # Case number from <h3>
        h3 = card.select_one('h3')
        if not h3:
            continue
        case_number_raw = h3.get_text(strip=True)
        # Extract clean case number (e.g. "2-63/2017" from "2-63/2017 (2-1163/2016;) ~ М-1229/2016")
        m = re.match(r'(\d{1,2}[А-Яа-я]{0,3}-\d+/\d{4})', case_number_raw)
        case_number = m.group(1) if m else case_number_raw

        # Category -> case_type
        category = _get_li_value(card, 'Категория').lower()
        case_type = _CATEGORY_MAP.get(category, '')

        # Date from "Регистрация"
        date_text = _get_li_value(card, 'Регистрация')
        date = ''
        date_m = re.search(r'(\d{2}\.\d{2}\.\d{4})', date_text)
        if date_m:
            date = date_m.group(1)

        # Status
        status = _get_li_value(card, 'Статус')

        # Role
        role = _detect_role(card, search_name)

        # URL from "Посмотреть дело" link — must be /sudrf/{numeric_id},
        # NOT /sudrf/participant?... which is a different page
        url = ''
        for a in card.select('a[href*="/sudrf/"]'):
            href = a.get('href', '')
            if '/participant' not in href:
                url = f'https://reputation.su{href}' if href.startswith('/') else href
                break

        if case_number in seen_numbers:
            continue
        seen_numbers.add(case_number)

        cases.append({
            'case_number': case_number,
            'court_name': '',
            'case_type': case_type,
            'date': date,
            'role': role,
            'status': status,
            'url': url,
            'source': 'reputation.su',
        })

    return cases


def search_reputation_su(full_name: str, timeout: int = 20) -> list:
    """Search reputation.su for court cases involving a person.

    Args:
        full_name: Full name in Russian (e.g. "Иванов Иван Иванович")
        timeout: HTTP request timeout in seconds

    Returns:
        List of court case dicts with keys:
        case_number, court_name, case_type, date, role, status, url, source
    """
    if not full_name or not full_name.strip():
        return []

    name = full_name.strip()
    # IMPORTANT: use ``query=`` not ``q=`` — the latter returns unfiltered results
    url = f'https://reputation.su/search?query={quote(name)}'
    logger.info(f"reputation.su: searching for '{name}'")

    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout)
        logger.debug(f"reputation.su: HTTP {resp.status_code}, {len(resp.text)} bytes")

        if resp.status_code != 200:
            logger.warning(f"reputation.su: unexpected status {resp.status_code}")
            return []

        cases = _parse_cards(resp.text, name)
        logger.info(f"reputation.su: found {len(cases)} cases for '{name}'")
        return cases

    except requests.Timeout:
        logger.warning(f"reputation.su: timeout after {timeout}s for '{name}'")
    except requests.RequestException as e:
        logger.warning(f"reputation.su: request failed: {e}")
    except Exception as e:
        logger.error(f"reputation.su: unexpected error: {e}")

    return []
