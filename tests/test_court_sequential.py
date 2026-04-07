import pytest

PIPELINE_PATH = 'app/services/candidate/pipeline.py'


def _read_source():
    with open(PIPELINE_PATH, 'r', encoding='utf-8') as f:
        return f.read()


def test_court_search_not_in_threadpool():
    """future_courts must be removed — court search no longer goes through the pool."""
    source = _read_source()
    assert 'future_courts' not in source, "future_courts must be removed"


def test_court_save_grace_period_removed():
    """The [COURT SAVE] grace period block must be deleted."""
    source = _read_source()
    assert 'COURT SAVE' not in source, "[COURT SAVE] grace period block must be removed"


def test_court_records_assigned_directly():
    """check.court_records must be assigned (it's still saved to DB)."""
    source = _read_source()
    assert 'check.court_records' in source


def test_court_search_called_directly():
    """_search_courts must still be called somewhere in pipeline.py."""
    source = _read_source()
    assert '_search_courts(' in source


def test_biz_and_fssp_still_parallel():
    """future_biz and future_fssp must still exist (parallel via ThreadPoolExecutor)."""
    source = _read_source()
    assert 'future_biz' in source
    assert 'future_fssp' in source


def test_threadpool_still_used_for_gov_pool():
    """ThreadPoolExecutor still used (for biz/fssp/pledges)."""
    source = _read_source()
    assert 'ThreadPoolExecutor' in source
