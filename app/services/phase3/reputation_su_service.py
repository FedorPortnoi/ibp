"""
reputation.su — Russian court case aggregator (58M+ cases).
============================================================
Uses the SSR search page at /search?q={name} and parses
the embedded __NUXT_DATA__ JSON payload for structured results.

No authentication required. No geo-blocking. Plain requests work.
"""

import json
import logging
import re
from typing import List, Dict
from urllib.parse import quote

import requests

logger = logging.getLogger(__name__)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
}

# Mapping for ProceedingType -> Russian case type
_PROCEEDING_MAP = {
    'Civil': 'гражданское',
    'Administrative': 'административное',
    'Criminal': 'уголовное',
    'Arbitr': 'арбитражное',
}

# Mapping for ParticipationType -> Russian role
_ROLE_MAP = {
    'Defendant': 'ответчик',
    'Plaintiff': 'истец',
    'ThirdParty': 'третье лицо',
    'Other': 'участник',
}


def _parse_nuxt_data(html: str) -> list:
    """Extract items from Nuxt 3 __NUXT_DATA__ payload.

    Nuxt 3 serializes data as JSON arrays in <script> tags with
    type="application/json" and an id like "__NUXT_DATA__" or similar.
    The format uses index references — each entry may be a primitive
    or reference other entries by index.
    """
    # Try to find the Nuxt data script tag
    # Nuxt 3 uses: <script type="application/json" data-ssr="true" id="__NUXT_DATA__:app:default">
    pattern = r'<script[^>]*id="__NUXT_DATA__[^"]*"[^>]*>(.*?)</script>'
    matches = re.findall(pattern, html, re.DOTALL)

    if not matches:
        # Alternative: look for window.__NUXT__ pattern
        pattern2 = r'window\.__NUXT__\s*=\s*({.*?})\s*;?\s*</script>'
        matches = re.findall(pattern2, html, re.DOTALL)

    if not matches:
        logger.debug("reputation.su: no __NUXT_DATA__ found in HTML")
        return []

    items = []
    for raw_data in matches:
        try:
            data = json.loads(raw_data)
        except (json.JSONDecodeError, ValueError):
            continue

        if isinstance(data, list):
            items.extend(_extract_cases_from_nuxt_array(data))
        elif isinstance(data, dict):
            items.extend(_extract_cases_from_dict(data))

    return items


def _extract_cases_from_nuxt_array(arr: list) -> list:
    """Extract court case records from Nuxt 3 indexed array format.

    Nuxt 3 __NUXT_DATA__ is a flat array where objects reference
    other elements by index. We scan for case number patterns and
    reconstruct records from surrounding entries.
    """
    cases = []

    # Strategy: find all strings that look like case numbers
    # Russian case numbers: digits-digits/year (e.g. "2-1234/2025")
    case_num_re = re.compile(r'^\d{1,2}[А-Яа-я]{0,3}-\d+/\d{4}$')

    for i, val in enumerate(arr):
        if not isinstance(val, str):
            continue
        if not case_num_re.match(val):
            continue

        # Found a case number. Look around for related data.
        case = {'case_number': val, 'source': 'reputation.su'}

        # Scan nearby entries for date, court name, status, proceeding type
        window = arr[max(0, i - 15):i + 15]
        for nearby in window:
            if not isinstance(nearby, str):
                continue
            if nearby == val:
                continue

            # Date pattern: YYYY-MM-DD
            if re.match(r'^\d{4}-\d{2}-\d{2}$', nearby):
                if 'date' not in case:
                    case['date'] = nearby
            # Proceeding type
            elif nearby in _PROCEEDING_MAP:
                case['case_type'] = _PROCEEDING_MAP[nearby]
            # Role
            elif nearby in _ROLE_MAP:
                if 'role' not in case:
                    case['role'] = _ROLE_MAP[nearby]
            # Status (Russian text with date in parens)
            elif re.match(r'^[А-Яа-я].*\(\d{2}\.\d{2}\.\d{4}\)$', nearby):
                case['status'] = nearby
            # Court name (contains "суд" or "судья" or "участок")
            elif any(kw in nearby.lower() for kw in ['суд', 'судья', 'участок']):
                if 'court_name' not in case:
                    case['court_name'] = nearby

        # Look for NumericId (integer) near the case number
        for j in range(max(0, i - 10), min(len(arr), i + 10)):
            if isinstance(arr[j], int) and arr[j] > 100000:
                case['url'] = f'https://reputation.su/sudrf/{arr[j]}'
                break

        if not case.get('court_name'):
            case['court_name'] = ''

        cases.append(case)

    return cases


def _extract_cases_from_dict(data: dict) -> list:
    """Extract cases from a window.__NUXT__ style dict."""
    cases = []

    # Navigate to the items array
    def _find_items(obj, depth=0):
        if depth > 5:
            return []
        found = []
        if isinstance(obj, dict):
            if 'Number' in obj and 'Participants' in obj:
                found.append(obj)
            for v in obj.values():
                found.extend(_find_items(v, depth + 1))
        elif isinstance(obj, list):
            for item in obj:
                found.extend(_find_items(item, depth + 1))
        return found

    raw_items = _find_items(data)
    for item in raw_items:
        case = {
            'case_number': item.get('Number', ''),
            'court_name': item.get('CourtName', ''),
            'date': item.get('Date', ''),
            'case_type': _PROCEEDING_MAP.get(item.get('ProceedingType', ''), ''),
            'status': item.get('Status', ''),
            'source': 'reputation.su',
            'url': f"https://reputation.su/sudrf/{item['NumericId']}"
                   if item.get('NumericId') else '',
        }

        # Determine role from Participants
        participants = item.get('Participants', [])
        for p in participants:
            ptype = p.get('ParticipationType', '')
            if ptype in _ROLE_MAP:
                case['role'] = _ROLE_MAP[ptype]
                break

        cases.append(case)

    return cases


def _parse_html_results(html: str) -> list:
    """Fallback: parse SSR-rendered HTML for court case data."""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return []

    soup = BeautifulSoup(html, 'lxml')
    cases = []
    case_num_re = re.compile(r'\d{1,2}[А-Яа-я]{0,3}-\d+/\d{4}')

    # Try common Nuxt/Vue result selectors
    for selector in ['.case-card', '.search-result', 'article', '.card',
                     '[class*="case"]', '[class*="result"]']:
        items = soup.select(selector)
        if not items or len(items) < 1:
            continue

        for item in items[:20]:
            text = item.get_text(' ', strip=True)
            m = case_num_re.search(text)
            if not m:
                continue

            link = item.select_one('a[href*="/sudrf/"]')
            url = ''
            if link:
                href = link.get('href', '')
                url = f'https://reputation.su{href}' if href.startswith('/') else href

            case = {
                'case_number': m.group(0),
                'court_name': '',
                'source': 'reputation.su',
                'url': url,
            }

            # Try to extract date
            date_m = re.search(r'(\d{2}\.\d{2}\.\d{4})', text)
            if date_m:
                case['date'] = date_m.group(1)

            cases.append(case)

        if cases:
            break

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
    url = f'https://reputation.su/search?q={quote(name)}'
    logger.info(f"reputation.su: searching for '{name}'")

    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout)
        logger.debug(f"reputation.su: HTTP {resp.status_code}, {len(resp.text)} bytes")

        if resp.status_code != 200:
            logger.warning(f"reputation.su: unexpected status {resp.status_code}")
            return []

        # Primary: parse __NUXT_DATA__
        cases = _parse_nuxt_data(resp.text)

        # Fallback: parse SSR HTML
        if not cases:
            cases = _parse_html_results(resp.text)

        logger.info(f"reputation.su: found {len(cases)} cases for '{name}'")
        return cases[:20]  # Cap at 20

    except requests.Timeout:
        logger.warning(f"reputation.su: timeout after {timeout}s for '{name}'")
    except requests.RequestException as e:
        logger.warning(f"reputation.su: request failed: {e}")
    except Exception as e:
        logger.error(f"reputation.su: unexpected error: {e}")

    return []
