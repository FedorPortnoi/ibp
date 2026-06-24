"""
Company Investigation Pipeline
===============================
3-wave parallel pipeline for company/ИП background checks.

  Wave 0: ЕГРЮЛ lookup (egrul_service)                         [0-35%]
  Wave 1: Courts + Sanctions + FSSP + Adverse media (parallel)  [35-75%]
  Wave 2: Risk scoring + AI summary                             [75-100%]
"""

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
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
    """Stage 2d — government contracts: zakupki.gov.ru (free) → DataNewton fallback."""
    try:
        from app.services.company.free_gov_service import fetch_gov_contracts
        result = fetch_gov_contracts(inn)
        if not result.get('unavailable'):
            return result
    except Exception as exc:
        logger.warning("[%s] zakupki.gov.ru contracts failed: %s", inn, exc)
    try:
        from app.services.company.datanewton_service import lookup_gov_contracts
        return lookup_gov_contracts(inn)
    except Exception as exc:
        logger.warning("[%s] Gov contracts fallback failed: %s", inn, exc)
        return {'found': False, 'unavailable': True}


def _run_bankruptcy(inn: str, query_name: str, egrul: dict) -> dict:
    """Stage 2c — bankruptcy: bankrot.fedresurs.ru (free) → DataNewton fallback."""
    try:
        from app.services.company.free_gov_service import fetch_bankruptcy
        result = fetch_bankruptcy(inn)
        if not result.get('unavailable'):
            return result
    except Exception as exc:
        logger.warning("[%s] fedresurs bankruptcy failed: %s", inn, exc)
    try:
        from app.services.company.datanewton_service import lookup_bankruptcy
        return lookup_bankruptcy(inn)
    except Exception as exc:
        logger.warning("[%s] Bankruptcy fallback failed: %s", inn, exc)
        return {'found': False}


def _run_rnp(inn: str) -> dict:
    """Stage 2f — check РНП (реестр недобросовестных поставщиков). Plain values only."""
    from app.services.company.rnp_service import RNPService
    try:
        svc = RNPService(timeout=20)
        return svc.lookup(inn=inn)
    except Exception as exc:
        logger.warning("[%s] РНП failed: %s", inn, exc)
        return {'found': False, 'unavailable': True}


def _run_fssp_company(inn: str, egrul: dict) -> dict:
    """Stage 2g — FSSP: parser-api.com search_ur_by_inn (PARSER_API_KEY) → DataNewton fallback."""
    empty = {'found': False, 'unavailable': False, 'proceedings': [], 'active_count': 0, 'total_count': 0, 'source': ''}
    if not inn:
        return empty
    try:
        from app.services.parser_api import fssp_search_ur, is_available
        if is_available():
            items, status = fssp_search_ur(inn)
            if status in ('ok', 'empty'):
                if not items:
                    return {**empty, 'source': 'parser-api.com (ФССП)'}
                proceedings = []
                active_count = 0
                for item in items:
                    end_date = item.get('stop_date') or ''
                    is_active = not end_date
                    if is_active:
                        active_count += 1
                    proceedings.append({
                        'number':     item.get('id') or item.get('process_id') or '',
                        'subject':    item.get('process_title') or item.get('subjects', [{}])[0].get('name', '') if item.get('subjects') else (item.get('process_title') or ''),
                        'amount':     _parse_fssp_amount(item),
                        'department': item.get('department_title') or '',
                        'start_date': item.get('process_date') or '',
                        'end_date':   end_date,
                        'end_reason': item.get('stop_reason') or '',
                        'is_active':  is_active,
                    })
                logger.info("[%s] parser-api FSSP → %d proceedings (%d active)", inn, len(proceedings), active_count)
                return {
                    'found': True, 'unavailable': False,
                    'proceedings': proceedings,
                    'active_count': active_count,
                    'total_count': len(proceedings),
                    'source': 'parser-api.com (ФССП)',
                }
    except Exception as exc:
        logger.warning("[%s] parser-api FSSP failed: %s", inn, exc)
    try:
        from app.services.company.datanewton_service import lookup_fssp_company
        return lookup_fssp_company(inn)
    except Exception as exc:
        logger.warning("[%s] FSSP fallback failed: %s", inn, exc)
        return {**empty, 'unavailable': True}


def _run_risks(inn: str) -> dict:
    """Stage 2j — DataNewton pre-computed risk flags."""
    try:
        from app.services.company.datanewton_service import lookup_risks
        return lookup_risks(inn)
    except Exception as exc:
        logger.warning("[%s] Risks failed: %s", inn, exc)
        return {'found': False, 'risks': []}


def _run_tax_info(inn: str) -> dict:
    """Stage 2k — DataNewton tax debts and violations."""
    try:
        from app.services.company.datanewton_service import lookup_tax_info
        return lookup_tax_info(inn)
    except Exception as exc:
        logger.warning("[%s] Tax info failed: %s", inn, exc)
        return {'found': False}


def _run_blocked_accounts(inn: str) -> dict:
    """Stage 2l — FNS blocked accounts: service.nalog.ru (free) → DataNewton fallback."""
    try:
        from app.services.company.free_gov_service import fetch_blocked_accounts
        result = fetch_blocked_accounts(inn)
        if not result.get('unavailable'):
            return result
    except Exception as exc:
        logger.warning("[%s] nalog.ru blocked accounts failed: %s", inn, exc)
    try:
        from app.services.company.datanewton_service import lookup_blocked_accounts
        return lookup_blocked_accounts(inn)
    except Exception as exc:
        logger.warning("[%s] Blocked accounts fallback failed: %s", inn, exc)
        return {'found': False, 'blocks': []}


def _run_inspections(inn: str) -> dict:
    """Stage 2m — inspections: proverki.gov.ru (free) → DataNewton fallback."""
    try:
        from app.services.company.free_gov_service import fetch_inspections
        result = fetch_inspections(inn)
        if not result.get('unavailable'):
            return result
    except Exception as exc:
        logger.warning("[%s] proverki.gov.ru failed: %s", inn, exc)
    try:
        from app.services.company.datanewton_service import lookup_inspections
        return lookup_inspections(inn)
    except Exception as exc:
        logger.warning("[%s] Inspections fallback failed: %s", inn, exc)
        return {'found': False, 'inspections': []}


def _parse_fssp_amount(item: dict):
    """Extract numeric amount from a parser-api FSSP result dict."""
    import re
    subjects = item.get('subjects') or []
    raw = ''
    if subjects and isinstance(subjects[0], dict):
        raw = subjects[0].get('sum', '') or ''
    if not raw:
        raw = item.get('process_total', '') or ''
    if not raw:
        return None
    m = re.search(r'(\d[\d\s\xa0]*)(?:[,.](\d{1,2}))?', raw)
    if not m:
        return None
    try:
        intpart = m.group(1).replace(' ', '').replace('\xa0', '')
        dec = m.group(2) or '0'
        return float(f'{intpart}.{dec}')
    except (ValueError, TypeError):
        return None


def _run_adverse_media_company(company_name: str, inn: str, egrul: dict) -> dict:
    """Stage 2h — adverse media search for a company."""
    empty = {'hits': [], 'status': 'unavailable', 'hit_count': 0}
    if not company_name:
        return empty
    try:
        from app.services.candidate.adverse_media_service import search_adverse_media, is_available
        if not is_available():
            return empty
        region = egrul.get('region') or egrul.get('address') or ''
        context = {
            'inns': [inn] if inn else [],
            'companies': [company_name],
            'birth_year': None,
            'city': region,
        }
        hits, status = search_adverse_media(company_name, context=context)
        return {
            'hits': [h.to_dict() for h in hits],
            'status': status,
            'hit_count': len(hits),
        }
    except Exception as exc:
        logger.warning("[%s] Adverse media failed: %s", inn, exc)
        return empty



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


def _score_risk(egrul: dict, courts: list, sanctions: list, bankruptcy: dict, financial: dict = None, rnp: dict = None, fssp: dict = None, risks: dict = None, tax_info: dict = None, blocked_accounts: dict = None) -> tuple:
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

    # РНП — Реестр недобросовестных поставщиков
    if rnp and rnp.get('found'):
        if rnp.get('active'):
            score += 50
            flags.append({
                'severity': 'critical',
                'text': 'Включён в реестр недобросовестных поставщиков (активная запись)',
            })
        else:
            score += 20
            flags.append({
                'severity': 'medium',
                'text': 'Ранее включался в реестр недобросовестных поставщиков (истёкшая запись)',
            })

    # Sanctions
    if sanctions:
        score += 40
        flags.append({
            'severity': 'critical',
            'text': f'Найдено в санкционных списках ({len(sanctions)} совпадений)',
        })

    # FSSP enforcement proceedings
    if fssp and fssp.get('found'):
        active = fssp.get('active_count', 0)
        total = fssp.get('total_count', 0)
        if active:
            score += min(active * 10, 30)
            flags.append({
                'severity': 'high',
                'text': f'ФССП: {active} активных исполнительных производств (всего {total})',
            })
        elif total:
            score += 10
            flags.append({
                'severity': 'medium',
                'text': f'ФССП: {total} завершённых исполнительных производств',
            })

    # DataNewton pre-computed risk flags
    if risks and risks.get('found'):
        for risk in risks.get('risks', []):
            sev = risk.get('severity', 'medium')
            pts = {'critical': 30, 'high': 20, 'medium': 10, 'low': 5}.get(sev, 10)
            score += pts
            flags.append({'severity': sev, 'text': risk.get('name', '')})

    # Tax debts and violations
    if tax_info and tax_info.get('found'):
        debt = tax_info.get('tax_debt')
        if debt and float(debt) > 0:
            score += 25
            flags.append({
                'severity': 'high',
                'text': f'Налоговая задолженность (ФНС): {tax_info.get("tax_debt_fmt", "")}',
            })
        if tax_info.get('violations'):
            score += 15
            flags.append({
                'severity': 'high',
                'text': f'Налоговые нарушения: {len(tax_info["violations"])}',
            })

    # Blocked bank accounts
    if blocked_accounts and blocked_accounts.get('found'):
        n = len(blocked_accounts.get('blocks', []))
        score += min(n * 15, 40)
        flags.append({
            'severity': 'critical',
            'text': f'ФНС: заблокированы банковские счета ({n})',
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

            # ── Wave 1: Courts + Sanctions + Bankruptcy + FSSP + Adverse media (parallel) ──
            _set_progress(check, 40, 'courts', 'Поиск судебных дел, ФССП и банкротства...')
            _log(check, 'Проверка судов, санкций, ФССП, банкротства и репутации')

            # Extract plain values before spawning threads — ORM objects
            # cannot be used outside the main thread's app context.
            _inn = check.inn
            _query_name = check.query_name or ''
            _company_name = check.company_name or egrul.get('short_name') or egrul.get('name') or _query_name or ''

            executor = ThreadPoolExecutor(max_workers=13, thread_name_prefix='co_pipeline')
            try:
                court_future           = executor.submit(_run_courts,               _inn, _query_name, egrul)
                sanctions_future       = executor.submit(_run_sanctions,            _inn, _query_name, egrul)
                bankruptcy_future      = executor.submit(_run_bankruptcy,           _inn, _query_name, egrul)
                contracts_future       = executor.submit(_run_gov_contracts,        _inn, _query_name, egrul)
                financial_future       = executor.submit(_run_financial,            _inn, _query_name, egrul)
                rnp_future             = executor.submit(_run_rnp,                  _inn)
                fssp_future            = executor.submit(_run_fssp_company,         _inn, egrul)
                adverse_future         = executor.submit(_run_adverse_media_company, _company_name, _inn, egrul)
                risks_future           = executor.submit(_run_risks,                _inn)
                tax_info_future        = executor.submit(_run_tax_info,             _inn)
                blocked_future         = executor.submit(_run_blocked_accounts,     _inn)
                inspections_future     = executor.submit(_run_inspections,          _inn)

                courts = []
                sanctions_wrap = {'results': [], 'no_key': False, 'unavailable': False}
                bankruptcy = {'found': False}
                gov_contracts = {'found': False, 'unavailable': False}
                financial = {'found': False, 'unavailable': False, 'no_key': False,
                            'income': None, 'expense': None, 'profit': None,
                            'is_loss': False, 'income_fmt': '', 'expense_fmt': '',
                            'profit_fmt': '', 'year': None, 'tax_system': '',
                            'debts': None, 'debts_fmt': '', 'employee_count': ''}
                rnp = {'found': False, 'unavailable': False}
                fssp = {'found': False, 'unavailable': False, 'proceedings': [], 'active_count': 0, 'total_count': 0}
                adverse_media = {'hits': [], 'status': 'unavailable', 'hit_count': 0}
                risks = {'found': False, 'risks': []}
                tax_info = {'found': False}
                blocked_accounts = {'found': False, 'blocks': []}
                inspections = {'found': False, 'inspections': []}

                try:
                    courts = court_future.result(timeout=30)
                except Exception as exc:
                    logger.warning("[%s] Courts future failed: %s", check.inn, exc)

                try:
                    sanctions_wrap = sanctions_future.result(timeout=20)
                except Exception as exc:
                    logger.warning("[%s] Sanctions future failed: %s", check.inn, exc)

                try:
                    bankruptcy = bankruptcy_future.result(timeout=20)
                except Exception as exc:
                    logger.warning("[%s] Bankruptcy future failed: %s", check.inn, exc)

                try:
                    gov_contracts = contracts_future.result(timeout=20)
                except Exception as exc:
                    logger.warning("[%s] Gov contracts future failed: %s", check.inn, exc)

                try:
                    financial = financial_future.result(timeout=30)
                except Exception as exc:
                    logger.warning("[%s] Financial future failed: %s", check.inn, exc)

                try:
                    rnp = rnp_future.result(timeout=20)
                except Exception as exc:
                    logger.warning("[%s] РНП future failed: %s", check.inn, exc)

                try:
                    fssp = fssp_future.result(timeout=20)
                except Exception as exc:
                    logger.warning("[%s] FSSP future failed: %s", check.inn, exc)

                try:
                    adverse_media = adverse_future.result(timeout=30)
                except Exception as exc:
                    logger.warning("[%s] Adverse media future failed: %s", check.inn, exc)

                try:
                    risks = risks_future.result(timeout=20)
                except Exception as exc:
                    logger.warning("[%s] Risks future failed: %s", check.inn, exc)

                try:
                    tax_info = tax_info_future.result(timeout=20)
                except Exception as exc:
                    logger.warning("[%s] Tax info future failed: %s", check.inn, exc)

                try:
                    blocked_accounts = blocked_future.result(timeout=20)
                except Exception as exc:
                    logger.warning("[%s] Blocked accounts future failed: %s", check.inn, exc)

                try:
                    inspections = inspections_future.result(timeout=20)
                except Exception as exc:
                    logger.warning("[%s] Inspections future failed: %s", check.inn, exc)

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
            check.rnp_data = rnp
            check.fssp_data = fssp
            check.adverse_media = adverse_media
            check.risks_data = risks
            check.tax_info_data = tax_info
            check.blocked_accounts_data = blocked_accounts
            check.inspections_data = inspections

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
            if rnp.get('found'):
                sources_found += 1
                active_str = 'активная запись' if rnp.get('active') else 'истёкшая запись'
                cnt = len(rnp.get('entries', []))
                _log(check, f'РНП: {cnt} запис{"ь" if cnt == 1 else "и" if cnt < 5 else "ей"} ({active_str})')
            elif rnp.get('unavailable'):
                _log(check, 'РНП: zakupki.gov.ru недоступен (geo-block)')
            else:
                _log(check, 'РНП: не найдено')

            if fssp.get('found'):
                sources_found += 1
                _log(check, f'ФССП: {fssp["total_count"]} производств ({fssp["active_count"]} активных) [{fssp.get("source", "")}]')
            elif fssp.get('unavailable'):
                _log(check, 'ФССП: сервис недоступен')
            else:
                _log(check, 'ФССП: производств не найдено')

            am_status = adverse_media.get('status', 'unavailable')
            am_count = adverse_media.get('hit_count', 0)
            if am_status in ('ok',) and am_count:
                sources_found += 1
                _log(check, f'Adverse media: {am_count} упоминаний')
            elif am_status == 'empty':
                _log(check, 'Adverse media: негативных упоминаний не найдено')
            else:
                _log(check, f'Adverse media: {am_status}')

            if risks.get('found'):
                sources_found += 1
                _log(check, f'Риски (DataNewton): {len(risks.get("risks", []))} флагов')
            if tax_info.get('found'):
                sources_found += 1
                debt_str = tax_info.get('tax_debt_fmt', '')
                _log(check, f'Налоги (ФНС): задолженность {debt_str}' if debt_str else 'Налоги (ФНС): данные получены')
            if blocked_accounts.get('found'):
                sources_found += 1
                _log(check, f'Блокировки счетов (ФНС): {len(blocked_accounts.get("blocks", []))}')
            if inspections.get('found'):
                sources_found += 1
                _log(check, f'Проверки: {inspections.get("total", 0)}')

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
            _set_progress(check, 80, 'risk', 'Оценка рисков...')
            score, level, flags = _score_risk(egrul, courts, sanctions, bankruptcy, financial, rnp, fssp, risks, tax_info, blocked_accounts)
            check.risk_score = score
            check.risk_level = level
            check.risk_flags = flags

            # ── AI executive summary ───────────────────────────────────────
            _set_progress(check, 90, 'ai', 'Генерация AI-резюме...')
            try:
                from app.services.ai.claude_integration import generate_company_summary, is_available as ai_available
                if ai_available():
                    defendant_count = sum(1 for c in courts if c.get('role') in ('ответчик', 'должник'))
                    summary_data = {
                        'company_name': check.company_name or '',
                        'inn': check.inn,
                        'company_status': check.company_status or '',
                        'risk_level': level,
                        'risk_score': score,
                        'risk_flags': flags,
                        'court_count': len(courts),
                        'defendant_count': defendant_count,
                        'sanctions_count': len(sanctions),
                        'bankruptcy': bankruptcy,
                        'financial': financial,
                        'rnp_found': rnp.get('found', False),
                        'fssp_count': fssp.get('total_count', 0),
                        'adverse_media_count': adverse_media.get('hit_count', 0),
                    }
                    ai_text = generate_company_summary(summary_data)
                    if ai_text:
                        check.ai_summary = ai_text
                        _log(check, 'AI-резюме сгенерировано')
            except Exception as exc:
                logger.warning("[%s] AI summary failed: %s", check.inn, exc)

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
