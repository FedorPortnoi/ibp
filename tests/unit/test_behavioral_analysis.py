"""
Tests for Stage 6: Behavioral Analysis Orchestrator
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime
from app.services.candidate.behavioral_analysis import (
    run_behavioral_analysis,
    _demo_response,
    _get_vk_profiles,
    _fetch_vk_wall_posts,
    _build_activity_timeline,
    _run_text_analysis,
    _run_geo_extraction,
)


def _make_check(**overrides):
    """Create a mock CandidateCheck."""
    check = MagicMock()
    check.full_name = overrides.get('full_name', 'Иванов Иван Петрович')
    check.confirmed_profiles = overrides.get('confirmed_profiles', [])
    check.social_media_profiles = overrides.get('social_media_profiles', [])
    check.created_at = overrides.get('created_at', datetime(2026, 1, 15, 10, 0))
    return check


class TestDemoMode:
    """Test demo mode response."""

    def test_demo_returns_expected_keys(self):
        result = _demo_response()
        assert 'text_analysis' in result
        assert 'geo_analysis' in result
        assert 'activity_timeline' in result

    def test_demo_text_analysis_has_sentiment(self):
        result = _demo_response()
        assert 'sentiment' in result['text_analysis']
        assert result['text_analysis']['sentiment']['score'] == 0.15

    def test_demo_text_analysis_has_keywords(self):
        result = _demo_response()
        assert len(result['text_analysis']['keywords']) == 10

    def test_demo_text_analysis_has_topics(self):
        result = _demo_response()
        assert len(result['text_analysis']['topics']) == 3

    def test_demo_geo_has_4_locations(self):
        result = _demo_response()
        assert len(result['geo_analysis']['locations']) == 4

    def test_demo_geo_has_home_location(self):
        result = _demo_response()
        assert result['geo_analysis']['home_location'] is not None
        assert result['geo_analysis']['home_location']['city'] == 'Москва'

    def test_demo_geo_has_frequent_places(self):
        result = _demo_response()
        assert len(result['geo_analysis']['frequent_places']) == 4

    def test_demo_timeline_has_30_events(self):
        result = _demo_response()
        assert len(result['activity_timeline']) == 30

    @patch.dict('os.environ', {'VK_SERVICE_TOKEN': '', 'VK_TOKEN': '', 'VK_USER_TOKEN': ''})
    def test_no_token_returns_demo(self):
        check = _make_check()
        result = run_behavioral_analysis(check)
        assert len(result['activity_timeline']) == 30
        assert result['text_analysis']['sentiment']['score'] == 0.15


class TestGetVkProfiles:
    """Test VK profile extraction."""

    def test_extracts_vk_only(self):
        check = _make_check(confirmed_profiles=[
            {'platform': 'vk', 'platform_id': '123'},
            {'platform': 'telegram', 'platform_id': '456'},
        ])
        result = _get_vk_profiles(check)
        assert len(result) == 1
        assert result[0]['platform'] == 'vk'

    def test_empty_profiles(self):
        check = _make_check()
        result = _get_vk_profiles(check)
        assert result == []

    def test_uses_social_media_profiles_fallback(self):
        check = _make_check(
            confirmed_profiles=[],
            social_media_profiles=[{'platform': 'vk', 'platform_id': '789'}],
        )
        result = _get_vk_profiles(check)
        assert len(result) == 1


class TestBuildTimeline:
    """Test activity timeline building."""

    def test_sorts_newest_first(self):
        posts = [
            {'text': 'Old post', 'date': 1700000000},
            {'text': 'New post', 'date': 1700100000},
        ]
        check = _make_check()
        result = _build_activity_timeline(posts, check)
        assert result[0]['timestamp'] > result[1]['timestamp']

    def test_includes_check_creation(self):
        check = _make_check(created_at=datetime(2026, 1, 15))
        result = _build_activity_timeline([], check)
        assert any(e['type'] == 'check_started' for e in result)

    def test_limits_to_100(self):
        posts = [{'text': f'Post {i}', 'date': 1700000000 + i * 100} for i in range(150)]
        check = _make_check()
        result = _build_activity_timeline(posts, check)
        assert len(result) <= 100

    def test_handles_missing_dates(self):
        posts = [
            {'text': 'No date post'},
            {'text': 'Has date', 'date': 1700000000},
        ]
        check = _make_check()
        result = _build_activity_timeline(posts, check)
        # Only posts with dates + check_started
        post_events = [e for e in result if e['type'] == 'post']
        assert len(post_events) == 1

    def test_empty_posts_returns_check_event(self):
        check = _make_check()
        result = _build_activity_timeline([], check)
        assert len(result) == 1
        assert result[0]['type'] == 'check_started'


class TestSubTaskIsolation:
    """Test that sub-task failures are isolated."""

    @patch.dict('os.environ', {'VK_SERVICE_TOKEN': 'test_token'})
    @patch('app.services.candidate.behavioral_analysis._fetch_vk_wall_posts', return_value=[])
    @patch('app.services.candidate.behavioral_analysis._run_text_analysis', side_effect=Exception("Text exploded"))
    @patch('app.services.candidate.behavioral_analysis._run_geo_extraction', return_value={'locations': []})
    def test_text_analysis_failure_isolated(self, mock_geo, mock_text, mock_wall):
        check = _make_check(confirmed_profiles=[{'platform': 'vk', 'platform_id': '123'}])
        result = run_behavioral_analysis(check)
        assert 'geo_analysis' in result
        assert 'activity_timeline' in result

    @patch.dict('os.environ', {'VK_SERVICE_TOKEN': 'test_token'})
    @patch('app.services.candidate.behavioral_analysis._fetch_vk_wall_posts', return_value=[])
    @patch('app.services.candidate.behavioral_analysis._run_text_analysis', return_value={})
    @patch('app.services.candidate.behavioral_analysis._run_geo_extraction', side_effect=Exception("Geo exploded"))
    def test_geo_extraction_failure_isolated(self, mock_geo, mock_text, mock_wall):
        check = _make_check(confirmed_profiles=[{'platform': 'vk', 'platform_id': '123'}])
        result = run_behavioral_analysis(check)
        assert 'text_analysis' in result
        assert 'activity_timeline' in result

    @patch.dict('os.environ', {'VK_SERVICE_TOKEN': 'test_token'})
    @patch('app.services.candidate.behavioral_analysis._fetch_vk_wall_posts', return_value=[])
    def test_no_posts_returns_valid_structure(self, mock_wall):
        check = _make_check(confirmed_profiles=[{'platform': 'vk', 'platform_id': '123'}])
        with patch('app.services.candidate.behavioral_analysis._run_geo_extraction', return_value={}):
            result = run_behavioral_analysis(check)
        assert result['text_analysis'] == {}
        assert 'activity_timeline' in result

    @patch.dict('os.environ', {'VK_SERVICE_TOKEN': 'test_token'})
    def test_callback_called(self):
        callback = MagicMock()
        check = _make_check(confirmed_profiles=[{'platform': 'vk', 'platform_id': '123'}])
        with patch('app.services.candidate.behavioral_analysis._fetch_vk_wall_posts', return_value=[]):
            with patch('app.services.candidate.behavioral_analysis._run_geo_extraction', return_value={}):
                run_behavioral_analysis(check, task_status_callback=callback)
        assert callback.call_count >= 1
