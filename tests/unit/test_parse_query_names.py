"""Tests for _parse_query_names() from vk_web_search."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from app.services.phase1.vk_web_search import _parse_query_names


class TestParseQueryNames:
    """Tests for name parsing from search queries."""

    def test_three_tokens_lfp_order(self):
        """3 tokens = Last First Patronymic → first='артем', last='судин'."""
        first, last = _parse_query_names("Судин Артем Алексеевич")
        assert first == "артем"
        assert last == "судин"

    def test_two_tokens_fl_order(self):
        """2 tokens = First Last → first='артем', last='судин'."""
        first, last = _parse_query_names("Артем Судин")
        assert first == "артем"
        assert last == "судин"

    def test_two_tokens_ivanov(self):
        """2 tokens = First Last for 'Иванов Иван'."""
        first, last = _parse_query_names("Иванов Иван")
        # With 2 tokens, first token is treated as first_name
        assert first == "иванов"
        assert last == "иван"

    def test_single_token_no_crash(self):
        """Single token should not crash; first_name set, last_name empty."""
        first, last = _parse_query_names("Иван")
        assert first == "иван"
        assert last == ""

    def test_empty_string_no_crash(self):
        """Empty string should return empty strings without crashing."""
        first, last = _parse_query_names("")
        assert first == ""
        assert last == ""

    def test_lowercase_output(self):
        """Output should always be lowercased."""
        first, last = _parse_query_names("ИВАНОВ ИВАН ИВАНОВИЧ")
        assert first == "иван"
        assert last == "иванов"

    def test_extra_whitespace_handled(self):
        """Extra whitespace between tokens should be handled."""
        first, last = _parse_query_names("  Судин   Артем   Алексеевич  ")
        assert first == "артем"
        assert last == "судин"
