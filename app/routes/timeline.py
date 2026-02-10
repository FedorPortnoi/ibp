"""
Timeline Routes
===============
Activity timeline visualization for investigations.
"""

from flask import Blueprint, render_template, jsonify
from app.models import Investigation

timeline_bp = Blueprint('timeline', __name__, url_prefix='/timeline')


@timeline_bp.route('/<investigation_id>')
def timeline_view(investigation_id):
    """Timeline visualization page."""
    investigation = Investigation.query.get_or_404(investigation_id)
    return render_template(
        'timeline.html',
        investigation=investigation,
    )


@timeline_bp.route('/api/<investigation_id>')
def timeline_data(investigation_id):
    """Timeline data JSON endpoint."""
    investigation = Investigation.query.get_or_404(investigation_id)

    from app.services.activity_timeline import activity_timeline
    data = activity_timeline.analyze(investigation_id)

    return jsonify({
        'success': True,
        'investigation_id': investigation_id,
        'target_name': investigation.input_name,
        **data,
    })
