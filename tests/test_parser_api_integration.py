"""
parser-api.com integration tests (#9 kad + #11-13 fssp).

parser-api.com proxies kad.arbitr.ru and ФССП server-side, so it works from
any IP. These tests mock all HTTP — no real requests, no quota burn, and no
real API key. They pin: the client's status model, the arbitr case→record
mapping (role/INN/namesake), and that the services prefer parser-api when
PARSER_API_KEY is set and fall back when it is not.
"""

from unittest.mock import MagicMock, patch

import pytest
import requests as _requests

from app.services import parser_api


def _resp(status=200, payload=None, bad_json=False):
    r = MagicMock()
    r.status_code = status
    if bad_json:
        r.json.side_effect = ValueError('not json')
    else:
        r.json.return_value = payload if payload is not None else {}
    return r


@pytest.fixture
def key(monkeypatch):
    monkeypatch.setenv('PARSER_API_KEY', 'test-key-not-real')


@pytest.fixture
def no_key(monkeypatch):
    monkeypatch.delenv('PARSER_API_KEY', raising=False)


# ── client status model ───────────────────────────────────────────────────

class TestClientStatus:

    def test_not_configured_without_key(self, no_key):
        assert parser_api.is_available() is False
        cases, status = parser_api.arbitr_search('7736050003')
        assert (cases, status) == ([], 'not_configured')

    def test_available_with_key(self, key):
        assert parser_api.is_available() is True

    def test_rate_limited_429(self, key):
        with patch.object(parser_api.requests, 'get', return_value=_resp(429)):
            cases, status = parser_api.arbitr_search('x')
        assert status == 'rate_limited'

    def test_blocked_401(self, key):
        with patch.object(parser_api.requests, 'get', return_value=_resp(401)):
            cases, status = parser_api.arbitr_search('x')
        assert status == 'blocked'

    def test_timeout(self, key):
        with patch.object(parser_api.requests, 'get', side_effect=_requests.Timeout('t')):
            cases, status = parser_api.arbitr_search('x')
        assert status == 'timeout'


# ── arbitr_search ──────────────────────────────────────────────────────────

def _arbitr_case(num='А40-1/2024', cid='c1'):
    return {
        'CaseId': cid, 'CaseNumber': num, 'CaseType': 'Г',
        'Court': 'АС Москвы', 'StartDate': '2024-03-15',
        'Plaintiffs': [{'Name': 'ООО Ромашка', 'Inn': '7700000001'}],
        'Respondents': [{'Name': 'Иванов Иван Иванович', 'Inn': '771234567890'}],
        'Thirds': [], 'Others': [],
    }


class TestArbitrSearch:

    def test_ok_with_cases(self, key):
        payload = {'Success': True, 'Cases': [_arbitr_case()], 'PagesCount': 1}
        with patch.object(parser_api.requests, 'get', return_value=_resp(200, payload)):
            cases, status = parser_api.arbitr_search('771234567890')
        assert status == 'ok'
        assert len(cases) == 1

    def test_empty(self, key):
        payload = {'Success': True, 'Cases': [], 'PagesCount': 1}
        with patch.object(parser_api.requests, 'get', return_value=_resp(200, payload)):
            cases, status = parser_api.arbitr_search('x')
        assert (cases, status) == ([], 'empty')

    def test_dedup_across_pages(self, key):
        page = {'Success': True, 'Cases': [_arbitr_case(cid='dup')], 'PagesCount': 2}
        with patch.object(parser_api.requests, 'get', return_value=_resp(200, page)):
            cases, status = parser_api.arbitr_search('x', max_pages=2)
        assert len(cases) == 1  # same CaseId deduped


# ── fssp_search_fiz ────────────────────────────────────────────────────────

class TestFsspSearchFiz:

    def test_done_1_with_results(self, key):
        payload = {'done': 1, 'result': [{'debtor_name': 'Иванов И.И.'}]}
        with patch.object(parser_api.requests, 'get', return_value=_resp(200, payload)):
            rows, status = parser_api.fssp_search_fiz('Иванов', 'Иван', 'Иванович', '1990-01-01')
        assert status == 'ok'
        assert len(rows) == 1

    def test_done_0_no_result_is_empty(self, key):
        payload = {'done': 0, 'result': [], 'error': 'not found'}
        with patch.object(parser_api.requests, 'get', return_value=_resp(400, payload)):
            rows, status = parser_api.fssp_search_fiz('X', 'Y', '', '1990-01-01')
        assert (rows, status) == ([], 'empty')

    def test_missing_names_skipped(self, key):
        assert parser_api.fssp_search_fiz('', '', '', '')[1] == 'skipped'


# ── kad_arbitr_service: parser-api case mapping + provider preference ──────

from app.services.phase3 import kad_arbitr_service as kad

FULL = 'Иванов Иван Иванович'
INN12 = '771234567890'


class TestKadParserMapping:

    def test_role_from_respondents_array(self):
        rec = kad._record_from_parser_case(_arbitr_case(), FULL, '', 'name')
        assert rec is not None
        assert rec['role'] == 'ответчик'
        assert rec['matched_by'] == 'full'
        assert rec['source'] == 'kad.arbitr.ru'
        assert rec['date'] == '15.03.2024'

    def test_inn_match(self):
        rec = kad._record_from_parser_case(_arbitr_case(), FULL, INN12, 'inn')
        assert rec['matched_by'] == 'inn'
        assert rec['role'] == 'ответчик'

    def test_namesake_different_inn_dropped(self):
        case = _arbitr_case()
        case['Respondents'] = [{'Name': FULL, 'Inn': '999999999999'}]
        rec = kad._record_from_parser_case(case, FULL, INN12, 'name')
        assert rec is None

    def test_name_query_unmatched_dropped(self):
        case = _arbitr_case()
        case['Respondents'] = [{'Name': 'Сидоров Пётр Петрович', 'Inn': ''}]
        case['Plaintiffs'] = [{'Name': 'ООО Ромашка', 'Inn': '7700000001'}]
        assert kad._record_from_parser_case(case, FULL, '', 'name') is None

    def test_bankruptcy_case_type(self):
        case = _arbitr_case()
        case['CaseType'] = 'Б'
        rec = kad._record_from_parser_case(case, FULL, '', 'name')
        assert rec['case_type'] == 'банкротное'


class TestKadProviderPreference:

    def test_uses_parser_api_when_available(self, key):
        with patch('app.services.parser_api.arbitr_search',
                   return_value=([_arbitr_case()], 'ok')) as mock_search:
            records, status = kad.search_kad_arbitr_person(FULL, inn='')
        assert status == 'ok'
        assert len(records) == 1
        assert mock_search.called

    def test_falls_back_to_direct_when_no_key(self, no_key):
        # parser-api not configured → goes to the direct kad path, which we
        # stub to a blocked geo-response (the dev-machine reality).
        with patch.object(kad, '_fetch_page', return_value=(None, 0, 'blocked')):
            records, status = kad.search_kad_arbitr_person(FULL, inn=INN12)
        assert status == 'blocked'

    def test_parser_api_empty_falls_through_to_direct(self, key):
        with patch('app.services.parser_api.arbitr_search', return_value=([], 'empty')), \
             patch.object(kad, '_fetch_page', return_value=(None, 0, 'blocked')):
            records, status = kad.search_kad_arbitr_person(FULL, inn=INN12)
        # parser-api empty → direct attempted → blocked from dev IP
        assert status == 'blocked'


# ── fssp_service: parser-api mapping + provider path ───────────────────────

from app.services.candidate import fssp_service


class TestFsspParserMapping:

    def test_maps_full_row(self):
        row = {
            'debtor_name': 'Иванов Иван Иванович',
            'debtor_dob': '1990-01-01',
            'process_title': 'Исполнительное производство 12345/23/77001-ИП',
            'process_total': '50 000 руб.',
            'subjects': [{'title': 'Задолженность по кредиту', 'sum': '50000'}],
            'department_title': 'ОСП по ЦАО',
            'officer_name': 'Петров П.П.',
            'document_num': 'ФС 12345',
            'stop_date': '',
            'stop_reason': '',
        }
        rec = fssp_service._fssp_record_from_parser(row)
        assert rec.debtor_name == 'Иванов Иван Иванович'
        assert rec.proceedings_number == '12345/23/77001-ИП'
        assert rec.amount == 50000.0
        assert rec.subject == 'Задолженность по кредиту'
        assert rec.department == 'ОСП по ЦАО'
        assert rec.is_active is True
        assert rec.source == 'api-ip.fssp.gov.ru'

    def test_stopped_proceeding_inactive(self):
        row = {'debtor_name': 'X', 'process_title': 'y', 'stop_date': '2023-05-01',
               'stop_reason': 'окончено', 'subjects': []}
        rec = fssp_service._fssp_record_from_parser(row)
        assert rec.is_active is False
        assert rec.end_date == '2023-05-01'

    def test_search_via_parser_not_configured(self, no_key):
        assert fssp_service.search_fssp_via_parser_api('Иванов Иван', '1990-01-01')[1] == 'not_configured'

    def test_search_via_parser_ok(self, key):
        with patch('app.services.parser_api.fssp_search_fiz',
                   return_value=([{'debtor_name': 'Иванов', 'process_title': '1/2/3-ИП',
                                   'subjects': []}], 'ok')):
            records, status = fssp_service.search_fssp_via_parser_api('Иванов Иван Иванович', '1990-01-01')
        assert status == 'ok'
        assert len(records) == 1
