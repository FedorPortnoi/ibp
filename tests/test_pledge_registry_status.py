"""
Tests for the pledge registry (reestr-zalogov.ru) status contract.

reestr-zalogov.ru is reCAPTCHA-walled, so automated name search is almost
always 'blocked'. The key guarantee: a blocked search must never read as
"no pledged assets". Playwright is mocked — no browser launches here.
"""

from unittest.mock import MagicMock, patch

import pytest

from app.services.phase3.pledge_registry import PledgeRegistrySearch, PledgeRecord


def test_empty_input_skipped():
    svc = PledgeRegistrySearch(timeout=5)
    assert svc.search_by_name('') == ([], 'skipped')
    assert svc.search_by_name('   ') == ([], 'skipped')


def test_playwright_unavailable_reports_unavailable():
    svc = PledgeRegistrySearch(timeout=5)
    # Simulate ImportError inside _search_playwright by patching the method to
    # exercise the real import guard: easier to call the public method with the
    # playwright module hidden.
    with patch.dict('sys.modules', {'playwright.sync_api': None}):
        records, status = svc.search_by_name('Иванов Иван Иванович')
    assert records == []
    assert status == 'unavailable'


def test_recaptcha_reports_blocked():
    """reCAPTCHA present → 'blocked', NOT empty 'no pledges'."""
    svc = PledgeRegistrySearch(timeout=5)

    def fake_search(full_name):
        return [], 'blocked'

    with patch.object(svc, '_search_playwright', side_effect=fake_search):
        records, status = svc.search_by_name('Иванов Иван Иванович')
    assert (records, status) == ([], 'blocked')


def test_exception_reports_error():
    svc = PledgeRegistrySearch(timeout=5)
    with patch.object(svc, '_search_playwright', side_effect=RuntimeError('boom')):
        records, status = svc.search_by_name('Иванов Иван Иванович')
    assert (records, status) == ([], 'error')


def test_records_report_ok():
    svc = PledgeRegistrySearch(timeout=5)
    rec = PledgeRecord(registration_number='2020-001-123', subject='Автомобиль')
    with patch.object(svc, '_search_playwright', return_value=([rec], 'ok')):
        records, status = svc.search_by_name('Иванов Иван Иванович')
    assert status == 'ok'
    assert len(records) == 1


def test_search_form_missing_is_blocked_not_empty():
    """If the form can't be found, that's 'blocked' (page changed/interstitial),
    not a confirmed empty result. Drives the real _search_playwright with a
    mocked page that returns no input element."""
    svc = PledgeRegistrySearch(timeout=1)

    page = MagicMock()
    page.query_selector.return_value = None  # no name input found
    browser = MagicMock()
    browser.new_page.return_value = page
    p_ctx = MagicMock()
    p_ctx.chromium.launch.return_value = browser

    sync_pw = MagicMock()
    sync_pw.return_value.__enter__.return_value = p_ctx
    sync_pw.return_value.__exit__.return_value = False

    fake_module = MagicMock()
    fake_module.sync_playwright = sync_pw
    with patch.dict('sys.modules', {'playwright.sync_api': fake_module}):
        records, status = svc.search_by_name('Иванов Иван Иванович')

    assert records == []
    assert status == 'blocked'
