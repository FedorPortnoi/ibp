"""
Phase 3 Routes - Deep Investigation
===================================
Find records, business ties, alternate accounts.
"""

from flask import Blueprint, render_template, request, jsonify

phase3_bp = Blueprint('phase3', __name__, url_prefix='/phase3')


@phase3_bp.route('/<investigation_id>', methods=['GET'])
def index(investigation_id):
    """Phase 3 start page - Deep investigation using all confirmed data."""
    return render_template('phase3.html', investigation_id=investigation_id)


@phase3_bp.route('/search', methods=['POST'])
def search():
    """Run deep investigation searches."""
    investigation_id = request.form.get('investigation_id')
    
    # TODO: Implement deep searches
    # Tools: Rusprofile, court records, breach databases, etc.
    
    results = {
        'status': 'placeholder',
        'message': 'Phase 3 search will be implemented soon',
        'investigation_id': investigation_id
    }
    
    return jsonify(results)


@phase3_bp.route('/results/<investigation_id>')
def results(investigation_id):
    """Display Phase 3 results - final review before card generation."""
    return render_template('phase3_results.html', investigation_id=investigation_id)
