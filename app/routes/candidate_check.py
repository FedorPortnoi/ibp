"""
Candidate Check Routes
======================
Blueprint for /candidate/* — background check pipeline.
"""

import re
import uuid
import threading
import logging
from datetime import datetime, date

from flask import Blueprint, render_template, request, jsonify, redirect, url_for, current_app

from app import db
from app.models.candidate_check import CandidateCheck
from app.services.candidate.pipeline import candidate_tasks, CandidateTaskStatus, run_candidate_pipeline

candidate_bp = Blueprint('candidate', __name__, url_prefix='/candidate')
logger = logging.getLogger(__name__)


@candidate_bp.route('/start', methods=['POST'])
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

    # --- Optional fields ---
    inn = (data.get('inn') or '').strip()[:12]
    if inn and not re.match(r'^\d{12}$', inn):
        return _error('ИНН должен содержать 12 цифр', 400)

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

    # --- Create DB record ---
    check_id = uuid.uuid4().hex
    check = CandidateCheck(
        id=check_id,
        full_name=full_name,
        date_of_birth=dob,
        inn=inn or None,
        passport_series=passport_series,
        passport_number=passport_number,
        registered_address=address or None,
        region=region or None,
        phone=phone or None,
        email=email or None,
        status='pending',
    )
    db.session.add(check)
    db.session.commit()

    # --- Start background pipeline ---
    task_id = uuid.uuid4().hex
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
    task = candidate_tasks.get(task_id)
    if not task:
        return render_template('errors/404.html'), 404

    return render_template(
        'candidate_progress.html',
        task_id=task_id,
        check_id=task.check_id,
        full_name=task.full_name,
    )


@candidate_bp.route('/progress/<task_id>/status')
def progress_status(task_id):
    """JSON polling endpoint for progress updates."""
    task = candidate_tasks.get(task_id)
    if not task:
        return jsonify({'error': 'Задача не найдена'}), 404
    return jsonify(task.to_dict())


@candidate_bp.route('/dossier/<check_id>')
def dossier_page(check_id):
    """View completed dossier."""
    check = CandidateCheck.query.get(check_id)
    if not check:
        return render_template('errors/404.html'), 404

    # If still running, redirect to progress page
    if check.status in ('pending', 'running'):
        # Find active task for this check
        for tid, t in candidate_tasks.items():
            if t.check_id == check_id:
                return redirect(f'/candidate/progress/{tid}')
        # No task found — show dossier anyway (stale state)

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
    )


@candidate_bp.route('/history')
def history():
    """List past candidate checks."""
    checks = CandidateCheck.query.order_by(CandidateCheck.created_at.desc()).limit(50).all()
    return jsonify({
        'checks': [c.to_dict() for c in checks],
    })


def _error(message: str, status_code: int):
    """Return error as JSON or redirect back with flash."""
    if request.is_json:
        return jsonify({'error': message}), status_code
    # For form POST, return JSON so the frontend JS can handle it
    return jsonify({'error': message}), status_code
