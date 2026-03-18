"""Tests for INN (Russian Tax ID) validation."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from app.utils.inn_validator import validate_inn


class TestInnValidator:
    """Tests for validate_inn()."""

    def test_valid_10_digit_inn(self):
        """Valid 10-digit INN (legal entity) should pass."""
        valid, msg = validate_inn("7707083893")
        assert valid is True
        assert msg == ""

    def test_valid_12_digit_inn(self):
        """Valid 12-digit INN (individual) should pass."""
        valid, msg = validate_inn("232308435186")
        assert valid is True
        assert msg == ""

    def test_9_digit_inn_fails(self):
        """9-digit INN should fail — must be 10 or 12."""
        valid, msg = validate_inn("770708389")
        assert valid is False
        assert msg  # non-empty error message

    def test_letters_in_inn_fails(self):
        """INN with letters should fail."""
        valid, msg = validate_inn("770708abc3")
        assert valid is False

    def test_empty_inn_fails(self):
        """Empty string should fail."""
        valid, msg = validate_inn("")
        assert valid is False

    def test_none_inn_no_exception(self):
        """None should fail gracefully without raising an exception."""
        valid, msg = validate_inn(None)
        assert valid is False

    def test_11_digit_inn_fails(self):
        """11-digit INN is invalid length."""
        valid, msg = validate_inn("77070838931")
        assert valid is False

    def test_invalid_checksum_10_digit(self):
        """10-digit INN with wrong checksum should fail."""
        valid, msg = validate_inn("7707083890")
        assert valid is False

    def test_invalid_checksum_12_digit(self):
        """12-digit INN with wrong checksum should fail."""
        valid, msg = validate_inn("232308435180")
        assert valid is False
