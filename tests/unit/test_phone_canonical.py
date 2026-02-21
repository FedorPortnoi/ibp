"""
Unit tests for the canonical phone normalization function in app/utils/phone.py.
Tests every Russian phone format plus edge cases.
"""

import pytest

from app.utils.phone import normalize_phone


class TestCanonicalNormalizePhone:
    """Tests for the canonical normalize_phone() in app/utils/phone."""

    # --- Standard Russian formats ---

    def test_plus7_parentheses_dashes(self):
        """+7 (916) 123-45-67 -> +79161234567"""
        assert normalize_phone("+7 (916) 123-45-67") == "+79161234567"

    def test_eight_dashes(self):
        """8-916-123-45-67 -> +79161234567"""
        assert normalize_phone("8-916-123-45-67") == "+79161234567"

    def test_plus7_spaces(self):
        """+7 916 1234567 -> +79161234567"""
        assert normalize_phone("+7 916 1234567") == "+79161234567"

    def test_eight_parentheses_no_spaces(self):
        """8(916)1234567 -> +79161234567"""
        assert normalize_phone("8(916)1234567") == "+79161234567"

    def test_eleven_digits_starting_with_7(self):
        """79161234567 -> +79161234567"""
        assert normalize_phone("79161234567") == "+79161234567"

    def test_plus7_dashes(self):
        """+7-916-123-45-67 -> +79161234567"""
        assert normalize_phone("+7-916-123-45-67") == "+79161234567"

    def test_already_normalized(self):
        """+79161234567 -> +79161234567 (no change)"""
        assert normalize_phone("+79161234567") == "+79161234567"

    def test_ten_digits(self):
        """9161234567 (10 digits, no prefix) -> +79161234567"""
        assert normalize_phone("9161234567") == "+79161234567"

    def test_eight_prefix_no_separators(self):
        """89161234567 -> +79161234567"""
        assert normalize_phone("89161234567") == "+79161234567"

    # --- Empty / None ---

    def test_empty_string(self):
        """Empty string -> ''"""
        assert normalize_phone("") == ""

    def test_none(self):
        """None -> ''"""
        assert normalize_phone(None) == ""

    # --- Non-normalizable inputs ---

    def test_non_phone_text(self):
        """Non-phone text like 'hello' -> returned as-is"""
        assert normalize_phone("hello") == "hello"

    def test_short_number(self):
        """Short number '123' -> returned as-is"""
        assert normalize_phone("123") == "123"

    def test_international_non_russian(self):
        """International non-Russian +1-202-555-0123 -> returned as-is"""
        result = normalize_phone("+1-202-555-0123")
        assert result == "+1-202-555-0123"

    # --- Additional edge cases ---

    def test_landline_moscow(self):
        """+7 (495) 123-45-67 -> +74951234567"""
        assert normalize_phone("+7 (495) 123-45-67") == "+74951234567"

    def test_eight_landline(self):
        """8(495)1234567 -> +74951234567"""
        assert normalize_phone("8(495)1234567") == "+74951234567"

    def test_ten_digits_landline(self):
        """4951234567 (10-digit landline) -> +74951234567"""
        assert normalize_phone("4951234567") == "+74951234567"
