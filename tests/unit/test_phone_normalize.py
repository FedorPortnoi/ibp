"""
Unit tests for Russian phone number normalization and validation.
Tests various input formats and edge cases.
"""

import pytest

from app.services.phase2.russian_phone_validator import (
    RussianPhoneValidator,
    normalize_phone,
    validate_phone,
)


class TestNormalizePhone:
    """Tests for phone number normalization to +7XXXXXXXXXX format."""

    def test_plus7_parentheses(self):
        assert normalize_phone("+7 (916) 123-45-67") == "+79161234567"

    def test_eight_dashes(self):
        assert normalize_phone("8-916-123-45-67") == "+79161234567"

    def test_plus7_spaces(self):
        assert normalize_phone("+7 916 1234567") == "+79161234567"

    def test_already_normalized(self):
        assert normalize_phone("+79161234567") == "+79161234567"

    def test_ten_digits_starting_with_9(self):
        assert normalize_phone("9161234567") == "+79161234567"

    def test_eight_prefix(self):
        assert normalize_phone("89161234567") == "+79161234567"

    def test_seven_prefix(self):
        assert normalize_phone("79161234567") == "+79161234567"

    def test_empty_string(self):
        assert normalize_phone("") == ""


class TestValidatePhone:
    """Tests for phone validation with metadata."""

    def test_valid_mobile(self):
        info = validate_phone("+7 (916) 123-45-67")
        assert info.is_valid is True
        assert info.is_mobile is True
        assert info.format_type == 'mobile'

    def test_valid_landline(self):
        info = validate_phone("+7 (495) 123-45-67")
        assert info.is_valid is True
        assert info.is_mobile is False
        assert info.format_type == 'landline'
        assert info.region == 'Moscow'

    def test_invalid_short(self):
        info = validate_phone("12345")
        assert info.is_valid is False

    def test_carrier_hint(self):
        info = validate_phone("+79161234567")
        assert info.carrier_hint is not None

    def test_display_format(self):
        info = validate_phone("+79161234567")
        assert info.display_format == "+7 (916) 123-45-67"


class TestExtractPhones:
    """Tests for phone extraction from text."""

    def test_extract_from_text(self):
        validator = RussianPhoneValidator()
        phones = validator.extract_phones("Звоните: +7(916)123-45-67 или 8-926-765-43-21")
        assert len(phones) == 2

    def test_extract_no_phones(self):
        validator = RussianPhoneValidator()
        phones = validator.extract_phones("Нет телефонов в этом тексте")
        assert phones == []

    def test_extract_deduplicates(self):
        validator = RussianPhoneValidator()
        phones = validator.extract_phones("+79161234567 and 89161234567")
        assert len(phones) == 1


class TestIsRussianMobile:
    """Tests for quick mobile check."""

    def test_plus7_mobile(self):
        assert RussianPhoneValidator.is_russian_mobile("+79161234567") is True

    def test_eight_mobile(self):
        assert RussianPhoneValidator.is_russian_mobile("89161234567") is True

    def test_ten_digit_mobile(self):
        assert RussianPhoneValidator.is_russian_mobile("9161234567") is True

    def test_landline_not_mobile(self):
        assert RussianPhoneValidator.is_russian_mobile("+74951234567") is False
