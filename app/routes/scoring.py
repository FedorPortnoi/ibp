"""
Scoring Routes - Risk Scoring Engine
=====================================
API and page routes for automated risk scoring.
"""

import logging
from flask import Blueprint, render_template, jsonify, request
from app import limiter
from app.routes.auth import admin_required

scoring_bp = Blueprint('scoring', __name__)
logger = logging.getLogger('ibp.routes.scoring')


@scoring_bp.route('/api/scoring/calculate', methods=['POST'])
@admin_required
@limiter.limit("10 per minute")
def calculate_score():
    """Calculate and store risk score for an investigation."""
    from app.services.risk_scoring import calculate_risk_score

    data = request.get_json()
    if not data or not data.get('investigation_id'):
        return jsonify({'error': 'investigation_id обязателен'}), 400

    investigation_id = data['investigation_id']
    result = calculate_risk_score(investigation_id)

    if result is None:
        return jsonify({'error': 'Расследование не найдено'}), 404

    return jsonify(result)


@scoring_bp.route('/api/scoring/breakdown/<investigation_id>')
@admin_required
def score_breakdown(investigation_id):
    """Return dimensional breakdown for an investigation."""
    from app.services.risk_scoring import get_score_breakdown

    result = get_score_breakdown(investigation_id)

    if result is None:
        return jsonify({'error': 'Расследование не найдено'}), 404

    return jsonify(result)


@scoring_bp.route('/risk-report/<investigation_id>')
@admin_required
def risk_report(investigation_id):
    """Full risk report page with radar chart."""
    from app.models import Investigation, SocialProfile
    from app.services.risk_scoring import calculate_risk_score

    investigation = Investigation.query.get(investigation_id)
    if not investigation:
        return render_template('errors/404.html'), 404

    score_data = calculate_risk_score(investigation_id)

    confirmed_profile = SocialProfile.query.filter_by(
        investigation_id=investigation_id,
        is_confirmed=True
    ).first()

    return render_template(
        'risk_report.html',
        investigation=investigation,
        profile=confirmed_profile,
        score=score_data,
    )
