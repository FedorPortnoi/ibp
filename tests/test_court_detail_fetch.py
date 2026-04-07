"""Tests for CourtCase.raw_text field and _fetch_case_details method."""
import pytest
from unittest.mock import MagicMock, patch
from app.services.phase3.court_search import CourtCase, CourtRecordSearch


class TestFetchCaseDetails:
    """Tests for _fetch_case_details."""

    def setup_method(self):
        self.searcher = CourtRecordSearch()

    def test_fetch_case_details_returns_string(self):
        """_fetch_case_details returns body text as a string (Playwright path)."""
        page = MagicMock()
        # Content must be long enough to pass the >100 char sanity check
        page.inner_text.return_value = (
            "Решение суда по делу 1-1/2024. "
            "Рассмотрено в открытом судебном заседании. "
            "Стороны представили свои доводы и доказательства."
        )

        result = self.searcher._fetch_case_details(page, "https://sudact.ru/regular/doc/123/")

        assert isinstance(result, str)
        assert "Решение суда" in result
        page.goto.assert_called_once()
        page.wait_for_selector.assert_called_once()

    def test_fetch_case_details_timeout_returns_empty(self):
        """Playwright timeout + requests fallback also fails → empty string."""
        page = MagicMock()
        page.goto.side_effect = Exception("timeout")

        # Mock requests fallback to also fail
        with patch.object(self.searcher.session, 'get', side_effect=Exception("network down")):
            result = self.searcher._fetch_case_details(
                page, "https://sudact.ru/regular/doc/123/"
            )

        assert result == ""

    def test_court_case_has_raw_text_field(self):
        """CourtCase dataclass has raw_text field defaulting to empty string."""
        case = CourtCase(case_number="1-1/2024", court_name="Тест")
        assert hasattr(case, 'raw_text')
        assert case.raw_text == ""

    def test_fetch_does_not_crash_on_bad_url(self):
        """_fetch_case_details handles empty URL gracefully."""
        page = MagicMock()

        result = self.searcher._fetch_case_details(page, "")

        assert result == ""
        page.goto.assert_not_called()
