"""
Unit tests for kad_arbitr_service — person search against kad.arbitr.ru.

All HTTP is mocked. The request/response schema mirrors the deployed
company-side client; these tests pin the person-specific behavior:
INN-first strategy, side matching (full ФИО subset / initials / INN),
namesake rejection, and the status contract ('blocked' != clean record).
"""

from unittest.mock import MagicMock, patch

import pytest
import requests as _requests

from app.services.phase3.kad_arbitr_service import (
    _convert_iso_date,
    _is_person_inn,
    _item_to_record,
    _match_side_to_person,
    _pick_person_side,
    search_kad_arbitr_person,
)

FULL_NAME = 'Иванов Иван Иванович'
INN12 = '771234567890'


# ── fixtures ──────────────────────────────────────────────────────────────

def _resp(status=200, payload=None, bad_json=False):
    resp = MagicMock()
    resp.status_code = status
    if bad_json:
        resp.json.side_effect = ValueError('not json')
    else:
        resp.json.return_value = payload if payload is not None else {}
    return resp


def _result(items, total=None):
    return {'Result': {'Items': items,
                       'TotalCount': total if total is not None else len(items)}}


def _side(name=FULL_NAME, inn='', side_type=1):
    side = {'Name': name, 'SideType': {'Id': side_type, 'Name': 'Ответчик'}}
    if inn:
        side['Inn'] = inn
    return side


def _item(case_number='А40-100/2024', court='АС города Москвы',
          date='2024-03-15T00:00:00', subject='О взыскании задолженности',
          case_id='abc123', sides=None):
    return {
        'CaseNumber': case_number,
        'CourtName': court,
        'DateTime': date,
        'Subject': subject,
        'CaseId': case_id,
        'Sides': sides if sides is not None else [_side()],
    }


def _run(posts, full_name=FULL_NAME, inn='', **kwargs):
    """Run search_kad_arbitr_person with mocked Session; returns
    (records, status, session_mock)."""
    with patch('app.services.phase3.kad_arbitr_service.requests.Session') as MockSession, \
         patch('app.services.phase3.kad_arbitr_service.time.sleep'):
        sess = MockSession.return_value
        if isinstance(posts, (list, tuple)):
            sess.post.side_effect = list(posts)
        else:
            # callable or exception instance — hand to mock as-is
            sess.post.side_effect = posts
        records, status = search_kad_arbitr_person(full_name, inn=inn, **kwargs)
    return records, status, sess


def _post_payload(sess, call_index=0):
    return sess.post.call_args_list[call_index].kwargs['json']


# ── _is_person_inn ────────────────────────────────────────────────────────

class TestIsPersonInn:

    def test_12_digit_accepted(self):
        assert _is_person_inn(INN12) is True

    def test_10_digit_company_inn_rejected(self):
        assert _is_person_inn('7712345678') is False

    def test_non_digits_rejected(self):
        assert _is_person_inn('77123456789x') is False

    def test_empty_rejected(self):
        assert _is_person_inn('') is False


# ── _match_side_to_person ─────────────────────────────────────────────────

class TestMatchSideToPerson:

    def test_full_three_part_match(self):
        assert _match_side_to_person('Иванов Иван Иванович', FULL_NAME) == 'full'

    def test_ip_prefix_matches(self):
        assert _match_side_to_person('ИП Иванов Иван Иванович', FULL_NAME) == 'full'

    def test_different_patronymic_rejected(self):
        """Namesake with another patronymic must NOT be attributed."""
        assert _match_side_to_person('Иванов Иван Петрович', FULL_NAME) is None

    def test_different_surname_rejected(self):
        assert _match_side_to_person('Петров Иван Иванович', FULL_NAME) is None

    def test_initials_match(self):
        assert _match_side_to_person('Иванов И.И.', FULL_NAME) == 'initials'

    def test_initials_with_spaces_match(self):
        assert _match_side_to_person('Иванов И. И.', FULL_NAME) == 'initials'

    def test_wrong_initials_rejected(self):
        assert _match_side_to_person('Иванов И.П.', FULL_NAME) is None

    def test_single_initial_for_three_part_name_rejected(self):
        assert _match_side_to_person('Иванов И.', FULL_NAME) is None

    def test_parenthesized_annotations_stripped(self):
        assert _match_side_to_person(
            'Иванов Иван Иванович (г. Москва, ИНН 771234567890)', FULL_NAME,
        ) == 'full'

    def test_single_word_query_rejected(self):
        assert _match_side_to_person('Иванов Иван Иванович', 'Иванов') is None

    def test_two_part_candidate_matches_fuller_side(self):
        assert _match_side_to_person('Иванов Иван Иванович', 'Иванов Иван') == 'full'

    def test_empty_inputs(self):
        assert _match_side_to_person('', FULL_NAME) is None
        assert _match_side_to_person('Иванов И.И.', '') is None


# ── _pick_person_side ─────────────────────────────────────────────────────

class TestPickPersonSide:

    def test_inn_equality_wins(self):
        sides = [_side(name='Какой-то Другой Человек', inn=INN12, side_type=2)]
        role, matched_by = _pick_person_side(sides, FULL_NAME, INN12)
        assert matched_by == 'inn'
        assert role == 'истец'

    def test_name_match_with_conflicting_inn_rejected(self):
        """Side name matches but its INN differs — that's a namesake."""
        sides = [_side(name=FULL_NAME, inn='999999999999')]
        role, matched_by = _pick_person_side(sides, FULL_NAME, INN12)
        assert matched_by is None

    def test_full_match_beats_initials(self):
        sides = [
            _side(name='Иванов И.И.', side_type=2),
            _side(name=FULL_NAME, side_type=1),
        ]
        role, matched_by = _pick_person_side(sides, FULL_NAME, '')
        assert matched_by == 'full'
        assert role == 'ответчик'

    def test_side_type_as_plain_int(self):
        sides = [{'Name': FULL_NAME, 'SideType': 3}]
        role, matched_by = _pick_person_side(sides, FULL_NAME, '')
        assert role == 'заявитель'
        assert matched_by == 'full'

    def test_side_type_missing_gives_empty_role(self):
        sides = [{'Name': FULL_NAME}]
        role, matched_by = _pick_person_side(sides, FULL_NAME, '')
        assert role == ''
        assert matched_by == 'full'

    def test_non_dict_sides_skipped(self):
        role, matched_by = _pick_person_side(['garbage', None], FULL_NAME, '')
        assert matched_by is None

    def test_no_match_returns_none(self):
        sides = [_side(name='ООО Ромашка')]
        role, matched_by = _pick_person_side(sides, FULL_NAME, '')
        assert (role, matched_by) == (None, None)


# ── _convert_iso_date / _item_to_record ───────────────────────────────────

class TestConversion:

    def test_iso_date_converted(self):
        assert _convert_iso_date('2024-03-15T00:00:00') == '15.03.2024'

    def test_bad_date_empty(self):
        assert _convert_iso_date('') == ''
        assert _convert_iso_date('2024') == ''

    def test_bankruptcy_case_type(self):
        item = _item(subject='О несостоятельности (банкротстве) гражданина')
        rec = _item_to_record(item, FULL_NAME, '', 'name')
        assert rec['case_type'] == 'банкротное'

    def test_regular_case_type(self):
        rec = _item_to_record(_item(), FULL_NAME, '', 'name')
        assert rec['case_type'] == 'арбитражное'

    def test_url_built_from_case_id(self):
        rec = _item_to_record(_item(case_id='xyz-9'), FULL_NAME, '', 'name')
        assert rec['url'] == 'https://kad.arbitr.ru/Card/xyz-9'

    def test_no_case_number_dropped(self):
        assert _item_to_record(_item(case_number=''), FULL_NAME, '', 'name') is None

    def test_name_query_unmatched_item_dropped(self):
        item = _item(sides=[_side(name='Сидоров Пётр Петрович')])
        assert _item_to_record(item, FULL_NAME, '', 'name') is None

    def test_inn_query_keeps_item_even_without_side_echo(self):
        """kad matched the INN itself; missing Inn in response sides is fine."""
        item = _item(sides=[_side(name='Сидоров Пётр Петрович')])
        rec = _item_to_record(item, FULL_NAME, INN12, 'inn')
        assert rec is not None
        assert rec['matched_by'] == 'inn'


# ── search_kad_arbitr_person ──────────────────────────────────────────────

class TestSearchInnFirst:

    def test_inn_hit_skips_name_query(self):
        posts = [_resp(payload=_result([_item(sides=[_side(inn=INN12)])]))]
        records, status, sess = _run(posts, inn=INN12)
        assert status == 'ok'
        assert len(records) == 1
        assert records[0]['matched_by'] == 'inn'
        assert sess.post.call_count == 1
        assert _post_payload(sess)['Sides'][0]['Inn'] == INN12

    def test_inn_empty_falls_back_to_name_query(self):
        posts = [
            _resp(payload=_result([])),               # INN query: nothing
            _resp(payload=_result([_item()])),        # name query: 1 case
        ]
        records, status, sess = _run(posts, inn=INN12)
        assert status == 'ok'
        assert len(records) == 1
        assert records[0]['matched_by'] == 'full'
        assert sess.post.call_count == 2
        assert _post_payload(sess, 1)['Sides'][0]['Name'] == FULL_NAME

    def test_company_10_digit_inn_not_queried(self):
        posts = [_resp(payload=_result([_item()]))]
        records, status, sess = _run(posts, inn='7712345678')
        assert sess.post.call_count == 1
        assert _post_payload(sess)['Sides'][0]['Name'] == FULL_NAME
        assert _post_payload(sess)['Sides'][0]['Inn'] == ''

    def test_empty_inputs_skipped_without_http(self):
        with patch('app.services.phase3.kad_arbitr_service.requests.Session') as MockSession:
            records, status = search_kad_arbitr_person('', inn='')
        assert (records, status) == ([], 'skipped')
        MockSession.assert_not_called()


class TestSearchStatuses:

    def test_451_blocked_aborts_everything(self):
        posts = [_resp(status=451)]
        records, status, sess = _run(posts, inn=INN12)
        assert (records, status) == ([], 'blocked')
        assert sess.post.call_count == 1  # name query NOT attempted after 451

    def test_451_after_records_keeps_them(self):
        page1 = [_item(case_number=f'А40-{i}/2024') for i in range(25)]
        posts = [
            _resp(payload=_result(page1, total=30)),
            _resp(status=451),
        ]
        records, status, sess = _run(posts)
        assert status == 'ok'
        assert len(records) == 25

    def test_429_rate_limited(self):
        records, status, _ = _run([_resp(status=429)])
        assert (records, status) == ([], 'rate_limited')

    def test_timeout(self):
        records, status, _ = _run(_requests.Timeout('boom'))
        assert (records, status) == ([], 'timeout')

    def test_network_error(self):
        records, status, _ = _run(_requests.ConnectionError('refused'))
        assert (records, status) == ([], 'error')

    def test_http_500(self):
        records, status, _ = _run([_resp(status=500)])
        assert (records, status) == ([], 'http_error')

    def test_bad_json(self):
        records, status, _ = _run([_resp(bad_json=True)])
        assert (records, status) == ([], 'error')

    def test_no_cases_empty(self):
        records, status, _ = _run([_resp(payload=_result([]))])
        assert (records, status) == ([], 'empty')

    def test_inn_failure_then_name_success_is_ok(self):
        posts = [
            _resp(status=500),                        # INN query fails
            _resp(payload=_result([_item()])),        # name query succeeds
        ]
        records, status, _ = _run(posts, inn=INN12)
        assert status == 'ok'
        assert len(records) == 1


class TestSearchPaginationAndFiltering:

    def test_pagination_fetches_next_page(self):
        page1 = [_item(case_number=f'А40-{i}/2024') for i in range(25)]
        page2 = [_item(case_number=f'А41-{i}/2024') for i in range(5)]
        posts = [
            _resp(payload=_result(page1, total=30)),
            _resp(payload=_result(page2, total=30)),
        ]
        records, status, sess = _run(posts)
        assert len(records) == 30
        assert sess.post.call_count == 2
        assert _post_payload(sess, 1)['Page'] == 2

    def test_dedup_across_pages(self):
        item = _item()
        posts = [
            _resp(payload=_result([item] * 3, total=60)),
            _resp(payload=_result([item], total=60)),
        ]
        records, _, _ = _run(posts)
        assert len(records) == 1

    def test_namesake_only_results_give_empty(self):
        item = _item(sides=[_side(name='Иванов Иван Петрович')])
        records, status, _ = _run([_resp(payload=_result([item]))])
        assert (records, status) == ([], 'empty')

    def test_name_query_with_known_inn_rejects_conflicting_side(self):
        posts = [
            _resp(payload=_result([])),  # INN query: nothing
            _resp(payload=_result(
                [_item(sides=[_side(inn='999999999999')])]
            )),
        ]
        records, status, _ = _run(posts, inn=INN12)
        assert (records, status) == ([], 'empty')

    def test_lowercase_response_keys(self):
        payload = {'result': {'items': [{
            'caseNumber': 'А40-7/2024',
            'courtName': 'АС города Москвы',
            'dateTime': '2024-01-09T00:00:00',
            'subject': '',
            'caseId': 'low-1',
            'sides': [{'name': FULL_NAME, 'SideType': {'Id': 2}}],
        }], 'totalCount': 1}}
        records, status, _ = _run([_resp(payload=payload)])
        assert status == 'ok'
        assert records[0]['case_number'] == 'А40-7/2024'
        assert records[0]['date'] == '09.01.2024'
        assert records[0]['role'] == 'истец'

    def test_record_fields_complete(self):
        records, _, _ = _run([_resp(payload=_result([_item()]))])
        rec = records[0]
        assert rec['case_number'] == 'А40-100/2024'
        assert rec['court_name'] == 'АС города Москвы'
        assert rec['date'] == '15.03.2024'
        assert rec['role'] == 'ответчик'
        assert rec['subject'] == 'О взыскании задолженности'
        assert rec['url'] == 'https://kad.arbitr.ru/Card/abc123'
        assert rec['source'] == 'kad.arbitr.ru'
        assert rec['matched_by'] == 'full'
