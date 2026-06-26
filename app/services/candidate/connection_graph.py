"""
Connection Graph (Axis 2 — the target's web of connections)
============================================================
Exposes every person and entity the investigation target is tied to, so the
investigator can see who/what they're linked to and judge significance. There
is NO employer watch-set / preferred-match list — we surface ALL meaningful
ties; the human decides what matters.

A connection is built from typed EDGES emitted by per-source extractors. Each
extractor (here, and the discarded-data rescuers in the source modules) returns
a list of raw edge dicts in this CONTRACT:

    {
        'kind':       'person' | 'company',
        'name':       str,
        'inn':        str,   # '' if unknown — the strong dedup/identity key
        'ogrn':       str,   # '' if unknown / for persons
        'relation':   str,   # machine code (see RELATION_LABELS)
        'label':      str,   # human Russian label for this specific tie
        'via':        str,   # the bridge: company, address, case №, phone, email
        'source':     str,   # provenance
        'confidence': 'strong' | 'weak',   # strong = ИНН/ОГРН-keyed evidence
    }

build_connections() entity-resolves edges into Connection objects (dedup by ИНН
when present, else by normalized name) so the same counterparty seen via five
sources is one node carrying all its relations.
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

# Human Russian labels per relation code (fallback when an edge omits 'label').
RELATION_LABELS = {
    'owns': 'Учредитель',
    'directs': 'Руководитель',
    'affiliated': 'Связан с компанией',
    'co_owner': 'Совладелец',
    'co_director': 'Соруководитель',
    'co_litigant': 'Сторона по судебному делу',
    'co_registered': 'Один адрес регистрации',
    'shared_business': 'Общие компании',
    'shared_contact': 'Общий контакт',
    'flagged_friend': 'Друг в соцсети (отмечен)',
}

# Relation priority for sorting (lower = surfaced first).
_RELATION_ORDER = {
    'co_owner': 0, 'co_director': 1, 'owns': 2, 'directs': 3,
    'co_litigant': 4, 'co_registered': 5, 'shared_business': 6,
    'affiliated': 7, 'shared_contact': 8, 'flagged_friend': 9,
}


def _norm_name(name: str) -> str:
    """Normalize a name for weak (no-ИНН) dedup: lowercase, ё→е, strip quotes/
    legal-form noise, collapse whitespace."""
    s = (name or '').lower().replace('ё', 'е')
    s = re.sub(r'[«»"\'(),.]', ' ', s)
    s = re.sub(r'\b(ооо|оао|зао|пао|ао|ип|нко|ано|тоо)\b', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()


@dataclass
class Connection:
    """A resolved counterparty the target is tied to, with all its relations."""
    kind: str
    name: str
    inn: str = ''
    ogrn: str = ''
    relations: List[dict] = field(default_factory=list)

    @property
    def confidence(self) -> str:
        return 'strong' if any(r.get('confidence') == 'strong' for r in self.relations) else 'weak'

    def to_dict(self) -> dict:
        return {
            'kind': self.kind,
            'name': self.name,
            'inn': self.inn,
            'ogrn': self.ogrn,
            'confidence': self.confidence,
            'relations': self.relations,
        }


def _resolution_key(edge: dict) -> str:
    inn = (edge.get('inn') or '').strip()
    if inn:
        return f'inn:{inn}'
    return f'name:{edge.get("kind", "")}:{_norm_name(edge.get("name", ""))}'


def build_connections(edges: List[dict]) -> List[Connection]:
    """Entity-resolve raw edges into Connection objects.

    Dedup by ИНН when present, else by (kind, normalized name). Relations are
    merged and de-duplicated; a counterparty gains ИНН/ОГРН from whichever edge
    supplied it. Sorted: strong before weak, then by most-significant relation,
    then by relation count, then name.
    """
    by_key: Dict[str, Connection] = {}
    for e in edges:
        name = (e.get('name') or '').strip()
        if not name:
            continue
        key = _resolution_key(e)
        conn = by_key.get(key)
        if conn is None:
            conn = Connection(kind=e.get('kind', 'person'), name=name)
            by_key[key] = conn
        # Fill identity from any edge that has it.
        if not conn.inn and e.get('inn'):
            conn.inn = e['inn'].strip()
        if not conn.ogrn and e.get('ogrn'):
            conn.ogrn = e['ogrn'].strip()
        # Prefer a longer/more complete name (e.g. full ФИО over initials).
        if len(name) > len(conn.name):
            conn.name = name

        relation = e.get('relation', 'affiliated')
        rel = {
            'relation': relation,
            'label': e.get('label') or RELATION_LABELS.get(relation, relation),
            'via': e.get('via', ''),
            'source': e.get('source', ''),
            'confidence': e.get('confidence', 'weak'),
        }
        # De-dup identical relations (same relation+via+source).
        sig = (rel['relation'], rel['via'], rel['source'])
        if sig not in {(r['relation'], r['via'], r['source']) for r in conn.relations}:
            conn.relations.append(rel)

    def _sort_key(c: Connection):
        best_rel = min((_RELATION_ORDER.get(r['relation'], 99) for r in c.relations), default=99)
        return (0 if c.confidence == 'strong' else 1, best_rel, -len(c.relations), c.name)

    return sorted(by_key.values(), key=_sort_key)


# ── Extractors for data already persisted on the CandidateCheck ─────────────

def from_business_records(records: List[dict]) -> List[dict]:
    """The target's own companies → company connections (owns/directs)."""
    edges = []
    for r in records or []:
        if not isinstance(r, dict):
            continue
        name = (r.get('company_name') or r.get('name') or '').strip()
        if not name or r.get('source') == 'manual':
            continue
        role = (r.get('role') or '').lower()
        if 'учред' in role or 'владел' in role:
            relation, label = 'owns', r.get('role') or 'Учредитель'
        elif 'директ' in role or 'руковод' in role:
            relation, label = 'directs', r.get('role') or 'Руководитель'
        else:
            relation, label = 'affiliated', r.get('role') or 'Связан с компанией'
        inn = (r.get('inn') or '').strip()
        edges.append({
            'kind': 'company', 'name': name, 'inn': inn,
            'ogrn': (r.get('ogrn') or '').strip(),
            'relation': relation, 'label': label,
            'via': name, 'source': r.get('source', 'ЕГРЮЛ'),
            'confidence': 'strong' if inn else 'weak',
        })
    return edges


def from_connected_checks(connected_checks: List[dict]) -> List[dict]:
    """Cross-investigation links (people who share a company/phone/email with
    the target, found among past checks) → person connections."""
    edges = []
    for c in connected_checks or []:
        if not isinstance(c, dict):
            continue
        name = (c.get('connected_name') or '').strip()
        if not name:
            continue
        for ct in c.get('connection_types', []) or []:
            t = ct.get('type')
            if t == 'shared_business':
                inns = ct.get('inns') or []
                edges.append({
                    'kind': 'person', 'name': name, 'inn': '', 'ogrn': '',
                    'relation': 'shared_business',
                    'label': 'Общие компании',
                    'via': ', '.join(f'ИНН {i}' for i in inns) if inns else '',
                    'source': 'связанные проверки',
                    'confidence': 'strong',   # shared company ИНН is strong evidence
                })
            elif t in ('shared_phone', 'shared_email'):
                edges.append({
                    'kind': 'person', 'name': name, 'inn': '', 'ogrn': '',
                    'relation': 'shared_contact',
                    'label': 'Общий телефон' if t == 'shared_phone' else 'Общий email',
                    'via': ct.get('description', ''),
                    'source': 'связанные проверки',
                    'confidence': 'weak',
                })
    return edges


def from_flagged_friends(social_graph_data: dict) -> List[dict]:
    """VK friends flagged against the wanted/extremist lists → person
    connections (weak — name-only, no civil identity)."""
    edges = []
    deep = (social_graph_data or {}).get('friends_risk_deep') or {}
    for f in deep.get('flagged_friends', []) or []:
        name = (f.get('name') or '').strip()
        if not name:
            continue
        hits = f.get('hits') or []
        sources = ', '.join(sorted({h.get('source', '') for h in hits if h.get('source')}))
        edges.append({
            'kind': 'person', 'name': name, 'inn': '', 'ogrn': '',
            'relation': 'flagged_friend',
            'label': 'Друг ВК — возможное совпадение с базой розыска/экстремистов',
            'via': f.get('url', ''),
            'source': sources or 'VK',
            'confidence': 'weak',
        })
    return edges


def build_graph_data(connections: List['Connection'], check) -> dict:
    """
    Build a D3-ready {target, nodes, links} graph with proper chain structure.

    Relation routing:
      - owns / directs / affiliated / flagged_friend → Target → Node  (direct)
      - co_director / co_owner / shared_business via Company → Target → Company → Person
        (reuses existing company node when via-name matches one already in connections)
      - co_litigant via Case# → Target → Case-node → Person
      - co_registered via Address → Target → Address-node → Person
      - shared_contact via phone/email → Target → Contact-node → Person
    """
    _RTYPE = {
        'owns': 'business', 'directs': 'business', 'co_owner': 'business',
        'co_director': 'business', 'affiliated': 'business', 'shared_business': 'business',
        'co_litigant': 'court', 'flagged_friend': 'court',
        'co_registered': 'address',
        'shared_contact': 'contact',
    }
    _DIRECT = {'owns', 'directs', 'affiliated', 'flagged_friend'}
    _VIA_COMPANY = {'co_director', 'co_owner', 'shared_business'}
    _VIA_CASE = {'co_litigant'}
    _VIA_ADDR = {'co_registered'}
    _VIA_CONTACT = {'shared_contact'}

    nodes: dict = {}   # id -> node dict (target excluded)
    links: list = []

    # Build lookup: normalised-name / INN → existing node_id for company nodes
    company_lookup: dict = {}
    for conn in connections:
        if conn.kind == 'company':
            nid = f'inn_{conn.inn}' if conn.inn else f'name_{conn.name}'
            company_lookup[_norm_name(conn.name)] = nid
            if conn.inn:
                company_lookup[conn.inn] = nid

    # Create all primary nodes
    for conn in connections:
        nid = f'inn_{conn.inn}' if conn.inn else f'name_{conn.name}'
        primary_group = next(
            (_RTYPE.get(r['relation'], 'business') for r in conn.relations),
            'business'
        )
        nodes[nid] = {
            'id': nid,
            'full': conn.name,
            'sub': conn.inn or conn.ogrn or '',
            'typeLabel': 'ЮР. ЛИЦО' if conn.kind == 'company' else 'ФИЗ. ЛИЦО',
            'type': conn.kind,
            'group': primary_group,
            'meta': {
                **(({'ИНН': conn.inn} if conn.inn else {})),
                **(({'ОГРН': conn.ogrn} if conn.ogrn else {})),
                'Тип': 'Юр. лицо' if conn.kind == 'company' else 'Физ. лицо',
            },
            'confidence': conn.confidence,
        }

    # Track nodes that already have a target → node edge to avoid duplicates
    has_target_edge: set = set()

    def _ensure_target_edge(vid: str, ltype: str, label: str) -> None:
        if vid not in has_target_edge:
            links.append({'source': 'target', 'target': vid, 'type': ltype, 'label': label})
            has_target_edge.add(vid)

    for conn in connections:
        nid = f'inn_{conn.inn}' if conn.inn else f'name_{conn.name}'

        for rel in conn.relations:
            relation = rel['relation']
            via = (rel.get('via') or '').strip()
            ltype = _RTYPE.get(relation, 'business')
            label = rel['label']

            if relation in _DIRECT or not via:
                _ensure_target_edge(nid, ltype, label)

            elif relation in _VIA_COMPANY:
                # Resolve via-name to existing company node or create intermediary
                vid = company_lookup.get(_norm_name(via)) or company_lookup.get(via)
                if not vid:
                    vid = f'via_biz_{_norm_name(via)}'
                    if vid not in nodes:
                        nodes[vid] = {
                            'id': vid, 'full': via, 'sub': '',
                            'typeLabel': 'ЮР. ЛИЦО', 'type': 'company', 'group': 'business',
                            'meta': {'Тип': 'Юр. лицо'}, 'confidence': 'weak',
                        }
                _ensure_target_edge(vid, 'business', 'Связанная компания')
                links.append({'source': vid, 'target': nid, 'type': ltype, 'label': label})

            elif relation in _VIA_CASE:
                vid = f'via_case_{via}'
                if vid not in nodes:
                    nodes[vid] = {
                        'id': vid, 'full': via or 'Судебное дело', 'sub': 'Дело',
                        'typeLabel': 'СУД. ДЕЛО', 'type': 'case', 'group': 'court',
                        'meta': ({'Номер дела': via} if via else {}), 'confidence': 'strong' if via else 'weak',
                    }
                _ensure_target_edge(vid, 'court', 'Участник дела')
                links.append({'source': vid, 'target': nid, 'type': 'court', 'label': label})

            elif relation in _VIA_ADDR:
                vid = f'via_addr_{via}'
                if vid not in nodes:
                    nodes[vid] = {
                        'id': vid, 'full': via or 'Адрес регистрации', 'sub': 'Адрес',
                        'typeLabel': 'АДРЕС', 'type': 'address_hub', 'group': 'address',
                        'meta': ({'Адрес': via} if via else {}), 'confidence': 'weak',
                    }
                _ensure_target_edge(vid, 'address', 'Адрес регистрации')
                links.append({'source': vid, 'target': nid, 'type': 'address', 'label': label})

            elif relation in _VIA_CONTACT:
                vid = f'via_contact_{via}'
                if vid not in nodes:
                    nodes[vid] = {
                        'id': vid, 'full': via or 'Общий контакт', 'sub': 'Контакт',
                        'typeLabel': 'КОНТАКТ', 'type': 'contact_hub', 'group': 'contact',
                        'meta': ({'Контакт': via} if via else {}), 'confidence': 'weak',
                    }
                _ensure_target_edge(vid, 'contact', 'Общий контакт')
                links.append({'source': vid, 'target': nid, 'type': 'contact', 'label': label})

            else:
                _ensure_target_edge(nid, ltype, label)

    dob = getattr(check, 'date_of_birth', None)
    return {
        'target': {
            'full': check.full_name,
            'inn': check.inn or '',
            'dob': dob.isoformat() if dob else '',
        },
        'nodes': list(nodes.values()),
        'links': links,
    }


def build_from_check(check, extra_edges: Optional[List[dict]] = None) -> List[Connection]:
    """Assemble the target's connection graph from everything available on the
    check, plus any extra edges from the discarded-data rescuers (co-owners,
    court co-parties, address co-registrants) passed in by the pipeline."""
    edges: List[dict] = []
    edges += from_business_records(getattr(check, 'business_records', None) or [])
    edges += from_connected_checks(getattr(check, 'connected_checks', None) or [])
    edges += from_flagged_friends(getattr(check, 'social_graph_data', None) or {})
    if extra_edges:
        edges += [e for e in extra_edges if isinstance(e, dict)]
    return build_connections(edges)
