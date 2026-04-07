"""Tests for court records save path — grace period recovery after future timeout."""
import pytest


def _pipeline_source():
    with open('app/services/candidate/pipeline.py', 'r', encoding='utf-8') as f:
        return f.read()


def test_pipeline_contains_court_save_log_marker():
    """Pipeline must contain the [COURT SAVE] log marker introduced by the fix."""
    source = _pipeline_source()
    assert '[COURT SAVE]' in source, (
        "Expected [COURT SAVE] log marker in pipeline.py"
    )


def test_pipeline_has_grace_period_wait_on_courts_future():
    """After TimeoutError, the fix must wait on future_courts with an extra timeout."""
    source = _pipeline_source()
    # The recovery branch should call future_courts.result(timeout=…)
    assert 'future_courts.result(timeout=' in source, (
        "Grace period recovery must call future_courts.result(timeout=…)"
    )


def test_grace_period_assigns_to_court_records():
    """The grace period block must assign its result back to court_records."""
    source = _pipeline_source()
    # The timeout branch should include `court_records = future_courts.result(...)`
    # — locate the TimeoutError block and check the pattern exists inside it.
    idx = source.find('except TimeoutError')
    assert idx != -1, "TimeoutError handler missing"
    # Search window — from TimeoutError handler to end of `finally`
    end_idx = source.find('gov_pool.shutdown', idx)
    assert end_idx != -1
    block = source[idx:end_idx]
    assert 'court_records = future_courts.result(' in block, (
        "Grace period must assign future_courts.result(...) to court_records "
        "inside the TimeoutError handler"
    )


def test_courts_normalization_runs_after_grace_period():
    """The existing normalize_court_confidence call must still cover grace-period records."""
    source = _pipeline_source()
    # Grace period is inside TimeoutError handler; normalize runs AFTER the try/except block.
    normalize_idx = source.find('_normalize_court_confidence(court_records')
    assign_idx = source.find('check.court_records = court_records')
    grace_idx = source.find('[COURT SAVE] Recovered')
    assert normalize_idx != -1, "normalize_court_confidence must still be called"
    assert assign_idx != -1, "check.court_records = court_records must exist"
    assert grace_idx != -1, "Grace period marker missing"
    # Order: grace period recovery → normalize → assign to check
    assert grace_idx < normalize_idx < assign_idx, (
        f"Expected order grace({grace_idx}) < normalize({normalize_idx}) "
        f"< assign({assign_idx})"
    )


def test_courts_timeout_does_not_crash_pipeline():
    """Grace period failure path must not re-raise — pipeline must continue."""
    source = _pipeline_source()
    idx = source.find('[COURT SAVE] Grace period failed')
    assert idx != -1, "Failure path must log [COURT SAVE] Grace period failed"
    # The failure branch should not raise — should just log and continue
    # Verify there's no `raise` keyword inside the except block for grace period
    fail_end = source.find('for future in timed_out:', idx)
    assert fail_end != -1
    fail_block = source[idx:fail_end]
    assert 'raise' not in fail_block, (
        "Grace period failure must not re-raise"
    )
