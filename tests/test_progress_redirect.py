"""Tests for progress page immediate-redirect behavior.

Verifies that GET /candidate/progress/<task_id>:
1. Redirects (302) to /candidate/dossier/<check_id> when task is already complete
2. Renders 200 progress page when task is still running
3. Returns 404 for a missing task_id

A logged-in admin session is required because of the global before_request
auth check (app/__init__.py).
"""

import sys
import os
import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest


@pytest.fixture(scope='module')
def app():
    from dotenv import load_dotenv
    load_dotenv()
    from app import create_app
    application = create_app('testing')

    with application.app_context():
        from app import db
        from app.models.user import User
        db.create_all()
        user = User.query.get(1)
        if not user:
            user = User(id=1, username='testadmin', role='admin')
            user.set_password('test')
            db.session.add(user)
            db.session.commit()

    yield application


@pytest.fixture
def client(app):
    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess['user_id'] = 1
            sess['username'] = 'testadmin'
            sess['role'] = 'admin'
            sess['last_active'] = datetime.datetime.now(
                datetime.timezone.utc
            ).isoformat()
        yield c


def _make_check(app, check_id):
    """Create a minimal CandidateCheck row owned by user 1."""
    from app import db
    from app.models.candidate_check import CandidateCheck
    with app.app_context():
        existing = CandidateCheck.query.get(check_id)
        if existing:
            return
        check = CandidateCheck(
            id=check_id,
            user_id=1,
            full_name='Тест Тестов',
            date_of_birth=datetime.date(1990, 1, 1),
            inn='500100732259',
            status='running',
        )
        db.session.add(check)
        db.session.commit()


def test_progress_page_completed_task_redirects(app, client):
    """Если task is_complete=True — progress page редиректит на dossier."""
    from app.services.candidate.pipeline import candidate_tasks, CandidateTaskStatus, _tasks_lock

    _make_check(app, 'test_check_123')

    task = CandidateTaskStatus('test_task_redirect', 'test_check_123', 'Тест Тестов')
    task.is_complete = True
    task.completed_at = datetime.datetime.now()
    with _tasks_lock:
        candidate_tasks['test_task_redirect'] = task

    try:
        resp = client.get('/candidate/progress/test_task_redirect', follow_redirects=False)
        assert resp.status_code == 302
        assert 'dossier/test_check_123' in resp.headers['Location']
    finally:
        with _tasks_lock:
            candidate_tasks.pop('test_task_redirect', None)


def test_progress_page_running_task_shows_page(app, client):
    """Если task не завершён — показывает progress страницу."""
    from app.services.candidate.pipeline import candidate_tasks, CandidateTaskStatus, _tasks_lock

    _make_check(app, 'test_check_456')

    task = CandidateTaskStatus('test_task_running', 'test_check_456', 'Тест Тестов')
    # Leave is_complete=False (default from __init__)
    with _tasks_lock:
        candidate_tasks['test_task_running'] = task

    try:
        resp = client.get('/candidate/progress/test_task_running', follow_redirects=False)
        assert resp.status_code == 200
        # Progress page JS references TASK_ID
        assert b'TASK_ID' in resp.data
    finally:
        with _tasks_lock:
            candidate_tasks.pop('test_task_running', None)


def test_progress_page_missing_task_404(client):
    """Несуществующий task_id → 404."""
    resp = client.get('/candidate/progress/nonexistent_task_id_xyz', follow_redirects=False)
    assert resp.status_code == 404
