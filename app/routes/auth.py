"""
Authentication routes for IBP.
Simple password-only auth gate.
"""

import bcrypt
import os
import logging
import datetime
from functools import wraps
from flask import (
    Blueprint, request, render_template, redirect,
    url_for, session, flash, current_app, jsonify
)

logger = logging.getLogger('ibp.auth')

auth_bp = Blueprint('auth', __name__)


def get_password_hash():
    """Get the password hash from environment."""
    pw_hash = os.environ.get('IBP_PASSWORD_HASH', '').strip()
    if pw_hash:
        return pw_hash

    plain = os.environ.get('IBP_PASSWORD', '').strip()
    if plain:
        return bcrypt.hashpw(plain.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

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
                return jsonify({'error': 'Authentication required', 'redirect': '/login'}), 401
            session['next_url'] = request.url
            return redirect(url_for('auth.login'))

        return f(*args, **kwargs)
    return decorated_function


@auth_bp.route('/login', methods=['GET', 'POST'])
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
            session['authenticated'] = True
            session.permanent = True

            if remember:
                timeout = int(os.environ.get('IBP_SESSION_REMEMBER', 2592000))
            else:
                timeout = int(os.environ.get('IBP_SESSION_TIMEOUT', 3600))

            current_app.permanent_session_lifetime = datetime.timedelta(seconds=timeout)

            logger.info("User authenticated successfully")

            next_url = session.pop('next_url', None)
            return redirect(next_url or url_for('main.dashboard'))
        else:
            error = 'Incorrect password'
            logger.warning(f"Failed login attempt from {request.remote_addr}")

    return render_template('login.html', error=error)


@auth_bp.route('/logout')
def logout():
    """Logout and clear session."""
    session.clear()
    return redirect(url_for('auth.login'))
