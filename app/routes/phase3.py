"""
Phase 3 Routes - Deep Investigation
===================================
Business records, court cases, geo-information, text analysis.
"""

import logging
import uuid
import threading
from datetime import datetime
from flask import Blueprint, render_template, request, jsonify

phase3_bp = Blueprint('phase3', __name__, url_prefix='/phase3')
logger = logging.getLogger(__name__)

# Task storage for async investigations
phase3_tasks = {}


class Phase3TaskStatus:
    """Holds the status of a Phase 3 investigation task."""

    def __init__(self, task_id: str, investigation_data: dict):
        self.task_id = task_id
        self.investigation_data = investigation_data
        self.target_name = investigation_data.get('target_name', 'Unknown')

        # Progress tracking
        self.current_step = 'initializing'
        self.percent_complete = 0
        self.messages = []

        # Results
        self.results = None
        self.error = None
        self.started_at = datetime.now()
        self.completed_at = None

    def add_message(self, text: str, msg_type: str = 'info'):
        self.messages.append({
            'text': text,
            'type': msg_type,
            'time': datetime.now().isoformat()
        })

    def to_dict(self):
        return {
            'task_id': self.task_id,
            'target_name': self.target_name,
            'current_step': self.current_step,
            'percent_complete': self.percent_complete,
            'messages': self.messages[-20:],
            'error': self.error,
            'is_complete': self.results is not None or self.error is not None
        }


def run_phase3_task(task_id: str):
    """Background task to run Phase 3 investigation."""
    task = phase3_tasks.get(task_id)
    if not task:
        return

    try:
        task.add_message(f'Starting Phase 3 investigation for {task.target_name}', 'info')

        results = {
            'business_records': [],
            'court_cases': [],
            'locations': [],
            'text_analysis': None,
            'stats': {}
        }

        # Get investigation data
        profiles = task.investigation_data.get('profiles', [])
        target_name = task.target_name

        # Step 1: Business Registry Search
        task.current_step = 'Searching business records...'
        task.percent_complete = 10
        task.add_message('Searching Russian business registries (ЕГРЮЛ/ЕГРИП)...', 'info')

        try:
            from app.services.phase3.business_registry import business_registry_search

            business_records = business_registry_search.search_by_name(target_name)
            results['business_records'] = [r.to_dict() for r in business_records]
            task.add_message(f'Found {len(business_records)} business affiliations', 'success')
        except Exception as e:
            task.add_message(f'Business search error: {str(e)}', 'warning')
            logger.warning(f"Business search failed: {e}")

        # Step 2: Court Records Search
        task.current_step = 'Searching court records...'
        task.percent_complete = 30
        task.add_message('Searching court databases (sudact.ru, arbitration)...', 'info')

        try:
            from app.services.phase3.court_search import court_search

            court_cases = court_search.search_by_name(target_name)
            results['court_cases'] = [c.to_dict() for c in court_cases]
            task.add_message(f'Found {len(court_cases)} court cases', 'success')
        except Exception as e:
            task.add_message(f'Court search error: {str(e)}', 'warning')
            logger.warning(f"Court search failed: {e}")

        # Step 3: Geo-Information Extraction
        task.current_step = 'Extracting location data...'
        task.percent_complete = 50
        task.add_message('Extracting geo-information from social media...', 'info')

        try:
            from app.services.phase3.geo_extractor import geo_extractor

            location_analysis = geo_extractor.extract_from_profiles(profiles)
            results['locations'] = location_analysis.to_dict()
            results['map_data'] = geo_extractor.generate_map_data(location_analysis.locations)
            task.add_message(f'Found {len(location_analysis.locations)} location points', 'success')
        except Exception as e:
            task.add_message(f'Geo extraction error: {str(e)}', 'warning')
            logger.warning(f"Geo extraction failed: {e}")

        # Step 4: Text Analysis
        task.current_step = 'Analyzing text content...'
        task.percent_complete = 70
        task.add_message('Running sentiment and keyword analysis...', 'info')

        # Collect posts from profiles
        posts = task.investigation_data.get('posts', [])
        if posts:
            try:
                from app.services.phase3.text_analyzer import text_analyzer

                text_result = text_analyzer.analyze_posts(posts)
                results['text_analysis'] = text_result.to_dict()
                task.add_message(
                    f'Text analysis complete: {text_result.sentiment.label if text_result.sentiment else "N/A"} sentiment',
                    'success'
                )
            except Exception as e:
                task.add_message(f'Text analysis error: {str(e)}', 'warning')
                logger.warning(f"Text analysis failed: {e}")
        else:
            task.add_message('No posts available for text analysis', 'info')

        # Step 5: Compile stats
        task.current_step = 'Finalizing...'
        task.percent_complete = 90

        results['stats'] = {
            'business_records_found': len(results['business_records']),
            'court_cases_found': len(results['court_cases']),
            'locations_found': len(results.get('locations', {}).get('locations', [])),
            'text_analyzed': bool(results.get('text_analysis'))
        }

        # Complete
        task.results = results
        task.completed_at = datetime.now()
        task.percent_complete = 100
        task.current_step = 'Complete'

        elapsed = (task.completed_at - task.started_at).total_seconds()
        task.add_message(f'Phase 3 investigation complete in {elapsed:.1f}s', 'success')

    except Exception as e:
        task.error = str(e)
        task.add_message(f'Error: {str(e)}', 'error')
        logger.error(f"Phase 3 task error: {e}", exc_info=True)


@phase3_bp.route('/<investigation_id>', methods=['GET'])
def index(investigation_id):
    """Phase 3 start page - Deep investigation using all confirmed data."""
    return render_template('phase3.html', investigation_id=investigation_id)


@phase3_bp.route('/start', methods=['POST'])
def start_investigation():
    """Start Phase 3 investigation (async)."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        target_name = data.get('target_name', '')
        if not target_name:
            return jsonify({'error': 'Target name required'}), 400

        # Create task
        task_id = uuid.uuid4().hex
        task = Phase3TaskStatus(task_id, data)
        phase3_tasks[task_id] = task

        # Start background thread
        thread = threading.Thread(target=run_phase3_task, args=(task_id,))
        thread.daemon = True
        thread.start()

        return jsonify({
            'success': True,
            'task_id': task_id
        })

    except Exception as e:
        logger.error(f"Phase 3 start error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@phase3_bp.route('/progress/<task_id>')
def get_progress(task_id):
    """Get task progress for polling."""
    task = phase3_tasks.get(task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    return jsonify(task.to_dict())


@phase3_bp.route('/results/<task_id>')
def get_results(task_id):
    """Get full results for a completed task."""
    task = phase3_tasks.get(task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404

    if task.error:
        return jsonify({'error': task.error}), 500

    if not task.results:
        return jsonify({'error': 'Task not complete'}), 400

    return jsonify({
        'status': 'success',
        'task_id': task_id,
        'target_name': task.target_name,
        'results': task.results
    })


@phase3_bp.route('/results/<investigation_id>')
def results_page(investigation_id):
    """Display Phase 3 results page."""
    return render_template('phase3_results.html', investigation_id=investigation_id)


# Direct API endpoints for individual services

@phase3_bp.route('/api/business-search', methods=['POST'])
def api_business_search():
    """Search business registries."""
    try:
        data = request.get_json()
        name = data.get('name', '')

        if not name:
            return jsonify({'error': 'Name required'}), 400

        from app.services.phase3.business_registry import business_registry_search
        results = business_registry_search.search_by_name(name)

        return jsonify({
            'success': True,
            'results': [r.to_dict() for r in results],
            'count': len(results)
        })

    except Exception as e:
        logger.error(f"Business search API error: {e}")
        return jsonify({'error': str(e)}), 500


@phase3_bp.route('/api/court-search', methods=['POST'])
def api_court_search():
    """Search court records."""
    try:
        data = request.get_json()
        name = data.get('name', '')

        if not name:
            return jsonify({'error': 'Name required'}), 400

        from app.services.phase3.court_search import court_search
        results = court_search.search_by_name(name)

        return jsonify({
            'success': True,
            'results': [c.to_dict() for c in results],
            'count': len(results)
        })

    except Exception as e:
        logger.error(f"Court search API error: {e}")
        return jsonify({'error': str(e)}), 500


@phase3_bp.route('/api/geo-extract', methods=['POST'])
def api_geo_extract():
    """Extract geo-information from profiles."""
    try:
        data = request.get_json()
        profiles = data.get('profiles', [])

        if not profiles:
            return jsonify({'error': 'Profiles required'}), 400

        from app.services.phase3.geo_extractor import geo_extractor
        analysis = geo_extractor.extract_from_profiles(profiles)
        map_data = geo_extractor.generate_map_data(analysis.locations)

        return jsonify({
            'success': True,
            'analysis': analysis.to_dict(),
            'map_data': map_data
        })

    except Exception as e:
        logger.error(f"Geo extraction API error: {e}")
        return jsonify({'error': str(e)}), 500


@phase3_bp.route('/api/text-analyze', methods=['POST'])
def api_text_analyze():
    """Analyze text content."""
    try:
        data = request.get_json()
        posts = data.get('posts', [])
        text = data.get('text', '')

        from app.services.phase3.text_analyzer import text_analyzer

        if text:
            result = text_analyzer.analyze_single_text(text)
        elif posts:
            result = text_analyzer.analyze_posts(posts)
        else:
            return jsonify({'error': 'Text or posts required'}), 400

        return jsonify({
            'success': True,
            'analysis': result.to_dict()
        })

    except Exception as e:
        logger.error(f"Text analysis API error: {e}")
        return jsonify({'error': str(e)}), 500
