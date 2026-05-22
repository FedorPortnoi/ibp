"""Focused regressions for external-service integration drift."""

import pytest

from app.services.candidate.opensanctions_service import OpenSanctionsService
from app.services.phase3.business_registry import BusinessRegistrySearch


pytestmark = pytest.mark.integration


def test_parse_nalog_ul_current_fields_marks_active_director():
    """Current EGRUL rows use `g` for executive text and `e` for end date."""
    row = {
        'c': 'ПАО СБЕРБАНК',
        'g': 'ПРЕЗИДЕНТ, ПРЕДСЕДАТЕЛЬ ПРАВЛЕНИЯ: Греф Герман Оскарович',
        'i': '7707083893',
        'k': 'ul',
        'n': 'ПУБЛИЧНОЕ АКЦИОНЕРНОЕ ОБЩЕСТВО "СБЕРБАНК РОССИИ"',
        'o': '1027700132195',
        'p': '773601001',
        'r': '16.08.2002',
        'rn': 'Г.Москва',
    }

    record = BusinessRegistrySearch()._parse_nalog_row(
        row, 'Греф Герман Оскарович'
    )

    assert record is not None
    assert record.status == 'Действующее'
    assert record.role == 'Директор'
    assert record.address == 'Г.Москва'
    assert record.inn == '7707083893'


def test_parse_nalog_ul_uses_e_as_liquidation_date():
    row = {
        'c': 'ООО "ТЕСТ"',
        'e': '01.01.2020',
        'g': 'ГЕНЕРАЛЬНЫЙ ДИРЕКТОР: Иванов Иван Иванович',
        'i': '7700000000',
        'k': 'ul',
        'n': 'ОБЩЕСТВО С ОГРАНИЧЕННОЙ ОТВЕТСТВЕННОСТЬЮ "ТЕСТ"',
        'o': '1027700000000',
        'p': '770001001',
        'r': '01.01.2000',
    }

    record = BusinessRegistrySearch()._parse_nalog_row(
        row, 'Иванов Иван Иванович'
    )

    assert record is not None
    assert record.status == 'Ликвидировано'
    assert record.role == 'Директор'


def test_opensanctions_missing_key_is_degraded_without_network(monkeypatch):
    monkeypatch.delenv('OPENSANCTIONS_API_KEY', raising=False)
    monkeypatch.delenv('OPEN_SANCTIONS_API_KEY', raising=False)

    svc = OpenSanctionsService(timeout=1)

    def fail_if_called(*args, **kwargs):
        raise AssertionError('remote OpenSanctions call should be skipped')

    monkeypatch.setattr(svc.session, 'post', fail_if_called)
    monkeypatch.setattr(svc.session, 'get', fail_if_called)

    assert svc.check_person('Test Person') == []
    assert svc.last_status == 'missing_credentials'
    assert not svc.has_credentials


def test_opensanctions_api_key_sets_authorization_header():
    svc = OpenSanctionsService(api_key='dummy-key')

    assert svc.has_credentials
    assert svc.session.headers['Authorization'] == 'ApiKey dummy-key'


def test_opensanctions_auth_failure_does_not_fallback_to_search(monkeypatch):
    svc = OpenSanctionsService(api_key='dummy-key')

    class AuthFailedResponse:
        status_code = 401

        def raise_for_status(self):
            raise AssertionError('401 should be handled before raise_for_status')

    monkeypatch.setattr(
        svc.session, 'post', lambda *args, **kwargs: AuthFailedResponse()
    )

    def fail_if_called(*args, **kwargs):
        raise AssertionError('search fallback should not run after auth failure')

    monkeypatch.setattr(svc.session, 'get', fail_if_called)

    assert svc.check_person('Test Person') == []
    assert svc.last_status == 'auth_failed'
