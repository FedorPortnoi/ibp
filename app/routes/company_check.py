"""
Company Check Routes
====================
Blueprint for /company/* — юридическое лицо / ИП investigation pipeline.
"""

import json
import re
import uuid
import logging
import threading
from datetime import datetime

from flask import Blueprint, render_template, request, jsonify, redirect, url_for, abort, make_response, current_app

from app import db, limiter
from app.permissions import is_admin, enforce_free_tier_limit, can_access_check
from app.utils.inn_validator import validate_inn

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
    if not can_access_check(user, check):
        abort(403)
    return check


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
    from app.models.company_check import CompanyCheck

    # Parse input
    if request.is_json:
        data = request.get_json(force=True, silent=True)
        if data is None:
            return _error('Некорректный JSON', 400)
    else:
        data = request.form.to_dict()

    # Validate INN
    inn = re.sub(r'\s', '', (data.get('inn') or ''))
    if not inn:
        return _error('ИНН обязателен', 400)
    inn_valid, inn_err = validate_inn(inn)
    if not inn_valid:
        return _error(inn_err, 400)

    # Optional name hint — strip HTML
    query_name = re.sub(r'<[^>]+>', '', (data.get('query_name') or '')).strip()[:255]

    # Free tier enforcement
    from app.routes.auth import get_current_user as _get_user
    _user = _get_user()
    allowed, tier_error = enforce_free_tier_limit(_user)
    if not allowed:
        return tier_error

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
    fssp = check.fssp_data
    adverse_media = check.adverse_media

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
        fssp=fssp,
        adverse_media=adverse_media,
    )


@company_bp.route('/export/<check_id>/json')
@limiter.limit("5 per minute")
def export_json(check_id: str):
    """Export company dossier as downloadable JSON."""
    check = _get_check_or_404(check_id)
    filename = f"company_{check.inn}_{check.id[:8]}.json"
    dossier = {
        'meta': {
            'generated_at': datetime.utcnow().isoformat(),
            'ibp_version': '1.0',
            'check_id': check.id,
            'duration_seconds': check.check_duration_seconds,
            'sources_checked': check.sources_checked,
            'status': check.status,
        },
        'company': {
            'inn': check.inn,
            'ogrn': check.ogrn,
            'company_name': check.company_name,
            'company_short_name': check.company_short_name,
            'company_type': check.company_type,
            'company_status': check.company_status,
        },
        'risk_assessment': {
            'risk_level': check.risk_level,
            'risk_level_display': check.risk_level_display,
            'risk_score': check.risk_score,
            'risk_flags': check.risk_flags,
        },
        'egrul_data': check.egrul_data,
        'court_records': check.court_records,
        'fssp_data': check.fssp_data,
        'sanctions_results': check.sanctions_results,
        'bankruptcy_data': check.bankruptcy_data,
        'gov_contracts_data': check.gov_contracts_data,
        'financial_data': check.financial_data,
        'rnp_data': check.rnp_data,
        'adverse_media': check.adverse_media,
        'ai_summary': check.ai_summary,
    }
    json_str = json.dumps(dossier, ensure_ascii=False, indent=2, default=str)
    response = make_response(json_str)
    response.headers['Content-Type'] = 'application/json; charset=utf-8'
    response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@company_bp.route('/export/<check_id>/pdf')
@limiter.limit("5 per minute")
def export_pdf(check_id: str):
    """Export company dossier as PDF via Playwright."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return jsonify({
            'error': 'PDF-генерация недоступна (Playwright не установлен). '
                     'Используйте кнопку "Печать" для сохранения в PDF через браузер.'
        }), 501

    check = _get_check_or_404(check_id)
    filename = f"company_{check.inn}_{check.id[:8]}.pdf"

    egrul = check.egrul_data
    courts = check.court_records
    sanctions = check.sanctions_results
    financial = check.financial_data
    fssp = check.fssp_data
    adverse_media = check.adverse_media

    from app.services.company.company_court_service import CompanyCourtSearch
    manual_urls = CompanyCourtSearch.get_manual_search_urls(
        company_name=check.display_name, inn=check.inn,
    )

    html_str = render_template(
        'company_dossier.html',
        check=check,
        egrul=egrul,
        courts=courts,
        sanctions=sanctions,
        sanctions_meta=check.sanctions_meta,
        bankruptcy=check.bankruptcy_data,
        gov_contracts=check.gov_contracts_data,
        financial=financial,
        rnp=check.rnp_data,
        flags=check.risk_flags,
        manual_urls=manual_urls,
        fssp=fssp,
        adverse_media=adverse_media,
        pdf_mode=True,
    )

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, timeout=15000)
            try:
                page = browser.new_page()
                def _block_external(route):
                    if route.request.url.startswith('data:'):
                        route.continue_()
                    else:
                        route.abort()
                page.route('**/*', _block_external)
                page.set_content(html_str, wait_until='domcontentloaded')
                pdf_bytes = page.pdf(
                    format='A4',
                    margin={'top': '1.5cm', 'bottom': '2cm', 'left': '1.5cm', 'right': '1.5cm'},
                    print_background=True,
                )
            finally:
                browser.close()
    except Exception as exc:
        logger.error("Company PDF generation failed for %s: %s", check_id, exc)
        return jsonify({'error': 'Ошибка генерации PDF. Используйте кнопку "Печать".'}), 500

    response = make_response(pdf_bytes)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@company_bp.route('/history')
def history():
    """List of company checks for current user."""
    from app.routes.auth import get_current_user
    from app.models.company_check import CompanyCheck
    user = get_current_user()
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
