"""
IBP Cross-Investigation Connections Routes
==========================================
Blueprint for analyzing and visualizing connections between investigations.
"""

import logging
from flask import Blueprint, render_template, jsonify, request

connections_bp = Blueprint('connections', __name__)
logger = logging.getLogger('ibp.routes.connections')


@connections_bp.route('/connections')
def connections_page():
    """Page showing cross-investigation connections with vis.js graph."""
    from app.models import Investigation, SocialProfile

    investigations = Investigation.query.order_by(Investigation.created_at.desc()).all()

    # Enhance with confirmed profile data
    for inv in investigations:
        inv.confirmed_profile_obj = SocialProfile.query.filter_by(
            investigation_id=inv.id,
            is_confirmed=True
        ).first()

    return render_template('connections.html', investigations=investigations)


@connections_bp.route('/api/connections/analyze', methods=['POST'])
def analyze_connections():
    """Run cross-investigation connection analysis.

    POST JSON body:
        { "investigation_ids": ["id1", "id2", ...] }
        If investigation_ids is empty or missing, analyzes all investigations.
    """
    from app.services.connection_intelligence import ConnectionIntelligence

    data = request.get_json(silent=True) or {}
    investigation_ids = data.get('investigation_ids')

    if investigation_ids and not isinstance(investigation_ids, list):
        return jsonify({'error': 'investigation_ids должен быть списком'}), 400

    try:
        engine = ConnectionIntelligence()
        results = engine.analyze(investigation_ids=investigation_ids or None)
        return jsonify(results)
    except Exception as e:
        logger.error(f"Connection analysis error: {e}", exc_info=True)
        return jsonify({'error': 'Внутренняя ошибка сервера'}), 500


@connections_bp.route('/api/connections/graph-data')
def graph_data():
    """Return vis.js compatible graph data for all investigations.

    Query params:
        ids - comma-separated investigation IDs (optional)
    """
    from app.services.connection_intelligence import ConnectionIntelligence

    ids_param = request.args.get('ids')
    investigation_ids = None
    if ids_param:
        investigation_ids = [i.strip() for i in ids_param.split(',') if i.strip()]

    try:
        engine = ConnectionIntelligence()
        results = engine.analyze(investigation_ids=investigation_ids)
        return jsonify({
            'nodes': results['nodes'],
            'edges': results['edges'],
            'summary': results['summary'],
        })
    except Exception as e:
        logger.error(f"Graph data error: {e}", exc_info=True)
        return jsonify({'error': 'Внутренняя ошибка сервера'}), 500
