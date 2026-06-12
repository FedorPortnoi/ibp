"""
Candidate Check Pipeline
========================
Orchestrates the 9-stage unified background check (Stage 0-8).

Wave-based parallel execution for speed:
  Wave 0: Stage 0 — Identity (ЕГРЮЛ + Bankruptcy in parallel)  [0-8%]
  Wave 1: Stage 1 + Stage 2 in parallel (60s timeout)          [8-27%]
          Stage 1 — Gov Registries (courts, ФССП, checko.ru)
          Stage 2 — Security (sanctions + MVD passport)
  Wave 2: Stage 3 — Social Media (VK+TG+Phone ALL parallel)    [27-42%]
  Wave 3: Stage 4 + Stage 5 in parallel                        [42-72%]
          Stage 4 — Contact Discovery (4 internal waves)
          Stage 5 — Deep Social Analysis (face, Snoop, graph)
  Wave 4: Stage 6 — Behavioral Intelligence (6 parallel subs)  [72-83%]
  Wave 5: Stage 7 — Risk Scoring                               [83-93%]
  Wave 6: Stage 8 — Report Generation                          [93-100%]
"""

import json
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

logger = logging.getLogger(__name__)


def _normalize_court_confidence(records, candidate_region=None):
    """Normalize court confidence to VERIFIED/LIKELY/POSSIBLE/UNVERIFIED scale.

    court_search.py returns 'high'/'medium' but the template and risk_scorer
    expect the four-level VERIFIED/LIKELY/POSSIBLE/UNVERIFIED system.

    Baseline per source:
      - судебныерешения.рф: POSSIBLE (participant-name search)
      - reputation.su: POSSIBLE (aggregator, name search)
      - kad.arbitr.ru: POSSIBLE for name matches (official cardfile, but a
        ФИО search still hits namesakes); INN-matched cases arrive already
        VERIFIED from court_search and are preserved below
      - sudact.ru: UNVERIFIED (full-text search, name may appear anywhere)

    Records whose confidence is already on the four-level scale keep it
    (the source asserted a final confidence, e.g. kad INN match).
    If the candidate's region matches the court name → upgrade one level.
    """
    SOURCE_BASELINE = {
        'судебныерешения.рф': 'POSSIBLE',
        'reputation.su': 'POSSIBLE',
        'kad.arbitr.ru': 'POSSIBLE',
        'sudact.ru': 'UNVERIFIED',
    }
    UPGRADE = {
        'UNVERIFIED': 'POSSIBLE',
        'POSSIBLE': 'LIKELY',
        'LIKELY': 'VERIFIED',
        'VERIFIED': 'VERIFIED',
    }
    FINAL_LEVELS = ('VERIFIED', 'LIKELY', 'POSSIBLE', 'UNVERIFIED')
    # Generic geography words would match ANY "... областной суд" — only the
    # distinctive part of the region name may trigger an upgrade.
    REGION_STOPWORDS = {
        'область', 'край', 'республика', 'город', 'округ',
        'автономный', 'автономная', 'федеральный', 'федерального',
    }

    region_keywords = []
    if candidate_region:
        for word in candidate_region.lower().replace('-', ' ').split():
            if len(word) >= 4 and word not in REGION_STOPWORDS:
                # Court names inflect region adjectives (Свердловская →
                # суд СвердловскОЙ области) — match on a stem, not the
                # exact form, or the upgrade never fires.
                stem = word[:-2] if len(word) >= 6 else word
                region_keywords.append(stem)

    for r in records:
        if r.get('confidence') in FINAL_LEVELS:
            continue  # source already assigned a final confidence
        source = r.get('source', '')
        r['confidence'] = SOURCE_BASELINE.get(source, 'UNVERIFIED')

        if region_keywords:
            court = r.get('court_name', '').lower()
            if any(kw in court for kw in region_keywords):
                r['confidence'] = UPGRADE[r['confidence']]

    return records


def _is_demo_mode():
    """Check if we're running without real API keys."""
    return not os.environ.get('VK_SERVICE_TOKEN')


def _get_demo_gov_data(full_name):
    """Return realistic demo data for Stage 1 government registries."""
    parts = full_name.split()
    last = parts[0] if parts else 'Иванов'
    first = parts[1] if len(parts) > 1 else 'Иван'

    biz = [
        {
            'name': f'ООО "Альфа-Строй"',
            'inn': '7707123456',
            'ogrn': '1027700123456',
            'role': 'Учредитель',
            'status': 'Действующее',
            'registration_date': '15.03.2018',
            'address': 'г. Москва, ул. Ленина, д. 10',
            'source': 'nalog.ru',
        },
        {
            'name': f'ИП {last} {first}',
            'inn': '770712345678',
            'ogrn': '312770700012345',
            'role': 'Индивидуальный предприниматель',
            'status': 'Действующее',
            'registration_date': '01.09.2020',
            'address': 'г. Москва',
            'source': 'nalog.ru',
        },
    ]

    courts = [
        {
            'case_number': '2-1234/2023',
            'court_name': 'Тверской районный суд г. Москвы',
            'case_type': 'Гражданское дело',
            'article': 'ст. 395 ГК РФ',
            'role': 'Ответчик',
            'date': '15.06.2023',
            'result': 'Удовлетворено частично',
            'source': 'sudact.ru',
        },
    ]

    fssp = [
        {
            'debtor_name': full_name,
            'debtor_dob': '',
            'proceedings_number': '12345/23/77001-ИП',
            'document_details': 'Судебный приказ №2-1234/2023 от 15.06.2023',
            'subject': 'Взыскание задолженности',
            'amount': 45000.0,
            'department': 'Тверской РОСП г. Москвы',
            'is_active': False,
            'end_date': '20.12.2023',
            'end_reason': 'Исполнено',
            'source': 'demo',
        },
    ]

    bankruptcy = []  # No bankruptcy for clean demo persona

    return biz, courts, fssp, bankruptcy


def _get_demo_sanctions():
    """Return realistic demo data for Stage 2 sanctions checks."""
    return [
        {
            'source_name': 'Росфинмониторинг',
            'checked': True,
            'found': False,
            'match_details': None,
            'error': None,
            'url': 'https://fedsfm.ru/documents/terr-list',
        },
        {
            'source_name': 'МВД — розыск',
            'checked': True,
            'found': False,
            'match_details': None,
            'error': None,
            'url': 'https://xn--b1aew.xn--p1ai/wanted',
        },
        {
            'source_name': 'Интерпол',
            'checked': True,
            'found': False,
            'match_details': None,
            'error': None,
            'url': 'https://www.interpol.int/How-we-work/Notices/View-Red-Notices',
        },
        {
            'source_name': 'Перечень экстремистов',
            'checked': True,
            'found': False,
            'match_details': None,
            'error': None,
            'url': 'https://minjust.gov.ru/ru/extremist-materials/',
        },
    ]


def _get_demo_contacts(full_name):
    """Return realistic demo data for Stage 4 contacts."""
    parts = full_name.split()
    last = (parts[0] if parts else 'ivanov').lower()
    first = (parts[1] if len(parts) > 1 else 'ivan').lower()

    # Transliterate basic Cyrillic → Latin for email generation
    translit = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e',
        'ё': 'e', 'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k',
        'л': 'l', 'м': 'm', 'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r',
        'с': 's', 'т': 't', 'у': 'u', 'ф': 'f', 'х': 'kh', 'ц': 'ts',
        'ч': 'ch', 'ш': 'sh', 'щ': 'shch', 'ъ': '', 'ы': 'y', 'ь': '',
        'э': 'e', 'ю': 'yu', 'я': 'ya',
    }
    first_lat = ''.join(translit.get(c, c) for c in first)
    last_lat = ''.join(translit.get(c, c) for c in last)

    return {
        'phones': [
            {
                'number': '+79161234501',
                'source': 'vk_profile',
                'confidence': 'средняя',
                'profile_name': 'VK профиль',
                'raw_value': '+7 (916) 123-45-01',
            },
        ],
        'emails': [
            {
                'email': f'{first_lat}.{last_lat}@mail.ru',
                'source': 'email_guess',
                'confidence': 'низкая',
                'verified': False,
                'profile_name': 'Транслитерация имени',
                'services': [],
            },
            {
                'email': f'{first_lat}_{last_lat}@yandex.ru',
                'source': 'email_guess',
                'confidence': 'низкая',
                'verified': False,
                'profile_name': 'Транслитерация имени',
                'services': [],
            },
        ],
    }

# In-memory task status (same pattern as Phase 2)
candidate_tasks = {}
_tasks_lock = threading.Lock()


def _kill_playwright_zombies(max_age_seconds=90):
    """Kill orphaned headless Chrome/Chromium processes spawned by Playwright.

    Called at both investigation START and END so zombies never accumulate
    across runs. Default threshold is 90s — shorter than any stage timeout,
    so a process from the previous investigation is always old enough to kill
    by the time the next one begins.

    Windows note: Playwright on Windows launches chrome.exe (not chromium).
    The name check covers both; cmdline access may be restricted for Chrome
    subprocesses, so we also match on 'playwright' in the data-dir path.
    """
    try:
        import psutil
    except ImportError:
        return

    cutoff = time.time() - max_age_seconds
    killed = 0
    for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time']):
        try:
            name = (proc.info.get('name') or '').lower()
            cmdline_list = proc.info.get('cmdline') or []
            cmdline_str = ' '.join(cmdline_list).lower()

            is_chrome = 'chromium' in name or 'chrome' in name
            is_headless = (
                '--headless' in cmdline_str
                or 'playwright' in cmdline_str
            )
            is_old = proc.info.get('create_time', time.time()) < cutoff

            if is_chrome and is_headless and is_old:
                proc.kill()
                killed += 1
                logger.info("Killed zombie Chrome PID %d (%s)", proc.pid, name)
        except Exception:
            pass
    if killed:
        logger.warning("Playwright cleanup: killed %d zombie Chrome process(es)", killed)


def cleanup_old_tasks(task_store, max_age_seconds=3600):
    """Remove completed tasks older than max_age_seconds and force-complete stale ones."""
    _kill_playwright_zombies()
    now = datetime.now()
    expired = []
    with _tasks_lock:
        for task_id, task in task_store.items():
            # Remove completed tasks after max_age_seconds
            if task.completed_at and (now - task.completed_at).total_seconds() > max_age_seconds:
                expired.append(task_id)
            # Force-complete tasks stuck running for >30 minutes
            elif hasattr(task, 'started_at') and task.started_at and not task.completed_at:
                elapsed = (now - task.started_at).total_seconds()
                if elapsed > 1800:
                    task.error = f"Pipeline timed out after {int(elapsed)}s"
                    task.completed_at = now
                    task.is_complete = True
                    task._sync_to_db()
                    logger.warning(f"Force-completed stale task {task_id} after {int(elapsed)}s")
                    expired.append(task_id)
            # Remove very old stuck tasks (prevent memory leak)
            elif hasattr(task, 'started_at') and task.started_at:
                if (now - task.started_at).total_seconds() > max_age_seconds * 4:
                    expired.append(task_id)
        for task_id in expired:
            del task_store[task_id]


class CandidateTaskStatus:
    """Progress tracker for a running candidate check.

    Maintains in-memory state AND syncs progress to the DB so that
    any gunicorn worker can serve the progress endpoint (Bug #1 fix).
    """

    def __init__(self, task_id: str, check_id: str, full_name: str):
        self.task_id = task_id
        self.check_id = check_id
        self.full_name = full_name

        self.current_stage = 'initializing'
        self.current_step = ''
        self.percent_complete = 0
        self.messages = []

        self.started_at = datetime.now()
        self.completed_at = None
        self.error = None
        self.cancelled = False
        self.is_complete = False
        self._check = None  # Bound CandidateCheck for DB persistence

    def bind_check(self, check):
        """Bind to a CandidateCheck instance for DB persistence."""
        self._check = check

    def add_message(self, text: str, msg_type: str = 'info'):
        self.messages.append({
            'text': text,
            'type': msg_type,
            'time': datetime.now().isoformat(),
        })

    def update(self, stage: str, step: str, percent: int):
        self.current_stage = stage
        self.current_step = step
        self.percent_complete = percent
        self.add_message(step)
        self._sync_to_db()

    def _sync_to_db(self):
        """Persist progress to DB for cross-worker visibility."""
        if not self._check:
            return
        try:
            from app import db
            self._check.task_progress = self.percent_complete
            self._check.task_stage = self.current_stage
            self._check.task_message = self.current_step
            self._check.task_error = self.error
            self._check.task_log = self.messages[-40:]
            db.session.commit()
        except Exception as e:
            logger.debug(f"Task progress DB sync: {e}")
            try:
                from app import db
                db.session.rollback()
            except Exception as e2:
                logger.warning(f"Non-critical error during rollback: {e2}")

    def to_dict(self):
        if self.error:
            status = 'error'
        elif self.cancelled:
            status = 'cancelled'
        elif self.completed_at:
            status = 'complete'
        else:
            status = 'running'

        if status in ('complete', 'error', 'cancelled'):
            self.is_complete = True

        return {
            'task_id': self.task_id,
            'check_id': self.check_id,
            'status': status,
            'full_name': self.full_name,
            'current_stage': self.current_stage,
            'current_step': self.current_step,
            'percent_complete': self.percent_complete,
            'messages': self.messages[-40:],
            'error': self.error,
            'is_complete': self.is_complete,
        }


def _run_stage2_computation(effective_name, inn, passport_series, passport_number):
    """Run Stage 2 (security checks) computation in background.

    Pure computation — no DB access, no task.update() calls.
    Returns (sanctions_results, passport_result).
    """
    from app.services.candidate.sanctions_check import SanctionsService
    sanctions_svc = SanctionsService()
    sanctions_results = sanctions_svc.check_all(effective_name, inn=inn)

    passport_result = None
    if passport_series and passport_number:
        try:
            from app.services.phase3.passport_check import check_passport_mvd
            passport_result = check_passport_mvd(passport_series, passport_number)
        except Exception as e:
            logger.warning(f"Stage 2 passport check failed in background: {e}")
            passport_result = {'valid': None, 'checked': False, 'error': str(e)}

    return sanctions_results, passport_result


def _make_ctx_wrapper(app_obj):
    """Create a wrapper that ensures Flask app context in ThreadPoolExecutor threads.

    Usage inside run_candidate_pipeline:
        _ctx = _make_ctx_wrapper(app)
        pool.submit(_ctx(some_func), arg1, arg2)
    """
    def _wrap(fn):
        """Return a new callable that pushes app context before calling *fn*."""
        from functools import wraps

        @wraps(fn)
        def _inner(*a, **kw):
            with app_obj.app_context():
                return fn(*a, **kw)
        return _inner
    return _wrap


def run_candidate_pipeline(app, task_id: str, check_id: str):
    """
    Background pipeline — runs inside a thread with app context.

    Wave-based parallel pipeline. See module docstring for wave breakdown.
    """
    with _tasks_lock:
        task = candidate_tasks.get(task_id)
    if not task:
        return

    # Clean up zombie Playwright processes from prior timed-out runs before
    # launching new ones — prevents progressive VPS memory exhaustion.
    _kill_playwright_zombies()

    # Helper to propagate Flask app context into ThreadPoolExecutor threads.
    _ctx = _make_ctx_wrapper(app)

    with app.app_context():
        from app import db
        from app.models.candidate_check import CandidateCheck

        check = db.session.get(CandidateCheck, check_id)
        if not check:
            task.error = 'Check record not found'
            return

        task.bind_check(check)
        check.status = 'running'
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.error(f"DB commit failed setting status to running: {e}")

        sources_checked = 0
        sources_with_results = 0
        all_red_flags = []

        try:
            demo_mode = _is_demo_mode()
            logger.warning(
                "Candidate pipeline demo_mode=%s (VK_SERVICE_TOKEN=%s)",
                demo_mode,
                "set" if os.environ.get('VK_SERVICE_TOKEN') else "missing",
            )
            if demo_mode:
                task.add_message(
                    "Demo mode is ON: VK_SERVICE_TOKEN is not configured; results may be degraded.",
                    "warning",
                )
                task._sync_to_db()

            # ══════════════════════════════════════════════
            # STAGE 0: IDENTITY CONFIRMATION [0-8%]
            # ══════════════════════════════════════════════
            task.update('identity', 'Подтверждение личности по ИНН...', 1)

            identity_data = {
                'egrul_status': 'not_checked',
                'confirmed_name': check.full_name,
                'linked_companies': [],
                'business_network': [],
                'bankruptcy_status': 'not_checked',
                'name_discrepancy': False,
            }
            bankruptcy_records = []

            # Step 0.1 + 0.2 — ЕГРЮЛ + Банкротство IN PARALLEL
            egrul_inn_records = []
            logger.info(
                f"Stage 0: Starting identity confirmation. "
                f"INN='{check.inn}', name='{check.full_name}', "
                f"demo_mode={demo_mode}"
            )
            task.update('identity', 'ЕГРЮЛ + ЕФРСБ — параллельная проверка...', 2)

            def _stage0_egrul():
                """EGRUL lookup by INN — pure computation."""
                if not check.inn:
                    return []
                from app.services.phase3.business_registry import BusinessRegistrySearch
                searcher = BusinessRegistrySearch(timeout=25)
                logger.info(f"Stage 0: Calling search_by_inn('{check.inn}', candidate_name='{check.full_name}')")
                results = searcher.search_by_inn(check.inn, candidate_name=check.full_name)
                return [r.to_dict() for r in results] if results else []

            def _stage0_bankruptcy():
                """Bankruptcy lookup — pure computation."""
                from app.services.candidate.bankruptcy_service import BankruptcyService
                svc = BankruptcyService(timeout=25)
                dob_str = check.date_of_birth.strftime('%Y-%m-%d') if check.date_of_birth else None
                results = svc.search(check.full_name, inn=check.inn, dob=dob_str)
                return [r.to_dict() for r in results]

            stage0_pool = ThreadPoolExecutor(max_workers=2)
            try:
                egrul_future = stage0_pool.submit(_ctx(_stage0_egrul))
                bankr_future = stage0_pool.submit(_ctx(_stage0_bankruptcy))

                # Collect EGRUL results
                try:
                    egrul_inn_records = egrul_future.result(timeout=30)
                    if egrul_inn_records:
                        identity_data['egrul_status'] = 'registered'
                        identity_data['linked_companies'] = egrul_inn_records

                        first_record = egrul_inn_records[0]
                        egrul_name = first_record.get('person_name') or first_record.get('name', '')
                        if egrul_name and egrul_name != check.full_name:
                            identity_data['name_discrepancy'] = True
                            identity_data['egrul_name'] = egrul_name
                            logger.info(
                                f"Stage 0: Name discrepancy — input '{check.full_name}' "
                                f"vs EGRUL '{egrul_name}'"
                            )

                        task.add_message(
                            f'ЕГРЮЛ по ИНН: найдено {len(egrul_inn_records)} записей',
                            'success',
                        )
                        sources_with_results += 1
                    else:
                        identity_data['egrul_status'] = 'not_registered'
                        task.add_message('ЕГРЮЛ по ИНН: записей не найдено', 'info')
                    sources_checked += 1
                except Exception as e:
                    logger.warning(f"Stage 0 EGRUL INN lookup failed: {e}")
                    task.add_message('ЕГРЮЛ по ИНН: источник недоступен', 'warning')
                    sources_checked += 1

                # Collect Bankruptcy results
                try:
                    bankruptcy_records = bankr_future.result(timeout=30)
                    is_manual = (
                        bankruptcy_records
                        and len(bankruptcy_records) == 1
                        and bankruptcy_records[0].get('source') == 'manual'
                    )
                    if is_manual:
                        task.add_message('ЕФРСБ: требуется ручная проверка', 'warning')
                    elif bankruptcy_records:
                        task.add_message(
                            f'Банкротство: найдено {len(bankruptcy_records)} записей',
                            'success',
                        )
                        identity_data['bankruptcy_status'] = 'found'
                        sources_with_results += 1
                    else:
                        task.add_message('Банкротство: записей не найдено', 'info')
                        identity_data['bankruptcy_status'] = 'clean'
                    sources_checked += 1
                except Exception as e:
                    logger.warning(f"Stage 0 bankruptcy lookup failed: {e}")
                    task.add_message('ЕФРСБ: источник недоступен', 'warning')
                    sources_checked += 1
            finally:
                stage0_pool.shutdown(wait=False, cancel_futures=True)

            # Step 0.3 — Linked Companies Deep Dive (parallel lookups)
            business_network = []
            if egrul_inn_records:
                task.update('identity', 'Анализ бизнес-связей...', 5)
                try:
                    from app.services.phase3.business_registry import BusinessRegistrySearch

                    seen_inns = {check.inn}
                    company_inns = []
                    company_map = {}
                    for company in egrul_inn_records[:5]:
                        company_inn = company.get('inn', '')
                        if company_inn and company_inn not in seen_inns:
                            seen_inns.add(company_inn)
                            company_inns.append(company_inn)
                            company_map[company_inn] = company.get('name', '')

                    def _lookup_company(c_inn):
                        """Lookup co-founders for a single company."""
                        net_searcher = BusinessRegistrySearch(timeout=15)
                        co_results = net_searcher.search_by_inn(c_inn)
                        if not co_results:
                            return None
                        co_founders = []
                        for cr in co_results:
                            d = cr.to_dict()
                            co_name = d.get('person_name') or d.get('name', '')
                            co_role = d.get('role', '')
                            if co_name and co_name != check.full_name:
                                co_founders.append({'name': co_name, 'role': co_role})
                        if co_founders:
                            return {
                                'company_inn': c_inn,
                                'company_name': company_map.get(c_inn, ''),
                                'co_founders': co_founders[:10],
                            }
                        return None

                    if company_inns:
                        biz_pool = ThreadPoolExecutor(max_workers=min(5, len(company_inns)))
                        try:
                            futures = {biz_pool.submit(_ctx(_lookup_company), inn): inn for inn in company_inns}
                            for future in as_completed(futures, timeout=20):
                                try:
                                    result = future.result(timeout=5)
                                    if result:
                                        business_network.append(result)
                                except Exception as e:
                                    logger.warning(f"Stage 0 co-founder lookup for {futures[future]} failed: {e}")
                        except TimeoutError:
                            logger.warning("Stage 0 business network: some lookups timed out")
                        finally:
                            biz_pool.shutdown(wait=False, cancel_futures=True)
                except Exception as e:
                    logger.warning(f"Stage 0 business network analysis failed: {e}")

            identity_data['business_network'] = business_network

            # Step 0.4 — Identity Confirmation Report
            # Set confirmed_name: use EGRUL name if found and different
            confirmed = check.full_name
            if egrul_inn_records:
                check.identity_confirmed = True
            identity_data['confirmed_name'] = confirmed
            check.confirmed_name = confirmed
            check.identity_confirmation = identity_data
            check.bankruptcy_records = bankruptcy_records
            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                logger.error(f"DB commit failed (Stage 0 identity): {e}")

            # ── Address intelligence ──
            if check.registered_address:
                try:
                    from app.services.phase3.address_intelligence import search_by_address
                    addr_intel = search_by_address(
                        check.registered_address, check.inn or '',
                    )
                    if addr_intel.get('mass_registration'):
                        task.add_message(
                            f"Адрес массовой регистрации: "
                            f"{addr_intel.get('mass_registration_count', '?')} организаций",
                            'warning',
                        )
                    elif addr_intel.get('found'):
                        task.add_message(
                            f"По адресу найдено {len(addr_intel['connections'])} связанных лиц",
                            'info',
                        )
                    elif addr_intel.get('status') in ('error', 'blocked'):
                        # Don't let an unreadable FNS lookup pass as "no
                        # connections" — a mass-registration address is a flag.
                        task.add_message(
                            'Проверка адреса (связанные лица) не выполнена — '
                            'источник ФНС недоступен',
                            'warning',
                        )
                    _addr_status = addr_intel.get('status', '')
                    if _addr_status:
                        _ss = check.source_statuses or {}
                        _ss['address_intel'] = _addr_status
                        check.source_statuses = _ss
                        db.session.commit()
                except Exception as e:
                    db.session.rollback()
                    logger.debug(f"Address intelligence: {e}")

            task.update('identity', 'Личность подтверждена', 8)
            logger.info(
                f"Stage 0 complete: INN={check.inn}, confirmed={check.identity_confirmed}, "
                f"discrepancy={identity_data['name_discrepancy']}, "
                f"companies={len(egrul_inn_records)}, network={len(business_network)}"
            )
            _pause()

            # Use confirmed_name for all subsequent stages
            effective_name = check.confirmed_name or check.full_name
            effective_name_parts = effective_name.strip().split()
            effective_parts = {
                'last': effective_name_parts[0] if len(effective_name_parts) > 0 else '',
                'first': effective_name_parts[1] if len(effective_name_parts) > 1 else '',
                'patronymic': effective_name_parts[2] if len(effective_name_parts) > 2 else '',
            }

            # ══════════════════════════════════════════════
            # WAVE 1: STAGE 1 + STAGE 2 IN PARALLEL [8-27%]
            # ══════════════════════════════════════════════
            # Launch Stage 2 (sanctions + passport) in background
            # while Stage 1 (gov registries) runs on the main thread.
            stage2_executor = ThreadPoolExecutor(max_workers=1)
            stage2_future = stage2_executor.submit(
                _ctx(_run_stage2_computation),
                effective_name,
                check.inn,
                check.passport_series,
                check.passport_number,
            )
            logger.info("Wave 1: Stage 2 (security) launched in background")

            # ── STAGE 1: GOVERNMENT REGISTRIES [8-18%] ──
            logger.info(
                f"Stage 1: Starting government registries. "
                f"effective_name='{effective_name}', INN='{check.inn}', "
                f"demo_mode={demo_mode}, "
                f"VK_SERVICE_TOKEN={'set' if os.environ.get('VK_SERVICE_TOKEN') else 'NOT SET'}"
            )
            task.update('gov_registries', 'Проверка государственных реестров...', 10)

            biz_records = []
            court_records = []

            # Run business registry + court search in parallel
            def _search_business(full_name, inn):
                """Search ЕГРЮЛ by name, and by INN if provided."""
                from app.services.phase3.business_registry import BusinessRegistrySearch
                from app.utils.name_similarity import calculate_name_similarity
                records = []
                searcher = BusinessRegistrySearch(timeout=30)

                # By name (always)
                logger.info(f"Stage 1 ЕГРЮЛ: searching by name '{full_name}'")
                name_results = searcher.search_by_name(full_name)
                if name_results:
                    # Filter: only keep records where person_name closely matches
                    # the candidate's full name (similarity >= 0.7).
                    # This avoids false matches on surname-only or first+patronymic-only.
                    raw_records = [r.to_dict() for r in name_results]
                    filtered = []
                    for r in raw_records:
                        company = r.get('company_name', '')
                        # For ИП records, the person name is embedded in company_name
                        # e.g. "ИП Судин Артем Алексеевич"
                        person_name = company.replace('ИП ', '', 1).strip() if company.upper().startswith('ИП ') else ''
                        sim = calculate_name_similarity(full_name, person_name) if person_name else 0.0
                        if sim >= 0.7:
                            filtered.append(r)
                        else:
                            logger.debug(
                                f"  ЕГРЮЛ filtered out: '{company}' (similarity={sim:.2f})"
                            )
                    logger.info(
                        f"Stage 1 ЕГРЮЛ by name: {len(raw_records)} raw, "
                        f"{len(filtered)} after name filtering"
                    )
                    records = filtered
                    for r in records[:3]:
                        logger.info(
                            f"  ЕГРЮЛ: {r.get('company_name', '?')} | "
                            f"INN: {r.get('inn', 'N/A')} | "
                            f"Source: {r.get('source', 'N/A')}"
                        )
                else:
                    logger.info("Stage 1 ЕГРЮЛ by name: 0 records")

                # By INN (if provided) — more precise, deduplicate against name results
                if inn:
                    logger.info(f"Stage 1 ЕГРЮЛ: searching by INN '{inn}'")
                    inn_results = searcher.search_by_inn(inn)
                    if inn_results:
                        logger.info(f"Stage 1 ЕГРЮЛ by INN: {len(inn_results)} records")
                        existing_keys = {
                            (r.get('inn', '') or '') + (r.get('ogrn', '') or '')
                            for r in records
                        }
                        for r in inn_results:
                            d = r.to_dict()
                            key = (d.get('inn', '') or '') + (d.get('ogrn', '') or '')
                            if key not in existing_keys:
                                records.append(d)
                                existing_keys.add(key)
                    else:
                        logger.info("Stage 1 ЕГРЮЛ by INN: 0 records")

                return records

            def _search_courts(full_name, inn=''):
                """Search court records — sudact + судебныерешения + reputation.su
                + kad.arbitr.ru (all inside CourtRecordSearch).

                casebook.ru was dropped 2026-06-11: /search 404s, the API
                returns 401 (login wall) — dead code fully covered by kad.

                Returns (records, source_statuses). source_statuses maps source
                name → 'ok'/'empty'/'blocked'/'timeout'/'error'/... so the
                dossier can distinguish "no cases" from "source unreadable".
                """
                records = []
                statuses = {}
                logger.info(f"Stage 1 Courts: searching for '{full_name}'")
                try:
                    from app.services.phase3.court_search import CourtRecordSearch
                    searcher = CourtRecordSearch(timeout=30)
                    results = searcher.search_by_name(full_name, inn=inn)
                    statuses = dict(getattr(searcher, 'last_source_statuses', {}) or {})
                    if results:
                        records = [r.to_dict() for r in results]
                        logger.info(f"Stage 1 Courts: {len(records)} cases")
                        for r in records[:3]:
                            logger.info(
                                f"  Court: {r.get('case_number', '?')} | "
                                f"{r.get('court_name', 'N/A')[:40]} | "
                                f"Source: {r.get('source', 'N/A')}"
                            )
                    else:
                        logger.info(f"Stage 1 Courts: 0 cases (statuses: {statuses})")
                except Exception as e:
                    logger.warning(f"Court search failed: {e}")

                return records, statuses

            def _search_fssp(full_name, date_of_birth, region):
                """Search enforcement proceedings.

                Provider order: parser-api.com (proxied official ФССП, works
                from ANY IP) → checko.ru aggregator → CAPTCHA-walled official
                ФССП. Returns (records, status). Status distinguishes a genuine
                "no debts" read ('empty') from an unreadable source
                ('rate_limited'/'blocked'/...) so the dossier never shows a
                falsely-clean enforcement section. Enforcement is high-stakes
                (debts/alimony/tax arrears) — a false "Нет" is the worst case.
                """
                dob_str = date_of_birth.strftime('%Y-%m-%d') if date_of_birth else None

                # Primary: parser-api.com — official ФССП data, any IP, when keyed.
                try:
                    from app.services.candidate.fssp_service import search_fssp_via_parser_api
                    pa_records, pa_status = search_fssp_via_parser_api(full_name, dob_str)
                    if pa_status == 'ok':
                        return [r.to_dict() for r in pa_records], 'ok'
                    if pa_status == 'empty':
                        return [], 'empty'
                    # not_configured / rate_limited / error → fall through
                except Exception as e:
                    logger.warning(f"parser-api ФССП search failed: {e}")

                # Secondary: checko.ru (aggregator). Trust a clean read; only
                # fall through to the CAPTCHA-walled official ФССП when checko
                # was NOT readable.
                checko_status = 'error'
                try:
                    from app.services.phase3.checko_service import CheckoService
                    checko = CheckoService(timeout=30)
                    checko_records, checko_status = checko.search_enforcement(full_name)
                    if checko_status == 'ok':
                        return [r.to_fssp_dict() for r in checko_records], 'ok'
                    if checko_status == 'empty':
                        # checko read the person and found nothing — a real
                        # clean signal. Don't show a misleading CAPTCHA card.
                        return [], 'empty'
                except Exception as e:
                    logger.warning(f"Checko.ru enforcement search failed: {e}")

                # Fallback: official ФССП (CAPTCHA/geo-walled from many IPs)
                from app.services.candidate.fssp_service import FSSPService
                svc = FSSPService(timeout=30, max_pages=3)
                results, fssp_status = svc.search_with_status(full_name, dob_str, region)
                if fssp_status in ('ok', 'empty'):
                    return [r.to_dict() for r in results], fssp_status
                # FSSP blocked too. Surface checko's non-clean status if it was
                # more specific (rate_limited/blocked) so the report is precise.
                merged = checko_status if checko_status not in ('ok', 'empty', 'error') else 'blocked'
                return [r.to_dict() for r in results], merged

            task.update('gov_registries', 'ЕГРЮЛ + Суды + ФССП + Залоги — параллельный поиск...', 12)

            fssp_records = []
            fssp_status = 'error'
            pledge_records = []
            pledge_status = 'error'
            # Note: bankruptcy_records already populated by Stage 0

            def _search_pledges(full_name):
                """Search pledge registry (reestr-zalogov.ru).

                Returns (records, status). reestr-zalogov.ru is reCAPTCHA-walled,
                so status is usually 'blocked' — that must not read as "no
                pledged assets".
                """
                try:
                    from app.services.phase3.pledge_registry import PledgeRegistrySearch
                    svc = PledgeRegistrySearch(timeout=30)
                    results, status = svc.search_by_name(full_name)
                    return [r.to_dict() for r in results], status
                except Exception as e:
                    logger.warning(f"Pledge registry search failed: {e}")
                    return [], 'error'

            # Run fast sources (biz + FSSP + pledges) in parallel. Court search
            # (sudact.ru via Playwright) is slow and unpredictable, so it runs
            # SEQUENTIALLY after the pool finishes with no timeout — otherwise
            # the as_completed() timeout silently drops court_records.
            gov_pool = ThreadPoolExecutor(max_workers=3)
            try:
                future_biz = gov_pool.submit(_ctx(_search_business), effective_name, check.inn)
                future_fssp = gov_pool.submit(
                    _ctx(_search_fssp), effective_name, check.date_of_birth, check.region,
                )
                future_pledges = gov_pool.submit(_ctx(_search_pledges), effective_name)

                all_futures = [future_biz, future_fssp, future_pledges]
                completed_futures = set()

                def _process_future(future):
                    nonlocal biz_records, fssp_records, fssp_status, pledge_records
                    nonlocal pledge_status, sources_checked, sources_with_results
                    try:
                        if future is future_biz:
                            biz_records = future.result(timeout=60)
                            if egrul_inn_records:
                                existing_keys = {
                                    (r.get('inn', '') or '') + (r.get('ogrn', '') or '')
                                    for r in biz_records
                                }
                                for r in egrul_inn_records:
                                    key = (r.get('inn', '') or '') + (r.get('ogrn', '') or '')
                                    if key not in existing_keys:
                                        biz_records.append(r)
                                        existing_keys.add(key)
                            if biz_records:
                                task.add_message(f'ЕГРЮЛ: найдено {len(biz_records)} записей', 'success')
                                sources_with_results += 1
                            else:
                                task.add_message('ЕГРЮЛ: записи не найдены', 'info')
                            sources_checked += 1

                        elif future is future_fssp:
                            fssp_records, fssp_status = future.result(timeout=60)
                            if fssp_status == 'ok':
                                task.add_message(
                                    f'ФССП: найдено {len(fssp_records)} производств', 'success',
                                )
                                sources_with_results += 1
                            elif fssp_status == 'empty':
                                task.add_message('ФССП: производств не найдено', 'info')
                            elif fssp_status == 'rate_limited':
                                task.add_message(
                                    'ФССП: источник ограничил запросы (429) — проверка неполная',
                                    'warning',
                                )
                            else:
                                # blocked / error — CAPTCHA or unreachable
                                task.add_message(
                                    'ФССП: требуется ручная проверка (источник недоступен)',
                                    'warning',
                                )
                            sources_checked += 1

                        elif future is future_pledges:
                            pledge_records, pledge_status = future.result(timeout=60)
                            if pledge_records:
                                task.add_message(
                                    f'Залоговый реестр: найдено {len(pledge_records)} записей',
                                    'warning',
                                )
                                sources_with_results += 1
                            elif pledge_status in ('ok', 'empty'):
                                task.add_message('Залоговый реестр: записей не найдено', 'info')
                            else:
                                # reCAPTCHA / unreadable — not a clean result
                                task.add_message(
                                    'Залоговый реестр: reCAPTCHA — требуется ручная проверка',
                                    'warning',
                                )
                            sources_checked += 1

                    except Exception as e:
                        if future is future_biz:
                            logger.warning("ЕГРЮЛ search failed: %s", e)
                            task.add_message('ЕГРЮЛ: источник недоступен', 'warning')
                        elif future is future_fssp:
                            fssp_status = 'error'
                            logger.warning("ФССП search failed: %s", e)
                            task.add_message('ФССП: источник недоступен', 'warning')
                        elif future is future_pledges:
                            pledge_status = 'error'
                            logger.warning("Pledge registry failed: %s", e)
                            task.add_message('Залоговый реестр: недоступен', 'warning')
                        sources_checked += 1

                try:
                    for future in as_completed(all_futures, timeout=60):
                        completed_futures.add(future)
                        _process_future(future)
                except TimeoutError:
                    # Some futures didn't finish in 60s — mark timed-out ones
                    timed_out = [f for f in all_futures if f not in completed_futures]
                    logger.warning(
                        "Gov registries: %d/%d futures timed out",
                        len(timed_out), len(all_futures),
                    )
                    for future in timed_out:
                        future.cancel()
                        if future is future_biz:
                            task.add_message('ЕГРЮЛ: таймаут (60с)', 'warning')
                        elif future is future_fssp:
                            fssp_status = 'timeout'
                            task.add_message('ФССП: таймаут (60с)', 'warning')
                        elif future is future_pledges:
                            pledge_status = 'timeout'
                            task.add_message('Залоговый реестр: таймаут (60с)', 'warning')
                        sources_checked += 1
            finally:
                gov_pool.shutdown(wait=False, cancel_futures=True)

            # Court search runs in a single-worker pool with 120s outer timeout.
            # Individual Playwright ops have 30s each; 120s covers retries + reputation.su.
            # Outer timeout prevents an OS-level browser hang from stalling the pipeline.
            _court_pool = ThreadPoolExecutor(max_workers=1)
            _COURT_SOURCES = (
                'sudact.ru', 'судебныерешения.рф', 'reputation.su', 'kad.arbitr.ru',
            )
            _FAILURE_STATUSES = (
                'blocked', 'timeout', 'http_error', 'rate_limited', 'error',
            )
            try:
                _court_future = _court_pool.submit(
                    _ctx(_search_courts), effective_name, check.inn or '',
                )
                try:
                    _court_result = _court_future.result(timeout=150)
                    court_records, court_source_statuses = _court_result or ([], {})
                    court_records = court_records or []
                    court_source_statuses = court_source_statuses or {}
                    _failed_sources = [
                        s for s, st in court_source_statuses.items()
                        if st in _FAILURE_STATUSES
                    ]
                    if court_records:
                        msg = f'Суды: найдено {len(court_records)} дел'
                        if _failed_sources:
                            msg += f' (недоступны: {", ".join(_failed_sources)})'
                        task.add_message(msg, 'success')
                        sources_with_results += 1
                    elif _failed_sources:
                        # An unreadable source is NOT a clean record — say so.
                        task.add_message(
                            f'Суды: источники недоступны ({", ".join(_failed_sources)}) '
                            f'— проверка неполная',
                            'warning',
                        )
                    else:
                        task.add_message('Суды: дела не найдены', 'info')
                except TimeoutError:
                    logger.warning("Court search: outer 150s timeout — Playwright may be hung")
                    task.add_message('Суды: таймаут (150с) — пропущен', 'warning')
                    court_records = []
                    court_source_statuses = dict.fromkeys(_COURT_SOURCES, 'timeout')
                except Exception as e:
                    logger.warning("Court search failed: %s", e)
                    task.add_message('Суды: источник недоступен', 'warning')
                    court_records = []
                    court_source_statuses = dict.fromkeys(_COURT_SOURCES, 'error')
            finally:
                _court_pool.shutdown(wait=False, cancel_futures=True)
            sources_checked += 1

            # Demo fallback for Stage 1
            logger.info(
                f"Stage 1 results: biz={len(biz_records)}, courts={len(court_records)}, "
                f"fssp={len(fssp_records)}, pledges={len(pledge_records)}, demo_mode={_is_demo_mode()}"
            )
            if _is_demo_mode() and not biz_records and not court_records:
                logger.info("Stage 1: Using DEMO fallback (no real data + demo mode)")
                demo_biz, demo_courts, demo_fssp, demo_bankruptcy = _get_demo_gov_data(effective_name)
                biz_records = demo_biz
                court_records = demo_courts
                court_source_statuses = {}  # demo data — real statuses would mislead
                fssp_records = demo_fssp
                fssp_status = 'ok' if demo_fssp else 'empty'
                pledge_status = 'empty'
                if not bankruptcy_records:
                    bankruptcy_records = demo_bankruptcy
                    check.bankruptcy_records = bankruptcy_records
                task.add_message('Реестры: демо-данные (нет API)', 'info')
                sources_with_results += 2
                sources_checked += 3

            # Normalize court confidence: high/medium → VERIFIED/LIKELY/POSSIBLE/UNVERIFIED
            if court_records:
                court_records = _normalize_court_confidence(court_records, check.region)
                conf_counts = {}
                for r in court_records:
                    c = r.get('confidence', '?')
                    conf_counts[c] = conf_counts.get(c, 0) + 1
                logger.info(f"Stage 1 Court confidence: {conf_counts}")

            # AI: Summarize court cases
            try:
                from app.services.ai.claude_integration import summarize_court_cases
                court_records = summarize_court_cases(court_records)
            except Exception as e:
                logger.debug(f"AI court summary skipped: {e}")

            # INN-based filtering: remove false positives from EGRUL by-name results
            if check.inn and biz_records:
                try:
                    from app.services.phase3.business_registry import filter_business_records_by_inn
                    pre_count = len(biz_records)
                    biz_records = filter_business_records_by_inn(biz_records, check.inn)
                    if pre_count != len(biz_records):
                        logger.info(
                            f"Stage 1 INN filter: {pre_count} → {len(biz_records)} business records"
                        )
                except Exception as e:
                    logger.warning(f"INN filter failed (keeping all records): {e}")

            check.business_records = biz_records
            check.court_records = court_records
            check.court_source_statuses = court_source_statuses
            check.fssp_records = fssp_records
            check.fssp_status = fssp_status
            check.source_statuses = {'reestr-zalogov.ru': pledge_status}
            check.pledge_records = pledge_records
            # bankruptcy_records already set in Stage 0
            stage1_elapsed = time.time() - task.started_at.timestamp()
            task.update('gov_registries', 'Реестры проверены', 18)
            logger.info(f"Stage 1 completed in {stage1_elapsed:.1f}s")

            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                logger.error(f"DB commit failed (Stage 1 gov registries): {e}")

            # ── STAGE 2: COLLECT SECURITY RESULTS (ran in parallel) ──
            task.update('security', 'Получение результатов проверки безопасности...', 20)
            stage2_start = time.time()

            try:
                sanctions_results, passport_result = stage2_future.result(timeout=60)
            except Exception as e:
                logger.error(f"Stage 2 background computation failed: {e}")
                sanctions_results = []
                passport_result = None
            finally:
                stage2_executor.shutdown(wait=False)

            # Process sanctions results (on main thread for safe task.update)
            sanctions_checked = 0
            for sr in sanctions_results:
                d = sr.to_dict()
                if d['checked'] and d['found']:
                    task.add_message(f"{d['source_name']}: НАЙДЕН", 'error')
                    sources_with_results += 1
                elif d['checked'] and not d['found']:
                    task.add_message(f"{d['source_name']}: не найден", 'success')
                else:
                    task.add_message(
                        f"{d['source_name']}: не удалось проверить"
                        + (f" ({d['error']})" if d['error'] else ''),
                        'warning',
                    )
                sanctions_checked += 1

            sources_checked += sanctions_checked
            task.update('security', f'Санкции: проверено {sanctions_checked} источника', 24)

            sanctions_dicts = [sr.to_dict() for sr in sanctions_results]

            # Demo fallback for Stage 2
            if _is_demo_mode() and not any(d.get('checked') for d in sanctions_dicts):
                sanctions_dicts = _get_demo_sanctions()
                task.add_message('Санкции: демо-данные (нет API)', 'info')
                sources_checked += 4

            # Process passport result (from background computation)
            if passport_result:
                if passport_result.get('checked'):
                    if passport_result.get('valid') is True:
                        task.add_message('МВД паспорт: действителен', 'success')
                    elif passport_result.get('valid') is False:
                        task.add_message('МВД паспорт: НЕДЕЙСТВИТЕЛЕН', 'error')
                        all_red_flags.append({
                            'code': 'PASSPORT_INVALID',
                            'description': 'Паспорт числится недействительным в базе МВД',
                            'severity': 'high',
                            'category': 'identity',
                            'source': 'МВД ГУВМ',
                        })
                    else:
                        task.add_message(
                            f"МВД паспорт: {passport_result.get('status', 'не определён')}",
                            'warning',
                        )
                    sources_with_results += 1
                else:
                    error_msg = passport_result.get('error', 'неизвестная ошибка')
                    task.add_message(f'МВД паспорт: {error_msg}', 'warning')
                sources_checked += 1

            logger.info(f"Stage 2 completed in {time.time() - stage2_start:.1f}s (ran parallel with Stage 1)")

            # Store passport check result in sanctions_dicts for dossier display
            if passport_result:
                sanctions_dicts.append({
                    'source_name': 'МВД — проверка паспорта',
                    'checked': passport_result.get('checked', False),
                    'found': passport_result.get('valid') is False,  # found=True means INVALID
                    'match_details': passport_result.get('status'),
                    'error': passport_result.get('error'),
                    'url': 'https://www.gosuslugi.ru/621102/1',
                })

            check.sanctions_results = sanctions_dicts
            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                logger.error(f"DB commit failed (Stage 2 sanctions): {e}")
            _pause()

            # ══════════════════════════════════════════════
            # STAGE 3: SOCIAL MEDIA DISCOVERY [27-42%]
            # Social searches run in parallel (VK+TG+Phone)
            # ══════════════════════════════════════════════
            stage3_start = time.time()
            task.update('social', 'VK + Telegram + Телефон — параллельный поиск...', 29)

            social_profiles = []
            vk_screen_names = []

            # Capture values needed by workers (no DB/task access inside workers)
            _tg_birth_year = check.date_of_birth.year if check.date_of_birth else None
            _tg_first = effective_parts['first']
            _tg_last = effective_parts['last']
            _vk_first = effective_parts['first']
            _vk_last = effective_parts['last']
            _tg_city = check.region or ''
            _phone = check.phone

            # Parse DOB into components for VK API
            vk_birth_day = vk_birth_month = vk_birth_year = None
            vk_age_from = vk_age_to = None
            if check.date_of_birth:
                from datetime import date as _date
                vk_birth_day = check.date_of_birth.day
                vk_birth_month = check.date_of_birth.month
                vk_birth_year = check.date_of_birth.year
                today = _date.today()
                age = today.year - check.date_of_birth.year - (
                    (today.month, today.day) < (check.date_of_birth.month, check.date_of_birth.day)
                )
                vk_age_from = max(age - 3, 16)
                vk_age_to = age + 3

            def _vk_search_worker():
                """VK People Search — returns list of VKProfileResult."""
                from app.services.phase1.buratino_vk_search import buratino_vk_search
                profiles, _ = buratino_vk_search.search(
                    query=effective_name,
                    first_name=_vk_first,
                    last_name=_vk_last,
                    target_name=f"{_vk_first} {_vk_last}".strip() or effective_name,
                    city=check.region,
                    age_from=vk_age_from,
                    age_to=vk_age_to,
                    birth_day=vk_birth_day,
                    birth_month=vk_birth_month,
                    birth_year=vk_birth_year,
                )
                return profiles

            def _tg_search_worker():
                """Telegram discovery — Methods B+C (no VK screen_names needed)."""
                from app.services.phase1.telegram_discovery import TelegramDiscoveryService
                svc = TelegramDiscoveryService()
                try:
                    # Run without VK screen_names (Method A skipped for parallelism).
                    # Methods B (guessing) and C (Telethon) work independently.
                    return svc.discover(
                        first_name=_tg_first,
                        last_name=_tg_last,
                        vk_screen_names=[],
                        city=_tg_city,
                        birth_year=_tg_birth_year,
                    )
                finally:
                    svc.close()

            def _phone_tg_worker():
                """Phone → Telegram lookup."""
                if not _phone:
                    return None
                from app.services.phase1.telegram_discovery import TelegramDiscoveryService
                tg_svc = TelegramDiscoveryService()
                try:
                    return tg_svc.search_by_phone(_phone)
                finally:
                    tg_svc.close()

            # Run social searches in parallel with 45s shared timeout
            social_pool = ThreadPoolExecutor(max_workers=3)
            try:
                vk_future = social_pool.submit(_ctx(_vk_search_worker))
                tg_future = social_pool.submit(_ctx(_tg_search_worker))
                phone_future = social_pool.submit(_ctx(_phone_tg_worker))
                social_deadline = time.monotonic() + 45

                def _remaining_social_timeout() -> float:
                    return max(0.1, social_deadline - time.monotonic())

                # Collect VK results
                vk_profiles = []
                try:
                    vk_profiles = vk_future.result(timeout=_remaining_social_timeout())
                except Exception as e:
                    logger.warning(f"VK search timeout/error: {e}")

                # Collect TG results
                tg_results = []
                try:
                    tg_results = tg_future.result(timeout=_remaining_social_timeout())
                except Exception as e:
                    logger.warning(f"Telegram search timeout/error: {e}")

                # Collect Phone→TG results
                phone_results = None
                try:
                    phone_results = phone_future.result(timeout=_remaining_social_timeout())
                except Exception as e:
                    logger.warning(f"TG phone lookup timeout/error: {e}")
            finally:
                social_pool.shutdown(wait=False, cancel_futures=True)

            # --- Process VK results ---
            try:
                logger.info(
                    f"Stage 3 VK: got {len(vk_profiles)} profiles from search "
                    f"(city={check.region!r}, age={vk_age_from}-{vk_age_to})"
                )
                for _dbg_p in vk_profiles[:5]:
                    _dbg_d = _dbg_p.to_dict() if hasattr(_dbg_p, 'to_dict') else _dbg_p
                    logger.info(
                        f"  VK profile: id{_dbg_d.get('vk_id')}, "
                        f"{_dbg_d.get('full_name')!r}, city={_dbg_d.get('city')!r}, "
                        f"age={_dbg_d.get('age')}, sim={_dbg_d.get('name_similarity', 0):.0f}%"
                    )

                if vk_profiles:
                    for p in vk_profiles[:10]:
                        d = p.to_dict() if hasattr(p, 'to_dict') else p
                        sim = d.get('name_similarity', 0)

                        if sim >= 75:
                            confidence = 'высокая'
                        elif sim >= 50:
                            confidence = 'средняя'
                        else:
                            continue

                        dob_match = False
                        conf_score = round(sim / 100, 2)
                        vk_bdate = d.get('birth_date', '')
                        if vk_bdate and check.date_of_birth:
                            bdate_parts = vk_bdate.split('.')
                            if len(bdate_parts) == 3:
                                try:
                                    bd, bm, by = int(bdate_parts[0]), int(bdate_parts[1]), int(bdate_parts[2])
                                    if (bd == check.date_of_birth.day
                                            and bm == check.date_of_birth.month
                                            and by == check.date_of_birth.year):
                                        dob_match = True
                                        conf_score = min(0.98, max(conf_score, 0.95))
                                        confidence = 'высокая'
                                except (ValueError, IndexError) as e:
                                    logger.warning(f"Non-critical error parsing VK birth date: {e}")

                        social_profiles.append({
                            'platform': 'vk',
                            'platform_id': d.get('vk_id'),
                            'display_name': d.get('full_name', ''),
                            'username': d.get('screen_name', ''),
                            'url': d.get('profile_url', ''),
                            'avatar_url': d.get('photo_url'),
                            'photo_url': d.get('photo_url'),
                            'confidence': confidence,
                            'confidence_score': conf_score,
                            'dob_match': dob_match,
                            'source_method': 'VK People Search',
                            'city': d.get('city', ''),
                        })

                        sn = d.get('screen_name', '')
                        if sn and not (sn.startswith('id') and sn[2:].isdigit()):
                            vk_screen_names.append(sn)

                    vk_count = sum(1 for p in social_profiles if p['platform'] == 'vk')
                    task.add_message(f'VK: найдено {vk_count} профилей', 'success')
                    sources_with_results += 1
                else:
                    task.add_message('VK: профили не найдены', 'info')
                sources_checked += 1
            except Exception as e:
                logger.warning(f"VK result processing failed: {e}")
                task.add_message('VK: поиск недоступен', 'warning')
                sources_checked += 1

            # --- VK→TG cross-reference (Method A) — quick post-hoc check ---
            # Runs in a thread with a 30s hard timeout so it cannot stall the
            # main pipeline thread (N screen_names × ~10s HTTP each was blocking
            # indefinitely with no progress update).
            if vk_screen_names:
                def _do_vk_tg_xref():
                    from app.services.phase1.telegram_discovery import TelegramDiscoveryService
                    svc = TelegramDiscoveryService()
                    try:
                        return svc._method_a_vk_crossref(vk_screen_names, _tg_first, _tg_last)
                    finally:
                        svc.close()

                _xref_pool = ThreadPoolExecutor(max_workers=1)
                try:
                    _xref_future = _xref_pool.submit(_ctx(_do_vk_tg_xref))
                    try:
                        xref_results = _xref_future.result(timeout=30)
                        if xref_results:
                            tg_results = (tg_results or []) + xref_results
                    except Exception as e:
                        logger.debug(f"VK→TG cross-ref timeout/error: {e}")
                finally:
                    _xref_pool.shutdown(wait=False, cancel_futures=True)

            # --- Process Telegram results ---
            tg_count = 0
            try:
                if tg_results:
                    for p in tg_results[:10]:
                        conf = p.get('confidence', '')
                        if conf not in ('высокая', 'средняя'):
                            continue

                        display_name = f"{p.get('first_name', '')} {p.get('last_name', '')}".strip()
                        source_raw = p.get('source', '')

                        if 'VK' in source_raw:
                            source_method = 'VK → Telegram'
                        elif 'Шаблон' in source_raw:
                            source_method = 'Username guessing'
                        elif 'Telethon' in source_raw or p.get('source_method', ''):
                            source_method = 'Telethon'
                        else:
                            source_method = 'Telegram search'

                        confidence_score = 0.85 if conf == 'высокая' else 0.55

                        social_profiles.append({
                            'platform': 'telegram',
                            'display_name': display_name or p.get('username', ''),
                            'username': p.get('username', ''),
                            'url': p.get('url', ''),
                            'avatar_url': p.get('photo_url'),
                            'photo_url': p.get('photo_url'),
                            'confidence': conf,
                            'confidence_score': confidence_score,
                            'source_method': source_method,
                            'city': p.get('city', ''),
                        })
                        tg_count += 1

                if tg_count:
                    task.add_message(f'Telegram: найдено {tg_count} профилей', 'success')
                    sources_with_results += 1
                else:
                    task.add_message('Telegram: профили не найдены', 'info')
                sources_checked += 1
            except Exception as e:
                logger.warning(f"Telegram result processing failed: {e}")
                task.add_message('Telegram: поиск недоступен', 'warning')
                sources_checked += 1

            # --- Process Phone → Telegram results ---
            if _phone:
                try:
                    if phone_results:
                        existing_usernames = {
                            p.get('username', '').lower() for p in social_profiles if p.get('username')
                        }
                        for p in phone_results:
                            uname = (p.get('username') or '').lower()
                            dedup_key = uname or f"tg_id_{p.get('tg_id', '')}"
                            if dedup_key not in existing_usernames:
                                social_profiles.append({
                                    'platform': 'telegram',
                                    'display_name': f"{p.get('first_name', '')} {p.get('last_name', '')}".strip(),
                                    'username': p.get('username', ''),
                                    'url': p.get('url', ''),
                                    'confidence': 'высокая',
                                    'confidence_score': 0.99,
                                    'source_method': 'Phone lookup (Telethon)',
                                    'city': '',
                                })
                                existing_usernames.add(dedup_key)
                        task.add_message(
                            f'Telegram по телефону: найдено {len(phone_results)} профилей',
                            'success',
                        )
                        sources_with_results += 1
                    else:
                        task.add_message('Telegram по телефону: не найден', 'info')
                    sources_checked += 1
                except Exception as e:
                    logger.warning(f"TG phone lookup result processing failed: {e}")
                    task.add_message('Telegram по телефону: ошибка', 'warning')
                    sources_checked += 1

            task.update('social', f'Соцсети: найдено {len(social_profiles)} профилей', 42)
            check.social_media_profiles = social_profiles
            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                logger.error(f"DB commit failed (Stage 3 social profiles): {e}")
            logger.info(f"Stage 3 completed in {time.time() - stage3_start:.1f}s")
            _pause()

            # --- Precise mode: pause for profile confirmation ---
            if getattr(check, 'check_mode', 'quick') == 'precise' and social_profiles:
                check.status = 'awaiting_confirmation'
                check.paused_at_stage = 'awaiting_confirmation'
                try:
                    db.session.commit()
                except Exception as e:
                    db.session.rollback()
                    logger.error(f"DB commit failed (precise mode pause): {e}")
                task.update('social', 'Ожидание подтверждения профиля', 42)
                logger.info(f"Pipeline paused for profile confirmation (check {check_id})")

                max_wait = 1800  # 30 minutes
                waited = 0
                while check.status == 'awaiting_confirmation' and waited < max_wait:
                    if task.cancelled:
                        check.status = 'error'
                        try:
                            db.session.commit()
                        except Exception as e:
                            db.session.rollback()
                            logger.error(f"DB commit failed (cancel during precise wait): {e}")
                        return
                    time.sleep(2)
                    waited += 2
                    db.session.expire(check)
                    db.session.refresh(check)

                if check.status == 'awaiting_confirmation':
                    # Timeout — auto-resume with best match
                    logger.warning(f"Profile confirmation timeout after {max_wait}s, auto-resuming")
                    check.status = 'running'
                    check.paused_at_stage = None
                    try:
                        db.session.commit()
                    except Exception as e:
                        db.session.rollback()
                        logger.error(f"DB commit failed (precise mode timeout resume): {e}")

                # If user confirmed, check.confirmed_profiles is now populated
                # and check.status is back to 'running'
                if check.status == 'running':
                    check.paused_at_stage = None
                    try:
                        db.session.commit()
                    except Exception as e:
                        db.session.rollback()
                        logger.error(f"DB commit failed (precise mode confirmed resume): {e}")
                    task.update('social', 'Профиль подтверждён — продолжение', 42)

            # ══════════════════════════════════════════════
            # WAVE 3: STAGE 4 + STAGE 5 IN PARALLEL [42-72%]
            # Stage 4 — Contact Discovery (breach APIs, oracle)
            # Stage 5 — Deep Social Analysis (face, Snoop, graph)
            # Both read from check (loaded in memory) — safe for
            # concurrent reads. DB writes happen after both complete.
            # ══════════════════════════════════════════════
            wave3_start = time.time()
            task.update('contacts', 'Контакты + Соц. анализ — параллельно...', 44)

            # Build input contacts fallback (always preserved even on timeout/error)
            input_contacts = {'phones': [], 'emails': []}
            if check.phone:
                from app.utils.phone import normalize_phone as _norm_phone
                _np = _norm_phone(check.phone)
                if _np:
                    input_contacts['phones'].append({
                        'number': _np, 'source': 'input', 'confidence': 'высокая',
                        'profile_name': 'Форма ввода', 'raw_value': check.phone,
                        'confidence_score': 0.99, 'sources': ['input'],
                    })
            if check.email:
                input_contacts['emails'].append({
                    'email': check.email.lower().strip(), 'source': 'input',
                    'confidence': 'высокая', 'verified': False,
                    'profile_name': 'Форма ввода', 'services': [],
                    'confidence_score': 0.99, 'sources': ['input'],
                })

            # ── Launch Stage 4 + Stage 5 in parallel ──
            from app.services.candidate.contact_discovery import ContactDiscoveryService
            from app.services.candidate.social_analysis import run_social_analysis

            def _run_contact_discovery():
                """Worker; caller enforces timeout via stage4_future.result(timeout=60)."""
                discovery = ContactDiscoveryService()
                return discovery.discover(check)

            def _run_social_analysis():
                return run_social_analysis(check)

            wave3_pool = ThreadPoolExecutor(max_workers=2)
            stage4_future = wave3_pool.submit(_ctx(_run_contact_discovery))
            stage5_future = wave3_pool.submit(_ctx(_run_social_analysis))
            logger.info("Wave 3: Stage 4 (contacts) + Stage 5 (social) launched in parallel")

            # ── Collect Stage 4 results ──
            contacts = input_contacts
            try:
                contacts = stage4_future.result(timeout=60)
                phones = contacts.get('phones', [])
                emails = contacts.get('emails', [])
                if phones or emails:
                    task.add_message(
                        f'Контакты: найдено {len(phones)} тел., {len(emails)} email',
                        'success',
                    )
                    sources_with_results += 1
                else:
                    task.add_message('Контакты: дополнительных данных не найдено', 'info')
                sources_checked += 1
            except Exception as e:
                logger.warning(f"Contact discovery timeout/error: {e}")
                task.add_message('Контакты: таймаут/ошибка', 'warning')
                sources_checked += 1

            task.update('contacts', 'Контакты найдены', 55)

            # Demo fallback for Stage 4
            phones = contacts.get('phones', [])
            emails = contacts.get('emails', [])
            if _is_demo_mode() and not phones and not emails:
                contacts = _get_demo_contacts(check.full_name)
                task.add_message('Контакты: демо-данные (нет API)', 'info')
                sources_with_results += 1

            # ── Phone intelligence + INN breach (quick, run while waiting for Stage 5) ──
            if check.phone:
                try:
                    from app.services.phase2.phone_intelligence import run_phone_intelligence
                    phone_intel = run_phone_intelligence(check.phone) or {}
                    summary = phone_intel.get('summary', {})
                    if summary.get('total_sources_with_data', 0) > 0:
                        task.add_message(
                            f"Телефон: найдено в {summary['total_sources_with_data']} источниках"
                            + (f", {summary['breach_count']} утечек" if summary.get('breach_count') else ''),
                            'success',
                        )
                    for email in summary.get('emails_found', []):
                        contacts.setdefault('emails', []).append({
                            'email': email.lower(), 'source': 'phone_intelligence',
                            'confidence': 'средняя', 'verified': False,
                            'profile_name': 'Разведка по телефону',
                            'confidence_score': 0.55, 'sources': ['phone_intelligence'],
                        })
                except Exception as e:
                    logger.debug(f"Phone intelligence: {e}")

            if check.inn:
                try:
                    from app.services.phase2.inn_breach_search import search_inn_in_breaches
                    inn_breaches = search_inn_in_breaches(check.inn)
                    if inn_breaches.get('found'):
                        task.add_message('ИНН найден в базах утечек данных', 'warning')
                except Exception as e:
                    logger.debug(f"INN breach search: {e}")

            check.contact_discoveries = contacts
            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                logger.error(f"DB commit failed (Stage 4 contacts): {e}")
            logger.info(f"Stage 4 completed in {time.time() - wave3_start:.1f}s")

            # ── Collect Stage 5 results ──
            task.update('social_analysis', 'Ожидание соц. анализа...', 60)
            social_results = {}
            try:
                social_results = stage5_future.result(timeout=90)

                check.social_graph_data = social_results.get('social_graph', {})
                check.face_matches = social_results.get('face_matches', [])
                check.username_accounts = social_results.get('username_accounts', [])
                # Merge face-search status into the general source-status map so
                # the dossier can tell "searched, no match" from "couldn't search"
                # (no API key + Playwright unavailable). Merge, don't overwrite —
                # Stage 1 already stored the pledge-registry status here.
                _face_status = social_results.get('face_search_status', '')
                _uname_status = social_results.get('username_search_status', '')
                if _face_status or _uname_status:
                    _ss = check.source_statuses or {}
                    if _face_status:
                        _ss['search4faces'] = _face_status
                    # username-search trio (Snoop/Maigret/Sherlock): records
                    # whether we could search at all, so an uninstalled toolset
                    # doesn't render as "no accounts found".
                    if _uname_status:
                        _ss['username_search'] = _uname_status
                    check.source_statuses = _ss
                db.session.commit()

                face_count = len(social_results.get('face_matches', []))
                acct_count = len(social_results.get('username_accounts', []))
                if face_count or acct_count:
                    task.add_message(
                        f'Соц. анализ: {face_count} совпадений лиц, '
                        f'{acct_count} аккаунтов',
                        'success',
                    )
                    sources_with_results += 1
                sources_checked += 1
            except Exception as e:
                db.session.rollback()
                logger.error(f"Stage 5 social analysis timeout/error: {e}")
                task.add_message('Глубокий анализ соцсетей: ошибка (пропущен)', 'warning')
                sources_checked += 1

            wave3_pool.shutdown(wait=False, cancel_futures=True)

            # Stage 5e: Feedback loop — new accounts → supplementary contacts
            # (runs after BOTH Stage 4 and 5 complete)
            new_accounts = social_results.get('new_accounts_for_enrichment', [])
            if new_accounts:
                task.update('social_analysis', 'Дообогащение новых аккаунтов', 67)
                try:
                    contact_service = ContactDiscoveryService()
                    supplementary = contact_service.discover_supplementary(
                        new_accounts=new_accounts,
                        existing_contacts=check.contact_discoveries or {},
                    )
                    existing = check.contact_discoveries or {}
                    for key in ['phones', 'emails']:
                        existing_list = existing.get(key, [])
                        new_list = supplementary.get(key, [])
                        existing_values = set()
                        for item in existing_list:
                            val = item.get('number', item.get('address', item.get('email', '')))
                            if val:
                                existing_values.add(val)
                        for item in new_list:
                            val = item.get('number', item.get('address', item.get('email', '')))
                            if val and val not in existing_values:
                                existing_list.append(item)
                                existing_values.add(val)
                        existing[key] = existing_list
                    check.contact_discoveries = existing
                    db.session.commit()

                    supp_phones = len(supplementary.get('phones', []))
                    supp_emails = len(supplementary.get('emails', []))
                    if supp_phones or supp_emails:
                        task.add_message(
                            f'Дообогащение: +{supp_phones} тел., +{supp_emails} email',
                            'success',
                        )
                except Exception as e:
                    db.session.rollback()
                    logger.warning(f"Stage 5e feedback loop error: {e}")

            task.update('social_analysis', 'Социальный анализ завершён', 72)
            logger.info(
                f"Wave 3 (Stage 4+5) completed in {time.time() - wave3_start:.1f}s"
            )

            # ══════════════════════════════════════════════
            # STAGE 6: BEHAVIORAL INTELLIGENCE [72-83%]
            # ══════════════════════════════════════════════
            stage6_start = time.time()
            task.update('behavioral', 'Поведенческий анализ...', 73)

            try:
                from app.services.candidate.behavioral_analysis import run_behavioral_analysis

                def stage6_callback(stage, msg, pct):
                    task.update('behavioral', msg, pct or 73)

                # Hard timeout: 60s max for behavioral analysis
                _beh_pool = ThreadPoolExecutor(max_workers=1)
                _beh_future = _beh_pool.submit(
                    _ctx(run_behavioral_analysis), check, stage6_callback,
                )
                try:
                    behavioral_results = _beh_future.result(timeout=60)
                except Exception as _beh_err:
                    logger.warning(f"Behavioral analysis timeout/error: {_beh_err}")
                    behavioral_results = {}
                finally:
                    _beh_pool.shutdown(wait=False, cancel_futures=True)

                check.text_analysis = behavioral_results.get('text_analysis', {})
                check.geo_analysis = behavioral_results.get('geo_analysis', {})
                check.activity_timeline = behavioral_results.get('activity_timeline', [])
                check.group_analysis = behavioral_results.get('group_analysis', {})
                check.activity_patterns = behavioral_results.get('activity_patterns', {})
                # Record whether the VK wall was actually readable so an empty
                # behavioral section doesn't read as "no activity" when the wall
                # was private / the token failed (VK returns 200 + error body).
                _vk_wall_status = behavioral_results.get('vk_wall_status', '')
                if _vk_wall_status:
                    _ss = check.source_statuses or {}
                    _ss['vk_wall'] = _vk_wall_status
                    check.source_statuses = _ss
                db.session.commit()

                has_text = bool(behavioral_results.get('text_analysis'))
                has_geo = bool(behavioral_results.get('geo_analysis'))
                has_timeline = bool(behavioral_results.get('activity_timeline'))
                parts = []
                if has_text:
                    parts.append('текст')
                if has_geo:
                    parts.append('гео')
                if has_timeline:
                    parts.append('таймлайн')
                if parts:
                    task.add_message(
                        f'Поведенческий анализ: {", ".join(parts)}',
                        'success',
                    )
                    sources_with_results += 1
                sources_checked += 1

            except Exception as e:
                db.session.rollback()
                logger.error(f"Stage 6 behavioral analysis error: {e}", exc_info=True)
                task.add_message('Поведенческий анализ: ошибка (пропущен)', 'warning')
                sources_checked += 1

            # AI: Behavioral summary from VK posts
            try:
                from app.services.ai.claude_integration import generate_behavioral_summary
                ai_behavioral = generate_behavioral_summary(
                    check.text_analysis, effective_name,
                )
                if ai_behavioral:
                    check.behavioral_summary = ai_behavioral
                    db.session.commit()
                    task.add_message('AI: поведенческий профиль сгенерирован', 'success')
            except Exception as e:
                db.session.rollback()
                logger.debug(f"AI behavioral summary skipped: {e}")

            task.update('behavioral', 'Поведенческий анализ завершён', 82)
            logger.info(f"Stage 6 completed in {time.time() - stage6_start:.1f}s")

            # ── Geo Intelligence (aggregated from all stages) ──
            task.update('geo_intelligence', 'Сбор геоданных...', 82)
            try:
                from app.services.phase3.geo_intelligence import collect_geo_intelligence
                geo_intel = collect_geo_intelligence(check, is_demo=_is_demo_mode())
                check.geo_intelligence = geo_intel
                db.session.commit()
                n_loc = geo_intel.get('summary', {}).get('total_locations', 0)
                if n_loc:
                    task.add_message(f'Геоинтеллект: {n_loc} локаций', 'success')
                    sources_with_results += 1
                sources_checked += 1
            except Exception as e:
                db.session.rollback()
                logger.error(f"Geo intelligence collection error: {e}", exc_info=True)
                task.add_message('Геоинтеллект: ошибка (пропущен)', 'warning')
                sources_checked += 1

            task.update('behavioral', 'Поведенческий анализ завершён', 83)
            _pause()

            # ══════════════════════════════════════════════
            # STAGE 7: RISK SCORING [83-93%]
            # ══════════════════════════════════════════════
            task.update('risk', 'Анализ рисков...', 84)

            # 7a. Find connections with previous checks
            task.update('risk', 'Поиск связей с другими проверками...', 85)
            try:
                from app.services.candidate.behavioral_analysis import find_connected_checks
                connections = find_connected_checks(check)
                if connections:
                    check.connected_checks = connections
                    db.session.commit()
                    task.add_message(
                        f'Связи: найдено {len(connections)} связанных проверок',
                        'success',
                    )
            except Exception as e:
                db.session.rollback()
                logger.warning(f"Connected checks analysis failed: {e}")

            task.update('risk', 'Расчёт рисков...', 86)

            from app.services.candidate.risk_scorer import RiskScorer, calculate_risk_score
            scorer = RiskScorer()
            _, scorer_flags = scorer.analyze(check)

            # Merge inline flags from stages 1-4 with scorer output, dedup by code
            seen_codes = {f['code'] for f in scorer_flags if f.get('code')}
            merged_flags = list(scorer_flags)
            for flag in all_red_flags:
                code = flag.get('code', '')
                if not code or code not in seen_codes:
                    merged_flags.append(flag)
                    if code:
                        seen_codes.add(code)

            check.red_flags = merged_flags
            check.red_flag_count = len(merged_flags)
            check.sources_checked = sources_checked
            check.sources_with_results = sources_with_results

            # Build risk_breakdown by category
            severity_score = {'critical': 40, 'high': 20, 'medium': 10, 'low': 5}
            cat_flags = {}
            for f in merged_flags:
                cat = f.get('category', 'other')
                cat_flags.setdefault(cat, []).append(f)
            breakdown = {}
            for cat, flags_list in cat_flags.items():
                cat_score = sum(severity_score.get(f['severity'], 0) for f in flags_list)
                breakdown[cat] = {
                    'count': len(flags_list),
                    'score': cat_score,
                    'max_severity': flags_list[0]['severity'] if flags_list else 'clean',
                    'flags': [f['code'] for f in flags_list if f.get('code')],
                }
            check.risk_breakdown = breakdown

            # Numeric risk score 0-100 from weighted flags
            score_result = calculate_risk_score(merged_flags)
            check.risk_score = score_result['score']
            check.risk_score_numeric = float(score_result['score'])
            check.risk_level = score_result['level']
            if any(f.get('severity') == 'critical' for f in merged_flags):
                check.risk_level = 'critical'

            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                logger.error(f"DB commit failed (Stage 7 risk scoring): {e}")

            # AI: Risk narrative
            try:
                from app.services.ai.claude_integration import generate_risk_narrative
                ai_narrative = generate_risk_narrative(
                    check.risk_level, check.risk_score_numeric,
                    merged_flags, effective_name,
                )
                if ai_narrative:
                    check.risk_narrative = ai_narrative
                    db.session.commit()
                    task.add_message('AI: нарратив рисков сгенерирован', 'success')
            except Exception as e:
                db.session.rollback()
                logger.debug(f"AI risk narrative skipped: {e}")

            task.update('risk', f'Риск: {check.risk_level_display}', 93)
            task.add_message(
                f'Оценка риска: {check.risk_level_display} '
                f'({len(merged_flags)} факторов)',
                'success',
            )
            _pause()

            # ══════════════════════════════════════════════
            # STAGE 8: REPORT GENERATION [93-100%]
            # ══════════════════════════════════════════════
            task.update('report', 'Генерация отчёта...', 95)

            try:
                from app.services.candidate.report_builder import build_report
                report_data = build_report(check)
                check.report_generated = True
                db.session.commit()
                task.add_message('Отчёт сгенерирован', 'success')
            except Exception as e:
                db.session.rollback()
                logger.error(f"Stage 8 report generation error: {e}", exc_info=True)
                task.add_message('Генерация отчёта: ошибка (пропущен)', 'warning')

            # AI: Executive summary (after all stages)
            try:
                from app.services.ai.claude_integration import generate_executive_summary
                check_data = {
                    'full_name': effective_name,
                    'inn': check.inn,
                    'identity_confirmed': check.identity_confirmed,
                    'risk_level': check.risk_level,
                    'risk_score_numeric': check.risk_score_numeric,
                    'red_flag_count': check.red_flag_count,
                    'red_flags': check.red_flags,
                    'business_records': check.business_records,
                    'court_records': check.court_records,
                    'fssp_records': check.fssp_records,
                    'bankruptcy_records': check.bankruptcy_records,
                    'social_media_profiles': check.social_media_profiles,
                    'contact_discoveries': check.contact_discoveries,
                    'sanctions_results': check.sanctions_results,
                }
                ai_summary = generate_executive_summary(check_data)
                if ai_summary:
                    check.executive_summary = ai_summary
                    db.session.commit()
                    task.add_message('AI: сводка расследования сгенерирована', 'success')
                # Record one honest AI status so empty AI sections aren't read
                # as "AI ran, nothing notable". All four AI summaries share the
                # same client, so a single status is accurate.
                from app.services.ai.claude_integration import is_available as _ai_available
                if ai_summary or check.behavioral_summary or check.risk_narrative:
                    _ai_status = 'ok'
                elif not _ai_available():
                    _ai_status = 'unavailable'
                    task.add_message('AI-сводка недоступна (ключ не настроен)', 'warning')
                else:
                    _ai_status = 'error'
                _ss = check.source_statuses or {}
                _ss['ai_summary'] = _ai_status
                check.source_statuses = _ss
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                logger.debug(f"AI executive summary skipped: {e}")

            # Complete
            check.status = 'complete'
            check.completed_at = datetime.utcnow()
            elapsed = (datetime.now() - task.started_at).total_seconds()
            check.check_duration_seconds = elapsed

            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                logger.error(f"DB commit failed (pipeline completion): {e}")

            task.completed_at = datetime.now()
            task.is_complete = True
            task.update('complete', 'Проверка завершена', 100)
            task.add_message(
                f'Проверено {sources_checked} источников за {elapsed:.1f}с. '
                f'Уровень риска: {check.risk_level_display}',
                'success',
            )

        except Exception as e:
            logger.error(f"Candidate pipeline error: {e}", exc_info=True)
            task.error = str(e)
            task.is_complete = True
            task.add_message(f'Ошибка: {e}', 'error')
            check.status = 'error'
            task._sync_to_db()
            try:
                db.session.commit()
            except Exception as e2:
                db.session.rollback()
                logger.warning(f"Non-critical error during error-state commit: {e2}")

        finally:
            # Kill any Chrome processes this investigation left behind, and
            # release the SQLAlchemy connection for this thread back to the pool.
            # This runs whether the pipeline succeeded, errored, or was cancelled —
            # so investigation N+1 always starts with a clean slate.
            _kill_playwright_zombies(max_age_seconds=0)
            try:
                db.session.remove()
            except Exception:
                pass


def _pause():
    """Minimal delay between source requests to avoid rate limiting."""
    time.sleep(0.05)
