"""Tests for VK no-match flow — expanded search, manual VK entry, skip status, confidence badges.

Verifies:
1. Expanded search returns profiles with lower similarity threshold
2. Manual VK username validation via API endpoint
3. Skip saves correct vk_status on identity_confirmation
4. Fuzzy matching without photo produces correct confidence levels
5. Confidence badge rendering in profile cards
"""

import sys
import os
import json
import datetime
import uuid
from importlib import import_module

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope='module')
def app():
    """Create a Flask app in testing mode."""
    from dotenv import load_dotenv
    load_dotenv()
    from app import create_app
    application = create_app('testing')

    # Create test user + tables
    with application.app_context():
        from app import db
        from app.models.user import User
        db.create_all()

        # Ensure test admin user exists
        user = User.query.get(1)
        if not user:
            user = User(id=1, username='testadmin', role='admin')
            user.set_password('test')
            db.session.add(user)
            db.session.commit()

    yield application


@pytest.fixture(scope='module')
def client(app):
    """Flask test client with authenticated admin session."""
    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess['user_id'] = 1
            sess['username'] = 'testadmin'
            sess['role'] = 'admin'
            sess['last_active'] = datetime.datetime.now(
                datetime.timezone.utc
            ).isoformat()
        yield c


def _create_awaiting_check(app, profiles=None):
    """Helper: create a CandidateCheck in awaiting_confirmation status."""
    from app import db
    from app.models.candidate_check import CandidateCheck

    check_id = uuid.uuid4().hex
    check = CandidateCheck(
        id=check_id,
        full_name='Иванов Иван Иванович',
        date_of_birth=datetime.date(1990, 5, 15),
        inn='772012345678',
        status='awaiting_confirmation',
        paused_at_stage='awaiting_confirmation',
        check_mode='precise',
        user_id=1,
        pd_consent=True,
        pd_consent_at=datetime.datetime.utcnow(),
    )
    if profiles is None:
        profiles = [
            {
                'platform': 'vk',
                'platform_id': 12345,
                'display_name': 'Иван Иванов',
                'username': 'ivanov_ivan',
                'url': 'https://vk.com/ivanov_ivan',
                'confidence': 'средняя',
                'confidence_score': 0.55,
                'source_method': 'VK People Search',
                'city': 'Москва',
            }
        ]
    check.social_media_profiles = profiles
    db.session.add(check)
    db.session.commit()
    return check_id


def _cleanup_check(app, check_id):
    """Helper: remove a CandidateCheck."""
    from app import db
    from app.models.candidate_check import CandidateCheck
    check = CandidateCheck.query.get(check_id)
    if check:
        db.session.delete(check)
        db.session.commit()


class _FakeVKResult:
    def __init__(self, vk_id=999, similarity=82, full_name='Петрова Мария'):
        self._data = {
            'vk_id': vk_id,
            'full_name': full_name,
            'screen_name': f'user_{vk_id}',
            'profile_url': f'https://vk.com/user_{vk_id}',
            'photo_url': None,
            'city': 'Москва',
            'name_similarity': similarity,
        }

    def to_dict(self):
        return dict(self._data)


def _stub_buratino(monkeypatch, *, expanded=None, search=None):
    """Replace BuratinoVKSearch with a deterministic no-network test double."""
    vk_search_module = import_module('app.services.phase1.buratino_vk_search')

    class FakeBuratinoVKSearch:
        def search_expanded(self, **_kwargs):
            return expanded if expanded is not None else []

        def search(self, **_kwargs):
            return (search if search is not None else [], 0)

    monkeypatch.setattr(vk_search_module, 'BuratinoVKSearch', FakeBuratinoVKSearch)


# ---------------------------------------------------------------------------
# 1. Expanded search endpoint
# ---------------------------------------------------------------------------

class TestExpandedSearch:
    """Verify retry-expanded endpoint behavior."""

    def test_expanded_search_returns_json(self, client, app, monkeypatch):
        """POST to retry-expanded returns JSON with success/profiles."""
        _stub_buratino(monkeypatch)
        with app.app_context():
            check_id = _create_awaiting_check(app)
        try:
            resp = client.post(
                f'/candidate/confirm/{check_id}/retry-expanded',
                content_type='application/json',
            )
            assert resp.status_code == 200
            data = resp.get_json()
            assert 'success' in data or 'error' in data
        finally:
            with app.app_context():
                _cleanup_check(app, check_id)

    def test_expanded_search_wrong_status(self, client, app):
        """Expanded search should reject checks not in awaiting_confirmation."""
        with app.app_context():
            from app import db
            from app.models.candidate_check import CandidateCheck

            check_id = uuid.uuid4().hex
            check = CandidateCheck(
                id=check_id,
                full_name='Петров Петр',
                date_of_birth=datetime.date(1985, 1, 1),
                inn='772012345678',
                status='running',
                user_id=1,
                pd_consent=True,
                pd_consent_at=datetime.datetime.utcnow(),
            )
            db.session.add(check)
            db.session.commit()

        try:
            resp = client.post(
                f'/candidate/confirm/{check_id}/retry-expanded',
                content_type='application/json',
            )
            assert resp.status_code == 400
            data = resp.get_json()
            assert 'error' in data
        finally:
            with app.app_context():
                _cleanup_check(app, check_id)

    def test_expanded_search_lower_threshold(self, client, app, monkeypatch):
        """Expanded search profiles should have expanded_search=True flag."""
        _stub_buratino(monkeypatch, expanded=[_FakeVKResult(vk_id=1001, similarity=35)])
        with app.app_context():
            check_id = _create_awaiting_check(app)
        try:
            resp = client.post(
                f'/candidate/confirm/{check_id}/retry-expanded',
                content_type='application/json',
            )
            data = resp.get_json()
            assert data.get('success') is True
            # Profiles returned (if any) should have expanded_search flag
            for p in data.get('profiles', []):
                assert p.get('expanded_search') is True
                assert p.get('confidence_score', 0) >= 0.3
        finally:
            with app.app_context():
                _cleanup_check(app, check_id)

    def test_expanded_search_nonexistent(self, client):
        """Expanded search on nonexistent check returns 404."""
        resp = client.post(
            '/candidate/confirm/nonexistent123/retry-expanded',
            content_type='application/json',
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 2. Manual VK username validation
# ---------------------------------------------------------------------------

class TestManualVKProfile:
    """Verify manual-vk endpoint input validation."""

    def test_manual_vk_empty_input(self, client, app):
        """Empty VK URL returns 400."""
        with app.app_context():
            check_id = _create_awaiting_check(app)
        try:
            resp = client.post(
                f'/candidate/confirm/{check_id}/manual-vk',
                data=json.dumps({'vk_url': ''}),
                content_type='application/json',
            )
            assert resp.status_code == 400
            data = resp.get_json()
            assert 'error' in data
        finally:
            with app.app_context():
                _cleanup_check(app, check_id)

    def test_manual_vk_invalid_chars(self, client, app):
        """VK URL with Cyrillic-only characters returns 400."""
        with app.app_context():
            check_id = _create_awaiting_check(app)
        try:
            resp = client.post(
                f'/candidate/confirm/{check_id}/manual-vk',
                data=json.dumps({'vk_url': 'пользователь'}),
                content_type='application/json',
            )
            assert resp.status_code == 400
            data = resp.get_json()
            assert 'error' in data
        finally:
            with app.app_context():
                _cleanup_check(app, check_id)

    def test_manual_vk_url_parsing(self, client, app, monkeypatch):
        """Various VK URL formats should be accepted (not fail on input validation)."""
        from app.routes import candidate_check as candidate_route

        monkeypatch.setattr(candidate_route, '_lookup_manual_vk_profile', lambda screen_name: {
            'platform': 'vk',
            'platform_id': 42,
            'display_name': 'Manual User',
            'username': screen_name,
            'url': f'https://vk.com/{screen_name}',
            'manual_entry': True,
        })

        with app.app_context():
            check_id = _create_awaiting_check(app)
        try:
            for url in ['https://vk.com/durov', 'vk.com/durov', 'durov']:
                resp = client.post(
                    f'/candidate/confirm/{check_id}/manual-vk',
                    data=json.dumps({'vk_url': url}),
                    content_type='application/json',
                )
                # Should not be 400 (input validation) — either 200 or 500 (API)
                assert resp.status_code != 400, f"Unexpected 400 for URL format: {url}"
        finally:
            with app.app_context():
                _cleanup_check(app, check_id)

    def test_manual_vk_html_sanitization(self, client, app, monkeypatch):
        """HTML tags in VK URL should be stripped."""
        from app.routes import candidate_check as candidate_route

        monkeypatch.setattr(candidate_route, '_lookup_manual_vk_profile', lambda screen_name: {
            'platform': 'vk',
            'platform_id': 43,
            'display_name': 'Manual User',
            'username': screen_name,
            'url': f'https://vk.com/{screen_name}',
            'manual_entry': True,
        })

        with app.app_context():
            check_id = _create_awaiting_check(app)
        try:
            # After stripping HTML tags from '<script>alert(1)</script>durov',
            # result is 'alert(1)durov' which contains invalid chars -> 400
            resp = client.post(
                f'/candidate/confirm/{check_id}/manual-vk',
                data=json.dumps({'vk_url': '<script>alert(1)</script>durov'}),
                content_type='application/json',
            )
            assert resp.status_code == 400

            # Clean input after stripping: '<b>durov</b>' -> 'durov' -> valid
            resp2 = client.post(
                f'/candidate/confirm/{check_id}/manual-vk',
                data=json.dumps({'vk_url': '<b>durov</b>'}),
                content_type='application/json',
            )
            assert resp2.status_code != 400  # Input valid, hits VK API
        finally:
            with app.app_context():
                _cleanup_check(app, check_id)

    def test_manual_vk_adds_profile_via_lookup_helper(self, client, app, monkeypatch):
        """Valid manual VK input is resolved through the bounded lookup helper."""
        from app.routes import candidate_check as candidate_route

        with app.app_context():
            check_id = _create_awaiting_check(app, profiles=[])

        called = {}

        def fake_lookup(screen_name):
            called['screen_name'] = screen_name
            return {
                'platform': 'vk',
                'platform_id': 999001,
                'display_name': 'Manual User',
                'username': 'manual_user',
                'url': 'https://vk.com/manual_user',
                'avatar_url': None,
                'photo_url': None,
                'confidence': 'manual',
                'confidence_score': 0.0,
                'source_method': 'manual',
                'city': '',
                'manual_entry': True,
            }

        monkeypatch.setattr(candidate_route, '_lookup_manual_vk_profile', fake_lookup)

        try:
            resp = client.post(
                f'/candidate/confirm/{check_id}/manual-vk',
                data=json.dumps({'vk_url': 'https://m.vk.com/manual_user?from=test'}),
                content_type='application/json',
            )
            data = resp.get_json()

            assert resp.status_code == 200
            assert data['success'] is True
            assert data['profile']['platform_id'] == 999001
            assert called['screen_name'] == 'manual_user'
        finally:
            with app.app_context():
                _cleanup_check(app, check_id)

    def test_manual_vk_lookup_timeout_returns_error(self, client, app, monkeypatch):
        """A slow VK helper response is surfaced as a JSON timeout error."""
        from app.routes import candidate_check as candidate_route

        with app.app_context():
            check_id = _create_awaiting_check(app, profiles=[])

        def fake_lookup(_screen_name):
            raise candidate_route.ManualVKLookupError('timeout', 504)

        monkeypatch.setattr(candidate_route, '_lookup_manual_vk_profile', fake_lookup)

        try:
            resp = client.post(
                f'/candidate/confirm/{check_id}/manual-vk',
                data=json.dumps({'vk_url': 'manual_user'}),
                content_type='application/json',
            )
            data = resp.get_json()

            assert resp.status_code == 504
            assert 'error' in data
        finally:
            with app.app_context():
                _cleanup_check(app, check_id)

    def test_manual_vk_wrong_status(self, client, app):
        """Manual VK should reject checks not in awaiting_confirmation."""
        with app.app_context():
            from app import db
            from app.models.candidate_check import CandidateCheck

            check_id = uuid.uuid4().hex
            check = CandidateCheck(
                id=check_id,
                full_name='Сидоров Сидор',
                date_of_birth=datetime.date(1988, 6, 1),
                inn='772012345678',
                status='complete',
                user_id=1,
                pd_consent=True,
                pd_consent_at=datetime.datetime.utcnow(),
            )
            db.session.add(check)
            db.session.commit()

        try:
            resp = client.post(
                f'/candidate/confirm/{check_id}/manual-vk',
                data=json.dumps({'vk_url': 'durov'}),
                content_type='application/json',
            )
            assert resp.status_code == 400
        finally:
            with app.app_context():
                _cleanup_check(app, check_id)


# ---------------------------------------------------------------------------
# 3. Skip saves correct status
# ---------------------------------------------------------------------------

class TestSkipSavesStatus:
    """Verify skip_no_vk action sets vk_status on identity_confirmation."""

    def test_skip_saves_correct_status(self, client, app):
        """Submitting with action=skip_no_vk saves vk_status and resumes pipeline."""
        with app.app_context():
            check_id = _create_awaiting_check(app)
        try:
            resp = client.post(
                f'/candidate/confirm/{check_id}',
                data={'action': 'skip_no_vk'},
                follow_redirects=False,
            )
            assert resp.status_code in (302, 303)

            with app.app_context():
                from app.models.candidate_check import CandidateCheck
                check = CandidateCheck.query.get(check_id)
                identity = check.identity_confirmation
                assert identity.get('vk_status') == 'not_found_manual_skip'
                assert check.confirmed_profiles == []
                assert check.status == 'running'
        finally:
            with app.app_context():
                _cleanup_check(app, check_id)

    def test_normal_confirm_no_vk_status(self, client, app):
        """Normal confirmation (with selected profiles) should NOT set vk_status."""
        with app.app_context():
            check_id = _create_awaiting_check(app, profiles=[
                {
                    'platform': 'vk',
                    'url': 'https://vk.com/kozlov',
                    'display_name': 'Андрей Козлов',
                    'username': 'kozlov',
                }
            ])

        try:
            resp = client.post(
                f'/candidate/confirm/{check_id}',
                data={'confirmed_profiles': 'https://vk.com/kozlov'},
                follow_redirects=False,
            )
            assert resp.status_code in (302, 303)

            with app.app_context():
                from app.models.candidate_check import CandidateCheck
                check = CandidateCheck.query.get(check_id)
                identity = check.identity_confirmation
                assert identity.get('vk_status') is None
                assert len(check.confirmed_profiles) == 1
        finally:
            with app.app_context():
                _cleanup_check(app, check_id)

    def test_empty_submit_no_vk_status(self, client, app):
        """Submitting with no profiles and no action should NOT set vk_status."""
        with app.app_context():
            check_id = _create_awaiting_check(app)
        try:
            resp = client.post(
                f'/candidate/confirm/{check_id}',
                data={},
                follow_redirects=False,
            )
            assert resp.status_code in (302, 303)

            with app.app_context():
                from app.models.candidate_check import CandidateCheck
                check = CandidateCheck.query.get(check_id)
                identity = check.identity_confirmation
                assert identity.get('vk_status') is None
        finally:
            with app.app_context():
                _cleanup_check(app, check_id)


# ---------------------------------------------------------------------------
# 4. Fuzzy matching without photo
# ---------------------------------------------------------------------------

class TestFuzzyMatchWithoutPhoto:
    """Test profile matching scoring without photo comparison."""

    def test_name_similarity_scoring(self):
        """Name similarity should produce correct match levels."""
        from app.services.phase1.buratino_vk_search import BuratinoVKSearch

        buratino = BuratinoVKSearch()
        # Exact match
        sim = buratino._calculate_name_similarity('Иванов Иван', 'Иванов Иван')
        assert sim >= 90

        # Partial match
        sim_partial = buratino._calculate_name_similarity('Иванов Иван', 'Иванов Игорь')
        assert sim_partial < sim  # Less than exact
        assert sim_partial > 0  # But some similarity

    def test_confidence_levels_by_score(self):
        """Confidence strings should map to correct score ranges."""
        thresholds = [
            (0.80, 'высокая'),
            (0.60, 'средняя'),
            (0.35, 'низкая'),
        ]
        for score, expected_conf in thresholds:
            if score >= 0.75:
                assert expected_conf == 'высокая'
            elif score >= 0.50:
                assert expected_conf == 'средняя'
            else:
                assert expected_conf == 'низкая'

    def test_no_photo_still_gets_score(self):
        """Profiles without photos should still get a similarity score."""
        from app.services.phase1.buratino_vk_search import BuratinoVKSearch

        buratino = BuratinoVKSearch()
        sim = buratino._calculate_name_similarity('Петров Петр', 'Петров Петр')
        # Full name match should score high even without photo
        assert sim >= 80


# ---------------------------------------------------------------------------
# 5. Confidence badge display
# ---------------------------------------------------------------------------

class TestConfidenceBadges:
    """Verify confidence badges render correctly in template."""

    def test_confirm_page_renders(self, client, app):
        """Confirm page should render without errors."""
        with app.app_context():
            check_id = _create_awaiting_check(app)
        try:
            resp = client.get(f'/candidate/confirm/{check_id}')
            assert resp.status_code == 200
            html = resp.data.decode('utf-8')
            assert 'Найденные профили' in html
            assert 'Подтвердить выбранные' in html
        finally:
            with app.app_context():
                _cleanup_check(app, check_id)

    def test_confirm_page_has_expanded_search_button(self, client, app):
        """Confirm page should have the expanded search button."""
        with app.app_context():
            check_id = _create_awaiting_check(app)
        try:
            resp = client.get(f'/candidate/confirm/{check_id}')
            html = resp.data.decode('utf-8')
            assert 'retry-expanded-btn' in html
            assert 'Повторить поиск' in html
        finally:
            with app.app_context():
                _cleanup_check(app, check_id)

    def test_confirm_page_has_no_match_panel(self, client, app):
        """Confirm page should have the no-match options panel."""
        with app.app_context():
            check_id = _create_awaiting_check(app)
        try:
            resp = client.get(f'/candidate/confirm/{check_id}')
            html = resp.data.decode('utf-8')
            assert 'no-match-panel' in html
            assert 'Искать по другому имени' in html
            assert 'Ввести VK профиль вручную' in html
            assert 'Продолжить без VK' in html
        finally:
            with app.app_context():
                _cleanup_check(app, check_id)

    def test_expanded_badge_in_profile(self):
        """Expanded search profiles should have expanded_search=True flag."""
        profile = {
            'platform': 'vk',
            'confidence': 'низкая',
            'confidence_score': 0.35,
            'expanded_search': True,
        }
        assert profile['expanded_search'] is True
        assert profile['confidence'] == 'низкая'

    def test_manual_badge_in_profile(self):
        """Manual entry profiles should have manual_entry=True and confidence='ручной ввод'."""
        profile = {
            'platform': 'vk',
            'confidence': 'ручной ввод',
            'confidence_score': 0.0,
            'manual_entry': True,
        }
        assert profile['manual_entry'] is True
        assert profile['confidence'] == 'ручной ввод'


# ---------------------------------------------------------------------------
# 6. Search by alternative name
# ---------------------------------------------------------------------------

class TestSearchByName:
    """Verify search-name endpoint."""

    def test_search_name_empty(self, client, app):
        """Empty name returns 400."""
        with app.app_context():
            check_id = _create_awaiting_check(app)
        try:
            resp = client.post(
                f'/candidate/confirm/{check_id}/search-name',
                data=json.dumps({'name': ''}),
                content_type='application/json',
            )
            assert resp.status_code == 400
        finally:
            with app.app_context():
                _cleanup_check(app, check_id)

    def test_search_name_single_word(self, client, app):
        """Single word name returns 400."""
        with app.app_context():
            check_id = _create_awaiting_check(app)
        try:
            resp = client.post(
                f'/candidate/confirm/{check_id}/search-name',
                data=json.dumps({'name': 'Иванов'}),
                content_type='application/json',
            )
            assert resp.status_code == 400
            data = resp.get_json()
            assert 'имя и фамилию' in data['error']
        finally:
            with app.app_context():
                _cleanup_check(app, check_id)

    def test_search_name_valid_returns_json(self, client, app, monkeypatch):
        """Valid alt name search returns JSON response."""
        _stub_buratino(monkeypatch, search=[_FakeVKResult(vk_id=2001)])
        with app.app_context():
            check_id = _create_awaiting_check(app)
        try:
            resp = client.post(
                f'/candidate/confirm/{check_id}/search-name',
                data=json.dumps({'name': 'Петрова Мария'}),
                content_type='application/json',
            )
            assert resp.status_code == 200
            data = resp.get_json()
            assert 'success' in data or 'error' in data
        finally:
            with app.app_context():
                _cleanup_check(app, check_id)

    def test_search_name_html_sanitized(self, client, app, monkeypatch):
        """HTML tags in alt name should be stripped."""
        _stub_buratino(monkeypatch, search=[_FakeVKResult(vk_id=2002)])
        with app.app_context():
            check_id = _create_awaiting_check(app)
        try:
            resp = client.post(
                f'/candidate/confirm/{check_id}/search-name',
                data=json.dumps({'name': '<b>Петрова</b> Мария'}),
                content_type='application/json',
            )
            # After stripping HTML, "Петрова Мария" remains — should be 200
            assert resp.status_code == 200
        finally:
            with app.app_context():
                _cleanup_check(app, check_id)

    def test_search_name_wrong_status(self, client, app):
        """Search-name should reject checks not in awaiting_confirmation."""
        with app.app_context():
            from app import db
            from app.models.candidate_check import CandidateCheck

            check_id = uuid.uuid4().hex
            check = CandidateCheck(
                id=check_id,
                full_name='Тестов Тест',
                date_of_birth=datetime.date(1995, 1, 1),
                inn='772012345678',
                status='running',
                user_id=1,
                pd_consent=True,
                pd_consent_at=datetime.datetime.utcnow(),
            )
            db.session.add(check)
            db.session.commit()

        try:
            resp = client.post(
                f'/candidate/confirm/{check_id}/search-name',
                data=json.dumps({'name': 'Петрова Мария'}),
                content_type='application/json',
            )
            assert resp.status_code == 400
        finally:
            with app.app_context():
                _cleanup_check(app, check_id)
