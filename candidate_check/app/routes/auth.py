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

from app import limiter

logger = logging.getLogger('ibp.auth')

auth_bp = Blueprint('auth', __name__)


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


@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def login():
    """Login page."""
    if not is_auth_enabled():
        return redirect(url_for('main.dashboard'))

    if session.get('authenticated'):
        return redirect(url_for('main.dashboard'))

    error = None
    if request.method == 'POST':
        password = request.form.get('password', '')
        remember = request.form.get('remember', False)

        pw_hash = get_password_hash()
        if pw_hash and bcrypt.checkpw(password.encode('utf-8'), pw_hash.encode('utf-8')):
            # Preserve next_url before clearing session (prevents session fixation)
            saved_next_url = session.get('next_url')
            session.clear()
            session['authenticated'] = True
            session['last_active'] = datetime.datetime.utcnow().isoformat()
            session.permanent = True

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
            return redirect(next_url or url_for('phase1.new_investigation'))
        else:
            error = 'Неверный пароль'
            logger.warning(f"Failed login attempt from {request.remote_addr}")

    return render_template('login.html', error=error)


@auth_bp.route('/logout')
def logout():
    """Logout and clear session."""
    session.clear()
    return redirect(url_for('auth.login'))
