"""
IBP Main Routes
===============
Root URL routing, investigations list, VK token management
"""

import logging
from flask import Blueprint, redirect, url_for, render_template, jsonify, request

main_bp = Blueprint('main', __name__)
logger = logging.getLogger('ibp.routes.main')


@main_bp.route('/health')
def health_check():
    """Health check with service status."""
    import os
    import subprocess
    from app import db as _db

    # Database connectivity
    db_ok = False
    try:
        _db.session.execute(_db.text('SELECT 1'))
        db_ok = True
    except Exception:
        pass

    # Git version (or VERSION file)
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

    # Key service status
    services = {
        'vk_token': bool(os.environ.get('VK_SERVICE_TOKEN')),
        'telegram': bool(os.environ.get('TELEGRAM_API_ID') and os.environ.get('TELEGRAM_API_HASH')),
        'ok_token': bool(os.environ.get('OK_SESSION_TOKEN')),
    }

    # OpenSanctions API reachable?
    opensanctions_ok = False
    try:
        from app.services.candidate.opensanctions_service import OpenSanctionsService
        opensanctions_ok = OpenSanctionsService(timeout=5).is_reachable()
    except Exception:
        pass

    # Local security data files present?
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
    """Home landing page."""
    return render_template('home.html')


@main_bp.route('/about')
def about():
    """About page — what СЛЕД is and how it works."""
    return render_template('about.html')


@main_bp.route('/services')
def services():
    """Services page — pipeline capabilities breakdown."""
    return render_template('services.html')


@main_bp.route('/projects')
def projects():
    """Projects page — recent candidate checks."""
    from app.models.candidate_check import CandidateCheck
    checks = CandidateCheck.query.order_by(CandidateCheck.created_at.desc()).limit(20).all()
    return render_template('projects.html', checks=checks)


@main_bp.route('/contact')
def contact():
    """Contact/access page."""
    return render_template('contact.html')


@main_bp.route('/dashboard')
def dashboard():
    """Dashboard - redirect to home."""
    return redirect(url_for('main.index'))


@main_bp.route('/investigations')
def investigations_list():
    """Show list of all past investigations."""
    from app.models import Investigation, SocialProfile

    investigations = Investigation.query.order_by(Investigation.created_at.desc()).all()

    # Enhance with confirmed profile data (single query instead of N+1)
    inv_ids = [inv.id for inv in investigations]
    confirmed_profiles = {}
    if inv_ids:
        profiles = SocialProfile.query.filter(
            SocialProfile.investigation_id.in_(inv_ids),
            SocialProfile.is_confirmed == True
        ).all()
        for p in profiles:
            if p.investigation_id not in confirmed_profiles:
                confirmed_profiles[p.investigation_id] = p
    for inv in investigations:
        inv.confirmed_profile_obj = confirmed_profiles.get(inv.id)

    return render_template('investigations_list.html', investigations=investigations)


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
    data = request.get_json()
    if not data or not data.get('token'):
        return jsonify({'error': 'Токен не предоставлен'}), 400

    token = data['token'].strip()
    if len(token) < 10:
        return jsonify({'error': 'Недействительный токен'}), 400

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
