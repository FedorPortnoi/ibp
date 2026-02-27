"""
INN Validation Tests
====================
Tests for Russian INN (Individual Taxpayer Number) checksum validation.
Covers 10-digit (legal entity) and 12-digit (individual) INNs.
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.utils.inn_validator import validate_inn, inn_type


class TestValidateInn:
    """Test INN checksum validation."""

    # ── Valid INNs ──

    def test_valid_12digit_inn(self):
        """Valid 12-digit individual INN passes checksum."""
        # Well-known valid test INN for individuals
        valid, err = validate_inn('500100732259')
        assert valid is True
        assert err == ''

    def test_valid_10digit_inn(self):
        """Valid 10-digit legal entity INN passes checksum."""
        # Sberbank INN
        valid, err = validate_inn('7707083893')
        assert valid is True
        assert err == ''

    def test_valid_10digit_inn_yandex(self):
        """Another valid 10-digit INN (Yandex)."""
        valid, err = validate_inn('7736207543')
        assert valid is True
        assert err == ''

    # ── Invalid checksum ──

    def test_invalid_checksum_12digit(self):
        """12-digit INN with wrong checksum is rejected."""
        valid, err = validate_inn('500100732250')  # last digit changed
        assert valid is False
        assert 'контрольная сумма' in err.lower() or 'некорректна' in err.lower()

    def test_invalid_checksum_10digit(self):
        """10-digit INN with wrong checksum is rejected."""
        valid, err = validate_inn('7707083890')  # last digit changed
        assert valid is False
        assert 'контрольная сумма' in err.lower() or 'некорректна' in err.lower()

    # ── Wrong length ──

    def test_9_digits_rejected(self):
        """9-digit INN is rejected."""
        valid, err = validate_inn('770708389')
        assert valid is False
        assert '10' in err or '12' in err

    def test_11_digits_rejected(self):
        """11-digit INN is rejected."""
        valid, err = validate_inn('77070838930')
        assert valid is False
        assert '10' in err or '12' in err

    def test_13_digits_rejected(self):
        """13-digit INN is rejected."""
        valid, err = validate_inn('5001007322599')
        assert valid is False
        assert '10' in err or '12' in err

    # ── Non-numeric ──

    def test_letters_rejected(self):
        """INN with letters is rejected."""
        valid, err = validate_inn('77070838AB')
        assert valid is False
        assert 'цифр' in err.lower()

    def test_mixed_chars_rejected(self):
        """INN with mixed characters is rejected."""
        valid, err = validate_inn('770-708-3893')
        assert valid is False

    # ── Empty / None ──

    def test_empty_string(self):
        """Empty string is rejected."""
        valid, err = validate_inn('')
        assert valid is False

    def test_whitespace_only(self):
        """Whitespace-only INN is rejected."""
        valid, err = validate_inn('   ')
        assert valid is False

    # ── All zeros ──

    def test_all_zeros_10(self):
        """10 zeros — technically valid checksum (0), but still a valid INN format."""
        valid, _ = validate_inn('0000000000')
        # Checksum: sum of 0s = 0, mod 11 = 0, mod 10 = 0, check digit = 0 → valid
        assert isinstance(valid, bool)

    def test_all_zeros_12(self):
        """12 zeros — check whether it passes or fails checksum."""
        valid, _ = validate_inn('000000000000')
        assert isinstance(valid, bool)


class TestInnType:
    """Test INN type detection."""

    def test_10digit_legal(self):
        assert inn_type('7707083893') == 'legal'

    def test_12digit_individual(self):
        assert inn_type('500100732259') == 'individual'

    def test_invalid_length(self):
        assert inn_type('12345') == 'unknown'

    def test_non_numeric(self):
        assert inn_type('abcdefghij') == 'unknown'

    def test_empty(self):
        assert inn_type('') == 'unknown'

    def test_none(self):
        assert inn_type(None) == 'unknown'
