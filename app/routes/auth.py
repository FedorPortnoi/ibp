"""
Authentication routes for IBP.
Multi-user: username + password, open registration, single admin.
"""

import os
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

logger = logging.getLogger('ibp.auth')

auth_bp = Blueprint('auth', __name__)


# Russian-speaking country codes
_RU_COUNTRIES = frozenset((
    'RU', 'BY', 'KZ', 'UA', 'UZ', 'KG', 'TJ', 'TM', 'AZ', 'AM', 'GE', 'MD',
))


def detect_language():
    """Auto-detect preferred language from session, geo-IP, or Accept-Language."""
    saved = session.get('lang')
    if saved in ('ru', 'en'):
        return saved

    # Geo-IP: try ip-api.com (free, no key)
    try:
        ip = request.remote_addr
        if ip and ip not in ('127.0.0.1', '::1'):
            resp = req.get(f'http://ip-api.com/json/{ip}?fields=countryCode', timeout=1.5)
            if resp.ok:
                cc = resp.json().get('countryCode', '')
                if cc in _RU_COUNTRIES:
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
    return User.query.get(user_id)


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
        user = get_current_user()
        if not user or not user.is_admin:
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
        return redirect(url_for('candidate.new_check'))

    lang = detect_language()

    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        remember = request.form.get('remember', False)

        from app.models.user import User
        user = User.query.filter_by(username=username, is_active=True).first()

        if user and user.check_password(password):
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

            next_url = saved_next_url
            # Validate next_url is a safe relative path (prevent open redirect)
            if next_url:
                parsed = urlparse(next_url)
                if parsed.netloc or parsed.scheme:
                    next_url = None
                elif next_url.startswith('//'):
                    next_url = None
            return redirect(next_url or url_for('candidate.new_check'))
        else:
            error = 'wrong_password'
            logger.warning(f"Failed login for '{username}' from {request.remote_addr}")

    return render_template('login.html', error=error, lang=lang, mode='login')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """Registration disabled — redirect to login."""
    return redirect(url_for('auth.login'))


@auth_bp.route('/logout')
def logout():
    """Logout and clear session."""
    session.clear()
    return redirect(url_for('auth.login'))
