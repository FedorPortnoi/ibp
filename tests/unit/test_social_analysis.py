"""
Tests for Stage 5: Social Analysis Orchestrator
"""

import pytest
from unittest.mock import patch, MagicMock, PropertyMock
from app.services.candidate.social_analysis import (
    run_social_analysis,
    _demo_response,
    _extract_usernames,
    _get_photo_url,
    _get_vk_id,
    _collect_new_accounts,
    _run_face_search,
    _run_snoop_search,
    _run_yaseeker,
)


def _make_check(**overrides):
    """Create a mock CandidateCheck."""
    check = MagicMock()
    check.full_name = overrides.get('full_name', 'Иванов Иван Петрович')
    check.confirmed_profiles = overrides.get('confirmed_profiles', [])
    check.social_media_profiles = overrides.get('social_media_profiles', [])
    check.contact_discoveries = overrides.get('contact_discoveries', {})
    return check


class TestDemoMode:
    """Test demo mode response."""

    def test_demo_returns_expected_structure(self):
        result = _demo_response()
        assert 'face_matches' in result
        assert 'social_graph' in result
        assert 'username_accounts' in result
        assert 'new_accounts_for_enrichment' in result

    def test_demo_face_matches_count(self):
        result = _demo_response()
        assert len(result['face_matches']) == 3

    def test_demo_face_matches_have_scores(self):
        result = _demo_response()
        scores = [m['similarity_score'] for m in result['face_matches']]
        assert scores == [0.92, 0.87, 0.73]

    def test_demo_social_graph_has_15_nodes(self):
        result = _demo_response()
        assert len(result['social_graph']['nodes']) == 15

    def test_demo_social_graph_has_edges(self):
        result = _demo_response()
        assert len(result['social_graph']['edges']) >= 19

    def test_demo_username_accounts_count(self):
        result = _demo_response()
        assert len(result['username_accounts']) == 5

    def test_demo_new_accounts_count(self):
        result = _demo_response()
        assert len(result['new_accounts_for_enrichment']) == 2

    @patch.dict('os.environ', {}, clear=True)
    def test_no_profiles_no_token_returns_demo(self):
        check = _make_check()
        # Remove VK token env vars
        with patch.dict('os.environ', {'VK_SERVICE_TOKEN': '', 'VK_TOKEN': ''}, clear=False):
            result = run_social_analysis(check)
        assert len(result['face_matches']) == 3
        assert len(result['username_accounts']) == 5


class TestExtractHelpers:
    """Test helper extraction functions."""

    def test_extract_usernames_from_profiles(self):
        profiles = [
            {'username': 'ivan.petrov', 'platform': 'vk'},
            {'username': 'ipetrov', 'platform': 'telegram'},
        ]
        result = _extract_usernames(profiles)
        assert 'ivan.petrov' in result
        assert 'ipetrov' in result

    def test_extract_usernames_skips_vk_ids(self):
        profiles = [
            {'username': 'id12345678', 'platform': 'vk'},
            {'username': 'ivan_real', 'platform': 'vk'},
        ]
        result = _extract_usernames(profiles)
        assert 'id12345678' not in result
        assert 'ivan_real' in result

    def test_extract_usernames_skips_short(self):
        profiles = [{'username': 'ab', 'platform': 'vk'}]
        result = _extract_usernames(profiles)
        assert len(result) == 0

    def test_extract_usernames_max_5(self):
        profiles = [
            {'username': f'user{i}', 'platform': 'vk'} for i in range(10)
        ]
        result = _extract_usernames(profiles)
        assert len(result) <= 5

    def test_get_photo_url_returns_first_valid(self):
        profiles = [
            {'photo_url': None},
            {'photo_url': 'https://example.com/photo.jpg'},
        ]
        assert _get_photo_url(profiles) == 'https://example.com/photo.jpg'

    def test_get_photo_url_skips_default_camera(self):
        profiles = [
            {'photo_url': 'https://vk.com/images/camera_100.png'},
        ]
        assert _get_photo_url(profiles) is None

    def test_get_photo_url_no_photos(self):
        assert _get_photo_url([]) is None

    def test_get_vk_id_from_platform_id(self):
        profiles = [{'platform': 'vk', 'platform_id': '12345'}]
        assert _get_vk_id(profiles) == 12345

    def test_get_vk_id_no_vk_profile(self):
        profiles = [{'platform': 'telegram', 'platform_id': '12345'}]
        assert _get_vk_id(profiles) is None


class TestCollectNewAccounts:
    """Test new account collection logic."""

    def test_collects_from_face_matches(self):
        matches = [
            {'profile_url': 'https://vk.com/newuser', 'username': 'newuser', 'platform': 'vk'},
        ]
        result = _collect_new_accounts(matches, [], {})
        assert len(result) == 1
        assert result[0]['source'] == 'face_search'

    def test_collects_from_username_accounts(self):
        accounts = [
            {'url': 'https://github.com/test', 'username': 'test', 'platform': 'github', 'source': 'snoop'},
        ]
        result = _collect_new_accounts([], accounts, {})
        assert len(result) == 1

    def test_deduplicates_by_url(self):
        matches = [
            {'profile_url': 'https://vk.com/same', 'username': 'same', 'platform': 'vk'},
        ]
        accounts = [
            {'url': 'https://vk.com/same', 'username': 'same', 'platform': 'vk', 'source': 'snoop'},
        ]
        result = _collect_new_accounts(matches, accounts, {})
        assert len(result) == 1

    def test_empty_inputs_return_empty(self):
        result = _collect_new_accounts([], [], {})
        assert result == []


class TestSubTaskIsolation:
    """Test that sub-task failures are isolated."""

    @patch('app.services.candidate.social_analysis._run_face_search', side_effect=Exception("Face search exploded"))
    @patch('app.services.candidate.social_analysis._run_snoop_search', return_value=[])
    @patch('app.services.candidate.social_analysis._run_yaseeker', return_value=[])
    def test_face_search_failure_doesnt_break_others(self, mock_ya, mock_snoop, mock_face):
        check = _make_check(
            confirmed_profiles=[
                {'platform': 'vk', 'platform_id': '123', 'username': 'testuser',
                 'photo_url': 'https://example.com/photo.jpg'}
            ]
        )
        result = run_social_analysis(check)
        assert 'face_matches' in result
        assert 'username_accounts' in result

    @patch('app.services.candidate.social_analysis._run_face_search', return_value=[])
    @patch('app.services.candidate.social_analysis._run_snoop_search', side_effect=Exception("Snoop exploded"))
    @patch('app.services.candidate.social_analysis._run_yaseeker', return_value=[])
    def test_snoop_failure_doesnt_break_others(self, mock_ya, mock_snoop, mock_face):
        check = _make_check(
            confirmed_profiles=[
                {'platform': 'vk', 'platform_id': '123', 'username': 'testuser',
                 'photo_url': 'https://example.com/photo.jpg'}
            ]
        )
        result = run_social_analysis(check)
        assert 'face_matches' in result
        assert 'username_accounts' in result

    @patch('app.services.candidate.social_analysis._run_face_search', return_value=[])
    @patch('app.services.candidate.social_analysis._run_snoop_search', return_value=[])
    @patch('app.services.candidate.social_analysis._run_yaseeker', side_effect=Exception("YaSeeker exploded"))
    def test_yaseeker_failure_doesnt_break_others(self, mock_ya, mock_snoop, mock_face):
        check = _make_check(
            confirmed_profiles=[
                {'platform': 'vk', 'platform_id': '123', 'username': 'testuser',
                 'photo_url': 'https://example.com/photo.jpg'}
            ]
        )
        result = run_social_analysis(check)
        assert 'face_matches' in result
        assert 'username_accounts' in result


class TestNoDataCases:
    """Test behavior with missing data."""

    def test_no_vk_profiles_skips_graph(self):
        check = _make_check(
            confirmed_profiles=[
                {'platform': 'telegram', 'username': 'testuser'}
            ]
        )
        with patch('app.services.candidate.social_analysis._run_snoop_search', return_value=[]):
            with patch('app.services.candidate.social_analysis._run_yaseeker', return_value=[]):
                result = run_social_analysis(check)
        assert result['social_graph'] == {}

    def test_no_photo_skips_face_search(self):
        check = _make_check(
            confirmed_profiles=[
                {'platform': 'vk', 'platform_id': '123', 'username': 'testuser'}
            ]
        )
        with patch('app.services.candidate.social_analysis._run_snoop_search', return_value=[]) as mock_snoop:
            with patch('app.services.candidate.social_analysis._run_yaseeker', return_value=[]):
                with patch('app.services.candidate.social_analysis._run_face_search') as mock_face:
                    result = run_social_analysis(check)
        # Face search should NOT have been called (no photo)
        mock_face.assert_not_called()

    def test_no_usernames_skips_snoop_and_yaseeker(self):
        check = _make_check(
            confirmed_profiles=[
                {'platform': 'vk', 'platform_id': '123',
                 'photo_url': 'https://example.com/photo.jpg'}
            ]
        )
        with patch('app.services.candidate.social_analysis._run_face_search', return_value=[]) as mock_face:
            with patch('app.services.candidate.social_analysis._run_snoop_search') as mock_snoop:
                with patch('app.services.candidate.social_analysis._run_yaseeker') as mock_ya:
                    result = run_social_analysis(check)
        mock_snoop.assert_not_called()
        mock_ya.assert_not_called()

    def test_callback_called(self):
        callback = MagicMock()
        check = _make_check(
            confirmed_profiles=[
                {'platform': 'vk', 'platform_id': '123', 'username': 'test',
                 'photo_url': 'https://example.com/photo.jpg'}
            ]
        )
        with patch('app.services.candidate.social_analysis._run_face_search', return_value=[]):
            with patch('app.services.candidate.social_analysis._run_snoop_search', return_value=[]):
                with patch('app.services.candidate.social_analysis._run_yaseeker', return_value=[]):
                    run_social_analysis(check, task_status_callback=callback)
        assert callback.call_count >= 1
