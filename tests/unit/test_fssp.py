"""Test ФССП service."""
import sys
import os
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))


def test_fssp_search_uses_stubbed_ajax_without_network():
    """FSSP search must split/normalize inputs before calling AJAX."""
    from app.services.candidate import fssp_service

    calls = []

    def fake_ajax(self, last_name, first_name, patronymic, dob, region_code):
        calls.append((last_name, first_name, patronymic, dob, region_code))
        return [
            fssp_service.FSSPRecord(
                debtor_name=f'{last_name} {first_name} {patronymic}',
                proceedings_number='12345/26/77000-ИП',
                source='stubbed ajax',
            )
        ]

    def fail_if_called(*args, **kwargs):
        raise AssertionError("Unexpected live-network strategy call")

    with (
        patch.dict(os.environ, {'FSSP_API_TOKEN': ''}),
        patch.object(fssp_service, 'PLAYWRIGHT_AVAILABLE', True),
        patch.object(fssp_service.FSSPService, '_search_api', fail_if_called),
        patch.object(fssp_service.FSSPService, '_search_ajax', fake_ajax),
        patch.object(fssp_service.FSSPService, '_search_playwright', fail_if_called),
    ):
        svc = fssp_service.FSSPService(timeout=1)
        results = svc.search('Иванов Иван Иванович', '1990-01-01', 'Москва')

    assert isinstance(results, list), "FAIL: not a list"
    assert calls == [('Иванов', 'Иван', 'Иванович', '01.01.1990', '77')]
    assert len(results) == 1
    assert results[0].source == 'stubbed ajax'
    assert results[0].debtor_name == 'Иванов Иван Иванович'


def test_fssp_search_manual_fallback_without_network():
    """FSSP search returns manual fallback when automated strategies fail."""
    from app.services.candidate import fssp_service

    def fake_ajax(*args, **kwargs):
        return None

    def fail_if_called(*args, **kwargs):
        raise AssertionError("Unexpected live-network strategy call")

    with (
        patch.dict(os.environ, {'FSSP_API_TOKEN': ''}),
        patch.object(fssp_service, 'PLAYWRIGHT_AVAILABLE', False),
        patch.object(fssp_service.FSSPService, '_search_api', fail_if_called),
        patch.object(fssp_service.FSSPService, '_search_ajax', fake_ajax),
        patch.object(fssp_service.FSSPService, '_search_playwright', fail_if_called),
    ):
        svc = fssp_service.FSSPService(timeout=1)
        records = svc.search('Иванов Иван Иванович', '01.01.1990', 'Москва')

    assert len(records) == 1
    assert records[0].source == 'manual'
    assert records[0].debtor_name == 'Иванов Иван Иванович'


def test_dob_format():
    """DOB format conversion must work."""
    from app.services.candidate.fssp_service import FSSPService
    svc = FSSPService()
    assert svc._format_dob('1990-01-15') == '15.01.1990'
    assert svc._format_dob('29.11.1990') == '29.11.1990'
    assert svc._format_dob('') == ''
    print("PASS: DOB format conversion works")


def test_name_split():
    """Name must split into lastname, firstname, patronymic."""
    parts = 'Судин Артем Алексеевич'.split()
    assert len(parts) == 3
    assert parts[0] == 'Судин'
    assert parts[1] == 'Артем'
    assert parts[2] == 'Алексеевич'
    print("PASS: Name split works")


def test_region_resolution():
    """Region resolution must work."""
    from app.services.candidate.fssp_service import FSSPService
    svc = FSSPService()
    assert svc._resolve_region('Москва') == '77'
    assert svc._resolve_region('Краснодар') == '23'
    assert svc._resolve_region(None) is None
    print("PASS: Region resolution works")


def test_manual_fallback():
    """Manual fallback must always return a record."""
    from app.services.candidate.fssp_service import FSSPService
    svc = FSSPService()
    records = svc._manual_fallback('Иванов', 'Иван', 'Иванович', '01.01.1990', '77')
    assert len(records) == 1
    assert records[0].source == 'manual'
    print("PASS: Manual fallback works")


if __name__ == '__main__':
    test_dob_format()
    test_name_split()
    test_region_resolution()
    test_manual_fallback()
    test_fssp_search_uses_stubbed_ajax_without_network()
    test_fssp_search_manual_fallback_without_network()
    print("\nAll FSSP tests PASSED")
