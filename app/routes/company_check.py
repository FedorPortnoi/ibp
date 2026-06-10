"""
Company Check Routes
====================
Blueprint for /company/* — юридическое лицо / ИП investigation pipeline.
"""

import re
import uuid
import logging
import threading
from datetime import datetime

from flask import Blueprint, render_template, request, jsonify, redirect, url_for, abort

from app import db, limiter
from app.permissions import can_access_check, is_admin

company_bp = Blueprint('company', __name__, url_prefix='/company')
logger = logging.getLogger(__name__)


def _error(msg: str, code: int = 400):
    if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'error': msg}), code
    return render_template('error.html', message=msg), code


def _get_check_or_404(check_id: str):
    from app.models.company_check import CompanyCheck
    check = db.session.get(CompanyCheck, check_id)
    if not check:
        abort(404)
    from app.routes.auth import get_current_user
    user = get_current_user()
    from app.permissions import can_access_check
    if not can_access_check(user, check):
        abort(403)
    return check


def _validate_inn(inn: str) -> str | None:
    """Return error message or None if valid."""
    if not re.match(r'^\d{10}(\d{2})?$', inn):
        return 'ИНН должен содержать 10 цифр (юрлицо) или 12 цифр (ИП)'

    d = [int(c) for c in inn]
    if len(d) == 10:
        w = [2, 4, 10, 3, 5, 9, 4, 6, 8]
        if (sum(w[i] * d[i] for i in range(9)) % 11 % 10) != d[9]:
            return 'Некорректная контрольная сумма ИНН'
    elif len(d) == 12:
        w11 = [7, 2, 4, 10, 3, 5, 9, 4, 6, 8]
        w12 = [3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8]
        if (sum(w11[i] * d[i] for i in range(10)) % 11 % 10) != d[10]:
            return 'Некорректная контрольная сумма ИНН (11-й разряд)'
        if (sum(w12[i] * d[i] for i in range(11)) % 11 % 10) != d[11]:
            return 'Некорректная контрольная сумма ИНН (12-й разряд)'
    return None


# ── Routes ───────────────────────────────────────────────────────────────────

@company_bp.route('/new')
def new_check():
    """Render company investigation form."""
    return render_template('company_new.html')


@company_bp.route('/start', methods=['POST'])
@limiter.limit("10 per minute; 50 per hour")
def start_check():
    """
    Start a company background check.
    Accepts form POST or JSON. Creates CompanyCheck, launches pipeline,
    returns JSON with redirect URL.
    """
    import json as _json
    from app.models.company_check import CompanyCheck

    # Parse input
    if request.is_json:
        try:
            data = _json.loads(request.get_data().decode('utf-8'))
        except Exception:
            data = request.get_json() or {}
    else:
        data = request.form.to_dict()

    # Validate INN
    inn = re.sub(r'\s', '', (data.get('inn') or ''))
    if not inn:
        return _error('ИНН обязателен', 400)
    err = _validate_inn(inn)
    if err:
        return _error(err, 400)

    # Optional name hint — strip HTML
    query_name = re.sub(r'<[^>]+>', '', (data.get('query_name') or '')).strip()[:255]

    # Free tier enforcement (same as candidate route)
    from app.routes.auth import get_current_user as _get_user
    from app.models.subscription import Subscription
    _user = _get_user()
    if _user and not _user.is_admin:
        try:
            db.session.execute(db.text("BEGIN IMMEDIATE"))
        except Exception:
            db.session.rollback()
        _sub = Subscription.query.filter_by(user_id=_user.id).first()
        if not _sub:
            _sub = Subscription(user_id=_user.id, status='inactive')
            db.session.add(_sub)
            try:
                db.session.flush()
            except Exception:
                db.session.rollback()
        if not _sub.can_run_check():
            db.session.rollback()
            return _error(
                'Лимит бесплатных проверок исчерпан (2 в неделю). '
                'Оформите подписку для безлимитного доступа.', 403
            )

    # Create record
    check = CompanyCheck(
        id=str(uuid.uuid4()),
        inn=inn,
        query_name=query_name or None,
        task_id=str(uuid.uuid4()),
        status='pending',
        user_id=_user.id if _user else None,
    )
    db.session.add(check)
    db.session.commit()

    # Launch pipeline in background thread
    from flask import current_app
    app = current_app._get_current_object()

    def _run():
        from app.services.company.company_pipeline import run_company_pipeline
        run_company_pipeline(check.id, app)

    t = threading.Thread(target=_run, daemon=True, name=f'co_{check.id[:8]}')
    t.start()

    logger.info("Company check %s started for INN %s", check.id, inn)

    return jsonify({
        'check_id': check.id,
        'redirect': url_for('company.progress', check_id=check.id),
    })


@company_bp.route('/progress/<check_id>')
def progress(check_id: str):
    """Progress page — polls /company/status/<check_id>."""
    check = _get_check_or_404(check_id)
    return render_template('company_progress.html', check=check)


@company_bp.route('/status/<check_id>')
def status(check_id: str):
    """JSON status endpoint polled by the progress page."""
    check = _get_check_or_404(check_id)
    data = check.task_status_dict()
    if data['status'] == 'complete':
        data['dossier_url'] = url_for('company.dossier', check_id=check_id)
    return jsonify(data)


@company_bp.route('/check/<check_id>')
def dossier(check_id: str):
    """Company investigation dossier."""
    check = _get_check_or_404(check_id)
    if check.status not in ('complete', 'error'):
        return redirect(url_for('company.progress', check_id=check_id))

    egrul = check.egrul_data
    courts = check.court_records
    sanctions = check.sanctions_results
    sanctions_meta = check.sanctions_meta
    bankruptcy = check.bankruptcy_data
    gov_contracts = check.gov_contracts_data
    financial = check.financial_data
    rnp = check.rnp_data
    flags = check.risk_flags

    # Manual search URLs for the investigator
    from app.services.company.company_court_service import CompanyCourtSearch
    manual_urls = CompanyCourtSearch.get_manual_search_urls(
        company_name=check.display_name,
        inn=check.inn,
    )

    return render_template(
        'company_dossier.html',
        check=check,
        egrul=egrul,
        courts=courts,
        sanctions=sanctions,
        sanctions_meta=sanctions_meta,
        bankruptcy=bankruptcy,
        gov_contracts=gov_contracts,
        financial=financial,
        rnp=rnp,
        flags=flags,
        manual_urls=manual_urls,
    )


@company_bp.route('/history')
def history():
    """List of company checks for current user."""
    from app.routes.auth import get_current_user
    from app.models.company_check import CompanyCheck
    user = get_current_user()
    if not user:
        return redirect(url_for('auth.login'))
    if is_admin(user):
        checks = CompanyCheck.query.order_by(CompanyCheck.created_at.desc()).limit(200).all()
    else:
        checks = (
            CompanyCheck.query
            .filter_by(user_id=user.id)
            .order_by(CompanyCheck.created_at.desc())
            .limit(100)
            .all()
        )
    return render_template('company_history.html', checks=checks)
