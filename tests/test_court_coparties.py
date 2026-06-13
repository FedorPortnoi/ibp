"""
Unit tests for extract_court_coparties() in kad_arbitr_service.

All tests use inline data — no HTTP, no DB, no fixtures.
"""

import pytest

from app.services.phase3.kad_arbitr_service import extract_court_coparties

# ── shared test data ───────────────────────────────────────────────────────

CASE_NUMBER = 'А40-1/2024'
COURT = 'АС Москвы'

CANDIDATE_INN = '771234567890'  # 12-digit personal INN
CANDIDATE_NAME = 'Иванов Иван Иванович'

# A company plaintiff (10-digit INN → kind='company', confidence='strong')
COMPANY_PLAINTIFF = {
    'Name': 'ООО Ромашка',
    'Address': 'Москва',
    'Inn': '7701234567',  # 10 digits
}

# The candidate as respondent — must be excluded
CANDIDATE_RESPONDENT = {
    'Name': CANDIDATE_NAME,
    'Address': '',
    'Inn': CANDIDATE_INN,
}

# A person third-party (no INN → kind='person', confidence='weak')
PERSON_THIRD = {
    'Name': 'Петров Пётр Петрович',
    'Address': '',
    'Inn': '',
}

STANDARD_CASE = {
    'CaseNumber': CASE_NUMBER,
    'Court': COURT,
    'CaseType': 'А',
    'StartDate': '2024-01-15T00:00:00',
    'Plaintiffs':  [COMPANY_PLAINTIFF],
    'Respondents': [CANDIDATE_RESPONDENT],
    'Thirds':      [PERSON_THIRD],
    'Others':      [],
}


# ── helpers ────────────────────────────────────────────────────────────────

def _find_edge(edges, name):
    return next((e for e in edges if e['name'] == name), None)


# ── main behavioural tests ─────────────────────────────────────────────────

class TestExtractCourtCoparties:

    def test_returns_list(self):
        result = extract_court_coparties([STANDARD_CASE], CANDIDATE_INN, CANDIDATE_NAME)
        assert isinstance(result, list)

    def test_candidate_excluded_by_inn(self):
        result = extract_court_coparties([STANDARD_CASE], CANDIDATE_INN, CANDIDATE_NAME)
        names = [e['name'] for e in result]
        assert CANDIDATE_NAME not in names

    def test_company_plaintiff_present(self):
        result = extract_court_coparties([STANDARD_CASE], CANDIDATE_INN, CANDIDATE_NAME)
        edge = _find_edge(result, 'ООО Ромашка')
        assert edge is not None

    def test_company_kind(self):
        result = extract_court_coparties([STANDARD_CASE], CANDIDATE_INN, CANDIDATE_NAME)
        edge = _find_edge(result, 'ООО Ромашка')
        assert edge['kind'] == 'company'

    def test_company_confidence_strong(self):
        result = extract_court_coparties([STANDARD_CASE], CANDIDATE_INN, CANDIDATE_NAME)
        edge = _find_edge(result, 'ООО Ромашка')
        assert edge['confidence'] == 'strong'

    def test_person_third_present(self):
        result = extract_court_coparties([STANDARD_CASE], CANDIDATE_INN, CANDIDATE_NAME)
        edge = _find_edge(result, 'Петров Пётр Петрович')
        assert edge is not None

    def test_person_kind(self):
        result = extract_court_coparties([STANDARD_CASE], CANDIDATE_INN, CANDIDATE_NAME)
        edge = _find_edge(result, 'Петров Пётр Петрович')
        assert edge['kind'] == 'person'

    def test_person_confidence_weak_no_inn(self):
        result = extract_court_coparties([STANDARD_CASE], CANDIDATE_INN, CANDIDATE_NAME)
        edge = _find_edge(result, 'Петров Пётр Петрович')
        assert edge['confidence'] == 'weak'
        assert edge['inn'] == ''

    def test_label_includes_case_number(self):
        result = extract_court_coparties([STANDARD_CASE], CANDIDATE_INN, CANDIDATE_NAME)
        for edge in result:
            assert CASE_NUMBER in edge['label']

    def test_label_plaintiff_role(self):
        result = extract_court_coparties([STANDARD_CASE], CANDIDATE_INN, CANDIDATE_NAME)
        edge = _find_edge(result, 'ООО Ромашка')
        assert 'истец' in edge['label'].lower()

    def test_label_third_role(self):
        result = extract_court_coparties([STANDARD_CASE], CANDIDATE_INN, CANDIDATE_NAME)
        edge = _find_edge(result, 'Петров Пётр Петрович')
        assert 'третье лицо' in edge['label'].lower()

    def test_via_includes_court(self):
        result = extract_court_coparties([STANDARD_CASE], CANDIDATE_INN, CANDIDATE_NAME)
        for edge in result:
            assert COURT in edge['via']
            assert CASE_NUMBER in edge['via']

    def test_edge_contract_keys(self):
        result = extract_court_coparties([STANDARD_CASE], CANDIDATE_INN, CANDIDATE_NAME)
        required = {'kind', 'name', 'inn', 'ogrn', 'relation', 'label', 'via', 'source', 'confidence'}
        for edge in result:
            assert required <= edge.keys()

    def test_relation_is_co_litigant(self):
        result = extract_court_coparties([STANDARD_CASE], CANDIDATE_INN, CANDIDATE_NAME)
        for edge in result:
            assert edge['relation'] == 'co_litigant'

    def test_source_is_kad(self):
        result = extract_court_coparties([STANDARD_CASE], CANDIDATE_INN, CANDIDATE_NAME)
        for edge in result:
            assert edge['source'] == 'kad.arbitr.ru'

    def test_ogrn_always_empty(self):
        result = extract_court_coparties([STANDARD_CASE], CANDIDATE_INN, CANDIDATE_NAME)
        for edge in result:
            assert edge['ogrn'] == ''

    def test_exactly_two_edges(self):
        # plaintiff (company) + third-party (person); candidate excluded
        result = extract_court_coparties([STANDARD_CASE], CANDIDATE_INN, CANDIDATE_NAME)
        assert len(result) == 2

    def test_candidate_excluded_by_name_when_no_inn(self):
        """Candidate is excluded by normalised name when INN absent."""
        cand_party = {
            'Name': CANDIDATE_NAME,
            'Address': '',
            'Inn': '',  # no INN on the party record
        }
        case = {
            'CaseNumber': 'А40-99/2024',
            'Court': COURT,
            'Plaintiffs': [cand_party],
            'Respondents': [],
            'Thirds':      [],
            'Others':      [],
        }
        result = extract_court_coparties([case], '', CANDIDATE_NAME)
        assert result == []

    def test_yo_normalisation_excludes_candidate(self):
        """ё and е treated the same when matching candidate name."""
        cand_name_yo = 'Фёдоров Фёдор Фёдорович'
        party_ye = {
            'Name': 'Федоров Федор Федорович',  # е instead of ё
            'Address': '',
            'Inn': '',
        }
        case = {
            'CaseNumber': 'А40-2/2024',
            'Court': '',
            'Plaintiffs': [party_ye],
            'Respondents': [],
            'Thirds': [],
            'Others': [],
        }
        result = extract_court_coparties([case], '', cand_name_yo)
        assert result == []

    def test_via_no_court_when_empty(self):
        case = {
            'CaseNumber': 'А40-3/2024',
            'Court': '',
            'Plaintiffs': [COMPANY_PLAINTIFF],
            'Respondents': [],
            'Thirds': [],
            'Others': [],
        }
        result = extract_court_coparties([case], CANDIDATE_INN, CANDIDATE_NAME)
        assert len(result) == 1
        assert result[0]['via'] == 'дело А40-3/2024'

    def test_company_by_legal_form_no_inn(self):
        """ОАО/ЗАО/ПАО with no INN still classified as company."""
        party = {'Name': 'ПАО Газпром', 'Address': '', 'Inn': ''}
        case = {
            'CaseNumber': 'А40-4/2024',
            'Court': COURT,
            'Plaintiffs': [party],
            'Respondents': [],
            'Thirds': [],
            'Others': [],
        }
        result = extract_court_coparties([case], CANDIDATE_INN, CANDIDATE_NAME)
        assert len(result) == 1
        assert result[0]['kind'] == 'company'
        assert result[0]['confidence'] == 'weak'

    def test_person_12_digit_inn_is_person(self):
        """12-digit INN → person even though INN is present."""
        party = {'Name': 'Сидоров Сидор Сидорович', 'Address': '', 'Inn': '123456789012'}
        case = {
            'CaseNumber': 'А40-5/2024',
            'Court': COURT,
            'Plaintiffs': [party],
            'Respondents': [],
            'Thirds': [],
            'Others': [],
        }
        result = extract_court_coparties([case], CANDIDATE_INN, CANDIDATE_NAME)
        assert len(result) == 1
        assert result[0]['kind'] == 'person'
        assert result[0]['confidence'] == 'strong'


# ── defensive / edge cases ─────────────────────────────────────────────────

class TestDefensiveCases:

    def test_empty_list_returns_empty(self):
        assert extract_court_coparties([]) == []

    def test_none_returns_empty(self):
        assert extract_court_coparties(None) == []  # type: ignore[arg-type]

    def test_not_a_list_returns_empty(self):
        assert extract_court_coparties('not a list') == []  # type: ignore[arg-type]

    def test_case_without_case_number_skipped(self):
        case = {'Court': COURT, 'Plaintiffs': [COMPANY_PLAINTIFF]}
        assert extract_court_coparties([case]) == []

    def test_none_arrays_handled(self):
        case = {
            'CaseNumber': 'А40-6/2024',
            'Court': COURT,
            'Plaintiffs':  None,
            'Respondents': None,
            'Thirds':      None,
            'Others':      None,
        }
        assert extract_court_coparties([case]) == []

    def test_missing_arrays_handled(self):
        case = {'CaseNumber': 'А40-7/2024', 'Court': COURT}
        assert extract_court_coparties([case]) == []

    def test_empty_name_party_skipped(self):
        party = {'Name': '', 'Address': '', 'Inn': '7701234567'}
        case = {
            'CaseNumber': 'А40-8/2024',
            'Court': COURT,
            'Plaintiffs': [party],
            'Respondents': [],
            'Thirds': [],
            'Others': [],
        }
        assert extract_court_coparties([case]) == []

    def test_non_dict_party_skipped(self):
        case = {
            'CaseNumber': 'А40-9/2024',
            'Court': COURT,
            'Plaintiffs': ['not a dict', None, 42],
            'Respondents': [],
            'Thirds': [],
            'Others': [],
        }
        assert extract_court_coparties([case]) == []

    def test_non_dict_case_skipped(self):
        result = extract_court_coparties(['bad', None, 123])
        assert result == []
