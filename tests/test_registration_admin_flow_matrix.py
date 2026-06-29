"""Matrix coverage for open registration and the Fedor/admin Users flow."""

import datetime as dt
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault('SECRET_KEY', 'test-secret-key')


@pytest.fixture(scope='module')
def app():
    import app.routes.auth as _auth_routes
    from app import create_app, db
    from app.models import AuditLog, CandidateCheck, ChatMessage, Subscription, User  # noqa: F401

    _orig_reg_open = _auth_routes._REGISTRATION_OPEN
    _auth_routes._REGISTRATION_OPEN = True
    application = create_app('testing')
    with application.app_context():
        db.create_all()
    yield application
    with application.app_context():
        db.session.remove()
        db.drop_all()
    _auth_routes._REGISTRATION_OPEN = _orig_reg_open


@pytest.fixture(autouse=True)
def reset_db(app):
    from app import db
    from app.models import AuditLog, CandidateCheck, ChatMessage, Subscription, User

    with app.app_context():
        db.session.remove()
        for model in (CandidateCheck, Subscription, ChatMessage, AuditLog, User):
            db.session.query(model).delete()
        db.session.commit()
    yield
    with app.app_context():
        db.session.remove()


@pytest.fixture
def client(app):
    return app.test_client()


def _text(resp):
    return resp.get_data(as_text=True)


def _register(client, username='newuser', password='secret123', confirm=None, extra=None):
    data = {
        'username': username,
        'password': password,
        'confirm': password if confirm is None else confirm,
    }
    if extra:
        data.update(extra)
    return client.post('/register', data=data, follow_redirects=False)


def _create_user(username, role='user', created_at=None):
    from app import db
    from app.models.user import User

    user = User(
        username=username,
        role=role,
        created_at=created_at or dt.datetime(2026, 5, 20, 9, 0),
    )
    user.set_password('secret123')
    db.session.add(user)
    db.session.flush()
    return user


def _create_check(user, check_id, full_name, created_at, status='complete',
                  risk_level='low', red_flag_count=0):
    from app import db
    from app.models.candidate_check import CandidateCheck

    check = CandidateCheck(
        id=check_id,
        user_id=user.id,
        full_name=full_name,
        date_of_birth=dt.date(1990, 1, 1),
        inn='500100732259',
        created_at=created_at,
        status=status,
        risk_level=risk_level,
        red_flag_count=red_flag_count,
    )
    db.session.add(check)
    return check


def _seed_admin_flow(app):
    from app import db

    with app.app_context():
        fedor = _create_user('Fedor', 'admin', dt.datetime(2026, 5, 20, 9, 0))
        alice = _create_user('alice', 'user', dt.datetime(2026, 5, 21, 9, 0))
        bob = _create_user('bob', 'user', dt.datetime(2026, 5, 22, 9, 0))
        charlie = _create_user('charlie', 'user', dt.datetime(2026, 5, 23, 9, 0))

        _create_check(
            alice, 'alice-old', 'Alice Old Candidate',
            dt.datetime(2026, 5, 26, 10, 0), 'complete', 'low', 0,
        )
        _create_check(
            alice, 'alice-new', 'Alice New Candidate',
            dt.datetime(2026, 5, 27, 11, 0), 'running', None, 1,
        )
        _create_check(
            bob, 'bob-high', 'Bob High Candidate',
            dt.datetime(2026, 5, 25, 12, 0), 'complete', 'high', 2,
        )
        db.session.commit()

        return {
            'Fedor': fedor.id,
            'alice': alice.id,
            'bob': bob.id,
            'charlie': charlie.id,
        }


def _login_as(client, app, username):
    from app.models.user import User

    with app.app_context():
        user = User.query.filter_by(username=username).one()
        user_id = user.id
        role = user.role

    with client.session_transaction() as sess:
        sess['user_id'] = user_id
        sess['username'] = username
        sess['role'] = role
        sess['last_active'] = dt.datetime.now(dt.timezone.utc).isoformat()


def _row_for(html, needle):
    for match in re.finditer(r'<tr\b.*?</tr>', html, re.S):
        row = match.group(0)
        if needle in row:
            return row
    raise AssertionError(f'No table row contains {needle!r}')


REGISTER_GET_FRAGMENTS = [
    'action="/register"',
    'data-mode="register"',
    'name="username"',
    'name="password"',
    'name="confirm"',
    'autocomplete="new-password"',
    'id="confirm-field"',
    'href="/login#auth"',
]


@pytest.mark.parametrize('fragment', REGISTER_GET_FRAGMENTS)
def test_register_get_renders_expected_contract(client, fragment):
    resp = client.get('/register')

    assert resp.status_code == 200
    assert fragment in _text(resp)


INVALID_REGISTRATION_PAYLOADS = [
    {'username': '', 'password': 'secret123', 'confirm': 'secret123'},
    {'username': 'ab', 'password': 'secret123', 'confirm': 'secret123'},
    {'username': '  ab  ', 'password': 'secret123', 'confirm': 'secret123'},
    {'username': 'validname', 'password': '', 'confirm': ''},
    {'username': 'validname', 'password': '1', 'confirm': '1'},
    {'username': 'validname', 'password': '12345', 'confirm': '12345'},
    {'username': 'validname', 'password': 'secret123', 'confirm': ''},
    {'username': 'validname', 'password': 'secret123', 'confirm': 'different'},
    {'username': 'validname', 'password': 'secret123', 'confirm': 'secret123 '},
    {'username': 'u' * 65, 'password': 'secret123', 'confirm': 'secret123'},
    {'username': '\t\n', 'password': 'secret123', 'confirm': 'secret123'},
    {'username': ' ok ', 'password': 'secret123', 'confirm': 'secret123'},
]


@pytest.mark.parametrize('payload', INVALID_REGISTRATION_PAYLOADS)
def test_register_rejects_invalid_payload_without_side_effects(app, client, payload):
    resp = client.post('/register', data=payload)

    assert resp.status_code == 400
    assert 'data-mode="register"' in _text(resp)
    with client.session_transaction() as sess:
        assert 'user_id' not in sess

    with app.app_context():
        from app.models.audit_log import AuditLog
        from app.models.subscription import Subscription
        from app.models.user import User

        assert User.query.count() == 0
        assert Subscription.query.count() == 0
        assert AuditLog.query.count() == 0


VALID_REGISTRATIONS = [
    ('alpha', 'alpha', 'secret123'),
    ('mixedCase', 'mixedCase', 'secret123'),
    ('under_score', 'under_score', 'secret123'),
    ('hyphen-user', 'hyphen-user', 'secret123'),
    ('dot.user', 'dot.user', 'secret123'),
    ('num123', 'num123', 'secret123'),
    ('  trimmed_user  ', 'trimmed_user', 'secret123'),
    ('u' * 64, 'u' * 64, 'secret123'),
    ('capsLOCK', 'capsLOCK', 'AnotherSecret9'),
    ('email_style@example.com', 'email_style@example.com', 'secret123'),
]


@pytest.mark.parametrize('submitted, expected, password', VALID_REGISTRATIONS)
def test_register_creates_regular_user_subscription_audit_and_session(
    app, client, submitted, expected, password
):
    resp = _register(client, submitted, password)

    assert resp.status_code == 302
    assert resp.headers['Location'].endswith('/dashboard')
    with client.session_transaction() as sess:
        assert sess['username'] == expected
        assert sess['role'] == 'user'
        assert sess['user_id']
        assert sess['last_active']

    with app.app_context():
        from app.models.audit_log import AuditLog
        from app.models.subscription import Subscription
        from app.models.user import User

        user = User.query.filter_by(username=expected).one()
        assert user.role == 'user'
        assert user.is_active is True
        assert user.password_hash != password
        assert user.check_password(password)

        sub = Subscription.query.filter_by(user_id=user.id).one()
        assert sub.status == 'inactive'

        audit = AuditLog.query.filter_by(action='auth.register', user_id=user.id).one()
        assert audit.outcome == 'success'
        assert audit.extra == {'username': expected}


ROLE_INJECTION_PAYLOADS = [
    {'role': 'admin'},
    {'role': 'admin', 'is_admin': 'true'},
    {'role': 'user', 'is_admin': 'true'},
    {'is_admin': '1'},
    {'admin': 'true'},
    {'permissions': 'admin'},
    {'user_id': '1'},
    {'subscription_status': 'active'},
    {'is_active': 'false'},
    {'role': 'admin\nuser', 'role[]': 'admin'},
]


@pytest.mark.parametrize('extra', ROLE_INJECTION_PAYLOADS)
def test_register_ignores_role_and_account_injection_fields(app, client, extra):
    resp = _register(client, 'injector', extra=extra)

    assert resp.status_code == 302
    with client.session_transaction() as sess:
        assert sess['username'] == 'injector'
        assert sess['role'] == 'user'

    with app.app_context():
        from app.models.subscription import Subscription
        from app.models.user import User

        user = User.query.filter_by(username='injector').one()
        assert user.role == 'user'
        assert user.is_admin is False
        assert user.is_active is True
        assert Subscription.query.filter_by(user_id=user.id, status='inactive').one()


FAILED_REGISTRATION_PAYLOADS = INVALID_REGISTRATION_PAYLOADS[:5]


@pytest.mark.parametrize('payload', FAILED_REGISTRATION_PAYLOADS)
def test_failed_register_never_starts_authenticated_session(client, payload):
    resp = client.post('/register', data=payload)

    assert resp.status_code == 400
    with client.session_transaction() as sess:
        assert 'user_id' not in sess
        assert 'role' not in sess
        assert 'username' not in sess


DUPLICATE_ATTEMPTS = [
    {'username': 'duplicate', 'password': 'secret123', 'confirm': 'secret123'},
    {'username': 'duplicate', 'password': 'newpass123', 'confirm': 'newpass123'},
    {'username': ' duplicate ', 'password': 'secret123', 'confirm': 'secret123'},
    {
        'username': 'duplicate',
        'password': 'secret123',
        'confirm': 'secret123',
        'role': 'admin',
    },
    {
        'username': 'duplicate',
        'password': 'secret123',
        'confirm': 'secret123',
        'is_admin': 'true',
    },
]


@pytest.mark.parametrize('second_payload', DUPLICATE_ATTEMPTS)
def test_duplicate_registration_keeps_original_account_only(app, client, second_payload):
    assert _register(client, 'duplicate').status_code == 302
    client.post('/logout')

    resp = client.post('/register', data=second_payload)

    assert resp.status_code == 400
    with app.app_context():
        from app.models.audit_log import AuditLog
        from app.models.subscription import Subscription
        from app.models.user import User

        user = User.query.filter_by(username='duplicate').one()
        assert user.role == 'user'
        assert User.query.count() == 1
        assert Subscription.query.filter_by(user_id=user.id).count() == 1
        assert AuditLog.query.filter_by(action='auth.register').count() == 1


@pytest.mark.parametrize('method,data', [
    ('get', None),
    ('post', {'username': 'ignored', 'password': 'secret123', 'confirm': 'secret123'}),
])
def test_logged_in_users_are_redirected_away_from_registration(app, client, method, data):
    _seed_admin_flow(app)
    _login_as(client, app, 'alice')

    resp = getattr(client, method)('/register', data=data, follow_redirects=False)

    assert resp.status_code == 302
    assert resp.headers['Location'].endswith('/dashboard')
    with app.app_context():
        from app.models.user import User

        assert User.query.filter_by(username='ignored').count() == 0


ADMIN_LIST_FRAGMENTS = [
    'Пользователи — СЛЕД',
    '<span class="text-accent">Пользователи</span>',
    'Выберите пользователя, чтобы просмотреть только его проверки.',
    'Новая проверка',
    '<th>Пользователь</th>',
    '<th>Роль</th>',
    '<th>Проверок</th>',
    '<th>Последняя проверка</th>',
    '<th>Зарегистрирован</th>',
    'role-admin',
    'role-user',
    'Fedor',
    'alice',
    'charlie',
]


@pytest.mark.parametrize('fragment', ADMIN_LIST_FRAGMENTS)
def test_admin_users_list_renders_expected_surface(app, client, fragment):
    _seed_admin_flow(app)
    _login_as(client, app, 'Fedor')

    resp = client.get('/admin/users/')

    assert resp.status_code == 200
    assert fragment in _text(resp)


ADMIN_LIST_COUNTS = [
    ('alice', '2'),
    ('bob', '1'),
    ('charlie', '0'),
]


@pytest.mark.parametrize('username, expected_count', ADMIN_LIST_COUNTS)
def test_admin_users_list_shows_per_user_investigation_counts(
    app, client, username, expected_count
):
    _seed_admin_flow(app)
    _login_as(client, app, 'Fedor')

    html = _text(client.get('/admin/users/'))
    row = _row_for(html, username)

    assert f'data-label="Проверок"' in row
    assert re.search(rf'>\s*{expected_count}\s*<', row)


SELECTED_USER_SCOPES = [
    ('alice', ['Alice New Candidate', 'Alice Old Candidate'], ['Bob High Candidate']),
    ('bob', ['Bob High Candidate'], ['Alice New Candidate', 'Alice Old Candidate']),
    ('charlie', ['Проверок пока нет'], ['Alice New Candidate', 'Bob High Candidate']),
]


@pytest.mark.parametrize('username, expected, absent', SELECTED_USER_SCOPES)
def test_admin_selected_user_page_is_scoped_to_that_user(app, client, username, expected, absent):
    ids = _seed_admin_flow(app)
    _login_as(client, app, 'Fedor')

    resp = client.get(f'/admin/users/{ids[username]}/investigations')
    html = _text(resp)

    assert resp.status_code == 200
    for fragment in expected:
        assert fragment in html
    for fragment in absent:
        assert fragment not in html


SELECTED_PAGE_FRAGMENTS = [
    ('alice', '&larr; Пользователи'),
    ('alice', 'Проверки — <span class="text-accent">alice</span>'),
    ('alice', 'Всего проверок: 2'),
    ('alice', 'Alice New Candidate'),
    ('alice', 'Alice Old Candidate'),
    ('alice', '/candidate/dossier/alice-new'),
    ('alice', '/candidate/dossier/alice-old'),
    ('alice', 'status-pill status-running'),
    ('alice', 'status-pill status-complete'),
    ('alice', 'risk-badge risk-low'),
    ('bob', 'risk-badge risk-high'),
    ('charlie', 'Всего проверок: 0'),
]


@pytest.mark.parametrize('username, fragment', SELECTED_PAGE_FRAGMENTS)
def test_admin_selected_user_page_renders_expected_details(app, client, username, fragment):
    ids = _seed_admin_flow(app)
    _login_as(client, app, 'Fedor')

    resp = client.get(f'/admin/users/{ids[username]}/investigations')

    assert resp.status_code == 200
    assert fragment in _text(resp)


@pytest.mark.parametrize('regular_user', ['alice', 'bob'])
@pytest.mark.parametrize('route_template', [
    '/admin/users/',
    '/admin/users/{alice}/investigations',
    '/admin/users/{bob}/investigations',
])
def test_regular_users_cannot_open_admin_users_routes(
    app, client, regular_user, route_template
):
    ids = _seed_admin_flow(app)
    _login_as(client, app, regular_user)

    resp = client.get(route_template.format(**ids))

    assert resp.status_code == 403


@pytest.mark.parametrize('route', [
    '/admin/users/',
    '/admin/users/1/investigations',
    '/candidate/history',
])
def test_anonymous_users_are_redirected_before_protected_feature_pages(client, route):
    resp = client.get(route, follow_redirects=False)

    assert resp.status_code == 302
    assert resp.headers['Location'].endswith('/login')


REGULAR_HISTORY_SCOPES = [
    ('alice', ['Alice New Candidate', 'Alice Old Candidate'], ['Bob High Candidate']),
    ('bob', ['Bob High Candidate'], ['Alice New Candidate', 'Alice Old Candidate']),
    ('charlie', [], ['Alice New Candidate', 'Alice Old Candidate', 'Bob High Candidate']),
]


@pytest.mark.parametrize('username, expected, absent', REGULAR_HISTORY_SCOPES)
def test_regular_history_keeps_existing_own_investigations_behavior(
    app, client, username, expected, absent
):
    _seed_admin_flow(app)
    _login_as(client, app, username)

    resp = client.get('/candidate/history')
    html = _text(resp)

    assert resp.status_code == 200
    assert '/admin/users/' not in html
    assert 'Users' not in html
    for fragment in expected:
        assert fragment in html
    for fragment in absent:
        assert fragment not in html


def test_admin_history_redirects_to_users_list_before_showing_investigations(app, client):
    _seed_admin_flow(app)
    _login_as(client, app, 'Fedor')

    resp = client.get('/candidate/history', follow_redirects=False)

    assert resp.status_code == 302
    assert resp.headers['Location'].endswith('/admin/users/')


NAV_VISIBILITY_CASES = [
    ('Fedor', '/admin/users/', True),
    ('Fedor', '/admin/users/{alice}/investigations', True),
    ('alice', '/candidate/history', False),
    ('bob', '/candidate/history', False),
]


@pytest.mark.parametrize('username, route_template, should_show_users', NAV_VISIBILITY_CASES)
def test_users_nav_item_visibility_matches_role(app, client, username, route_template, should_show_users):
    ids = _seed_admin_flow(app)
    _login_as(client, app, username)

    html = _text(client.get(route_template.format(**ids), follow_redirects=True))

    assert ('/admin/users/' in html) is should_show_users
    assert ('Пользователи' in html) is should_show_users


PERMISSION_CASES = [
    ('Fedor', 'alice-old', True),
    ('Fedor', 'bob-high', True),
    ('alice', 'alice-old', True),
    ('alice', 'bob-high', False),
    ('bob', 'alice-old', False),
    (None, 'alice-old', False),
]


@pytest.mark.parametrize('username, check_id, expected', PERMISSION_CASES)
def test_permission_helper_matches_admin_and_owner_rules(app, username, check_id, expected):
    _seed_admin_flow(app)

    with app.app_context():
        from app.models.candidate_check import CandidateCheck
        from app.models.user import User
        from app.permissions import can_access_check

        user = User.query.filter_by(username=username).one() if username else None
        check = CandidateCheck.query.get(check_id)

        assert can_access_check(user, check) is expected
