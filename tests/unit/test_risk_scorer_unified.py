"""
Tests for RiskScorer unified pipeline dimensions.
Tests new Category 7 (social behavior) and Category 8 (behavioral patterns).
"""

import pytest
from unittest.mock import MagicMock
from datetime import datetime, timedelta
from app.services.candidate.risk_scorer import RiskScorer


def _make_check(**overrides):
    """Create a mock CandidateCheck with default empty values."""
    check = MagicMock()
    check.business_records = overrides.get('business_records', [])
    check.court_records = overrides.get('court_records', [])
    check.fssp_records = overrides.get('fssp_records', [])
    check.bankruptcy_records = overrides.get('bankruptcy_records', [])
    check.sanctions_results = overrides.get('sanctions_results', {})
    check.social_media_profiles = overrides.get('social_media_profiles', [])
    check.social_graph_data = overrides.get('social_graph_data', {})
    check.face_matches = overrides.get('face_matches', [])
    check.username_accounts = overrides.get('username_accounts', [])
    check.text_analysis = overrides.get('text_analysis', {})
    check.geo_analysis = overrides.get('geo_analysis', {})
    check.activity_timeline = overrides.get('activity_timeline', [])
    check.registered_address = overrides.get('registered_address', '')
    check.full_name = overrides.get('full_name', 'Тест Тестов')
    return check


class TestSocialBehaviorEmpty:
    """Test Category 7 with empty/default data."""

    def test_empty_graph_no_flags(self):
        scorer = RiskScorer()
        check = _make_check()
        flags = scorer._analyze_social_behavior(check)
        # Empty dict should not trigger no_friends (graph not built yet)
        codes = [f['code'] for f in flags]
        assert 'no_friends' not in codes

    def test_empty_string_graph_no_crash(self):
        scorer = RiskScorer()
        check = _make_check(social_graph_data='{}')
        flags = scorer._analyze_social_behavior(check)
        assert isinstance(flags, list)

    def test_invalid_json_string_no_crash(self):
        scorer = RiskScorer()
        check = _make_check(social_graph_data='not json')
        flags = scorer._analyze_social_behavior(check)
        assert isinstance(flags, list)


class TestSocialBehaviorFlags:
    """Test Category 7 flag detection."""

    def test_no_friends_flag(self):
        scorer = RiskScorer()
        check = _make_check(social_graph_data={
            'nodes': [],
            'edges': [],
            'stats': {'node_count': 0, 'edge_count': 0},
        })
        flags = scorer._analyze_social_behavior(check)
        codes = [f['code'] for f in flags]
        assert 'no_friends' in codes

    def test_isolated_graph_flag(self):
        scorer = RiskScorer()
        check = _make_check(social_graph_data={
            'nodes': [{'id': 'vk_1'}, {'id': 'vk_2'}],
            'edges': [],
            'stats': {'node_count': 2, 'edge_count': 0},
        })
        flags = scorer._analyze_social_behavior(check)
        codes = [f['code'] for f in flags]
        assert 'isolated_graph' in codes

    def test_isolated_graph_severity_medium(self):
        scorer = RiskScorer()
        check = _make_check(social_graph_data={
            'stats': {'node_count': 5, 'edge_count': 0},
        })
        flags = scorer._analyze_social_behavior(check)
        isolated = [f for f in flags if f['code'] == 'isolated_graph']
        assert len(isolated) == 1
        assert isolated[0]['severity'] == 'medium'

    def test_fake_profile_indicators(self):
        scorer = RiskScorer()
        check = _make_check(social_media_profiles=[
            {'platform': 'vk', 'username': 'test', 'photo_url': '', 'photo_100': '', 'post_count': 0},
        ])
        flags = scorer._analyze_social_behavior(check)
        codes = [f['code'] for f in flags]
        assert 'fake_profile_indicators' in codes

    def test_established_identity_5_platforms(self):
        scorer = RiskScorer()
        accounts = [
            {'platform': f'platform{i}', 'url': f'https://example{i}.com/user'}
            for i in range(6)
        ]
        check = _make_check(username_accounts=accounts)
        flags = scorer._analyze_social_behavior(check)
        codes = [f['code'] for f in flags]
        assert 'established_identity' in codes

    def test_established_identity_severity_low(self):
        scorer = RiskScorer()
        accounts = [{'platform': f'p{i}'} for i in range(7)]
        check = _make_check(username_accounts=accounts)
        flags = scorer._analyze_social_behavior(check)
        est = [f for f in flags if f['code'] == 'established_identity']
        assert len(est) == 1
        assert est[0]['severity'] == 'low'

    def test_normal_graph_no_flags(self):
        scorer = RiskScorer()
        check = _make_check(social_graph_data={
            'stats': {'node_count': 50, 'edge_count': 120},
        })
        flags = scorer._analyze_social_behavior(check)
        codes = [f['code'] for f in flags]
        assert 'no_friends' not in codes
        assert 'isolated_graph' not in codes


class TestBehavioralPatternsEmpty:
    """Test Category 8 with empty/default data."""

    def test_empty_text_analysis_no_flags(self):
        scorer = RiskScorer()
        check = _make_check()
        flags = scorer._analyze_behavioral_patterns(check)
        assert isinstance(flags, list)
        assert len(flags) == 0

    def test_empty_string_text_analysis(self):
        scorer = RiskScorer()
        check = _make_check(text_analysis='{}')
        flags = scorer._analyze_behavioral_patterns(check)
        assert isinstance(flags, list)

    def test_empty_geo_analysis_no_crash(self):
        scorer = RiskScorer()
        check = _make_check(geo_analysis='{}')
        flags = scorer._analyze_behavioral_patterns(check)
        assert isinstance(flags, list)


class TestBehavioralPatternsFlags:
    """Test Category 8 flag detection."""

    def test_negative_sentiment_flag(self):
        scorer = RiskScorer()
        check = _make_check(text_analysis={
            'sentiment': {'score': -0.5, 'label': 'negative'},
        })
        flags = scorer._analyze_behavioral_patterns(check)
        codes = [f['code'] for f in flags]
        assert 'negative_sentiment' in codes

    def test_neutral_sentiment_no_flag(self):
        scorer = RiskScorer()
        check = _make_check(text_analysis={
            'sentiment': {'score': 0.1, 'label': 'neutral'},
        })
        flags = scorer._analyze_behavioral_patterns(check)
        codes = [f['code'] for f in flags]
        assert 'negative_sentiment' not in codes

    def test_risk_keywords_flag(self):
        scorer = RiskScorer()
        check = _make_check(text_analysis={
            'keywords': [('суд', 5), ('банкрот', 3), ('работа', 10)],
        })
        flags = scorer._analyze_behavioral_patterns(check)
        codes = [f['code'] for f in flags]
        assert 'risk_keywords' in codes

    def test_risk_keywords_severity_medium(self):
        scorer = RiskScorer()
        check = _make_check(text_analysis={
            'keywords': [('долг', 8)],
        })
        flags = scorer._analyze_behavioral_patterns(check)
        rk = [f for f in flags if f['code'] == 'risk_keywords']
        assert len(rk) == 1
        assert rk[0]['severity'] == 'medium'

    def test_no_risk_keywords_no_flag(self):
        scorer = RiskScorer()
        check = _make_check(text_analysis={
            'keywords': [('работа', 10), ('друзья', 5), ('спорт', 3)],
        })
        flags = scorer._analyze_behavioral_patterns(check)
        codes = [f['code'] for f in flags]
        assert 'risk_keywords' not in codes

    def test_night_activity_flag(self):
        scorer = RiskScorer()
        # >50% of 10 posts between 2-5 AM
        check = _make_check(text_analysis={
            'posting_times': [2, 3, 4, 5, 3, 2, 12, 15, 18, 20],
        })
        flags = scorer._analyze_behavioral_patterns(check)
        codes = [f['code'] for f in flags]
        # 6 out of 10 = 60% night
        assert 'night_activity' in codes

    def test_day_activity_no_flag(self):
        scorer = RiskScorer()
        check = _make_check(text_analysis={
            'posting_times': [9, 10, 12, 14, 15, 18, 20, 21, 22, 23],
        })
        flags = scorer._analyze_behavioral_patterns(check)
        codes = [f['code'] for f in flags]
        assert 'night_activity' not in codes

    def test_geo_discrepancy_flag(self):
        scorer = RiskScorer()
        check = _make_check(
            social_media_profiles=[
                {'platform': 'vk', 'city': 'Москва'},
            ],
            geo_analysis={
                'home_location': {'city': 'Казань', 'lat': 55.83, 'lng': 49.07},
            },
        )
        flags = scorer._analyze_behavioral_patterns(check)
        codes = [f['code'] for f in flags]
        assert 'geo_discrepancy' in codes

    def test_same_city_no_geo_flag(self):
        scorer = RiskScorer()
        check = _make_check(
            social_media_profiles=[
                {'platform': 'vk', 'city': 'Москва'},
            ],
            geo_analysis={
                'home_location': {'city': 'Москва', 'lat': 55.75, 'lng': 37.62},
            },
        )
        flags = scorer._analyze_behavioral_patterns(check)
        codes = [f['code'] for f in flags]
        assert 'geo_discrepancy' not in codes

    def test_inactive_profile_flag(self):
        scorer = RiskScorer()
        old_date = (datetime.now() - timedelta(days=400)).isoformat()
        check = _make_check(activity_timeline=[
            {'type': 'post', 'timestamp': old_date, 'source': 'vk'},
        ])
        flags = scorer._analyze_behavioral_patterns(check)
        codes = [f['code'] for f in flags]
        assert 'inactive_profile' in codes

    def test_active_profile_no_flag(self):
        scorer = RiskScorer()
        recent_date = (datetime.now() - timedelta(days=30)).isoformat()
        check = _make_check(activity_timeline=[
            {'type': 'post', 'timestamp': recent_date, 'source': 'vk'},
        ])
        flags = scorer._analyze_behavioral_patterns(check)
        codes = [f['code'] for f in flags]
        assert 'inactive_profile' not in codes


class TestAnalyzeIncludesNewCategories:
    """Test that analyze() includes new categories in output."""

    def test_analyze_returns_social_behavior_flags(self):
        scorer = RiskScorer()
        check = _make_check(
            social_graph_data={'stats': {'node_count': 0, 'edge_count': 0}},
        )
        risk_level, flags = scorer.analyze(check)
        categories = [f['category'] for f in flags]
        assert 'social_behavior' in categories

    def test_analyze_returns_behavioral_flags(self):
        scorer = RiskScorer()
        check = _make_check(
            text_analysis={'sentiment': {'score': -0.5}},
        )
        risk_level, flags = scorer.analyze(check)
        categories = [f['category'] for f in flags]
        assert 'behavioral' in categories

    def test_analyze_risk_level_includes_new_flags(self):
        scorer = RiskScorer()
        check = _make_check(
            social_graph_data={'stats': {'node_count': 5, 'edge_count': 0}},
            text_analysis={'keywords': [('суд', 5), ('банкрот', 3)]},
        )
        risk_level, flags = scorer.analyze(check)
        # Two medium flags from new categories should affect risk level
        medium_flags = [f for f in flags if f['severity'] == 'medium']
        assert len(medium_flags) >= 2

    def test_analyze_empty_check_no_crash(self):
        scorer = RiskScorer()
        check = _make_check()
        risk_level, flags = scorer.analyze(check)
        assert risk_level in ('clean', 'low', 'medium', 'high', 'critical')
        assert isinstance(flags, list)
