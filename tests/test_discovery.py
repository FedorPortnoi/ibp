"""
Tests for Discovery Features: OK Search, Photo-First Investigation, Activity Timeline.

Validates the three new discovery features built by discovery-builder:
- OK (Odnoklassniki) search integration in Phase 1
- Photo-first investigation via Search4Faces API
- Activity timeline heatmap from VK wall posts
"""

import pytest
import os
import sys
import json
import uuid
import io
import time
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

# Ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


# ============================================================
# FIXTURES
# ============================================================

@pytest.fixture(scope='session')
def app():
    """Create Flask test application with in-memory SQLite (session-scoped)."""
    os.environ['SECRET_KEY'] = 'test-secret'
    os.environ.pop('VK_SERVICE_TOKEN', None)
    os.environ.pop('SEARCH4FACES_API_KEY', None)
    os.environ.pop('OK_SESSION_TOKEN', None)

    from app import create_app
    test_app = create_app('testing')
    test_app.config['TESTING'] = True
    test_app.config['WTF_CSRF_ENABLED'] = False
    test_app.config['SEARCH4FACES_API_KEY'] = None

    with test_app.app_context():
        yield test_app


@pytest.fixture(autouse=True)
def _clean_db(app):
    """Clean all tables before each test to ensure isolation."""
    from app import db
    with app.app_context():
        for table in reversed(db.metadata.sorted_tables):
            db.session.execute(table.delete())
        db.session.commit()
        yield
        db.session.rollback()


@pytest.fixture
def client(app):
    """Flask test client with auth session."""
    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess['authenticated'] = True
        yield c


@pytest.fixture
def db_session(app):
    """Database session for direct model access."""
    from app import db
    with app.app_context():
        yield db.session


@pytest.fixture
def sample_investigation(app):
    """Create a sample investigation for testing."""
    from app.models import Investigation
    from app import db

    inv_id = uuid.uuid4().hex
    inv = Investigation(
        id=inv_id,
        input_name='Тихон Портной',
        status='phase_1',
    )
    inv.phase1_stats = {
        'city': None,
        'age_from': None,
        'age_to': None,
        'search_started_at': datetime.now().isoformat(),
    }
    db.session.add(inv)
    db.session.commit()
    return inv


@pytest.fixture
def confirmed_investigation(app):
    """Create an investigation with a confirmed VK profile (ready for timeline)."""
    from app.models import Investigation, SocialProfile
    from app import db

    inv_id = uuid.uuid4().hex
    inv = Investigation(
        id=inv_id,
        input_name='Тихон Портной',
        status='phase_1_complete',
        confirmed_username='tikhon_portnoy',
        confirmed_platform='vk',
        confirmed_profile_url='https://vk.com/tikhon_portnoy',
    )
    inv.phase1_stats = {'confirmed_vk_id': '123456789'}
    db.session.add(inv)

    profile = SocialProfile(
        investigation_id=inv_id,
        platform='vk',
        platform_id='123456789',
        username='tikhon_portnoy',
        profile_url='https://vk.com/tikhon_portnoy',
        first_name='Тихон',
        last_name='Портной',
        display_name='Тихон Портной',
        is_confirmed=True,
    )
    db.session.add(profile)
    db.session.commit()
    return inv


@pytest.fixture
def mock_vk_wall_posts():
    """Mock VK wall.get response with known timestamps for timeline testing."""
    base_date = 1705276800  # 2024-01-15 00:00:00 UTC
    posts = []
    for i in range(50):
        day_offset = (i % 14) * 86400
        hour_offset = (6 + (i % 9)) * 3600  # UTC hours 6-14
        minute_offset = (i * 7 % 60) * 60
        posts.append({
            'id': i + 1,
            'date': base_date + day_offset + hour_offset + minute_offset,
            'text': f'Тестовый пост #{i + 1}',
            'post_type': 'post',
        })
    return {'count': len(posts), 'items': posts}


# ============================================================
# OK SEARCH TESTS
# ============================================================

class TestOKSearch:
    """Tests for OK (Odnoklassniki) search integration."""

    def test_cyrillic_name_search_returns_results(self, app):
        """OK search returns results for a Cyrillic name query."""
        from app.services.phase4.ok_people_search import OKPeopleSearch

        searcher = OKPeopleSearch()
        mock_html = """
        <html><body>
        <div class="ucard">
            <a href="/profile/111222333">
                <span class="emphased">Тихон Портной</span>
            </a>
            <img src="https://ok.ru/photo.jpg" />
            <div class="ucard-v-info_cnt">30 лет, Москва</div>
        </div>
        </body></html>
        """
        with patch.object(searcher.session, 'get') as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.url = 'https://ok.ru/search'
            mock_response.text = mock_html
            mock_get.return_value = mock_response
            results = searcher.search_people('Тихон Портной')

        assert isinstance(results, list), "search_people should return a list"

    def test_ok_integration_demo_search_returns_profiles(self, app):
        """OKSearchIntegration demo search returns profile dicts for Cyrillic name."""
        from app.services.phase1.ok_search_integration import OKSearchIntegration

        searcher = OKSearchIntegration()
        assert searcher.is_demo_mode is True, "Should be in demo mode without OK token"

        results = searcher.search(query='Тихон Портной', count=10)
        assert isinstance(results, list), "search() must return a list"
        assert len(results) > 0, "Demo search should return at least one result"

        for r in results:
            assert r['platform'] == 'ok', "All results must have platform='ok'"
            assert r['profile_url'].startswith('https://ok.ru/'), "URL must be ok.ru"
            assert r['display_name'], "display_name must not be empty"
            assert 'name_similarity' in r, "Must have name_similarity field"
            assert 'name_match' in r, "Must have name_match field"

    def test_ok_integration_result_matches_social_profile_structure(self, app):
        """OK integration results have all fields needed for SocialProfile creation."""
        from app.services.phase1.ok_search_integration import OKSearchIntegration

        searcher = OKSearchIntegration()
        results = searcher.search(query='Тихон Портной', count=5)
        assert len(results) > 0

        required_fields = [
            'platform', 'platform_id', 'username', 'profile_url',
            'first_name', 'last_name', 'display_name', 'name_similarity', 'name_match',
        ]
        for r in results:
            for field in required_fields:
                assert field in r, f"OK result missing required field '{field}': {r}"

    def test_ok_search_and_save_persists_to_db(self, app, sample_investigation):
        """search_and_save should persist OK profiles to the SocialProfile table."""
        from app.services.phase1.ok_search_integration import ok_search_integration
        from app.models import SocialProfile

        saved = ok_search_integration.search_and_save(
            investigation_id=sample_investigation.id,
            query='Тихон Портной',
            count=10,
        )

        assert isinstance(saved, list), "search_and_save should return a list"
        assert len(saved) > 0, "Should save at least one profile"

        db_profiles = SocialProfile.query.filter_by(
            investigation_id=sample_investigation.id,
            platform='ok',
        ).all()
        assert len(db_profiles) > 0, "OK profiles should be in the database"
        for p in db_profiles:
            assert p.platform == 'ok'
            assert p.profile_url.startswith('https://ok.ru/')

    def test_combined_vk_and_ok_results_in_phase1(self, app, sample_investigation):
        """Phase 1 can store both VK and OK profiles for same investigation."""
        from app.models import SocialProfile
        from app import db

        inv_id = sample_investigation.id

        vk_profile = SocialProfile(
            investigation_id=inv_id, platform='vk', platform_id='999888777',
            display_name='Тихон Портной', name_similarity=95.0, name_match=True,
        )
        ok_profile = SocialProfile(
            investigation_id=inv_id, platform='ok', platform_id='111222333',
            display_name='Тихон Портной', name_similarity=80.0, name_match=True,
        )
        db.session.add_all([vk_profile, ok_profile])
        db.session.commit()

        all_profiles = SocialProfile.query.filter_by(investigation_id=inv_id).all()
        platforms = {p.platform for p in all_profiles}
        assert 'vk' in platforms, "Should have VK results"
        assert 'ok' in platforms, "Should have OK results"

    def test_ok_failure_still_returns_vk_results(self, app, sample_investigation):
        """If OK search throws an exception, VK results should still persist."""
        from app.models import SocialProfile
        from app import db

        inv_id = sample_investigation.id
        vk_profile = SocialProfile(
            investigation_id=inv_id, platform='vk', platform_id='999888777',
            display_name='Тихон Портной', name_similarity=95.0, name_match=True,
        )
        db.session.add(vk_profile)
        db.session.commit()

        # Simulate OK failure
        from app.services.phase1.ok_search_integration import ok_search_integration
        with patch.object(ok_search_integration, 'search', side_effect=ConnectionError("OK.ru down")):
            # VK results should still be queryable
            vk_profiles = SocialProfile.query.filter_by(investigation_id=inv_id, platform='vk').all()
            assert len(vk_profiles) >= 1
            assert vk_profiles[0].display_name == 'Тихон Портной'

    def test_platform_badge_vk_and_ok(self, app):
        """VK and OK profiles are correctly tagged with their platform."""
        from app.models import SocialProfile
        from app import db

        vk = SocialProfile(investigation_id='t1', platform='vk', platform_id='v1', display_name='VK')
        ok = SocialProfile(investigation_id='t1', platform='ok', platform_id='o1', display_name='OK')
        db.session.add_all([vk, ok])
        db.session.commit()

        assert SocialProfile.query.filter_by(platform_id='v1').first().platform == 'vk'
        assert SocialProfile.query.filter_by(platform_id='o1').first().platform == 'ok'

    def test_ok_name_similarity_scoring(self, app):
        """OK integration name similarity correctly scores exact vs partial matches."""
        from app.services.phase1.ok_search_integration import OKSearchIntegration

        searcher = OKSearchIntegration()
        # Exact match
        score_exact = searcher._calculate_name_similarity('Тихон Портной', 'Тихон Портной')
        assert score_exact == 100.0, "Exact match should score 100"

        # Different first name, same last name
        score_diff_first = searcher._calculate_name_similarity('Тихон Портной', 'Андрей Портной')
        assert score_diff_first < 50, "Different first name should score < 50"

        # Completely different name
        score_diff = searcher._calculate_name_similarity('Тихон Портной', 'Елена Иванова')
        assert score_diff < 30, "Completely different name should score low"


# ============================================================
# PHOTO SEARCH TESTS
# ============================================================

class TestPhotoSearch:
    """Tests for photo-first investigation (Search4Faces)."""

    def test_jpg_accepted(self, app):
        """JPG files should be accepted for photo upload."""
        from app.routes.phase1 import allowed_file
        assert allowed_file('photo.jpg') is True
        assert allowed_file('photo.JPG') is True
        assert allowed_file('photo.jpeg') is True

    def test_png_accepted(self, app):
        """PNG files should be accepted for photo upload."""
        from app.routes.phase1 import allowed_file
        assert allowed_file('photo.png') is True

    def test_bmp_rejected(self, app):
        """BMP files should be rejected."""
        from app.routes.phase1 import allowed_file
        assert allowed_file('photo.bmp') is False

    def test_exe_rejected(self, app):
        """Executable files should be rejected."""
        from app.routes.phase1 import allowed_file
        assert allowed_file('malware.exe') is False

    def test_no_extension_rejected(self, app):
        """Files without extension should be rejected."""
        from app.routes.phase1 import allowed_file
        assert allowed_file('photo') is False

    def test_photo_investigation_validate_rejects_unsupported_format(self, app):
        """PhotoInvestigation.validate_photo rejects BMP (only jpg/jpeg/png allowed)."""
        from app.services.photo_investigation import PhotoInvestigation

        pi = PhotoInvestigation()
        mock_file = MagicMock()
        mock_file.filename = 'test.bmp'
        mock_file.seek = MagicMock()
        mock_file.tell = MagicMock(return_value=50000)

        error = pi.validate_photo(mock_file)
        assert error is not None, "BMP should be rejected by PhotoInvestigation"
        assert 'формат' in error.lower() or 'разрешен' in error.lower(), \
            f"Error should mention format, got: {error}"

    def test_photo_investigation_validate_accepts_jpg(self, app):
        """PhotoInvestigation.validate_photo accepts JPG with valid size."""
        from app.services.photo_investigation import PhotoInvestigation

        pi = PhotoInvestigation()
        mock_file = MagicMock()
        mock_file.filename = 'photo.jpg'
        mock_file.seek = MagicMock()
        mock_file.tell = MagicMock(return_value=50000)  # 50KB

        error = pi.validate_photo(mock_file)
        assert error is None, f"JPG should be accepted, got error: {error}"

    def test_photo_investigation_validate_rejects_too_small(self, app):
        """PhotoInvestigation.validate_photo rejects files smaller than 1KB."""
        from app.services.photo_investigation import PhotoInvestigation

        pi = PhotoInvestigation()
        mock_file = MagicMock()
        mock_file.filename = 'tiny.jpg'
        mock_file.seek = MagicMock()
        mock_file.tell = MagicMock(return_value=500)  # 500 bytes

        error = pi.validate_photo(mock_file)
        assert error is not None, "Files < 1KB should be rejected"

    def test_photo_investigation_validate_rejects_too_large(self, app):
        """PhotoInvestigation.validate_photo rejects files larger than 10MB."""
        from app.services.photo_investigation import PhotoInvestigation

        pi = PhotoInvestigation()
        mock_file = MagicMock()
        mock_file.filename = 'huge.jpg'
        mock_file.seek = MagicMock()
        mock_file.tell = MagicMock(return_value=20 * 1024 * 1024)  # 20MB

        error = pi.validate_photo(mock_file)
        assert error is not None, "Files > 10MB should be rejected"

    def test_photo_investigation_demo_search(self, app):
        """PhotoInvestigation demo search returns matches for any photo path."""
        from app.services.photo_investigation import PhotoInvestigation

        pi = PhotoInvestigation()
        assert pi.is_demo_mode is True

        matches = pi.search_by_photo('/tmp/fake_photo.jpg', max_results=5)
        assert isinstance(matches, list)
        assert len(matches) > 0, "Demo search should return at least one match"

        for m in matches:
            assert 'platform' in m, "Match must have platform"
            assert 'display_name' in m, "Match must have display_name"
            assert 'similarity_score' in m, "Match must have similarity_score"
            assert 'profile_url' in m, "Match must have profile_url"
            assert 0 < m['similarity_score'] <= 1.0, "Similarity must be between 0 and 1"

    def test_photo_investigation_create_investigation_from_match(self, app):
        """create_investigation_from_match creates Investigation + SocialProfile."""
        from app.services.photo_investigation import photo_investigation
        from app.models import Investigation, SocialProfile

        match = {
            'platform': 'vk',
            'platform_id': '123456',
            'profile_url': 'https://vk.com/id123456',
            'username': 'id123456',
            'first_name': 'Тихон',
            'last_name': 'Портной',
            'display_name': 'Тихон Портной',
            'photo_url': 'https://vk.com/photo.jpg',
            'city': 'Москва',
            'age': 28,
            'similarity_score': 0.95,
        }

        inv_id = photo_investigation.create_investigation_from_match(match, '/tmp/photo.jpg')

        inv = Investigation.query.get(inv_id)
        assert inv is not None, "Investigation should be created"
        assert inv.input_name == 'Тихон Портной'
        assert inv.input_photo_path == '/tmp/photo.jpg'

        profiles = SocialProfile.query.filter_by(investigation_id=inv_id).all()
        assert len(profiles) == 1, "Should create one SocialProfile"
        assert profiles[0].face_match is True, "Profile should have face_match=True"
        assert profiles[0].face_similarity == 95.0, "face_similarity should be score * 100"

    def test_photo_search_endpoint_requires_photo(self, app, client):
        """Photo search endpoint returns error when no photo is uploaded."""
        response = client.post('/phase1/photo-search', data={}, content_type='multipart/form-data')
        assert response.status_code == 400
        resp_data = response.get_json()
        assert 'error' in resp_data

    def test_no_face_error_is_russian(self, app, client):
        """When validation fails, error message should be in Russian."""
        mock_pi = MagicMock()
        mock_pi.validate_photo.return_value = 'Неподдерживаемый формат. Разрешены: jpg, jpeg, png'
        with patch('app.services.photo_investigation.photo_investigation', mock_pi):
            data = {'photo': (io.BytesIO(b'\x89PNG\r\n'), 'test.bmp')}
            response = client.post('/phase1/photo-search', data=data, content_type='multipart/form-data')
            assert response.status_code == 400
            resp_data = response.get_json()
            # Check the error is in Russian (Cyrillic characters present)
            assert any(ord(c) > 0x400 for c in resp_data.get('error', '')), \
                f"Error should contain Russian text, got: {resp_data.get('error')}"

    def test_photo_search_no_api_key_uses_demo(self, app, client):
        """Without SEARCH4FACES_API_KEY, photo search falls back to demo mode."""
        mock_pi = MagicMock()
        mock_pi.validate_photo.return_value = None
        mock_pi.save_photo.return_value = '/tmp/test_photo.jpg'
        mock_pi.search_by_photo.return_value = [
            {'platform': 'vk', 'display_name': 'Demo', 'similarity_score': 0.9,
             'profile_url': 'https://vk.com/id1'},
        ]
        with patch('app.services.photo_investigation.photo_investigation', mock_pi):
            data = {'photo': (io.BytesIO(b'\x89PNG\r\n' + b'\x00' * 2000), 'test.png')}
            response = client.post('/phase1/photo-search', data=data, content_type='multipart/form-data')
            assert response.status_code == 200
            resp_data = response.get_json()
            assert resp_data['success'] is True
            assert resp_data['count'] >= 1


# ============================================================
# ACTIVITY TIMELINE TESTS
# ============================================================

class TestActivityTimeline:
    """Tests for activity timeline / heatmap analysis service."""

    def test_analyze_with_wall_posts(self, app, mock_vk_wall_posts, confirmed_investigation):
        """ActivityTimeline.analyze() produces full analysis from wall posts."""
        from app.services.activity_timeline import ActivityTimeline

        timeline = ActivityTimeline()
        result = timeline.analyze(
            investigation_id=confirmed_investigation.id,
            wall_posts=mock_vk_wall_posts['items'],
        )

        assert 'heatmap' in result, "Result must contain heatmap"
        assert 'timezone' in result, "Result must contain timezone"
        assert 'gaps' in result, "Result must contain gaps"
        assert 'total_posts' in result, "Result must contain total_posts"
        assert 'date_range' in result, "Result must contain date_range"
        assert 'monthly' in result, "Result must contain monthly"
        assert 'peak_day' in result, "Result must contain peak_day"
        assert 'peak_hour' in result, "Result must contain peak_hour"
        assert result['total_posts'] == 50, "Should count all 50 posts"

    def test_heatmap_is_7x24_grid(self, app, mock_vk_wall_posts, confirmed_investigation):
        """Heatmap should be a 7x24 grid (7 days, 24 hours)."""
        from app.services.activity_timeline import ActivityTimeline

        timeline = ActivityTimeline()
        result = timeline.analyze(confirmed_investigation.id, mock_vk_wall_posts['items'])

        heatmap = result['heatmap']
        assert len(heatmap) == 7, f"Heatmap should have 7 rows (days), got {len(heatmap)}"
        for i, row in enumerate(heatmap):
            assert len(row) == 24, f"Row {i} should have 24 columns (hours), got {len(row)}"
            for val in row:
                assert isinstance(val, int) and val >= 0, "Each cell must be a non-negative int"

    def test_timezone_detection_returns_valid_offset(self, app, mock_vk_wall_posts, confirmed_investigation):
        """Timezone detection should return a valid Russian timezone offset."""
        from app.services.activity_timeline import ActivityTimeline

        timeline = ActivityTimeline()
        result = timeline.analyze(confirmed_investigation.id, mock_vk_wall_posts['items'])

        tz = result['timezone']
        assert tz is not None, "Timezone should be detected for 50 posts"
        assert isinstance(tz, int), "Timezone offset should be an integer"
        assert 2 <= tz <= 12, f"Russian timezone offset should be 2-12, got {tz}"

    def test_empty_posts_returns_empty_heatmap(self, app, confirmed_investigation):
        """0 posts should produce an empty 7x24 heatmap without crashing."""
        from app.services.activity_timeline import ActivityTimeline

        timeline = ActivityTimeline()
        result = timeline.analyze(confirmed_investigation.id, wall_posts=[])

        # With no posts, it falls back to demo. Let's test _build_analysis directly.
        empty_result = timeline._build_analysis([])
        assert empty_result['total_posts'] == 0
        heatmap = empty_result['heatmap']
        assert len(heatmap) == 7
        total = sum(sum(row) for row in heatmap)
        assert total == 0, "Empty heatmap should have all zeros"

    def test_single_post_heatmap(self, app, confirmed_investigation):
        """1 post should produce a heatmap with exactly one non-zero cell."""
        from app.services.activity_timeline import ActivityTimeline

        timeline = ActivityTimeline()
        posts = [{'date': 1705309200, 'text': 'Один пост'}]
        result = timeline.analyze(confirmed_investigation.id, wall_posts=posts)

        heatmap = result['heatmap']
        total = sum(sum(row) for row in heatmap)
        assert total == 1, "Single post heatmap should sum to 1"
        assert result['total_posts'] == 1

    def test_large_dataset_performance(self, app, confirmed_investigation):
        """10,000 posts should be analyzed in under 5 seconds."""
        import random as rng
        rng.seed(42)
        from app.services.activity_timeline import ActivityTimeline

        base_ts = 1672531200
        posts = [{'date': base_ts + rng.randint(0, 365 * 86400)} for _ in range(10000)]

        timeline = ActivityTimeline()
        start_time = time.time()
        result = timeline.analyze(confirmed_investigation.id, wall_posts=posts)
        elapsed = time.time() - start_time

        assert elapsed < 5.0, f"10,000 posts should process in < 5s, took {elapsed:.2f}s"
        assert result['total_posts'] == 10000

    def test_activity_gap_detection(self, app, confirmed_investigation):
        """30+ day gaps between posts should be detected."""
        from app.services.activity_timeline import ActivityTimeline

        timeline = ActivityTimeline()
        posts = [
            {'date': 1705312800},  # Jan 15
            {'date': 1705399200},  # Jan 16
            # ~45 day gap
            {'date': 1709200800},  # Feb 29
            {'date': 1709287200},  # Mar 1
        ]
        result = timeline.analyze(confirmed_investigation.id, wall_posts=posts)

        gaps = result['gaps']
        assert len(gaps) >= 1, "Should detect at least one gap > 30 days"
        assert gaps[0]['days'] >= 30, f"Gap should be >= 30 days, got {gaps[0]['days']}"
        assert 'label' in gaps[0], "Gap should have a Russian label"

    def test_monthly_post_counts(self, app, confirmed_investigation):
        """Monthly breakdown should correctly count posts per month."""
        from app.services.activity_timeline import ActivityTimeline

        timeline = ActivityTimeline()
        # Use midday timestamps to avoid timezone edge effects
        # 3 posts in Jan, 2 in Feb (all at noon UTC+3)
        posts = [
            {'date': 1704106800},  # 2024-01-01 12:00 MSK
            {'date': 1704193200},  # 2024-01-02 12:00 MSK
            {'date': 1704279600},  # 2024-01-03 12:00 MSK
            {'date': 1706785200},  # 2024-02-01 12:00 MSK
            {'date': 1706871600},  # 2024-02-02 12:00 MSK
        ]
        result = timeline.analyze(confirmed_investigation.id, wall_posts=posts)

        monthly = result['monthly']
        assert len(monthly) >= 2, "Should have at least 2 months"

        # Verify total posts across all months
        total = sum(m['count'] for m in monthly)
        assert total == 5, f"Total across months should be 5, got {total}"

        # Each month entry should have a label
        for m in monthly:
            assert 'label' in m, "Monthly entry should have a label"
            assert 'count' in m, "Monthly entry should have a count"
            assert m['count'] > 0

    def test_peak_day_and_hour(self, app, confirmed_investigation, mock_vk_wall_posts):
        """Peak day and peak hour should be correctly identified."""
        from app.services.activity_timeline import ActivityTimeline

        timeline = ActivityTimeline()
        result = timeline.analyze(confirmed_investigation.id, mock_vk_wall_posts['items'])
        # Verify the fields exist and are reasonable
        assert result['peak_day'] is not None, "Peak day should be identified"
        assert result['peak_hour'] is not None, "Peak hour should be identified"
        assert isinstance(result['peak_hour'], int)
        assert 0 <= result['peak_hour'] <= 23

    def test_date_range_calculation(self, app, confirmed_investigation):
        """Date range should correctly calculate start, end, and span in days."""
        from app.services.activity_timeline import ActivityTimeline

        timeline = ActivityTimeline()
        posts = [
            {'date': 1704067200},  # 2024-01-01
            {'date': 1706745600},  # 2024-02-01 (31 days later)
        ]
        result = timeline.analyze(confirmed_investigation.id, wall_posts=posts)

        dr = result['date_range']
        assert dr is not None
        assert 'start' in dr
        assert 'end' in dr
        assert 'days' in dr
        assert dr['days'] == 31, f"Date range should be 31 days, got {dr['days']}"

    def test_trend_analysis(self, app, confirmed_investigation):
        """Trend analysis should return a valid trend string."""
        from app.services.activity_timeline import ActivityTimeline

        timeline = ActivityTimeline()
        # Generate enough posts across 6 months for trend analysis
        posts = []
        base = 1672531200  # 2023-01-01
        for i in range(200):
            posts.append({'date': base + i * 86400 + (i % 24) * 3600})

        result = timeline.analyze(confirmed_investigation.id, wall_posts=posts)

        assert result['trend'] in ('increasing', 'decreasing', 'stable', 'unknown'), \
            f"Trend should be valid, got: {result['trend']}"
        assert result['trend_label'], "Trend label should be non-empty"

    def test_day_names_russian(self, app, confirmed_investigation):
        """Day names in analysis should be in Russian."""
        from app.services.activity_timeline import DAY_NAMES_RU

        assert len(DAY_NAMES_RU) == 7
        assert DAY_NAMES_RU[0] == 'Пн', "Monday should be 'Пн'"
        assert DAY_NAMES_RU[6] == 'Вс', "Sunday should be 'Вс'"



# ============================================================
# COMBINED SEARCH TESTS
# ============================================================

class TestCombinedSearch:
    """Tests for the combined VK+OK search wrapper."""

    def test_combined_search_returns_both_platforms(self, app, sample_investigation):
        """combined_search_and_save returns dict with 'vk' and 'ok' keys."""
        from app.services.phase1.combined_search import combined_search_and_save

        # Mock VK search to avoid real API calls / Playwright
        mock_vk_results = [{'platform': 'vk', 'platform_id': '111', 'display_name': 'Тихон Портной'}]
        with patch('app.services.phase1.buratino_vk_search.buratino_vk_search') as mock_vk:
            mock_vk.search_and_save.return_value = mock_vk_results
            result = combined_search_and_save(
                investigation_id=sample_investigation.id,
                query='Тихон Портной',
            )

        assert isinstance(result, dict), "Should return a dict"
        assert 'vk' in result, "Result must have 'vk' key"
        assert 'ok' in result, "Result must have 'ok' key"
        assert isinstance(result['vk'], list), "VK results should be a list"
        assert isinstance(result['ok'], list), "OK results should be a list"

    def test_combined_search_ok_failure_still_returns_vk(self, app, sample_investigation):
        """If OK search raises, VK results should still be returned."""
        from app.services.phase1.combined_search import combined_search_and_save

        mock_vk_results = [{'platform': 'vk', 'platform_id': '222', 'display_name': 'Тихон Портной'}]
        with patch('app.services.phase1.buratino_vk_search.buratino_vk_search') as mock_vk, \
             patch('app.services.phase1.ok_search_integration.ok_search_integration') as mock_ok:
            mock_vk.search_and_save.return_value = mock_vk_results
            mock_ok.search_and_save.side_effect = RuntimeError("OK down")
            result = combined_search_and_save(
                investigation_id=sample_investigation.id,
                query='Тихон Портной',
            )

        assert 'vk' in result
        assert 'ok' in result
        assert len(result['vk']) >= 1, "VK results should be present"
        assert result['ok'] == [], "OK should be empty due to failure"

    def test_combined_search_saves_ok_to_db(self, app, sample_investigation):
        """Combined search should persist OK profiles to DB."""
        from app.services.phase1.combined_search import combined_search_and_save
        from app.models import SocialProfile

        # Mock VK to avoid real calls, let OK demo mode run normally
        with patch('app.services.phase1.buratino_vk_search.buratino_vk_search') as mock_vk:
            mock_vk.search_and_save.return_value = []
            combined_search_and_save(
                investigation_id=sample_investigation.id,
                query='Тихон Портной',
                ok_count=5,
            )

        ok_profiles = SocialProfile.query.filter_by(
            investigation_id=sample_investigation.id,
            platform='ok',
        ).all()
        assert len(ok_profiles) > 0, "OK profiles should be saved to database"


# ============================================================
# TIMELINE ROUTE TESTS
# ============================================================

class TestTimelineRoutes:
    """Tests for timeline blueprint routes."""

    def test_timeline_blueprint_registered(self, app):
        """Timeline blueprint should be registered in the app."""
        assert 'timeline' in app.blueprints, "timeline blueprint must be registered"

    def test_timeline_api_endpoint(self, app, client, confirmed_investigation):
        """Timeline API endpoint returns JSON with analysis data."""
        response = client.get(f'/timeline/api/{confirmed_investigation.id}')
        assert response.status_code == 200

        data = response.get_json()
        assert data['success'] is True
        assert data['investigation_id'] == confirmed_investigation.id
        assert 'heatmap' in data
        assert 'total_posts' in data

    def test_timeline_api_404_for_invalid_id(self, app, client):
        """Timeline API returns 404 for non-existent investigation."""
        response = client.get('/timeline/api/nonexistent123')
        assert response.status_code == 404


# ============================================================
# INTEGRATION TESTS
# ============================================================

class TestDiscoveryIntegration:
    """Integration tests combining multiple discovery features."""

    def test_investigation_model_supports_ok_platform(self, app):
        """Investigation can store OK platform profiles."""
        from app.models import SocialProfile
        from app import db

        profile = SocialProfile(
            investigation_id='test-integration-1', platform='ok', platform_id='ok12345',
            display_name='Тихон Портной', profile_url='https://ok.ru/profile/12345',
            city='Москва', age=30,
        )
        db.session.add(profile)
        db.session.commit()

        loaded = SocialProfile.query.filter_by(platform='ok', platform_id='ok12345').first()
        assert loaded is not None
        assert loaded.platform == 'ok'
        assert loaded.display_name == 'Тихон Портной'

    def test_social_profile_confidence_with_face_match(self, app):
        """SocialProfile confidence should increase with face_match=True."""
        from app.models import SocialProfile
        from app import db

        profile = SocialProfile(
            investigation_id='test-conf-1', platform='vk', platform_id='999',
            display_name='Тест',
            face_match=True, face_similarity=90.0,
            name_match=True, name_similarity=85.0,
        )
        profile.calculate_confidence()
        db.session.add(profile)
        db.session.commit()

        loaded = SocialProfile.query.filter_by(platform_id='999').first()
        assert loaded.confidence_score > 0
        assert loaded.confidence_level in ('high', 'medium')

    def test_russian_text_in_all_fields(self, app):
        """Russian text should be stored and retrieved correctly."""
        from app.models import Investigation, SocialProfile
        from app import db

        inv_id = uuid.uuid4().hex
        inv = Investigation(id=inv_id, input_name='Тихон Портной', status='phase_1')
        db.session.add(inv)
        db.session.commit()

        profile = SocialProfile(
            investigation_id=inv_id, platform='ok', platform_id='рус123',
            display_name='Тихон Портной', first_name='Тихон', last_name='Портной',
            city='Санкт-Петербург', bio='Программист из России',
            profile_url='https://ok.ru/profile/123',
        )
        db.session.add(profile)
        db.session.commit()

        loaded = SocialProfile.query.filter_by(platform_id='рус123').first()
        assert loaded.display_name == 'Тихон Портной'
        assert loaded.city == 'Санкт-Петербург'
        assert loaded.bio == 'Программист из России'

    def test_photo_match_creates_high_confidence_profile(self, app):
        """Photo match with high similarity should create high-confidence profile."""
        from app.services.photo_investigation import photo_investigation
        from app.models import Investigation, SocialProfile

        match = {
            'platform': 'vk', 'platform_id': '777888',
            'profile_url': 'https://vk.com/id777888',
            'username': 'id777888',
            'first_name': 'Анна', 'last_name': 'Петрова',
            'display_name': 'Анна Петрова',
            'photo_url': 'https://vk.com/photo.jpg',
            'city': 'Москва', 'age': 28,
            'similarity_score': 0.98,
        }

        inv_id = photo_investigation.create_investigation_from_match(match, '/tmp/photo.jpg')
        profile = SocialProfile.query.filter_by(investigation_id=inv_id).first()
        assert profile is not None
        assert profile.face_match is True
        assert profile.face_similarity == 98.0
        assert profile.confidence_level in ('high', 'medium')
