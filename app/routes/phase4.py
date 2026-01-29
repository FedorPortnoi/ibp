"""
Phase 4 routes: Graph visualization, People search, Connection analysis.
Agent 6 - Frontend/Database
"""
from flask import Blueprint, render_template, jsonify, request
from app import db

phase4_bp = Blueprint('phase4', __name__)


@phase4_bp.route('/search/people')
def people_search():
    """Russian social media people search page."""
    return render_template('people_search.html')


@phase4_bp.route('/api/search/people', methods=['POST'])
def api_people_search():
    """
    API endpoint for cross-platform people search.
    Orchestrated by Agent 1's research_orchestrator.
    """
    data = request.json or {}
    name = data.get('name', '').strip()

    if not name:
        return jsonify({'error': 'Name is required'}), 400

    # Get optional filters
    city = data.get('city')
    age_from = data.get('age_from')
    age_to = data.get('age_to')
    platforms = data.get('platforms', ['vk', 'ok', 'telegram'])
    investigation_id = data.get('investigation_id')

    # Try to use the orchestrator (Agent 1 implementation)
    try:
        from app.services.phase4.research_orchestrator import research_orchestrator
        results = research_orchestrator.search_person(
            name=name,
            city=city,
            age_from=age_from,
            age_to=age_to,
            platforms=platforms,
            investigation_id=investigation_id
        )
        return jsonify(results)
    except ImportError:
        # Orchestrator not yet created by Agent 1 - return placeholder
        return jsonify({
            'status': 'pending',
            'message': 'Search orchestrator pending implementation by Agent 1',
            'profiles': [],
            'stats': {
                'total_found': 0,
                'platforms_searched': platforms,
                'search_time': 0
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@phase4_bp.route('/investigation/<investigation_id>/graph')
def show_graph(investigation_id):
    """Display interactive relationship graph for an investigation."""
    try:
        from app.models.investigation import Investigation
        investigation = Investigation.query.get_or_404(investigation_id)
        return render_template('graph.html', investigation=investigation)
    except Exception as e:
        return render_template('error.html', error=f"Error loading investigation: {e}"), 500


@phase4_bp.route('/api/investigation/<investigation_id>/graph-data')
def get_graph_data(investigation_id):
    """
    Return graph data in vis.js format.
    Nodes are entities (people, groups, companies).
    Edges are connections between them.
    """
    try:
        from app.models.connection import Connection
        from app.models.investigation import Investigation

        # Verify investigation exists
        investigation = Investigation.query.get(investigation_id)
        if not investigation:
            return jsonify({'error': 'Investigation not found', 'nodes': [], 'edges': []}), 404

        # Get all connections for this investigation
        connections = Connection.query.filter_by(investigation_id=investigation_id).all()

        nodes = {}
        edges = []

        # Add the target person as the central node
        if investigation.input_name:
            target_id = f"target_{investigation_id}"
            nodes[target_id] = {
                'id': target_id,
                'label': investigation.input_name,
                'group': 'target',
                'shape': 'dot',
                'size': 30
            }

        # Process connections
        for conn in connections:
            # Add source node if not exists
            if conn.source_id and conn.source_id not in nodes:
                nodes[conn.source_id] = conn.to_vis_node('source')

            # Add target node if not exists
            if conn.target_id and conn.target_id not in nodes:
                nodes[conn.target_id] = conn.to_vis_node('target')

            # Add edge
            edges.append(conn.to_vis_edge())

        return jsonify({
            'nodes': list(nodes.values()),
            'edges': edges,
            'stats': {
                'total_nodes': len(nodes),
                'total_edges': len(edges)
            }
        })

    except Exception as e:
        return jsonify({
            'error': str(e),
            'nodes': [],
            'edges': []
        }), 500


@phase4_bp.route('/api/investigation/<investigation_id>/connections', methods=['GET'])
def get_connections(investigation_id):
    """Get all connections for an investigation as list."""
    try:
        from app.models.connection import Connection

        connections = Connection.query.filter_by(investigation_id=investigation_id).all()
        return jsonify({
            'connections': [c.to_dict() for c in connections],
            'count': len(connections)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@phase4_bp.route('/api/investigation/<investigation_id>/connections', methods=['POST'])
def add_connection(investigation_id):
    """
    Add a new connection to an investigation.
    Expected format (from AGENT_CONTRACT.md):
    {
        "source_id": "profile_url_or_id",
        "target_id": "profile_url_or_id",
        "connection_type": "friend|colleague|family|group_member",
        "strength": 0.8,
        "evidence": "How discovered",
        "platform": "vk|ok|telegram"
    }
    """
    try:
        from app.models.connection import Connection

        data = request.json
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        # Validate required fields
        if not data.get('source_id') or not data.get('target_id'):
            return jsonify({'error': 'source_id and target_id are required'}), 400

        # Create connection using contract format
        conn = Connection.create_from_dict(data, investigation_id=investigation_id)

        # Add optional name fields if provided
        if data.get('source_name'):
            conn.source_name = data['source_name']
        if data.get('target_name'):
            conn.target_name = data['target_name']
        if data.get('source_type'):
            conn.source_type = data['source_type']
        if data.get('target_type'):
            conn.target_type = data['target_type']

        db.session.add(conn)
        db.session.commit()

        return jsonify({
            'success': True,
            'connection': conn.to_dict()
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@phase4_bp.route('/api/connections/<int:connection_id>', methods=['DELETE'])
def delete_connection(connection_id):
    """Delete a connection."""
    try:
        from app.models.connection import Connection

        conn = Connection.query.get_or_404(connection_id)
        db.session.delete(conn)
        db.session.commit()

        return jsonify({'success': True, 'deleted_id': connection_id})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
