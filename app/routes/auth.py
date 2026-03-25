"""
Authentication routes for IBP.
Simple password-only auth gate.
"""

import bcrypt
import os
import logging
import datetime
from functools import wraps
from urllib.parse import urlparse
from flask import (
    Blueprint, request, render_template, redirect,
    url_for, session, flash, current_app, jsonify
)
import requests as req

from app import limiter

logger = logging.getLogger('ibp.auth')

auth_bp = Blueprint('auth', __name__)


# Russian-speaking country codes
_RU_COUNTRIES = frozenset((
    'RU', 'BY', 'KZ', 'UA', 'UZ', 'KG', 'TJ', 'TM', 'AZ', 'AM', 'GE', 'MD',
))


def detect_language():
    """Detect user language by IP. Returns 'ru' or 'en'."""
    # Manual override in session takes priority
    if session.get('lang') in ('ru', 'en'):
        return session['lang']

    try:
        ip = request.headers.get('X-Forwarded-For',
             request.headers.get('X-Real-IP',
             request.remote_addr)) or ''
        ip = ip.split(',')[0].strip()

        # Private/localhost → fall back to Accept-Language
        if ip in ('127.0.0.1', 'localhost', '::1') or \
           ip.startswith('192.168.') or \
           ip.startswith('10.') or \
           ip.startswith('172.'):
            lang_header = request.headers.get('Accept-Language', '')
            return 'ru' if 'ru' in lang_header.lower() else 'en'

        r = req.get(
            f'http://ip-api.com/json/{ip}',
            params={'fields': 'countryCode'},
            timeout=2,
        )
        if r.status_code == 200:
            country = r.json().get('countryCode', '')
            if country in _RU_COUNTRIES:
                return 'ru'
            return 'en'
    except Exception:
        pass

    # Final fallback: Accept-Language header
    lang_header = request.headers.get('Accept-Language', '')
    return 'ru' if 'ru' in lang_header.lower() else 'en'


_cached_password_hash = None
_cached_password_source = None


def get_password_hash():
    """Get the password hash from environment. Cached to avoid re-hashing on every request."""
    global _cached_password_hash, _cached_password_source

    pw_hash = os.environ.get('IBP_PASSWORD_HASH', '').strip()
    if pw_hash:
        return pw_hash

    plain = os.environ.get('IBP_PASSWORD', '').strip()
    if plain:
        # Cache the hash so we don't call bcrypt.gensalt() on every login attempt
        if _cached_password_hash and _cached_password_source == plain:
            return _cached_password_hash
        _cached_password_hash = bcrypt.hashpw(plain.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        _cached_password_source = plain
        return _cached_password_hash

    return None


def is_auth_enabled():
    """Check if authentication is configured."""
    return bool(
        os.environ.get('IBP_PASSWORD_HASH', '').strip() or
        os.environ.get('IBP_PASSWORD', '').strip()
    )


def login_required(f):
    """Decorator to require authentication on routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_auth_enabled():
            return f(*args, **kwargs)

        if not session.get('authenticated'):
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'error': 'Требуется авторизация', 'redirect': '/login'}), 401
            session['next_url'] = request.path
            return redirect(url_for('auth.login'))

        return f(*args, **kwargs)
    return decorated_function


@auth_bp.route('/set-lang/<lang>')
def set_lang(lang):
    """Manual language override."""
    if lang in ('ru', 'en'):
        session['lang'] = lang
        session.modified = True
        session.permanent = True
    return redirect(url_for('auth.login'))


@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def login():
    """Login page."""
    if not is_auth_enabled():
        return redirect(url_for('main.dashboard'))

    if session.get('authenticated'):
        return redirect(url_for('main.dashboard'))

    lang = detect_language()

    error = None
    if request.method == 'POST':
        password = request.form.get('password', '')
        remember = request.form.get('remember', False)

        pw_hash = get_password_hash()
        if pw_hash and bcrypt.checkpw(password.encode('utf-8'), pw_hash.encode('utf-8')):
            # Preserve next_url and lang before clearing session (prevents session fixation)
            saved_next_url = session.get('next_url')
            saved_lang = session.get('lang')
            session.clear()
            session['authenticated'] = True
            session['last_active'] = datetime.datetime.utcnow().isoformat()
            session.permanent = True
            if saved_lang:
                session['lang'] = saved_lang

            if remember:
                timeout = int(os.environ.get('IBP_SESSION_REMEMBER', 2592000))
            else:
                timeout = int(os.environ.get('IBP_SESSION_TIMEOUT', 3600))

            current_app.permanent_session_lifetime = datetime.timedelta(seconds=timeout)

            logger.info("User authenticated successfully")

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
            logger.warning(f"Failed login attempt from {request.remote_addr}")

    return render_template('login.html', error=error, lang=lang)


@auth_bp.route('/logout')
def logout():
    """Logout and clear session."""
    session.clear()
    return redirect(url_for('auth.login'))
