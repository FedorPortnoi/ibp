"""
IBP Main Routes
===============
Root URL routing, investigations list, VK token management
"""

import logging
import os
from flask import Blueprint, redirect, url_for, render_template, jsonify, request, session
from app.permissions import is_admin
from app.routes.auth import admin_required, get_current_user, login_required

main_bp = Blueprint('main', __name__)
logger = logging.getLogger('ibp.routes.main')


def _project_root():
    return os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(__file__)), '..'))


def _probe_database():
    from app import db as _db

    try:
        _db.session.execute(_db.text('SELECT 1'))
        return True
    except Exception as exc:
        logger.warning("Database readiness probe failed: %s", exc)
        return False


def _app_version():
    version = os.environ.get('APP_VERSION', 'unknown')
    if version != 'unknown':
        return version

    version_file = os.path.join(_project_root(), 'VERSION')
    if not os.path.exists(version_file):
        return version

    try:
        with open(version_file, encoding='utf-8') as f:
            return f.read().strip() or 'unknown'
    except OSError as exc:
        logger.warning("Could not read VERSION file: %s", exc)
        return version


def _local_data_status():
    data_dir = os.path.join(_project_root(), 'data')
    return {
        'mvd_wanted': os.path.exists(os.path.join(data_dir, 'mvd_wanted.json')),
        'extremist_list': os.path.exists(os.path.join(data_dir, 'extremist_list.json')),
    }


@main_bp.route('/health')
def health_check():
    """Health check endpoint.

    Returns minimal status for unauthenticated requests (load balancer / uptime monitor).
    Returns detailed service status only for authenticated users.
    """
    authenticated = bool(session.get('user_id'))

    # Unauthenticated: minimal liveness response for load balancers / uptime monitors.
    if not authenticated:
        return jsonify({'status': 'ok'}), 200

    db_ok = _probe_database()

    # Detailed service status only for admins — prevents infrastructure enumeration.
    if not is_admin(get_current_user()):
        return jsonify({'status': 'ok' if db_ok else 'degraded'}), 200 if db_ok else 503

    version = _app_version()
    services = {
        'vk_token': bool(os.environ.get('VK_SERVICE_TOKEN')),
        'telegram': bool(os.environ.get('TELEGRAM_API_ID') and os.environ.get('TELEGRAM_API_HASH')),
    }

    opensanctions_ok = False
    try:
        from app.services.candidate.opensanctions_service import OpenSanctionsService
        opensanctions_ok = OpenSanctionsService(timeout=5).is_reachable()
    except Exception as exc:
        logger.warning("OpenSanctions health probe failed: %s", exc)

    return jsonify({
        'status': 'ok' if db_ok else 'degraded',
        'version': version,
        'database': db_ok,
        'services': services,
        'opensanctions': opensanctions_ok,
        'local_data': _local_data_status(),
    }), 200 if db_ok else 503


@main_bp.route('/ready')
def readiness_check():
    """Readiness check for deploy monitors.

    Exposes internal readiness state (database connectivity, local data files)
    so orchestrators can distinguish degraded from healthy without revealing
    external-service credentials or upstream API reachability.
    """
    db_ok = _probe_database()
    return jsonify({
        'status': 'ok' if db_ok else 'degraded',
        'database': db_ok,
        'local_data': _local_data_status(),
    }), 200 if db_ok else 503


@main_bp.route('/privacy')
def privacy():
    """Privacy policy page (152-FZ compliance)."""
    return render_template('privacy.html')


@main_bp.route('/')
def index():
    """Root — authenticated users go to dashboard, others to login."""
    return redirect(url_for('main.dashboard'))


@main_bp.route('/dashboard')
def dashboard():
    """Investigation type selection — first screen after login."""
    return render_template('dashboard.html')


@main_bp.route('/investigations')
@login_required
def investigations_list():
    from app.models.candidate_check import CandidateCheck
    from app.models.company_check import CompanyCheck
    user = get_current_user()
    candidate_checks = CandidateCheck.query.filter_by(user_id=user.id).order_by(CandidateCheck.created_at.desc()).limit(50).all()
    company_checks = CompanyCheck.query.filter_by(user_id=user.id).order_by(CompanyCheck.created_at.desc()).limit(50).all()
    return render_template('investigations.html', candidate_checks=candidate_checks, company_checks=company_checks)


# ============================================
# VK TOKEN MANAGEMENT
# ============================================

@main_bp.route('/vk/auth')
@admin_required
def vk_auth():
    """Redirect to VK OAuth URL for token acquisition."""
    from app.utils.vk_token_manager import get_oauth_url
    url, error = get_oauth_url()
    if error:
        return render_template('vk_callback.html', error=error)
    return redirect(url)


@main_bp.route('/vk/callback')
@admin_required
def vk_callback():
    """Landing page that captures VK token from URL fragment via JS."""
    return render_template('vk_callback.html', error=None)


@main_bp.route('/vk/save-token', methods=['POST'])
@admin_required
def vk_save_token():
    """Save VK token received from OAuth callback. Admin only."""
    from app.utils.vk_token_manager import _sanitize_token, save_token, get_token_status

    data = request.get_json()
    if not data or not data.get('token'):
        return jsonify({'error': 'Токен не предоставлен'}), 400

    raw = data['token']
    if len(raw) < 10 or len(raw) > 500:
        return jsonify({'error': 'Недействительный токен'}), 400

    token = _sanitize_token(raw)
    if not token:
        return jsonify({'error': 'Недействительный формат токена'}), 400

    save_token(token)
    status = get_token_status()
    return jsonify({'success': True, 'status': status})


@main_bp.route('/api/vk/token-status')
@admin_required
def vk_token_status():
    """Get VK token status. Admin only."""
    from app.utils.vk_token_manager import get_token_status
    return jsonify(get_token_status())
