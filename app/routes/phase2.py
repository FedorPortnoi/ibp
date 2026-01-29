"""
Phase 2 Routes - Contact Information Discovery
==============================================
Find phone numbers, email addresses, and additional profiles.
"""

from flask import Blueprint, render_template, request, jsonify, current_app
import json
import logging
import os
import threading
import uuid
from datetime import datetime

from app.services.phase2.combined_search import Phase2CombinedSearch, Phase2Results

phase2_bp = Blueprint('phase2', __name__, url_prefix='/phase2')
logger = logging.getLogger(__name__)

# Task storage for async investigations
phase2_tasks = {}


class Phase2TaskStatus:
    """Holds the status of a Phase 2 investigation task."""

    def __init__(self, task_id: str, target_name: str, selected_profiles: list):
        self.task_id = task_id
        self.target_name = target_name
        self.selected_profiles = selected_profiles

        # Progress tracking
        self.current_step = 'initializing'
        self.percent_complete = 0

        # Messages for UI
        self.messages = []

        # Results
        self.results = None
        self.error = None
        self.started_at = datetime.now()
        self.completed_at = None

    def add_message(self, text: str, msg_type: str = 'info'):
        """Add a message for display."""
        self.messages.append({
            'text': text,
            'type': msg_type,
            'time': datetime.now().isoformat()
        })

    def update_progress(self, step: str, percent: int):
        """Update progress."""
        self.current_step = step
        self.percent_complete = percent
        self.add_message(step, 'info')

    def to_dict(self):
        """Convert to dict for JSON response."""
        return {
            'task_id': self.task_id,
            'target_name': self.target_name,
            'current_step': self.current_step,
            'percent_complete': self.percent_complete,
            'messages': self.messages[-20:],  # Last 20 messages
            'error': self.error,
            'is_complete': self.results is not None or self.error is not None
        }


def run_phase2_task(task_id: str, target_photo_path: str = None, fast_mode: bool = True):
    """Background task to run Phase 2 investigation."""
    task = phase2_tasks.get(task_id)
    if not task:
        return

    try:
        mode_str = "FAST MODE" if fast_mode else "standard mode"
        task.add_message(f'Starting Phase 2 investigation ({mode_str}) for {task.target_name}', 'info')
        task.add_message(f'Analyzing {len(task.selected_profiles)} selected profiles', 'info')

        # Initialize search service
        searcher = Phase2CombinedSearch()
        searcher.set_progress_callback(task.update_progress)

        # Run investigation - use fast mode by default
        if fast_mode:
            results = searcher.investigate_fast(
                selected_profiles=task.selected_profiles,
                target_name=task.target_name,
                target_photo_path=target_photo_path
            )
        else:
            results = searcher.investigate(
                selected_profiles=task.selected_profiles,
                target_name=task.target_name,
                target_photo_path=target_photo_path
            )

        # Store results
        task.results = results
        task.completed_at = datetime.now()
        task.percent_complete = 100
        task.current_step = 'Complete'

        elapsed = (task.completed_at - task.started_at).total_seconds()
        task.add_message(f'Investigation complete in {elapsed:.1f}s', 'success')
        task.add_message(f'Found {len(results.phones)} phones, {len(results.emails)} emails', 'success')

    except Exception as e:
        task.error = str(e)
        task.add_message(f'Error: {str(e)}', 'error')
        logger.error(f"Phase 2 task error: {e}", exc_info=True)


@phase2_bp.route('/')
def phase2_page():
    """Render Phase 2 page."""
    return render_template('phase2.html')


@phase2_bp.route('/start', methods=['POST'])
def start_investigation():
    """
    Start Phase 2 investigation (async).

    Request body (JSON):
    {
        "selected_profiles": [
            {"platform": "vk", "username": "pasha", "url": "https://vk.com/pasha"},
            ...
        ],
        "target_name": "Pavel Durov",
        "target_photo_path": "/path/to/photo.jpg",  (optional)
        "fast_mode": true  (optional, default true)
    }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({'error': 'No data provided'}), 400

        selected_profiles = data.get('selected_profiles', [])
        target_name = data.get('target_name', '')
        target_photo_path = data.get('target_photo_path')
        fast_mode = data.get('fast_mode', True)  # Default to fast mode

        # Validate
        if not selected_profiles:
            return jsonify({'error': 'No profiles selected'}), 400

        if len(selected_profiles) > 5:
            return jsonify({'error': 'Maximum 5 profiles allowed'}), 400

        if not target_name:
            return jsonify({'error': 'Target name required'}), 400

        # Resolve photo path if provided
        actual_photo_path = None
        if target_photo_path:
            # Handle both relative and absolute paths
            if target_photo_path.startswith('/phase1/uploads/'):
                filename = target_photo_path.replace('/phase1/uploads/', '')
                upload_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads')
                if not os.path.isabs(upload_folder):
                    upload_folder = os.path.join(current_app.root_path, upload_folder)
                actual_photo_path = os.path.join(upload_folder, filename)
            elif os.path.exists(target_photo_path):
                actual_photo_path = target_photo_path

        # Create task
        task_id = uuid.uuid4().hex
        task = Phase2TaskStatus(task_id, target_name, selected_profiles)
        phase2_tasks[task_id] = task

        # Start background thread
        thread = threading.Thread(
            target=run_phase2_task,
            args=(task_id, actual_photo_path, fast_mode)
        )
        thread.daemon = True
        thread.start()

        return jsonify({
            'success': True,
            'task_id': task_id
        })

    except Exception as e:
        logger.error(f"Phase 2 start error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@phase2_bp.route('/progress/<task_id>')
def get_progress(task_id):
    """Get task progress for polling."""
    task = phase2_tasks.get(task_id)

    if not task:
        return jsonify({'error': 'Task not found'}), 404

    return jsonify(task.to_dict())


@phase2_bp.route('/results/<task_id>')
def get_results(task_id):
    """Get full results for a completed task."""
    task = phase2_tasks.get(task_id)

    if not task:
        return jsonify({'error': 'Task not found'}), 404

    if task.error:
        return jsonify({'error': task.error}), 500

    if not task.results:
        return jsonify({'error': 'Task not complete'}), 400

    results = task.results

    # Convert to JSON-serializable format
    response = {
        'status': 'success',
        'task_id': task_id,
        'target_name': task.target_name,
        'results': {
            'phones': [
                {
                    'number': p.number,
                    'source': p.source,
                    'confidence': p.confidence,
                    'verified_on': p.verified_on
                }
                for p in results.phones
            ],
            'emails': [
                {
                    'email': e.email,
                    'source': e.source,
                    'confidence': e.confidence,
                    'verified_on': e.verified_on
                }
                for e in results.emails
            ],
            'additional_profiles': [
                {
                    'platform': p.platform,
                    'url': p.url,
                    'username': p.username,
                    'source': p.source
                }
                for p in results.additional_profiles
            ],
            'face_matches': [
                {
                    'platform': f.platform,
                    'profile_url': f.profile_url,
                    'username': f.username,
                    'similarity': f.similarity_score,
                    'thumbnail_url': f.thumbnail_url
                }
                for f in results.face_matches
            ]
        },
        'stats': results.stats,
        'errors': results.errors
    }

    return jsonify(response)


@phase2_bp.route('/api/investigate', methods=['POST'])
def investigate_sync():
    """
    Run Phase 2 investigation synchronously (for simpler clients).

    Request body:
    {
        "selected_profiles": [...],
        "target_name": "Pavel Durov",
        "target_photo_path": "/uploads/photo.jpg",  (optional)
        "fast_mode": true  (optional, default true)
    }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({'error': 'No data provided'}), 400

        selected_profiles = data.get('selected_profiles', [])
        target_name = data.get('target_name', '')
        target_photo_path = data.get('target_photo_path')
        fast_mode = data.get('fast_mode', True)  # Default to fast mode

        # Validate
        if not selected_profiles:
            return jsonify({'error': 'No profiles selected'}), 400

        if len(selected_profiles) > 5:
            return jsonify({'error': 'Maximum 5 profiles allowed'}), 400

        if not target_name:
            return jsonify({'error': 'Target name required'}), 400

        # Resolve photo path
        actual_photo_path = None
        if target_photo_path:
            if target_photo_path.startswith('/phase1/uploads/'):
                filename = target_photo_path.replace('/phase1/uploads/', '')
                upload_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads')
                if not os.path.isabs(upload_folder):
                    upload_folder = os.path.join(current_app.root_path, upload_folder)
                actual_photo_path = os.path.join(upload_folder, filename)
            elif os.path.exists(target_photo_path):
                actual_photo_path = target_photo_path

        # Run investigation - use fast mode by default
        searcher = Phase2CombinedSearch()
        if fast_mode:
            results = searcher.investigate_fast(
                selected_profiles=selected_profiles,
                target_name=target_name,
                target_photo_path=actual_photo_path
            )
        else:
            results = searcher.investigate(
                selected_profiles=selected_profiles,
                target_name=target_name,
                target_photo_path=actual_photo_path
            )

        # Convert to JSON-serializable format
        response = {
            'status': 'success',
            'results': {
                'phones': [
                    {
                        'number': p.number,
                        'source': p.source,
                        'confidence': p.confidence,
                        'verified_on': p.verified_on
                    }
                    for p in results.phones
                ],
                'emails': [
                    {
                        'email': e.email,
                        'source': e.source,
                        'confidence': e.confidence,
                        'verified_on': e.verified_on
                    }
                    for e in results.emails
                ],
                'additional_profiles': [
                    {
                        'platform': p.platform,
                        'url': p.url,
                        'username': p.username,
                        'source': p.source
                    }
                    for p in results.additional_profiles
                ],
                'face_matches': [
                    {
                        'platform': f.platform,
                        'profile_url': f.profile_url,
                        'username': f.username,
                        'similarity': f.similarity_score
                    }
                    for f in results.face_matches
                ]
            },
            'stats': results.stats,
            'errors': results.errors
        }

        return jsonify(response)

    except Exception as e:
        logger.error(f"Phase 2 investigation error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@phase2_bp.route('/status')
def get_status():
    """Get current system status."""
    return jsonify({
        'status': 'ready',
        'active_tasks': len([t for t in phase2_tasks.values() if not t.results and not t.error])
    })
