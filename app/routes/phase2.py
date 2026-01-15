"""
Phase 2 Routes - Contact Information Discovery
==============================================
Find phone numbers and email addresses.
"""

from flask import Blueprint, render_template, request, jsonify

phase2_bp = Blueprint('phase2', __name__, url_prefix='/phase2')


@phase2_bp.route('/<investigation_id>', methods=['GET'])
def index(investigation_id):
    """Phase 2 start page - Uses confirmed data from Phase 1."""
    return render_template('phase2.html', investigation_id=investigation_id)


@phase2_bp.route('/search', methods=['POST'])
def search():
    """Run contact information searches."""
    investigation_id = request.form.get('investigation_id')
    
    # TODO: Implement facial recognition, email/phone discovery
    # Tools: Search4faces, Epieos, Truecaller, etc.
    
    results = {
        'status': 'placeholder',
        'message': 'Phase 2 search will be implemented soon',
        'investigation_id': investigation_id
    }
    
    return jsonify(results)


@phase2_bp.route('/results/<investigation_id>')
def results(investigation_id):
    """Display Phase 2 results for user confirmation."""
    return render_template('phase2_results.html', investigation_id=investigation_id)
