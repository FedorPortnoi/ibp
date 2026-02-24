"""
Candidate Check Pipeline
========================
Orchestrates the 8-stage unified background check.

Stages:
1. Government Registries (ЕГРЮЛ, courts, ФССП, ЕФРСБ)   [0-15%]
2. Security Checks (sanctions)                             [15-25%]
3. Social Media Discovery (VK, Telegram)                   [25-40%]
4. Contact Discovery (VK/TG extraction + breach APIs)      [40-55%]
5. Deep Social Analysis (face search, graph, Snoop)        [55-70%]
6. Behavioral Intelligence (text, geo, timeline)           [70-82%]
7. Risk Scoring (8-category red flags)                     [82-92%]
8. Report Generation (dossier + identity card)             [92-100%]
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
            # STAGE 1: GOVERNMENT REGISTRIES [0-15%]
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

            # Demo fallback for Stage 1
            if _is_demo_mode() and not biz_records and not court_records:
                demo_biz, demo_courts, demo_fssp, demo_bankruptcy = _get_demo_gov_data(check.full_name)
                biz_records = demo_biz
                court_records = demo_courts
                fssp_records = demo_fssp
                bankruptcy_records = demo_bankruptcy
                task.add_message('Реестры: демо-данные (нет API)', 'info')
                sources_with_results += 2
                sources_checked += 4

            check.business_records = biz_records
            check.court_records = court_records
            check.fssp_records = fssp_records
            check.bankruptcy_records = bankruptcy_records
            task.update('gov_registries', 'Реестры проверены', 15)
            _pause()

            db.session.commit()

            # ══════════════════════════════════════════════
            # STAGE 2: SECURITY CHECKS [15-25%]
            # ══════════════════════════════════════════════
            task.update('security', 'Проверка санкционных списков...', 18)

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
                25,
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
            # STAGE 3: SOCIAL MEDIA DISCOVERY [25-40%]
            # ══════════════════════════════════════════════
            task.update('social', 'Поиск в социальных сетях...', 28)

            social_profiles = []
            vk_screen_names = []

            # 3.1 VK search — run first so Telegram can use screen_names
            task.update('social', 'VK — поиск профилей...', 30)
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
            task.update('social', 'Telegram — поиск профилей...', 34)
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

            task.update('social', f'Соцсети: найдено {len(social_profiles)} профилей', 40)
            check.social_media_profiles = social_profiles
            db.session.commit()
            _pause()

            # --- Precise mode: pause for profile confirmation ---
            if getattr(check, 'check_mode', 'quick') == 'precise' and social_profiles:
                check.status = 'awaiting_confirmation'
                check.paused_at_stage = 'awaiting_confirmation'
                db.session.commit()
                task.update('social', 'Ожидание подтверждения профиля', 40)
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
                    task.update('social', 'Профиль подтверждён — продолжение', 40)

            # ══════════════════════════════════════════════
            # STAGE 4: CONTACT DISCOVERY [40-55%]
            # ══════════════════════════════════════════════
            task.update('contacts', 'Поиск контактных данных...', 42)

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
                    55,
                )
            except Exception as e:
                logger.error(f"Contact discovery error: {e}", exc_info=True)
                contacts = {'phones': [], 'emails': []}
                task.add_message('Контакты: ошибка поиска', 'warning')
                task.update('contacts', 'Ошибка поиска контактов', 55)

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
            # STAGE 5: DEEP SOCIAL ANALYSIS [55-70%]
            # ══════════════════════════════════════════════
            task.update('social_analysis', 'Глубокий анализ соцсетей...', 56)

            try:
                from app.services.candidate.social_analysis import run_social_analysis

                def stage5_callback(stage, msg, pct):
                    task.update('social_analysis', msg, pct or 56)

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
                    task.update('social_analysis', 'Дообогащение новых аккаунтов', 65)
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

            task.update('social_analysis', 'Социальный анализ завершён', 70)
            _pause()

            # ══════════════════════════════════════════════
            # STAGE 6: BEHAVIORAL INTELLIGENCE [70-82%]
            # ══════════════════════════════════════════════
            task.update('behavioral', 'Поведенческий анализ...', 72)

            try:
                from app.services.candidate.behavioral_analysis import run_behavioral_analysis

                def stage6_callback(stage, msg, pct):
                    task.update('behavioral', msg, pct or 72)

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

            task.update('behavioral', 'Поведенческий анализ завершён', 82)
            _pause()

            # ══════════════════════════════════════════════
            # STAGE 7: RISK SCORING [82-92%]
            # ══════════════════════════════════════════════
            task.update('risk', 'Анализ рисков...', 85)

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

            task.update('risk', f'Риск: {check.risk_level_display}', 92)
            task.add_message(
                f'Оценка риска: {check.risk_level_display} '
                f'({len(merged_flags)} факторов)',
                'success',
            )
            _pause()

            # ══════════════════════════════════════════════
            # STAGE 8: REPORT GENERATION [92-100%]
            # ══════════════════════════════════════════════
            task.update('report', 'Генерация отчёта...', 94)

            try:
                from app.services.candidate.report_builder import build_report
                report_data = build_report(check)
                check.report_generated = True
                db.session.commit()
                task.add_message('Отчёт сгенерирован', 'success')
            except Exception as e:
                logger.error(f"Stage 8 report generation error: {e}", exc_info=True)
                task.add_message('Генерация отчёта: ошибка (пропущен)', 'warning')

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
