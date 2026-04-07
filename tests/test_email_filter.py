import pytest
from app.services.phase2.sources.breach_api import _is_valid_email


class TestValidEmails:
    def test_normal_mail_ru(self):
        assert _is_valid_email('zobov.73@mail.ru') is True

    def test_normal_gmail(self):
        assert _is_valid_email('test.user@gmail.com') is True

    def test_simple_three_letter(self):
        assert _is_valid_email('abc@gmail.com') is True

    def test_with_dots(self):
        assert _is_valid_email('john.doe@example.org') is True

    def test_yandex(self):
        assert _is_valid_email('ivanov@yandex.ru') is True


class TestJunkEmails:
    def test_domain_as_local_part(self):
        """gmail.com@gmail.com — local part contained in domain."""
        assert _is_valid_email('gmail.com@gmail.com') is False

    def test_single_underscore(self):
        assert _is_valid_email('_@gmail.com') is False

    def test_four_underscores(self):
        assert _is_valid_email('____@gmail.com') is False

    def test_mixed_underscore_dash(self):
        assert _is_valid_email('__--__@gmail.com') is False

    def test_only_digits_local(self):
        assert _is_valid_email('1234@gmail.com') is False

    def test_double_dash(self):
        assert _is_valid_email('--@gmail.com') is False


class TestMalformed:
    def test_empty(self):
        assert _is_valid_email('') is False

    def test_none(self):
        assert _is_valid_email(None) is False

    def test_no_at(self):
        assert _is_valid_email('notanemail') is False

    def test_no_tld(self):
        assert _is_valid_email('user@localhost') is False

    def test_single_char_local(self):
        """len(local) < 2 must be blocked."""
        assert _is_valid_email('a@gmail.com') is False

    def test_too_short_overall(self):
        assert _is_valid_email('a@b.c') is False

    def test_non_string(self):
        assert _is_valid_email(12345) is False
