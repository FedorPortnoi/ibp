"""Tests for _fetch_case_details Playwright → requests fallback."""
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def app_ctx():
    from app import create_app
    app = create_app('testing')
    with app.app_context():
        yield app


def _make_searcher():
    from app.services.phase3.court_search import CourtRecordSearch
    return CourtRecordSearch()


def test_fetch_case_details_playwright_timeout_falls_back_to_requests(app_ctx):
    """Playwright timeout → requests fallback returns parsed text."""
    searcher = _make_searcher()

    mock_page = MagicMock()
    mock_page.goto.side_effect = Exception("Timeout 25000ms exceeded")

    fake_html = (
        '<html><body><p>Признан виновным по ч.2 ст.228 УК РФ. '
        'Приговорён к лишению свободы 4 года условно с испытательным сроком. '
        'Суд рассмотрел дело в открытом заседании и постановил.</p></body></html>'
    )
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = fake_html

    with patch.object(searcher.session, 'get', return_value=mock_resp) as mock_get:
        result = searcher._fetch_case_details(
            mock_page, 'https://sudact.ru/regular/doc/test/'
        )

    mock_get.assert_called_once()
    assert result != ""
    assert 'ст.228' in result
    assert 'виновным' in result


def test_fetch_case_details_both_fail_returns_empty(app_ctx):
    """Both Playwright and requests fail → empty string, no exception."""
    searcher = _make_searcher()

    mock_page = MagicMock()
    mock_page.goto.side_effect = Exception("Timeout 25000ms exceeded")

    with patch.object(searcher.session, 'get', side_effect=Exception("Connection refused")):
        result = searcher._fetch_case_details(
            mock_page, 'https://sudact.ru/regular/doc/bad/'
        )

    assert result == ""


def test_fetch_case_details_playwright_success_skips_requests(app_ctx):
    """Playwright success → requests fallback is NOT called."""
    searcher = _make_searcher()

    mock_page = MagicMock()
    mock_page.goto.return_value = None
    mock_page.wait_for_selector.return_value = None
    long_text = "Приговор: осуждён по ч.2 ст.228 УК РФ. " * 20
    mock_page.inner_text.return_value = long_text

    with patch.object(searcher.session, 'get') as mock_get:
        result = searcher._fetch_case_details(
            mock_page, 'https://sudact.ru/regular/doc/good/'
        )

    mock_get.assert_not_called()
    assert '228' in result


def test_fetch_case_details_playwright_timeout_then_requests_404(app_ctx):
    """Playwright timeout + requests 404 → empty string."""
    searcher = _make_searcher()

    mock_page = MagicMock()
    mock_page.goto.side_effect = Exception("Timeout")

    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_resp.text = ""

    with patch.object(searcher.session, 'get', return_value=mock_resp):
        result = searcher._fetch_case_details(
            mock_page, 'https://sudact.ru/regular/doc/missing/'
        )

    assert result == ""


def test_fetch_case_details_empty_url_returns_empty(app_ctx):
    """Empty URL → empty string without calling Playwright or requests."""
    searcher = _make_searcher()
    mock_page = MagicMock()

    with patch.object(searcher.session, 'get') as mock_get:
        result = searcher._fetch_case_details(mock_page, '')

    mock_page.goto.assert_not_called()
    mock_get.assert_not_called()
    assert result == ""


def test_fetch_case_details_uses_25s_timeout(app_ctx):
    """Playwright calls must use 25000ms timeout, not 10000ms."""
    searcher = _make_searcher()

    mock_page = MagicMock()
    mock_page.goto.return_value = None
    mock_page.wait_for_selector.return_value = None
    mock_page.inner_text.return_value = "x" * 200

    searcher._fetch_case_details(mock_page, 'https://sudact.ru/regular/doc/ok/')

    # goto must be called with timeout=25000
    _, goto_kwargs = mock_page.goto.call_args
    assert goto_kwargs.get('timeout') == 25000, (
        f"Expected goto timeout=25000, got {goto_kwargs}"
    )
    # wait_for_selector must be called with timeout=25000
    _, wait_kwargs = mock_page.wait_for_selector.call_args
    assert wait_kwargs.get('timeout') == 25000, (
        f"Expected wait_for_selector timeout=25000, got {wait_kwargs}"
    )
