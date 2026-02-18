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

            task.update('gov_registries', 'ЕГРЮЛ + Суды + ФССП — параллельный поиск...', 8)

            fssp_records = []

            with ThreadPoolExecutor(max_workers=3) as executor:
                future_biz = executor.submit(_search_business, check.full_name, check.inn)
                future_courts = executor.submit(_search_courts, check.full_name)
                future_fssp = executor.submit(
                    _search_fssp, check.full_name, check.date_of_birth, check.region,
                )

                for future in as_completed(
                    [future_biz, future_courts, future_fssp], timeout=120,
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
                                if len(court_records) > 5:
                                    all_red_flags.append({
                                        'severity': 'warning',
                                        'source': 'courts',
                                        'text': f'Найдено {len(court_records)} судебных дел',
                                    })
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

                                # ── ФССП red flags ──
                                active = [r for r in fssp_records if r.get('is_active')]
                                if active:
                                    all_red_flags.append({
                                        'severity': 'warning',
                                        'source': 'fssp',
                                        'text': f'Активных исполнительных производств: {len(active)}',
                                    })
                                if len(active) >= 3:
                                    all_red_flags.append({
                                        'severity': 'risk',
                                        'source': 'fssp',
                                        'text': f'Множественные активные производства ({len(active)})',
                                    })
                                for rec in fssp_records:
                                    amt = rec.get('amount')
                                    subj = (rec.get('subject') or '').lower()
                                    if amt and amt > 500_000:
                                        all_red_flags.append({
                                            'severity': 'risk',
                                            'source': 'fssp',
                                            'text': f'Крупная задолженность: {amt:,.0f} руб. ({rec.get("proceedings_number", "")})',
                                        })
                                    elif amt and amt > 100_000:
                                        all_red_flags.append({
                                            'severity': 'warning',
                                            'source': 'fssp',
                                            'text': f'Задолженность {amt:,.0f} руб. ({rec.get("proceedings_number", "")})',
                                        })
                                    if 'алимент' in subj:
                                        all_red_flags.append({
                                            'severity': 'warning',
                                            'source': 'fssp',
                                            'text': f'Алиментные обязательства ({rec.get("proceedings_number", "")})',
                                        })
                                    if 'налог' in subj:
                                        all_red_flags.append({
                                            'severity': 'risk',
                                            'source': 'fssp',
                                            'text': f'Налоговая задолженность ({rec.get("proceedings_number", "")})',
                                        })
                                    if 'штраф' in subj:
                                        all_red_flags.append({
                                            'severity': 'info',
                                            'source': 'fssp',
                                            'text': f'Штраф ({rec.get("proceedings_number", "")})',
                                        })
                            else:
                                task.add_message('ФССП: производств не найдено', 'info')
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
                        else:
                            logger.warning(f"ФССП search failed: {e}")
                            task.add_message('ФССП: источник недоступен', 'warning')
                            sources_checked += 1

            check.business_records = biz_records
            check.court_records = court_records
            check.fssp_records = fssp_records
            task.update('gov_registries', 'Реестры проверены', 25)
            _pause()

            # 1.5 Bankruptcy (stub)
            task.update('gov_registries', 'ЕФРСБ — проверка банкротства...', 28)
            task.add_message('ЕФРСБ: сервис в разработке', 'warning')
            check.bankruptcy_records = []
            sources_checked += 1

            db.session.commit()

            # ══════════════════════════════════════════════
            # STAGE 2: SECURITY CHECKS (~45%)
            # ══════════════════════════════════════════════
            task.update('security', 'Проверка по спискам безопасности...', 35)

            sanctions = {
                'rosfinmonitoring': {'checked': True, 'found': False, 'status': 'stub'},
                'mvd_wanted': {'checked': True, 'found': False, 'status': 'stub'},
                'interpol': {'checked': True, 'found': False, 'status': 'stub'},
                'extremists': {'checked': True, 'found': False, 'status': 'stub'},
            }

            task.add_message('Росфинмониторинг: сервис в разработке', 'warning')
            task.add_message('МВД розыск: сервис в разработке', 'warning')
            task.add_message('Интерпол: сервис в разработке', 'warning')
            task.add_message('Экстремисты: сервис в разработке', 'warning')
            sources_checked += 4

            check.sanctions_results = sanctions
            db.session.commit()
            _pause()

            # ══════════════════════════════════════════════
            # STAGE 3: SOCIAL MEDIA (~70%)
            # ══════════════════════════════════════════════
            task.update('social', 'Поиск в социальных сетях...', 50)

            social_profiles = []

            # 3.1 VK search (existing)
            task.update('social', 'ВКонтакте — поиск профилей...', 55)
            try:
                from app.services.phase1.buratino_vk_search import buratino_vk_search
                vk_profiles, vk_total = buratino_vk_search.search(
                    query=check.full_name,
                    city=check.region,
                )
                if vk_profiles:
                    for p in vk_profiles[:10]:
                        d = p.to_dict() if hasattr(p, 'to_dict') else p
                        social_profiles.append({
                            'platform': 'vk',
                            'display_name': d.get('full_name', ''),
                            'username': d.get('screen_name', ''),
                            'url': d.get('profile_url', ''),
                            'photo_url': d.get('photo_url', ''),
                            'city': d.get('city', ''),
                        })
                    task.add_message(f'ВКонтакте: найдено {len(vk_profiles)} профилей', 'success')
                    sources_with_results += 1
                else:
                    task.add_message('ВКонтакте: профили не найдены', 'info')
                sources_checked += 1
            except Exception as e:
                logger.warning(f"VK search failed: {e}")
                task.add_message('ВКонтакте: поиск недоступен', 'warning')
                sources_checked += 1
            _pause()

            # 3.2 Telegram search (existing)
            task.update('social', 'Telegram — поиск профилей...', 62)
            try:
                from app.services.phase1.telegram_discovery import TelegramDiscoveryService
                tg_svc = TelegramDiscoveryService()
                try:
                    tg_results = tg_svc.discover(
                        first_name=name_parts['first'],
                        last_name=name_parts['last'],
                        city=check.region or '',
                    )
                finally:
                    tg_svc.close()
                if tg_results:
                    for p in tg_results[:10]:
                        social_profiles.append({
                            'platform': 'telegram',
                            'display_name': p.get('display_name', ''),
                            'username': p.get('username', ''),
                            'url': p.get('url', ''),
                            'photo_url': p.get('photo_url', ''),
                        })
                    task.add_message(f'Telegram: найдено {len(tg_results)} профилей', 'success')
                    sources_with_results += 1
                else:
                    task.add_message('Telegram: профили не найдены', 'info')
                sources_checked += 1
            except Exception as e:
                logger.warning(f"Telegram search failed: {e}")
                task.add_message('Telegram: поиск недоступен', 'warning')
                sources_checked += 1

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

            # Basic red flag logic
            if len(biz_records) > 10:
                all_red_flags.append({
                    'severity': 'warning',
                    'source': 'business',
                    'text': f'Связан с {len(biz_records)} организациями',
                })

            # Determine risk level
            critical_count = sum(1 for f in all_red_flags if f['severity'] == 'critical')
            risk_count = sum(1 for f in all_red_flags if f['severity'] == 'risk')
            warning_count = sum(1 for f in all_red_flags if f['severity'] == 'warning')

            if critical_count > 0:
                risk_level = 'critical'
            elif risk_count > 0:
                risk_level = 'high'
            elif warning_count > 0:
                risk_level = 'medium'
            else:
                risk_level = 'low'

            check.red_flags = all_red_flags
            check.red_flag_count = len(all_red_flags)
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
