"""Tests for extract_egrul_coparties — Axis 2 co-director/co-founder edge extraction.

Covers:
- 2 officers + 1 founder → correct edges (relation, inn, name)
- Candidate excluded by INN
- Candidate excluded by name (ё→е normalization, case-insensitive)
- Single-dict (non-list) officer handled without error
- Missing/empty raw → []
- Founder ownership % appears in label
"""
import pytest
from app.services.phase3.business_registry import extract_egrul_coparties


# ── FNS JSON builder helpers ───────────────────────────────────────────────────

def _fl_node(last: str, first: str, middle: str = '', inn: str = '') -> dict:
    """Build a СвФЛ-style node."""
    attrs = {'Фамилия': last, 'Имя': first}
    if middle:
        attrs['Отчество'] = middle
    if inn:
        attrs['ИННФЛ'] = inn
    return {'@attributes': attrs}


def _officer_entry(last: str, first: str, middle: str = '',
                   inn: str = '', role: str = 'Генеральный директор') -> dict:
    return {
        'СвФЛ': _fl_node(last, first, middle, inn),
        'СвДолжн': {'@attributes': {'НаимДолжн': role}},
    }


def _founder_entry(last: str, first: str, middle: str = '',
                   inn: str = '', percent: str = '') -> dict:
    entry = {
        'СвФЛ': _fl_node(last, first, middle, inn),
    }
    if percent:
        entry['ДолУстКап'] = {'@attributes': {'Процент': percent}}
    return entry


def _make_raw(officers=None, founders_fl=None) -> dict:
    """Wrap officer/founder lists into a СвЮЛ root dict."""
    root: dict = {}
    if officers is not None:
        root['СведДолжнФЛ'] = officers
    if founders_fl is not None:
        root['СвУчредит'] = {'УчрФЛ': founders_fl}
    return {'СвЮЛ': root}


# ── Tests ──────────────────────────────────────────────────────────────────────

COMPANY = 'ООО Ромашка'
COMPANY_INN = '7700000001'


def test_two_officers_one_founder_basic():
    """2 officers + 1 founder → 3 edges with correct fields."""
    raw = _make_raw(
        officers=[
            _officer_entry('Иванов', 'Иван', 'Иванович', inn='770100000001',
                           role='Генеральный директор'),
            _officer_entry('Петров', 'Пётр', 'Петрович', inn='770200000002',
                           role='Коммерческий директор'),
        ],
        founders_fl=[
            _founder_entry('Сидоров', 'Сидор', 'Сидорович', inn='770300000003',
                           percent='50'),
        ],
    )

    edges = extract_egrul_coparties(raw, COMPANY, COMPANY_INN)

    assert len(edges) == 3

    directors = [e for e in edges if e['relation'] == 'co_director']
    owners = [e for e in edges if e['relation'] == 'co_owner']

    assert len(directors) == 2
    assert len(owners) == 1

    ivanov = next(e for e in directors if 'Иванов' in e['name'])
    assert ivanov['inn'] == '770100000001'
    assert ivanov['kind'] == 'person'
    assert ivanov['ogrn'] == ''
    assert ivanov['source'] == 'ЕГРЮЛ'
    assert ivanov['confidence'] == 'strong'
    assert COMPANY in ivanov['via']
    assert COMPANY_INN in ivanov['via']

    sidorov = owners[0]
    assert sidorov['inn'] == '770300000003'
    assert sidorov['confidence'] == 'strong'
    assert '50' in sidorov['label']   # percent in label


def test_candidate_excluded_by_inn():
    """Officer whose INN matches candidate_inn is excluded."""
    raw = _make_raw(
        officers=[
            _officer_entry('Кандидат', 'Константин', 'Константинович',
                           inn='999999999999'),
            _officer_entry('Другой', 'Дмитрий', 'Дмитриевич',
                           inn='111111111111'),
        ],
    )

    edges = extract_egrul_coparties(
        raw, COMPANY, COMPANY_INN,
        candidate_inn='999999999999',
    )

    assert len(edges) == 1
    assert edges[0]['inn'] == '111111111111'
    assert 'Другой' in edges[0]['name']


def test_candidate_excluded_by_name():
    """Officer whose normalized name matches candidate_name is excluded (no INN match needed)."""
    raw = _make_raw(
        officers=[
            _officer_entry('Ёлкин', 'Елена', 'Алексеевна'),  # ё in surname
            _officer_entry('Зайцев', 'Захар', 'Захарович', inn='222222222222'),
        ],
    )

    # candidate_name uses е (not ё) — normalization must handle ё→е
    edges = extract_egrul_coparties(
        raw, COMPANY, COMPANY_INN,
        candidate_name='елкин елена алексеевна',
    )

    assert len(edges) == 1
    assert 'Зайцев' in edges[0]['name']


def test_single_dict_officer_not_list():
    """A single officer given as dict (not list) is handled correctly."""
    raw = _make_raw(
        officers=_officer_entry('Одиночный', 'Олег', 'Олегович',
                                inn='333333333333'),
    )

    edges = extract_egrul_coparties(raw, COMPANY, COMPANY_INN)

    assert len(edges) == 1
    assert edges[0]['name'] == 'Одиночный Олег Олегович'
    assert edges[0]['relation'] == 'co_director'


def test_empty_raw_returns_empty_list():
    """Empty dict → []."""
    assert extract_egrul_coparties({}, COMPANY, COMPANY_INN) == []


def test_none_like_raw_returns_empty_list():
    """Raw with no recognizable keys → []."""
    assert extract_egrul_coparties({'garbage': 42}, COMPANY, COMPANY_INN) == []


def test_founder_percent_in_label():
    """Ownership percentage appears in the co_owner label."""
    raw = _make_raw(
        founders_fl=_founder_entry('Акционер', 'Антон', 'Антонович',
                                   inn='444444444444', percent='33.33'),
    )

    edges = extract_egrul_coparties(raw, COMPANY, COMPANY_INN)

    assert len(edges) == 1
    assert '33.33' in edges[0]['label']
    assert edges[0]['relation'] == 'co_owner'


def test_founder_no_percent_label_still_works():
    """Founder without percent → label still formed correctly."""
    raw = _make_raw(
        founders_fl=_founder_entry('Безпроцент', 'Борис', 'Борисович',
                                   inn='555555555555'),
    )

    edges = extract_egrul_coparties(raw, COMPANY, COMPANY_INN)

    assert len(edges) == 1
    assert COMPANY in edges[0]['label']
    assert '%' not in edges[0]['label']


def test_weak_confidence_when_no_inn():
    """Officer without INN gets confidence='weak'."""
    raw = _make_raw(
        officers=[_officer_entry('Безинн', 'Борис', 'Борисович')],
    )

    edges = extract_egrul_coparties(raw, COMPANY, COMPANY_INN)

    assert len(edges) == 1
    assert edges[0]['confidence'] == 'weak'
    assert edges[0]['inn'] == ''


def test_via_string_format():
    """via field is formatted as 'Name (ИНН xxx)'."""
    raw = _make_raw(
        officers=[_officer_entry('Виа', 'Виктор', 'Викторович',
                                 inn='666666666666')],
    )

    edges = extract_egrul_coparties(raw, COMPANY, COMPANY_INN)

    assert edges[0]['via'] == f'{COMPANY} (ИНН {COMPANY_INN})'


def test_via_without_company_inn():
    """When company_inn is empty, via is just the company name."""
    raw = _make_raw(
        officers=[_officer_entry('Безинн', 'Виталий', 'Витальевич',
                                 inn='777777777777')],
    )

    edges = extract_egrul_coparties(raw, COMPANY, company_inn='')

    assert edges[0]['via'] == COMPANY


def test_candidate_excluded_by_both_inn_and_name():
    """When both candidate_inn and candidate_name match, still only excluded once."""
    raw = _make_raw(
        officers=[
            _officer_entry('Двойной', 'Дмитрий', 'Дмитриевич',
                           inn='888888888888'),
        ],
    )

    edges = extract_egrul_coparties(
        raw, COMPANY, COMPANY_INN,
        candidate_inn='888888888888',
        candidate_name='Двойной Дмитрий Дмитриевич',
    )

    assert edges == []


def test_single_dict_founder_not_list():
    """Single founder as dict (not list) is handled without error."""
    raw = _make_raw(
        founders_fl=_founder_entry('Одинфунд', 'Ольга', 'Олеговна',
                                   inn='900000000009', percent='100'),
    )

    edges = extract_egrul_coparties(raw, COMPANY, COMPANY_INN)

    assert len(edges) == 1
    assert edges[0]['relation'] == 'co_owner'
    assert '100' in edges[0]['label']
