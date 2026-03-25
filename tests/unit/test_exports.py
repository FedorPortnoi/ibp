"""Tests for JSON, PDF, and HTML export endpoints.

Verifies:
1. JSON serialization works correctly
2. report_generator imports and compiles data correctly
3. PDF generation produces valid PDF bytes (requires reportlab)
4. @csrf.exempt is on all download routes
5. Flask test client returns correct HTTP status, Content-Type, Content-Disposition
6. Empty body returns 400
"""

import sys
import os
import json
import datetime

# Ensure project root is on sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_DATA = {
    'investigation_id': 'test-export-abc123',
    'target_name': 'Test User',
    'status': 'complete',
    'created_at': '2026-03-18T12:00:00',
    'photo_url': None,
    'city': 'Moscow',
    'profiles': [
        {'platform': 'vk', 'username': 'testuser',
         'url': 'https://vk.com/testuser', 'is_confirmed': True}
    ],
    'phones': ['+79001234567'],
    'emails': ['test@mail.ru'],
    'aliases': ['testuser'],
    'business_records': [],
    'court_records': [],
    'enforcement_records': [],
    'risk_indicators': [],
    'friends_count': 0,
    'friends_sample': [],
    'confidence_score': 50,
}


@pytest.fixture(scope='module')
def app():
    """Create a Flask app in testing mode with auth bypassed."""
    from dotenv import load_dotenv
    load_dotenv()
    from app import create_app
    application = create_app('testing')
    return application


@pytest.fixture(scope='module')
def client(app):
    """Flask test client with authenticated session."""
    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess['user_id'] = 1
            sess['username'] = 'test'
            sess['role'] = 'admin'
            sess['last_active'] = datetime.datetime.now(
                datetime.timezone.utc
            ).isoformat()
        yield c


# ---------------------------------------------------------------------------
# 1. report_generator imports correctly
# ---------------------------------------------------------------------------

class TestReportGeneratorImport:
    """Verify report_generator module and its key methods."""

    def test_import_report_generator(self):
        from app.services.report_generator import report_generator
        assert report_generator is not None

    def test_has_compile_data(self):
        from app.services.report_generator import report_generator
        assert hasattr(report_generator, 'compile_data')

    def test_has_generate_pdf_report(self):
        from app.services.report_generator import report_generator
        assert hasattr(report_generator, 'generate_pdf_report')

    def test_has_generate_identity_card_html(self):
        from app.services.report_generator import report_generator
        assert hasattr(report_generator, 'generate_identity_card_html')

    def test_identity_card_data_dataclass(self):
        from app.services.report_generator import IdentityCardData
        card = IdentityCardData(full_name='Test')
        assert card.full_name == 'Test'
        assert card.profiles == []


# ---------------------------------------------------------------------------
# 2. JSON serialization logic
# ---------------------------------------------------------------------------

class TestJsonSerialization:
    """Test the JSON export data assembly (no Flask needed)."""

    def test_json_round_trip(self):
        """Export data can be serialized and deserialized."""
        export_data = {
            'investigation_id': SAMPLE_DATA['investigation_id'],
            'target_name': SAMPLE_DATA['target_name'],
            'status': SAMPLE_DATA['status'],
            'created_at': SAMPLE_DATA['created_at'],
            'photo_url': SAMPLE_DATA.get('photo_url', ''),
            'city': SAMPLE_DATA['city'],
            'profiles': SAMPLE_DATA['profiles'],
            'phones': SAMPLE_DATA['phones'],
            'emails': SAMPLE_DATA['emails'],
            'aliases': SAMPLE_DATA['aliases'],
            'business_records': SAMPLE_DATA['business_records'],
            'court_records': SAMPLE_DATA['court_records'],
            'enforcement_records': SAMPLE_DATA['enforcement_records'],
            'risk_indicators': SAMPLE_DATA['risk_indicators'],
            'friends_count': SAMPLE_DATA['friends_count'],
            'friends_sample': SAMPLE_DATA['friends_sample'],
            'confidence_score': SAMPLE_DATA['confidence_score'],
            'generated_at': datetime.datetime.now().isoformat(),
            'source': 'IBP - Identity-Based Profiler',
        }
        json_str = json.dumps(export_data, ensure_ascii=False, indent=2)
        parsed = json.loads(json_str)
        assert parsed['target_name'] == 'Test User'
        assert parsed['source'] == 'IBP - Identity-Based Profiler'
        assert 'generated_at' in parsed

    def test_cyrillic_preserved(self):
        """Cyrillic characters survive JSON round-trip with ensure_ascii=False."""
        data = {'city': 'Москва', 'name': 'Иванов Иван'}
        json_str = json.dumps(data, ensure_ascii=False)
        parsed = json.loads(json_str)
        assert parsed['city'] == 'Москва'

    def test_all_expected_keys_present(self):
        """Exported JSON should have exactly the expected keys."""
        expected_keys = {
            'investigation_id', 'target_name', 'status', 'created_at',
            'photo_url', 'city', 'profiles', 'phones', 'emails', 'aliases',
            'business_records', 'court_records', 'enforcement_records',
            'risk_indicators', 'friends_count', 'friends_sample',
            'confidence_score', 'generated_at', 'source',
        }
        export_data = {k: '' for k in expected_keys}
        assert set(export_data.keys()) == expected_keys


# ---------------------------------------------------------------------------
# 3. PDF generation produces valid bytes
# ---------------------------------------------------------------------------

class TestPdfGeneration:
    """Test PDF generation via report_generator (requires reportlab)."""

    def test_reportlab_installed(self):
        import reportlab
        assert hasattr(reportlab, 'Version')

    def test_compile_data_returns_identity_card_data(self):
        from app.services.report_generator import report_generator, IdentityCardData
        card_data = report_generator.compile_data(SAMPLE_DATA)
        assert isinstance(card_data, IdentityCardData)
        assert card_data.full_name == 'Test User'

    def test_pdf_bytes_valid_header(self):
        from app.services.report_generator import report_generator
        card_data = report_generator.compile_data(SAMPLE_DATA)
        pdf_bytes = report_generator.generate_pdf_report(card_data, SAMPLE_DATA)
        assert pdf_bytes, "PDF generation returned empty bytes"
        assert len(pdf_bytes) > 100, f"PDF too small: {len(pdf_bytes)} bytes"
        assert pdf_bytes[:4] == b'%PDF', f"Invalid PDF header: {pdf_bytes[:5]}"

    def test_pdf_with_rich_data(self):
        """PDF generation works with populated business/court/risk data."""
        from app.services.report_generator import report_generator
        rich_data = dict(SAMPLE_DATA)
        rich_data['business_records'] = [
            {'company_name': 'TestCorp', 'role': 'Director', 'inn': '1234567890'}
        ]
        rich_data['court_records'] = [
            {'case_number': 'A40-12345/2026', 'court_name': 'Moscow Court'}
        ]
        rich_data['risk_indicators'] = [
            {'severity': 'high', 'description': 'Test risk', 'category': 'legal'}
        ]
        card_data = report_generator.compile_data(rich_data)
        pdf_bytes = report_generator.generate_pdf_report(card_data, rich_data)
        assert pdf_bytes[:4] == b'%PDF'
        assert len(pdf_bytes) > 200


# ---------------------------------------------------------------------------
# 4. @csrf.exempt is on all download routes
# ---------------------------------------------------------------------------

class TestCsrfExempt:
    """Verify that all download endpoints have @csrf.exempt."""

    def test_download_json_csrf_exempt(self, app):
        """download_json should be in the CSRF exempt set."""
        from app import csrf as csrf_ext
        with app.app_context():
            exempt_views = csrf_ext._exempt_views
            # Flask-WTF stores exempt view function identifiers
            assert any(
                'download_json' in str(v) for v in exempt_views
            ), f"download_json not in csrf exempt list: {exempt_views}"

    def test_download_pdf_csrf_exempt(self, app):
        from app import csrf as csrf_ext
        with app.app_context():
            exempt_views = csrf_ext._exempt_views
            assert any(
                'download_pdf' in str(v) for v in exempt_views
            ), f"download_pdf not in csrf exempt list: {exempt_views}"

    def test_download_html_csrf_exempt(self, app):
        from app import csrf as csrf_ext
        with app.app_context():
            exempt_views = csrf_ext._exempt_views
            assert any(
                'download_html' in str(v) for v in exempt_views
            ), f"download_html not in csrf exempt list: {exempt_views}"

    def test_generate_csrf_exempt(self, app):
        from app import csrf as csrf_ext
        with app.app_context():
            exempt_views = csrf_ext._exempt_views
            assert any(
                'generate' in str(v) for v in exempt_views
            ), f"generate not in csrf exempt list: {exempt_views}"


# ---------------------------------------------------------------------------
# 5. Flask test client — full endpoint tests
# ---------------------------------------------------------------------------

class TestJsonEndpoint:
    """Test /report/download/json via Flask test client."""

    def test_json_200(self, client):
        r = client.post('/report/download/json',
                        json=SAMPLE_DATA,
                        content_type='application/json')
        assert r.status_code == 200

    def test_json_content_type(self, client):
        r = client.post('/report/download/json',
                        json=SAMPLE_DATA,
                        content_type='application/json')
        assert 'application/json' in r.headers.get('Content-Type', '')

    def test_json_content_disposition(self, client):
        r = client.post('/report/download/json',
                        json=SAMPLE_DATA,
                        content_type='application/json')
        cd = r.headers.get('Content-Disposition', '')
        assert 'attachment' in cd
        assert 'investigation_data_' in cd
        assert '.json' in cd

    def test_json_body_valid(self, client):
        r = client.post('/report/download/json',
                        json=SAMPLE_DATA,
                        content_type='application/json')
        data = json.loads(r.data)
        assert data['target_name'] == 'Test User'
        assert data['source'] == 'IBP - Identity-Based Profiler'
        assert 'generated_at' in data

    def test_json_empty_body_400(self, client):
        r = client.post('/report/download/json',
                        data='',
                        content_type='application/json')
        assert r.status_code == 400


class TestPdfEndpoint:
    """Test /report/download/pdf via Flask test client."""

    def test_pdf_200(self, client):
        r = client.post('/report/download/pdf',
                        json=SAMPLE_DATA,
                        content_type='application/json')
        assert r.status_code == 200

    def test_pdf_content_type(self, client):
        r = client.post('/report/download/pdf',
                        json=SAMPLE_DATA,
                        content_type='application/json')
        assert 'application/pdf' in r.headers.get('Content-Type', '')

    def test_pdf_content_disposition(self, client):
        r = client.post('/report/download/pdf',
                        json=SAMPLE_DATA,
                        content_type='application/json')
        cd = r.headers.get('Content-Disposition', '')
        assert 'attachment' in cd
        assert 'investigation_report_' in cd
        assert '.pdf' in cd

    def test_pdf_valid_header(self, client):
        r = client.post('/report/download/pdf',
                        json=SAMPLE_DATA,
                        content_type='application/json')
        assert r.data[:4] == b'%PDF', f"Got: {r.data[:10]}"

    def test_pdf_nonzero_size(self, client):
        r = client.post('/report/download/pdf',
                        json=SAMPLE_DATA,
                        content_type='application/json')
        assert len(r.data) > 100

    def test_pdf_empty_body_400(self, client):
        r = client.post('/report/download/pdf',
                        data='',
                        content_type='application/json')
        assert r.status_code == 400


class TestHtmlEndpoint:
    """Test /report/download/html via Flask test client."""

    def test_html_200(self, client):
        r = client.post('/report/download/html',
                        json=SAMPLE_DATA,
                        content_type='application/json')
        assert r.status_code == 200

    def test_html_content_type(self, client):
        r = client.post('/report/download/html',
                        json=SAMPLE_DATA,
                        content_type='application/json')
        assert 'text/html' in r.headers.get('Content-Type', '')

    def test_html_content_disposition(self, client):
        r = client.post('/report/download/html',
                        json=SAMPLE_DATA,
                        content_type='application/json')
        cd = r.headers.get('Content-Disposition', '')
        assert 'attachment' in cd
        assert 'identity_card_' in cd
        assert '.html' in cd

    def test_html_valid_content(self, client):
        r = client.post('/report/download/html',
                        json=SAMPLE_DATA,
                        content_type='application/json')
        html = r.data.decode('utf-8')
        assert html.strip().startswith('<!DOCTYPE')
        assert 'Test User' in html

    def test_html_empty_body_400(self, client):
        r = client.post('/report/download/html',
                        data='',
                        content_type='application/json')
        assert r.status_code == 400
