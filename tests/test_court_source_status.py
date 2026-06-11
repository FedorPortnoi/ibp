"""
Tests for court-source status honesty at the pipeline level:
- _normalize_court_confidence with kad.arbitr.ru + preserved final levels
"""

import pytest

from app.services.candidate.pipeline import _normalize_court_confidence


def _rec(source, confidence='medium', court='Тестовый суд'):
    return {'source': source, 'confidence': confidence, 'court_name': court}


class TestNormalizeCourtConfidence:

    def test_kad_baseline_possible(self):
        records = _normalize_court_confidence([_rec('kad.arbitr.ru')])
        assert records[0]['confidence'] == 'POSSIBLE'

    def test_kad_inn_verified_preserved(self):
        """INN-matched kad cases arrive VERIFIED and must stay VERIFIED."""
        records = _normalize_court_confidence(
            [_rec('kad.arbitr.ru', confidence='VERIFIED')],
            candidate_region='Москва',
        )
        assert records[0]['confidence'] == 'VERIFIED'

    def test_final_level_not_downgraded_by_baseline(self):
        records = _normalize_court_confidence(
            [_rec('sudact.ru', confidence='LIKELY')]
        )
        assert records[0]['confidence'] == 'LIKELY'

    def test_legacy_medium_overwritten_by_baseline(self):
        records = _normalize_court_confidence([_rec('reputation.su', 'medium')])
        assert records[0]['confidence'] == 'POSSIBLE'

    def test_region_match_upgrades_kad_name_match(self):
        records = _normalize_court_confidence(
            [_rec('kad.arbitr.ru', court='Арбитражный суд Свердловской области')],
            candidate_region='Свердловская область',
        )
        assert records[0]['confidence'] == 'LIKELY'

    def test_region_mismatch_keeps_baseline(self):
        records = _normalize_court_confidence(
            [_rec('kad.arbitr.ru', court='АС города Москвы')],
            candidate_region='Свердловская область',
        )
        assert records[0]['confidence'] == 'POSSIBLE'

    def test_generic_region_word_does_not_upgrade_other_oblast(self):
        """'область' alone must not match every областной суд in the country."""
        records = _normalize_court_confidence(
            [_rec('reputation.su', court='Арбитражный суд Тульской области')],
            candidate_region='Свердловская область',
        )
        assert records[0]['confidence'] == 'POSSIBLE'

    def test_inflected_city_region_matches(self):
        """Москва (region) vs 'суд г. Москвы' (genitive in court name)."""
        records = _normalize_court_confidence(
            [_rec('reputation.su', court='Тверской районный суд г. Москвы')],
            candidate_region='Москва',
        )
        assert records[0]['confidence'] == 'LIKELY'

    def test_unknown_source_unverified(self):
        records = _normalize_court_confidence([_rec('mystery.ru')])
        assert records[0]['confidence'] == 'UNVERIFIED'

    def test_sudact_baseline_unverified(self):
        records = _normalize_court_confidence([_rec('sudact.ru')])
        assert records[0]['confidence'] == 'UNVERIFIED'
