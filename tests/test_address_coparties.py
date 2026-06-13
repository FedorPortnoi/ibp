"""
Tests for extract_address_coparties (address_intelligence.py).
"""
import pytest
from app.services.phase3.address_intelligence import extract_address_coparties

ADDRESS = 'г. Москва, ул. Ленина, д. 1'
CANDIDATE_INN = '7701234567'

CONNECTIONS = [
    # Company — 10-digit INN, should become kind='company', confidence='strong'
    {'name': 'ООО Ромашка', 'inn': '7709876543', 'ogrn': '1027700123456', 'status': 'active'},
    # Person — 12-digit INN (individual), kind='person', confidence='strong'
    {'name': 'Иванов Иван Иванович', 'inn': '770901234567', 'ogrn': '', 'status': 'active'},
    # Candidate's own entry — must be excluded
    {'name': 'Кандидат ООО', 'inn': CANDIDATE_INN, 'ogrn': '1027700999999', 'status': 'active'},
]


def test_basic_edges():
    edges = extract_address_coparties(CONNECTIONS, ADDRESS, CANDIDATE_INN)
    assert len(edges) == 2


def test_company_edge():
    edges = extract_address_coparties(CONNECTIONS, ADDRESS, CANDIDATE_INN)
    company = next(e for e in edges if e['inn'] == '7709876543')
    assert company['kind'] == 'company'
    assert company['name'] == 'ООО Ромашка'
    assert company['ogrn'] == '1027700123456'
    assert company['relation'] == 'co_registered'
    assert company['label'] == 'Один адрес регистрации'
    assert company['via'] == ADDRESS
    assert company['source'] == 'ЕГРЮЛ (адрес)'
    assert company['confidence'] == 'strong'


def test_person_edge():
    edges = extract_address_coparties(CONNECTIONS, ADDRESS, CANDIDATE_INN)
    person = next(e for e in edges if e['name'] == 'Иванов Иван Иванович')
    assert person['kind'] == 'person'
    assert person['inn'] == '770901234567'
    assert person['confidence'] == 'strong'
    assert person['via'] == ADDRESS


def test_candidate_excluded():
    edges = extract_address_coparties(CONNECTIONS, ADDRESS, CANDIDATE_INN)
    inns = [e['inn'] for e in edges]
    assert CANDIDATE_INN not in inns


def test_empty_connections():
    assert extract_address_coparties([], ADDRESS, CANDIDATE_INN) == []


def test_none_connections():
    assert extract_address_coparties(None, ADDRESS, CANDIDATE_INN) == []


def test_no_address_uses_fallback_via():
    edges = extract_address_coparties(CONNECTIONS[:1], '', '')
    assert edges[0]['via'] == 'общий адрес регистрации'


def test_weak_confidence_when_no_inn():
    conn = [{'name': 'Петров Пётр Петрович', 'inn': '', 'ogrn': '', 'status': 'active'}]
    edges = extract_address_coparties(conn, ADDRESS, '')
    assert edges[0]['confidence'] == 'weak'


def test_empty_name_skipped():
    conn = [{'name': '', 'inn': '7709999999', 'ogrn': '', 'status': 'active'}]
    assert extract_address_coparties(conn, ADDRESS, '') == []


def test_legal_form_prefix_makes_company():
    for prefix in ('ООО', 'ОАО', 'ЗАО', 'ПАО', 'АО', 'НКО', 'АНО'):
        conn = [{'name': f'{prefix} Тест', 'inn': '123', 'ogrn': '', 'status': 'active'}]
        edges = extract_address_coparties(conn, ADDRESS, '')
        assert edges[0]['kind'] == 'company', f'Failed for prefix {prefix}'


def test_10_digit_inn_makes_company_regardless_of_name():
    conn = [{'name': 'Кто-то непонятный', 'inn': '7701112233', 'ogrn': '', 'status': ''}]
    edges = extract_address_coparties(conn, ADDRESS, '')
    assert edges[0]['kind'] == 'company'


def test_candidate_not_excluded_when_inn_unknown():
    """If either INN is absent, the entry must NOT be skipped."""
    conn = [{'name': 'Похожий кандидат', 'inn': '', 'ogrn': '', 'status': ''}]
    edges = extract_address_coparties(conn, ADDRESS, CANDIDATE_INN)
    assert len(edges) == 1


def test_malformed_entry_skipped():
    """Non-dict entries must not raise."""
    conn = [None, 42, 'bad', {'name': 'Нормальный', 'inn': '770111222333', 'ogrn': ''}]
    edges = extract_address_coparties(conn, ADDRESS, '')
    assert len(edges) == 1
    assert edges[0]['name'] == 'Нормальный'
