"""
Tests for BankruptcyService — filter logic, API response parsing, helpers.
No live HTTP calls — all network interactions are mocked.
"""

import pytest
from unittest.mock import MagicMock, patch

from app.services.candidate.bankruptcy_service import (
    BankruptcyRecord,
    BankruptcyService,
    ACTIVE_STAGES,
    COMPLETED_STAGES,
)


# ── Helpers ────────────────────────────────────────────────────────────────

def make_record(name='', inn=None, case_number=None, stage=None, is_active=False):
    return BankruptcyRecord(
        debtor_name=name,
        debtor_inn=inn,
        case_number=case_number,
        stage=stage,
        is_active=is_active,
    )


def make_svc():
    return BankruptcyService(timeout=5)


# ── _filter_results ────────────────────────────────────────────────────────

class TestFilterResults:

    def test_empty_records_returns_empty(self):
        svc = make_svc()
        assert svc._filter_results([], 'Иванов Иван Иванович') == []

    def test_inn_exact_match_wins(self):
        svc = make_svc()
        match = make_record(name='Иванов Иван Иванович', inn='771234567890')
        other = make_record(name='Петров Петр Петрович', inn='771234567891')
        result = svc._filter_results([match, other], 'Иванов Иван Иванович', inn='771234567890')
        assert result == [match]

    def test_inn_match_returns_immediately_ignoring_name(self):
        """INN match should win even if the name in the record differs."""
        svc = make_svc()
        # Same INN, slightly different name spelling (data entry variation)
        rec = make_record(name='Иванов Иван', inn='771234567890')
        result = svc._filter_results([rec], 'Иванов Иван Иванович', inn='771234567890')
        assert result == [rec]

    def test_full_name_exact_match(self):
        svc = make_svc()
        rec = make_record(name='Иванов Иван Иванович')
        result = svc._filter_results([rec], 'Иванов Иван Иванович')
        assert result == [rec]

    def test_two_of_three_parts_match(self):
        svc = make_svc()
        # Record has last name + first name but no patronymic
        rec = make_record(name='Иванов Иван')
        result = svc._filter_results([rec], 'Иванов Иван Иванович')
        assert result == [rec]

    def test_unrelated_name_filtered_out(self):
        svc = make_svc()
        rec = make_record(name='Сидоров Борис Аркадьевич')
        result = svc._filter_results([rec], 'Иванов Иван Иванович')
        assert result == []

    def test_no_match_returns_empty_not_all(self):
        """When nothing matches, must return [] — not the original list."""
        svc = make_svc()
        recs = [
            make_record(name='Сидоров Борис'),
            make_record(name='Кузнецов Андрей'),
        ]
        result = svc._filter_results(recs, 'Иванов Иван Иванович')
        assert result == []

    def test_record_without_name_is_kept(self):
        """Records with no parsed name matched on search string — keep them."""
        svc = make_svc()
        rec = make_record(name='')
        result = svc._filter_results([rec], 'Иванов Иван Иванович')
        assert result == [rec]

    def test_russian_genitive_declension(self):
        """Stem match handles genitive case declension of the same name.

        ЕФРСБ occasionally stores names in genitive:
          Иванов Иван Иванович → Иванова Ивана Ивановича
        Surname + first-name stem both match → same person.
        """
        svc = make_svc()
        rec = make_record(name='Иванова Ивана Ивановича')  # genitive of the same name
        result = svc._filter_results([rec], 'Иванов Иван Иванович')
        assert result == [rec]

    def test_similar_but_different_short_surname_not_falsely_matched(self):
        """Short surnames (<5 chars) skip stem matching — avoid false positives."""
        svc = make_svc()
        rec = make_record(name='Лева Андрей Иванович')
        result = svc._filter_results([rec], 'Лев Борис Сергеевич')
        # 'лева' and 'лев' are only 3-4 chars — stem rule skipped
        # name similarity also low — should not match
        assert result == []

    def test_multiple_records_only_matching_ones_returned(self):
        svc = make_svc()
        rec1 = make_record(name='Иванов Иван Иванович')
        rec2 = make_record(name='Иванов Иван')
        rec3 = make_record(name='Петров Сергей Александрович')
        result = svc._filter_results([rec1, rec2, rec3], 'Иванов Иван Иванович')
        assert rec1 in result
        assert rec2 in result
        assert rec3 not in result

    def test_inn_no_match_falls_through_to_name(self):
        """If INN provided but no record has it, name filter still runs."""
        svc = make_svc()
        rec = make_record(name='Иванов Иван Иванович', inn='000000000000')
        result = svc._filter_results([rec], 'Иванов Иван Иванович', inn='771234567890')
        # INN didn't match (different INN), but name matches
        assert result == [rec]


# ── _parse_api_response ────────────────────────────────────────────────────

class TestParseApiResponse:

    def test_empty_list(self):
        svc = make_svc()
        assert svc._parse_api_response([]) == []

    def test_empty_dict(self):
        svc = make_svc()
        assert svc._parse_api_response({}) == []

    def test_list_of_items(self):
        svc = make_svc()
        data = [
            {
                'name': 'Иванов Иван Иванович',
                'inn': '771234567890',
                'caseNumber': 'А40-12345/2022',
                'procedure': 'Конкурсное производство',
                'courtName': 'Арбитражный суд г. Москвы',
            }
        ]
        records = svc._parse_api_response(data)
        assert len(records) == 1
        r = records[0]
        assert r.debtor_name == 'Иванов Иван Иванович'
        assert r.debtor_inn == '771234567890'
        assert r.case_number == 'А40-12345/2022'
        assert r.stage == 'Конкурсное производство'
        assert r.court_name == 'Арбитражный суд г. Москвы'

    def test_dict_with_pagedata_wrapper(self):
        svc = make_svc()
        data = {
            'pageData': [
                {'name': 'Петров Петр', 'inn': '123456789012'}
            ],
            'total': 1,
        }
        records = svc._parse_api_response(data)
        assert len(records) == 1
        assert records[0].debtor_name == 'Петров Петр'

    def test_dict_with_data_wrapper(self):
        svc = make_svc()
        data = {'data': [{'fullName': 'Сидоров Сидор', 'INN': '987654321098'}]}
        records = svc._parse_api_response(data)
        assert len(records) == 1
        assert records[0].debtor_name == 'Сидоров Сидор'
        assert records[0].debtor_inn == '987654321098'

    def test_active_stage_sets_is_active_true(self):
        svc = make_svc()
        for stage in ACTIVE_STAGES:
            records = svc._parse_api_response([{'name': 'Тест', 'procedure': stage}])
            assert records[0].is_active, f'Expected is_active=True for stage: {stage}'

    def test_completed_stage_sets_is_active_false(self):
        svc = make_svc()
        records = svc._parse_api_response([{'name': 'Тест', 'procedure': 'завершено'}])
        assert not records[0].is_active

    def test_item_without_name_or_inn_skipped(self):
        svc = make_svc()
        data = [{'caseNumber': 'А40-99999/2020'}]  # no name, no inn
        assert svc._parse_api_response(data) == []

    def test_date_iso_format_normalized(self):
        svc = make_svc()
        data = [{'name': 'Тест', 'publishDate': '2023-04-15T00:00:00'}]
        records = svc._parse_api_response(data)
        assert records[0].publication_date == '15.04.2023'

    def test_debtor_url_built_from_guid(self):
        svc = make_svc()
        data = [{'name': 'Тест', 'guid': 'abc-123'}]
        records = svc._parse_api_response(data)
        assert records[0].url == 'https://bankrot.fedresurs.ru/DebtorCard.aspx?id=abc-123'

    def test_non_dict_items_skipped(self):
        svc = make_svc()
        data = [None, 'string', 42, {'name': 'Иванов'}]
        records = svc._parse_api_response(data)
        assert len(records) == 1


# ── _is_active_stage ──────────────────────────────────────────────────────

class TestIsActiveStage:

    def test_none_stage_is_active(self):
        assert BankruptcyService._is_active_stage(None) is True

    def test_known_active_stages(self):
        for stage in ACTIVE_STAGES:
            assert BankruptcyService._is_active_stage(stage) is True, stage

    def test_known_completed_stages(self):
        for stage in COMPLETED_STAGES:
            assert BankruptcyService._is_active_stage(stage) is False, stage

    def test_завершено_substring(self):
        assert BankruptcyService._is_active_stage('Производство завершено') is False

    def test_unknown_stage_is_active(self):
        assert BankruptcyService._is_active_stage('Неизвестная процедура') is True


# ── _format_date ──────────────────────────────────────────────────────────

class TestFormatDate:

    def test_already_dd_mm_yyyy(self):
        assert BankruptcyService._format_date('15.04.2023') == '15.04.2023'

    def test_iso_date(self):
        assert BankruptcyService._format_date('2023-04-15') == '15.04.2023'

    def test_iso_datetime(self):
        assert BankruptcyService._format_date('2023-04-15T12:34:56') == '15.04.2023'

    def test_unknown_format_returned_as_is(self):
        assert BankruptcyService._format_date('April 2023') == 'April 2023'


# ── BankruptcyRecord.to_dict ───────────────────────────────────────────────

class TestBankruptcyRecordToDict:

    def test_type_field_present(self):
        r = BankruptcyRecord(debtor_name='Тест')
        d = r.to_dict()
        assert d['type'] == 'bankruptcy'

    def test_all_fields_serialized(self):
        r = BankruptcyRecord(
            debtor_name='Иванов',
            debtor_inn='123456789012',
            case_number='А40-1/2020',
            court_name='Суд',
            stage='Наблюдение',
            arbitration_manager='Петров',
            publication_date='01.01.2020',
            is_active=True,
            source='bankrot.fedresurs.ru',
            url='https://example.com',
        )
        d = r.to_dict()
        assert d['debtor_name'] == 'Иванов'
        assert d['is_active'] is True
        assert d['source'] == 'bankrot.fedresurs.ru'


# ── _search_fedresurs_api (mocked) ────────────────────────────────────────

class TestSearchFedresursApi:

    def test_returns_none_on_request_exception(self):
        import requests as _requests
        svc = make_svc()
        with patch.object(svc.session, 'get', side_effect=_requests.RequestException('timeout')):
            result = svc._search_fedresurs_api('Иванов Иван')
        assert result is None

    def test_returns_none_on_non_200(self):
        svc = make_svc()
        mock_resp = MagicMock()
        mock_resp.status_code = 403
        with patch.object(svc.session, 'get', return_value=mock_resp):
            result = svc._search_fedresurs_api('Иванов Иван')
        assert result is None

    def test_returns_none_on_html_response(self):
        svc = make_svc()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {'Content-Type': 'text/html'}
        mock_resp.text = '<html><body>blocked</body></html>'
        with patch.object(svc.session, 'get', return_value=mock_resp):
            result = svc._search_fedresurs_api('Иванов Иван')
        assert result is None

    def test_parses_valid_json_response(self):
        svc = make_svc()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {'Content-Type': 'application/json'}
        mock_resp.text = '[{"name":"Иванов Иван","inn":"771234567890"}]'
        mock_resp.json.return_value = [{'name': 'Иванов Иван', 'inn': '771234567890'}]
        with patch.object(svc.session, 'get', return_value=mock_resp):
            result = svc._search_fedresurs_api('Иванов Иван')
        assert result is not None
        assert len(result) == 1
        assert result[0].debtor_name == 'Иванов Иван'

    def test_returns_empty_list_on_no_results(self):
        svc = make_svc()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {'Content-Type': 'application/json'}
        mock_resp.text = '[]'
        mock_resp.json.return_value = []
        with patch.object(svc.session, 'get', return_value=mock_resp):
            result = svc._search_fedresurs_api('НенайденныйЧеловек')
        assert result == []


# ── search() integration (mocked) ────────────────────────────────────────

class TestSearchIntegration:

    def test_returns_filtered_results_when_api_succeeds(self):
        svc = make_svc()
        api_data = [
            {'name': 'Иванов Иван Иванович', 'inn': '771234567890',
             'procedure': 'Конкурсное производство'},
            {'name': 'Иванов Степан Борисович', 'inn': '771234567891'},
        ]
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {'Content-Type': 'application/json'}
        mock_resp.text = str(api_data)
        mock_resp.json.return_value = api_data

        with patch.object(svc.session, 'get', return_value=mock_resp):
            results = svc.search('Иванов Иван Иванович', inn='771234567890')

        # INN match wins — only the first record returned
        assert len(results) == 1
        assert results[0].debtor_inn == '771234567890'

    def test_falls_through_to_manual_when_all_fail(self):
        svc = make_svc()
        with patch.object(svc, '_search_fedresurs_api', return_value=None), \
             patch.object(svc, '_search_api', return_value=None):
            results = svc.search('Иванов Иван Иванович')

        assert len(results) == 1
        assert results[0].source == 'manual'
        assert 'fedresurs.ru' in results[0].url

    def test_no_false_positives_for_common_name(self):
        """When the primary API returns results for a different person with
        the same surname, _filter_results returns [] and search returns []
        (no bankruptcy found) rather than the mismatched records."""
        svc = make_svc()
        # API returns a different Иванов — same surname, different given name
        api_data = [{'name': 'Иванов Борис Аркадьевич', 'inn': '339900112233'}]
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {'Content-Type': 'application/json'}
        mock_resp.text = str(api_data)
        mock_resp.json.return_value = api_data

        with patch.object(svc.session, 'get', return_value=mock_resp), \
             patch.object(svc, '_search_api', return_value=None):
            results = svc.search('Иванов Иван Иванович', inn='771234567890')

        # INN mismatch + name similarity below threshold (shared surname only)
        # → filter returns [] → search returns [] (no false positives)
        non_manual = [r for r in results if r.source != 'manual']
        assert non_manual == [], f'Expected no non-manual records, got: {non_manual}'
