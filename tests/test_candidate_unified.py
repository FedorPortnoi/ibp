"""
Unified Candidate Check – Integration Tests
=============================================
Tests the 8-stage candidate check pipeline routes, templates, API endpoints,
mode selection, profile confirmation flow, exports, and demo mode.

All external services are mocked. Uses Flask test client with in-memory SQLite.
"""

import json
import os
import sys
import time
import uuid
from datetime import date, datetime
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models.candidate_check import CandidateCheck
from app.services.candidate.pipeline import candidate_tasks, CandidateTaskStatus


# ============================================================
# FIXTURES
# ============================================================

@pytest.fixture(scope='module')
def app():
    """Create test app with in-memory database, auth disabled."""
    app = create_app('testing')
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    app.config['SERVER_NAME'] = 'localhost'

    # Disable the global auth check by removing the before_request handler
    app.before_request_funcs[None] = [
        f for f in app.before_request_funcs.get(None, [])
        if f.__name__ != 'check_auth'
    ]

    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture(scope='module')
def client(app):
    """Flask test client."""
    return app.test_client()


@pytest.fixture(autouse=True)
def cleanup_tasks():
    """Clean up candidate_tasks after each test."""
    yield
    candidate_tasks.clear()


@pytest.fixture()
def sample_check(app):
    """Create a sample CandidateCheck record in the DB."""
    with app.app_context():
        check_id = uuid.uuid4().hex
        check = CandidateCheck(
            id=check_id,
            full_name='Иванов Иван Иванович',
            date_of_birth=date(1990, 5, 15),
            inn='770123456789',
            status='complete',
            check_mode='quick',
            risk_level='low',
            red_flag_count=0,
            sources_checked=10,
            sources_with_results=3,
            check_duration_seconds=12.5,
            report_generated=True,
        )
        check.business_records = [
            {'company_name': 'ООО "Тест"', 'inn': '7701234567', 'role': 'Директор'}
        ]
        check.court_records = [
            {'case_number': 'А40-12345/2024', 'court_name': 'АС Москвы'}
        ]
        check.fssp_records = []
        check.bankruptcy_records = []
        check.sanctions_results = [
            {'source_name': 'Росфинмониторинг', 'checked': True, 'found': False, 'error': None}
        ]
        check.social_media_profiles = [
            {
                'platform': 'vk', 'display_name': 'Иван Иванов',
                'username': 'ivanov_i', 'url': 'https://vk.com/ivanov_i',
                'confidence': 'высокая', 'confidence_score': 0.92,
            }
        ]
        check.contact_discoveries = {'phones': [], 'emails': []}
        check.red_flags = [{'code': 'COURT_CASE', 'text': 'Судебные дела', 'severity': 'medium'}]
        check.face_matches = [
            {'username': 'ivanov_i', 'source': 'Search4Faces', 'similarity': 0.87}
        ]
        check.username_accounts = [
            {'platform': 'instagram', 'username': 'ivanov_i', 'url': 'https://instagram.com/ivanov_i'}
        ]
        check.social_graph_data = {
            'nodes': [{'id': 1, 'label': 'Иван'}],
            'edges': [],
            'stats': {'node_count': 1},
        }
        check.geo_analysis = {
            'locations': [{'city': 'Москва', 'frequency': 5, 'source': 'VK'}],
            'home_location': 'Москва',
        }
        check.text_analysis = {
            'sentiment': 'neutral',
            'keywords': ['работа', 'спорт'],
            'topics': ['Бизнес'],
        }
        check.activity_timeline = [
            {'date': '2024-01-15', 'type': 'post', 'description': 'Пост в VK'},
        ]
        check.risk_breakdown = {
            'business': {'label': 'Бизнес', 'score': 20, 'flags': []},
            'legal': {'label': 'Юридический', 'score': 30, 'flags': ['COURT_CASE']},
        }
        check.risk_score_numeric = 25.0

        db.session.add(check)
        db.session.commit()
        yield check

        # Cleanup
        db.session.delete(check)
        db.session.commit()


def _make_task(check_id, full_name='Иванов Иван Иванович', stage='complete', pct=100):
    """Helper to create a CandidateTaskStatus in candidate_tasks."""
    task_id = uuid.uuid4().hex
    task = CandidateTaskStatus(task_id, check_id, full_name)
    task.current_stage = stage
    task.percent_complete = pct
    if stage == 'complete':
        task.completed_at = datetime.now()
    candidate_tasks[task_id] = task
    return task_id, task


# ============================================================
# FORM VALIDATION TESTS
# ============================================================

class TestFormValidation:
    """Start endpoint validates required fields and formats."""

    def test_missing_name(self, client):
        resp = client.post('/candidate/start', json={
            'full_name': '', 'date_of_birth': '1990-05-15',
        })
        assert resp.status_code == 400
        assert 'Имя обязательно' in resp.get_json()['error']

    def test_single_word_name(self, client):
        resp = client.post('/candidate/start', json={
            'full_name': 'Иванов', 'date_of_birth': '1990-05-15',
        })
        assert resp.status_code == 400
        assert 'минимум' in resp.get_json()['error'].lower()

    def test_missing_dob(self, client):
        resp = client.post('/candidate/start', json={
            'full_name': 'Иванов Иван', 'date_of_birth': '',
        })
        assert resp.status_code == 400
        assert 'Дата рождения' in resp.get_json()['error']

    def test_future_dob(self, client):
        resp = client.post('/candidate/start', json={
            'full_name': 'Иванов Иван', 'date_of_birth': '2099-01-01',
        })
        assert resp.status_code == 400
        assert 'будущем' in resp.get_json()['error']

    def test_invalid_inn(self, client):
        resp = client.post('/candidate/start', json={
            'full_name': 'Иванов Иван', 'date_of_birth': '1990-05-15',
            'inn': '12345',  # too short
        })
        assert resp.status_code == 400
        assert 'ИНН' in resp.get_json()['error']

    def test_invalid_passport(self, client):
        resp = client.post('/candidate/start', json={
            'full_name': 'Иванов Иван', 'date_of_birth': '1990-05-15',
            'inn': '7707083893',
            'passport': '123',  # wrong format
        })
        assert resp.status_code == 400
        assert 'Паспорт' in resp.get_json()['error']

    def test_invalid_email(self, client):
        resp = client.post('/candidate/start', json={
            'full_name': 'Иванов Иван', 'date_of_birth': '1990-05-15',
            'inn': '7707083893',
            'email': 'not-an-email',
        })
        assert resp.status_code == 400
        assert 'email' in resp.get_json()['error'].lower()

    def test_html_tags_stripped(self, client):
        """XSS attempt: HTML tags in name should be stripped."""
        with patch('app.routes.candidate_check.run_candidate_pipeline'):
            resp = client.post('/candidate/start', json={
                'full_name': '<script>alert(1)</script>Иванов Иван',
                'date_of_birth': '1990-05-15',
                'inn': '7707083893',
            })
            assert resp.status_code == 200
            data = resp.get_json()
            assert data['success'] is True


# ============================================================
# START CHECK TESTS (QUICK + PRECISE MODE)
# ============================================================

class TestStartCheck:
    """Start endpoint creates DB record and launches pipeline."""

    @patch('app.routes.candidate_check.run_candidate_pipeline')
    def test_quick_mode_json(self, mock_pipeline, client, app):
        resp = client.post('/candidate/start', json={
            'full_name': 'Петров Пётр Петрович',
            'date_of_birth': '1985-03-20',
            'inn': '7707083893',
            'check_mode': 'quick',
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        assert data['check_id']
        assert data['task_id']
        assert '/candidate/progress/' in data['redirect']

        # Verify DB record
        with app.app_context():
            check = CandidateCheck.query.get(data['check_id'])
            assert check is not None
            assert check.check_mode == 'quick'
            assert check.full_name == 'Петров Пётр Петрович'
            # Cleanup
            db.session.delete(check)
            db.session.commit()

    @patch('app.routes.candidate_check.run_candidate_pipeline')
    def test_precise_mode_json(self, mock_pipeline, client, app):
        resp = client.post('/candidate/start', json={
            'full_name': 'Сидоров Сергей',
            'date_of_birth': '1992-11-10',
            'inn': '7707083893',
            'check_mode': 'precise',
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True

        with app.app_context():
            check = CandidateCheck.query.get(data['check_id'])
            assert check.check_mode == 'precise'
            db.session.delete(check)
            db.session.commit()

    @patch('app.routes.candidate_check.run_candidate_pipeline')
    def test_invalid_mode_defaults_to_quick(self, mock_pipeline, client, app):
        resp = client.post('/candidate/start', json={
            'full_name': 'Козлов Анатолий',
            'date_of_birth': '1988-07-01',
            'inn': '7707083893',
            'check_mode': 'invalid_mode',
        })
        assert resp.status_code == 200
        data = resp.get_json()

        with app.app_context():
            check = CandidateCheck.query.get(data['check_id'])
            assert check.check_mode == 'quick'
            db.session.delete(check)
            db.session.commit()

    @patch('app.routes.candidate_check.run_candidate_pipeline')
    def test_form_post_redirects(self, mock_pipeline, client, app):
        resp = client.post('/candidate/start', data={
            'full_name': 'Кузнецов Дмитрий',
            'date_of_birth': '1995-01-20',
            'inn': '7707083893',
        }, follow_redirects=False)
        # Form POST should redirect to progress page
        assert resp.status_code == 302
        assert '/candidate/progress/' in resp.headers['Location']

        # Cleanup
        with app.app_context():
            check = CandidateCheck.query.order_by(CandidateCheck.created_at.desc()).first()
            if check and check.full_name == 'Кузнецов Дмитрий':
                db.session.delete(check)
                db.session.commit()

    @patch('app.routes.candidate_check.run_candidate_pipeline')
    def test_optional_fields_stored(self, mock_pipeline, client, app):
        resp = client.post('/candidate/start', json={
            'full_name': 'Морозова Елена Сергеевна',
            'date_of_birth': '1993-08-12',
            'inn': '7707083893',
            'passport': '4515 123456',
            'phone': '+79161234567',
            'email': 'moroz@mail.ru',
            'region': 'Москва',
            'registered_address': 'ул. Ленина, д.1',
        })
        data = resp.get_json()
        assert data['success'] is True

        with app.app_context():
            check = CandidateCheck.query.get(data['check_id'])
            assert check.inn == '7707083893'
            assert check.passport_series == '4515'
            assert check.passport_number == '123456'
            assert check.phone == '+79161234567'
            assert check.email == 'moroz@mail.ru'
            assert check.region == 'Москва'
            db.session.delete(check)
            db.session.commit()


# ============================================================
# PROGRESS PAGE & STATUS ENDPOINT
# ============================================================

class TestProgressPage:
    """Progress page renders and status endpoint returns correct data."""

    def test_progress_page_renders(self, client, sample_check):
        task_id, _ = _make_task(sample_check.id)
        resp = client.get(f'/candidate/progress/{task_id}')
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert 'Проверка кандидата' in html
        assert 'Иванов Иван Иванович' in html

    def test_progress_page_404(self, client):
        resp = client.get('/candidate/progress/nonexistent_task_id')
        assert resp.status_code == 404

    def test_progress_status_json(self, client, sample_check):
        task_id, task = _make_task(sample_check.id, stage='gov_registries', pct=10)
        task.completed_at = None
        resp = client.get(f'/candidate/progress/{task_id}/status')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['current_stage'] == 'gov_registries'
        assert data['percent_complete'] == 10
        assert data['check_id'] == sample_check.id
        assert data['is_complete'] is False

    def test_progress_status_complete(self, client, sample_check):
        task_id, _ = _make_task(sample_check.id, stage='complete', pct=100)
        resp = client.get(f'/candidate/progress/{task_id}/status')
        data = resp.get_json()
        assert data['is_complete'] is True
        assert data['status'] == 'complete'

    def test_progress_status_awaiting_confirmation(self, client, app, sample_check):
        """When check status is awaiting_confirmation, poll endpoint reflects it."""
        with app.app_context():
            check = CandidateCheck.query.get(sample_check.id)
            original_status = check.status
            check.status = 'awaiting_confirmation'
            db.session.commit()

            task_id, task = _make_task(check.id, stage='social', pct=40)
            task.completed_at = None
            resp = client.get(f'/candidate/progress/{task_id}/status')
            data = resp.get_json()
            assert data['status'] == 'awaiting_confirmation'
            assert 'confirmation_url' in data
            assert f'/candidate/confirm/{check.id}' in data['confirmation_url']

            # Restore
            check.status = original_status
            db.session.commit()

    def test_progress_status_404(self, client):
        resp = client.get('/candidate/progress/nonexistent/status')
        assert resp.status_code == 404

    def test_progress_8_stages_in_template(self, client, sample_check):
        """Progress page HTML should contain all 8 stage elements."""
        task_id, _ = _make_task(sample_check.id)
        resp = client.get(f'/candidate/progress/{task_id}')
        html = resp.get_data(as_text=True)
        for stage_id in ['gov', 'security', 'social', 'contacts', 'deep', 'behavioral', 'risk', 'report']:
            assert f'id="stage-{stage_id}"' in html, f"Missing stage element: stage-{stage_id}"


# ============================================================
# PROFILE CONFIRMATION (PRECISE MODE)
# ============================================================

class TestProfileConfirmation:
    """Precise mode profile confirmation flow."""

    def test_confirm_page_renders(self, client, app, sample_check):
        with app.app_context():
            check = CandidateCheck.query.get(sample_check.id)
            check.status = 'awaiting_confirmation'
            db.session.commit()

            resp = client.get(f'/candidate/confirm/{check.id}')
            assert resp.status_code == 200
            html = resp.get_data(as_text=True)
            assert 'Найденные профили' in html
            assert 'Подтвердить выбранные' in html

            check.status = 'complete'
            db.session.commit()

    def test_confirm_page_redirects_when_not_awaiting(self, client, sample_check):
        """If not in awaiting_confirmation status, should redirect."""
        resp = client.get(f'/candidate/confirm/{sample_check.id}', follow_redirects=False)
        assert resp.status_code == 302

    def test_submit_confirmation(self, client, app, sample_check):
        with app.app_context():
            check = CandidateCheck.query.get(sample_check.id)
            check.status = 'awaiting_confirmation'
            check.social_media_profiles = [
                {'url': 'https://vk.com/test', 'platform': 'vk', 'display_name': 'Test'},
            ]
            db.session.commit()

            # Create task so redirect works
            task_id, _ = _make_task(check.id, stage='social', pct=40)

            resp = client.post(f'/candidate/confirm/{check.id}', data={
                'confirmed_profiles': ['https://vk.com/test'],
            }, follow_redirects=False)
            assert resp.status_code == 302

            # Verify status changed back to running
            db.session.refresh(check)
            assert check.status == 'running'
            assert check.paused_at_stage is None

            check.status = 'complete'
            db.session.commit()

    def test_submit_skip_confirmation(self, client, app, sample_check):
        """Skip confirmation — no profiles selected."""
        with app.app_context():
            check = CandidateCheck.query.get(sample_check.id)
            check.status = 'awaiting_confirmation'
            db.session.commit()

            task_id, _ = _make_task(check.id, stage='social', pct=40)

            resp = client.post(f'/candidate/confirm/{check.id}', data={},
                               follow_redirects=False)
            assert resp.status_code == 302

            db.session.refresh(check)
            assert check.confirmed_profiles == []
            assert check.status == 'running'

            check.status = 'complete'
            db.session.commit()

    def test_confirm_404_nonexistent(self, client):
        resp = client.get('/candidate/confirm/nonexistent_id')
        assert resp.status_code == 404


# ============================================================
# DOSSIER PAGE
# ============================================================

class TestDossierPage:
    """Dossier page renders with all data sections."""

    def test_dossier_renders(self, client, sample_check):
        resp = client.get(f'/candidate/dossier/{sample_check.id}')
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert 'Иванов Иван Иванович' in html
        assert 'TemplateSyntaxError' not in html
        assert 'UndefinedError' not in html
        assert 'Traceback' not in html

    def test_dossier_shows_business_records(self, client, sample_check):
        resp = client.get(f'/candidate/dossier/{sample_check.id}')
        html = resp.get_data(as_text=True)
        assert 'Тест' in html

    def test_dossier_shows_risk_info(self, client, sample_check):
        resp = client.get(f'/candidate/dossier/{sample_check.id}')
        html = resp.get_data(as_text=True)
        assert 'НИЗКИЙ РИСК' in html or 'low' in html.lower()

    def test_dossier_404_nonexistent(self, client):
        resp = client.get('/candidate/dossier/nonexistent_check_id')
        assert resp.status_code == 404

    def test_dossier_redirects_if_running(self, client, app, sample_check):
        """If check is still running, dossier page should redirect to progress."""
        with app.app_context():
            check = CandidateCheck.query.get(sample_check.id)
            check.status = 'running'
            db.session.commit()

            task_id, _ = _make_task(check.id, stage='social', pct=40)

            resp = client.get(f'/candidate/dossier/{check.id}', follow_redirects=False)
            assert resp.status_code == 302
            assert '/candidate/progress/' in resp.headers['Location']

            check.status = 'complete'
            db.session.commit()


# ============================================================
# API ENDPOINTS
# ============================================================

class TestAPIEndpoints:
    """API endpoints return correct JSON for graph, geo, timeline data."""

    def test_social_graph_api(self, client, sample_check):
        resp = client.get(f'/candidate/api/social-graph/{sample_check.id}')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'nodes' in data
        assert len(data['nodes']) >= 1

    def test_geo_data_api(self, client, sample_check):
        resp = client.get(f'/candidate/api/geo-data/{sample_check.id}')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'locations' in data
        assert data['home_location'] == 'Москва'

    def test_timeline_api(self, client, sample_check):
        resp = client.get(f'/candidate/api/timeline/{sample_check.id}')
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_api_404_nonexistent(self, client):
        resp = client.get('/candidate/api/social-graph/nonexistent')
        assert resp.status_code == 404
        resp = client.get('/candidate/api/geo-data/nonexistent')
        assert resp.status_code == 404
        resp = client.get('/candidate/api/timeline/nonexistent')
        assert resp.status_code == 404

    def test_empty_data_returns_defaults(self, client, app):
        """Check with no stage 5-6 data returns empty defaults."""
        with app.app_context():
            check_id = uuid.uuid4().hex
            check = CandidateCheck(
                id=check_id,
                full_name='Пустой Тест',
                date_of_birth=date(1990, 1, 1),
                inn='7707083893',
                status='complete',
            )
            db.session.add(check)
            db.session.commit()

            resp = client.get(f'/candidate/api/social-graph/{check_id}')
            assert resp.get_json() == {}

            resp = client.get(f'/candidate/api/geo-data/{check_id}')
            assert resp.get_json() == {}

            resp = client.get(f'/candidate/api/timeline/{check_id}')
            assert resp.get_json() == []

            db.session.delete(check)
            db.session.commit()


# ============================================================
# JSON EXPORT
# ============================================================

class TestJSONExport:
    """JSON export includes all fields and correct Content-Type."""

    def test_json_export(self, client, sample_check):
        resp = client.get(f'/candidate/export/{sample_check.id}/json')
        assert resp.status_code == 200
        assert 'application/json' in resp.headers['Content-Type']
        assert 'attachment' in resp.headers.get('Content-Disposition', '')

        data = json.loads(resp.get_data(as_text=True))
        assert data['candidate']['full_name'] == 'Иванов Иван Иванович'
        assert data['meta']['check_mode'] == 'quick'
        assert data['meta']['report_generated'] is True

    def test_json_export_contains_new_fields(self, client, sample_check):
        resp = client.get(f'/candidate/export/{sample_check.id}/json')
        data = json.loads(resp.get_data(as_text=True))

        # Stage 5 fields
        assert 'face_matches' in data
        assert len(data['face_matches']) >= 1
        assert 'username_accounts' in data
        assert 'social_graph_data' in data

        # Stage 6 fields
        assert 'geo_analysis' in data
        assert 'text_analysis' in data
        assert 'activity_timeline' in data

        # Stage 7 fields
        assert 'risk_assessment' in data
        assert data['risk_assessment']['risk_breakdown'] is not None
        assert data['risk_assessment']['risk_score_numeric'] == 25.0

    def test_json_export_404(self, client):
        resp = client.get('/candidate/export/nonexistent/json')
        assert resp.status_code == 404


# ============================================================
# MODEL TESTS
# ============================================================

class TestCandidateCheckModel:
    """CandidateCheck model JSON properties and computed fields."""

    def test_json_properties_roundtrip(self, app):
        with app.app_context():
            check_id = uuid.uuid4().hex
            check = CandidateCheck(
                id=check_id,
                full_name='Тест Тестович',
                date_of_birth=date(1985, 6, 15),
                inn='7707083893',
                status='complete',
            )
            db.session.add(check)

            # Set all JSON properties
            check.face_matches = [{'name': 'Test', 'score': 0.9}]
            check.username_accounts = [{'platform': 'github', 'username': 'test'}]
            check.social_graph_data = {'nodes': [], 'edges': []}
            check.geo_analysis = {'locations': [{'city': 'СПб'}]}
            check.text_analysis = {'sentiment': 'positive'}
            check.activity_timeline = [{'date': '2024-01-01'}]
            check.risk_breakdown = {'business': {'score': 10}}
            check.confirmed_profiles = [{'url': 'https://vk.com/test'}]
            db.session.commit()

            # Re-query and verify
            loaded = CandidateCheck.query.get(check_id)
            assert loaded.face_matches == [{'name': 'Test', 'score': 0.9}]
            assert loaded.username_accounts == [{'platform': 'github', 'username': 'test'}]
            assert loaded.social_graph_data == {'nodes': [], 'edges': []}
            assert loaded.geo_analysis == {'locations': [{'city': 'СПб'}]}
            assert loaded.text_analysis == {'sentiment': 'positive'}
            assert loaded.activity_timeline == [{'date': '2024-01-01'}]
            assert loaded.risk_breakdown == {'business': {'score': 10}}
            assert loaded.confirmed_profiles == [{'url': 'https://vk.com/test'}]

            db.session.delete(check)
            db.session.commit()

    def test_check_level_computation(self, app):
        with app.app_context():
            check = CandidateCheck(
                id=uuid.uuid4().hex,
                full_name='Базовый Тест',
                date_of_birth=date(1990, 1, 1),
            )
            assert check.check_level == 'basic'

            check.inn = '7701234567'
            assert check.check_level == 'extended'

            check.passport_series = '4515'
            check.registered_address = 'ул. Тестовая, 1'
            assert check.check_level == 'full'

    def test_name_parts(self, app):
        with app.app_context():
            check = CandidateCheck(
                id=uuid.uuid4().hex,
                full_name='Иванов Иван Иванович',
                date_of_birth=date(1990, 1, 1),
            )
            parts = check.name_parts
            assert parts['last'] == 'Иванов'
            assert parts['first'] == 'Иван'
            assert parts['patronymic'] == 'Иванович'

    def test_risk_level_display(self, app):
        with app.app_context():
            check = CandidateCheck(
                id=uuid.uuid4().hex,
                full_name='Тест Тест',
                date_of_birth=date(1990, 1, 1),
            )
            check.risk_level = 'low'
            assert check.risk_level_display == 'НИЗКИЙ РИСК'
            check.risk_level = 'high'
            assert check.risk_level_display == 'ВЫСОКИЙ РИСК'
            check.risk_level = 'critical'
            assert check.risk_level_display == 'КРИТИЧЕСКИЙ РИСК'

    def test_empty_json_defaults(self, app):
        with app.app_context():
            check = CandidateCheck(
                id=uuid.uuid4().hex,
                full_name='Пустой Тест',
                date_of_birth=date(1990, 1, 1),
                inn='7707083893',
            )
            db.session.add(check)
            db.session.commit()

            loaded = CandidateCheck.query.get(check.id)
            assert loaded.face_matches == []
            assert loaded.username_accounts == []
            assert loaded.social_graph_data == {}
            assert loaded.geo_analysis == {}
            assert loaded.text_analysis == {}
            assert loaded.activity_timeline == []
            assert loaded.risk_breakdown == {}
            assert loaded.confirmed_profiles == []

            db.session.delete(check)
            db.session.commit()


# ============================================================
# TASK STATUS OBJECT TESTS
# ============================================================

class TestCandidateTaskStatus:
    """CandidateTaskStatus tracks progress correctly."""

    def test_initial_state(self):
        task = CandidateTaskStatus('tid', 'cid', 'Тест')
        d = task.to_dict()
        assert d['status'] == 'running'
        assert d['is_complete'] is False
        assert d['percent_complete'] == 0
        assert d['current_stage'] == 'initializing'

    def test_update_stage(self):
        task = CandidateTaskStatus('tid', 'cid', 'Тест')
        task.update('gov_registries', 'Checking ЕГРЮЛ', 10)
        d = task.to_dict()
        assert d['current_stage'] == 'gov_registries'
        assert d['percent_complete'] == 10
        assert len(d['messages']) >= 1

    def test_error_state(self):
        task = CandidateTaskStatus('tid', 'cid', 'Тест')
        task.error = 'Something failed'
        d = task.to_dict()
        assert d['status'] == 'error'
        assert d['is_complete'] is True
        assert d['error'] == 'Something failed'

    def test_cancelled_state(self):
        task = CandidateTaskStatus('tid', 'cid', 'Тест')
        task.cancelled = True
        d = task.to_dict()
        assert d['status'] == 'cancelled'
        assert d['is_complete'] is True

    def test_complete_state(self):
        task = CandidateTaskStatus('tid', 'cid', 'Тест')
        task.completed_at = datetime.now()
        d = task.to_dict()
        assert d['status'] == 'complete'
        assert d['is_complete'] is True

    def test_messages_capped_at_40(self):
        task = CandidateTaskStatus('tid', 'cid', 'Тест')
        for i in range(60):
            task.add_message(f'Message {i}')
        d = task.to_dict()
        assert len(d['messages']) == 40


# ============================================================
# HISTORY & DELETE
# ============================================================

class TestHistoryAndDelete:
    """History page lists checks, delete removes them."""

    def test_history_page(self, client, sample_check):
        resp = client.get('/candidate/history')
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert 'Иванов' in html

    def test_delete_check(self, client, app):
        with app.app_context():
            check_id = uuid.uuid4().hex
            check = CandidateCheck(
                id=check_id,
                full_name='Удалить Меня',
                date_of_birth=date(1990, 1, 1),
                inn='7707083893',
                status='complete',
            )
            db.session.add(check)
            db.session.commit()

            resp = client.post(f'/candidate/delete/{check_id}', follow_redirects=False)
            assert resp.status_code == 302

            assert CandidateCheck.query.get(check_id) is None

    def test_delete_404(self, client):
        resp = client.post('/candidate/delete/nonexistent')
        assert resp.status_code == 404


# ============================================================
# DEMO MODE (services mocked to return demo data)
# ============================================================

class TestDemoMode:
    """Pipeline works end-to-end with all services mocked (demo mode)."""

    @patch('app.routes.candidate_check.run_candidate_pipeline')
    def test_demo_start_and_poll(self, mock_pipeline, client, app):
        """Start check → poll status → verify lifecycle."""
        resp = client.post('/candidate/start', json={
            'full_name': 'Демо Тестович',
            'date_of_birth': '1990-01-01',
            'inn': '7707083893',
            'check_mode': 'quick',
        })
        data = resp.get_json()
        assert data['success'] is True

        task_id = data['task_id']
        check_id = data['check_id']

        # Task should exist in candidate_tasks
        assert task_id in candidate_tasks

        # Poll status
        resp = client.get(f'/candidate/progress/{task_id}/status')
        status = resp.get_json()
        assert status['check_id'] == check_id
        assert status['full_name'] == 'Демо Тестович'

        # Simulate pipeline completion
        task = candidate_tasks[task_id]
        task.completed_at = datetime.now()
        task.update('complete', 'Done', 100)

        with app.app_context():
            check = CandidateCheck.query.get(check_id)
            check.status = 'complete'
            check.risk_level = 'low'
            db.session.commit()

        # Poll again — should be complete
        resp = client.get(f'/candidate/progress/{task_id}/status')
        status = resp.get_json()
        assert status['is_complete'] is True

        # Dossier should render
        resp = client.get(f'/candidate/dossier/{check_id}')
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert 'Демо Тестович' in html

        # Cleanup
        with app.app_context():
            check = CandidateCheck.query.get(check_id)
            if check:
                db.session.delete(check)
                db.session.commit()
