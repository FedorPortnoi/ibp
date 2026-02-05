"""
VK OAuth Token Refresh Routes
==============================
Handles VK token acquisition and refresh for IBP.

VK uses OAuth Implicit Flow for standalone apps, which returns
the access_token as a URL fragment (#access_token=...).
Since fragments are client-side only, we need JS to capture it
and POST it to the server.

Two approaches:
1. AUTOMATIC: VK redirects to our local callback, JS captures token
2. MANUAL: User pastes the redirect URL, we extract the token
"""

import os
import re
import time
from datetime import datetime, timedelta
from flask import Blueprint, redirect, request, jsonify, render_template, url_for
from dotenv import load_dotenv, set_key

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

# ── VK App Configuration ────────────────────────────────────────────
VK_APP_ID = "54271656"
VK_API_VERSION = "5.199"
VK_SCOPES = "friends,groups"
VK_LOCAL_REDIRECT = "http://127.0.0.1:5000/auth/vk/callback"
VK_BLANK_REDIRECT = "https://oauth.vk.com/blank.html"

# Path to .env file (project root)
ENV_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')


def _build_auth_url(redirect_uri: str) -> str:
    """Build VK OAuth authorization URL."""
    return (
        f"https://oauth.vk.com/authorize?"
        f"client_id={VK_APP_ID}"
        f"&display=page"
        f"&redirect_uri={redirect_uri}"
        f"&scope={VK_SCOPES}"
        f"&response_type=token"
        f"&v={VK_API_VERSION}"
    )


# ── Route: Token Status ─────────────────────────────────────────────
@auth_bp.route('/vk/status')
def vk_token_status():
    """
    Check if VK token exists and roughly when it was saved.
    Returns JSON for use by the UI status indicator.
    """
    token = os.environ.get('VK_SERVICE_TOKEN', '')
    token_saved_at = os.environ.get('VK_TOKEN_SAVED_AT', '')

    if not token:
        return jsonify({
            'status': 'missing',
            'message': 'Токен не найден',
            'icon': '🔴'
        })

    # Check if we have a saved timestamp
    if token_saved_at:
        try:
            saved_time = datetime.fromisoformat(token_saved_at)
            expires_at = saved_time + timedelta(hours=24)
            now = datetime.now()

            if now > expires_at:
                return jsonify({
                    'status': 'expired',
                    'message': f'Токен истёк ({saved_time.strftime("%d.%m %H:%M")})',
                    'icon': '🔴',
                    'saved_at': token_saved_at
                })

            remaining = expires_at - now
            hours_left = remaining.seconds // 3600
            mins_left = (remaining.seconds % 3600) // 60

            return jsonify({
                'status': 'valid',
                'message': f'Осталось ~{hours_left}ч {mins_left}м',
                'icon': '🟢',
                'saved_at': token_saved_at,
                'expires_at': expires_at.isoformat()
            })
        except (ValueError, TypeError):
            pass

    # Token exists but no timestamp — assume it might work
    return jsonify({
        'status': 'unknown',
        'message': 'Токен есть, статус неизвестен',
        'icon': '🟡'
    })


# ── Route: Start VK Auth (automatic redirect) ───────────────────────
@auth_bp.route('/vk')
def vk_auth():
    """
    Redirect user to VK OAuth page.
    Tries local redirect first (best UX).
    """
    auth_url = _build_auth_url(VK_LOCAL_REDIRECT)
    return redirect(auth_url)


# ── Route: Callback Page ────────────────────────────────────────────
@auth_bp.route('/vk/callback')
def vk_callback():
    """
    Callback page after VK auth.
    VK redirects here with token in URL fragment.
    JS on this page extracts it and POSTs to /auth/vk/save.
    """
    return render_template('buratino_auth_callback.html')


# ── Route: Manual Token Paste Page ──────────────────────────────────
@auth_bp.route('/vk/manual')
def vk_manual():
    """
    Fallback: opens VK auth with blank.html redirect.
    Shows a form where user pastes the redirect URL.
    Use this if VK rejects the local redirect.
    """
    auth_url = _build_auth_url(VK_BLANK_REDIRECT)
    return render_template('buratino_auth_callback.html', 
                           manual_mode=True,
                           auth_url=auth_url)


# ── Route: Save Token ───────────────────────────────────────────────
@auth_bp.route('/vk/save', methods=['POST'])
def vk_save_token():
    """
    Save the VK access token to .env and reload into environment.
    Accepts JSON: {"access_token": "...", "user_id": "...", "expires_in": ...}
    """
    data = request.get_json()

    if not data or 'access_token' not in data:
        return jsonify({'success': False, 'error': 'No access_token provided'}), 400

    token = data['access_token']
    user_id = data.get('user_id', '')
    expires_in = data.get('expires_in', 86400)

    try:
        # Ensure .env file exists
        if not os.path.exists(ENV_PATH):
            with open(ENV_PATH, 'w') as f:
                f.write('')

        # Save token and metadata to .env
        set_key(ENV_PATH, 'VK_SERVICE_TOKEN', token)
        set_key(ENV_PATH, 'VK_TOKEN_SAVED_AT', datetime.now().isoformat())
        if user_id:
            set_key(ENV_PATH, 'VK_USER_ID', str(user_id))

        # Reload into current process environment
        os.environ['VK_SERVICE_TOKEN'] = token
        os.environ['VK_TOKEN_SAVED_AT'] = datetime.now().isoformat()
        if user_id:
            os.environ['VK_USER_ID'] = str(user_id)

        # Also reload dotenv to be safe
        load_dotenv(ENV_PATH, override=True)

        # Try to update the BuratinoVKSearch singleton if it exists
        try:
            from app.services.phase1.buratino_vk_search import buratino_vk_search
            buratino_vk_search.access_token = token
            buratino_vk_search._demo_mode = False
        except (ImportError, AttributeError):
            pass  # Service not loaded yet, that's fine

        return jsonify({
            'success': True,
            'message': 'Токен сохранён! Действителен ~24 часа.',
            'expires_in': expires_in,
            'saved_at': datetime.now().isoformat()
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ── Route: Extract Token from Pasted URL ────────────────────────────
@auth_bp.route('/vk/extract', methods=['POST'])
def vk_extract_token():
    """
    Extract access_token from a pasted VK redirect URL.
    URL format: https://oauth.vk.com/blank.html#access_token=TOKEN&expires_in=86400&user_id=12345
    """
    data = request.get_json()
    url = data.get('url', '')

    if not url:
        return jsonify({'success': False, 'error': 'No URL provided'}), 400

    # Extract token from URL fragment
    token_match = re.search(r'access_token=([a-zA-Z0-9._-]+)', url)
    user_id_match = re.search(r'user_id=(\d+)', url)
    expires_match = re.search(r'expires_in=(\d+)', url)

    if not token_match:
        return jsonify({'success': False, 'error': 'Токен не найден в URL'}), 400

    # Forward to the save endpoint
    token_data = {
        'access_token': token_match.group(1),
        'user_id': user_id_match.group(1) if user_id_match else '',
        'expires_in': int(expires_match.group(1)) if expires_match else 86400
    }

    # Save directly (reuse logic)
    try:
        if not os.path.exists(ENV_PATH):
            with open(ENV_PATH, 'w') as f:
                f.write('')

        set_key(ENV_PATH, 'VK_SERVICE_TOKEN', token_data['access_token'])
        set_key(ENV_PATH, 'VK_TOKEN_SAVED_AT', datetime.now().isoformat())
        if token_data['user_id']:
            set_key(ENV_PATH, 'VK_USER_ID', str(token_data['user_id']))

        os.environ['VK_SERVICE_TOKEN'] = token_data['access_token']
        os.environ['VK_TOKEN_SAVED_AT'] = datetime.now().isoformat()
        load_dotenv(ENV_PATH, override=True)

        try:
            from app.services.phase1.buratino_vk_search import buratino_vk_search
            buratino_vk_search.access_token = token_data['access_token']
            buratino_vk_search._demo_mode = False
        except (ImportError, AttributeError):
            pass

        return jsonify({
            'success': True,
            'message': 'Токен извлечён и сохранён!',
            'user_id': token_data['user_id'],
            'expires_in': token_data['expires_in']
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
