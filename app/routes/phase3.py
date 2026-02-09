"""
Phase 3 Routes - Deep Investigation
===================================
Business records, court cases, geo-information, text analysis.

Buratino-style integration with Investigation model.
"""

import logging
import uuid
import threading
from datetime import datetime
from flask import Blueprint, render_template, request, jsonify

from app import db

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
    """
    Background task to run Phase 3 investigation.

    Uses Phase3CombinedSearch orchestrator for Буратино-style deep investigation.
    """
    task = phase3_tasks.get(task_id)
    if not task:
        return

    try:
        task.add_message(f'Starting Phase 3 deep investigation for {task.target_name}', 'info')

        # Get investigation data
        profiles = task.investigation_data.get('profiles', [])
        contacts = task.investigation_data.get('contacts', {})
        target_name = task.target_name

        # Use Phase 3 Combined Search orchestrator
        from app.services.phase3.combined_search import Phase3CombinedSearch

        searcher = Phase3CombinedSearch()

        # Progress callback
        def update_progress(step: str, percent: int):
            task.current_step = step
            task.percent_complete = percent
            task.add_message(step, 'info')

        searcher.set_progress_callback(update_progress)

        # Run the investigation
        phase3_results = searcher.investigate(
            target_name=target_name,
            confirmed_profiles=profiles,
            discovered_contacts=contacts,
            search_business=True,
            search_courts=True,
            build_social_graph=True,
            analyze_text=True
        )

        # Convert results to dict format
        results = phase3_results.to_dict()

        # Add summary messages
        stats = results.get('stats', {})
        task.add_message(f"Found {stats.get('business_records_found', 0)} business records", 'success')
        task.add_message(f"Found {stats.get('court_cases_found', 0)} court cases", 'success')
        task.add_message(f"Found {stats.get('social_connections_found', 0)} social connections", 'success')
        task.add_message(f"Risk level: {stats.get('overall_risk', 'unknown')}", 'info')

        # Complete
        task.results = results
        task.completed_at = datetime.now()
        task.percent_complete = 100
        task.current_step = 'Complete'

        elapsed = (task.completed_at - task.started_at).total_seconds()
        task.add_message(f'Phase 3 deep investigation complete in {elapsed:.1f}s', 'success')

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


@phase3_bp.route('/api/results/<task_id>')
def get_results(task_id):
    """Get full results for a completed task (API)."""
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


# ============================================
# BURATINO-STYLE ROUTES (Investigation-based)
# ============================================

@phase3_bp.route('/buratino/<investigation_id>')
def buratino_page(investigation_id):
    """Phase 3 start page for Buratino flow - uses database investigation."""
    from app.models import Investigation, SocialProfile

    investigation = Investigation.query.get(investigation_id)
    if not investigation:
        return render_template('error.html', error='Investigation not found'), 404

    confirmed_profile = SocialProfile.query.filter_by(
        investigation_id=investigation_id,
        is_confirmed=True
    ).first()

    return render_template('phase3_buratino.html',
                         investigation=investigation,
                         profile=confirmed_profile)


@phase3_bp.route('/api/buratino/start/<investigation_id>', methods=['POST'])
def start_buratino_investigation(investigation_id):
    """Start Phase 3 investigation for a Buratino-flow investigation."""
    from flask import current_app
    from app.models import Investigation, SocialProfile

    investigation = Investigation.query.get(investigation_id)
    if not investigation:
        return jsonify({'error': 'Investigation not found'}), 404

    confirmed_profile = SocialProfile.query.filter_by(
        investigation_id=investigation_id,
        is_confirmed=True
    ).first()

    task_id = uuid.uuid4().hex

    # Get app reference for background thread
    app = current_app._get_current_object()

    # Store data needed for background task (avoid passing SQLAlchemy objects)
    input_name = investigation.input_name
    profile_data = None
    if confirmed_profile:
        profile_data = {
            'platform': confirmed_profile.platform,
            'username': confirmed_profile.username,
            'full_name': confirmed_profile.full_name,
            'bio': confirmed_profile.bio,
            'platform_id': confirmed_profile.platform_id
        }

    def run_buratino_phase3(app, investigation_id, input_name, profile_data, task_id):
        with app.app_context():
            try:
                from app import db
                from app.models import Investigation, BusinessRecord as DBBusinessRecord, CourtRecord as DBCourtRecord
                from app.services.phase3.combined_search import Phase3CombinedSearch

                # Re-query investigation inside app context
                investigation = Investigation.query.get(investigation_id)
                if not investigation:
                    raise Exception('Investigation not found')

                task = phase3_tasks[task_id]
                task.add_message('Starting Phase 3 deep investigation', 'info')

                # Prepare profile data
                profiles = []
                if profile_data:
                    profiles.append({
                        'platform': profile_data['platform'],
                        'username': profile_data['username'],
                        'full_name': profile_data['full_name'],
                        'bio': profile_data['bio'],
                        'url': f"https://vk.com/id{profile_data['platform_id']}"
                    })

                # Get discovered contacts from Phase 2
                contacts = {
                    'phones': investigation.discovered_phones or [],
                    'emails': investigation.discovered_emails or []
                }

                # Run investigation
                searcher = Phase3CombinedSearch()
                searcher.set_progress_callback(
                    lambda step, pct: (setattr(task, 'current_step', step), setattr(task, 'percent_complete', pct), task.add_message(step, 'info'))
                )

                results = searcher.investigate(
                    target_name=input_name,
                    confirmed_profiles=profiles,
                    discovered_contacts=contacts,
                    search_business=True,
                    search_courts=True,
                    build_social_graph=True,
                    analyze_text=True
                )

                # Save business records to database
                for biz in results.business_records:
                    db_record = DBBusinessRecord(
                        investigation_id=investigation_id,
                        company_name=biz.company_name,
                        inn=biz.inn,
                        ogrn=biz.ogrn,
                        role=biz.role,
                        status=biz.status,
                        legal_address=biz.address,
                        source=biz.source,
                        source_url=biz.url
                    )
                    # Parse registration date if it's a string
                    if biz.registration_date:
                        try:
                            from dateutil.parser import parse
                            db_record.registration_date = parse(biz.registration_date).date()
                        except:
                            pass
                    db.session.add(db_record)

                # Save court records to database
                for court in results.court_cases:
                    db_court = DBCourtRecord(
                        investigation_id=investigation_id,
                        case_number=court.case_number,
                        court_name=court.court_name,
                        category=court.case_type,  # case_type → category
                        person_role=court.role,
                        subcategory=court.category,  # category → subcategory
                        decision_summary=court.result,
                        source=court.source,
                        source_url=court.url
                    )
                    db.session.add(db_court)

                # Save FSSP enforcement proceedings to investigation JSON
                investigation.property_records = [e.to_dict() for e in results.enforcement_proceedings]

                # Save risk indicators and manual links to investigation JSON
                investigation.risk_indicators = [r.to_dict() for r in results.risk_indicators]
                investigation.additional_findings = [l.to_dict() for l in results.manual_search_links]

                # Update investigation status
                investigation.status = 'phase_3_complete'
                db.session.commit()

                task.results = results.to_dict()
                task.completed_at = datetime.now()
                task.percent_complete = 100
                task.current_step = 'Complete'

                elapsed = (task.completed_at - task.started_at).total_seconds()
                task.add_message(f'Phase 3 complete in {elapsed:.1f}s', 'success')

            except Exception as e:
                logger.error(f"Buratino Phase 3 error: {e}", exc_info=True)
                phase3_tasks[task_id].error = str(e)
                phase3_tasks[task_id].add_message(f'Error: {str(e)}', 'error')

    # Create task
    task = Phase3TaskStatus(task_id, {
        'target_name': input_name,
        'investigation_id': investigation_id
    })
    phase3_tasks[task_id] = task

    # Start background thread with app context
    thread = threading.Thread(target=run_buratino_phase3, args=(app, investigation_id, input_name, profile_data, task_id))
    thread.daemon = True
    thread.start()

    return jsonify({'success': True, 'task_id': task_id})


@phase3_bp.route('/buratino/results/<investigation_id>')
def buratino_results(investigation_id):
    """Display Phase 3 results for Buratino flow."""
    from app.models import Investigation, SocialProfile, BusinessRecord as DBBusinessRecord, CourtRecord as DBCourtRecord
    from urllib.parse import quote

    investigation = Investigation.query.get(investigation_id)
    if not investigation:
        return render_template('error.html', error='Investigation not found'), 404

    confirmed_profile = SocialProfile.query.filter_by(
        investigation_id=investigation_id,
        is_confirmed=True
    ).first()

    business_records = DBBusinessRecord.query.filter_by(investigation_id=investigation_id).all()
    court_records = DBCourtRecord.query.filter_by(investigation_id=investigation_id).all()

    # Get FSSP, risk indicators, and manual links from investigation JSON
    enforcement_proceedings = investigation.property_records or []
    risk_indicators = investigation.risk_indicators or []
    manual_search_links = investigation.additional_findings or []

    # Generate manual links if not stored yet
    if not manual_search_links:
        name = investigation.input_name or ''
        encoded = quote(name)
        manual_search_links = [
            {'name': 'ЕГРЮЛ (ФНС)', 'url': 'https://egrul.nalog.ru/', 'description': 'Реестр юрлиц и ИП'},
            {'name': 'Rusprofile.ru', 'url': f'https://www.rusprofile.ru/search?query={encoded}&type=person', 'description': 'Поиск компаний'},
            {'name': 'ФССП', 'url': 'https://fssp.gov.ru/iss/ip', 'description': 'Исполнительные производства'},
            {'name': 'Sudact.ru', 'url': f'https://sudact.ru/regular/doc/?regular-txt={encoded}', 'description': 'Судебные акты'},
            {'name': 'Арбитраж', 'url': 'https://kad.arbitr.ru/', 'description': 'Арбитражные дела'},
            {'name': 'ЕГРЮЛ (ФНС)', 'url': 'https://egrul.nalog.ru/', 'description': 'Официальный реестр'},
        ]

    return render_template('phase3_buratino_results.html',
                         investigation=investigation,
                         profile=confirmed_profile,
                         business_records=business_records,
                         court_records=court_records,
                         enforcement_proceedings=enforcement_proceedings,
                         risk_indicators=risk_indicators,
                         manual_search_links=manual_search_links)
