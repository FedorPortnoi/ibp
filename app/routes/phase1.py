"""
IBP Phase 1 Routes - VK People Search (Buratino-style)
======================================================
Person-first investigation: Name → VK Search → Select Profile → Confirm
"""

from flask import Blueprint, render_template, request, jsonify, send_from_directory, current_app
from werkzeug.utils import secure_filename
import os
import uuid
from datetime import datetime

from app import db
from app.models import Investigation, SocialProfile

phase1_bp = Blueprint('phase1', __name__, url_prefix='/phase1')


# ============================================
# HELPER FUNCTIONS
# ============================================

def allowed_file(filename):
    """Check if file extension is allowed."""
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_upload_folder():
    """Get the upload folder path."""
    upload_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads')
    if not os.path.isabs(upload_folder):
        upload_folder = os.path.join(current_app.root_path, upload_folder)
    os.makedirs(upload_folder, exist_ok=True)
    return upload_folder


# ============================================
# BURATINO-STYLE ROUTES (VK People Search)
# ============================================

@phase1_bp.route('/')
def index():
    """Redirect to new investigation page."""
    return new_investigation()


@phase1_bp.route('/new', methods=['GET', 'POST'])
def new_investigation():
    """
    Start a new Buratino-style investigation.

    GET: Show the input form
    POST: Create investigation and run VK search
    """
    if request.method == 'POST':
        # Get form data with sanitization
        import re as _re
        target_name = request.form.get('target_name', '').strip()[:100]
        city = request.form.get('city', '').strip()[:100] or None
        age_from = request.form.get('age_from', type=int)
        age_to = request.form.get('age_to', type=int)

        # Reject HTML/script tags
        if _re.search(r'<[^>]+>', target_name):
            target_name = _re.sub(r'<[^>]+>', '', target_name).strip()
        if city and _re.search(r'<[^>]+>', city):
            city = _re.sub(r'<[^>]+>', '', city).strip() or None

        if not target_name:
            return jsonify({'error': 'Имя обязательно'}), 400

        # Handle photo upload
        photo_path = None
        if 'photo' in request.files:
            file = request.files['photo']
            if file and file.filename and allowed_file(file.filename):
                photo_filename = secure_filename(f"{uuid.uuid4().hex}_{file.filename}")
                upload_folder = get_upload_folder()
                photo_path = os.path.join(upload_folder, photo_filename)
                file.save(photo_path)

        # Create investigation
        investigation_id = uuid.uuid4().hex
        investigation = Investigation(
            id=investigation_id,
            input_name=target_name,
            input_photo_path=photo_path,
            status='phase_1'
        )

        # Store filters in phase1_stats
        investigation.phase1_stats = {
            'city': city,
            'age_from': age_from,
            'age_to': age_to,
            'search_started_at': datetime.now().isoformat()
        }

        db.session.add(investigation)
        db.session.commit()

        # Redirect to search results page
        return jsonify({
            'success': True,
            'investigation_id': investigation_id,
            'redirect': f'/phase1/search/{investigation_id}'
        })

    # GET: Show the form
    return render_template('phase1_buratino_new.html')


@phase1_bp.route('/search/<investigation_id>')
def buratino_search_results(investigation_id):
    """
    Run VK + OK People Search and show results for selection.
    """
    investigation = Investigation.query.get_or_404(investigation_id)

    # Get search parameters
    stats = investigation.phase1_stats
    city = stats.get('city') or None  # None = search all cities
    age_from = stats.get('age_from')
    age_to = stats.get('age_to')

    # Run VK search if not already done
    existing_vk = SocialProfile.query.filter_by(
        investigation_id=investigation_id,
        platform='vk'
    ).all()

    if not existing_vk:
        # Import and run Buratino VK search
        from app.services.phase1.buratino_vk_search import buratino_vk_search

        buratino_vk_search.search_and_save(
            investigation_id=investigation_id,
            query=investigation.input_name,
            city=city,
            age_from=age_from,
            age_to=age_to,
            count=50
        )

    # Run OK search if not already done
    existing_ok = SocialProfile.query.filter_by(
        investigation_id=investigation_id,
        platform='ok'
    ).all()

    if not existing_ok:
        try:
            from app.services.phase1.ok_search_integration import ok_search_integration
            ok_search_integration.search_and_save(
                investigation_id=investigation_id,
                query=investigation.input_name,
                city=city,
                age_from=age_from,
                age_to=age_to,
                count=20
            )
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"OK search failed: {e}")

    # Reload all profiles (VK + OK) sorted by similarity
    all_profiles = SocialProfile.query.filter_by(
        investigation_id=investigation_id
    ).filter(
        SocialProfile.platform.in_(['vk', 'ok'])
    ).order_by(SocialProfile.name_similarity.desc()).all()

    # Update search stats
    vk_count = sum(1 for p in all_profiles if p.platform == 'vk')
    ok_count = sum(1 for p in all_profiles if p.platform == 'ok')
    stats['vk_results_count'] = vk_count
    stats['ok_results_count'] = ok_count
    stats['search_completed_at'] = datetime.now().isoformat()
    investigation.phase1_stats = stats
    db.session.commit()

    return render_template(
        'phase1_buratino_results.html',
        investigation=investigation,
        profiles=all_profiles,
        search_name=investigation.input_name,
        city=city,
        age_from=age_from,
        age_to=age_to
    )


@phase1_bp.route('/confirm/<investigation_id>/<int:profile_id>', methods=['POST'])
def confirm_profile(investigation_id, profile_id):
    """
    User confirms this is the correct profile.
    """
    investigation = Investigation.query.get_or_404(investigation_id)
    profile = SocialProfile.query.get_or_404(profile_id)

    # Verify profile belongs to this investigation
    if profile.investigation_id != investigation_id:
        return jsonify({'error': 'Профиль не принадлежит этому расследованию'}), 400

    # Mark profile as confirmed
    profile.confirm()

    # Update investigation with confirmed profile data
    investigation.confirmed_profile = profile.to_dict()
    investigation.confirmed_username = profile.username
    investigation.confirmed_platform = profile.platform
    investigation.confirmed_profile_url = profile.profile_url
    investigation.status = 'phase_1_complete'
    investigation.profile_confirmed_at = datetime.now()

    # Store VK ID for Phase 2
    stats = investigation.phase1_stats
    stats['confirmed_vk_id'] = profile.platform_id
    investigation.phase1_stats = stats

    db.session.commit()

    return jsonify({
        'success': True,
        'message': 'Профиль подтвержден',
        'redirect': f'/phase2/analyze/{investigation_id}'
    })


@phase1_bp.route('/reject/<investigation_id>/<int:profile_id>', methods=['POST'])
def reject_profile(investigation_id, profile_id):
    """
    User rejects this profile.
    """
    profile = SocialProfile.query.get_or_404(profile_id)

    if profile.investigation_id != investigation_id:
        return jsonify({'error': 'Профиль не принадлежит этому расследованию'}), 400

    profile.reject()
    db.session.commit()

    return jsonify({
        'success': True,
        'message': 'Профиль отклонен'
    })


@phase1_bp.route('/api/search/<investigation_id>/refresh', methods=['POST'])
def refresh_search(investigation_id):
    """
    Refresh VK search with new parameters.
    """
    investigation = Investigation.query.get_or_404(investigation_id)

    # Get new parameters
    city = (request.json.get('city') or '').strip() or None  # None = search all cities
    age_from = request.json.get('age_from')
    age_to = request.json.get('age_to')

    # Delete old unconfirmed search results (VK + OK)
    SocialProfile.query.filter_by(
        investigation_id=investigation_id,
        is_confirmed=False
    ).filter(
        SocialProfile.platform.in_(['vk', 'ok'])
    ).delete(synchronize_session='fetch')
    db.session.commit()

    # Update stats
    stats = investigation.phase1_stats
    stats['city'] = city
    stats['age_from'] = age_from
    stats['age_to'] = age_to
    investigation.phase1_stats = stats
    db.session.commit()

    # Run new VK search
    from app.services.phase1.buratino_vk_search import buratino_vk_search
    saved_profiles = buratino_vk_search.search_and_save(
        investigation_id=investigation_id,
        query=investigation.input_name,
        city=city,
        age_from=age_from,
        age_to=age_to,
        count=50
    )

    # Run new OK search
    try:
        from app.services.phase1.ok_search_integration import ok_search_integration
        ok_saved = ok_search_integration.search_and_save(
            investigation_id=investigation_id,
            query=investigation.input_name,
            city=city,
            age_from=age_from,
            age_to=age_to,
            count=20
        )
        saved_profiles.extend(ok_saved)
    except Exception:
        pass

    return jsonify({
        'success': True,
        'count': len(saved_profiles),
        'profiles': saved_profiles
    })


@phase1_bp.route('/uploads/<filename>')
def get_upload(filename):
    """Serve uploaded files."""
    upload_folder = get_upload_folder()
    return send_from_directory(upload_folder, filename)


@phase1_bp.route('/photo-search', methods=['POST'])
def photo_search():
    """
    Photo-first investigation: upload photo -> face search -> results.
    """
    from app.services.photo_investigation import photo_investigation

    if 'photo' not in request.files:
        return jsonify({'error': 'Фото не загружено'}), 400

    file = request.files['photo']
    error = photo_investigation.validate_photo(file)
    if error:
        return jsonify({'error': error}), 400

    upload_folder = get_upload_folder()
    photo_path = photo_investigation.save_photo(file, upload_folder)

    # Search for face matches
    matches = photo_investigation.search_by_photo(photo_path)

    return jsonify({
        'success': True,
        'photo_path': photo_path,
        'matches': matches,
        'count': len(matches),
    })


@phase1_bp.route('/photo-select', methods=['POST'])
def photo_select():
    """
    User selects a match from photo search results.
    Creates investigation and redirects to Phase 2.
    """
    from app.services.photo_investigation import photo_investigation

    data = request.get_json()
    if not data or 'match' not in data:
        return jsonify({'error': 'Не выбран профиль'}), 400

    match = data['match']
    photo_path = data.get('photo_path', '')

    investigation_id = photo_investigation.create_investigation_from_match(match, photo_path)

    return jsonify({
        'success': True,
        'investigation_id': investigation_id,
        'redirect': f'/phase2/analyze/{investigation_id}',
    })


@phase1_bp.route('/investigations')
def list_investigations():
    """
    List all investigations.
    """
    investigations = Investigation.query.order_by(Investigation.created_at.desc()).limit(50).all()

    return render_template(
        'investigations_list.html',
        investigations=investigations
    )
