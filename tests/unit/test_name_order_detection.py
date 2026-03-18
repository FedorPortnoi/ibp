"""Tests for name order detection (LFP vs FL) in _parse_query_names."""

import sys
import os
import unicodedata

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from app.services.phase1.vk_web_search import _parse_query_names


class TestNameOrderDetection:
    """Edge cases for Russian name order parsing."""

    def test_lfp_stasyuk(self):
        """LFP: 'Стасюк Сергей Анатольевич' → first='сергей', last='стасюк'."""
        first, last = _parse_query_names("Стасюк Сергей Анатольевич")
        assert first == "сергей"
        assert last == "стасюк"

    def test_fl_stasyuk(self):
        """FL: 'Сергей Стасюк' → first='сергей', last='стасюк'."""
        first, last = _parse_query_names("Сергей Стасюк")
        assert first == "сергей"
        assert last == "стасюк"

    def test_unicode_normalization(self):
        """Names composed with Unicode combining characters should still parse."""
        # Build "Иван" using NFD (decomposed) form
        name_nfd = unicodedata.normalize("NFD", "Иванов Иван Иванович")
        first, last = _parse_query_names(name_nfd)
        # The function uses .lower().split() which works on any Unicode form
        assert "иван" in unicodedata.normalize("NFC", first) or first == unicodedata.normalize("NFC", "иван")
        assert last != ""

    def test_yo_ye_handled(self):
        """Names with ё should parse without errors."""
        first, last = _parse_query_names("Семёнов Пётр Алексеевич")
        assert first == "пётр"
        assert last == "семёнов"

    def test_ye_variant(self):
        """Names with е (instead of ё) should also parse."""
        first, last = _parse_query_names("Семенов Петр Алексеевич")
        assert first == "петр"
        assert last == "семенов"

    def test_four_tokens_still_lfp(self):
        """4+ tokens still treated as LFP (only first two matter)."""
        first, last = _parse_query_names("Иванов Иван Иванович Младший")
        assert first == "иван"
        assert last == "иванов"

    def test_hyphenated_last_name_single_split(self):
        """Hyphenated last name: split() treats it as one token."""
        first, last = _parse_query_names("Салтыков-Щедрин Михаил")
        # 2 tokens → FL order
        assert first == "салтыков-щедрин"
        assert last == "михаил"
