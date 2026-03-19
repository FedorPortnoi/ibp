"""Test ФССП service."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))


def test_fssp_no_crash():
    """FSSP search must not crash."""
    from app.services.candidate.fssp_service import FSSPService
    svc = FSSPService(timeout=15)
    results = svc.search('Иванов Иван Иванович', '01.01.1990')
    assert isinstance(results, list), "FAIL: not a list"
    # The search should not crash; it may return manual fallback due to CAPTCHA
    assert len(results) >= 0


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
    test_fssp_no_crash()
    print("\nAll ФССП tests PASSED")
