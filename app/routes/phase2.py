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

from app import db
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

    # Handle both dict results (from Buratino flow) and Phase2Results objects
    if isinstance(results, dict):
        # Results from Buratino flow - already a dict with different structure
        response = {
            'status': 'success',
            'task_id': task_id,
            'target_name': task.target_name,
            'results': results,
            'stats': results,
            'errors': []
        }
    else:
        # Results from Phase2Results object (original flow)
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


# ============================================
# BURATINO-STYLE ROUTES (Investigation-based)
# ============================================

@phase2_bp.route('/analyze/<investigation_id>')
def analyze_investigation(investigation_id):
    """
    Start Phase 2 analysis for a confirmed investigation.
    This is the entry point from Phase 1 Buratino flow.
    """
    from app.models import Investigation, SocialProfile

    investigation = Investigation.query.get(investigation_id)
    if not investigation:
        return render_template('error.html', error='Investigation not found'), 404

    # Get confirmed profile
    confirmed_profile = SocialProfile.query.filter_by(
        investigation_id=investigation_id,
        is_confirmed=True
    ).first()

    if not confirmed_profile:
        return render_template('error.html', error='No confirmed profile found'), 400

    return render_template('phase2_analyze.html',
                         investigation=investigation,
                         profile=confirmed_profile)


@phase2_bp.route('/buratino/results/<investigation_id>')
def buratino_results(investigation_id):
    """
    Display Phase 2 results with social graph visualization.
    """
    from app.models import Investigation, SocialProfile, Friend

    investigation = Investigation.query.get(investigation_id)
    if not investigation:
        return render_template('error.html', error='Investigation not found'), 404

    # Get confirmed profile
    confirmed_profile = SocialProfile.query.filter_by(
        investigation_id=investigation_id,
        is_confirmed=True
    ).first()

    # Get friends count
    friends_count = Friend.query.filter_by(investigation_id=investigation_id).count()

    return render_template('phase2_buratino_results.html',
                         investigation=investigation,
                         profile=confirmed_profile,
                         friends_count=friends_count)


@phase2_bp.route('/api/graph/<investigation_id>')
def get_graph_data(investigation_id):
    """
    Get social graph data in vis.js format.
    """
    from app.models import Investigation, SocialProfile, Friend
    from app.services.phase2.social_graph import SocialGraphBuilder

    investigation = Investigation.query.get(investigation_id)
    if not investigation:
        return jsonify({'error': 'Investigation not found'}), 404

    # Get confirmed profile
    confirmed_profile = SocialProfile.query.filter_by(
        investigation_id=investigation_id,
        is_confirmed=True
    ).first()

    if not confirmed_profile:
        return jsonify({'error': 'No confirmed profile'}), 400

    # Get friends
    friends = Friend.query.filter_by(investigation_id=investigation_id).all()

    # Build graph
    builder = SocialGraphBuilder()

    # If no friends, return demo graph
    if not friends:
        demo_name = f"{confirmed_profile.first_name or ''} {confirmed_profile.last_name or ''}"
        graph = builder.get_demo_graph(demo_name.strip() or "Пользователь")
        vis_data = builder.export_visjs(graph)
        vis_data['is_demo'] = True
        return jsonify(vis_data)

    # Build real graph from friends
    center_data = {
        'first_name': confirmed_profile.first_name,
        'last_name': confirmed_profile.last_name,
        'photo_100': confirmed_profile.photo_url,
        'city': {'title': confirmed_profile.city} if confirmed_profile.city else None
    }

    friend_data = [f.to_dict() for f in friends]

    graph = builder.build_from_friends(
        center_vk_id=int(confirmed_profile.platform_id),
        center_data=center_data,
        friends=friend_data
    )

    vis_data = builder.export_visjs(graph)
    vis_data['is_demo'] = False

    return jsonify(vis_data)


@phase2_bp.route('/api/start-analysis/<investigation_id>', methods=['POST'])
def start_buratino_analysis(investigation_id):
    """
    Start Phase 2 analysis for an investigation (async).
    Extracts friends AND contacts from the confirmed VK profile.
    """
    from app.models import Investigation, SocialProfile

    investigation = Investigation.query.get(investigation_id)
    if not investigation:
        return jsonify({'error': 'Investigation not found'}), 404

    confirmed_profile = SocialProfile.query.filter_by(
        investigation_id=investigation_id,
        is_confirmed=True
    ).first()

    if not confirmed_profile:
        return jsonify({'error': 'No confirmed profile'}), 400

    # Create a task for background processing
    task_id = uuid.uuid4().hex

    # Get app reference for background thread
    app = current_app._get_current_object()

    # Store data needed for background task (avoid passing SQLAlchemy objects)
    vk_id = int(confirmed_profile.platform_id)
    input_name = investigation.input_name
    username = confirmed_profile.username or confirmed_profile.platform_id
    profile_url = f"https://vk.com/id{vk_id}"
    if confirmed_profile.username:
        profile_url = f"https://vk.com/{confirmed_profile.username}"

    def run_analysis(app, investigation_id, vk_id, input_name, username, profile_url, task_id):
        with app.app_context():
            try:
                from app import db
                from app.models import Investigation, Friend
                from app.services.phase1.buratino_vk_search import buratino_vk_search

                # Import contact discovery services
                from app.services.phase2.vk_api_extractor import VKAPIExtractor
                from app.services.phase2.email_generator import generate_email_candidates, generate_from_username
                from app.services.phase2.gravatar_lookup import check_gravatar
                import os
                import time

                task = phase2_tasks[task_id]

                # Re-query investigation inside app context
                investigation = Investigation.query.get(investigation_id)
                if not investigation:
                    raise Exception('Investigation not found')

                discovered_phones = []
                discovered_emails = []
                alternate_accounts = []

                # ===== STEP 1: VK API Contact Extraction =====
                task.add_message('Extracting contacts from VK profile...', 'info')
                task.update_progress('VK Contact Extraction', 10)

                try:
                    vk_token = os.environ.get('VK_SERVICE_TOKEN')
                    extractor = VKAPIExtractor(access_token=vk_token)
                    vk_contact = extractor.extract_from_url(profile_url)

                    if not vk_contact.error:
                        # Add phones from VK profile
                        for phone in vk_contact.phones:
                            discovered_phones.append({
                                'number': phone,
                                'source': 'VK Profile',
                                'confidence': 'high',
                                'verified_on': ['vk']
                            })
                            task.add_message(f'Found phone: {phone}', 'success')

                        # Add emails from VK profile
                        for email in vk_contact.emails:
                            discovered_emails.append({
                                'email': email,
                                'source': 'VK Profile',
                                'confidence': 'high',
                                'verified_on': ['vk']
                            })
                            task.add_message(f'Found email: {email}', 'success')

                        # Add linked social accounts
                        if vk_contact.telegram:
                            alternate_accounts.append({
                                'platform': 'telegram',
                                'username': vk_contact.telegram,
                                'url': f'https://t.me/{vk_contact.telegram}',
                                'source': 'VK Profile connections'
                            })
                            task.add_message(f'Found Telegram: @{vk_contact.telegram}', 'success')

                        if vk_contact.instagram:
                            alternate_accounts.append({
                                'platform': 'instagram',
                                'username': vk_contact.instagram,
                                'url': f'https://instagram.com/{vk_contact.instagram}',
                                'source': 'VK Profile connections'
                            })
                            task.add_message(f'Found Instagram: @{vk_contact.instagram}', 'success')

                        if vk_contact.twitter:
                            alternate_accounts.append({
                                'platform': 'twitter',
                                'username': vk_contact.twitter,
                                'url': f'https://twitter.com/{vk_contact.twitter}',
                                'source': 'VK Profile connections'
                            })

                        if vk_contact.facebook:
                            alternate_accounts.append({
                                'platform': 'facebook',
                                'username': vk_contact.facebook,
                                'url': f'https://facebook.com/{vk_contact.facebook}',
                                'source': 'VK Profile connections'
                            })

                        if vk_contact.skype:
                            alternate_accounts.append({
                                'platform': 'skype',
                                'username': vk_contact.skype,
                                'url': f'skype:{vk_contact.skype}',
                                'source': 'VK Profile connections'
                            })

                        # Add websites
                        for website in vk_contact.websites:
                            alternate_accounts.append({
                                'platform': 'website',
                                'username': website,
                                'url': website if website.startswith('http') else f'https://{website}',
                                'source': 'VK Profile site field'
                            })

                        logger.info(f"VK extraction: {len(vk_contact.phones)} phones, {len(vk_contact.emails)} emails")
                    else:
                        task.add_message(f'VK extraction limited: {vk_contact.error}', 'warning')

                except Exception as e:
                    logger.warning(f"VK extraction error: {e}")
                    task.add_message(f'VK extraction error: {str(e)[:50]}', 'warning')

                # ===== STEP 2: Collect ALL Usernames =====
                task.add_message('Collecting usernames for email generation...', 'info')
                task.update_progress('Collecting usernames', 20)

                # Collect ALL discovered usernames for email generation
                all_usernames = []
                if username:
                    all_usernames.append(username)

                # Add usernames from discovered accounts
                for acc in alternate_accounts:
                    acc_username = acc.get('username', '')
                    if acc_username and acc_username not in all_usernames:
                        all_usernames.append(acc_username)

                task.add_message(f'Found {len(all_usernames)} usernames: {all_usernames[:5]}', 'info')

                # ===== STEP 3: Generate Smart Email Candidates =====
                task.add_message('Generating email candidates with name patterns + diminutives...', 'info')
                task.update_progress('Email Generation', 25)

                try:
                    # Import enhanced email generator
                    from app.services.phase2.email_generator import (
                        generate_smart_email_candidates,
                        verify_email_candidates
                    )

                    # Parse name
                    name_parts = input_name.strip().split()
                    first_name = name_parts[0] if name_parts else ""
                    last_name = name_parts[-1] if len(name_parts) > 1 else ""

                    # Generate candidates with ALL usernames and diminutives
                    email_candidates = generate_smart_email_candidates(
                        first_name=first_name,
                        last_name=last_name,
                        usernames=all_usernames,
                        max_candidates=50
                    )

                    task.add_message(f'Generated {len(email_candidates)} prioritized email candidates', 'info')
                    if email_candidates:
                        sample = [c['email'] for c in email_candidates[:3]]
                        task.add_message(f'Top candidates: {sample}', 'info')

                except Exception as e:
                    logger.warning(f"Email generation error: {e}")
                    email_candidates = []

                # ===== STEP 4: SMTP Verification (with fallback) =====
                task.add_message('Verifying emails...', 'info')
                task.update_progress('Email Verification', 35)

                smtp_verified_count = 0
                smtp_attempted = False

                try:
                    from app.services.phase2.email_generator import smtp_verify_email, CATCH_ALL_DOMAINS

                    # Domains that block SMTP verification (same as in smtp_verify_email)
                    BLOCKED_DOMAINS = {'mail.ru', 'bk.ru', 'list.ru', 'inbox.ru', 'yandex.ru', 'ya.ru'}

                    # Find a testable email (not from blocked or catch-all domain)
                    test_result = None
                    test_email = None
                    for candidate in email_candidates[:10]:
                        email = candidate['email']
                        domain = email.split('@')[1] if '@' in email else ''
                        if domain and domain not in BLOCKED_DOMAINS and domain not in CATCH_ALL_DOMAINS:
                            test_email = email
                            test_result = smtp_verify_email(email, timeout=5)
                            if test_result is not None:
                                break  # Found a testable domain

                    if test_result is not None:
                        # SMTP verification working - use it
                        smtp_attempted = True
                        task.add_message('SMTP verification available, checking emails...', 'info')

                        verified_candidates = verify_email_candidates(
                            email_candidates,
                            max_to_verify=15,
                            delay=0.8
                        )

                        for candidate in verified_candidates:
                            verification = candidate.get('verification', 'unverified')

                            if verification == 'smtp_verified':
                                smtp_verified_count += 1
                                discovered_emails.append({
                                    'email': candidate['email'],
                                    'source': candidate.get('source', 'Email pattern'),
                                    'confidence': 'high',
                                    'verified_on': ['smtp'],
                                    'verification': 'smtp_verified'
                                })
                                task.add_message(f'SMTP verified: {candidate["email"]}', 'success')

                            elif verification in ('catch_all_domain', 'likely'):
                                # Both catch-all and blocked domains (mail.ru, yandex.ru) are marked "likely"
                                discovered_emails.append({
                                    'email': candidate['email'],
                                    'source': candidate.get('source', 'Email pattern'),
                                    'confidence': 'medium',
                                    'verified_on': [],
                                    'verification': 'likely'
                                })

                            elif verification in ('inconclusive', 'unchecked'):
                                # Emails we couldn't verify - keep but mark appropriately
                                priority = candidate.get('priority', 99)
                                if priority <= 3:  # Keep high priority patterns
                                    discovered_emails.append({
                                        'email': candidate['email'],
                                        'source': candidate.get('source', 'Email pattern'),
                                        'confidence': 'low',
                                        'verified_on': [],
                                        'verification': 'pattern'
                                    })
                    else:
                        # SMTP blocked - use pattern-based confidence
                        task.add_message('SMTP verification unavailable (blocked by mail servers)', 'warning')
                        task.add_message('Using pattern-based confidence instead...', 'info')

                        for candidate in email_candidates:
                            priority = candidate.get('priority', 99)

                            # Priority 1-2: High quality patterns - mark as "likely"
                            if priority <= 2:
                                discovered_emails.append({
                                    'email': candidate['email'],
                                    'source': candidate.get('source', 'Email pattern'),
                                    'confidence': 'medium',
                                    'verified_on': [],
                                    'verification': 'likely'
                                })
                            # Priority 3-4: Diminutive/username patterns - mark as "possible"
                            elif priority <= 4 and len(discovered_emails) < 15:
                                discovered_emails.append({
                                    'email': candidate['email'],
                                    'source': candidate.get('source', 'Email pattern'),
                                    'confidence': 'low',
                                    'verified_on': [],
                                    'verification': 'pattern'
                                })

                    if smtp_attempted:
                        task.add_message(f'SMTP verified {smtp_verified_count} emails', 'info')
                    else:
                        task.add_message(f'Added {len(discovered_emails)} pattern-based email candidates', 'info')

                except Exception as e:
                    logger.warning(f"Email verification error: {e}")
                    # Fallback: add top candidates based on priority
                    for candidate in email_candidates[:12]:
                        priority = candidate.get('priority', 99)
                        discovered_emails.append({
                            'email': candidate['email'],
                            'source': candidate.get('source', 'Email pattern'),
                            'confidence': 'medium' if priority <= 2 else 'low',
                            'verified_on': [],
                            'verification': 'pattern'
                        })

                # ===== STEP 5: Gravatar Check on Verified Emails =====
                task.add_message('Checking Gravatar profiles...', 'info')
                task.update_progress('Gravatar Check', 50)

                gravatar_verified = 0
                try:
                    # Check Gravatar for high-confidence emails first
                    emails_to_check = [e['email'] for e in discovered_emails if e.get('confidence') in ['high', 'medium']][:15]

                    for i, email in enumerate(emails_to_check):
                        try:
                            gravatar = check_gravatar(email)
                            if gravatar.exists:
                                gravatar_verified += 1
                                # Update the email's verified_on list
                                for disc_email in discovered_emails:
                                    if disc_email['email'].lower() == email.lower():
                                        if 'gravatar' not in disc_email.get('verified_on', []):
                                            disc_email['verified_on'] = disc_email.get('verified_on', []) + ['gravatar']
                                        disc_email['confidence'] = 'high'
                                        break

                                task.add_message(f'Gravatar found: {email}', 'success')

                                # Add linked accounts from Gravatar
                                for account in gravatar.accounts:
                                    if account.get('url'):
                                        alternate_accounts.append({
                                            'platform': account.get('domain', 'unknown'),
                                            'username': account.get('username', ''),
                                            'url': account['url'],
                                            'source': f'Gravatar ({email})'
                                        })

                            time.sleep(0.2)

                        except Exception as e:
                            logger.debug(f"Gravatar check error for {email}: {e}")

                        if i % 5 == 0:
                            task.update_progress(f'Gravatar check ({i+1}/{len(emails_to_check)})', 50 + (i * 2))

                    task.add_message(f'Gravatar verified {gravatar_verified} emails', 'info')

                except Exception as e:
                    logger.warning(f"Gravatar verification error: {e}")

                # ===== STEP 5.5: Run SourceManager (Breach DB + Holehe) =====
                task.add_message('Running breach database & verification sources...', 'info')
                task.update_progress('Breach Database Search', 60)

                try:
                    from app.services.phase2.source_manager import SourceManager

                    sm = SourceManager(max_workers=4, timeout=120.0)

                    # Collect emails found so far for breach checking
                    known_emails = [e['email'] for e in discovered_emails]
                    # Also add top email candidates that weren't yet verified
                    email_cands_for_sm = []
                    for c in email_candidates[:10]:
                        addr = c['email'] if isinstance(c, dict) else str(c)
                        if addr not in known_emails:
                            email_cands_for_sm.append(c)

                    # Collect passwords found by breach sources for HIBP validation
                    # (will be populated by HudsonRock results through cross-source flow)

                    sm_results = sm.run_all(
                        name=input_name,
                        email=known_emails[0] if known_emails else None,
                        username=username,
                        vk_id=str(vk_id),
                        email_candidates=email_cands_for_sm,
                    )

                    sm_email_count = 0
                    sm_phone_count = 0
                    sm_profile_count = 0
                    sm_credential_count = 0

                    # Merge email results from SourceManager
                    for sr in sm_results.get('email', []):
                        # Check if this email is already discovered
                        if sr.value.lower() not in {e['email'].lower() for e in discovered_emails}:
                            discovered_emails.append({
                                'email': sr.value,
                                'source': sr.source_name,
                                'confidence': sr.confidence_label,
                                'verified_on': ['breach'] if sr.verified else [],
                                'verification': sr.metadata.get('verification', 'breach_found'),
                                'metadata': {
                                    k: v for k, v in sr.metadata.items()
                                    if k not in ('sources', 'source_count')
                                },
                            })
                            sm_email_count += 1
                        else:
                            # Email already known — boost its confidence if breach-confirmed
                            if sr.verified:
                                for disc in discovered_emails:
                                    if disc['email'].lower() == sr.value.lower():
                                        if 'breach' not in disc.get('verified_on', []):
                                            disc['verified_on'] = disc.get('verified_on', []) + ['breach']
                                        disc['confidence'] = 'high'
                                        disc['verification'] = sr.metadata.get('verification', disc.get('verification', ''))
                                        break

                    # Merge phone results
                    for sr in sm_results.get('phone', []):
                        if sr.value not in {p['number'] for p in discovered_phones}:
                            discovered_phones.append({
                                'number': sr.value,
                                'source': sr.source_name,
                                'confidence': sr.confidence_label,
                                'verified_on': ['breach'] if sr.verified else [],
                            })
                            sm_phone_count += 1

                    # Merge username/profile results
                    for sr in sm_results.get('username', []):
                        alternate_accounts.append({
                            'platform': 'unknown',
                            'username': sr.value,
                            'url': '',
                            'source': sr.source_name,
                        })
                        sm_profile_count += 1

                    for sr in sm_results.get('profile', []):
                        if sr.value not in {a.get('url', '') for a in alternate_accounts}:
                            alternate_accounts.append({
                                'platform': sr.metadata.get('platform', 'unknown'),
                                'username': sr.metadata.get('email_used', ''),
                                'url': sr.value,
                                'source': sr.source_name,
                            })
                            sm_profile_count += 1

                    # Count credentials found
                    for sr in sm_results.get('credential', []):
                        sm_credential_count += 1

                    # Store credential data in investigation metadata
                    credential_results = sm_results.get('credential', [])
                    if credential_results:
                        breach_credentials = []
                        for sr in credential_results:
                            breach_credentials.append({
                                'username': sr.value,
                                'url': sr.raw_data.get('url', ''),
                                'source': sr.source_name,
                                'date': sr.metadata.get('date_compromised', ''),
                            })

                    if sm_email_count or sm_phone_count or sm_profile_count or sm_credential_count:
                        task.add_message(
                            f'SourceManager found: {sm_email_count} emails, '
                            f'{sm_phone_count} phones, {sm_profile_count} profiles, '
                            f'{sm_credential_count} credentials',
                            'success'
                        )
                    else:
                        task.add_message('No new data from breach sources', 'info')

                except Exception as e:
                    logger.warning(f"SourceManager error: {e}", exc_info=True)
                    task.add_message(f'Breach source error: {str(e)[:80]}', 'warning')

                # ===== STEP 5.5: Phone Discovery Service =====
                task.add_message('Running phone discovery service...', 'info')
                task.update_progress('Phone Discovery', 65)

                try:
                    from app.services.phase2.phone_discovery import PhoneDiscoveryService

                    phone_service = PhoneDiscoveryService(max_candidates=50, verify_timeout=10.0)

                    phone_results = phone_service.discover_sync(
                        first_name=first_name if first_name else input_name.split()[0],
                        last_name=last_name if last_name else (input_name.split()[-1] if len(input_name.split()) > 1 else ''),
                        usernames=all_usernames,
                        profile_urls=[{'url': profile_url, 'platform': 'vk'}],
                        emails=[e['email'] for e in discovered_emails if 'email' in e]
                    )

                    new_phone_count = 0
                    for dp in phone_results.phones:
                        # Deduplicate against already-found phones
                        normalized = dp.number.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
                        if normalized not in {p['number'].replace(' ', '').replace('-', '').replace('(', '').replace(')', '') for p in discovered_phones}:
                            discovered_phones.append({
                                'number': dp.number,
                                'source': dp.source,
                                'confidence': dp.confidence,
                                'verified_on': [],
                                'carrier': dp.carrier or '',
                                'region': dp.region or '',
                            })
                            new_phone_count += 1

                    if new_phone_count:
                        task.add_message(f'Phone discovery found {new_phone_count} new phone numbers', 'success')
                    else:
                        task.add_message(f'Phone discovery: {phone_results.candidates_generated} candidates checked, no new phones', 'info')

                    phone_service.close()

                except Exception as e:
                    logger.warning(f"Phone discovery error: {e}")
                    task.add_message(f'Phone discovery error: {str(e)[:80]}', 'warning')

                # ===== STEP 6: Extract Friends =====
                task.add_message('Extracting friends network...', 'info')
                task.update_progress('Friends Extraction', 70)

                friends_data = buratino_vk_search.fetch_friends(vk_id)
                task.add_message(f'Found {len(friends_data)} friends', 'info')

                # Save friends to database
                for friend in friends_data:
                    f = Friend(
                        investigation_id=investigation_id,
                        platform='vk',
                        platform_id=str(friend.get('id', '')),
                        first_name=friend.get('first_name', ''),
                        last_name=friend.get('last_name', ''),
                        city=friend.get('city', {}).get('title') if isinstance(friend.get('city'), dict) else friend.get('city'),
                        photo_url=friend.get('photo_100') or friend.get('photo_url')
                    )
                    db.session.add(f)

                task.update_progress('Saving results', 90)

                # ===== STEP 7: Save Discovered Contacts =====
                # Deduplicate phones
                seen_phones = set()
                unique_phones = []
                for phone in discovered_phones:
                    normalized = phone['number'].replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
                    if normalized not in seen_phones:
                        seen_phones.add(normalized)
                        unique_phones.append(phone)

                # Deduplicate emails
                seen_emails = set()
                unique_emails = []
                for email in discovered_emails:
                    key = email['email'].lower()
                    if key not in seen_emails:
                        seen_emails.add(key)
                        unique_emails.append(email)

                # Deduplicate profiles
                seen_urls = set()
                unique_accounts = []
                for acc in alternate_accounts:
                    key = acc.get('url', '').lower()
                    if key and key not in seen_urls:
                        seen_urls.add(key)
                        unique_accounts.append(acc)

                # Update investigation with discovered contacts
                investigation.discovered_phones = unique_phones
                investigation.discovered_emails = unique_emails
                investigation.alternate_accounts = unique_accounts
                investigation.status = 'phase_2_complete'

                db.session.commit()
                task.add_message('Analysis complete!', 'success')

                # Final stats
                results = {
                    'friends_count': len(friends_data),
                    'phones_found': len(unique_phones),
                    'emails_found': len(unique_emails),
                    'profiles_found': len(unique_accounts)
                }

                task.results = results
                task.completed_at = datetime.now()
                task.update_progress('Complete', 100)

                logger.info(f"Phase 2 complete: {results}")

            except Exception as e:
                logger.error(f"Phase 2 analysis error: {e}", exc_info=True)
                phase2_tasks[task_id].error = str(e)

    # Create task status
    task = Phase2TaskStatus(task_id, input_name, [])
    task.add_message('Starting Phase 2 analysis...', 'info')
    phase2_tasks[task_id] = task

    # Start background thread with app context
    thread = threading.Thread(
        target=run_analysis,
        args=(app, investigation_id, vk_id, input_name, username, profile_url, task_id)
    )
    thread.daemon = True
    thread.start()

    return jsonify({'success': True, 'task_id': task_id})


@phase2_bp.route('/results/<investigation_id>')
def results_by_investigation(investigation_id):
    """
    Display Phase 2 results for a specific investigation.
    Redirects to buratino_results for consistency.
    """
    return buratino_results(investigation_id)


# ============================================
# SOURCE PLUGIN SYSTEM API ROUTES
# ============================================

@phase2_bp.route('/api/sources/status')
def get_sources_status():
    """
    Get status of all Phase 2 data source plugins.
    Shows which sources are configured, available, and their tiers.
    """
    try:
        from app.services.phase2.source_manager import SourceManager
        manager = SourceManager()
        return jsonify({
            'status': 'ok',
            'sources': manager.get_source_status(),
            'total': len(manager.sources),
            'available': len([s for s in manager.sources if s.is_available()]),
        })
    except Exception as e:
        logger.error(f"Source status error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@phase2_bp.route('/api/telegram/status')
def get_telegram_status():
    """
    Get Telegram session manager status.
    Returns whether Telegram is configured and connected.
    """
    try:
        from app.services.telegram.session_manager import TelegramSessionManager
        status = TelegramSessionManager.get_status()
        return jsonify({
            'status': 'ok',
            'telegram': status,
        })
    except ImportError:
        return jsonify({
            'status': 'ok',
            'telegram': {
                'configured': False,
                'client_exists': False,
                'connected': False,
                'error': 'telethon not installed',
            },
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e),
        }), 500
