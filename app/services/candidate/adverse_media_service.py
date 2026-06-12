"""
Adverse-Media Screening (Axis 1 — dirt on the applicant)
========================================================
Surfaces compromising *unstructured* mentions of a person — news articles,
blogs, forums, compromat sites — i.e. the dirt that is NOT in a structured
registry (those are covered by the courts / FSSP / bankruptcy / sanctions
checks). This is the negative-media / "adverse media" layer.

Design (matches the pipeline doctrine):
1. Search via a real search API, never speculative scraping. Provider is
   pluggable; the free default is Google Programmable Search (CSE), one query
   per candidate to stay inside the free 100/day tier. A Yandex adapter can be
   dropped in later for deeper Russian/compromat coverage.
2. DISAMBIGUATION is the whole game. A common ФИО returns mentions of many
   different people, so every hit is gated against what we already know about
   THIS person (birth year, city/region, ИНН-linked company names, ИНН). A hit
   is 'confirmed' only with corroboration; otherwise it is 'possible'
   (однофамилец) and must never be asserted as the applicant's dirt.
3. Status honesty: 'unavailable' (no key) / 'error' / 'blocked' must never read
   as "no adverse media found". Only 'empty' means we actually searched and the
   person turned up clean.

Env: GOOGLE_CSE_KEY + GOOGLE_CSE_ID (both free).
"""

import logging
import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import requests

logger = logging.getLogger(__name__)

GOOGLE_CSE_URL = 'https://www.googleapis.com/customsearch/v1'
_TIMEOUT = 20

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

# Terms OR-ed into the single search query (stemmed roots kept short for recall).
_QUERY_TERMS = LEXICON['criminal'] + LEXICON['reputational']


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


def is_available() -> bool:
    """True only if a search backend is configured (Google CSE key + id)."""
    return bool(os.environ.get('GOOGLE_CSE_KEY') and os.environ.get('GOOGLE_CSE_ID'))


def _build_query(full_name: str) -> str:
    """Quoted full name + OR-ed negative lexicon, one query per candidate."""
    terms = ' OR '.join(_QUERY_TERMS)
    return f'"{full_name}" ({terms})'


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

    items, err = _google_cse_search(_build_query(full_name))
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
