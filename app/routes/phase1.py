"""
IBP Phase 1 Routes - VK People Search (Buratino-style)
======================================================
Person-first investigation: Name → VK Search → Select Profile → Confirm
"""

from flask import Blueprint, render_template, request, jsonify, send_from_directory, current_app
from werkzeug.utils import secure_filename
import os
import uuid
import logging
from datetime import datetime
import requests as vk_http
from requests import RequestException

from app import db, limiter
from app.models import Investigation, SocialProfile

logger = logging.getLogger(__name__)

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


VK_API_BASE_URL = 'https://api.vk.com/method'
VK_API_VERSION = '5.131'
VK_PREVIEW_TIMEOUT_SECONDS = 10


class VKPreviewService:
    """Small adapter for the VK preview endpoint's external API calls."""

    def __init__(self, token_getter, request_func=None, timeout=VK_PREVIEW_TIMEOUT_SECONDS):
        self._token_getter = token_getter
        self._request_func = request_func or vk_http.request
        self._timeout = timeout

    def fetch(self, vk_id):
        service_token = self._token_getter('search')
        user_token = self._token_getter('private')

        if not service_token:
            return {'error': 'No VK token'}

        result = self._empty_preview()

        profile = self._fetch_profile(vk_id, service_token)
        if profile:
            result.update(self._profile_preview(profile))

        result['posts'] = self._fetch_wall_posts(vk_id, user_token or service_token)
        return result

    @staticmethod
    def _empty_preview():
        return {
            'photo': '',
            'last_seen': None,
            'friends': 0,
            'groups': 0,
            'status': '',
            'posts': [],
        }

    def _fetch_profile(self, vk_id, service_token):
        payload = self._vk_api_get('users.get', {
            'user_ids': vk_id,
            'fields': 'photo_400_orig,last_seen,counters,status,city',
            'access_token': service_token,
        }, vk_id)
        users = payload.get('response') if payload else None
        if not isinstance(users, list) or not users:
            return {}
        return users[0] if isinstance(users[0], dict) else {}

    @staticmethod
    def _profile_preview(profile):
        last_seen = profile.get('last_seen', {})
        counters = profile.get('counters', {})
        return {
            'photo': profile.get('photo_400_orig', ''),
            'last_seen': last_seen.get('time') if isinstance(last_seen, dict) else None,
            'friends': counters.get('friends', 0) if isinstance(counters, dict) else 0,
            'groups': counters.get('groups', 0) if isinstance(counters, dict) else 0,
            'status': profile.get('status', ''),
        }

    def _fetch_wall_posts(self, vk_id, token):
        payload = self._vk_api_get('wall.get', {
            'owner_id': vk_id,
            'count': 3,
            'filter': 'owner',
            'access_token': token,
        }, vk_id)
        response = payload.get('response') if payload else None
        posts = response.get('items', []) if isinstance(response, dict) else []
        if not isinstance(posts, list):
            return []

        preview_posts = []
        for post in posts:
            if not isinstance(post, dict):
                continue
            text = post.get('text')
            if not text:
                continue
            preview_posts.append({
                'text': str(text)[:150],
                'date': post.get('date'),
            })
        return preview_posts

    def _vk_api_get(self, method, params, vk_id):
        request_params = dict(params)
        request_params['v'] = VK_API_VERSION

        try:
            response = self._request_func(
                'GET',
                f'{VK_API_BASE_URL}/{method}',
                params=request_params,
                timeout=self._timeout,
            )
            response.raise_for_status()
            payload = response.json()
        except RequestException as e:
            logger.warning("VK preview %s request error for %s: %s", method, vk_id, e)
            return None
        except ValueError as e:
            logger.warning("VK preview %s invalid JSON for %s: %s", method, vk_id, e)
            return None
        except Exception as e:
            logger.warning("VK preview %s fetch error for %s: %s", method, vk_id, e)
            return None

        if not isinstance(payload, dict):
            logger.warning("VK preview %s returned non-object JSON for %s", method, vk_id)
            return None

        if 'error' in payload:
            error = payload.get('error')
            if isinstance(error, dict):
                error_detail = error.get('error_msg') or error.get('error_code')
            else:
                error_detail = error
            logger.info("VK preview %s API error for %s: %s", method, vk_id, error_detail)
            return None

        return payload


# ============================================
# BURATINO-STYLE ROUTES (VK People Search)
# ============================================

@phase1_bp.route('/')
def index():
    """Redirect to new investigation page."""
    return new_investigation()


@phase1_bp.route('/new', methods=['GET', 'POST'])
@limiter.limit("10 per minute", methods=["POST"])
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

    # GET: Show the three-column search page
    return render_template('people_search.html')


@phase1_bp.route('/search/<investigation_id>')
def buratino_search_results(investigation_id):
    """
    Run VK People Search and show results for selection.
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
        )

    # Reload VK profiles sorted by similarity
    all_profiles = SocialProfile.query.filter_by(
        investigation_id=investigation_id,
    ).filter(
        SocialProfile.platform == 'vk'
    ).order_by(SocialProfile.name_similarity.desc()).all()

    # Update search stats
    stats['vk_results_count'] = len(all_profiles)
    stats['search_completed_at'] = datetime.now().isoformat()
    investigation.phase1_stats = stats
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error(f"Failed to save phase1 stats: {e}")

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
@limiter.limit("10 per minute")
def refresh_search(investigation_id):
    """
    Refresh VK search with new parameters.
    """
    investigation = Investigation.query.get_or_404(investigation_id)

    # Get new parameters
    city = (request.json.get('city') or '').strip() or None  # None = search all cities
    age_from = request.json.get('age_from')
    age_to = request.json.get('age_to')

    # Delete old unconfirmed VK search results
    SocialProfile.query.filter_by(
        investigation_id=investigation_id,
        is_confirmed=False,
        platform='vk'
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
    )

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
@limiter.limit("5 per minute")
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


@phase1_bp.route('/vk-preview/<int:vk_id>')
def vk_preview(vk_id):
    """Fetch quick preview data for a VK profile (hover popup)."""
    from app.utils.vk_token_manager import get_vk_token

    return jsonify(VKPreviewService(get_vk_token).fetch(vk_id))


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
