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


# ── sanctions_check honesty: "unchecked" must never read as "clean" ────────

from unittest.mock import patch, MagicMock
from app.services.candidate.sanctions_check import SanctionsService, SanctionsResult


def _opensanctions_result(status, matches=None):
    """Run _check_opensanctions with a mocked OpenSanctionsService."""
    fake = MagicMock()
    fake.check_person.return_value = matches or []
    fake.last_status = status
    with patch(
        'app.services.candidate.opensanctions_service.OpenSanctionsService',
        return_value=fake,
    ):
        return SanctionsService()._check_opensanctions('Иванов Иван Иванович')


@pytest.mark.parametrize('status', [
    'missing_credentials', 'auth_failed', 'rate_limited',
    'timeout', 'connection_error', 'server_error', 'error', 'not_checked',
])
def test_opensanctions_non_ok_status_is_unchecked_not_clean(status):
    """The high-stakes false-clean guard: a screening that did not actually
    run must report checked=False, never checked=True/found=False."""
    results = _opensanctions_result(status)
    assert len(results) == 1
    r = results[0]
    assert r.checked is False, f"status {status} must not be 'checked'"
    assert r.found is False
    assert r.error  # an explanation is present


def test_opensanctions_ok_no_matches_is_verified_clean():
    results = _opensanctions_result('ok', matches=[])
    assert len(results) == 1
    assert results[0].checked is True
    assert results[0].found is False


def test_opensanctions_ok_with_match_is_found():
    match = MagicMock()
    match.to_sanctions_dict.return_value = {
        'source_name': 'US OFAC SDN',
        'match_details': 'Совпадение (95%)',
        'url': 'https://opensanctions.org/entities/x/',
    }
    results = _opensanctions_result('ok', matches=[match])
    assert results[0].checked is True
    assert results[0].found is True
    assert results[0].source_name == 'US OFAC SDN'


def test_check_all_does_not_vouch_rosfinmonitoring_without_opensanctions(monkeypatch):
    """When OpenSanctions could not run, the filled Rosfinmonitoring slot must
    NOT be marked checked=True (it used to free-ride on a false OS 'ok')."""
    svc = SanctionsService()
    monkeypatch.setattr(svc, '_check_opensanctions', lambda *a, **k: [
        SanctionsResult(source_name='OpenSanctions', checked=False, found=False,
                        error='API-ключ OpenSanctions не настроен')
    ])
    # Force every other source to "unavailable" so we isolate the slot-fill.
    for m in ('_check_mvd_local', '_check_extremist_local', '_check_interpol',
              '_check_rosfinmonitoring'):
        monkeypatch.setattr(svc, m, lambda *a, **k: SanctionsResult(
            source_name=m, checked=False, found=False, error='unavailable'))

    results = svc.check_all('Иванов Иван Иванович')
    rfm = [r for r in results if r.source_name == 'Росфинмониторинг']
    assert rfm, 'Rosfinmonitoring slot should exist'
    assert all(r.checked is False for r in rfm), \
        'Rosfinmonitoring must not be vouched as checked when OpenSanctions did not run'
