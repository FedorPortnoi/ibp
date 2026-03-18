"""
Candidate Check Routes
======================
Blueprint for /candidate/* — background check pipeline.
"""

import re
import uuid
import json
import threading
import logging
from datetime import datetime, date

from flask import Blueprint, render_template, request, jsonify, redirect, url_for, current_app, make_response

from app import db, limiter
from app.models.candidate_check import CandidateCheck
from app.services.candidate.pipeline import candidate_tasks, CandidateTaskStatus, run_candidate_pipeline, cleanup_old_tasks

candidate_bp = Blueprint('candidate', __name__, url_prefix='/candidate')
logger = logging.getLogger(__name__)


def _safe_filename(name_slug: str) -> str:
    """Sanitize a string for safe use in Content-Disposition filenames."""
    # Remove any characters that could break headers or enable injection
    safe = re.sub(r'[^\w\-.]', '_', name_slug)
    # Collapse multiple underscores
    safe = re.sub(r'_+', '_', safe).strip('_')
    return safe[:100] or 'candidate'


@candidate_bp.route('/start', methods=['POST'])
@limiter.limit("10 per minute")
def start_check():
    """
    Start a candidate background check.

    Accepts form POST (from the tab UI) or JSON.
    Creates a CandidateCheck record, launches pipeline in background,
    redirects to progress page.
    """
    # Parse input — support both form and JSON
    if request.is_json:
        data = request.get_json()
    else:
        data = request.form.to_dict()

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
        status='pending',
        check_mode=check_mode,
        task_id=task_id,
        task_started_at=datetime.utcnow(),
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
    # Try in-memory first (same worker)
    task = candidate_tasks.get(task_id)
    if task:
        return render_template(
            'candidate_progress.html',
            task_id=task_id,
            check_id=task.check_id,
            full_name=task.full_name,
        )

    # DB fallback (cross-worker)
    check = CandidateCheck.query.filter_by(task_id=task_id).first()
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
    if check.status != 'awaiting_confirmation':
        return redirect(url_for('candidate.dossier_page', check_id=check.id))

    confirmed_ids = request.form.getlist('confirmed_profiles')

    if confirmed_ids:
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


@candidate_bp.route('/api/social-graph/<check_id>')
def api_social_graph(check_id):
    """Return vis.js social graph data for dossier."""
    check = CandidateCheck.query.filter_by(id=check_id).first_or_404()
    return jsonify(check.social_graph_data or {})


@candidate_bp.route('/api/geo-data/<check_id>')
def api_geo_data(check_id):
    """Return geo analysis data for dossier map."""
    check = CandidateCheck.query.filter_by(id=check_id).first_or_404()
    return jsonify(check.geo_analysis or {})


@candidate_bp.route('/api/timeline/<check_id>')
def api_timeline(check_id):
    """Return activity timeline data."""
    check = CandidateCheck.query.filter_by(id=check_id).first_or_404()
    return jsonify(check.activity_timeline or [])


@candidate_bp.route('/dossier/<check_id>')
def dossier_page(check_id):
    """View completed dossier."""
    check = CandidateCheck.query.get(check_id)
    if not check:
        return render_template('errors/404.html'), 404

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
        sanctions=check.sanctions_results,
        social_profiles=check.social_media_profiles,
        contacts=check.contact_discoveries,
        red_flags=check.red_flags,
        social_graph_data=check.social_graph_data or {},
        face_matches=check.face_matches or [],
        username_accounts=check.username_accounts or [],
        geo_analysis=check.geo_analysis or {},
        text_analysis=check.text_analysis or {},
        activity_timeline=check.activity_timeline or [],
        risk_breakdown=check.risk_breakdown or {},
        report_generated=check.report_generated,
    )


@candidate_bp.route('/history')
def history():
    """List past candidate checks."""
    checks = CandidateCheck.query.order_by(CandidateCheck.created_at.desc()).all()
    return render_template('candidate_history.html', checks=checks)


@candidate_bp.route('/delete/<check_id>', methods=['POST'])
@limiter.limit("10 per minute")
def delete_check(check_id):
    """Delete a candidate check record."""
    check = CandidateCheck.query.get(check_id)
    if not check:
        return jsonify({'error': 'Проверка не найдена'}), 404

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
            'risk_score_numeric': check.risk_score_numeric,
            'red_flag_count': check.red_flag_count,
            'red_flags': check.red_flags,
            'risk_breakdown': check.risk_breakdown,
        },
        'business_records': check.business_records,
        'court_records': check.court_records,
        'fssp_records': check.fssp_records,
        'bankruptcy_records': check.bankruptcy_records,
        'sanctions_results': check.sanctions_results,
        'social_media_profiles': check.social_media_profiles,
        'confirmed_profiles': check.confirmed_profiles,
        'contact_discoveries': check.contact_discoveries,
        'social_graph_data': check.social_graph_data,
        'face_matches': check.face_matches,
        'username_accounts': check.username_accounts,
        'geo_analysis': check.geo_analysis,
        'text_analysis': check.text_analysis,
        'activity_timeline': check.activity_timeline,
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
        sanctions=check.sanctions_results,
        social_profiles=check.social_media_profiles,
        contacts=check.contact_discoveries,
        red_flags=check.red_flags,
        generated_date=datetime.utcnow().strftime('%d.%m.%Y %H:%M'),
        face_matches=check.face_matches or [],
        username_accounts=check.username_accounts or [],
        geo_analysis=check.geo_analysis or {},
        text_analysis=check.text_analysis or {},
        activity_timeline=check.activity_timeline or [],
        risk_breakdown=check.risk_breakdown or {},
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
