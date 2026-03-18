"""Tests for _safe_filename() from candidate_check routes."""

import re
import sys
import os

# Ensure project root is on sys.path so we can import from app
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

# Import the function directly — it's a module-level helper, not tied to Flask routes.
# Re-implement the import to avoid needing full Flask app context.
from app.routes.candidate_check import _safe_filename


class TestSafeFilename:
    """Tests for _safe_filename sanitization."""

    def test_cyrillic_input_produces_ascii_only(self):
        """Cyrillic characters should be replaced, producing ASCII-only output."""
        result = _safe_filename("Стасюк_СА_2026")
        # No Cyrillic characters should remain
        assert result.isascii(), f"Result contains non-ASCII chars: {result}"
        # Underscores and digits should survive
        assert "2026" in result

    def test_special_chars_stripped(self):
        """Characters like <>:\"/\\|?* should be replaced."""
        result = _safe_filename('test<>:"/\\|?*file')
        for ch in '<>:"/\\|?*':
            assert ch not in result, f"Special char {ch!r} still present in {result!r}"

    def test_spaces_become_underscores(self):
        """Spaces should be replaced with underscores."""
        result = _safe_filename("hello world test")
        assert " " not in result
        # The function replaces non-alnum chars with _ then collapses
        assert "hello_world_test" == result

    def test_empty_string_returns_candidate(self):
        """Empty string should fall back to 'candidate'."""
        result = _safe_filename("")
        assert result == "candidate"

    def test_long_filename_truncated_to_100(self):
        """Filenames longer than 100 chars should be truncated."""
        long_name = "a" * 200
        result = _safe_filename(long_name)
        assert len(result) <= 100

    def test_only_special_chars_returns_candidate(self):
        """A string with only special characters should fall back to 'candidate'."""
        result = _safe_filename("***???")
        assert result == "candidate"

    def test_normal_ascii_passes_through(self):
        """Normal ASCII alphanumeric + underscore/hyphen/dot pass through."""
        result = _safe_filename("report_2026-03.pdf")
        assert result == "report_2026-03.pdf"

    def test_multiple_underscores_collapsed(self):
        """Multiple consecutive underscores should be collapsed to one."""
        result = _safe_filename("a___b")
        assert result == "a_b"
