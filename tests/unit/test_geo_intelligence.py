"""
Tests for Geo Intelligence Service
====================================
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

from app.services.phase3.geo_intelligence import (
    geocode_city,
    parse_vk_activity,
    build_location_history,
    collect_geo_intelligence,
    _extract_vk_profile_locations,
    _extract_egrul_locations,
    _extract_form_location,
    _extract_telegram_locations,
    _extract_city_from_address,
    _get_demo_geo_intelligence,
)


class TestGeocodeCity:
    """Test geocoding from local dictionary + Nominatim fallback."""

    def test_geocode_moscow(self):
        lat, lon = geocode_city('Москва')
        assert abs(lat - 55.7558) < 0.01
        assert abs(lon - 37.6173) < 0.01

    def test_geocode_moscow_prefix(self):
        lat, lon = geocode_city('г. Москва')
        assert abs(lat - 55.7558) < 0.01

    def test_geocode_kazan(self):
        lat, lon = geocode_city('Казань')
        assert abs(lat - 55.83) < 0.01
        assert abs(lon - 49.07) < 0.1

    def test_geocode_spb_alias(self):
        lat, lon = geocode_city('СПб')
        assert abs(lat - 59.93) < 0.1

    def test_geocode_with_country_suffix(self):
        lat, lon = geocode_city('Москва, Россия')
        assert abs(lat - 55.7558) < 0.01

    def test_geocode_empty(self):
        assert geocode_city('') is None
        assert geocode_city(None) is None

    def test_geocode_unknown_no_network(self):
        """Unknown city without network should return None (Nominatim mocked)."""
        with patch('app.services.phase3.geo_intelligence._nominatim_geocode', return_value=None):
            result = geocode_city('НесуществующийГород12345')
            assert result is None

    def test_geocode_yo_normalization(self):
        """ё should be normalized to е for lookup."""
        # 'орёл' → 'орел' in the dict? Actually 'орёл' is in RUSSIAN_CITIES
        result = geocode_city('Орёл')
        assert result is not None


class TestParseVkActivity:
    """Test 7-day activity timeline construction."""

    def test_empty_input(self):
        result = parse_vk_activity({}, [])
        assert len(result) == 7
        for day in result:
            assert day['total_activity'] == 0
            assert 'date' in day
            assert 'day_label' in day
            assert 'slots' in day

    def test_with_activity_patterns(self):
        now = datetime.now()
        ts = int(now.timestamp())
        patterns = {
            'last_seen': {
                'most_recent': {
                    'last_seen_ts': ts,
                    'platform_name': 'Android',
                },
                'preferred_platform': 'mobile',
            }
        }
        result = parse_vk_activity(patterns, [])
        # Today should have activity
        today = result[-1]
        assert today['date'] == now.strftime('%Y-%m-%d')
        assert today['total_activity'] >= 1
        assert today['platform'] is not None

    def test_with_timeline_entries(self):
        now = datetime.now()
        # Create a morning entry for today
        morning = now.replace(hour=9, minute=0, second=0)
        timeline = [{'timestamp': int(morning.timestamp())}]
        result = parse_vk_activity({}, timeline)
        today = result[-1]
        assert today['slots']['morning'] is True

    def test_seven_days_coverage(self):
        result = parse_vk_activity({}, [])
        assert len(result) == 7
        dates = [d['date'] for d in result]
        # Should be chronological
        assert dates == sorted(dates)
        # First day is 6 days ago
        now = datetime.now()
        expected_first = (now - timedelta(days=6)).strftime('%Y-%m-%d')
        assert result[0]['date'] == expected_first

    def test_day_labels_russian(self):
        result = parse_vk_activity({}, [])
        valid_labels = {'Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'}
        for day in result:
            assert day['day_label'] in valid_labels


class TestBuildLocationHistory:
    """Test chronological location history construction."""

    def test_empty(self):
        assert build_location_history([]) == []

    def test_sorted_chronologically(self):
        points = [
            {'source': 'vk_post', 'location': 'Москва', 'timestamp': '2025-06-01', 'confidence': 'high'},
            {'source': 'form', 'location': 'Казань', 'timestamp': '2024-01-15', 'confidence': 'high'},
            {'source': 'egrul', 'location': 'Самара', 'timestamp': '2023-03-10', 'confidence': 'high'},
        ]
        history = build_location_history(points)
        assert len(history) == 3
        # Check chronological order
        assert history[0]['location'] == 'Самара'
        assert history[1]['location'] == 'Казань'
        assert history[2]['location'] == 'Москва'

    def test_deduplication(self):
        points = [
            {'source': 'vk_profile', 'location': 'Москва', 'timestamp': None, 'confidence': 'high'},
            {'source': 'vk_profile', 'location': 'Москва', 'timestamp': None, 'confidence': 'high'},
        ]
        history = build_location_history(points)
        assert len(history) == 1

    def test_date_display_format(self):
        points = [
            {'source': 'egrul', 'location': 'Тула', 'timestamp': '2024-03-15', 'confidence': 'high'},
        ]
        history = build_location_history(points)
        assert history[0]['date_display'] == 'Мар 2024'

    def test_undated_entries_last(self):
        points = [
            {'source': 'vk_profile', 'location': 'Москва', 'timestamp': None, 'confidence': 'high'},
            {'source': 'egrul', 'location': 'Казань', 'timestamp': '2024-01-01', 'confidence': 'high'},
        ]
        history = build_location_history(points)
        assert history[0]['location'] == 'Казань'  # Dated first
        assert history[1]['location'] == 'Москва'  # Undated last

    def test_source_labels(self):
        points = [
            {'source': 'vk_profile', 'location': 'A', 'timestamp': None, 'confidence': 'high'},
            {'source': 'egrul', 'location': 'B', 'timestamp': None, 'confidence': 'medium'},
            {'source': 'telegram', 'location': 'C', 'timestamp': None, 'confidence': 'low'},
        ]
        history = build_location_history(points)
        labels = [h['source_label'] for h in history]
        assert 'VK профиль' in labels
        assert 'ЕГРЮЛ' in labels
        assert 'Telegram' in labels


class TestExtractors:
    """Test individual data extractors."""

    def test_extract_city_from_address(self):
        assert _extract_city_from_address('г. Москва, ул. Ленина, д. 10') == 'Москва'
        assert _extract_city_from_address('г Казань, ул. Баумана') == 'Казань'
        assert _extract_city_from_address('') == ''

    def test_vk_profile_locations(self):
        profiles = [{
            'platform': 'vk',
            'vk_data': {
                'city': {'title': 'Москва'},
                'country': {'title': 'Россия'},
                'home_town': 'Казань',
            },
        }]
        points = _extract_vk_profile_locations(profiles)
        assert len(points) == 2  # city + home_town
        assert points[0]['source'] == 'vk_profile'
        assert points[0]['icon_color'] == 'yellow'
        assert 'Москва' in points[0]['location']
        assert 'Казань' in points[1]['location']

    def test_vk_profile_same_city_hometown(self):
        """If city == home_town, only one point."""
        profiles = [{
            'platform': 'vk',
            'vk_data': {
                'city': {'title': 'Москва'},
                'home_town': 'Москва',
            },
        }]
        points = _extract_vk_profile_locations(profiles)
        assert len(points) == 1

    def test_egrul_locations(self):
        identity = {
            'egrul': {'address': 'г. Москва, ул. Тверская, д. 1', 'registration_date': '01.01.2020'},
        }
        biz = [
            {'name': 'ООО Тест', 'address': 'г. Казань, ул. Пушкина, д. 5', 'registration_date': '15.03.2018'},
        ]
        points = _extract_egrul_locations(identity, biz)
        assert len(points) == 2
        assert all(p['source'] == 'egrul' for p in points)
        assert all(p['icon_color'] == 'red' for p in points)

    def test_form_location(self):
        points = _extract_form_location('г. Москва, ул. Ленина, д. 10', '')
        assert len(points) == 1
        assert points[0]['source'] == 'form'
        assert points[0]['icon_color'] == 'red'

    def test_form_region_fallback(self):
        points = _extract_form_location('', 'Москва')
        assert len(points) == 1
        assert points[0]['lat'] is not None

    def test_telegram_bio_city(self):
        # Bio must contain exact city name (nominative case) for matching
        profiles = [{
            'platform': 'telegram',
            'bio': 'Москва | Разработчик',
        }]
        points = _extract_telegram_locations(profiles)
        assert len(points) == 1
        assert points[0]['source'] == 'telegram'
        assert points[0]['icon_color'] == 'blue'

    def test_telegram_bio_no_city(self):
        profiles = [{
            'platform': 'telegram',
            'bio': 'Просто человек',
        }]
        points = _extract_telegram_locations(profiles)
        assert len(points) == 0


class TestDemoData:
    """Test demo data structure."""

    def test_demo_data_structure(self):
        data = _get_demo_geo_intelligence()
        assert 'location_points' in data
        assert 'activity_timeline' in data
        assert 'location_history' in data
        assert 'summary' in data

    def test_demo_location_points(self):
        data = _get_demo_geo_intelligence()
        points = data['location_points']
        assert len(points) >= 3
        for pt in points:
            assert 'source' in pt
            assert 'label' in pt
            assert 'location' in pt
            assert 'lat' in pt
            assert 'lon' in pt
            assert 'confidence' in pt
            assert 'icon_color' in pt

    def test_demo_activity_timeline(self):
        data = _get_demo_geo_intelligence()
        timeline = data['activity_timeline']
        assert len(timeline) == 7
        for day in timeline:
            assert 'date' in day
            assert 'day_label' in day
            assert 'slots' in day
            assert 'platform' in day

    def test_demo_location_history(self):
        data = _get_demo_geo_intelligence()
        history = data['location_history']
        assert len(history) >= 2
        for entry in history:
            assert 'date' in entry
            assert 'source' in entry
            assert 'source_label' in entry
            assert 'location' in entry
            assert 'confidence' in entry

    def test_demo_summary(self):
        data = _get_demo_geo_intelligence()
        summary = data['summary']
        assert summary['total_locations'] >= 3
        assert summary['sources_count'] >= 2
        assert summary['primary_city'] is not None


class TestCollectGeoIntelligence:
    """Test the main entry point."""

    def test_demo_mode(self):
        mock_check = MagicMock()
        result = collect_geo_intelligence(mock_check, is_demo=True)
        assert 'location_points' in result
        assert len(result['location_points']) >= 3

    def test_real_mode_empty_check(self):
        mock_check = MagicMock()
        mock_check.social_media_profiles = []
        mock_check.identity_confirmation = {}
        mock_check.business_records = []
        mock_check.registered_address = ''
        mock_check.region = ''
        mock_check.activity_patterns = {}
        mock_check.activity_timeline = []

        result = collect_geo_intelligence(mock_check, is_demo=False)
        assert result['summary']['total_locations'] == 0
        assert result['location_points'] == []
        assert len(result['activity_timeline']) == 7  # Always 7 days

    def test_real_mode_with_vk_data(self):
        mock_check = MagicMock()
        mock_check.social_media_profiles = [{
            'platform': 'vk',
            'vk_data': {
                'city': {'title': 'Москва'},
                'country': {'title': 'Россия'},
            },
        }]
        mock_check.identity_confirmation = {}
        mock_check.business_records = []
        mock_check.registered_address = 'г. Казань, ул. Баумана'
        mock_check.region = ''
        mock_check.activity_patterns = {}
        mock_check.activity_timeline = []

        result = collect_geo_intelligence(mock_check, is_demo=False)
        assert result['summary']['total_locations'] >= 2
        # Should have VK + form locations
        sources = {p['source'] for p in result['location_points']}
        assert 'vk_profile' in sources
        assert 'form' in sources
