"""Tests for self-service registration."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault('SECRET_KEY', 'test-secret-key')


@pytest.fixture
def app():
    from app import create_app, db
    from app.models import AuditLog, CandidateCheck, ChatMessage, Subscription, User  # noqa: F401

    application = create_app('testing')
    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def test_get_register_renders_registration_mode(client):
    resp = client.get('/register')

    assert resp.status_code == 200
    assert b'action="/register"' in resp.data
    assert b'name="confirm"' in resp.data
    assert b'data-mode="register"' in resp.data


def test_register_creates_regular_user_subscription_and_session(app, client):
    resp = client.post(
        '/register',
        data={
            'username': 'newuser',
            'password': 'secret123',
            'confirm': 'secret123',
            'role': 'admin',
            'is_admin': 'true',
        },
        follow_redirects=False,
    )

    assert resp.status_code == 302
    assert '/candidate/new' in resp.headers['Location']

    with app.app_context():
        from app.models.audit_log import AuditLog
        from app.models.subscription import Subscription
        from app.models.user import User

        user = User.query.filter_by(username='newuser').one()
        assert user.role == 'user'
        assert user.check_password('secret123')
        assert Subscription.query.filter_by(user_id=user.id, status='inactive').one()
        assert AuditLog.query.filter_by(action='auth.register', user_id=user.id).one()

    with client.session_transaction() as sess:
        assert sess['username'] == 'newuser'
        assert sess['role'] == 'user'


def test_register_rejects_duplicate_username(app, client):
    data = {
        'username': 'duplicate',
        'password': 'secret123',
        'confirm': 'secret123',
    }

    assert client.post('/register', data=data).status_code == 302
    client.get('/logout')
    resp = client.post('/register', data=data)

    assert resp.status_code == 400
    assert b'data-mode="register"' in resp.data

    with app.app_context():
        from app.models.user import User

        assert User.query.filter_by(username='duplicate').count() == 1


def test_register_rejects_password_mismatch(app, client):
    resp = client.post(
        '/register',
        data={
            'username': 'mismatch',
            'password': 'secret123',
            'confirm': 'different',
        },
    )

    assert resp.status_code == 400

    with app.app_context():
        from app.models.user import User

        assert User.query.filter_by(username='mismatch').count() == 0
