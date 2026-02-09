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
    """Health check for Render.com / uptime monitors."""
    return jsonify({'status': 'ok'}), 200


@main_bp.route('/')
def index():
    """Redirect root to Buratino-style new investigation page."""
    return redirect(url_for('phase1.new_investigation'))


@main_bp.route('/dashboard')
def dashboard():
    """Dashboard - redirect to investigations list."""
    return redirect(url_for('main.investigations_list'))


@main_bp.route('/investigations')
def investigations_list():
    """Show list of all past investigations."""
    from app.models import Investigation, SocialProfile

    investigations = Investigation.query.order_by(Investigation.created_at.desc()).all()

    # Enhance with confirmed profile data
    for inv in investigations:
        inv.confirmed_profile_obj = SocialProfile.query.filter_by(
            investigation_id=inv.id,
            is_confirmed=True
        ).first()

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
