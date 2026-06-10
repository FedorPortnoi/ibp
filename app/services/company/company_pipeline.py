"""
Company Investigation Pipeline
===============================
3-wave parallel pipeline for company/ИП background checks.

  Wave 0: ЕГРЮЛ lookup (egrul_service)              [0-35%]
  Wave 1: Courts + Sanctions in parallel             [35-75%]
  Wave 2: Risk scoring                               [75-100%]
"""

import logging
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

logger = logging.getLogger(__name__)

# In-memory task store for SSE-style status queries within this process.
# Keyed by task_id → dict with status info.
_company_tasks: dict = {}
_tasks_lock = threading.Lock()


def _log(check, msg: str) -> None:
    """Append a log entry to check.task_log and commit."""
    from app import db
    try:
        log = check.task_log
        log.append({'ts': datetime.utcnow().strftime('%H:%M:%S'), 'msg': msg})
        check.task_log = log
        db.session.commit()
    except Exception as exc:
        logger.debug("_log commit failed: %s", exc)
        try:
            db.session.rollback()
        except Exception:
            pass


def _set_progress(check, pct: int, stage: str, msg: str) -> None:
    """Update progress fields in DB."""
    from app import db
    try:
        check.task_progress = pct
        check.task_stage = stage
        check.task_message = msg
        db.session.commit()
        logger.info("[%s] %d%% — %s", check.inn, pct, msg)
    except Exception as exc:
        logger.debug("_set_progress commit failed: %s", exc)
        try:
            db.session.rollback()
        except Exception:
            pass


def _run_egrul(check) -> dict:
    """Stage 1 — fetch company profile via EGRULService."""
    from app.services.company.egrul_service import EGRULService
    inn = check.inn
    try:
        svc = EGRULService(timeout=25)
        profile = svc.lookup(inn=inn)
        return profile.to_dict() if profile else {}
    except Exception as exc:
        logger.warning("[%s] EGRUL failed: %s", inn, exc)
        return {}


def _run_courts(inn: str, query_name: str, egrul: dict) -> list:
    """Stage 2a — fetch court cases. Receives plain values, not ORM object."""
    from app.services.company.company_court_service import CompanyCourtSearch
    company_name = egrul.get('short_name') or egrul.get('name') or query_name or ''
    if not company_name and not inn:
        return []
    try:
        svc = CompanyCourtSearch(timeout=25)
        cases = svc.search(company_name=company_name, inn=inn, limit=50)
        return [c.to_dict() for c in cases]
    except Exception as exc:
        logger.warning("[%s] Courts failed: %s", inn, exc)
        return []


def _run_financial(inn: str, query_name: str, egrul: dict) -> dict:
    """Stage 2e — fetch financial snapshot from dadata.ru. Plain values only."""
    from app.services.company.financial_service import FinancialService
    try:
        svc = FinancialService(timeout=15)
        return svc.lookup(inn=inn)
    except Exception as exc:
        logger.warning("[%s] Financial data failed: %s", inn, exc)
        return {'found': False, 'unavailable': True}


def _run_gov_contracts(inn: str, query_name: str, egrul: dict) -> dict:
    """Stage 2d — search ЕИС Закупки for government contracts. Plain values only."""
    from app.services.company.gov_contracts_service import GovContractsService
    company_name = egrul.get('short_name') or egrul.get('name') or query_name or ''
    try:
        svc = GovContractsService(timeout=20)
        return svc.lookup(inn=inn, company_name=company_name)
    except Exception as exc:
        logger.warning("[%s] ЕИС Закупки failed: %s", inn, exc)
        return {'found': False, 'unavailable': True}


def _run_bankruptcy(inn: str, query_name: str, egrul: dict) -> dict:
    """Stage 2c — check ЕФРСБ bankruptcy registry. Plain values only."""
    from app.services.company.fedresurs_service import FedresursService
    company_name = egrul.get('short_name') or egrul.get('name') or query_name or ''
    try:
        svc = FedresursService(timeout=20)
        return svc.lookup(inn=inn, company_name=company_name)
    except Exception as exc:
        logger.warning("[%s] ЕФРСБ failed: %s", inn, exc)
        return {'found': False}


def _run_sanctions(inn: str, query_name: str, egrul: dict) -> dict:
    """
    Stage 2b — check local sanctions database (OFAC + UN SC).
    No API key required. Downloads lists on first use, caches for 7 days.
    Returns dict: {results: [...], no_key: bool, unavailable: bool}
    """
    empty = {'results': [], 'no_key': False, 'unavailable': False}
    company_name = egrul.get('name') or egrul.get('short_name') or query_name or ''
    if not company_name:
        return empty
    try:
        from app.services.company.sanctions_local_service import SanctionsLocalService  # noqa: PLC0415
        svc = SanctionsLocalService()
        ogrn = egrul.get('ogrn') or ''
        result = svc.check(company_name=company_name, inn=inn, ogrn=ogrn)
        return {
            'results': result.get('matches', []),
            'no_key': False,
            'unavailable': result.get('unavailable', False),
            'sources_checked': result.get('sources_checked', []),
        }
    except Exception as exc:
        logger.warning("[%s] Sanctions check failed: %s", inn, exc)
        return {**empty, 'unavailable': True}


def _score_risk(egrul: dict, courts: list, sanctions: list, bankruptcy: dict, financial: dict = None) -> tuple:
    """
    Risk scoring for companies.

    Returns (score: int 0-100, level: str, flags: list).
    """
    score = 0
    flags = []

    # ЕФРСБ bankruptcy — definitive signal, higher weight than court inference
    if bankruptcy.get('found'):
        stage = bankruptcy.get('stage') or 'неизвестная стадия'
        if bankruptcy.get('active'):
            score += 75  # pushes straight to critical regardless of other factors
            flags.append({
                'severity': 'critical',
                'text': f'Процедура банкротства (ЕФРСБ): {stage}',
            })
        else:
            # Completed/terminated proceedings — yellow flag
            score += 25
            flags.append({
                'severity': 'medium',
                'text': f'Завершённая процедура банкротства (ЕФРСБ): {stage}',
            })

    # Liquidated or bankruptcy status from EGRUL
    status = (egrul.get('status') or '').lower()
    if any(kw in status for kw in ('ликвидир', 'прекрат', 'прекращ', 'банкрот')):
        score += 25
        flags.append({'severity': 'high', 'text': f'Статус организации: {egrul.get("status", "")}'})

    # Court cases
    defendant_cases = [c for c in courts if c.get('role') in ('ответчик', 'должник')]
    plaintiff_cases = [c for c in courts if c.get('role') == 'истец']
    # Court-inferred bankruptcy only adds weight if ЕФРСБ didn't already flag it
    bankruptcy_cases = [c for c in courts if c.get('case_type') == 'банкротное']
    if bankruptcy_cases and not bankruptcy.get('found'):
        score += 30
        flags.append({'severity': 'critical', 'text': f'Банкротные дела в суде: {len(bankruptcy_cases)}'})

    if defendant_cases:
        pts = min(len(defendant_cases) * 5, 25)
        score += pts
        flags.append({
            'severity': 'medium' if len(defendant_cases) < 5 else 'high',
            'text': f'Ответчик в {len(defendant_cases)} делах',
        })

    if len(plaintiff_cases) >= 5:
        score += 5
        flags.append({'severity': 'low', 'text': f'Частый истец: {len(plaintiff_cases)} дел'})

    # Financial risk indicators
    if financial and financial.get('found'):
        if financial.get('is_loss'):
            score += 15
            yr = financial.get('year', '')
            flags.append({'severity': 'medium', 'text': f'Убыток по итогам {yr} года'})
        if financial.get('debts') and financial['debts'] > 0:
            score += 20
            flags.append({'severity': 'high', 'text': f'Налоговая задолженность: {financial.get("debts_fmt", "")}' })

    # Sanctions
    if sanctions:
        score += 40
        flags.append({
            'severity': 'critical',
            'text': f'Найдено в санкционных списках ({len(sanctions)} совпадений)',
        })

    score = min(score, 100)

    if score <= 20:
        level = 'low'
    elif score <= 45:
        level = 'medium'
    elif score <= 70:
        level = 'high'
    else:
        level = 'critical'

    return score, level, flags


def run_company_pipeline(check_id: str, app) -> None:
    """
    Background thread entry point for company investigation.

    Always runs inside a Flask app context so SQLAlchemy sessions work.
    Uses try/finally on ThreadPoolExecutor (never bare `with`).
    """
    from app import db
    from app.models.company_check import CompanyCheck

    with app.app_context():
        start_time = time.time()
        check = db.session.get(CompanyCheck, check_id)
        if not check:
            logger.error("CompanyCheck %s not found", check_id)
            return

        try:
            check.status = 'running'
            check.task_started_at = datetime.utcnow()
            db.session.commit()

            # ── Wave 0: EGRUL ──────────────────────────────────────────────
            _set_progress(check, 10, 'egrul', 'Запрос ЕГРЮЛ...')
            _log(check, 'Получение данных ЕГРЮЛ/ЕГРИП')
            egrul = _run_egrul(check)

            if egrul:
                check.company_name = egrul.get('name', '')
                check.company_short_name = egrul.get('short_name', '')
                check.company_type = egrul.get('company_type', '')
                check.company_status = egrul.get('status', '')
                check.ogrn = egrul.get('ogrn', '')
                check.egrul_data = egrul
                sources_found = 1
            else:
                sources_found = 0
                _log(check, 'ЕГРЮЛ: данные не найдены')

            _set_progress(check, 35, 'egrul', 'ЕГРЮЛ получен')

            # ── Wave 1: Courts + Sanctions + Bankruptcy (parallel) ─────────
            _set_progress(check, 40, 'courts', 'Поиск судебных дел и банкротства...')
            _log(check, 'Проверка судов, санкций и банкротства')

            # Extract plain values before spawning threads — ORM objects
            # cannot be used outside the main thread's app context.
            _inn = check.inn
            _query_name = check.query_name or ''

            executor = ThreadPoolExecutor(max_workers=5, thread_name_prefix='co_pipeline')
            try:
                court_future      = executor.submit(_run_courts,        _inn, _query_name, egrul)
                sanctions_future  = executor.submit(_run_sanctions,     _inn, _query_name, egrul)
                bankruptcy_future = executor.submit(_run_bankruptcy,    _inn, _query_name, egrul)
                contracts_future  = executor.submit(_run_gov_contracts, _inn, _query_name, egrul)
                financial_future  = executor.submit(_run_financial,     _inn, _query_name, egrul)

                courts = []
                sanctions_wrap = {'results': [], 'no_key': False, 'unavailable': False}
                bankruptcy = {'found': False}
                gov_contracts = {'found': False, 'unavailable': False}
                financial = {'found': False, 'unavailable': False, 'no_key': False,
                            'income': None, 'expense': None, 'profit': None,
                            'is_loss': False, 'income_fmt': '', 'expense_fmt': '',
                            'profit_fmt': '', 'year': None, 'tax_system': '',
                            'debts': None, 'debts_fmt': '', 'employee_count': ''}

                try:
                    courts = court_future.result(timeout=65)
                except Exception as exc:
                    logger.warning("[%s] Courts future failed: %s", check.inn, exc)

                try:
                    sanctions_wrap = sanctions_future.result(timeout=20)
                except Exception as exc:
                    logger.warning("[%s] Sanctions future failed: %s", check.inn, exc)

                try:
                    bankruptcy = bankruptcy_future.result(timeout=25)
                except Exception as exc:
                    logger.warning("[%s] Bankruptcy future failed: %s", check.inn, exc)

                try:
                    gov_contracts = contracts_future.result(timeout=25)
                except Exception as exc:
                    logger.warning("[%s] Gov contracts future failed: %s", check.inn, exc)

                try:
                    # 55s: allows Playwright 45s geo-block timeout + margin
                    financial = financial_future.result(timeout=55)
                except Exception as exc:
                    logger.warning("[%s] Financial future failed: %s", check.inn, exc)

            finally:
                executor.shutdown(wait=False, cancel_futures=True)

            sanctions = sanctions_wrap.get('results', [])
            check.court_records = courts
            check.sanctions_results = sanctions
            check.sanctions_meta = {
                'no_key': sanctions_wrap.get('no_key', False),
                'unavailable': sanctions_wrap.get('unavailable', False),
            }
            check.bankruptcy_data = bankruptcy
            check.gov_contracts_data = gov_contracts
            check.financial_data = financial

            if courts:
                sources_found += 1
                _log(check, f'Суды: {len(courts)} дел')
            if sanctions:
                sources_found += 1
                _log(check, f'Санкции: {len(sanctions)} совпадений')
            elif sanctions_wrap.get('unavailable'):
                _log(check, 'Санкции: базы данных загружаются / недоступны')
            else:
                sources = ', '.join(sanctions_wrap.get('sources_checked', []))
                _log(check, f'Санкции: не найдено ({sources})')
            if gov_contracts.get('found'):
                sources_found += 1
                cnt = gov_contracts.get('total_count', 0)
                amt = gov_contracts.get('total_amount_fmt', '')
                _log(check, f'Госконтракты: {cnt}' + (f' на {amt}' if amt else ''))
            if financial.get('found'):
                sources_found += 1
                inc = financial.get('income_fmt', '')
                yr = financial.get('year', '')
                _log(check, f'Финансы {yr}: доходы {inc}')
            elif financial.get('no_key'):
                _log(check, 'Финансы: DADATA_API_KEY не настроен')
            if bankruptcy.get('found'):
                sources_found += 1
                stage = bankruptcy.get('stage', '')
                _log(check, f'ЕФРСБ: банкротство — {stage}' if stage else 'ЕФРСБ: найдена процедура банкротства')
            else:
                _log(check, 'ЕФРСБ: банкротство не найдено')

            _set_progress(check, 75, 'courts', f'Суды: {len(courts)} дел')

            # ── ИП identity patch from dadata ──────────────────────────────
            # egrul.org is often stale or misses the entrepreneur's name for 12-digit INNs.
            # dadata returns name and current status in the same call already made for
            # financials — reuse those fields here at no extra quota cost.
            if len(_inn) == 12:
                party_name = financial.get('party_name') or financial.get('party_short_name')
                if party_name and (not check.company_name or check.company_name == check.inn):
                    check.company_name = financial.get('party_name') or party_name
                    check.company_short_name = financial.get('party_short_name') or party_name
                    _log(check, f'ИП: наименование получено из dadata — {check.company_short_name}')
                if financial.get('party_status'):
                    check.company_status = financial['party_status']
                    egrul['status'] = financial['party_status']  # risk scorer reads this
                    _egrul = check.egrul_data or {}
                    _egrul['status'] = financial['party_status']
                    if financial.get('party_liquidation_date'):
                        _egrul['liquidation_date'] = financial['party_liquidation_date']
                        _log(check, f'ИП: прекращение деятельности {financial["party_liquidation_date"]}')
                    check.egrul_data = _egrul

            # ── Wave 2: Risk scoring ────────────────────────────────────────
            _set_progress(check, 85, 'risk', 'Оценка рисков...')
            score, level, flags = _score_risk(egrul, courts, sanctions, bankruptcy, financial)
            check.risk_score = score
            check.risk_level = level
            check.risk_flags = flags

            # ── Finalize ────────────────────────────────────────────────────
            check.sources_checked = sources_found
            check.check_duration_seconds = round(time.time() - start_time, 1)
            check.status = 'complete'
            check.completed_at = datetime.utcnow()
            check.task_progress = 100
            check.task_stage = 'complete'
            check.task_message = 'Расследование завершено'
            _log(check, f'Завершено за {check.check_duration_seconds}s')
            db.session.commit()

        except Exception as exc:
            logger.exception("[%s] Pipeline error: %s", check_id, exc)
            try:
                check.status = 'error'
                check.task_error = str(exc)
                check.task_progress = 0
                db.session.commit()
            except Exception:
                db.session.rollback()
