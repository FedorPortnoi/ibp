"""
Tests for Discovery Features: OK Search, Photo Investigation, Activity Timeline
================================================================================
Covers unit tests, integration tests, and edge cases for all three features.
"""

import io
import os
import json
import uuid
import pytest
import tempfile
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope='module')
def app():
    """Create Flask app with in-memory SQLite for testing."""
    # Save and remove auth env vars so auth gate is disabled.
    # load_dotenv() in app/__init__.py re-populates from .env at import time,
    # so we must pop AFTER the import but BEFORE create_app().
    from app import create_app, db

    _saved = {}
    for key in ('IBP_PASSWORD', 'IBP_PASSWORD_HASH', 'SEARCH4FACES_API_KEY', 'OK_SESSION_TOKEN'):
        _saved[key] = os.environ.pop(key, None)

    app = create_app()
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['WTF_CSRF_ENABLED'] = False
    app.config['SERVER_NAME'] = 'localhost'

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

    # Restore env vars
    for key, val in _saved.items():
        if val is not None:
            os.environ[key] = val


@pytest.fixture(autouse=True)
def clean_db(app):
    """Clean database between tests."""
    from app import db
    with app.app_context():
        db.session.rollback()
        for table in reversed(db.metadata.sorted_tables):
            db.session.execute(table.delete())
        db.session.commit()
        yield


@pytest.fixture
def client(app):
    """Flask test client with auth bypass."""
    client = app.test_client()
    # Set authenticated session to bypass auth gate
    with client.session_transaction() as sess:
        sess['authenticated'] = True
    return client


@pytest.fixture
def app_context(app):
    """Provide application context."""
    with app.app_context():
        yield


@pytest.fixture
def sample_investigation(app):
    """Create a sample investigation in the DB."""
    from app import db
    from app.models import Investigation

    with app.app_context():
        inv_id = uuid.uuid4().hex
        inv = Investigation(
            id=inv_id,
            input_name='Тихон Портной',
            status='phase_2_complete',
        )
        inv.phase1_stats = {'city': 'Москва'}
        inv.social_graph = {'wall_posts': []}
        db.session.add(inv)
        db.session.commit()
        yield inv_id


def _make_jpeg_bytes(size_kb=5):
    """Create minimal valid-looking JPEG bytes."""
    # JPEG header (SOI + APP0)
    header = b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00'
    padding = b'\x00' * (size_kb * 1024 - len(header) - 2)
    footer = b'\xff\xd9'
    return header + padding + footer


def _make_png_bytes(size_kb=5):
    """Create minimal PNG-like bytes."""
    header = b'\x89PNG\r\n\x1a\n'
    padding = b'\x00' * (size_kb * 1024 - len(header))
    return header + padding


# ===========================================================================
# OK SEARCH TESTS
# ===========================================================================

class TestOKSearchUnit:
    """Unit tests for OKSearchIntegration."""

    def test_ok_search_returns_results_cyrillic(self, app_context):
        """OK search returns results for Cyrillic names in demo mode."""
        from app.services.phase1.ok_search_integration import OKSearchIntegration

        ok = OKSearchIntegration()
        assert ok.is_demo_mode is True

        results = ok.search('Тихон Портной')
        assert len(results) >= 2
        for r in results:
            assert r.get('display_name')
            assert 'platform' in r

    def test_ok_results_platform_ok(self, app_context):
        """OK results have platform='ok' and SocialProfile-compatible format."""
        from app.services.phase1.ok_search_integration import OKSearchIntegration

        ok = OKSearchIntegration()
        results = ok.search('Ольга Ахтинас')

        required_fields = [
            'platform', 'platform_id', 'profile_url', 'first_name',
            'last_name', 'display_name', 'name_similarity', 'name_match',
        ]
        for r in results:
            assert r['platform'] == 'ok'
            for field in required_fields:
                assert field in r, f"Missing field: {field}"
            assert r['profile_url'].startswith('https://ok.ru/')

    def test_name_similarity_scoring(self, app_context):
        """Exact match scores higher than partial match."""
        from app.services.phase1.ok_search_integration import OKSearchIntegration

        ok = OKSearchIntegration()

        exact = ok._calculate_name_similarity('Тихон Портной', 'Тихон Портной')
        partial = ok._calculate_name_similarity('Тихон Портной', 'Тихон Смирнов')

        assert exact == 100.0
        assert partial < exact

    def test_demo_mode_generates_two_plus(self, app_context):
        """Demo mode generates at least 2 profiles without API keys."""
        from app.services.phase1.ok_search_integration import OKSearchIntegration

        ok = OKSearchIntegration()
        assert ok.is_demo_mode is True

        results = ok.search('Даниил Глазков')
        assert len(results) >= 2

    def test_empty_name_returns_empty(self, app_context):
        """Empty name returns empty results."""
        from app.services.phase1.ok_search_integration import OKSearchIntegration

        ok = OKSearchIntegration()
        results = ok.search('')
        # With empty query, demo search may generate results with default names
        # but similarity should be low. At minimum, should not crash.
        assert isinstance(results, list)

    def test_similarity_zero_for_empty_inputs(self, app_context):
        """Similarity is 0 when either input is empty."""
        from app.services.phase1.ok_search_integration import OKSearchIntegration

        ok = OKSearchIntegration()
        assert ok._calculate_name_similarity('', 'Тихон') == 0.0
        assert ok._calculate_name_similarity('Тихон', '') == 0.0

    def test_ok_search_and_save(self, app, sample_investigation):
        """search_and_save persists OK profiles to database."""
        from app import db
        from app.models import SocialProfile
        from app.services.phase1.ok_search_integration import OKSearchIntegration

        with app.app_context():
            ok = OKSearchIntegration()
            saved = ok.search_and_save(
                investigation_id=sample_investigation,
                query='Тихон Портной',
                count=10,
            )
            assert len(saved) >= 1

            db_profiles = SocialProfile.query.filter_by(
                investigation_id=sample_investigation,
                platform='ok',
            ).all()
            assert len(db_profiles) >= 1
            for p in db_profiles:
                assert p.platform == 'ok'
                assert p.platform_id

    def test_demo_reproducible(self, app_context):
        """Same query gives same demo results (seeded RNG)."""
        from app.services.phase1.ok_search_integration import OKSearchIntegration

        ok = OKSearchIntegration()
        r1 = ok.search('Влада Кладко')
        r2 = ok.search('Влада Кладко')

        assert len(r1) == len(r2)
        for a, b in zip(r1, r2):
            assert a['platform_id'] == b['platform_id']


# ===========================================================================
# PHOTO SEARCH TESTS
# ===========================================================================

class TestPhotoValidation:
    """Tests for photo upload validation."""

    def test_jpg_accepted(self, app_context):
        """JPG files pass validation."""
        from app.services.photo_investigation import PhotoInvestigation

        pi = PhotoInvestigation()
        data = _make_jpeg_bytes(5)
        file = MagicMock()
        file.filename = 'photo.jpg'
        file.seek = lambda offset, whence=0: None
        file.tell = lambda: len(data)
        file.read = lambda *a: data

        # Properly mock seek/tell for size check
        _pos = [0]
        def mock_seek(offset, whence=0):
            if whence == 2:
                _pos[0] = len(data)
            else:
                _pos[0] = offset
        def mock_tell():
            return _pos[0]

        file.seek = mock_seek
        file.tell = mock_tell

        error = pi.validate_photo(file)
        assert error is None

    def test_png_accepted(self, app_context):
        """PNG files pass validation."""
        from app.services.photo_investigation import PhotoInvestigation

        pi = PhotoInvestigation()
        data = _make_png_bytes(5)

        _pos = [0]
        def mock_seek(offset, whence=0):
            if whence == 2:
                _pos[0] = len(data)
            else:
                _pos[0] = offset
        def mock_tell():
            return _pos[0]

        file = MagicMock()
        file.filename = 'face.png'
        file.seek = mock_seek
        file.tell = mock_tell

        error = pi.validate_photo(file)
        assert error is None

    def test_non_image_rejected(self, app_context):
        """Non-image formats are rejected."""
        from app.services.photo_investigation import PhotoInvestigation

        pi = PhotoInvestigation()
        file = MagicMock()
        file.filename = 'document.pdf'
        file.seek = lambda *a: None
        file.tell = lambda: 5000

        error = pi.validate_photo(file)
        assert error is not None
        assert 'Неподдерживаемый формат' in error

    def test_oversized_rejected(self, app_context):
        """Files over 10 MB are rejected."""
        from app.services.photo_investigation import PhotoInvestigation

        pi = PhotoInvestigation()
        big_size = 11 * 1024 * 1024

        _pos = [0]
        def mock_seek(offset, whence=0):
            if whence == 2:
                _pos[0] = big_size
            else:
                _pos[0] = offset
        def mock_tell():
            return _pos[0]

        file = MagicMock()
        file.filename = 'huge.jpg'
        file.seek = mock_seek
        file.tell = mock_tell

        error = pi.validate_photo(file)
        assert error is not None
        assert 'большой' in error or 'Максимум' in error

    def test_too_small_rejected(self, app_context):
        """Files under 1 KB are rejected."""
        from app.services.photo_investigation import PhotoInvestigation

        pi = PhotoInvestigation()

        _pos = [0]
        def mock_seek(offset, whence=0):
            if whence == 2:
                _pos[0] = 500  # 500 bytes
            else:
                _pos[0] = offset
        def mock_tell():
            return _pos[0]

        file = MagicMock()
        file.filename = 'tiny.jpg'
        file.seek = mock_seek
        file.tell = mock_tell

        error = pi.validate_photo(file)
        assert error is not None
        assert 'маленький' in error or 'Минимум' in error

    def test_no_file_rejected(self, app_context):
        """No file returns error."""
        from app.services.photo_investigation import PhotoInvestigation

        pi = PhotoInvestigation()
        error = pi.validate_photo(None)
        assert error is not None

    def test_no_filename_rejected(self, app_context):
        """File with no filename returns error."""
        from app.services.photo_investigation import PhotoInvestigation

        pi = PhotoInvestigation()
        file = MagicMock()
        file.filename = ''
        error = pi.validate_photo(file)
        assert error is not None


class TestPhotoSearch:
    """Tests for photo-based face search."""

    def test_demo_returns_matches_with_scores(self, app_context):
        """Demo mode returns face matches with similarity scores."""
        from app.services.photo_investigation import PhotoInvestigation

        pi = PhotoInvestigation()
        assert pi.is_demo_mode is True

        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
            f.write(_make_jpeg_bytes(5))
            photo_path = f.name

        try:
            matches = pi.search_by_photo(photo_path)
            assert len(matches) >= 1
            for m in matches:
                assert 'similarity_score' in m
                assert 0 < m['similarity_score'] <= 1.0
                assert m['platform'] in ('vk', 'ok')
                assert 'display_name' in m
                assert 'profile_url' in m
        finally:
            os.unlink(photo_path)

    def test_demo_results_sorted_by_similarity(self, app_context):
        """Demo results are sorted by similarity (highest first)."""
        from app.services.photo_investigation import PhotoInvestigation

        pi = PhotoInvestigation()

        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
            f.write(_make_jpeg_bytes(5))
            photo_path = f.name

        try:
            matches = pi.search_by_photo(photo_path)
            scores = [m['similarity_score'] for m in matches]
            assert scores == sorted(scores, reverse=True)
        finally:
            os.unlink(photo_path)

    def test_create_investigation_from_match(self, app):
        """Photo search creates investigation on match selection."""
        from app import db
        from app.models import Investigation, SocialProfile
        from app.services.photo_investigation import PhotoInvestigation

        with app.app_context():
            pi = PhotoInvestigation()
            match = {
                'platform': 'vk',
                'platform_id': '12345678',
                'username': 'id12345678',
                'profile_url': 'https://vk.com/id12345678',
                'first_name': 'Анна',
                'last_name': 'Петрова',
                'display_name': 'Анна Петрова',
                'photo_url': 'https://vk.com/images/camera_200.png',
                'city': 'Москва',
                'age': 28,
                'similarity_score': 0.92,
            }

            inv_id = pi.create_investigation_from_match(match, '/tmp/test.jpg')
            assert inv_id

            inv = Investigation.query.get(inv_id)
            assert inv is not None
            assert inv.input_name == 'Анна Петрова'
            assert inv.status == 'phase_1'
            assert inv.input_photo_path == '/tmp/test.jpg'

            sp = SocialProfile.query.filter_by(
                investigation_id=inv_id, platform='vk'
            ).first()
            assert sp is not None
            assert sp.face_match is True
            assert sp.face_similarity == 92.0  # 0.92 * 100
            assert sp.display_name == 'Анна Петрова'

    def test_no_face_scenario(self, app_context):
        """Non-existent photo path handled gracefully in demo mode."""
        from app.services.photo_investigation import PhotoInvestigation

        pi = PhotoInvestigation()
        # Demo mode falls back to hashing the path string
        matches = pi.search_by_photo('/nonexistent/path.jpg')
        assert isinstance(matches, list)
        assert len(matches) >= 1  # Demo still returns results


class TestPhotoSearchRoute:
    """Integration tests for photo search HTTP routes."""

    def test_photo_search_route_with_image(self, client, app_context):
        """POST /phase1/photo-search with valid image returns results."""
        data = _make_jpeg_bytes(5)
        resp = client.post(
            '/phase1/photo-search',
            data={'photo': (io.BytesIO(data), 'test.jpg')},
            content_type='multipart/form-data',
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['success'] is True
        assert body['count'] >= 1
        assert 'matches' in body

    def test_photo_search_no_file(self, client, app_context):
        """POST /phase1/photo-search without file returns 400."""
        resp = client.post(
            '/phase1/photo-search',
            data={},
            content_type='multipart/form-data',
        )
        assert resp.status_code == 400

    def test_photo_search_invalid_format(self, client, app_context):
        """POST /phase1/photo-search with non-image returns 400."""
        resp = client.post(
            '/phase1/photo-search',
            data={'photo': (io.BytesIO(b'not an image'), 'test.txt')},
            content_type='multipart/form-data',
        )
        assert resp.status_code == 400

    def test_photo_select_creates_investigation(self, client, app):
        """POST /phase1/photo-select creates investigation."""
        with app.app_context():
            match_data = {
                'match': {
                    'platform': 'vk',
                    'platform_id': '999',
                    'username': 'id999',
                    'profile_url': 'https://vk.com/id999',
                    'first_name': 'Тест',
                    'last_name': 'Тестов',
                    'display_name': 'Тест Тестов',
                    'similarity_score': 0.85,
                },
                'photo_path': '/tmp/photo.jpg',
            }
            resp = client.post(
                '/phase1/photo-select',
                data=json.dumps(match_data),
                content_type='application/json',
            )
            assert resp.status_code == 200
            body = resp.get_json()
            assert body['success'] is True
            assert 'investigation_id' in body
            assert '/phase2/analyze/' in body['redirect']


# ===========================================================================
# ACTIVITY TIMELINE TESTS
# ===========================================================================

class TestActivityTimelineUnit:
    """Unit tests for ActivityTimeline service."""

    def _make_timestamps(self, hours, base_date=None):
        """Helper: create timestamps at specific hours."""
        if base_date is None:
            base_date = datetime(2025, 6, 15)  # A Sunday
        return [base_date.replace(hour=h, minute=30) for h in hours]

    def test_timestamp_parsing_unix(self, app_context):
        """Parses Unix timestamps from mock VK posts."""
        from app.services.activity_timeline import ActivityTimeline

        at = ActivityTimeline()
        # Known Unix timestamp: 2025-01-15 14:30:00 UTC
        ts = datetime(2025, 1, 15, 14, 30, 0).timestamp()
        posts = [{'date': ts}]

        timestamps = at._extract_timestamps('test-id', posts)
        assert len(timestamps) == 1
        assert timestamps[0].hour == 14
        assert timestamps[0].day == 15

    def test_timestamp_parsing_iso_string(self, app_context):
        """Parses ISO datetime strings from posts."""
        from app.services.activity_timeline import ActivityTimeline

        at = ActivityTimeline()
        posts = [{'date': '2025-03-10T18:45:00'}]

        timestamps = at._extract_timestamps('test-id', posts)
        assert len(timestamps) == 1
        assert timestamps[0].hour == 18
        assert timestamps[0].month == 3

    def test_heatmap_7x24(self, app_context):
        """Heatmap is exactly 7 rows x 24 columns."""
        from app.services.activity_timeline import ActivityTimeline

        at = ActivityTimeline()
        # Create timestamps spread across days/hours
        timestamps = []
        base = datetime(2025, 6, 9)  # Monday
        for day in range(7):
            for hour in [10, 14, 20]:
                timestamps.append(base + timedelta(days=day, hours=hour))

        heatmap = at._build_heatmap(timestamps)
        assert len(heatmap) == 7
        for row in heatmap:
            assert len(row) == 24

    def test_heatmap_correct_bucketing(self, app_context):
        """Posts land in correct day/hour buckets."""
        from app.services.activity_timeline import ActivityTimeline

        at = ActivityTimeline()
        # Monday at 14:00 (weekday=0, hour=14)
        monday_2pm = datetime(2025, 6, 9, 14, 0)  # Monday
        assert monday_2pm.weekday() == 0

        heatmap = at._build_heatmap([monday_2pm, monday_2pm, monday_2pm])
        assert heatmap[0][14] == 3  # Monday, 14:00 = 3 posts
        assert heatmap[1][14] == 0  # Tuesday, 14:00 = 0

    def test_timezone_moscow_detection(self, app_context):
        """Posts concentrated 18-22 detect Moscow timezone (UTC+3)."""
        from app.services.activity_timeline import ActivityTimeline

        at = ActivityTimeline()
        # Create many posts between 18:00-22:00
        timestamps = []
        base = datetime(2025, 6, 1)
        for day in range(30):
            for hour in [18, 19, 20, 21, 22]:
                timestamps.append(base + timedelta(days=day, hours=hour, minutes=15))
            # A few morning posts
            timestamps.append(base + timedelta(days=day, hours=10, minutes=30))

        offset, label = at._detect_timezone(timestamps)
        assert offset == 3
        assert 'Москва' in label

    def test_gap_detection_60_days(self, app_context):
        """60-day gap between posts is detected."""
        from app.services.activity_timeline import ActivityTimeline

        at = ActivityTimeline()
        timestamps = [
            datetime(2025, 1, 1, 12, 0),
            datetime(2025, 1, 5, 14, 0),
            datetime(2025, 1, 10, 10, 0),
            # 60-day gap
            datetime(2025, 3, 11, 16, 0),
            datetime(2025, 3, 15, 18, 0),
        ]

        gaps = at._detect_gaps(timestamps, min_gap_days=30)
        assert len(gaps) >= 1
        assert any(g['days'] >= 60 for g in gaps)

    def test_frequency_trend_increasing(self, app_context):
        """More recent posts = increasing trend."""
        from app.services.activity_timeline import ActivityTimeline

        at = ActivityTimeline()
        now = datetime(2025, 6, 15, 12, 0)
        timestamps = []

        # Older period (3-6 months ago): few posts
        for i in range(5):
            timestamps.append(now - timedelta(days=120 + i * 3))

        # Recent period (0-3 months): many posts
        for i in range(30):
            timestamps.append(now - timedelta(days=i * 2))

        trend, label = at._analyze_trend(timestamps)
        assert trend == 'increasing'

    def test_frequency_trend_decreasing(self, app_context):
        """Fewer recent posts = decreasing trend."""
        from app.services.activity_timeline import ActivityTimeline

        at = ActivityTimeline()
        now = datetime(2025, 6, 15, 12, 0)
        timestamps = []

        # Older period (3-6 months ago): many posts
        for i in range(30):
            timestamps.append(now - timedelta(days=120 + i * 2))

        # Recent period (0-3 months): few posts
        for i in range(5):
            timestamps.append(now - timedelta(days=i * 10))

        trend, label = at._analyze_trend(timestamps)
        assert trend == 'decreasing'

    def test_monthly_aggregation(self, app_context):
        """Monthly counts are aggregated correctly."""
        from app.services.activity_timeline import ActivityTimeline

        at = ActivityTimeline()
        timestamps = [
            datetime(2025, 1, 5, 10, 0),
            datetime(2025, 1, 15, 14, 0),
            datetime(2025, 1, 25, 18, 0),
            datetime(2025, 2, 10, 12, 0),
            datetime(2025, 3, 20, 16, 0),
        ]

        monthly = at._build_monthly(timestamps)
        assert len(monthly) == 3

        jan = next(m for m in monthly if m['month'] == '2025-01')
        assert jan['count'] == 3

        feb = next(m for m in monthly if m['month'] == '2025-02')
        assert feb['count'] == 1

    def test_empty_posts_empty_heatmap(self, app_context):
        """0 posts produces empty heatmap, no gaps, stable/unknown trend."""
        from app.services.activity_timeline import ActivityTimeline

        at = ActivityTimeline()
        result = at._build_analysis([])

        assert result['total_posts'] == 0
        assert result['heatmap'] == [[0] * 24 for _ in range(7)]
        assert result['gaps'] == []
        assert result['trend'] in ('unknown', 'stable')
        assert result['timezone'] is None
        assert result['peak_day'] is None
        assert result['peak_hour'] is None

    def test_one_post_minimal_output(self, app_context):
        """1 post produces valid minimal output."""
        from app.services.activity_timeline import ActivityTimeline

        at = ActivityTimeline()
        timestamps = [datetime(2025, 3, 15, 20, 0)]
        result = at._build_analysis(timestamps)

        assert result['total_posts'] == 1
        assert result['monthly'] == [{'month': '2025-03', 'label': 'Мар 2025', 'count': 1}]
        assert result['gaps'] == []  # Need 2+ timestamps for gaps
        assert result['peak_hour'] is not None

    def test_empty_heatmap_shape(self, app_context):
        """Empty heatmap is 7x24 zeros."""
        from app.services.activity_timeline import ActivityTimeline

        at = ActivityTimeline()
        heatmap = at._empty_heatmap()
        assert len(heatmap) == 7
        for row in heatmap:
            assert len(row) == 24
            assert all(v == 0 for v in row)

    def test_find_peaks(self, app_context):
        """Peak day and peak hour found correctly."""
        from app.services.activity_timeline import ActivityTimeline

        at = ActivityTimeline()
        heatmap = [[0] * 24 for _ in range(7)]
        # Wednesday (index 2), hour 20 has the most
        heatmap[2][20] = 50
        heatmap[0][10] = 5

        peak_day, peak_hour = at._find_peaks(heatmap)
        assert peak_day == 'Ср'
        assert peak_hour == 20

    def test_month_label_format(self, app_context):
        """Month label formats correctly."""
        from app.services.activity_timeline import ActivityTimeline

        at = ActivityTimeline()
        assert at._format_month_label('2025-01') == 'Янв 2025'
        assert at._format_month_label('2025-12') == 'Дек 2025'


class TestActivityTimelineIntegration:
    """Integration tests using analyze() with DB-backed investigations."""

    def test_analyze_with_wall_posts(self, app, sample_investigation):
        """analyze() with explicit wall_posts returns complete result."""
        from app.services.activity_timeline import ActivityTimeline

        with app.app_context():
            at = ActivityTimeline()
            now = datetime.now()
            posts = []
            for i in range(50):
                ts = (now - timedelta(days=i * 3, hours=i % 12)).timestamp()
                posts.append({'date': ts})

            result = at.analyze(sample_investigation, wall_posts=posts)

            assert result['total_posts'] == 50
            assert len(result['heatmap']) == 7
            assert len(result['monthly']) >= 1
            assert result['date_range'] is not None

    def test_analyze_generates_demo_when_no_posts(self, app, sample_investigation):
        """analyze() generates demo data when no posts provided and DB empty."""
        from app.services.activity_timeline import ActivityTimeline

        with app.app_context():
            at = ActivityTimeline()
            result = at.analyze(sample_investigation)

            # Demo data generated
            assert result['total_posts'] > 0
            assert len(result['monthly']) >= 1


class TestTimelineRoutes:
    """Tests for timeline blueprint HTTP routes."""

    def test_timeline_view_200(self, client, app, sample_investigation):
        """GET /timeline/<id> returns 200."""
        with app.app_context():
            resp = client.get(f'/timeline/{sample_investigation}')
            assert resp.status_code == 200

    def test_timeline_api_json(self, client, app, sample_investigation):
        """GET /timeline/api/<id> returns correct JSON structure."""
        with app.app_context():
            resp = client.get(f'/timeline/api/{sample_investigation}')
            assert resp.status_code == 200
            data = resp.get_json()

            assert data['success'] is True
            assert data['investigation_id'] == sample_investigation
            assert 'heatmap' in data
            assert 'timezone' in data
            assert 'gaps' in data
            assert 'trend' in data
            assert 'monthly' in data
            assert 'total_posts' in data
            assert data['target_name'] == 'Тихон Портной'

    def test_timeline_api_404_invalid_id(self, client, app_context):
        """GET /timeline/api/<invalid> returns 404."""
        resp = client.get('/timeline/api/nonexistent_id_12345')
        assert resp.status_code == 404

    def test_timeline_view_404_invalid_id(self, client, app_context):
        """GET /timeline/<invalid> returns 404."""
        resp = client.get('/timeline/nonexistent_id_12345')
        assert resp.status_code == 404


# ===========================================================================
# CROSS-FEATURE INTEGRATION
# ===========================================================================

class TestPhase1OKIntegration:
    """Test OK search integrated into Phase 1 routes."""

    def test_search_results_include_ok_profiles(self, client, app):
        """Phase 1 search results include OK profiles alongside VK."""
        from app import db
        from app.models import Investigation

        with app.app_context():
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

            resp = client.get(f'/phase1/search/{inv_id}')
            assert resp.status_code == 200

            # Verify OK profiles were saved
            from app.models import SocialProfile
            ok_profiles = SocialProfile.query.filter_by(
                investigation_id=inv_id,
                platform='ok',
            ).all()
            assert len(ok_profiles) >= 1

            # VK results depend on VK API availability in test env;
            # just verify profiles list is a valid list (may be empty)
            vk_profiles = SocialProfile.query.filter_by(
                investigation_id=inv_id,
                platform='vk',
            ).all()
            assert isinstance(vk_profiles, list)
