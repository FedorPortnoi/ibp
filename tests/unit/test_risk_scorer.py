"""
Unit tests for RiskScorer.
Tests risk analysis logic with mock candidate check objects.
"""

import pytest
from types import SimpleNamespace

from app.services.candidate.risk_scorer import RiskScorer


def _make_check(**kwargs):
    """Create a minimal mock CandidateCheck with default empty fields."""
    defaults = {
        'business_records': None,
        'court_records': None,
        'fssp_records': None,
        'bankruptcy_records': None,
        'sanctions_results': None,
        'social_media_profiles': None,
        'registered_address': None,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


class TestRiskScorerClean:
    """Tests for clean results (no red flags)."""

    def test_clean_result_no_data(self):
        scorer = RiskScorer()
        level, flags = scorer.analyze(_make_check())
        # No social presence flag triggers 'low' risk
        assert level == 'low'
        assert len(flags) == 1
        assert flags[0]['code'] == 'no_social_presence'

    def test_clean_with_social_profiles(self):
        scorer = RiskScorer()
        check = _make_check(social_media_profiles=[{'platform': 'vk', 'url': 'https://vk.com/id1'}])
        level, flags = scorer.analyze(check)
        assert level == 'clean'
        assert flags == []

    def test_clean_with_few_business_records(self):
        scorer = RiskScorer()
        records = [
            {'name': 'Company A', 'role': 'учредитель', 'status': 'действующая', 'source': 'nalog'},
        ]
        check = _make_check(
            business_records=records,
            social_media_profiles=[{'platform': 'vk'}],
        )
        level, flags = scorer.analyze(check)
        assert level == 'clean'


class TestRiskScorerBusiness:
    """Tests for business-related red flags."""

    def test_mass_director_flag(self):
        scorer = RiskScorer()
        records = [
            {'name': f'Company {i}', 'role': 'директор', 'status': 'действующая', 'source': 'nalog'}
            for i in range(6)
        ]
        check = _make_check(business_records=records, social_media_profiles=[{'platform': 'vk'}])
        level, flags = scorer.analyze(check)
        codes = [f['code'] for f in flags]
        assert 'mass_director' in codes

    def test_liquidated_companies_flag(self):
        scorer = RiskScorer()
        records = [
            {'name': f'Company {i}', 'role': 'учредитель', 'status': 'ликвидирована', 'end_date': '01.01.2020', 'source': 'nalog'}
            for i in range(3)
        ]
        check = _make_check(business_records=records, social_media_profiles=[{'platform': 'vk'}])
        level, flags = scorer.analyze(check)
        codes = [f['code'] for f in flags]
        assert 'liquidated_companies' in codes

    def test_manual_source_ignored(self):
        scorer = RiskScorer()
        records = [
            {'name': f'Company {i}', 'role': 'директор', 'source': 'manual'}
            for i in range(10)
        ]
        check = _make_check(business_records=records, social_media_profiles=[{'platform': 'vk'}])
        level, flags = scorer.analyze(check)
        assert level == 'clean'


class TestRiskScorerSanctions:
    """Tests for sanctions-related red flags."""

    def test_sanctions_match_critical(self):
        scorer = RiskScorer()
        sanctions = [
            {'source_name': 'SDN List', 'checked': True, 'found': True, 'match_details': 'Exact match'},
        ]
        check = _make_check(sanctions_results=sanctions, social_media_profiles=[{'platform': 'vk'}])
        level, flags = scorer.analyze(check)
        assert level == 'critical'
        codes = [f['code'] for f in flags]
        assert 'sanctions_match' in codes

    def test_sanctions_not_found(self):
        scorer = RiskScorer()
        sanctions = [
            {'source_name': 'SDN List', 'checked': True, 'found': False},
        ]
        check = _make_check(sanctions_results=sanctions, social_media_profiles=[{'platform': 'vk'}])
        level, flags = scorer.analyze(check)
        assert level == 'clean'


class TestRiskScorerBankruptcy:
    """Tests for bankruptcy red flags."""

    def test_active_bankruptcy_high(self):
        scorer = RiskScorer()
        records = [
            {'is_active': True, 'stage': 'Конкурсное производство', 'source': 'efrsb'},
        ]
        check = _make_check(bankruptcy_records=records, social_media_profiles=[{'platform': 'vk'}])
        level, flags = scorer.analyze(check)
        codes = [f['code'] for f in flags]
        assert 'active_bankruptcy' in codes
        assert any(f['severity'] == 'high' for f in flags if f['code'] == 'active_bankruptcy')


class TestRiskScorerLevel:
    """Tests for risk level thresholds."""

    def test_no_flags_clean(self):
        assert RiskScorer._calculate_risk_level([]) == 'clean'

    def test_one_medium_is_low(self):
        flags = [{'severity': 'medium'}]
        assert RiskScorer._calculate_risk_level(flags) == 'low'

    def test_one_high_is_medium(self):
        flags = [{'severity': 'high'}]
        assert RiskScorer._calculate_risk_level(flags) == 'medium'

    def test_two_high_is_high(self):
        flags = [{'severity': 'high'}, {'severity': 'high'}]
        assert RiskScorer._calculate_risk_level(flags) == 'high'

    def test_critical_always_critical(self):
        flags = [{'severity': 'critical'}]
        assert RiskScorer._calculate_risk_level(flags) == 'critical'

    def test_three_medium_is_medium(self):
        flags = [{'severity': 'medium'}] * 3
        assert RiskScorer._calculate_risk_level(flags) == 'medium'

    def test_red_flag_count(self):
        scorer = RiskScorer()
        records = [
            {'name': f'Company {i}', 'role': 'директор', 'status': 'действующая', 'source': 'nalog'}
            for i in range(6)
        ]
        check = _make_check(business_records=records, social_media_profiles=[{'platform': 'vk'}])
        _, flags = scorer.analyze(check)
        assert len(flags) >= 1
