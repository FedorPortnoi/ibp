"""
Candidate Check Pipeline
========================
Orchestrates the 5-stage background check.
Wires existing IBP services and stubs out future ones.
"""

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

logger = logging.getLogger(__name__)

# In-memory task status (same pattern as Phase 2)
candidate_tasks = {}


class CandidateTaskStatus:
    """Progress tracker for a running candidate check."""

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

    def to_dict(self):
        if self.error:
            status = 'error'
        elif self.cancelled:
            status = 'cancelled'
        elif self.completed_at:
            status = 'complete'
        else:
            status = 'running'

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
            'is_complete': status in ('complete', 'error', 'cancelled'),
        }


def run_candidate_pipeline(app, task_id: str, check_id: str):
    """
    Background pipeline — runs inside a thread with app context.

    Stages:
    1. Government registries (ЕГРЮЛ, courts)
    2. Security checks (sanctions, wanted — stubs)
    3. Social media (VK, Telegram)
    4. Contact enrichment (if phone/email given)
    5. Risk analysis
    """
    task = candidate_tasks.get(task_id)
    if not task:
        return

    with app.app_context():
        from app import db
        from app.models.candidate_check import CandidateCheck

        check = CandidateCheck.query.get(check_id)
        if not check:
            task.error = 'Check record not found'
            return

        check.status = 'running'
        db.session.commit()

        sources_checked = 0
        sources_with_results = 0
        all_red_flags = []

        try:
            name_parts = check.name_parts

            # ══════════════════════════════════════════════
            # STAGE 1: GOVERNMENT REGISTRIES (~30%)
            # ══════════════════════════════════════════════
            task.update('gov_registries', 'Проверка государственных реестров...', 5)

            biz_records = []
            court_records = []

            # Run business registry + court search in parallel
            def _search_business(full_name, inn):
                """Search ЕГРЮЛ by name, and by INN if provided."""
                from app.services.phase3.business_registry import BusinessRegistrySearch
                records = []
                searcher = BusinessRegistrySearch(timeout=30)

                # By name (always)
                name_results = searcher.search_by_name(full_name)
                if name_results:
                    records = [r.to_dict() for r in name_results]

                # By INN (if provided) — more precise, deduplicate against name results
                if inn:
                    inn_results = searcher.search_by_inn(inn)
                    if inn_results:
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

                return records

            def _search_courts(full_name):
                """Search court records by name."""
                from app.services.phase3.court_search import CourtRecordSearch
                searcher = CourtRecordSearch(timeout=30)
                results = searcher.search_by_name(full_name)
                return [r.to_dict() for r in results] if results else []

            def _search_fssp(full_name, date_of_birth, region):
                """Search ФССП enforcement proceedings."""
                from app.services.candidate.fssp_service import FSSPService
                svc = FSSPService(timeout=30, max_pages=3)
                dob_str = date_of_birth.strftime('%Y-%m-%d') if date_of_birth else None
                results = svc.search(full_name, dob_str, region)
                return [r.to_dict() for r in results]

            task.update('gov_registries', 'ЕГРЮЛ + Суды + ФССП + ЕФРСБ — параллельный поиск...', 8)

            fssp_records = []
            bankruptcy_records = []

            def _search_bankruptcy(full_name, inn, date_of_birth):
                """Search ЕФРСБ bankruptcy records."""
                from app.services.candidate.bankruptcy_service import BankruptcyService
                svc = BankruptcyService(timeout=30)
                dob_str = date_of_birth.strftime('%Y-%m-%d') if date_of_birth else None
                results = svc.search(full_name, inn=inn, dob=dob_str)
                return [r.to_dict() for r in results]

            with ThreadPoolExecutor(max_workers=4) as executor:
                future_biz = executor.submit(_search_business, check.full_name, check.inn)
                future_courts = executor.submit(_search_courts, check.full_name)
                future_fssp = executor.submit(
                    _search_fssp, check.full_name, check.date_of_birth, check.region,
                )
                future_bankruptcy = executor.submit(
                    _search_bankruptcy, check.full_name, check.inn, check.date_of_birth,
                )

                for future in as_completed(
                    [future_biz, future_courts, future_fssp, future_bankruptcy],
                    timeout=120,
                ):
                    try:
                        if future is future_biz:
                            biz_records = future.result(timeout=60)
                            if biz_records:
                                task.add_message(f'ЕГРЮЛ: найдено {len(biz_records)} записей', 'success')
                                sources_with_results += 1
                            else:
                                task.add_message('ЕГРЮЛ: записи не найдены', 'info')
                            sources_checked += 1
                            if check.inn:
                                sources_checked += 1  # INN search counts as separate source

                        elif future is future_courts:
                            court_records = future.result(timeout=60)
                            if court_records:
                                task.add_message(f'Суды: найдено {len(court_records)} дел', 'success')
                                sources_with_results += 1
                            else:
                                task.add_message('Суды: дела не найдены', 'info')
                            sources_checked += 1

                        elif future is future_fssp:
                            fssp_records = future.result(timeout=90)
                            is_manual = (
                                fssp_records
                                and len(fssp_records) == 1
                                and fssp_records[0].get('source') == 'manual'
                            )
                            if is_manual:
                                task.add_message(
                                    'ФССП: требуется ручная проверка (CAPTCHA)',
                                    'warning',
                                )
                            elif fssp_records:
                                task.add_message(
                                    f'ФССП: найдено {len(fssp_records)} производств', 'success',
                                )
                                sources_with_results += 1

                            else:
                                task.add_message('ФССП: производств не найдено', 'info')
                            sources_checked += 1

                        elif future is future_bankruptcy:
                            bankruptcy_records = future.result(timeout=60)
                            is_manual = (
                                bankruptcy_records
                                and len(bankruptcy_records) == 1
                                and bankruptcy_records[0].get('source') == 'manual'
                            )
                            if is_manual:
                                task.add_message(
                                    'ЕФРСБ: требуется ручная проверка',
                                    'warning',
                                )
                            elif bankruptcy_records:
                                task.add_message(
                                    f'Банкротство: найдено {len(bankruptcy_records)} записей',
                                    'success',
                                )
                                sources_with_results += 1

                            else:
                                task.add_message(
                                    'Банкротство: записей не найдено', 'info',
                                )
                            sources_checked += 1

                    except Exception as e:
                        if future is future_biz:
                            logger.warning(f"ЕГРЮЛ search failed: {e}")
                            task.add_message('ЕГРЮЛ: источник недоступен', 'warning')
                            sources_checked += 1
                        elif future is future_courts:
                            logger.warning(f"Court search failed: {e}")
                            task.add_message('Суды: источник недоступен', 'warning')
                            sources_checked += 1
                        elif future is future_fssp:
                            logger.warning(f"ФССП search failed: {e}")
                            task.add_message('ФССП: источник недоступен', 'warning')
                            sources_checked += 1
                        else:
                            logger.warning(f"ЕФРСБ search failed: {e}")
                            task.add_message('ЕФРСБ: источник недоступен', 'warning')
                            sources_checked += 1

            check.business_records = biz_records
            check.court_records = court_records
            check.fssp_records = fssp_records
            check.bankruptcy_records = bankruptcy_records
            task.update('gov_registries', 'Реестры проверены', 25)
            _pause()

            db.session.commit()

            # ══════════════════════════════════════════════
            # STAGE 2: SECURITY CHECKS (~45%)
            # ══════════════════════════════════════════════
            task.update('security', 'Проверка санкционных списков...', 35)

            from app.services.candidate.sanctions_check import SanctionsService
            sanctions_svc = SanctionsService()
            sanctions_results = sanctions_svc.check_all(check.full_name, inn=check.inn)

            sanctions_checked = 0
            for sr in sanctions_results:
                d = sr.to_dict()
                if d['checked'] and d['found']:
                    task.add_message(
                        f"{d['source_name']}: НАЙДЕН",
                        'error',
                    )
                    sources_with_results += 1
                elif d['checked'] and not d['found']:
                    task.add_message(
                        f"{d['source_name']}: не найден",
                        'success',
                    )
                else:
                    task.add_message(
                        f"{d['source_name']}: не удалось проверить"
                        + (f" ({d['error']})" if d['error'] else ''),
                        'warning',
                    )
                sanctions_checked += 1

            sources_checked += sanctions_checked
            task.update(
                'security',
                f'Санкции: проверено {sanctions_checked} источника',
                45,
            )

            check.sanctions_results = [sr.to_dict() for sr in sanctions_results]
            db.session.commit()
            _pause()

            # ══════════════════════════════════════════════
            # STAGE 3: SOCIAL MEDIA (~70%)
            # ══════════════════════════════════════════════
            task.update('social', 'Поиск в социальных сетях...', 50)

            social_profiles = []
            vk_screen_names = []

            # 3.1 VK search — run first so Telegram can use screen_names
            task.update('social', 'VK — поиск профилей...', 52)
            try:
                from app.services.phase1.buratino_vk_search import buratino_vk_search

                # Calculate age range from DOB for filtering (±2 years)
                vk_age_from = vk_age_to = None
                if check.date_of_birth:
                    from datetime import date as _date
                    today = _date.today()
                    age = today.year - check.date_of_birth.year - (
                        (today.month, today.day) < (check.date_of_birth.month, check.date_of_birth.day)
                    )
                    vk_age_from = max(age - 2, 16)
                    vk_age_to = age + 2

                def _vk_search():
                    return buratino_vk_search.search(
                        query=check.full_name,
                        city=check.region,
                        age_from=vk_age_from,
                        age_to=vk_age_to,
                    )

                # Timeout: 60s max for VK search
                with ThreadPoolExecutor(max_workers=1) as vk_pool:
                    vk_future = vk_pool.submit(_vk_search)
                    try:
                        vk_profiles, _ = vk_future.result(timeout=60)
                    except Exception as e:
                        logger.warning(f"VK search timeout/error: {e}")
                        vk_profiles = []

                if vk_profiles:
                    for p in vk_profiles[:10]:
                        d = p.to_dict() if hasattr(p, 'to_dict') else p
                        sim = d.get('name_similarity', 0)

                        # Only high + medium confidence
                        if sim >= 75:
                            confidence = 'высокая'
                        elif sim >= 50:
                            confidence = 'средняя'
                        else:
                            continue

                        social_profiles.append({
                            'platform': 'vk',
                            'display_name': d.get('full_name', ''),
                            'username': d.get('screen_name', ''),
                            'url': d.get('profile_url', ''),
                            'avatar_url': d.get('photo_url'),
                            'photo_url': d.get('photo_url'),
                            'confidence': confidence,
                            'confidence_score': round(sim / 100, 2),
                            'source_method': 'VK People Search',
                            'city': d.get('city', ''),
                        })

                        # Collect screen_names for Telegram cross-ref (Method A)
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
                logger.warning(f"VK search failed: {e}")
                task.add_message('VK: поиск недоступен', 'warning')
                sources_checked += 1
            _pause()

            # 3.2 Telegram search — uses VK screen_names for cross-ref
            task.update('social', 'Telegram — поиск профилей...', 62)
            try:
                from app.services.phase1.telegram_discovery import TelegramDiscoveryService

                def _tg_search():
                    svc = TelegramDiscoveryService()
                    try:
                        return svc.discover(
                            first_name=name_parts['first'],
                            last_name=name_parts['last'],
                            vk_screen_names=vk_screen_names,
                            city=check.region or '',
                        )
                    finally:
                        svc.close()

                # Timeout: 60s max for Telegram search
                with ThreadPoolExecutor(max_workers=1) as tg_pool:
                    tg_future = tg_pool.submit(_tg_search)
                    try:
                        tg_results = tg_future.result(timeout=60)
                    except Exception as e:
                        logger.warning(f"Telegram search timeout/error: {e}")
                        tg_results = []

                tg_count = 0
                if tg_results:
                    for p in tg_results[:10]:
                        conf = p.get('confidence', '')
                        # Only high + medium confidence
                        if conf not in ('высокая', 'средняя'):
                            continue

                        display_name = f"{p.get('first_name', '')} {p.get('last_name', '')}".strip()
                        source_raw = p.get('source', '')

                        # Derive source_method from source description
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
                logger.warning(f"Telegram search failed: {e}")
                task.add_message('Telegram: поиск недоступен', 'warning')
                sources_checked += 1

            task.update('social', f'Соцсети: найдено {len(social_profiles)} профилей', 70)
            check.social_media_profiles = social_profiles
            db.session.commit()
            _pause()

            # ══════════════════════════════════════════════
            # STAGE 4: CONTACT ENRICHMENT (~85%)
            # ══════════════════════════════════════════════
            contacts = {'phones': [], 'emails': []}
            if check.phone or check.email:
                task.update('contacts', 'Обогащение контактных данных...', 75)

                if check.phone:
                    contacts['phones'].append({
                        'number': check.phone,
                        'source': 'input',
                        'verified': False,
                    })
                    task.add_message(f'Телефон {check.phone}: добавлен из формы', 'info')

                if check.email:
                    contacts['emails'].append({
                        'address': check.email,
                        'source': 'input',
                        'verified': False,
                    })
                    task.add_message(f'Email {check.email}: добавлен из формы', 'info')

                sources_checked += 1
            else:
                task.update('contacts', 'Контакты не указаны, пропуск...', 80)

            check.contact_discoveries = contacts
            db.session.commit()

            # ══════════════════════════════════════════════
            # STAGE 5: RISK ANALYSIS (~100%)
            # ══════════════════════════════════════════════
            task.update('risk', 'Анализ рисков...', 90)

            from app.services.candidate.risk_scorer import RiskScorer
            scorer = RiskScorer()
            risk_level, scorer_flags = scorer.analyze(check)

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
            check.risk_level = risk_level
            check.sources_checked = sources_checked
            check.sources_with_results = sources_with_results

            # Complete
            check.status = 'complete'
            check.completed_at = datetime.utcnow()
            elapsed = (datetime.now() - task.started_at).total_seconds()
            check.check_duration_seconds = elapsed

            db.session.commit()

            task.completed_at = datetime.now()
            task.update('complete', 'Проверка завершена', 100)
            task.add_message(
                f'Проверено {sources_checked} источников за {elapsed:.1f}с. '
                f'Уровень риска: {check.risk_level_display}',
                'success',
            )

        except Exception as e:
            logger.error(f"Candidate pipeline error: {e}", exc_info=True)
            task.error = str(e)
            task.add_message(f'Ошибка: {e}', 'error')
            check.status = 'error'
            db.session.commit()


def _pause():
    """Polite delay between source requests."""
    time.sleep(1)
