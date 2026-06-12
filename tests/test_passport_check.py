"""
Tests for the MVD invalid-passport check (gosuslugi/ГУВМ МВД, source #22).

The ГУВМ МВД registry service has been dead since July 2023. The guarantees
under test: input normalization, and that no failure/unrecognized path ever
reports a passport as verified-valid when the check did not actually run.
"""

from unittest.mock import MagicMock, patch

import pytest
import requests as _requests

from app.services.phase3.passport_check import (
    check_passport_mvd,
    normalize_passport,
)


class TestNormalizePassport:

    @pytest.mark.parametrize('raw,expected', [
        ('0312 107459', ('0312', '107459')),
        ('0312107459', ('0312', '107459')),
        ('03 12 107459', ('0312', '107459')),
        ('  0312-107459 ', ('0312', '107459')),
    ])
    def test_valid_forms(self, raw, expected):
        assert normalize_passport(raw) == expected

    @pytest.mark.parametrize('raw', ['123', '', 'abcd', '031210745'])
    def test_invalid_returns_none(self, raw):
        assert normalize_passport(raw) == (None, None)


class TestCheckPassportInputValidation:

    def test_missing_fields_not_checked(self):
        r = check_passport_mvd('', '')
        assert r['checked'] is False
        assert r['valid'] is None

    def test_bad_format_not_checked(self):
        assert check_passport_mvd('03', '107459')['checked'] is False
        assert check_passport_mvd('0312', '12')['checked'] is False


def _post_returning(html, status=200):
    resp = MagicMock()
    resp.status_code = status
    resp.text = html
    return resp


class TestCheckPassportHonesty:

    def test_service_unreachable_is_unchecked(self):
        with patch('app.services.phase3.passport_check.requests.post',
                   side_effect=_requests.ConnectionError('geo')):
            r = check_passport_mvd('0312', '107459')
        assert r['checked'] is False
        assert r['valid'] is None

    def test_404_is_unchecked(self):
        with patch('app.services.phase3.passport_check.requests.post',
                   return_value=_post_returning('', 404)):
            r = check_passport_mvd('0312', '107459')
        assert r['checked'] is False
        assert r['valid'] is None

    def test_unrecognized_page_is_unchecked_not_valid(self):
        """A 200 page we can't parse must NOT read as a valid passport."""
        with patch('app.services.phase3.passport_check.requests.post',
                   return_value=_post_returning('<html><body>что-то непонятное</body></html>')):
            r = check_passport_mvd('0312', '107459')
        assert r['checked'] is False
        assert r['valid'] is None

    def test_gosuslugi_redirect_is_unchecked(self):
        with patch('app.services.phase3.passport_check.requests.post',
                   return_value=_post_returning('<html>Перейдите на Госуслуги для авторизации</html>')):
            r = check_passport_mvd('0312', '107459')
        assert r['checked'] is False

    def test_valid_passport_recognized(self):
        html = '<html><body>Паспорт среди недействительных не значится</body></html>'
        with patch('app.services.phase3.passport_check.requests.post',
                   return_value=_post_returning(html)):
            r = check_passport_mvd('0312', '107459')
        assert r['checked'] is True
        assert r['valid'] is True

    def test_invalid_passport_recognized(self):
        html = '<html><body>Паспорт недействителен</body></html>'
        with patch('app.services.phase3.passport_check.requests.post',
                   return_value=_post_returning(html)):
            r = check_passport_mvd('0312', '107459')
        assert r['checked'] is True
        assert r['valid'] is False
