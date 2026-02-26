"""
IBP End-to-End Smoke Tests
==========================
Validates all routes and APIs boot without crashes.
Uses Flask test client (no live server needed).
"""

import pytest
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Disable auth before importing app so is_auth_enabled() returns False
_orig_pw = os.environ.get('IBP_PASSWORD')
_orig_ph = os.environ.get('IBP_PASSWORD_HASH')
os.environ['IBP_PASSWORD'] = ''
os.environ['IBP_PASSWORD_HASH'] = ''

from app import create_app, db


@pytest.fixture(scope='module')
def app():
    """Create test app with in-memory database, auth disabled."""
    application = create_app('testing')
    application.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    application.config['TESTING'] = True
    application.config['WTF_CSRF_ENABLED'] = False

    # Remove global auth check so routes are accessible
    application.before_request_funcs[None] = [
        f for f in application.before_request_funcs.get(None, [])
        if f.__name__ != 'check_auth'
    ]

    with application.app_context():
        db.create_all()
        yield application
        db.drop_all()

    # Restore original env vars
    for key, orig_val in [
        ('IBP_PASSWORD', _orig_pw),
        ('IBP_PASSWORD_HASH', _orig_ph),
    ]:
        if orig_val:
            os.environ[key] = orig_val
        elif key in os.environ:
            del os.environ[key]


@pytest.fixture(scope='module')
def client(app):
    """Flask test client."""
    return app.test_client()


# ============================================
# PAGE LOAD TESTS
# ============================================

class TestPageLoads:
    """All key pages should load without Jinja2 or server errors."""

    @pytest.mark.parametrize('path', [
        '/',
        '/phase1/new',
        '/investigations',
        '/phase2/',
        '/vk/callback',
    ])
    def test_page_loads(self, client, path):
        response = client.get(path, follow_redirects=True)
        assert response.status_code == 200, f"{path} returned {response.status_code}"
        text = response.get_data(as_text=True)
        assert 'TemplateSyntaxError' not in text, f"{path} has Jinja2 syntax error"
        assert 'UndefinedError' not in text, f"{path} has undefined variable"
        assert 'Traceback' not in text, f"{path} shows raw traceback"

    def test_404_page(self, client):
        response = client.get('/nonexistent-page-xyz')
        assert response.status_code == 404
        text = response.get_data(as_text=True)
        assert 'Traceback' not in text, "404 should not show raw traceback"


# ============================================
# API ENDPOINT TESTS
# ============================================

class TestAPIs:
    """API endpoints should return valid JSON responses."""

    def test_vk_token_status(self, client):
        response = client.get('/api/vk/token-status')
        assert response.status_code == 200
        data = response.get_json()
        assert 'valid' in data
        assert 'token_set' in data

    def test_phase2_status(self, client):
        response = client.get('/phase2/status')
        assert response.status_code == 200
        data = response.get_json()
        assert 'status' in data
        assert data['status'] == 'ready'

    def test_phase2_start_no_data(self, client):
        response = client.post('/phase2/start',
                               content_type='application/json',
                               data='{}')
        assert response.status_code == 400

    def test_phase2_start_no_profiles(self, client):
        response = client.post('/phase2/start',
                               content_type='application/json',
                               data=json.dumps({
                                   'selected_profiles': [],
                                   'target_name': 'Test',
                               }))
        assert response.status_code == 400

    def test_phase2_progress_not_found(self, client):
        response = client.get('/phase2/progress/nonexistent123')
        assert response.status_code == 404

    def test_delete_investigation_not_found(self, client):
        response = client.delete('/api/investigations/nonexistent123')
        assert response.status_code == 404


# ============================================
# INVESTIGATION LIFECYCLE TEST
# ============================================

class TestInvestigationLifecycle:
    """Test creating an investigation through Phase 1."""

    def test_create_investigation(self, client, app):
        """Phase 1 POST should create an investigation."""
        response = client.post('/phase1/new',
                               data={
                                   'target_name': 'Тихон Портной',
                                   'city': '',
                               },
                               content_type='application/x-www-form-urlencoded')
        assert response.status_code == 200
        data = response.get_json()
        assert data.get('success') is True
        assert 'investigation_id' in data
        assert 'redirect' in data

        # Verify investigation exists in DB
        with app.app_context():
            from app.models import Investigation
            inv = Investigation.query.get(data['investigation_id'])
            assert inv is not None
            assert inv.input_name == 'Тихон Портной'
            assert inv.status == 'phase_1'

    def test_investigations_list_shows_created(self, client):
        """Investigations list page should show the created investigation."""
        response = client.get('/investigations')
        assert response.status_code == 200
        text = response.get_data(as_text=True)
        # The investigation we just created should appear
        assert 'Тихон' in text or 'investigation-card' in text


# ============================================
# SECURITY TESTS
# ============================================

class TestSecurity:
    """Basic security validations."""

    def test_html_injection_stripped(self, client):
        """HTML tags in name input should be stripped."""
        response = client.post('/phase1/new',
                               data={
                                   'target_name': '<script>alert(1)</script>Test Name',
                                   'city': '',
                               },
                               content_type='application/x-www-form-urlencoded')
        assert response.status_code == 200
        data = response.get_json()
        if data.get('success'):
            # Verify the stored name doesn't contain script tags
            from app.models import Investigation
            inv = Investigation.query.get(data['investigation_id'])
            assert '<script>' not in (inv.input_name or '')

    def test_vk_save_token_rejects_empty(self, client):
        """VK save token should reject empty tokens."""
        response = client.post('/vk/save-token',
                               content_type='application/json',
                               data=json.dumps({'token': ''}))
        assert response.status_code == 400


# ============================================
# ERROR HANDLING TESTS
# ============================================

class TestErrorHandling:
    """Verify error pages display correctly."""

    def test_report_nonexistent(self, client):
        """Report for non-existent investigation should return error."""
        response = client.get('/report/nonexistent-id-123')
        assert response.status_code in [404, 200]  # Some routes render error.html with 404
        text = response.get_data(as_text=True)
        assert 'Traceback' not in text

    def test_phase2_analyze_nonexistent(self, client):
        """Phase 2 analyze for non-existent investigation should return error."""
        response = client.get('/phase2/analyze/nonexistent-id-123')
        assert response.status_code in [404, 400, 200]
        text = response.get_data(as_text=True)
        assert 'Traceback' not in text
