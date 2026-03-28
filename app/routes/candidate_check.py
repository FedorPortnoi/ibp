"""
Candidate Check Routes
======================
Blueprint for /candidate/* — background check pipeline.
"""

import os
import re
import uuid
import json
import threading
import logging
from datetime import datetime, date

from flask import Blueprint, render_template, request, jsonify, redirect, url_for, current_app, make_response, abort
from werkzeug.utils import secure_filename

from app import db, limiter
from app.models.candidate_check import CandidateCheck
from app.services.candidate.pipeline import candidate_tasks, CandidateTaskStatus, run_candidate_pipeline, cleanup_old_tasks

candidate_bp = Blueprint('candidate', __name__, url_prefix='/candidate')
logger = logging.getLogger(__name__)


def _check_owner_or_admin(check):
    """Verify current user owns this CandidateCheck or is admin. Returns (user, error_response)."""
    from app.routes.auth import get_current_user
    user = get_current_user()
    if not user:
        return None, abort(403)
    if user.is_admin:
        return user, None
    if check.user_id and check.user_id != user.id:
        return None, abort(403)
    return user, None


def _check_owner_or_admin_by_task(task_id):
    """Look up CandidateCheck by task_id and verify ownership. Returns (check, error_response)."""
    from app.routes.auth import get_current_user
    user = get_current_user()
    if not user:
        abort(403)

    # Try in-memory first
    task = candidate_tasks.get(task_id)
    check = None
    if task:
        check = CandidateCheck.query.get(task.check_id)
    if not check:
        check = CandidateCheck.query.filter_by(task_id=task_id).first()
    if not check:
        return None, None  # Let caller handle 404

    if not user.is_admin and check.user_id and check.user_id != user.id:
        abort(403)
    return check, None


def _safe_filename(name_slug: str) -> str:
    """Sanitize a string for safe use in Content-Disposition filenames.

    Transliterates Cyrillic to Latin before stripping non-ASCII chars.
    """
    # Transliterate Cyrillic to Latin for filename compatibility
    _cyr_to_lat = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e',
        'ё': 'yo', 'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k',
        'л': 'l', 'м': 'm', 'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r',
        'с': 's', 'т': 't', 'у': 'u', 'ф': 'f', 'х': 'kh', 'ц': 'ts',
        'ч': 'ch', 'ш': 'sh', 'щ': 'shch', 'ъ': '', 'ы': 'y', 'ь': '',
        'э': 'e', 'ю': 'yu', 'я': 'ya',
    }
    transliterated = []
    for ch in name_slug:
        low = ch.lower()
        if low in _cyr_to_lat:
            repl = _cyr_to_lat[low]
            transliterated.append(repl.upper() if ch.isupper() else repl)
        else:
            transliterated.append(ch)
    slug = ''.join(transliterated)
    # Remove any characters that could break headers or enable injection
    safe = re.sub(r'[^a-zA-Z0-9_\-.]', '_', slug)
    # Collapse multiple underscores
    safe = re.sub(r'_+', '_', safe).strip('_')
    return safe[:100] or 'candidate'


@candidate_bp.route('/new')
def new_check():
    """Render the candidate check form."""
    return render_template('candidate_new.html')


@candidate_bp.route('/start', methods=['POST'])
@limiter.limit("10 per minute; 50 per hour")
def start_check():
    """
    Start a candidate background check.

    Accepts form POST (from the tab UI) or JSON.
    Creates a CandidateCheck record, launches pipeline in background,
    redirects to progress page.
    """
    # --- Free tier enforcement ---
    from app.routes.auth import get_current_user as _get_user
    from app.models.subscription import Subscription
    _user = _get_user()
    if _user and not _user.is_admin:
        _sub = Subscription.query.filter_by(user_id=_user.id).first()
        if not _sub:
            _sub = Subscription(user_id=_user.id, status='inactive')
            db.session.add(_sub)
            db.session.commit()
        if not _sub.can_run_check():
            return _error(
                'Лимит бесплатных проверок исчерпан (2 в неделю). '
                'Оформите подписку для безлимитного доступа.', 403
            )

    # Parse input — support both form and JSON
    # Explicit UTF-8 decoding to prevent locale-dependent encoding corruption
    if request.is_json:
        raw_bytes = request.get_data()
        try:
            data = json.loads(raw_bytes.decode('utf-8'))
        except (UnicodeDecodeError, json.JSONDecodeError):
            data = request.get_json() or {}
    else:
        data = request.form.to_dict()

    # --- 152-FZ: PD consent validation ---
    if not data.get('pd_consent'):
        return _error('Необходимо подтвердить согласие на обработку персональных данных', 400)

    # --- Validate required fields ---
    full_name = (data.get('full_name') or '').strip()[:255]
    dob_raw = (data.get('date_of_birth') or '').strip()

    # Sanitize: strip HTML tags
    if re.search(r'<[^>]+>', full_name):
        full_name = re.sub(r'<[^>]+>', '', full_name).strip()

    if not full_name:
        return _error('Имя обязательно', 400)

    # At least 2 words
    if len(full_name.split()) < 2:
        return _error('Укажите полное имя (минимум имя и фамилия)', 400)

    if not dob_raw:
        return _error('Дата рождения обязательна', 400)

    try:
        dob = date.fromisoformat(dob_raw)
    except (ValueError, TypeError):
        return _error('Неверный формат даты рождения', 400)

    # Not in the future
    if dob > date.today():
        return _error('Дата рождения не может быть в будущем', 400)

    # Age 16-100
    age = (date.today() - dob).days // 365
    if age < 16 or age > 100:
        return _error('Возраст должен быть от 16 до 100 лет', 400)

    # --- INN (required) ---
    inn = (data.get('inn') or '').strip()[:12]
    if not inn:
        return _error('ИНН обязателен', 400)
    if not re.match(r'^\d{10}(\d{2})?$', inn):
        return _error('ИНН должен содержать 10 или 12 цифр', 400)

    from app.utils.inn_validator import validate_inn
    inn_valid, inn_error = validate_inn(inn)
    if not inn_valid:
        return _error(inn_error, 400)

    # --- Optional fields ---

    passport_raw = (data.get('passport') or '').strip()
    passport_series = None
    passport_number = None
    if passport_raw:
        # Accept "4515 123456" or "4515123456"
        m = re.match(r'^(\d{4})\s?(\d{6})$', passport_raw)
        if not m:
            return _error('Паспорт: 4 цифры серии + 6 цифр номера', 400)
        passport_series = m.group(1)
        passport_number = m.group(2)

    address = (data.get('registered_address') or '').strip()[:500]
    region = (data.get('region') or '').strip()[:100]
    phone = (data.get('phone') or '').strip()[:20]
    email = (data.get('email') or '').strip()[:255]

    if email and not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email):
        return _error('Неверный формат email', 400)

    # --- Mode ---
    check_mode = (data.get('check_mode') or 'quick').strip().lower()
    if check_mode not in ('quick', 'precise'):
        check_mode = 'quick'

    # --- Create DB record ---
    check_id = uuid.uuid4().hex
    task_id = uuid.uuid4().hex

    # --- Photo Upload ---
    photo_path = None
    photo = request.files.get('photo')
    if photo and photo.filename:
        filename = secure_filename(photo.filename)
        if filename:
            photo_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'photos')
            os.makedirs(photo_dir, exist_ok=True)
            photo_path = os.path.join(photo_dir, f"{check_id}_{filename}")
            photo.save(photo_path)

    # Get current user for ownership
    from app.routes.auth import get_current_user
    current_user = get_current_user()

    check = CandidateCheck(
        id=check_id,
        full_name=full_name,
        date_of_birth=dob,
        inn=inn,
        passport_series=passport_series,
        passport_number=passport_number,
        registered_address=address or None,
        region=region or None,
        phone=phone or None,
        email=email or None,
        photo_path=photo_path,
        status='pending',
        check_mode=check_mode,
        task_id=task_id,
        task_started_at=datetime.utcnow(),
        user_id=current_user.id if current_user else None,
        pd_consent=True,
        pd_consent_at=datetime.utcnow(),
    )
    db.session.add(check)
    db.session.commit()

    # --- Start background pipeline ---
    # Cleanup old completed tasks before adding new ones
    cleanup_old_tasks(candidate_tasks)

    # Limit concurrent running tasks to prevent resource exhaustion
    active_count = sum(1 for t in candidate_tasks.values()
                       if not hasattr(t, 'completed') or not t.completed)
    if active_count >= 10:
        return _error('Слишком много активных проверок. Дождитесь завершения текущих.', 429)

    task = CandidateTaskStatus(task_id, check_id, full_name)
    candidate_tasks[task_id] = task

    app = current_app._get_current_object()
    thread = threading.Thread(
        target=run_candidate_pipeline,
        args=(app, task_id, check_id),
        daemon=True,
    )
    thread.start()

    logger.info(f"Candidate check started: {check_id} for '{full_name}', task={task_id}")

    # Respond based on request type
    if request.is_json:
        return jsonify({
            'success': True,
            'check_id': check_id,
            'task_id': task_id,
            'redirect': f'/candidate/progress/{task_id}',
        })

    return redirect(f'/candidate/progress/{task_id}')


@candidate_bp.route('/progress/<task_id>')
def progress_page(task_id):
    """Render progress page — polls /candidate/progress/<task_id>/status via JS."""
    # Ownership check
    check, _ = _check_owner_or_admin_by_task(task_id)

    # Try in-memory first (same worker)
    task = candidate_tasks.get(task_id)
    if task:
        return render_template(
            'candidate_progress.html',
            task_id=task_id,
            check_id=task.check_id,
            full_name=task.full_name,
        )

    # DB fallback (cross-worker) — check already loaded by ownership check
    if check:
        return render_template(
            'candidate_progress.html',
            task_id=task_id,
            check_id=check.id,
            full_name=check.full_name,
        )

    return render_template('errors/404.html'), 404


@candidate_bp.route('/progress/<task_id>/status')
def progress_status(task_id):
    """JSON polling endpoint for progress updates — 8 stages."""
    # Ownership check
    _check_owner_or_admin_by_task(task_id)

    # Try in-memory first (most up-to-date on same worker)
    task = candidate_tasks.get(task_id)
    if task:
        data = task.to_dict()
        check = CandidateCheck.query.get(task.check_id)
        if check and check.status == 'awaiting_confirmation':
            data['status'] = 'awaiting_confirmation'
            data['confirmation_url'] = f'/candidate/confirm/{check.id}'
        return jsonify(data)

    # DB fallback (cross-worker — reads progress from DB)
    check = CandidateCheck.query.filter_by(task_id=task_id).first()
    if not check:
        return jsonify({'error': 'Задача не найдена'}), 404

    return jsonify(check.task_status_dict())


@candidate_bp.route('/confirm/<check_id>')
def confirm_profiles(check_id):
    """Show discovered profiles for user confirmation (Precise Mode)."""
    check = CandidateCheck.query.filter_by(id=check_id).first_or_404()
    _check_owner_or_admin(check)
    if check.status != 'awaiting_confirmation':
        # Already confirmed or not in precise mode — redirect to progress
        for tid, t in candidate_tasks.items():
            if t.check_id == check_id:
                return redirect(f'/candidate/progress/{tid}')
        if check.task_id and check.status in ('pending', 'running'):
            return redirect(f'/candidate/progress/{check.task_id}')
        return redirect(url_for('candidate.dossier_page', check_id=check.id))

    profiles = check.social_media_profiles or []
    return render_template('candidate_confirm_profiles.html',
                           check=check, profiles=profiles)


@candidate_bp.route('/confirm/<check_id>', methods=['POST'])
def submit_confirmation(check_id):
    """Process profile confirmation and resume pipeline."""
    check = CandidateCheck.query.filter_by(id=check_id).first_or_404()
    _check_owner_or_admin(check)
    if check.status != 'awaiting_confirmation':
        return redirect(url_for('candidate.dossier_page', check_id=check.id))

    action = request.form.get('action', '')
    confirmed_ids = request.form.getlist('confirmed_profiles')

    if action == 'skip_no_vk':
        # Explicit skip — mark VK as not found
        check.confirmed_profiles = []
        identity_conf = check.identity_confirmation or {}
        identity_conf['vk_status'] = 'not_found_manual_skip'
        check.identity_confirmation = identity_conf
    elif confirmed_ids:
        all_profiles = check.social_media_profiles or []
        confirmed = [
            p for p in all_profiles
            if str(p.get('id', '')) in confirmed_ids
            or p.get('url', '') in confirmed_ids
            or p.get('username', '') in confirmed_ids
        ]
        check.confirmed_profiles = confirmed
    else:
        check.confirmed_profiles = []

    check.status = 'running'
    check.paused_at_stage = None
    db.session.commit()

    # Find active task to redirect to progress
    for tid, t in candidate_tasks.items():
        if t.check_id == check_id:
            return redirect(f'/candidate/progress/{tid}')
    if check.task_id:
        return redirect(f'/candidate/progress/{check.task_id}')
    return redirect(url_for('candidate.dossier_page', check_id=check.id))


@candidate_bp.route('/confirm/<check_id>/retry-expanded', methods=['POST'])
@limiter.limit("5 per minute")
def retry_expanded_search(check_id):
    """Re-run VK search with relaxed matching thresholds."""
    check = CandidateCheck.query.filter_by(id=check_id).first_or_404()
    _check_owner_or_admin(check)
    if check.status != 'awaiting_confirmation':
        return jsonify({'error': 'Проверка не в режиме подтверждения'}), 400

    try:
        from app.services.phase1.buratino_vk_search import BuratinoVKSearch

        buratino = BuratinoVKSearch()
        effective_name = check.confirmed_name or check.full_name
        name_parts = effective_name.strip().split()

        vk_age_from = None
        vk_age_to = None
        if check.date_of_birth:
            from datetime import date as _date
            today = _date.today()
            age = today.year - check.date_of_birth.year - (
                (today.month, today.day) < (check.date_of_birth.month, check.date_of_birth.day)
            )
            vk_age_from = max(age - 5, 16)
            vk_age_to = age + 5

        expanded_profiles = buratino.search_expanded(
            query=effective_name,
            city=check.region,
            age_from=vk_age_from,
            age_to=vk_age_to,
            count=50,
        )

        new_profiles = []
        existing_ids = {
            p.get('platform_id') for p in (check.social_media_profiles or [])
            if p.get('platform') == 'vk'
        }

        for p in expanded_profiles[:20]:
            d = p.to_dict() if hasattr(p, 'to_dict') else p
            sim = d.get('name_similarity', 0)
            if sim < 30:
                continue
            vk_id = d.get('vk_id')
            if vk_id in existing_ids:
                continue

            if sim >= 75:
                confidence = 'высокая'
            elif sim >= 50:
                confidence = 'средняя'
            else:
                confidence = 'низкая'

            new_profiles.append({
                'platform': 'vk',
                'platform_id': vk_id,
                'display_name': d.get('full_name', ''),
                'username': d.get('screen_name', ''),
                'url': d.get('profile_url', ''),
                'avatar_url': d.get('photo_url'),
                'photo_url': d.get('photo_url'),
                'confidence': confidence,
                'confidence_score': round(sim / 100, 2),
                'source_method': 'VK расширенный поиск',
                'city': d.get('city', ''),
                'expanded_search': True,
            })

        # Merge into existing profiles
        all_profiles = check.social_media_profiles or []
        all_profiles.extend(new_profiles)
        check.social_media_profiles = all_profiles
        db.session.commit()

        return jsonify({
            'success': True,
            'new_count': len(new_profiles),
            'profiles': new_profiles,
        })

    except Exception as e:
        logger.error(f"Expanded VK search failed for {check_id}: {e}")
        return jsonify({'error': 'Ошибка расширенного поиска'}), 500


@candidate_bp.route('/confirm/<check_id>/search-name', methods=['POST'])
@limiter.limit("5 per minute")
def search_by_name(check_id):
    """Search VK by an alternative name (maiden name, alias, etc.)."""
    check = CandidateCheck.query.filter_by(id=check_id).first_or_404()
    _check_owner_or_admin(check)
    if check.status != 'awaiting_confirmation':
        return jsonify({'error': 'Проверка не в режиме подтверждения'}), 400

    data = request.get_json() or {}
    alt_name = (data.get('name') or '').strip()[:255]
    if re.search(r'<[^>]+>', alt_name):
        alt_name = re.sub(r'<[^>]+>', '', alt_name).strip()

    if not alt_name or len(alt_name.split()) < 2:
        return jsonify({'error': 'Укажите имя и фамилию'}), 400

    try:
        from app.services.phase1.buratino_vk_search import BuratinoVKSearch

        buratino = BuratinoVKSearch()

        vk_age_from = None
        vk_age_to = None
        if check.date_of_birth:
            from datetime import date as _date
            today = _date.today()
            age = today.year - check.date_of_birth.year - (
                (today.month, today.day) < (check.date_of_birth.month, check.date_of_birth.day)
            )
            vk_age_from = max(age - 3, 16)
            vk_age_to = age + 3

        profiles, _ = buratino.search(
            query=alt_name,
            city=check.region,
            age_from=vk_age_from,
            age_to=vk_age_to,
            target_name=alt_name,
            strict_mode=False,
        )

        new_profiles = []
        existing_ids = {
            p.get('platform_id') for p in (check.social_media_profiles or [])
            if p.get('platform') == 'vk'
        }

        for p in profiles[:15]:
            d = p.to_dict() if hasattr(p, 'to_dict') else p
            sim = d.get('name_similarity', 0)
            if sim < 30:
                continue
            vk_id = d.get('vk_id')
            if vk_id in existing_ids:
                continue

            if sim >= 75:
                confidence = 'высокая'
            elif sim >= 50:
                confidence = 'средняя'
            else:
                confidence = 'низкая'

            new_profiles.append({
                'platform': 'vk',
                'platform_id': vk_id,
                'display_name': d.get('full_name', ''),
                'username': d.get('screen_name', ''),
                'url': d.get('profile_url', ''),
                'avatar_url': d.get('photo_url'),
                'photo_url': d.get('photo_url'),
                'confidence': confidence,
                'confidence_score': round(sim / 100, 2),
                'source_method': f'VK поиск: {alt_name}',
                'city': d.get('city', ''),
                'alt_name_search': True,
            })

        all_profiles = check.social_media_profiles or []
        all_profiles.extend(new_profiles)
        check.social_media_profiles = all_profiles
        db.session.commit()

        return jsonify({
            'success': True,
            'new_count': len(new_profiles),
            'profiles': new_profiles,
            'searched_name': alt_name,
        })

    except Exception as e:
        logger.error(f"Alt-name VK search failed for {check_id}: {e}")
        return jsonify({'error': 'Ошибка поиска'}), 500


@candidate_bp.route('/confirm/<check_id>/manual-vk', methods=['POST'])
@limiter.limit("5 per minute")
def manual_vk_profile(check_id):
    """Validate and add a manually entered VK profile."""
    check = CandidateCheck.query.filter_by(id=check_id).first_or_404()
    _check_owner_or_admin(check)
    if check.status != 'awaiting_confirmation':
        return jsonify({'error': 'Проверка не в режиме подтверждения'}), 400

    data = request.get_json() or {}
    vk_input = (data.get('vk_url') or '').strip()[:500]
    if re.search(r'<[^>]+>', vk_input):
        vk_input = re.sub(r'<[^>]+>', '', vk_input).strip()

    if not vk_input:
        return jsonify({'error': 'Введите ссылку или username'}), 400

    # Extract screen name from various VK URL formats
    screen_name = vk_input
    for prefix in ['https://vk.com/', 'http://vk.com/', 'vk.com/', 'https://m.vk.com/', 'http://m.vk.com/']:
        if screen_name.lower().startswith(prefix):
            screen_name = screen_name[len(prefix):]
            break
    screen_name = screen_name.strip('/').split('?')[0]

    if not screen_name or not re.match(r'^[a-zA-Z0-9_.]+$', screen_name):
        return jsonify({'error': 'Неверный формат VK ссылки или username'}), 400

    try:
        import requests as http_requests
        from app.utils.vk_token_manager import get_vk_token

        token = get_vk_token('search')
        if not token:
            return jsonify({'error': 'VK токен не настроен'}), 500

        # Resolve screen name to user ID
        resp = http_requests.post(
            'https://api.vk.com/method/utils.resolveScreenName',
            data={
                'screen_name': screen_name,
                'access_token': token,
                'v': '5.199',
            },
            timeout=10,
        )
        resolve_data = resp.json().get('response', {})
        if not resolve_data or resolve_data.get('type') != 'user':
            return jsonify({'error': 'Профиль не найден или это не пользователь'}), 404

        user_id = resolve_data['object_id']

        # Get full profile
        resp = http_requests.post(
            'https://api.vk.com/method/users.get',
            data={
                'user_ids': str(user_id),
                'fields': 'photo_200,screen_name,city,bdate,verified',
                'access_token': token,
                'v': '5.199',
            },
            timeout=10,
        )
        users = resp.json().get('response', [])
        if not users:
            return jsonify({'error': 'Не удалось загрузить профиль'}), 404

        user = users[0]
        display_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
        profile_url = f"https://vk.com/{user.get('screen_name', f'id{user_id}')}"

        new_profile = {
            'platform': 'vk',
            'platform_id': user_id,
            'display_name': display_name,
            'username': user.get('screen_name', ''),
            'url': profile_url,
            'avatar_url': user.get('photo_200'),
            'photo_url': user.get('photo_200'),
            'confidence': 'ручной ввод',
            'confidence_score': 0.0,
            'source_method': 'Введён вручную',
            'city': (user.get('city') or {}).get('title', ''),
            'manual_entry': True,
        }

        all_profiles = check.social_media_profiles or []

        # Check duplicate
        for p in all_profiles:
            if p.get('platform_id') == user_id and p.get('platform') == 'vk':
                return jsonify({
                    'success': True,
                    'profile': p,
                    'duplicate': True,
                    'message': 'Этот профиль уже в списке',
                })

        all_profiles.append(new_profile)
        check.social_media_profiles = all_profiles
        db.session.commit()

        return jsonify({
            'success': True,
            'profile': new_profile,
        })

    except Exception as e:
        logger.error(f"Manual VK profile failed for {check_id}: {e}")
        return jsonify({'error': 'Ошибка проверки профиля'}), 500


@candidate_bp.route('/api/social-graph/<check_id>')
def api_social_graph(check_id):
    """Return vis.js social graph data for dossier."""
    check = CandidateCheck.query.filter_by(id=check_id).first_or_404()
    _check_owner_or_admin(check)
    return jsonify(check.social_graph_data or {})


@candidate_bp.route('/api/geo-data/<check_id>')
def api_geo_data(check_id):
    """Return geo analysis data for dossier map."""
    check = CandidateCheck.query.filter_by(id=check_id).first_or_404()
    _check_owner_or_admin(check)
    return jsonify(check.geo_analysis or {})


@candidate_bp.route('/api/geo-intelligence/<check_id>')
def api_geo_intelligence(check_id):
    """Return aggregated geo intelligence data for dossier."""
    check = CandidateCheck.query.filter_by(id=check_id).first_or_404()
    _check_owner_or_admin(check)
    return jsonify(check.geo_intelligence or {})


@candidate_bp.route('/api/timeline/<check_id>')
def api_timeline(check_id):
    """Return activity timeline data."""
    check = CandidateCheck.query.filter_by(id=check_id).first_or_404()
    _check_owner_or_admin(check)
    return jsonify(check.activity_timeline or [])


@candidate_bp.route('/dossier/<check_id>')
def dossier_page(check_id):
    """View completed dossier."""
    check = CandidateCheck.query.get(check_id)
    if not check:
        return render_template('errors/404.html'), 404

    # Access control: owner or admin
    from app.routes.auth import get_current_user
    user = get_current_user()
    if user and not user.is_admin and check.user_id != user.id:
        abort(403)

    # If still running, redirect to progress page
    if check.status in ('pending', 'running', 'awaiting_confirmation'):
        if check.status == 'awaiting_confirmation':
            return redirect(f'/candidate/confirm/{check_id}')
        # Try in-memory first
        for tid, t in candidate_tasks.items():
            if t.check_id == check_id:
                return redirect(f'/candidate/progress/{tid}')
        # DB fallback: use stored task_id
        if check.task_id:
            return redirect(f'/candidate/progress/{check.task_id}')

    # Format duration
    duration_display = ''
    if check.check_duration_seconds:
        secs = check.check_duration_seconds
        if secs >= 60:
            mins = int(secs // 60)
            remaining = int(secs % 60)
            duration_display = f'{mins}м {remaining}с'
        else:
            duration_display = f'{secs:.0f}с'

    return render_template(
        'candidate_dossier.html',
        check=check,
        duration_display=duration_display,
        business_records=check.business_records,
        court_records=check.court_records,
        fssp_records=check.fssp_records,
        bankruptcy_records=check.bankruptcy_records,
        pledge_records=check.pledge_records,
        sanctions=check.sanctions_results,
        social_profiles=check.social_media_profiles,
        contacts=check.contact_discoveries,
        red_flags=check.red_flags,
        social_graph_data=check.social_graph_data or {},
        face_matches=check.face_matches or [],
        username_accounts=check.username_accounts or [],
        geo_analysis=check.geo_analysis or {},
        geo_intelligence=check.geo_intelligence or {},
        text_analysis=check.text_analysis or {},
        activity_timeline=check.activity_timeline or [],
        risk_breakdown=check.risk_breakdown or {},
        report_generated=check.report_generated,
        group_analysis=check.group_analysis or {},
        activity_patterns=check.activity_patterns or {},
        connected_checks=check.connected_checks or [],
    )


@candidate_bp.route('/history')
def history():
    """List past candidate checks — admin sees all, users see own."""
    from app.routes.auth import get_current_user
    user = get_current_user()
    if user and user.is_admin:
        checks = CandidateCheck.query.order_by(CandidateCheck.created_at.desc()).all()
    elif user:
        checks = CandidateCheck.query.filter_by(user_id=user.id).order_by(
            CandidateCheck.created_at.desc()
        ).all()
    else:
        checks = []
    return render_template('candidate_history.html', checks=checks)


@candidate_bp.route('/delete/<check_id>', methods=['POST'])
@limiter.limit("10 per minute")
def delete_check(check_id):
    """Delete a candidate check record."""
    check = CandidateCheck.query.get(check_id)
    if not check:
        return jsonify({'error': 'Проверка не найдена'}), 404

    # Access control: owner or admin
    from app.routes.auth import get_current_user
    user = get_current_user()
    if user and not user.is_admin and check.user_id != user.id:
        abort(403)

    logger.info(f"Deleting candidate check {check_id} for '{check.full_name}'")
    db.session.delete(check)
    db.session.commit()
    return redirect(url_for('candidate.history'))


@candidate_bp.route('/export/<check_id>/json')
@limiter.limit("5 per minute")
def export_json(check_id):
    """Export dossier as downloadable JSON file."""
    check = CandidateCheck.query.get(check_id)
    if not check:
        return jsonify({'error': 'Проверка не найдена'}), 404

    # Access control: owner or admin
    from app.routes.auth import get_current_user
    user = get_current_user()
    if user and not user.is_admin and check.user_id != user.id:
        abort(403)

    # Build initials for filename (e.g. "Иванов_ИИ")
    parts = check.full_name.strip().split()
    if len(parts) >= 3:
        name_slug = f"{parts[0]}_{''.join(p[0] for p in parts[1:])}"
    elif len(parts) == 2:
        name_slug = f"{parts[0]}_{parts[1][0]}"
    else:
        name_slug = parts[0] if parts else 'candidate'

    date_str = datetime.utcnow().strftime('%Y-%m-%d')
    filename = f"dossier_{_safe_filename(name_slug)}_{date_str}.json"

    dossier = {
        'meta': {
            'generated_at': datetime.utcnow().isoformat(),
            'ibp_version': '1.0',
            'check_id': check.id,
            'check_mode': check.check_mode,
            'duration_seconds': check.check_duration_seconds,
            'check_level': check.check_level_display,
            'sources_checked': check.sources_checked,
            'sources_with_results': check.sources_with_results,
            'status': check.status,
            'report_generated': check.report_generated,
        },
        'candidate': {
            'full_name': check.full_name,
            'date_of_birth': check.date_of_birth.isoformat() if check.date_of_birth else None,
            'inn': check.inn,
            'region': check.region,
            'phone': check.phone,
            'email': check.email,
        },
        'risk_assessment': {
            'risk_level': check.risk_level,
            'risk_level_display': check.risk_level_display,
            'risk_score': check.risk_score,
            'risk_score_numeric': check.risk_score_numeric,
            'red_flag_count': check.red_flag_count,
            'red_flags': check.red_flags,
            'risk_breakdown': check.risk_breakdown,
        },
        'business_records': check.business_records,
        'court_records': check.court_records,
        'fssp_records': check.fssp_records,
        'bankruptcy_records': check.bankruptcy_records,
        'pledge_records': check.pledge_records,
        'sanctions_results': check.sanctions_results,
        'social_media_profiles': check.social_media_profiles,
        'confirmed_profiles': check.confirmed_profiles,
        'contact_discoveries': check.contact_discoveries,
        'social_graph_data': check.social_graph_data,
        'face_matches': check.face_matches,
        'username_accounts': check.username_accounts,
        'geo_analysis': check.geo_analysis,
        'geo_intelligence': check.geo_intelligence,
        'text_analysis': check.text_analysis,
        'activity_timeline': check.activity_timeline,
        'group_analysis': check.group_analysis,
        'activity_patterns': check.activity_patterns,
        'connected_checks': check.connected_checks,
    }

    json_str = json.dumps(dossier, ensure_ascii=False, indent=2, default=str)
    response = make_response(json_str)
    response.headers['Content-Type'] = 'application/json; charset=utf-8'
    response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@candidate_bp.route('/export/<check_id>/pdf')
@limiter.limit("5 per minute")
def export_pdf(check_id):
    """Export dossier as PDF via Playwright (Chromium)."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return jsonify({
            'error': 'PDF-генерация недоступна (Playwright не установлен). '
                     'Используйте кнопку "Печать" для сохранения в PDF через браузер.'
        }), 501

    check = CandidateCheck.query.get(check_id)
    if not check:
        return jsonify({'error': 'Проверка не найдена'}), 404

    # Access control: owner or admin
    from app.routes.auth import get_current_user
    user = get_current_user()
    if user and not user.is_admin and check.user_id != user.id:
        abort(403)

    # Build filename
    parts = check.full_name.strip().split()
    if len(parts) >= 3:
        name_slug = f"{parts[0]}_{''.join(p[0] for p in parts[1:])}"
    elif len(parts) == 2:
        name_slug = f"{parts[0]}_{parts[1][0]}"
    else:
        name_slug = parts[0] if parts else 'candidate'

    date_str = datetime.utcnow().strftime('%Y-%m-%d')
    filename = f"dossier_{_safe_filename(name_slug)}_{date_str}.pdf"

    # Format duration
    duration_display = ''
    if check.check_duration_seconds:
        secs = check.check_duration_seconds
        if secs >= 60:
            mins = int(secs // 60)
            remaining = int(secs % 60)
            duration_display = f'{mins}м {remaining}с'
        else:
            duration_display = f'{secs:.0f}с'

    html_str = render_template(
        'candidate_dossier_pdf.html',
        check=check,
        duration_display=duration_display,
        business_records=check.business_records,
        court_records=check.court_records,
        fssp_records=check.fssp_records,
        bankruptcy_records=check.bankruptcy_records,
        pledge_records=check.pledge_records,
        sanctions=check.sanctions_results,
        social_profiles=check.social_media_profiles,
        contacts=check.contact_discoveries,
        red_flags=check.red_flags,
        generated_date=datetime.utcnow().strftime('%d.%m.%Y %H:%M'),
        face_matches=check.face_matches or [],
        username_accounts=check.username_accounts or [],
        geo_analysis=check.geo_analysis or {},
        geo_intelligence=check.geo_intelligence or {},
        text_analysis=check.text_analysis or {},
        activity_timeline=check.activity_timeline or [],
        risk_breakdown=check.risk_breakdown or {},
        group_analysis=check.group_analysis or {},
        activity_patterns=check.activity_patterns or {},
        connected_checks=check.connected_checks or [],
    )

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.set_content(html_str, wait_until='networkidle')
                pdf_bytes = page.pdf(
                    format='A4',
                    margin={'top': '1.5cm', 'bottom': '2cm', 'left': '1.5cm', 'right': '1.5cm'},
                    print_background=True,
                )
            finally:
                browser.close()
    except Exception as e:
        logger.error(f"PDF generation failed for check {check_id}: {e}")
        return jsonify({'error': 'Ошибка генерации PDF. Используйте кнопку "Печать".'}), 500

    response = make_response(pdf_bytes)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


def _error(message: str, status_code: int):
    """Return error as JSON or redirect back with flash."""
    if request.is_json:
        return jsonify({'error': message}), status_code
    # For form POST, return JSON so the frontend JS can handle it
    return jsonify({'error': message}), status_code
