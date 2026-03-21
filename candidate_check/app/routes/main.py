"""
IBP Main Routes
===============
Root URL routing, investigations list, VK token management
"""

import logging
from flask import Blueprint, redirect, url_for, render_template, jsonify, request
from app import limiter

main_bp = Blueprint('main', __name__)
logger = logging.getLogger('ibp.routes.main')


@main_bp.route('/health')
def health_check():
    """Health check endpoint.

    Returns minimal status for unauthenticated requests (load balancer / uptime monitor).
    Returns detailed service status only for authenticated users.
    """
    import os
    import subprocess
    from flask import session
    from app import db as _db

    # Database connectivity
    db_ok = False
    try:
        _db.session.execute(_db.text('SELECT 1'))
        db_ok = True
    except Exception:
        pass

    # Unauthenticated: minimal response (for load balancers / uptime monitors)
    if not session.get('authenticated'):
        return jsonify({'status': 'ok' if db_ok else 'degraded'}), 200 if db_ok else 503

    # Authenticated: full details
    version = 'unknown'
    try:
        result = subprocess.run(
            ['git', 'rev-parse', '--short', 'HEAD'],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            version = result.stdout.strip()
    except Exception:
        version_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), '..', 'VERSION')
        if os.path.exists(version_file):
            with open(version_file) as f:
                version = f.read().strip()

    services = {
        'vk_token': bool(os.environ.get('VK_SERVICE_TOKEN')),
        'telegram': bool(os.environ.get('TELEGRAM_API_ID') and os.environ.get('TELEGRAM_API_HASH')),
        'ok_token': bool(os.environ.get('OK_SESSION_TOKEN')),
    }

    opensanctions_ok = False
    try:
        from app.services.candidate.opensanctions_service import OpenSanctionsService
        opensanctions_ok = OpenSanctionsService(timeout=5).is_reachable()
    except Exception:
        pass

    data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), '..', 'data')
    local_data = {
        'mvd_wanted': os.path.exists(os.path.join(data_dir, 'mvd_wanted.json')),
        'extremist_list': os.path.exists(os.path.join(data_dir, 'extremist_list.json')),
    }

    return jsonify({
        'status': 'ok' if db_ok else 'degraded',
        'version': version,
        'database': db_ok,
        'services': services,
        'opensanctions': opensanctions_ok,
        'local_data': local_data,
    }), 200 if db_ok else 503


@main_bp.route('/')
def index():
    """Root — authenticated users go to new investigation, others to login."""
    from flask import session as _session
    if _session.get('authenticated'):
        return redirect(url_for('phase1.new_investigation'))
    return redirect(url_for('auth.login'))


@main_bp.route('/dashboard')
def dashboard():
    """Dashboard — redirect to new investigation."""
    return redirect(url_for('phase1.new_investigation'))


@main_bp.route('/investigations')
def investigations_list():
    return redirect(url_for('candidate.history'))


# ============================================
# VK TOKEN MANAGEMENT
# ============================================

@main_bp.route('/vk/auth')
def vk_auth():
    """Redirect to VK OAuth URL for token acquisition."""
    from app.utils.vk_token_manager import get_oauth_url
    url, error = get_oauth_url()
    if error:
        return render_template('vk_callback.html', error=error)
    return redirect(url)


@main_bp.route('/vk/callback')
def vk_callback():
    """Landing page that captures VK token from URL fragment via JS."""
    return render_template('vk_callback.html', error=None)


@main_bp.route('/vk/save-token', methods=['POST'])
def vk_save_token():
    """Save VK token received from OAuth callback."""
    import re as _re
    data = request.get_json()
    if not data or not data.get('token'):
        return jsonify({'error': 'Токен не предоставлен'}), 400

    token = data['token'].strip()
    if len(token) < 10 or len(token) > 500:
        return jsonify({'error': 'Недействительный токен'}), 400

    # VK tokens are alphanumeric with dots/dashes only
    if not _re.match(r'^[a-zA-Z0-9._\-]+$', token):
        return jsonify({'error': 'Недействительный формат токена'}), 400

    from app.utils.vk_token_manager import save_token, get_token_status
    save_token(token)
    status = get_token_status()
    return jsonify({'success': True, 'status': status})


@main_bp.route('/api/vk/token-status')
def vk_token_status():
    """Get VK token status for AJAX polling."""
    from app.utils.vk_token_manager import get_token_status
    return jsonify(get_token_status())


# ============================================
# INVESTIGATION CRUD API
# ============================================

@main_bp.route('/api/investigations/<investigation_id>', methods=['DELETE'])
@limiter.limit("10 per minute")
def delete_investigation(investigation_id):
    """Delete an investigation and all related records."""
    from app import db
    from app.models import Investigation, SocialProfile, Friend

    investigation = Investigation.query.get(investigation_id)
    if not investigation:
        return jsonify({'error': 'Расследование не найдено'}), 404

    # Delete related records
    SocialProfile.query.filter_by(investigation_id=investigation_id).delete()
    Friend.query.filter_by(investigation_id=investigation_id).delete()
    db.session.delete(investigation)
    db.session.commit()

    logger.info(f"Deleted investigation {investigation_id}")
    return jsonify({'success': True})
