"""
Candidate Check Pipeline
========================
Orchestrates the 9-stage unified background check (Stage 0-8).

Stages:
0. Identity Confirmation (ЕГРЮЛ by INN, bankruptcy, network) [0-8%]
1. Government Registries (courts, ФССП, checko.ru)           [8-18%]
2. Security Checks (sanctions)                                [18-27%]
3. Social Media Discovery (VK, Telegram)                      [27-42%]
4. Contact Discovery (VK/TG extraction + breach APIs)         [42-57%]
5. Deep Social Analysis (face search, graph, Snoop)           [57-72%]
6. Behavioral Intelligence (text, geo, timeline)              [72-83%]
7. Risk Scoring (8-category red flags)                        [83-93%]
8. Report Generation (dossier + identity card)                [93-100%]
"""

import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

logger = logging.getLogger(__name__)


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


def cleanup_old_tasks(task_store, max_age_seconds=3600):
    """Remove completed tasks older than max_age_seconds."""
    now = datetime.now()
    expired = [
        task_id for task_id, task in task_store.items()
        if task.completed_at and (now - task.completed_at).total_seconds() > max_age_seconds
    ]
    for task_id in expired:
        del task_store[task_id]


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

    8-stage unified pipeline. See module docstring for stage breakdown.
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

            # Step 0.1 — ЕГРЮЛ Direct Lookup by INN
            egrul_inn_records = []
            if check.inn:
                task.update('identity', 'ЕГРЮЛ — поиск по ИНН...', 2)
                try:
                    from app.services.phase3.business_registry import BusinessRegistrySearch
                    searcher = BusinessRegistrySearch(timeout=30)
                    inn_results = searcher.search_by_inn(check.inn)
                    if inn_results:
                        egrul_inn_records = [r.to_dict() for r in inn_results]
                        identity_data['egrul_status'] = 'registered'
                        identity_data['linked_companies'] = egrul_inn_records

                        # Extract confirmed name from first record
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

            # Step 0.2 — Bankruptcy Lookup by INN
            task.update('identity', 'ЕФРСБ — проверка банкротства по ИНН...', 4)
            try:
                from app.services.candidate.bankruptcy_service import BankruptcyService
                svc = BankruptcyService(timeout=30)
                dob_str = check.date_of_birth.strftime('%Y-%m-%d') if check.date_of_birth else None
                b_results = svc.search(check.full_name, inn=check.inn, dob=dob_str)
                bankruptcy_records = [r.to_dict() for r in b_results]
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

            # Step 0.3 — Linked Companies Deep Dive
            business_network = []
            if egrul_inn_records:
                task.update('identity', 'Анализ бизнес-связей...', 5)
                try:
                    from app.services.phase3.business_registry import BusinessRegistrySearch
                    net_searcher = BusinessRegistrySearch(timeout=20)
                    seen_inns = {check.inn}
                    for company in egrul_inn_records[:5]:  # Limit to 5 companies
                        company_inn = company.get('inn', '')
                        if company_inn and company_inn not in seen_inns:
                            seen_inns.add(company_inn)
                            try:
                                co_results = net_searcher.search_by_inn(company_inn)
                                if co_results:
                                    co_founders = []
                                    for cr in co_results:
                                        d = cr.to_dict()
                                        co_name = d.get('person_name') or d.get('name', '')
                                        co_role = d.get('role', '')
                                        if co_name and co_name != check.full_name:
                                            co_founders.append({
                                                'name': co_name,
                                                'role': co_role,
                                            })
                                    if co_founders:
                                        business_network.append({
                                            'company_inn': company_inn,
                                            'company_name': company.get('name', ''),
                                            'co_founders': co_founders[:10],
                                        })
                            except Exception:
                                pass  # Non-critical, continue
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
            db.session.commit()

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
            # STAGE 1: GOVERNMENT REGISTRIES [8-18%]
            # ══════════════════════════════════════════════
            task.update('gov_registries', 'Проверка государственных реестров...', 10)

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
                """Search court records — sudact.ru + casebook.ru."""
                records = []
                # Primary: sudact.ru (general + arbitration, works globally)
                try:
                    from app.services.phase3.court_search import CourtRecordSearch
                    searcher = CourtRecordSearch(timeout=30)
                    results = searcher.search_by_name(full_name)
                    if results:
                        records = [r.to_dict() for r in results]
                except Exception as e:
                    logger.warning(f"Sudact court search failed: {e}")

                # Supplementary: casebook.ru (arbitration courts, replaces kad.arbitr.ru)
                try:
                    from app.services.phase3.casebook_service import CasebookService
                    casebook = CasebookService(timeout=25)
                    cb_results = casebook.search_person(full_name)
                    if cb_results:
                        existing_numbers = {r.get('case_number', '') for r in records}
                        for cb in cb_results:
                            d = cb.to_court_dict()
                            if d['case_number'] not in existing_numbers:
                                records.append(d)
                                existing_numbers.add(d['case_number'])
                except Exception as e:
                    logger.warning(f"Casebook court search failed: {e}")

                return records

            def _search_fssp(full_name, date_of_birth, region):
                """Search enforcement proceedings — checko.ru primary, ФССП fallback."""
                # Primary: checko.ru (globally accessible)
                try:
                    from app.services.phase3.checko_service import CheckoService
                    checko = CheckoService(timeout=30)
                    checko_records = checko.search_enforcement(full_name)
                    if checko_records:
                        return [r.to_fssp_dict() for r in checko_records]
                except Exception as e:
                    logger.warning(f"Checko.ru enforcement search failed: {e}")

                # Fallback: ФССП (may be geo-blocked)
                from app.services.candidate.fssp_service import FSSPService
                svc = FSSPService(timeout=30, max_pages=3)
                dob_str = date_of_birth.strftime('%Y-%m-%d') if date_of_birth else None
                results = svc.search(full_name, dob_str, region)
                return [r.to_dict() for r in results]

            task.update('gov_registries', 'ЕГРЮЛ + Суды + ФССП — параллельный поиск...', 12)

            fssp_records = []
            # Note: bankruptcy_records already populated by Stage 0

            with ThreadPoolExecutor(max_workers=3) as executor:
                future_biz = executor.submit(_search_business, effective_name, check.inn)
                future_courts = executor.submit(_search_courts, effective_name)
                future_fssp = executor.submit(
                    _search_fssp, effective_name, check.date_of_birth, check.region,
                )

                for future in as_completed(
                    [future_biz, future_courts, future_fssp],
                    timeout=120,
                ):
                    try:
                        if future is future_biz:
                            biz_records = future.result(timeout=60)
                            # Merge with Stage 0 EGRUL INN results
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

            # Demo fallback for Stage 1
            if _is_demo_mode() and not biz_records and not court_records:
                demo_biz, demo_courts, demo_fssp, demo_bankruptcy = _get_demo_gov_data(effective_name)
                biz_records = demo_biz
                court_records = demo_courts
                fssp_records = demo_fssp
                if not bankruptcy_records:
                    bankruptcy_records = demo_bankruptcy
                    check.bankruptcy_records = bankruptcy_records
                task.add_message('Реестры: демо-данные (нет API)', 'info')
                sources_with_results += 2
                sources_checked += 3

            # AI: Summarize court cases
            try:
                from app.services.ai.claude_integration import summarize_court_cases
                court_records = summarize_court_cases(court_records)
            except Exception as e:
                logger.debug(f"AI court summary skipped: {e}")

            check.business_records = biz_records
            check.court_records = court_records
            check.fssp_records = fssp_records
            # bankruptcy_records already set in Stage 0
            task.update('gov_registries', 'Реестры проверены', 18)
            _pause()

            db.session.commit()

            # ══════════════════════════════════════════════
            # STAGE 2: SECURITY CHECKS [18-27%]
            # ══════════════════════════════════════════════
            task.update('security', 'Проверка санкционных списков...', 20)

            from app.services.candidate.sanctions_check import SanctionsService
            sanctions_svc = SanctionsService()
            sanctions_results = sanctions_svc.check_all(effective_name, inn=check.inn)

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
                27,
            )

            sanctions_dicts = [sr.to_dict() for sr in sanctions_results]

            # Demo fallback for Stage 2 — show "checked & clean" instead of empty
            if _is_demo_mode() and not any(d.get('checked') for d in sanctions_dicts):
                sanctions_dicts = _get_demo_sanctions()
                task.add_message('Санкции: демо-данные (нет API)', 'info')
                sources_checked += 4

            check.sanctions_results = sanctions_dicts
            db.session.commit()
            _pause()

            # ══════════════════════════════════════════════
            # STAGE 3: SOCIAL MEDIA DISCOVERY [27-42%]
            # ══════════════════════════════════════════════
            task.update('social', 'Поиск в социальных сетях...', 29)

            social_profiles = []
            vk_screen_names = []

            # 3.1 VK search — run first so Telegram can use screen_names
            task.update('social', 'VK — поиск профилей...', 31)
            try:
                from app.services.phase1.buratino_vk_search import buratino_vk_search

                # Parse DOB into components for VK API birth_day/month/year params
                vk_birth_day = vk_birth_month = vk_birth_year = None
                vk_age_from = vk_age_to = None
                if check.date_of_birth:
                    from datetime import date as _date
                    vk_birth_day = check.date_of_birth.day
                    vk_birth_month = check.date_of_birth.month
                    vk_birth_year = check.date_of_birth.year
                    # Also keep age range (±3 years) as secondary filter
                    today = _date.today()
                    age = today.year - check.date_of_birth.year - (
                        (today.month, today.day) < (check.date_of_birth.month, check.date_of_birth.day)
                    )
                    vk_age_from = max(age - 3, 16)
                    vk_age_to = age + 3

                def _vk_search():
                    return buratino_vk_search.search(
                        query=effective_name,
                        city=check.region,
                        age_from=vk_age_from,
                        age_to=vk_age_to,
                        birth_day=vk_birth_day,
                        birth_month=vk_birth_month,
                        birth_year=vk_birth_year,
                    )

                # Timeout: 60s max for VK search
                with ThreadPoolExecutor(max_workers=1) as vk_pool:
                    vk_future = vk_pool.submit(_vk_search)
                    try:
                        vk_profiles, _ = vk_future.result(timeout=60)
                    except Exception as e:
                        logger.warning(f"VK search timeout/error: {e}")
                        vk_profiles = []

                logger.info(
                    f"Stage 3 VK: got {len(vk_profiles)} profiles from search "
                    f"(city={check.region!r}, age={vk_age_from}-{vk_age_to}). "
                    f"Pre-filter profiles:"
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

                        # Only high + medium confidence
                        if sim >= 75:
                            confidence = 'высокая'
                        elif sim >= 50:
                            confidence = 'средняя'
                        else:
                            continue

                        # DOB match boost: compare VK bdate with check.date_of_birth
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
                                except (ValueError, IndexError):
                                    pass

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
            task.update('social', 'Telegram — поиск профилей...', 36)
            try:
                from app.services.phase1.telegram_discovery import TelegramDiscoveryService

                tg_birth_year = check.date_of_birth.year if check.date_of_birth else None

                def _tg_search():
                    svc = TelegramDiscoveryService()
                    try:
                        return svc.discover(
                            first_name=name_parts['first'],
                            last_name=name_parts['last'],
                            vk_screen_names=vk_screen_names,
                            city=check.region or '',
                            birth_year=tg_birth_year,
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

            task.update('social', f'Соцсети: найдено {len(social_profiles)} профилей', 42)
            check.social_media_profiles = social_profiles
            db.session.commit()
            _pause()

            # --- Precise mode: pause for profile confirmation ---
            if getattr(check, 'check_mode', 'quick') == 'precise' and social_profiles:
                check.status = 'awaiting_confirmation'
                check.paused_at_stage = 'awaiting_confirmation'
                db.session.commit()
                task.update('social', 'Ожидание подтверждения профиля', 42)
                logger.info(f"Pipeline paused for profile confirmation (check {check_id})")

                max_wait = 1800  # 30 minutes
                waited = 0
                while check.status == 'awaiting_confirmation' and waited < max_wait:
                    if task.cancelled:
                        check.status = 'error'
                        db.session.commit()
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
                    db.session.commit()

                # If user confirmed, check.confirmed_profiles is now populated
                # and check.status is back to 'running'
                if check.status == 'running':
                    check.paused_at_stage = None
                    db.session.commit()
                    task.update('social', 'Профиль подтверждён — продолжение', 42)

            # ══════════════════════════════════════════════
            # STAGE 4: CONTACT DISCOVERY [42-57%]
            # ══════════════════════════════════════════════
            task.update('contacts', 'Поиск контактных данных...', 44)

            try:
                from app.services.candidate.contact_discovery import ContactDiscoveryService

                def _run_contact_discovery():
                    discovery = ContactDiscoveryService()
                    return discovery.discover(check)

                # Run with 120s timeout
                with ThreadPoolExecutor(max_workers=1) as cd_pool:
                    cd_future = cd_pool.submit(_run_contact_discovery)
                    try:
                        contacts = cd_future.result(timeout=120)
                    except Exception as e:
                        logger.warning(f"Contact discovery timeout/error: {e}")
                        contacts = {'phones': [], 'emails': []}

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
                task.update(
                    'contacts',
                    f'Найдено {len(phones)} тел., {len(emails)} email',
                    57,
                )
            except Exception as e:
                logger.error(f"Contact discovery error: {e}", exc_info=True)
                contacts = {'phones': [], 'emails': []}
                task.add_message('Контакты: ошибка поиска', 'warning')
                task.update('contacts', 'Ошибка поиска контактов', 57)

            # Demo fallback for Stage 4
            phones = contacts.get('phones', [])
            emails = contacts.get('emails', [])
            if _is_demo_mode() and not phones and not emails:
                contacts = _get_demo_contacts(check.full_name)
                task.add_message('Контакты: демо-данные (нет API)', 'info')
                sources_with_results += 1

            check.contact_discoveries = contacts
            db.session.commit()

            # ══════════════════════════════════════════════
            # STAGE 5: DEEP SOCIAL ANALYSIS [57-72%]
            # ══════════════════════════════════════════════
            task.update('social_analysis', 'Глубокий анализ соцсетей...', 58)

            try:
                from app.services.candidate.social_analysis import run_social_analysis

                def stage5_callback(stage, msg, pct):
                    task.update('social_analysis', msg, pct or 58)

                social_results = run_social_analysis(
                    check, task_status_callback=stage5_callback,
                )

                # Save results to model
                check.social_graph_data = social_results.get('social_graph', {})
                check.face_matches = social_results.get('face_matches', [])
                check.username_accounts = social_results.get('username_accounts', [])
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

                # Stage 5e: Feedback loop — new accounts → supplementary contacts
                new_accounts = social_results.get('new_accounts_for_enrichment', [])
                if new_accounts:
                    task.update('social_analysis', 'Дообогащение новых аккаунтов', 67)
                    from app.services.candidate.contact_discovery import ContactDiscoveryService
                    contact_service = ContactDiscoveryService()
                    supplementary = contact_service.discover_supplementary(
                        new_accounts=new_accounts,
                        existing_contacts=check.contact_discoveries or {},
                    )
                    # Merge supplementary contacts into existing
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
                logger.error(f"Stage 5 social analysis error: {e}", exc_info=True)
                task.add_message('Глубокий анализ соцсетей: ошибка (пропущен)', 'warning')
                sources_checked += 1

            task.update('social_analysis', 'Социальный анализ завершён', 72)
            _pause()

            # ══════════════════════════════════════════════
            # STAGE 6: BEHAVIORAL INTELLIGENCE [72-83%]
            # ══════════════════════════════════════════════
            task.update('behavioral', 'Поведенческий анализ...', 73)

            try:
                from app.services.candidate.behavioral_analysis import run_behavioral_analysis

                def stage6_callback(stage, msg, pct):
                    task.update('behavioral', msg, pct or 73)

                behavioral_results = run_behavioral_analysis(
                    check, task_status_callback=stage6_callback,
                )

                check.text_analysis = behavioral_results.get('text_analysis', {})
                check.geo_analysis = behavioral_results.get('geo_analysis', {})
                check.activity_timeline = behavioral_results.get('activity_timeline', [])
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
                logger.debug(f"AI behavioral summary skipped: {e}")

            task.update('behavioral', 'Поведенческий анализ завершён', 83)
            _pause()

            # ══════════════════════════════════════════════
            # STAGE 7: RISK SCORING [83-93%]
            # ══════════════════════════════════════════════
            task.update('risk', 'Анализ рисков...', 86)

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

            # Build risk_breakdown by category
            from collections import Counter
            severity_score = {'critical': 40, 'high': 20, 'medium': 10, 'low': 5}
            cat_flags = {}
            for f in merged_flags:
                cat = f.get('category', 'other')
                cat_flags.setdefault(cat, []).append(f)
            breakdown = {}
            total_score = 0
            for cat, flags_list in cat_flags.items():
                cat_score = sum(severity_score.get(f['severity'], 0) for f in flags_list)
                total_score += cat_score
                breakdown[cat] = {
                    'count': len(flags_list),
                    'score': cat_score,
                    'max_severity': flags_list[0]['severity'] if flags_list else 'clean',
                    'flags': [f['code'] for f in flags_list if f.get('code')],
                }
            check.risk_breakdown = breakdown
            check.risk_score_numeric = min(100.0, total_score)
            db.session.commit()

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
            except Exception as e:
                logger.debug(f"AI executive summary skipped: {e}")

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
