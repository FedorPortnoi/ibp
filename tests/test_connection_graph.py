"""Axis 2 connection-graph spine: entity resolution + the already-persisted
extractors. The discarded-data rescuers (co-owners, court co-parties, address)
are tested separately as they land."""

import pytest

from app.services.candidate import connection_graph as cg


# ── entity resolution ───────────────────────────────────────────────────────

def test_dedup_by_inn_merges_relations():
    edges = [
        {'kind': 'person', 'name': 'Иванов И.', 'inn': '770000000001',
         'relation': 'co_owner', 'via': 'ООО А', 'source': 's1', 'confidence': 'strong'},
        {'kind': 'person', 'name': 'Иванов Иван Иванович', 'inn': '770000000001',
         'relation': 'co_litigant', 'via': 'дело №1', 'source': 's2', 'confidence': 'strong'},
    ]
    conns = cg.build_connections(edges)
    assert len(conns) == 1
    c = conns[0]
    assert c.inn == '770000000001'
    assert c.name == 'Иванов Иван Иванович'   # longer/fuller name wins
    assert {r['relation'] for r in c.relations} == {'co_owner', 'co_litigant'}


def test_dedup_by_name_when_no_inn():
    edges = [
        {'kind': 'person', 'name': 'Петров Пётр', 'relation': 'shared_contact',
         'via': 'тел', 'source': 's', 'confidence': 'weak'},
        {'kind': 'person', 'name': 'петров петр', 'relation': 'flagged_friend',
         'via': '', 'source': 'vk', 'confidence': 'weak'},
    ]
    conns = cg.build_connections(edges)
    assert len(conns) == 1 and len(conns[0].relations) == 2


def test_different_inn_not_merged():
    edges = [
        {'kind': 'person', 'name': 'Иванов', 'inn': '111', 'relation': 'co_owner',
         'via': 'a', 'source': 's', 'confidence': 'strong'},
        {'kind': 'person', 'name': 'Иванов', 'inn': '222', 'relation': 'co_owner',
         'via': 'b', 'source': 's', 'confidence': 'strong'},
    ]
    assert len(cg.build_connections(edges)) == 2


def test_confidence_strong_if_any_relation_strong():
    edges = [
        {'kind': 'person', 'name': 'X', 'inn': '5', 'relation': 'shared_contact',
         'via': '', 'source': 's', 'confidence': 'weak'},
        {'kind': 'person', 'name': 'X', 'inn': '5', 'relation': 'co_owner',
         'via': '', 'source': 's', 'confidence': 'strong'},
    ]
    assert cg.build_connections(edges)[0].confidence == 'strong'


def test_identical_relation_deduped():
    e = {'kind': 'person', 'name': 'X', 'inn': '5', 'relation': 'co_owner',
         'via': 'ООО А', 'source': 's', 'confidence': 'strong'}
    assert len(cg.build_connections([e, dict(e)])[0].relations) == 1


def test_strong_sorted_before_weak():
    edges = [
        {'kind': 'person', 'name': 'Weak', 'relation': 'flagged_friend',
         'via': '', 'source': 'vk', 'confidence': 'weak'},
        {'kind': 'company', 'name': 'Strong', 'inn': '9', 'relation': 'co_owner',
         'via': '', 'source': 's', 'confidence': 'strong'},
    ]
    conns = cg.build_connections(edges)
    assert conns[0].name == 'Strong' and conns[1].name == 'Weak'


# ── extractors ──────────────────────────────────────────────────────────────

def test_from_business_records_roles():
    recs = [
        {'company_name': 'ООО Ромашка', 'inn': '7700000001', 'role': 'Учредитель', 'source': 'ЕГРЮЛ'},
        {'company_name': 'ООО Тюльпан', 'inn': '7700000002', 'role': 'Генеральный директор', 'source': 'ЕГРЮЛ'},
        {'company_name': 'Manual Co', 'role': 'x', 'source': 'manual'},
    ]
    edges = cg.from_business_records(recs)
    assert len(edges) == 2   # manual skipped
    rels = {e['name']: e['relation'] for e in edges}
    assert rels['ООО Ромашка'] == 'owns' and rels['ООО Тюльпан'] == 'directs'
    assert all(e['confidence'] == 'strong' for e in edges)


def test_from_connected_checks_business_strong_contact_weak():
    cc = [{
        'connected_name': 'Сидоров С.С.',
        'connection_types': [
            {'type': 'shared_business', 'inns': ['7700000009'], 'description': 'x'},
            {'type': 'shared_phone', 'description': '+7900'},
        ],
    }]
    edges = cg.from_connected_checks(cc)
    by_rel = {e['relation']: e for e in edges}
    assert by_rel['shared_business']['confidence'] == 'strong'
    assert by_rel['shared_contact']['confidence'] == 'weak'


def test_from_flagged_friends():
    sg = {'friends_risk_deep': {'flagged_friends': [
        {'name': 'Опасный Друг', 'url': 'https://vk.com/id5',
         'hits': [{'source': 'mvd_wanted'}]},
    ]}}
    edges = cg.from_flagged_friends(sg)
    assert len(edges) == 1 and edges[0]['relation'] == 'flagged_friend'
    assert edges[0]['confidence'] == 'weak'


# ── build_from_check integration ────────────────────────────────────────────

class _Check:
    business_records = [{'company_name': 'ООО Ромашка', 'inn': '7700000001',
                         'role': 'Учредитель', 'source': 'ЕГРЮЛ'}]
    connected_checks = [{'connected_name': 'Сидоров', 'connection_types': [
        {'type': 'shared_business', 'inns': ['7700000001']}]}]
    social_graph_data = {}


def test_build_from_check_combines_sources_and_extra_edges():
    extra = [{'kind': 'person', 'name': 'Co Owner', 'inn': '770000000050',
              'relation': 'co_owner', 'via': 'ООО Ромашка', 'source': 'ЕГРЮЛ', 'confidence': 'strong'}]
    conns = cg.build_from_check(_Check(), extra_edges=extra, include_cross_checks=True)
    names = {c.name for c in conns}
    assert 'ООО Ромашка' in names and 'Сидоров' in names and 'Co Owner' in names
