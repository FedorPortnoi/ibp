"""
IBP Main Routes
===============
Root URL routing and investigations list
"""

from flask import Blueprint, redirect, url_for, render_template

main_bp = Blueprint('main', __name__)


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
