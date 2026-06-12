"""
Adverse-Media Screening (Axis 1 — dirt on the applicant)
========================================================
Surfaces compromising *unstructured* mentions of a person — news articles,
blogs, forums, compromat sites — i.e. the dirt that is NOT in a structured
registry (those are covered by the courts / FSSP / bankruptcy / sanctions
checks). This is the negative-media / "adverse media" layer.

Design (matches the pipeline doctrine):
1. Search via a real search API, never speculative scraping. Provider is
   pluggable; the PRIMARY backend is Yandex XML (Google is blocked in Russia
   and the pipeline runs from the RU VM; Yandex also has better RU/compromat
   coverage). Google CSE remains a fallback for non-RU deployments. One query
   per candidate.
2. DISAMBIGUATION is the whole game. A common ФИО returns mentions of many
   different people, so every hit is gated against what we already know about
   THIS person (birth year, city/region, ИНН-linked company names, ИНН). A hit
   is 'confirmed' only with corroboration; otherwise it is 'possible'
   (однофамилец) and must never be asserted as the applicant's dirt.
3. Status honesty: 'unavailable' (no key) / 'error' / 'blocked' must never read
   as "no adverse media found". Only 'empty' means we actually searched and the
   person turned up clean.

Env: YANDEX_XML_KEY + YANDEX_XML_FOLDERID (primary), or GOOGLE_CSE_KEY +
GOOGLE_CSE_ID (fallback).
"""

import base64
import logging
import os
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import requests

logger = logging.getLogger(__name__)

# Yandex is the PRIMARY backend: Google is blocked in Russia (the pipeline runs
# from the RU VM) and Yandex has better Russian/compromat coverage. Google CSE
# is kept as a fallback for non-RU deployments.
#
# Yandex Search API v2 (AI Studio): POST with an `Authorization: Api-Key <key>`
# header; the response JSON carries the yandexsearch XML base64-encoded in
# `rawData`. Auth = an AI Studio API key (it already has the needed roles) +
# the Cloud folder id. https://searchapi.api.cloud.yandex.net/v2/web/search
YANDEX_SEARCH_URL = 'https://searchapi.api.cloud.yandex.net/v2/web/search'
GOOGLE_CSE_URL = 'https://www.googleapis.com/customsearch/v1'
_TIMEOUT = 25

# Negative-term lexicon, grouped by severity. Deliberately leans toward the
# criminal / reputational dimension that structured registries miss — we do
# NOT lean on financial terms (банкрот/иск/пристав) because FSSP, courts and
# bankruptcy already cover those authoritatively; duplicating them here would
# just add namesake noise.
LEXICON: Dict[str, List[str]] = {
    'criminal': [
        'мошенник', 'мошенничеств', 'уголовн', 'обвиняем', 'обвинён', 'осужд',
        'приговор', 'задержан', 'арестован', 'взятк', 'коррупц', 'хищение',
        'растрат', 'наркотик', 'экстремист', 'террор', 'розыск', 'преступлен',
        'педофил', 'насил', 'вымогательств', 'контрабанд',
    ],
    'reputational': [
        'скандал', 'афер', 'обманул', 'кинул', 'недобросовестн', 'компромат',
        'разоблач', 'фальсификац', 'подделк', 'фиктивн', 'обнал',
    ],
}

# Terms used in the actual search query. Kept short to respect Yandex's ~400-char
# query limit; classification below still scans the FULL lexicon in the results.
_SEARCH_TERMS = LEXICON['criminal'] + ['скандал', 'афер', 'компромат', 'разоблач']


@dataclass
class AdverseMediaHit:
    """One negative mention, with its disambiguation verdict."""
    title: str
    url: str
    snippet: str
    source_domain: str
    severity: str                      # 'criminal' | 'reputational'
    matched_terms: List[str]
    confidence: str                    # 'confirmed' | 'possible'
    corroboration: List[str] = field(default_factory=list)  # why confirmed

    def to_dict(self) -> dict:
        return {
            'title': self.title,
            'url': self.url,
            'snippet': self.snippet,
            'source_domain': self.source_domain,
            'severity': self.severity,
            'matched_terms': self.matched_terms,
            'confidence': self.confidence,
            'corroboration': self.corroboration,
        }


def _provider() -> Optional[str]:
    """Pick the configured search backend. Yandex preferred (Google is blocked
    in Russia); Google CSE is the fallback for non-RU deployments."""
    if os.environ.get('YANDEX_XML_KEY') and os.environ.get('YANDEX_XML_FOLDERID'):
        return 'yandex'
    if os.environ.get('GOOGLE_CSE_KEY') and os.environ.get('GOOGLE_CSE_ID'):
        return 'google'
    return None


def is_available() -> bool:
    """True only if a search backend (Yandex or Google) is configured."""
    return _provider() is not None


def _build_query_google(full_name: str) -> str:
    """Quoted full name + OR-ed negative lexicon (Google syntax)."""
    return f'"{full_name}" ({" OR ".join(_SEARCH_TERMS)})'


def _build_query_yandex(full_name: str) -> str:
    """Quoted full name + |-ed negative lexicon (Yandex query language)."""
    return f'"{full_name}" ({" | ".join(_SEARCH_TERMS)})'


def _google_cse_search(query: str, num: int = 10) -> Tuple[List[dict], str]:
    """One Google CSE call. Returns (items, status).

    status: '' on success, else unavailable/rate_limited/blocked/timeout/error.
    """
    key = os.environ.get('GOOGLE_CSE_KEY')
    cse_id = os.environ.get('GOOGLE_CSE_ID')
    if not key or not cse_id:
        return [], 'unavailable'
    try:
        r = requests.get(GOOGLE_CSE_URL, params={
            'key': key, 'cx': cse_id, 'q': query,
            'num': min(num, 10), 'hl': 'ru', 'lr': 'lang_ru',
        }, timeout=_TIMEOUT)
    except requests.Timeout:
        return [], 'timeout'
    except requests.RequestException as e:
        logger.warning('adverse-media: request failed: %s', e)
        return [], 'error'

    if r.status_code == 429:
        return [], 'rate_limited'           # free 100/day exhausted
    if r.status_code in (401, 403):
        return [], 'blocked'                 # bad/over-quota key
    try:
        data = r.json()
    except ValueError:
        return [], 'error'
    if r.status_code != 200:
        return [], 'error'
    return data.get('items', []) or [], ''


def _parse_yandex_xml(xml_text: str) -> Tuple[List[dict], str]:
    """Parse a yandexsearch XML document into (items, status). Items normalized
    to {title, snippet, link}. A <error code=..> body maps to empty/rate_limited/
    blocked so failures never read as 'clean'."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return [], 'error'

    err = root.find('.//error')
    if err is not None:
        code = err.get('code')
        if code in ('15', '55'):            # nothing found
            return [], 'empty'
        if code in ('32', '33'):            # query / IP limit reached
            return [], 'rate_limited'
        logger.warning('adverse-media: yandex error %s: %s', code, err.text or '')
        return [], 'blocked'                # bad key / folder / config

    items = []
    for doc in root.findall('.//doc'):
        url = (doc.findtext('url') or '').strip()
        title_el = doc.find('title')
        title = ''.join(title_el.itertext()).strip() if title_el is not None else ''
        passages_el = doc.find('.//passages')
        snippet = ''
        if passages_el is not None:
            snippet = ' '.join(
                ''.join(p.itertext()) for p in passages_el.findall('passage')
            ).strip()
        if url:
            items.append({'title': title, 'snippet': snippet, 'link': url})
    return items, ''


def _yandex_search(query: str) -> Tuple[List[dict], str]:
    """One Yandex Search API v2 (synchronous, XML) call. Returns (items, status)
    normalized to {title, snippet, link}. The response JSON carries the
    yandexsearch XML base64-encoded in `rawData`."""
    key = os.environ.get('YANDEX_XML_KEY')
    folderid = os.environ.get('YANDEX_XML_FOLDERID')
    if not key or not folderid:
        return [], 'unavailable'
    body = {
        'query': {
            'searchType': 'SEARCH_TYPE_RU',
            'queryText': query,
            'familyMode': 'FAMILY_MODE_NONE',
        },
        'groupSpec': {
            'groupMode': 'GROUP_MODE_FLAT', 'groupsOnPage': 10, 'docsInGroup': 1,
        },
        'responseFormat': 'FORMAT_XML',
        'folderId': folderid,
    }
    try:
        r = requests.post(
            YANDEX_SEARCH_URL,
            headers={'Authorization': f'Api-Key {key}'},
            json=body, timeout=_TIMEOUT,
        )
    except requests.Timeout:
        return [], 'timeout'
    except requests.RequestException as e:
        logger.warning('adverse-media: yandex request failed: %s', e)
        return [], 'error'

    if r.status_code in (401, 403):
        return [], 'blocked'
    if r.status_code == 429:
        return [], 'rate_limited'
    if r.status_code != 200:
        return [], 'error'
    try:
        raw = (r.json() or {}).get('rawData')
    except ValueError:
        return [], 'error'
    if not raw:
        return [], 'error'
    try:
        xml_text = base64.b64decode(raw).decode('utf-8', 'replace')
    except (ValueError, TypeError):
        return [], 'error'
    return _parse_yandex_xml(xml_text)


def _run_search(full_name: str) -> Tuple[List[dict], str]:
    """Dispatch to the configured provider. Items normalized to {title,snippet,link}."""
    provider = _provider()
    if provider == 'yandex':
        return _yandex_search(_build_query_yandex(full_name))
    if provider == 'google':
        return _google_cse_search(_build_query_google(full_name))
    return [], 'unavailable'


def _domain(url: str) -> str:
    m = re.match(r'https?://([^/]+)', url or '')
    return (m.group(1).lower().replace('www.', '') if m else '')


def _classify_terms(text: str) -> Tuple[str, List[str]]:
    """Return (severity, matched_terms) for the text. Criminal wins over
    reputational when both are present."""
    low = text.lower()
    crim = [t for t in LEXICON['criminal'] if t in low]
    rep = [t for t in LEXICON['reputational'] if t in low]
    if crim:
        return 'criminal', crim + rep
    if rep:
        return 'reputational', rep
    return '', []


def _disambiguate(text: str, context: dict) -> Tuple[str, List[str]]:
    """Decide if a mention is about THIS person.

    Returns (confidence, corroboration). 'confirmed' requires at least one
    strong corroborator from the known context (ИНН, an ИНН-linked company
    name, or the birth year); city/region alone is supporting but not, by
    itself, enough (cities are shared by many namesakes). Everything else is
    'possible' (однофамилец) — never asserted as the applicant's.
    """
    low = text.lower()
    evidence: List[str] = []

    for inn in context.get('inns', []) or []:
        if inn and inn in text:
            evidence.append(f'ИНН {inn}')

    for company in context.get('companies', []) or []:
        c = (company or '').strip().lower()
        if len(c) >= 5 and c in low:
            evidence.append(f'компания «{company}»')

    birth_year = context.get('birth_year')
    if birth_year and str(birth_year) in text:
        evidence.append(f'{birth_year} г.р.')

    strong = bool(evidence)

    city = (context.get('city') or '').strip().lower()
    city_hit = bool(city) and len(city) >= 4 and city in low
    if city_hit:
        evidence.append(f'город {context["city"]}')

    # Confirmed only with a strong corroborator (INN / company / birth year).
    # A city match supports but cannot confirm on its own.
    return ('confirmed' if strong else 'possible'), evidence


def search_adverse_media(
    full_name: str,
    context: Optional[dict] = None,
) -> Tuple[List[AdverseMediaHit], str]:
    """Screen for adverse media about a person.

    Args:
        full_name: "Фамилия Имя Отчество".
        context: disambiguation context — keys: inns (list[str]),
            companies (list[str]), birth_year (int|str), city (str).

    Returns:
        (hits, status). status: 'ok' (confirmed/possible hits found) /
        'empty' (searched, nothing) / 'unavailable' (no key) / 'rate_limited' /
        'blocked' / 'timeout' / 'error' / 'skipped' (bad name).
        Non-ok/empty must never render as "no adverse media".
    """
    context = context or {}
    if not full_name or len(full_name.strip().split()) < 2:
        return [], 'skipped'

    items, err = _run_search(full_name)
    if err:
        return [], err

    name_tokens = [t.lower() for t in full_name.strip().split() if len(t) > 2]
    hits: List[AdverseMediaHit] = []
    for item in items:
        title = item.get('title', '') or ''
        snippet = item.get('snippet', '') or ''
        url = item.get('link', '') or ''
        text = f'{title}\n{snippet}'
        low = text.lower()

        # The surname (first token) must appear — guards against CSE returning
        # loosely-related pages that don't actually name the person.
        if name_tokens and name_tokens[0] not in low:
            continue

        severity, matched = _classify_terms(text)
        if not matched:
            continue  # no negative term actually present in the result text

        confidence, corroboration = _disambiguate(text, context)
        hits.append(AdverseMediaHit(
            title=title, url=url, snippet=snippet, source_domain=_domain(url),
            severity=severity, matched_terms=matched,
            confidence=confidence, corroboration=corroboration,
        ))

    return hits, ('ok' if hits else 'empty')
