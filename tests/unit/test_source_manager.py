"""Tests for Phase 2 source deduplication and confidence boosting."""

import pytest

from app.services.phase2.base_source import SourceResult, SourceTier
from app.services.phase2.source_manager import SourceManager


def _result(value, source_name, confidence=0.50):
    return SourceResult(
        data_type='email',
        value=value,
        source_name=source_name,
        source_tier=SourceTier.B,
        confidence=confidence,
    )


@pytest.mark.parametrize(
    ('source_count', 'expected_confidence'),
    [
        (1, 0.50),
        (2, 0.60),
        (3, 0.65),
        (4, 0.70),
    ],
)
def test_confidence_boost_applies_after_dedup(source_count, expected_confidence):
    manager = SourceManager.__new__(SourceManager)
    results = [
        _result('person@example.com', f'source-{idx}')
        for idx in range(source_count)
    ]

    [deduped] = manager._deduplicate(results)

    assert deduped.metadata['source_count'] == source_count
    assert deduped.confidence == pytest.approx(expected_confidence)


def test_confidence_boost_is_capped_below_one():
    manager = SourceManager.__new__(SourceManager)
    results = [
        _result('person@example.com', f'source-{idx}', confidence=0.90)
        for idx in range(4)
    ]

    [deduped] = manager._deduplicate(results)

    assert deduped.confidence == pytest.approx(0.98)
