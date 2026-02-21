"""
Unit tests for Russian → Latin transliteration.
Tests multi-variant generation and edge cases.
"""

import pytest

from app.services.phase1.transliteration import (
    transliterate_russian,
    transliterate_name_part,
)


class TestTransliterateRussian:
    """Tests for full name transliteration."""

    def test_basic_ivanov(self):
        variants = transliterate_russian("Иванов")
        # At least one variant should contain 'ivanov'
        assert any('ivanov' in v.lower() for v in variants)

    def test_empty_string(self):
        assert transliterate_russian("") == []

    def test_whitespace_only(self):
        assert transliterate_russian("   ") == []

    def test_already_latin(self):
        variants = transliterate_russian("Ivanov")
        assert "ivanov" in variants

    def test_multi_word_name(self):
        variants = transliterate_russian("Тихон Портной")
        assert len(variants) > 0
        # Each variant should be two words
        for v in variants:
            assert ' ' in v

    def test_max_variants_limit(self):
        variants = transliterate_russian("Тихон Портной", max_variants=5)
        assert len(variants) <= 5


class TestEdgeCases:
    """Tests for tricky Cyrillic characters."""

    def test_yo_char(self):
        """Ё should transliterate to yo/e/jo."""
        variants = transliterate_name_part("Фёдор")
        lower_variants = [v.lower() for v in variants]
        assert any('yo' in v or 'e' in v for v in lower_variants)

    def test_shch_char(self):
        """Щ should transliterate to shch/sch."""
        variants = transliterate_name_part("Щукин")
        lower_variants = [v.lower() for v in variants]
        assert any(v.startswith('shch') or v.startswith('sch') for v in lower_variants)

    def test_y_char(self):
        """Ы should transliterate to y/i."""
        variants = transliterate_name_part("Крысин")
        lower_variants = [v.lower() for v in variants]
        assert any('y' in v or 'i' in v for v in lower_variants)

    def test_hard_sign(self):
        """Ъ (hard sign) should be omitted."""
        variants = transliterate_name_part("Объедков")
        lower_variants = [v.lower() for v in variants]
        # No variant should contain the Cyrillic ъ
        assert all('ъ' not in v for v in lower_variants)

    def test_soft_sign(self):
        """Ь (soft sign) should be omitted or replaced with apostrophe."""
        variants = transliterate_name_part("Кузьмин")
        lower_variants = [v.lower() for v in variants]
        assert all('ь' not in v for v in lower_variants)

    def test_ending_oy(self):
        """Surname ending -ой should produce -oi/-oy variants."""
        variants = transliterate_name_part("Портной")
        lower_variants = [v.lower() for v in variants]
        assert any(v.endswith('oi') or v.endswith('oy') for v in lower_variants)


class TestTransliterateNamePart:
    """Tests for single name part transliteration."""

    def test_returns_list(self):
        result = transliterate_name_part("Иван")
        assert isinstance(result, list)
        assert len(result) > 0

    def test_max_variants(self):
        result = transliterate_name_part("Александр", max_variants=3)
        assert len(result) <= 3
