"""
SanctionsLocalService — Local Sanctions Database
=================================================
Downloads and caches official sanctions lists locally. No API key required.
Checks by exact INN match first, then normalized name, then fuzzy name.

Sources (all public domain / open government data):
  OFAC SDN   — US Treasury Specially Designated Nationals list
               ~12,000 entities including Russian companies under EO14024
  UN SC      — UN Security Council Consolidated Sanctions List
               ~700 entities + ~500 individuals

Cache: instance/sanctions_cache/  (auto-created, never committed to git)
TTL:   7 days — re-downloads if any source is stale or missing

Matching priority:
  1. INN / registration number  — exact, score 1.0  (fastest, most reliable)
  2. Normalized exact name      — score 0.95
  3. Word-sorted name match     — score 0.92  (handles "ПАО ГАЗПРОМ" vs "ГАЗПРОМ ПАО")
  4. Fuzzy name (SequenceMatcher ≥ 0.85) — O(N) over candidates sharing keywords
"""

import logging
import os
import pickle
import re
import threading
import time
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Dict, List, Optional
from xml.etree import ElementTree as ET

import requests

logger = logging.getLogger(__name__)

# ── Config ───────────────────────────────────────────────────────────────────

CACHE_TTL_SECONDS = 24 * 3600   # 24 hours — OFAC updates 2-3x/week
FUZZY_THRESHOLD   = 0.85
INDEX_FILE        = 'sanctions_index.pkl'

SOURCES = {
    'ofac_sdn': {
        'display': 'US OFAC SDN',
        'display_ru': 'OFAC SDN (Минфин США)',
        'url': 'https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/SDN.XML',
        'fallback_url': 'https://www.treasury.gov/ofac/downloads/sdn.xml',
        'filename': 'ofac_sdn.xml',
        'search_url': 'https://sanctionssearch.ofac.treas.gov/',
    },
    'un_sc': {
        'display': 'UN Security Council',
        'display_ru': 'Совет Безопасности ООН',
        'url': 'https://scsanctions.un.org/resources/xml/en/consolidated.xml',
        'fallback_url': 'https://scsanctions.un.org/resources/xml/en/name/consolidated.xml',
        'filename': 'un_sc.xml',
        'search_url': 'https://www.un.org/securitycouncil/content/un-sc-consolidated-list',
    },
}

_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/122.0.0.0 Safari/537.36'
    ),
}

# ── Internal entry format ────────────────────────────────────────────────────

@dataclass
class _Entry:
    uid: str
    names: List[str]              # all name variants (original case)
    normalized: List[str]         # all normalized forms
    sorted_normalized: List[str]  # word-sorted normalized forms
    inns: List[str]               # registration numbers / INNs
    source: str                   # 'ofac_sdn' | 'un_sc'
    entity_type: str              # 'Company' | 'Individual'
    programs: List[str]           # OFAC programs or UN list types
    search_url: str


# ── Normalization helpers ────────────────────────────────────────────────────

def _norm(name: str) -> str:
    """Uppercase + strip punctuation + collapse spaces."""
    s = name.upper()
    s = re.sub(r'[^\w\s]', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()


def _sort_norm(name: str) -> str:
    """Normalize then sort words for order-independent matching."""
    return ' '.join(sorted(_norm(name).split()))


def _entry_words(entry: _Entry) -> set:
    """All words ≥4 chars across all normalized name forms."""
    words: set = set()
    for n in entry.normalized:
        words.update(w for w in n.split() if len(w) >= 4)
    return words


# ── Main service ─────────────────────────────────────────────────────────────

class SanctionsLocalService:
    """
    Local sanctions screening. Downloads lists on first use; checks in-memory.

    Usage:
        svc = SanctionsLocalService()
        result = svc.check(company_name='ПАО ГАЗПРОМ', inn='7736050003')
    """

    def __init__(self, cache_dir: Optional[str] = None):
        if cache_dir is None:
            here = os.path.dirname(os.path.abspath(__file__))
            cache_dir = os.path.normpath(
                os.path.join(here, '..', '..', '..', 'instance', 'sanctions_cache')
            )
        self.cache_dir = cache_dir
        self._index: Optional[Dict] = None
        self._lock = threading.Lock()

    # ── Public API ────────────────────────────────────────────────────────────

    def check(self, company_name: str, inn: str = '', ogrn: str = '') -> Dict:
        """
        Screen a company against all cached sanctions lists.

        Returns dict:
          found          — True if a match was found
          unavailable    — True if no lists could be loaded
          matches        — list of match dicts
          sources_checked — list of source display names that were checked
        """
        index = self._load_index()
        if index is None:
            return {'found': False, 'matches': [], 'unavailable': True, 'sources_checked': []}

        matches: List[Dict] = []
        seen_uids: set = set()

        def _add(entry: _Entry, match_type: str, score: float, matched_term: str) -> None:
            if entry.uid not in seen_uids:
                seen_uids.add(entry.uid)
                src = SOURCES[entry.source]
                matches.append({
                    'name': entry.names[0] if entry.names else matched_term,
                    'source_name': src['display_ru'],
                    'list_code': entry.source,
                    'match_type': match_type,
                    'score': round(score, 3),
                    'entity_type': entry.entity_type,
                    'programs': entry.programs,
                    'url': entry.search_url,
                    'datasets': [src['display_ru']],
                    'match_details': (
                        f"Совпадение ({score:.0%}): {entry.names[0] if entry.names else ''}. "
                        f"Список: {src['display_ru']}"
                    ),
                })

        # 1. Registration number exact match — try INN (10/12 digits) and OGRN (13/15 digits)
        for reg_num in filter(None, [inn.strip(), ogrn.strip()]):
            cleaned = re.sub(r'[^\d]', '', reg_num)
            for lookup in {cleaned, reg_num} - {''}:
                for entry in index['by_inn'].get(lookup, []):
                    _add(entry, 'inn', 1.0, lookup)

        # 2. Exact normalized name
        company_norm = _norm(company_name)
        for entry in index['by_name'].get(company_norm, []):
            _add(entry, 'exact_name', 0.95, company_name)

        # 3. Word-sorted normalized name (handles different word orders)
        company_sorted = _sort_norm(company_name)
        for entry in index['by_sorted'].get(company_sorted, []):
            _add(entry, 'exact_name', 0.92, company_name)

        # 4. Fuzzy name — only if no exact match found
        if not matches and len(company_norm) >= 5:
            # Pre-filter: candidates must share at least one long keyword
            query_words = {w for w in company_norm.split() if len(w) >= 4}
            candidates = [
                e for e in index['all_entries']
                if query_words & _entry_words(e)
            ] if query_words else []

            best_score = 0.0
            best_entry: Optional[_Entry] = None
            for entry in candidates:
                for n in entry.normalized:
                    score = SequenceMatcher(None, company_norm, n).ratio()
                    if score >= FUZZY_THRESHOLD and score > best_score:
                        best_score = score
                        best_entry = entry

            if best_entry:
                _add(best_entry, 'fuzzy_name', best_score, company_name)

        sources = [SOURCES[k]['display'] for k in index.get('sources_loaded', [])]
        return {
            'found': bool(matches),
            'matches': matches,
            'unavailable': False,
            'sources_checked': sources,
        }

    def status(self) -> Dict:
        """Return cache status — loaded sources, entry counts, age."""
        os.makedirs(self.cache_dir, exist_ok=True)
        result = {'sources': {}, 'index_built': None, 'index_stale': True}
        idx_path = os.path.join(self.cache_dir, INDEX_FILE)
        if os.path.exists(idx_path):
            age = time.time() - os.path.getmtime(idx_path)
            result['index_built'] = time.strftime(
                '%Y-%m-%d %H:%M', time.localtime(os.path.getmtime(idx_path))
            )
            result['index_stale'] = age > CACHE_TTL_SECONDS
        for src_id, src in SOURCES.items():
            fpath = os.path.join(self.cache_dir, src['filename'])
            if os.path.exists(fpath):
                age = time.time() - os.path.getmtime(fpath)
                result['sources'][src_id] = {
                    'present': True,
                    'stale': age > CACHE_TTL_SECONDS,
                    'size_kb': os.path.getsize(fpath) // 1024,
                }
            else:
                result['sources'][src_id] = {'present': False, 'stale': True}
        return result

    def refresh(self) -> Dict:
        """Force re-download all sources and rebuild index. Returns status dict."""
        with self._lock:
            self._index = None
            # Delete existing files to force re-download
            idx_path = os.path.join(self.cache_dir, INDEX_FILE)
            if os.path.exists(idx_path):
                os.remove(idx_path)
        return self._build_index()

    # ── Index management ─────────────────────────────────────────────────────

    def _load_index(self) -> Optional[Dict]:
        """Lazy-load index from pickle. Downloads and builds if missing/stale."""
        if self._index is not None:
            return self._index

        with self._lock:
            if self._index is not None:
                return self._index

            os.makedirs(self.cache_dir, exist_ok=True)
            idx_path = os.path.join(self.cache_dir, INDEX_FILE)

            # Load from pickle if fresh
            if os.path.exists(idx_path):
                age = time.time() - os.path.getmtime(idx_path)
                if age < CACHE_TTL_SECONDS:
                    try:
                        with open(idx_path, 'rb') as f:
                            self._index = pickle.load(f)
                        logger.info(
                            "Sanctions index loaded from cache (%d entries, %d sources)",
                            len(self._index.get('all_entries', [])),
                            len(self._index.get('sources_loaded', [])),
                        )
                        return self._index
                    except Exception as exc:
                        logger.warning("Sanctions cache read error: %s", exc)

            # Build fresh
            self._index = self._build_index()
            return self._index if self._index.get('all_entries') else None

    def _build_index(self) -> Dict:
        """Download all sources, parse, build in-memory index, pickle it."""
        logger.info("Building sanctions index...")
        t0 = time.time()

        all_entries: List[_Entry] = []
        sources_loaded: List[str] = []

        for src_id, src in SOURCES.items():
            try:
                fpath = self._ensure_file(src_id, src)
                if fpath is None:
                    continue
                entries = self._parse_source(src_id, fpath)
                all_entries.extend(entries)
                sources_loaded.append(src_id)
                logger.info(
                    "Sanctions: loaded %d entries from %s", len(entries), src['display']
                )
            except Exception as exc:
                logger.warning("Sanctions: failed to load %s: %s", src_id, exc)

        if not all_entries:
            logger.warning("Sanctions: no entries loaded from any source")
            return {'all_entries': [], 'by_inn': {}, 'by_name': {}, 'by_sorted': {}, 'sources_loaded': []}

        # Build lookup dicts
        by_inn: Dict[str, List[_Entry]] = {}
        by_name: Dict[str, List[_Entry]] = {}
        by_sorted: Dict[str, List[_Entry]] = {}

        for entry in all_entries:
            for inn in entry.inns:
                by_inn.setdefault(inn, []).append(entry)
            for n in entry.normalized:
                by_name.setdefault(n, []).append(entry)
            for sn in entry.sorted_normalized:
                by_sorted.setdefault(sn, []).append(entry)

        index = {
            'all_entries': all_entries,
            'by_inn': by_inn,
            'by_name': by_name,
            'by_sorted': by_sorted,
            'sources_loaded': sources_loaded,
            'built_at': time.time(),
        }

        # Pickle for next startup
        idx_path = os.path.join(self.cache_dir, INDEX_FILE)
        try:
            with open(idx_path, 'wb') as f:
                pickle.dump(index, f, protocol=pickle.HIGHEST_PROTOCOL)
            logger.info(
                "Sanctions index built in %.1fs: %d entries, pickle %.0fKB",
                time.time() - t0,
                len(all_entries),
                os.path.getsize(idx_path) / 1024,
            )
        except Exception as exc:
            logger.warning("Sanctions: could not pickle index: %s", exc)

        return index

    def _ensure_file(self, src_id: str, src: Dict) -> Optional[str]:
        """Return path to local XML file, downloading if missing or stale."""
        fpath = os.path.join(self.cache_dir, src['filename'])

        if os.path.exists(fpath):
            age = time.time() - os.path.getmtime(fpath)
            if age < CACHE_TTL_SECONDS:
                return fpath

        # Download
        for url in [src['url'], src.get('fallback_url')]:
            if not url:
                continue
            try:
                logger.info("Sanctions: downloading %s from %s", src_id, url)
                resp = requests.get(url, headers=_HEADERS, timeout=60, stream=True)
                if resp.status_code != 200:
                    logger.warning("Sanctions: HTTP %d for %s", resp.status_code, src_id)
                    continue
                tmp = fpath + '.tmp'
                with open(tmp, 'wb') as f:
                    for chunk in resp.iter_content(65536):
                        f.write(chunk)
                os.replace(tmp, fpath)
                logger.info(
                    "Sanctions: downloaded %s (%.0fKB)",
                    src_id, os.path.getsize(fpath) / 1024,
                )
                return fpath
            except Exception as exc:
                logger.warning("Sanctions: download failed for %s from %s: %s", src_id, url, exc)

        return None

    # ── Parsers ───────────────────────────────────────────────────────────────

    def _parse_source(self, src_id: str, fpath: str) -> List[_Entry]:
        if src_id == 'ofac_sdn':
            return self._parse_ofac(fpath)
        if src_id == 'un_sc':
            return self._parse_un(fpath)
        return []

    def _parse_ofac(self, fpath: str) -> List[_Entry]:
        """Parse OFAC SDN XML into _Entry list."""
        entries: List[_Entry] = []
        search_url = SOURCES['ofac_sdn']['search_url']

        try:
            tree = ET.parse(fpath)
            root = tree.getroot()
            # Strip namespace if present: {http://...}sdnList → look for sdnEntry anywhere
            ns = ''
            if root.tag.startswith('{'):
                ns = root.tag.split('}')[0] + '}'
        except Exception as exc:
            logger.warning("OFAC XML parse error: %s", exc)
            return entries

        for node in root.iter(f'{ns}sdnEntry'):
            sdn_type = (node.findtext(f'{ns}sdnType') or '').strip()
            entity_type = 'Company' if sdn_type == 'Entity' else 'Individual'

            uid = node.findtext(f'{ns}uid') or ''
            last_name = (node.findtext(f'{ns}lastName') or '').strip()
            first_name = (node.findtext(f'{ns}firstName') or '').strip()
            if first_name:
                primary_name = f'{last_name} {first_name}'.strip()
            else:
                primary_name = last_name

            if not primary_name:
                continue

            # AKAs
            all_names = [primary_name]
            for aka in node.iter(f'{ns}aka'):
                aka_last = (aka.findtext(f'{ns}lastName') or '').strip()
                aka_first = (aka.findtext(f'{ns}firstName') or '').strip()
                aka_name = f'{aka_last} {aka_first}'.strip() if aka_first else aka_last
                if aka_name and aka_name not in all_names:
                    all_names.append(aka_name)

            # Programs
            programs = [
                p.text.strip()
                for p in node.iter(f'{ns}program')
                if p.text and p.text.strip()
            ]

            # Registration numbers — OFAC uses OGRN (13-digit) for Russian companies,
            # not INN. Store all registration-type IDs so OGRN lookup works.
            inns: List[str] = []
            for id_node in node.iter(f'{ns}id'):
                id_type = (id_node.findtext(f'{ns}idType') or '').strip().lower()
                id_number = (id_node.findtext(f'{ns}idNumber') or '').strip()
                if id_number and ('registration' in id_type or 'ogrn' in id_type or 'inn' in id_type):
                    cleaned = re.sub(r'[^\d]', '', id_number)
                    # Store both the cleaned digits and the raw value
                    if cleaned and cleaned not in inns:
                        inns.append(cleaned)
                    if id_number not in inns and id_number != cleaned:
                        inns.append(id_number)

            norm_names = list(dict.fromkeys(_norm(n) for n in all_names if n))
            sorted_norms = list(dict.fromkeys(_sort_norm(n) for n in all_names if n))

            entries.append(_Entry(
                uid=f'ofac_{uid}',
                names=all_names,
                normalized=norm_names,
                sorted_normalized=sorted_norms,
                inns=inns,
                source='ofac_sdn',
                entity_type=entity_type,
                programs=programs,
                search_url=search_url,
            ))

        return entries

    def _parse_un(self, fpath: str) -> List[_Entry]:
        """Parse UN SC consolidated XML into _Entry list."""
        entries: List[_Entry] = []
        search_url = SOURCES['un_sc']['search_url']

        try:
            tree = ET.parse(fpath)
            root = tree.getroot()
            ns = ''
            if root.tag.startswith('{'):
                ns = root.tag.split('}')[0] + '}'
        except Exception as exc:
            logger.warning("UN SC XML parse error: %s", exc)
            return entries

        # Parse both ENTITIES (companies) and INDIVIDUALS
        for section, etype in [('ENTITIES', 'Company'), ('INDIVIDUALS', 'Individual')]:
            container = root.find(f'{ns}{section}')
            if container is None:
                # Try case-insensitive
                for child in root:
                    if child.tag.upper().endswith(section):
                        container = child
                        break
            if container is None:
                continue

            item_tag = 'ENTITY' if etype == 'Company' else 'INDIVIDUAL'
            for node in container.iter(f'{ns}{item_tag}'):
                dataid = node.findtext(f'{ns}DATAID') or node.findtext('DATAID') or ''

                # Name: different fields for entities vs individuals
                parts = []
                for field_name in ['FIRST_NAME', 'SECOND_NAME', 'THIRD_NAME', 'FOURTH_NAME']:
                    v = (node.findtext(f'{ns}{field_name}') or node.findtext(field_name) or '').strip()
                    if v:
                        parts.append(v)
                primary_name = ' '.join(parts).strip()
                if not primary_name:
                    continue

                # Aliases
                all_names = [primary_name]
                alias_list = node.find(f'{ns}ALIAS_LIST') or node.find('ALIAS_LIST')
                if alias_list is not None:
                    for alias in alias_list:
                        alias_name = (
                            alias.findtext(f'{ns}NAME') or
                            alias.findtext('NAME') or
                            alias.findtext(f'{ns}ALIAS_NAME') or
                            alias.findtext('ALIAS_NAME') or ''
                        ).strip()
                        if alias_name and alias_name not in all_names:
                            all_names.append(alias_name)

                # List type (UN category)
                list_type = (
                    node.findtext(f'{ns}UN_LIST_TYPE') or
                    node.findtext('UN_LIST_TYPE') or ''
                ).strip()
                programs = [list_type] if list_type else ['UN SC Consolidated']

                norm_names = list(dict.fromkeys(_norm(n) for n in all_names if n))
                sorted_norms = list(dict.fromkeys(_sort_norm(n) for n in all_names if n))

                entries.append(_Entry(
                    uid=f'un_{dataid}',
                    names=all_names,
                    normalized=norm_names,
                    sorted_normalized=sorted_norms,
                    inns=[],  # UN list rarely has registration numbers
                    source='un_sc',
                    entity_type=etype,
                    programs=programs,
                    search_url=search_url,
                ))

        return entries
