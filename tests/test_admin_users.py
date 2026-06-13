"""Tests for the admin-only Users investigation flow."""

import datetime
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


def _login_as(client, user):
    with client.session_transaction() as sess:
        sess['user_id'] = user.id
        sess['username'] = user.username
        sess['role'] = user.role
        sess['last_active'] = datetime.datetime.now(
            datetime.timezone.utc
        ).isoformat()


def _seed(app):
    from app import db
    from app.models.candidate_check import CandidateCheck
    from app.models.user import User

    with app.app_context():
        fedor = User(username='Fedor', role='admin')
        fedor.set_password('adminpass')
        alice = User(username='alice', role='user')
        alice.set_password('secret123')
        bob = User(username='bob', role='user')
        bob.set_password('secret123')
        db.session.add_all([fedor, alice, bob])
        db.session.flush()

        alice_check = CandidateCheck(
            id='alice-check',
            user_id=alice.id,
            full_name='Alice Candidate',
            date_of_birth=datetime.date(1990, 1, 1),
            inn='500100732259',
            status='complete',
            risk_level='low',
            red_flag_count=0,
        )
        bob_check = CandidateCheck(
            id='bob-check',
            user_id=bob.id,
            full_name='Bob Candidate',
            date_of_birth=datetime.date(1991, 1, 1),
            inn='500100732260',
            status='complete',
            risk_level='high',
            red_flag_count=2,
        )
        db.session.add_all([alice_check, bob_check])
        db.session.commit()

        return fedor.id, alice.id, bob.id


def _get_user(app, user_id):
    from app.models.user import User

    with app.app_context():
        return User.query.get(user_id)


def test_admin_sees_users_nav_and_user_list(app, client):
    fedor_id, alice_id, bob_id = _seed(app)
    _login_as(client, _get_user(app, fedor_id))

    resp = client.get('/admin/users/')

    assert resp.status_code == 200
    assert 'Пользователи'.encode() in resp.data
    assert b'alice' in resp.data
    assert b'bob' in resp.data
    assert f'/admin/users/{alice_id}/investigations'.encode() in resp.data
    assert f'/admin/users/{bob_id}/investigations'.encode() in resp.data


def test_regular_user_cannot_access_users_page(app, client):
    _fedor_id, alice_id, _bob_id = _seed(app)
    _login_as(client, _get_user(app, alice_id))

    resp = client.get('/admin/users/')

    assert resp.status_code == 403


def test_admin_user_investigation_page_is_scoped_to_selected_user(app, client):
    fedor_id, alice_id, _bob_id = _seed(app)
    _login_as(client, _get_user(app, fedor_id))

    resp = client.get(f'/admin/users/{alice_id}/investigations')

    assert resp.status_code == 200
    assert b'Alice Candidate' in resp.data
    assert b'Bob Candidate' not in resp.data
    assert b'/candidate/dossier/alice-check' in resp.data


def test_admin_history_redirects_to_users_first(app, client):
    fedor_id, _alice_id, _bob_id = _seed(app)
    _login_as(client, _get_user(app, fedor_id))

    resp = client.get('/candidate/history', follow_redirects=False)

    assert resp.status_code == 302
    assert '/admin/users/' in resp.headers['Location']


def test_regular_history_stays_regular_user_only(app, client):
    _fedor_id, alice_id, _bob_id = _seed(app)
    _login_as(client, _get_user(app, alice_id))

    resp = client.get('/candidate/history')

    assert resp.status_code == 200
    assert b'Alice Candidate' in resp.data
    assert b'Bob Candidate' not in resp.data
    assert b'Users' not in resp.data
