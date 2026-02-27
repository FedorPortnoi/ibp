"""
Tests for report_builder.py (Stage 8).
Verifies build_report() compiles all pipeline data correctly.
"""

import pytest
from unittest.mock import MagicMock
from datetime import datetime, timedelta
from app.services.candidate.report_builder import build_report, _safe_json, _extract_phones, _extract_emails


def _make_check(**overrides):
    """Create a mock CandidateCheck with all fields."""
    check = MagicMock()
    check.full_name = overrides.get('full_name', 'Тестов Тест Тестович')
    check.date_of_birth = overrides.get('date_of_birth', None)
    check.created_at = overrides.get('created_at', datetime(2026, 1, 15, 10, 0, 0))
    check.completed_at = overrides.get('completed_at', datetime(2026, 1, 15, 10, 5, 0))
    check.check_duration_seconds = overrides.get('check_duration_seconds', 300)
    check.id = overrides.get('id', 'test-check-001')
    check.risk_level = overrides.get('risk_level', 'low')
    check.risk_score_numeric = overrides.get('risk_score_numeric', 15.0)
    check.check_mode = overrides.get('check_mode', 'quick')
    check.report_generated = overrides.get('report_generated', False)

    # JSON fields — can be dicts/lists or JSON strings
    check.business_records = overrides.get('business_records', [])
    check.court_records = overrides.get('court_records', [])
    check.fssp_records = overrides.get('fssp_records', [])
    check.bankruptcy_records = overrides.get('bankruptcy_records', [])
    check.sanctions_results = overrides.get('sanctions_results', {})
    check.social_media_profiles = overrides.get('social_media_profiles', [])
    check.confirmed_profiles = overrides.get('confirmed_profiles', [])
    check.contact_discoveries = overrides.get('contact_discoveries', {})
    check.social_graph_data = overrides.get('social_graph_data', {})
    check.face_matches = overrides.get('face_matches', [])
    check.username_accounts = overrides.get('username_accounts', [])
    check.text_analysis = overrides.get('text_analysis', {})
    check.geo_analysis = overrides.get('geo_analysis', {})
    check.activity_timeline = overrides.get('activity_timeline', [])
    check.red_flags = overrides.get('red_flags', [])
    check.risk_breakdown = overrides.get('risk_breakdown', {})
    check.inn = overrides.get('inn', '7707083893')
    check.confirmed_name = overrides.get('confirmed_name', None)
    check.identity_confirmed = overrides.get('identity_confirmed', False)
    check.identity_confirmation = overrides.get('identity_confirmation', {})
    return check


class TestBuildReportSections:
    """Test that build_report returns all required sections."""

    def test_all_sections_present(self):
        check = _make_check()
        report = build_report(check)
        expected_keys = [
            'identity_card', 'identity_confirmation', 'risk_summary',
            'government_records', 'sanctions', 'social_profiles',
            'contact_info', 'social_graph_summary', 'geo_summary',
            'behavioral_summary', 'face_matches', 'timeline_events',
            'metadata',
        ]
        for key in expected_keys:
            assert key in report, f"Missing section: {key}"

    def test_identity_card_fields(self):
        check = _make_check(full_name='Иванов Иван')
        report = build_report(check)
        card = report['identity_card']
        assert card['full_name'] == 'Иванов Иван'
        assert 'photo_url' in card
        assert 'city' in card
        assert 'confirmed_accounts' in card

    def test_government_records_subsections(self):
        check = _make_check(business_records=[{'company_name': 'ООО Тест'}])
        report = build_report(check)
        gov = report['government_records']
        assert 'business_records' in gov
        assert 'court_records' in gov
        assert 'fssp_records' in gov
        assert 'bankruptcy_records' in gov


class TestFullyPopulatedCheck:
    """Test with all fields populated."""

    def test_full_data_report(self):
        check = _make_check(
            full_name='Петров Пётр Петрович',
            date_of_birth=datetime(1990, 5, 20).date(),
            business_records=[{'company_name': 'ООО Рога', 'inn': '7701234567'}],
            court_records=[{'case_number': '123/2025', 'court_name': 'МГС'}],
            fssp_records=[{'case_id': 'FSSP-001'}],
            bankruptcy_records=[{'case_number': 'B-001'}],
            sanctions_results={'checked': True, 'found': False},
            social_media_profiles=[
                {'platform': 'vk', 'username': 'petrov', 'city': 'Москва', 'photo_url': 'https://vk.com/photo.jpg'},
            ],
            contact_discoveries={
                'phones': [{'number': '+79161234567', 'source': 'vk', 'confidence': 'high'}],
                'emails': [{'email': 'petrov@mail.ru', 'source': 'holehe', 'confidence': 'high', 'verified': True}],
            },
            social_graph_data={
                'nodes': [{'id': 'vk_1', 'label': 'Friend 1'}],
                'edges': [{'from': 'center', 'to': 'vk_1'}],
                'stats': {'node_count': 2, 'edge_count': 1, 'density': 0.5},
            },
            face_matches=[{'platform': 'vk', 'similarity_score': 0.95}],
            username_accounts=[{'platform': 'github', 'username': 'petrov', 'url': 'https://github.com/petrov'}],
            text_analysis={
                'sentiment': {'score': 0.1, 'label': 'neutral'},
                'keywords': [('работа', 10)],
                'topics': {'работа': 0.5},
                'posting_times': [9, 10, 14, 18],
            },
            geo_analysis={
                'home_location': {'city': 'Москва', 'lat': 55.75, 'lng': 37.62},
                'locations': [{'city': 'Москва'}],
            },
            red_flags=[{'severity': 'low', 'text': 'Мало подключений'}],
            risk_breakdown={'legal': 5, 'social': 10},
            risk_level='low',
            risk_score_numeric=15.0,
        )
        report = build_report(check)

        assert report['identity_card']['full_name'] == 'Петров Пётр Петрович'
        assert report['identity_card']['city'] == 'Москва'
        assert report['identity_card']['photo_url'] == 'https://vk.com/photo.jpg'
        assert len(report['government_records']['business_records']) == 1
        assert len(report['government_records']['court_records']) == 1
        assert len(report['contact_info']['phones']) == 1
        assert len(report['contact_info']['emails']) == 1
        assert report['social_graph_summary']['edge_count'] == 1
        assert len(report['face_matches']) == 1
        assert report['risk_summary']['risk_level'] == 'low'
        assert report['risk_summary']['risk_score'] == 15.0
        assert report['behavioral_summary']['sentiment']['label'] == 'neutral'

    def test_social_profiles_includes_username_accounts(self):
        check = _make_check(
            social_media_profiles=[{'platform': 'vk', 'username': 'user1'}],
            username_accounts=[{'platform': 'github', 'username': 'user1', 'url': 'https://github.com/user1', 'source': 'snoop'}],
        )
        report = build_report(check)
        platforms = [p['platform'] for p in report['social_profiles']]
        assert 'vk' in platforms
        assert 'github' in platforms


class TestMinimalCheck:
    """Test with only name, no other data."""

    def test_minimal_name_only(self):
        check = _make_check(full_name='Сидоров Сидор')
        report = build_report(check)
        assert report['identity_card']['full_name'] == 'Сидоров Сидор'
        assert report['identity_card']['photo_url'] == ''
        assert report['identity_card']['city'] == ''
        assert report['contact_info']['phones'] == []
        assert report['contact_info']['emails'] == []
        assert report['face_matches'] == []

    def test_minimal_no_crash(self):
        check = _make_check()
        report = build_report(check)
        assert isinstance(report, dict)
        assert len(report) >= 10


class TestDemoReport:
    """Test demo mode returns a complete structure."""

    def test_demo_returns_complete_structure(self):
        check = _make_check(full_name='', business_records=[], social_media_profiles=[], contact_discoveries={})
        report = build_report(check)
        # Should get demo report since no real data and no name
        assert report['identity_card']['full_name'] == 'Иванов Иван Петрович'
        assert report['risk_summary']['risk_level'] == 'low'

    def test_demo_all_sections_present(self):
        check = _make_check(full_name='')
        report = build_report(check)
        expected_keys = [
            'identity_card', 'risk_summary', 'government_records',
            'sanctions', 'social_profiles', 'contact_info',
            'social_graph_summary', 'geo_summary', 'behavioral_summary',
            'face_matches', 'timeline_events', 'metadata',
        ]
        for key in expected_keys:
            assert key in report

    def test_demo_has_contact_info(self):
        check = _make_check(full_name='')
        report = build_report(check)
        assert len(report['contact_info']['phones']) >= 1
        assert len(report['contact_info']['emails']) >= 1


class TestMetadata:
    """Test metadata section."""

    def test_metadata_timestamps(self):
        created = datetime(2026, 2, 1, 12, 0, 0)
        completed = datetime(2026, 2, 1, 12, 5, 0)
        check = _make_check(created_at=created, completed_at=completed)
        report = build_report(check)
        meta = report['metadata']
        assert meta['created_at'] == '2026-02-01T12:00:00'
        assert meta['completed_at'] == '2026-02-01T12:05:00'
        assert meta['duration_seconds'] == 300.0

    def test_metadata_check_id(self):
        check = _make_check(id='abc-123')
        report = build_report(check)
        assert report['metadata']['check_id'] == 'abc-123'

    def test_metadata_mode(self):
        check = _make_check(check_mode='deep')
        report = build_report(check)
        assert report['metadata']['mode'] == 'deep'


class TestHelperFunctions:
    """Test helper functions."""

    def test_safe_json_with_string(self):
        result = _safe_json('{"key": "value"}', {})
        assert result == {"key": "value"}

    def test_safe_json_with_dict(self):
        result = _safe_json({"key": "value"}, {})
        assert result == {"key": "value"}

    def test_safe_json_with_none(self):
        result = _safe_json(None, [])
        assert result == []

    def test_safe_json_with_invalid_string(self):
        result = _safe_json("not json", {})
        assert result == {}

    def test_extract_phones(self):
        contacts = {'phones': [{'number': '+79161234567', 'source': 'vk', 'confidence': 'high'}]}
        phones = _extract_phones(contacts)
        assert len(phones) == 1
        assert phones[0]['number'] == '+79161234567'

    def test_extract_emails(self):
        contacts = {'emails': [{'email': 'test@mail.ru', 'source': 'holehe', 'confidence': 'high', 'verified': True}]}
        emails = _extract_emails(contacts)
        assert len(emails) == 1
        assert emails[0]['address'] == 'test@mail.ru'
        assert emails[0]['verified'] is True

    def test_extract_phones_empty(self):
        assert _extract_phones({}) == []
        assert _extract_phones({'phones': None}) == []

    def test_extract_emails_empty(self):
        assert _extract_emails({}) == []
        assert _extract_emails({'emails': None}) == []


class TestTimelineEvents:
    """Test timeline event building."""

    def test_timeline_includes_check_events(self):
        check = _make_check(
            created_at=datetime(2026, 1, 15, 10, 0),
            completed_at=datetime(2026, 1, 15, 10, 5),
        )
        report = build_report(check)
        types = [e['type'] for e in report['timeline_events']]
        assert 'check_started' in types
        assert 'check_completed' in types

    def test_timeline_sorted_newest_first(self):
        check = _make_check(
            activity_timeline=[
                {'timestamp': '2026-01-10T08:00:00', 'type': 'post', 'source': 'vk', 'summary': 'Пост'},
            ],
            created_at=datetime(2026, 1, 15, 10, 0),
            completed_at=datetime(2026, 1, 15, 10, 5),
        )
        report = build_report(check)
        timestamps = [e['timestamp'] for e in report['timeline_events']]
        assert timestamps == sorted(timestamps, reverse=True)


class TestStagesCounted:
    """Test _count_stages logic via metadata."""

    def test_stages_with_all_data(self):
        check = _make_check(
            business_records=[{'x': 1}],
            sanctions_results={'checked': True},
            social_media_profiles=[{'platform': 'vk'}],
            contact_discoveries={'phones': [{'number': '123'}]},
            social_graph_data={'stats': {'node_count': 5}},
            text_analysis={'sentiment': {'score': 0.1}},
            risk_level='low',
            report_generated=True,
            identity_confirmed=True,
        )
        report = build_report(check)
        assert report['metadata']['stages_completed'] == 9  # Stage 0-8

    def test_stages_empty_check(self):
        check = _make_check(risk_level=None, report_generated=False)
        report = build_report(check)
        assert report['metadata']['stages_completed'] == 0
