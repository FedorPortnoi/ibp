"""
reputation.su — Russian court case aggregator (58M+ cases).
============================================================
SSR search page at /search?query={name} returns Nuxt 3 HTML
with court case cards (div.srch-card__affairs-box).

Key: use ``query=`` parameter (not ``q=``). ``q=`` returns
unfiltered results identical for every query.

No authentication required. Cloudflare bot protection is present —
plain requests return a JS challenge page ("Click to continue") from
non-Russian IPs. Works reliably from Yandex Cloud VM (Russian IP).
Same geo pattern as судебныерешения.рф.

A challenge page comes back as HTTP 200 with no case cards, so it is
indistinguishable from "person has no court cases" unless detected
explicitly. search_reputation_su therefore returns (cases, status):
'blocked' means the source was NOT readable and zero cases proves
nothing — callers must never present it as a clean record.
"""

import logging
import re
import time
from typing import List, Tuple
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup
from app.services.shared.court_utils import COURT_CATEGORY_MAP, get_li_value

logger = logging.getLogger(__name__)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
}

# Bot-wall fingerprints (Cloudflare / DDoS-Guard interstitials).
_BLOCK_MARKERS = (
    'click to continue',
    'just a moment',
    'checking your browser',
    'cf-browser-verification',
    'cf-challenge',
    '__cf_chl',
    'ddos-guard',
    'ddg-l7',
)

# A real reputation.su page is a Nuxt SSR document well over 50KB even for
# zero results. The observed Cloudflare challenge is ~1.2KB. Anything this
# small cannot be a valid results page.
_MIN_VALID_PAGE_BYTES = 2048

# Deep parse limits: each detail fetch costs an HTTP round-trip + 0.5s sleep.
_DEEP_PARSE_MAX_FETCHES = 8
_DEEP_PARSE_MAX_CONSECUTIVE_FAILURES = 3
_DETAIL_TIMEOUT = 10

# Deep-parse priority: criminal verdicts/articles are what the dossier needs
# most; civil cases rarely contain УК РФ data worth a round-trip.
_DEEP_PARSE_PRIORITY = {'уголовное': 0, 'административное': 1}


def _is_blocked_page(html: str, size_heuristic: bool = True) -> bool:
    """True if the response is a bot-wall interstitial, not a results page.

    ``size_heuristic`` applies to SEARCH pages only (a real Nuxt results page
    is large even with zero cards). Detail pages pass ``size_heuristic=False``
    — there only explicit bot-wall markers count, because a short legitimate
    detail page must not be discarded.
    """
    if not html:
        return False
    lowered = html.lower()
    if any(marker in lowered for marker in _BLOCK_MARKERS):
        return True
    # Tiny 200-response without any case cards: interstitial or proxy stub —
    # either way not a readable results page.
    if size_heuristic and len(html) < _MIN_VALID_PAGE_BYTES and 'srch-card' not in lowered:
        return True
    return False

# Category label -> case_type



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
        category = get_li_value(card, 'Категория').lower()
        case_type = COURT_CATEGORY_MAP.get(category, '')

        # Date from "Регистрация"
        date_text = get_li_value(card, 'Регистрация')
        date = ''
        date_m = re.search(r'(\d{2}\.\d{2}\.\d{4})', date_text)
        if date_m:
            date = date_m.group(1)

        # Status
        status = get_li_value(card, 'Статус')

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

        # Court name — try multiple label strategies
        court_name = get_li_value(card, 'Суд')
        if not court_name:
            for label in ('Наименование суда', 'Судебный орган', 'Наименование'):
                court_name = get_li_value(card, label)
                if court_name:
                    break
        # Regex fallback from full card text
        if not court_name:
            card_text = card.get_text(' ', strip=True)
            court_patterns = [
                r'([А-ЯЁ][а-яёА-ЯЁ\s\-]{3,80}(?:районный\s+суд|городской\s+суд|краевой\s+суд|областной\s+суд|верховный\s+суд|арбитражный\s+суд|мировой\s+суд)[а-яёА-ЯЁ\s\-]{0,60})',
                r'([А-ЯЁ][а-яёА-ЯЁ\s\-]{3,80}суд[а-яёА-ЯЁ\s\-]{0,60})',
            ]
            for pattern in court_patterns:
                m = re.search(pattern, card_text, re.IGNORECASE)
                if m:
                    court_name = m.group(1).strip()[:200]
                    break
        if not court_name:
            court_name = 'Суд не определён'

        # Subject (предмет дела) — from "Предмет" label or description block
        subject = get_li_value(card, 'Предмет')
        if not subject:
            for label in ('Суть дела', 'Описание', 'Иск о'):
                subject = get_li_value(card, label)
                if subject:
                    break
        if not subject:
            desc = card.select_one(
                'p.srch-card__description, p.srch-card__subject, '
                '.case-description, .case-subject, p.description'
            )
            if desc:
                subject = desc.get_text(strip=True)[:300]

        if case_number in seen_numbers:
            continue
        seen_numbers.add(case_number)

        logger.debug(
            f"[REPUTATION] case {case_number}: court='{court_name}', "
            f"subject='{(subject or '')[:50]}'"
        )

        cases.append({
            'case_number': case_number,
            'court_name': court_name,
            'case_type': case_type,
            'date': date,
            'role': role,
            'status': status,
            'subject': subject,
            'url': url,
            'source': 'reputation.su',
        })

    return cases


def _extract_criminal_articles(text: str) -> list:
    """Extract criminal code articles (УК РФ) mentions from court case text.

    Returns a list of unique string mentions (e.g. ``ч.2 ст.228 УК РФ``).
    """
    if not text:
        return []
    patterns = [
        r'п\.\s*[а-я«»"\']+\s*ч\.\s*\d+\s*ст\.\s*\d+(?:\.\d+)?\s*УК\s*РФ',
        r'ч\.\s*\d+\s*ст\.\s*\d+(?:\.\d+)?\s*УК\s*РФ',
        r'ст\.\s*\d+(?:\.\d+)?\s*УК\s*РФ',
        r'осуждён[а]?\s+по\s+ст\.\s*\d+(?:\.\d+)?',
        r'признан[а]?\s+виновн(?:ым|ой)\s+по\s+ч\.\s*\d+\s*ст\.\s*\d+(?:\.\d+)?',
    ]
    found = []
    for p in patterns:
        for m in re.finditer(p, text, re.IGNORECASE):
            art = m.group(0).strip()
            if art not in found:
                found.append(art)
    return found


def _fetch_reputation_case_details(
    url: str, session: requests.Session, timeout: int = _DETAIL_TIMEOUT,
) -> str:
    """Fetch a reputation.su case detail page and return its text body.

    Uses the caller's session (cookie continuity matters under Cloudflare).
    Returns an empty string on any error or bot-wall page — never raises.
    """
    if not url:
        return ""
    try:
        resp = session.get(url, timeout=timeout)
        if resp.status_code == 200:
            if _is_blocked_page(resp.text, size_heuristic=False):
                logger.debug(f"[REPUTATION] detail fetch blocked for {url}")
                return ""
            soup = BeautifulSoup(resp.text, 'lxml')
            for tag in soup(['script', 'style', 'nav', 'header', 'footer']):
                tag.decompose()
            return soup.get_text(separator=' ', strip=True)[:5000]
        logger.debug(f"[REPUTATION] detail fetch HTTP {resp.status_code} for {url}")
    except Exception as e:
        logger.debug(f"[REPUTATION] detail fetch failed for {url}: {e}")
    return ""


def _deep_parse_records(
    records: list,
    session: requests.Session,
    max_fetches: int = _DEEP_PARSE_MAX_FETCHES,
) -> None:
    """Second-pass: visit case URLs and enrich with criminal_articles + verdict.

    Mutates ``records`` in-place. Bounded so a common name with a wall of
    civil cases can't burn the pipeline's time budget:
    - criminal cases first, then administrative, then the rest (stable order)
    - at most ``max_fetches`` detail requests per search
    - aborts after 3 consecutive failed fetches (site blocking detail pages)
    Records beyond the budget keep their card-level data.
    """
    verdict_patterns = [
        r'(лишение свободы[^.]{0,100})',
        r'(условн[ыо][йе][^.]{0,80})',
        r'(штраф[^.]{0,80})',
        r'(исправительн[^.]{0,80}работ[^.]{0,50})',
    ]

    candidates = [
        r for r in records
        if r.get('url') and not r.get('criminal_articles')
    ]
    candidates.sort(
        key=lambda r: _DEEP_PARSE_PRIORITY.get(r.get('case_type', ''), 2)
    )

    fetches = 0
    consecutive_failures = 0
    for record in candidates:
        if fetches >= max_fetches:
            logger.debug(
                f"[REPUTATION] deep parse budget ({max_fetches}) exhausted, "
                f"{len(candidates) - fetches} cases keep card-level data only"
            )
            break
        if consecutive_failures >= _DEEP_PARSE_MAX_CONSECUTIVE_FAILURES:
            logger.warning(
                "[REPUTATION] deep parse aborted: "
                f"{consecutive_failures} consecutive fetch failures"
            )
            break

        time.sleep(0.5)
        fetches += 1
        detail_text = _fetch_reputation_case_details(record['url'], session)
        if not detail_text:
            consecutive_failures += 1
            continue
        consecutive_failures = 0

        record['criminal_articles'] = _extract_criminal_articles(detail_text)
        for vp in verdict_patterns:
            m = re.search(vp, detail_text, re.IGNORECASE)
            if m:
                record['verdict'] = m.group(1).strip()[:200]
                break
        logger.debug(
            f"[REPUTATION] {record.get('case_number')}: "
            f"articles={record.get('criminal_articles')}, "
            f"verdict={(record.get('verdict') or '')[:60]}"
        )


def search_reputation_su(full_name: str, timeout: int = 20) -> Tuple[List[dict], str]:
    """Search reputation.su for court cases involving a person.

    Args:
        full_name: Full name in Russian (e.g. "Иванов Иван Иванович")
        timeout: HTTP request timeout in seconds

    Returns:
        (cases, status). Cases are dicts with keys: case_number, court_name,
        case_type, date, role, status, subject, url, source (+
        criminal_articles/verdict from deep parse).

        Status is one of:
        - 'ok'         — page read, >=1 case parsed
        - 'empty'      — page read, genuinely no cases for this name
        - 'blocked'    — bot-wall page (Cloudflare/DDoS-Guard); the source was
                         NOT readable, zero cases proves nothing
        - 'http_error' — non-200 response
        - 'timeout'    — request timed out
        - 'error'      — network or unexpected failure
        - 'skipped'    — empty input, source not queried
    """
    if not full_name or not full_name.strip():
        return [], 'skipped'

    name = full_name.strip()
    # IMPORTANT: use ``query=`` not ``q=`` — the latter returns unfiltered results
    url = f'https://reputation.su/search?query={quote(name)}'
    logger.info(f"reputation.su: searching for '{name}'")

    session = requests.Session()
    session.headers.update(HEADERS)
    try:
        resp = session.get(url, timeout=timeout)
        logger.debug(f"reputation.su: HTTP {resp.status_code}, {len(resp.text)} bytes")

        if resp.status_code != 200:
            logger.warning(f"reputation.su: unexpected status {resp.status_code}")
            return [], 'http_error'

        if _is_blocked_page(resp.text):
            logger.warning(
                f"reputation.su: bot-wall page detected ({len(resp.text)} bytes) "
                f"— source blocked, NOT a clean record"
            )
            return [], 'blocked'

        cases = _parse_cards(resp.text, name)
        logger.info(f"reputation.su: found {len(cases)} cases for '{name}'")

        # Deep parse: visit case URLs and extract criminal_articles + verdict
        if cases:
            try:
                _deep_parse_records(cases, session)
            except Exception as e:
                logger.warning(f"reputation.su: deep parse failed: {e}")

        return cases, ('ok' if cases else 'empty')

    except requests.Timeout:
        logger.warning(f"reputation.su: timeout after {timeout}s for '{name}'")
        return [], 'timeout'
    except requests.RequestException as e:
        logger.warning(f"reputation.su: request failed: {e}")
        return [], 'error'
    except Exception as e:
        logger.error(f"reputation.su: unexpected error: {e}")
        return [], 'error'
    finally:
        session.close()
