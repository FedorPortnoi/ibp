"""
Authentication routes for IBP.
Multi-user: username + password, open registration, admin/user roles.
"""

import os
import time as _time
import logging
import datetime
from functools import wraps
from urllib.parse import urlparse
from flask import (
    Blueprint, request, render_template, redirect,
    url_for, session, current_app, jsonify, abort
)
from sqlalchemy.exc import IntegrityError
import requests as req

from app import db, limiter
from app.market.russia import CIS_COUNTRY_CODES
from app.permissions import is_admin

logger = logging.getLogger('ibp.auth')

auth_bp = Blueprint('auth', __name__)

_REGISTRATION_OPEN = os.environ.get('IBP_REGISTRATION_OPEN', '').lower() in ('1', 'true', 'yes')

_geo_cache: dict = {}
_GEO_CACHE_TTL = 3600

# ---------------------------------------------------------------------------
# Per-username login lockout (defends against brute-force via IP rotation).
# IP-based rate limits (Flask-Limiter) can be bypassed by spoofing
# X-Forwarded-For.  Username-based lockout is immune to that vector.
# DB-backed so lockout is enforced across all workers.
# ---------------------------------------------------------------------------
_LOCKOUT_MAX_FAILURES = 5      # attempts within the window before lockout
_LOCKOUT_WINDOW_SECS  = 300    # rolling 5-minute window
_LOCKOUT_DURATION_SECS = 900   # 15-minute lockout


def _record_login_failure(username: str) -> None:
    from app import db
    from app.models.login_attempt import LoginAttempt
    try:
        db.session.add(LoginAttempt(username_lower=username.lower()))
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.warning(f"Could not record login failure for '{username}'")


def _clear_login_failures(username: str) -> None:
    from app import db
    from app.models.login_attempt import LoginAttempt
    import datetime as _dt
    try:
        cutoff = _dt.datetime.utcnow() - _dt.timedelta(seconds=_LOCKOUT_DURATION_SECS)
        LoginAttempt.query.filter(
            LoginAttempt.username_lower == username.lower(),
            LoginAttempt.attempted_at >= cutoff,
        ).delete()
        # Prune old records opportunistically
        old_cutoff = _dt.datetime.utcnow() - _dt.timedelta(seconds=_LOCKOUT_DURATION_SECS * 4)
        LoginAttempt.query.filter(LoginAttempt.attempted_at < old_cutoff).delete()
        db.session.commit()
    except Exception:
        db.session.rollback()


def _is_locked_out(username: str) -> bool:
    from app import db
    from app.models.login_attempt import LoginAttempt
    import datetime as _dt
    try:
        now = _dt.datetime.utcnow()
        window_start = now - _dt.timedelta(seconds=_LOCKOUT_WINDOW_SECS)
        recent = LoginAttempt.query.filter(
            LoginAttempt.username_lower == username.lower(),
            LoginAttempt.attempted_at >= window_start,
        ).count()
        if recent >= _LOCKOUT_MAX_FAILURES:
            latest = (
                LoginAttempt.query
                .filter(LoginAttempt.username_lower == username.lower())
                .order_by(LoginAttempt.attempted_at.desc())
                .first()
            )
            if latest:
                lockout_end = latest.attempted_at + _dt.timedelta(seconds=_LOCKOUT_DURATION_SECS)
                return now < lockout_end
    except Exception:
        logger.warning("Lockout DB check failed, defaulting to not locked out")
        return False
    return False


def detect_language():
    """Auto-detect preferred language from session, geo-IP, or Accept-Language."""
    saved = session.get('lang')
    if saved in ('ru', 'en'):
        return saved

    # Geo-IP: try ip-api.com (free, no key) — results cached per IP for _GEO_CACHE_TTL seconds
    try:
        ip = request.remote_addr
        if ip and ip not in ('127.0.0.1', '::1'):
            cached = _geo_cache.get(ip)
            if cached and (_time.time() - cached[1]) < _GEO_CACHE_TTL:
                cc = cached[0]
            else:
                resp = req.get(f'http://ip-api.com/json/{ip}?fields=countryCode', timeout=1.5)
                cc = resp.json().get('countryCode', '') if resp.ok else ''
                _geo_cache[ip] = (cc, _time.time())
                if len(_geo_cache) > 5000:
                    # Prune oldest half
                    sorted_keys = sorted(_geo_cache, key=lambda k: _geo_cache[k][1])
                    for k in sorted_keys[:2500]:
                        _geo_cache.pop(k, None)
            if cc in CIS_COUNTRY_CODES:
                return 'ru'
            return 'en'
    except Exception:
        pass

    # Final fallback: Accept-Language header
    lang_header = request.headers.get('Accept-Language', '')
    return 'ru' if 'ru' in lang_header.lower() else 'en'


# ── Helpers ──

def get_current_user():
    """Get the currently logged-in User object, or None."""
    user_id = session.get('user_id')
    if not user_id:
        return None
    from app.models.user import User
    return db.session.get(User, user_id)


def login_required(f):
    """Decorator to require authentication on routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('user_id'):
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'error': 'Требуется авторизация', 'redirect': '/login'}), 401
            session['next_url'] = request.path
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """Decorator to require admin role."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_admin(get_current_user()):
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


# ── Routes ──

@auth_bp.route('/set-lang/<lang>')
def set_lang(lang):
    """Manual language override."""
    if lang in ('ru', 'en'):
        session['lang'] = lang
        session.modified = True
        session.permanent = True
    return redirect(url_for('auth.login'))


@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute; 20 per hour", methods=["POST"])
def login():
    """Login page — username + password."""
    if session.get('user_id'):
        return redirect(url_for('main.dashboard'))

    lang = detect_language()

    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        remember = request.form.get('remember', False)

        # Per-username lockout — immune to IP-rotation bypass of Flask-Limiter.
        if _is_locked_out(username):
            logger.warning(f"Login blocked (lockout) for '{username}' from {request.remote_addr}")
            error = 'account_locked'
            return render_template('login.html', error=error, lang=lang, mode='login')

        from app.models.user import User
        user = User.query.filter_by(username=username, is_active=True).first()

        if user and user.check_password(password):
            _clear_login_failures(username)

            # Preserve next_url and lang before clearing session (prevents session fixation)
            saved_next_url = session.get('next_url')
            saved_lang = session.get('lang')
            session.clear()
            session['user_id'] = user.id
            session['username'] = user.username
            session['role'] = user.role
            session['last_active'] = datetime.datetime.utcnow().isoformat()
            session.permanent = True
            if saved_lang:
                session['lang'] = saved_lang

            if remember:
                timeout = int(os.environ.get('IBP_SESSION_REMEMBER', 2592000))
            else:
                timeout = int(os.environ.get('IBP_SESSION_TIMEOUT', 3600))

            current_app.permanent_session_lifetime = datetime.timedelta(seconds=timeout)

            logger.info(f"User '{user.username}' (role={user.role}) authenticated")
            from app import audit
            audit.log('auth.login', user_id=user.id, metadata={'username': user.username})

            next_url = saved_next_url
            # Validate next_url is a safe relative path (prevent open redirect)
            if next_url:
                parsed = urlparse(next_url)
                if parsed.netloc or parsed.scheme:
                    next_url = None
                elif next_url.startswith('//'):
                    next_url = None
            return redirect(next_url or url_for('main.dashboard'))
        else:
            _record_login_failure(username)
            error = 'wrong_password'
            logger.warning(f"Failed login for '{username}' from {request.remote_addr}")
            from app import audit
            audit.log('auth.login_failed', outcome='failure', metadata={'username': username})

    return render_template('login.html', error=error, lang=lang, mode='login')


@auth_bp.route('/register', methods=['GET', 'POST'])
@limiter.limit("5 per minute; 20 per hour", methods=["POST"])
def register():
    """Create a regular user account and sign in immediately."""
    if not _REGISTRATION_OPEN:
        lang = detect_language()
        return render_template('login.html', error='registration_closed', lang=lang, mode='register'), 403

    if session.get('user_id'):
        return redirect(url_for('main.dashboard'))

    lang = detect_language()

    if request.method == 'GET':
        return render_template('login.html', error=None, lang=lang, mode='register')

    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')
    confirm = request.form.get('confirm', '')

    def _render_error(error_code):
        return render_template(
            'login.html',
            error=error_code,
            lang=lang,
            mode='register',
            username=username,
        ), 400

    if len(username) < 3:
        return _render_error('username_short')
    if len(username) > 64:
        return _render_error('username_long')
    if len(password) < 6:
        return _render_error('password_short')
    if password != confirm:
        return _render_error('password_mismatch')

    from app.models.user import User
    from app.models.subscription import Subscription

    if User.query.filter_by(username=username).first():
        return _render_error('registration_error')

    user = User(username=username, role='user')
    user.set_password(password)
    db.session.add(user)

    try:
        db.session.flush()
        db.session.add(Subscription(user_id=user.id, status='inactive'))
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return _render_error('registration_error')

    session.clear()
    session['user_id'] = user.id
    session['username'] = user.username
    session['role'] = user.role
    session['last_active'] = datetime.datetime.utcnow().isoformat()
    session.permanent = True
    current_app.permanent_session_lifetime = datetime.timedelta(
        seconds=int(os.environ.get('IBP_SESSION_TIMEOUT', 3600))
    )

    logger.info(f"User '{user.username}' registered")
    from app import audit
    audit.log('auth.register', user_id=user.id, metadata={'username': user.username})

    return redirect(url_for('main.dashboard'))


@auth_bp.route('/logout', methods=['POST'])
def logout():
    """Logout and clear session."""
    session.clear()
    return redirect(url_for('auth.login'))
