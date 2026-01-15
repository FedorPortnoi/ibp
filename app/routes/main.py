"""
IBP Main Routes
===============
Redirects root URL to Phase 1 investigation page
"""

from flask import Blueprint, redirect, url_for

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    """Redirect root to Phase 1 start page."""
    return redirect(url_for('phase1.index'))


@main_bp.route('/dashboard')
def dashboard():
    """Dashboard - coming soon."""
    return redirect(url_for('phase1.index'))

