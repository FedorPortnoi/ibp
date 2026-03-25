"""
Risk Scorer for Candidate Pipeline
===================================
Numeric 0-100 risk scoring with fact/suspicion distinction.
Each flag has: type, code, description, evidence, severity, recommendation.
"""

import json
import logging
import re
from collections import Counter
from datetime import datetime, date

logger = logging.getLogger(__name__)

SEVERITY_CRITICAL = "critical"
SEVERITY_HIGH = "high"
SEVERITY_MEDIUM = "medium"
SEVERITY_LOW = "low"

# Numeric weights for risk score calculation
RISK_WEIGHTS = {
    # FACTS (verified data)
    'court_criminal': 25,
    'court_admin': 10,
    'fraud_case': 20,
    'active_debts': 10,
    'multiple_active': 15,
    'fssp_debt': 15,
    'critical_debt': 20,
    'large_debt': 15,
    'medium_debt': 8,
    'alimony_debt': 10,
    'tax_debt': 15,
    'active_bankruptcy': 20,
    'recent_bankruptcy': 10,
    'many_pledges': 8,
    'pledge_found': 3,
    'sanctions_match': 30,
    'passport_invalid': 20,
    'interpol_found': 35,
    'name_discrepancy': 8,
    # SUSPICIONS (indirect signals)
    'serial_entrepreneur': 5,
    'mass_director': 8,
    'liquidated_companies': 8,
    'recent_liquidation': 6,
    'liquidated_with_debt': 10,
    'mass_registration_address': 6,
    'address_match': 5,
    'geo_discrepancy': 5,
    'high_night_activity': 5,
    'unusual_timezone': 3,
    'political_groups': 8,
    'criminal_groups': 15,
    'gambling_groups': 8,
    'drug_groups': 20,
    'security_groups': 5,
    'name_mismatch': 8,
    'new_account': 3,
    'private_profile': 2,
    'no_photo': 2,
    'connected_high_risk': 10,
    'no_social_presence': 5,
    'no_friends': 3,
    'isolated_graph': 5,
    'fake_profile_indicators': 8,
    'negative_sentiment': 3,
    'risk_keywords': 5,
    'night_activity': 5,
    'inactive_profile': 3,
    'identity_not_confirmed': 3,
    'sanctions_unchecked': 5,
    'many_cases': 8,
    'defendant_cases': 10,
}

# HR-friendly recommendations per code
RECOMMENDATIONS = {
    'court_criminal': 'Рекомендуется запросить справку об отсутствии судимости',
    'fraud_case': 'Рекомендуется дополнительная проверка службой безопасности',
    'active_debts': 'Информационный факт. Рекомендуется уточнить у кандидата',
    'multiple_active': 'Множественные долги указывают на финансовые проблемы. Рекомендуется проверка платёжеспособности',
    'critical_debt': 'Критическая задолженность. Рекомендуется отказ для финансовых позиций',
    'large_debt': 'Крупная задолженность. Рекомендуется дополнительная проверка',
    'medium_debt': 'Умеренная задолженность. Рекомендуется уточнить у кандидата',
    'alimony_debt': 'Задолженность по алиментам. Информационный факт',
    'tax_debt': 'Критично для финансового сектора. Рекомендуется дополнительная проверка',
    'active_bankruptcy': 'Банкрот не может занимать руководящие должности (3 года)',
    'recent_bankruptcy': 'Недавнее банкротство. Рекомендуется учесть при принятии решения',
    'many_pledges': 'Множественные залоги. Возможны значительные финансовые обязательства',
    'pledge_found': 'Информационный факт — обнаружены записи в реестре залогов',
    'sanctions_match': 'КРИТИЧНО: кандидат в санкционном списке. Немедленное уведомление compliance',
    'passport_invalid': 'Паспорт числится недействительным. Рекомендуется запросить оригинал',
    'name_discrepancy': 'Расхождение ФИО. Рекомендуется уточнить у кандидата',
    'serial_entrepreneur': 'Косвенный признак. Множественные бизнес-связи могут быть нормой',
    'mass_director': 'Возможный массовый директор. Рекомендуется проверка реальности бизнеса',
    'liquidated_companies': 'Множество ликвидированных компаний. Рекомендуется уточнить причины',
    'recent_liquidation': 'Недавняя ликвидация. Рекомендуется уточнить причины',
    'liquidated_with_debt': 'Ликвидация при наличии долгов. Рекомендуется дополнительная проверка',
    'mass_registration_address': 'Признак массовой регистрации. Косвенный факт',
    'address_match': 'Информационный факт — бизнес по месту жительства',
    'geo_discrepancy': 'Косвенный признак. Возможна работа в другом городе',
    'high_night_activity': 'Косвенный признак. Возможна работа в ночную смену или другой часовой пояс',
    'unusual_timezone': 'Информационный факт — пик активности в нестандартном часовом поясе',
    'political_groups': 'Информационный факт. Членство в политических группах',
    'criminal_groups': 'Серьёзный признак. Рекомендуется дополнительная проверка',
    'gambling_groups': 'Возможная склонность к азартным играм. Критично для финансовых позиций',
    'drug_groups': 'Серьёзный признак. Рекомендуется дополнительная проверка',
    'security_groups': 'Интерес к кибербезопасности. Оценить в контексте должности',
    'name_mismatch': 'Имя в соцсетях отличается. Рекомендуется уточнить',
    'new_account': 'Информационный факт — относительно новый аккаунт',
    'private_profile': 'Информационный факт — закрытый профиль',
    'no_photo': 'Информационный факт — отсутствует фото профиля',
    'connected_high_risk': 'Связан с кандидатом высокого риска. Рекомендуется проверка характера связи',
    'no_social_presence': 'Необычное отсутствие соцсетей. Возможно, использует другие имена',
    'no_friends': 'Пустой социальный граф. Косвенный признак нового или фейкового аккаунта',
    'isolated_graph': 'Изолированный граф. Косвенный признак',
    'fake_profile_indicators': 'Подозрительный профиль. Рекомендуется проверка подлинности',
    'negative_sentiment': 'Косвенный признак. Негативный тон может отражать жизненные обстоятельства',
    'risk_keywords': 'Рисковые ключевые слова в публикациях. Рекомендуется контекстная оценка',
    'night_activity': 'Косвенный признак. Возможна работа в ночную смену',
    'inactive_profile': 'Информационный факт — давно не активен',
    'identity_not_confirmed': 'ИНН не найден в ЕГРЮЛ. Не является негативным фактором для физлиц',
    'sanctions_unchecked': 'Рекомендуется ручная проверка недоступных источников',
    'many_cases': 'Повышенная судебная активность. Рекомендуется изучить характер дел',
    'defendant_cases': 'Множественные дела в качестве ответчика. Рекомендуется проверка',
    'established_identity': 'Положительный признак — устоявшаяся цифровая личность',
}


def calculate_risk_score(flags: list) -> dict:
    """Calculate numeric risk score 0-100 from flags."""
    raw_score = 0
    for flag in flags:
        weight = RISK_WEIGHTS.get(flag.get('code', ''), 0)
        raw_score += weight

    score = min(raw_score, 100)

    if score >= 60:
        level, level_name = 'critical', 'Критический риск'
    elif score >= 35:
        level, level_name = 'high', 'Высокий риск'
    elif score >= 15:
        level, level_name = 'medium', 'Средний риск'
    else:
        level, level_name = 'low', 'Низкий риск'

    return {
        'score': score,
        'level': level,
        'level_name': level_name,
        'raw_score': raw_score,
    }


class RiskScorer:
    """Centralized risk analysis for candidate background checks."""

    def analyze(self, check):
        """
        Analyze a CandidateCheck and return (risk_level, red_flags).

        Returns:
            tuple: (risk_level_str, list_of_red_flag_dicts)
        """
        red_flags = []

        red_flags.extend(self._analyze_identity(check))
        red_flags.extend(self._analyze_business(check))
        red_flags.extend(self._analyze_courts(check))
        red_flags.extend(self._analyze_fssp(check))
        red_flags.extend(self._analyze_bankruptcy(check))
        red_flags.extend(self._analyze_pledges(check))
        red_flags.extend(self._analyze_sanctions(check))
        red_flags.extend(self._analyze_social(check))
        red_flags.extend(self._analyze_social_behavior(check))
        red_flags.extend(self._analyze_behavioral_patterns(check))
        red_flags.extend(self._analyze_groups(check))
        red_flags.extend(self._analyze_activity_patterns(check))
        red_flags.extend(self._analyze_profile_anomalies(check))
        red_flags.extend(self._analyze_connections(check))

        # Calculate numeric score
        score_data = calculate_risk_score(red_flags)
        risk_level = score_data['level']

        # Backward-compat: also check old severity-based logic for critical
        if any(f['severity'] == SEVERITY_CRITICAL for f in red_flags):
            risk_level = 'critical'

        severity_order = {
            SEVERITY_CRITICAL: 0,
            SEVERITY_HIGH: 1,
            SEVERITY_MEDIUM: 2,
            SEVERITY_LOW: 3,
        }
        red_flags.sort(key=lambda f: severity_order.get(f['severity'], 99))

        return risk_level, red_flags

    def analyze_with_score(self, check):
        """Analyze and return (risk_level, red_flags, risk_score)."""
        risk_level, red_flags = self.analyze(check)
        score_data = calculate_risk_score(red_flags)
        return risk_level, red_flags, score_data['score']

    # ── Identity Red Flags (Stage 0) ──

    def _analyze_identity(self, check):
        flags = []
        identity = getattr(check, 'identity_confirmation', None) or {}

        if identity.get('name_discrepancy'):
            egrul_name = identity.get('egrul_name', '')
            flags.append(self._flag(
                SEVERITY_MEDIUM, 'identity', 'name_discrepancy',
                'Расхождение ФИО: введённое имя отличается от данных ЕГРЮЛ',
                flag_type='fact',
                evidence=f'ЕГРЮЛ: {egrul_name}' if egrul_name else '',
                details=f'ЕГРЮЛ: {egrul_name}' if egrul_name else '',
            ))

        if hasattr(check, 'identity_confirmed') and check.identity_confirmed is False:
            if check.inn:
                flags.append(self._flag(
                    SEVERITY_LOW, 'identity', 'identity_not_confirmed',
                    'ИНН не подтверждён через ЕГРЮЛ (нет записей)',
                    flag_type='fact',
                ))

        return flags

    # ── Business Red Flags ──

    def _analyze_business(self, check):
        flags = []
        records = getattr(check, 'business_records', None) or []
        if not records:
            return flags

        real_records = [r for r in records if r.get('source') != 'manual']
        if not real_records:
            return flags

        if len(real_records) >= 4:
            flags.append(self._flag(
                SEVERITY_LOW, 'business', 'serial_entrepreneur',
                f'Связан с {len(real_records)} компаниями',
                flag_type='suspicion',
                evidence=f'{len(real_records)} записей в ЕГРЮЛ/ЕГРИП',
                details=f'Информационный флаг — множественные бизнес-связи',
            ))

        director_roles = ['директор', 'руководитель', 'учредитель', 'генеральный директор']
        director_count = sum(
            1 for r in real_records
            if any(role in (r.get('role', '') or '').lower() for role in director_roles)
        )
        if director_count >= 5:
            flags.append(self._flag(
                SEVERITY_MEDIUM, 'business', 'mass_director',
                'Руководитель/учредитель 5+ компаний (возможный массовый директор)',
                flag_type='suspicion',
                evidence=f'Руководящая роль в {director_count} организациях (ЕГРЮЛ)',
                details=f'Руководящая роль в {director_count} организациях',
            ))

        liquidated = [
            r for r in real_records
            if 'ликвид' in (r.get('status', '') or '').lower()
            or r.get('end_date')
        ]
        if len(liquidated) >= 3:
            flags.append(self._flag(
                SEVERITY_MEDIUM, 'business', 'liquidated_companies',
                f'{len(liquidated)} ликвидированных компании',
                flag_type='fact',
                evidence=f'ЕГРЮЛ: {len(liquidated)} ликвидированных юрлиц',
            ))

        for r in liquidated:
            end_date_str = r.get('end_date', '') or ''
            end_date = self._parse_date(end_date_str)
            if end_date:
                days_ago = (date.today() - end_date).days
                if days_ago <= 365:
                    flags.append(self._flag(
                        SEVERITY_MEDIUM, 'business', 'recent_liquidation',
                        'Недавно ликвидированная компания',
                        flag_type='fact',
                        evidence=f'{r.get("name", r.get("company_name", ""))} — ликвидирована {end_date_str}',
                        details=f'{r.get("name", r.get("company_name", ""))} — ликвидирована {end_date_str}',
                    ))
                    break

        if liquidated:
            fssp_records = getattr(check, 'fssp_records', None) or []
            active_fssp = [r for r in fssp_records if not r.get('completed')]
            if active_fssp:
                flags.append(self._flag(
                    SEVERITY_MEDIUM, 'business', 'liquidated_with_debt',
                    'Ликвидированная компания при наличии активных исп. производств',
                    flag_type='fact',
                    evidence=f'{len(liquidated)} ликвид. компаний + {len(active_fssp)} активных производств ФССП',
                    details=f'{len(liquidated)} ликвид. компаний, {len(active_fssp)} активных производств ФССП',
                ))

        addresses = [
            (r.get('address', '') or '').strip().lower()
            for r in real_records
            if (r.get('address', '') or '').strip()
        ]
        if addresses:
            addr_counts = Counter(addresses)
            for addr, count in addr_counts.items():
                if count >= 3:
                    flags.append(self._flag(
                        SEVERITY_MEDIUM, 'business', 'mass_registration_address',
                        'Несколько компаний по одному адресу',
                        flag_type='suspicion',
                        evidence=f'{count} компаний по адресу: {addr[:80]}',
                        details=f'{count} компаний по адресу: {addr[:80]}',
                    ))
                    break

        candidate_addr = (getattr(check, 'registered_address', '') or '').strip().lower()
        if candidate_addr and len(candidate_addr) > 10:
            for r in real_records:
                biz_addr = (r.get('address', '') or '').strip().lower()
                if biz_addr and (candidate_addr in biz_addr or biz_addr in candidate_addr):
                    flags.append(self._flag(
                        SEVERITY_MEDIUM, 'business', 'address_match',
                        'Компания зарегистрирована по адресу проживания кандидата',
                        flag_type='fact',
                        evidence=r.get('name', r.get('company_name', '')),
                        details=r.get('name', r.get('company_name', '')),
                    ))
                    break

        return flags

    # ── Court Red Flags ──

    # Confidence weights: UNVERIFIED court records don't affect risk score
    COURT_CONFIDENCE_WEIGHTS = {
        'VERIFIED':   1.0,   # Full weight — INN confirmed
        'LIKELY':     0.7,   # 70% — region + DOB match
        'POSSIBLE':   0.3,   # 30% — region only
        'UNVERIFIED': 0.0,   # No impact — name-only match, could be namesake
    }

    def _get_court_confidence_weight(self, record):
        """Return confidence weight for a court record. UNVERIFIED = 0."""
        confidence = record.get('confidence', '')
        return self.COURT_CONFIDENCE_WEIGHTS.get(confidence, 1.0)

    def _filter_courts_by_confidence(self, records):
        """Filter out UNVERIFIED records from risk-affecting analysis."""
        return [
            r for r in records
            if r.get('confidence', '') != 'UNVERIFIED'
        ]

    def _analyze_courts(self, check):
        flags = []
        records = getattr(check, 'court_records', None) or []
        if not records:
            return flags

        real_records = [r for r in records if r.get('source') != 'manual']
        if not real_records:
            return flags

        # Filter: only consider records with confidence > UNVERIFIED for risk
        risk_records = self._filter_courts_by_confidence(real_records)
        unverified_count = len(real_records) - len(risk_records)
        if unverified_count > 0:
            logger.info(
                f"Court risk: skipping {unverified_count} UNVERIFIED records "
                f"(namesake risk), using {len(risk_records)} verified/likely/possible"
            )

        # Use risk_records (excludes UNVERIFIED) for all risk-affecting checks
        criminal_pattern = re.compile(
            r'ст\.\s*1[5-6][0-9]|уголовн|УК\s+РФ|'
            r'ст\.\s*159|ст\.\s*160|ст\.\s*158',
            re.IGNORECASE,
        )
        for r in risk_records:
            text = ' '.join(filter(None, [
                r.get('category', ''),
                r.get('article', ''),
                r.get('text', ''),
                r.get('title', ''),
            ]))
            if criminal_pattern.search(text):
                conf = r.get('confidence', '')
                flags.append(self._flag(
                    SEVERITY_HIGH, 'courts', 'court_criminal',
                    'Найдено уголовное дело',
                    flag_type='fact',
                    evidence=f'sudact.ru: Дело {r.get("case_number", "Б/Н")}, {r.get("court_name", r.get("court", ""))} [{conf}]',
                    details=r.get('case_number', ''),
                ))
                break

        fraud_keywords = ['мошенничество', 'хищение', 'растрата', 'присвоение']
        for r in risk_records:
            text = ' '.join(filter(None, [
                r.get('category', ''),
                r.get('text', ''),
                r.get('title', ''),
            ])).lower()
            if any(kw in text for kw in fraud_keywords):
                conf = r.get('confidence', '')
                flags.append(self._flag(
                    SEVERITY_HIGH, 'courts', 'fraud_case',
                    'Судебное дело о мошенничестве/хищении',
                    flag_type='fact',
                    evidence=f'sudact.ru: Дело {r.get("case_number", "Б/Н")} [{conf}]',
                    details=r.get('case_number', ''),
                ))
                break

        if len(risk_records) >= 5:
            flags.append(self._flag(
                SEVERITY_MEDIUM, 'courts', 'many_cases',
                f'Повышенная судебная активность ({len(risk_records)} подтверждённых дел)',
                flag_type='fact',
                evidence=f'{len(risk_records)} судебных дел (VERIFIED/LIKELY/POSSIBLE) на sudact.ru/casebook.ru',
            ))

        defendant_keywords = ['ответчик', 'defendant', 'обвиняем', 'подсудим']
        defendant_count = sum(
            1 for r in risk_records
            if any(kw in (r.get('role', '') or '').lower() for kw in defendant_keywords)
        )
        if defendant_count >= 3:
            flags.append(self._flag(
                SEVERITY_MEDIUM, 'courts', 'defendant_cases',
                f'Ответчик в {defendant_count} делах',
                flag_type='fact',
                evidence=f'Роль «ответчик» в {defendant_count} подтверждённых делах',
            ))

        return flags

    # ── FSSP Red Flags ──

    def _analyze_fssp(self, check):
        flags = []
        records = getattr(check, 'fssp_records', None) or []
        if not records:
            return flags

        real_records = [r for r in records if r.get('source') != 'manual']
        if not real_records:
            return flags

        active = [r for r in real_records if r.get('is_active')]

        if active:
            flags.append(self._flag(
                SEVERITY_MEDIUM, 'fssp', 'active_debts',
                f'Активные исполнительные производства ({len(active)})',
                flag_type='fact',
                evidence=f'ФССП: {len(active)} активных производств',
            ))

        if len(active) >= 3:
            flags.append(self._flag(
                SEVERITY_HIGH, 'fssp', 'multiple_active',
                f'Множественные активные производства ({len(active)})',
                flag_type='fact',
                evidence=f'ФССП: {len(active)} активных производств одновременно',
            ))

        total_active_debt = sum(self._safe_number(r.get('amount')) for r in active)

        if total_active_debt > 1_000_000:
            flags.append(self._flag(
                SEVERITY_HIGH, 'fssp', 'critical_debt',
                'Критическая задолженность (>1 000 000\u20bd)',
                flag_type='fact',
                evidence=f'Общая сумма: {total_active_debt:,.0f}\u20bd по {len(active)} производствам',
                details=f'Общая сумма: {total_active_debt:,.0f}\u20bd по {len(active)} производствам',
            ))
        elif total_active_debt > 500_000:
            flags.append(self._flag(
                SEVERITY_HIGH, 'fssp', 'large_debt',
                'Крупная задолженность (>500 000\u20bd)',
                flag_type='fact',
                evidence=f'Общая сумма: {total_active_debt:,.0f}\u20bd по {len(active)} производствам',
                details=f'Общая сумма: {total_active_debt:,.0f}\u20bd по {len(active)} производствам',
            ))
        elif total_active_debt > 100_000:
            flags.append(self._flag(
                SEVERITY_MEDIUM, 'fssp', 'medium_debt',
                'Задолженность >100 000\u20bd',
                flag_type='fact',
                evidence=f'Общая сумма: {total_active_debt:,.0f}\u20bd',
                details=f'Общая сумма: {total_active_debt:,.0f}\u20bd',
            ))

        for r in real_records:
            if 'алимент' in (r.get('subject') or '').lower():
                flags.append(self._flag(
                    SEVERITY_MEDIUM, 'fssp', 'alimony_debt',
                    'Задолженность по алиментам',
                    flag_type='fact',
                    evidence='ФССП: исполнительное производство по алиментам',
                ))
                break

        for r in real_records:
            if 'налог' in (r.get('subject') or '').lower():
                flags.append(self._flag(
                    SEVERITY_HIGH, 'fssp', 'tax_debt',
                    'Налоговая задолженность (критично для финансового сектора)',
                    flag_type='fact',
                    evidence='ФССП: исполнительное производство по налоговой задолженности',
                ))
                break

        return flags

    # ── Bankruptcy Red Flags ──

    def _analyze_bankruptcy(self, check):
        flags = []
        records = getattr(check, 'bankruptcy_records', None) or []
        if not records:
            return flags

        real_records = [r for r in records if r.get('source') != 'manual']
        if not real_records:
            return flags

        for r in real_records:
            if r.get('is_active'):
                flags.append(self._flag(
                    SEVERITY_HIGH, 'bankruptcy', 'active_bankruptcy',
                    'Активное банкротство — запрет на руководящие должности',
                    flag_type='fact',
                    evidence='ЕФРСБ: активное дело о банкротстве',
                ))
                break

        for r in real_records:
            stage = (r.get('stage') or '').lower()
            if 'завершен' in stage or 'прекращен' in stage:
                pub_date = self._parse_date(r.get('publication_date', ''))
                if pub_date:
                    years_ago = (date.today() - pub_date).days / 365.25
                    if years_ago < 3:
                        flags.append(self._flag(
                            SEVERITY_MEDIUM, 'bankruptcy', 'recent_bankruptcy',
                            'Недавнее банкротство (менее 3 лет)',
                            flag_type='fact',
                            evidence=f'ЕФРСБ: банкротство завершено {years_ago:.1f} лет назад',
                        ))
                        break

        return flags

    # ── Pledge Registry Red Flags ──

    def _analyze_pledges(self, check):
        flags = []
        records = getattr(check, 'pledge_records', None) or []
        if not records:
            return flags

        active_pledges = [r for r in records if r.get('status', '').lower() not in ('прекращён', 'удовлетворён')]
        if len(active_pledges) >= 3:
            flags.append(self._flag(
                SEVERITY_MEDIUM, 'financial', 'many_pledges',
                f'Множественные залоги ({len(active_pledges)} активных) — возможные финансовые обязательства',
                flag_type='fact',
                evidence=f'Реестр залогов ФНП: {len(active_pledges)} активных записей',
            ))
        elif active_pledges:
            flags.append(self._flag(
                SEVERITY_LOW, 'financial', 'pledge_found',
                f'Обнаружены записи в залоговом реестре ({len(active_pledges)} записей)',
                flag_type='info',
                evidence=f'Реестр залогов ФНП: {len(active_pledges)} записей',
            ))

        return flags

    # ── Sanctions Red Flags ──

    def _analyze_sanctions(self, check):
        flags = []
        results = getattr(check, 'sanctions_results', None)
        if not results:
            return flags

        if isinstance(results, dict):
            results_list = list(results.values()) if results else []
        elif isinstance(results, list):
            results_list = results
        else:
            return flags

        for r in results_list:
            if isinstance(r, dict) and r.get('checked') and r.get('found'):
                source = r.get('source_name', 'Неизвестный источник')
                details = r.get('match_details', '')
                flags.append(self._flag(
                    SEVERITY_CRITICAL, 'sanctions', 'sanctions_match',
                    f'Найден в санкционном/розыскном списке: {source}',
                    flag_type='fact',
                    evidence=f'{source}: совпадение подтверждено',
                    details=details,
                ))

        unchecked = [
            r for r in results_list
            if isinstance(r, dict) and not r.get('checked')
        ]
        if len(unchecked) >= 2:
            sources = ', '.join(r.get('source_name', '?') for r in unchecked)
            flags.append(self._flag(
                SEVERITY_MEDIUM, 'sanctions', 'sanctions_unchecked',
                'Не удалось проверить санкционные списки — рекомендуется ручная проверка',
                flag_type='suspicion',
                evidence=f'Недоступные источники: {sources}',
                details=f'Источники: {sources}',
            ))

        return flags

    # ── Social Media Red Flags ──

    def _analyze_social(self, check):
        flags = []
        profiles = getattr(check, 'social_media_profiles', None) or []

        if not profiles:
            flags.append(self._flag(
                SEVERITY_MEDIUM, 'social', 'no_social_presence',
                'Не обнаружено присутствие в соцсетях (необычно)',
                flag_type='suspicion',
                evidence='VK, Telegram: профили не найдены',
            ))

        return flags

    # ── Social Behavior Red Flags (Stage 5) ──

    def _analyze_social_behavior(self, check):
        flags = []

        graph = self._safe_json_attr(check, 'social_graph_data', {})
        face_matches = self._safe_json_attr(check, 'face_matches', [])
        username_accounts = self._safe_json_attr(check, 'username_accounts', [])

        stats = graph.get('stats', {})
        node_count = stats.get('node_count', 0)
        if graph and node_count == 0:
            flags.append(self._flag(
                SEVERITY_LOW, 'social_behavior', 'no_friends',
                'Социальный граф пуст — нет друзей в VK',
                flag_type='suspicion',
                evidence='VK friends.get: 0 активных друзей',
            ))

        edge_count = stats.get('edge_count', 0)
        if graph and node_count > 0 and edge_count == 0:
            flags.append(self._flag(
                SEVERITY_MEDIUM, 'social_behavior', 'isolated_graph',
                'Изолированный граф — нет связей между контактами',
                flag_type='suspicion',
                evidence=f'VK: {node_count} друзей, 0 взаимных связей',
            ))

        profiles = self._safe_json_attr(check, 'social_media_profiles', [])
        for p in profiles:
            if isinstance(p, dict):
                has_no_photos = not p.get('photo_url') and not p.get('photo_100')
                has_no_posts = p.get('post_count', -1) == 0
                if has_no_photos and has_no_posts:
                    flags.append(self._flag(
                        SEVERITY_MEDIUM, 'social_behavior', 'fake_profile_indicators',
                        'Подозрительный профиль: нет фото и постов',
                        flag_type='suspicion',
                        evidence=f'Профиль @{p.get("username", "?")} без фото и постов',
                        details=p.get('username', ''),
                    ))
                    break

        platform_count = len(username_accounts)
        if platform_count >= 5:
            flags.append(self._flag(
                SEVERITY_LOW, 'social_behavior', 'established_identity',
                f'Установленная личность: найден на {platform_count} платформах',
                flag_type='fact',
                evidence=f'Snoop/Maigret/Sherlock: аккаунты на {platform_count} платформах',
            ))

        return flags

    # ── Behavioral Patterns Red Flags (Stage 6) ──

    def _analyze_behavioral_patterns(self, check):
        flags = []

        text_analysis = self._safe_json_attr(check, 'text_analysis', {})
        geo_analysis = self._safe_json_attr(check, 'geo_analysis', {})
        activity_timeline = self._safe_json_attr(check, 'activity_timeline', [])

        sentiment = text_analysis.get('sentiment', {})
        if isinstance(sentiment, dict):
            score = sentiment.get('score', 0)
            if isinstance(score, (int, float)) and score < -0.3:
                flags.append(self._flag(
                    SEVERITY_LOW, 'behavioral', 'negative_sentiment',
                    'Преимущественно негативный тон публикаций',
                    flag_type='suspicion',
                    evidence=f'Sentiment score: {score:.2f}',
                    details=f'Sentiment score: {score:.2f}',
                ))

        risk_words = {'долг', 'суд', 'банкрот', 'розыск', 'кредит', 'мошенник'}
        keywords = text_analysis.get('keywords', [])
        found_risk_words = []
        for kw_pair in keywords:
            word = kw_pair[0] if isinstance(kw_pair, (list, tuple)) else str(kw_pair)
            if word.lower() in risk_words:
                found_risk_words.append(word)
        if found_risk_words:
            flags.append(self._flag(
                SEVERITY_MEDIUM, 'behavioral', 'risk_keywords',
                'Рисковые ключевые слова в публикациях',
                flag_type='suspicion',
                evidence=f'VK wall: слова «{", ".join(found_risk_words)}» в публикациях',
                details=', '.join(found_risk_words),
            ))

        posting_times = text_analysis.get('posting_times', [])
        if posting_times and len(posting_times) >= 5:
            night_count = sum(1 for h in posting_times if 2 <= h <= 5)
            night_ratio = night_count / len(posting_times)
            if night_ratio > 0.5:
                flags.append(self._flag(
                    SEVERITY_LOW, 'behavioral', 'night_activity',
                    'Ночная активность: >50% постов между 2-5 утра',
                    flag_type='suspicion',
                    evidence=f'{night_ratio:.0%} постов VK опубликовано с 02:00 до 05:00',
                    details=f'{night_ratio:.0%} ночных постов',
                ))

        profiles = self._safe_json_attr(check, 'social_media_profiles', [])
        claimed_city = ''
        for p in profiles:
            if isinstance(p, dict) and p.get('city'):
                claimed_city = p['city'].lower().strip()
                break

        home_location = geo_analysis.get('home_location')
        if isinstance(home_location, dict):
            geo_city = (home_location.get('city') or '').lower().strip()
            if claimed_city and geo_city and claimed_city != geo_city:
                if claimed_city not in geo_city and geo_city not in claimed_city:
                    if not self._cities_are_related(claimed_city, geo_city):
                        flags.append(self._flag(
                            SEVERITY_MEDIUM, 'behavioral', 'geo_discrepancy',
                            'Расхождение геолокации: заявленный город отличается от фактического',
                            flag_type='suspicion',
                            evidence=f'Профиль: {claimed_city}, Геолокация по постам: {geo_city}',
                            details=f'Профиль: {claimed_city}, Геолокация: {geo_city}',
                        ))

        if activity_timeline:
            post_events = [
                e for e in activity_timeline
                if isinstance(e, dict) and e.get('type') == 'post'
            ]
            if post_events:
                try:
                    newest = max(e.get('timestamp', '') for e in post_events)
                    if newest:
                        newest_dt = datetime.fromisoformat(newest.replace('Z', '+00:00'))
                        days_since = (datetime.now() - newest_dt.replace(tzinfo=None)).days
                        if days_since > 365:
                            flags.append(self._flag(
                                SEVERITY_LOW, 'behavioral', 'inactive_profile',
                                'Неактивный профиль: нет постов более 12 месяцев',
                                flag_type='fact',
                                evidence=f'Последний пост: {days_since} дней назад',
                                details=f'Последний пост: {days_since} дней назад',
                            ))
                except Exception as e:
                    logger.debug(f"[RiskScorer] Error parsing activity dates: {e}")

        return flags

    # ── VK Groups Red Flags (Stage 6 new) ──

    def _analyze_groups(self, check):
        flags = []
        group_analysis = self._safe_json_attr(check, 'group_analysis', {})
        if not group_analysis:
            return flags

        category_counts = group_analysis.get('category_counts', {})
        flagged_groups = group_analysis.get('flagged_groups', [])

        category_to_code = {
            'political_opposition': 'political_groups',
            'political_progovernment': 'political_groups',
            'criminal': 'criminal_groups',
            'gambling': 'gambling_groups',
            'drugs': 'drug_groups',
            'religious_extremist': 'criminal_groups',
            'security_interest': 'security_groups',
        }

        seen_codes = set()
        for group in flagged_groups:
            for cat in group.get('categories', []):
                code = category_to_code.get(cat)
                if code and code not in seen_codes:
                    seen_codes.add(code)

                    severity = SEVERITY_MEDIUM
                    if code in ('criminal_groups', 'drug_groups'):
                        severity = SEVERITY_HIGH

                    cat_display = {
                        'political_groups': 'политические группы',
                        'criminal_groups': 'криминальные группы',
                        'gambling_groups': 'группы азартных игр',
                        'drug_groups': 'группы о наркотиках',
                        'security_groups': 'группы по кибербезопасности',
                    }.get(code, code)

                    count = sum(
                        1 for g in flagged_groups
                        if cat in g.get('categories', [])
                    )

                    flags.append(self._flag(
                        severity, 'groups', code,
                        f'Участник подозрительных групп VK: {cat_display}',
                        flag_type='suspicion',
                        evidence=f'VK groups.get: {count} группа(ы) категории «{cat_display}»',
                    ))

        return flags

    # ── Activity Patterns Red Flags (Stage 6 new) ──

    def _analyze_activity_patterns(self, check):
        flags = []
        patterns = self._safe_json_attr(check, 'activity_patterns', {})
        if not patterns:
            return flags

        activity_flags = patterns.get('activity_flags', [])
        for af in activity_flags:
            code = af.get('code', '')
            if code and code in RISK_WEIGHTS:
                flags.append(self._flag(
                    af.get('severity', SEVERITY_LOW),
                    'behavioral',
                    code,
                    af.get('description', ''),
                    flag_type=af.get('type', 'suspicion'),
                    evidence=af.get('description', ''),
                ))

        return flags

    # ── Profile Anomaly Red Flags (Stage 6 new) ──

    def _analyze_profile_anomalies(self, check):
        """Analyze VK profile anomalies from behavioral analysis."""
        flags = []
        # Profile anomalies are stored by behavioral_analysis in vk_snapshot,
        # but also passed through behavioral_data. Check both.
        behavioral = self._safe_json_attr(check, 'activity_patterns', {})
        # The actual anomaly flags are stored in the behavioral_results
        # during Stage 6 and saved separately. We read them from the
        # pipeline's group_analysis or vk_snapshot.
        snapshot = self._safe_json_attr(check, 'vk_snapshot', {})
        if not snapshot:
            return flags

        vk_id = snapshot.get('vk_id', 0)
        if vk_id and vk_id > 700_000_000:
            flags.append(self._flag(
                SEVERITY_LOW, 'social', 'new_account',
                f'VK аккаунт создан относительно недавно (ID: {vk_id})',
                flag_type='fact',
                evidence=f'VK ID {vk_id} > 700M (создан после ~2020)',
            ))

        if snapshot.get('is_closed'):
            flags.append(self._flag(
                SEVERITY_LOW, 'social', 'private_profile',
                'Профиль VK закрыт — данные ограничены',
                flag_type='fact',
                evidence='VK: is_closed=true',
            ))

        if not snapshot.get('photo_hash'):
            flags.append(self._flag(
                SEVERITY_LOW, 'social', 'no_photo',
                'Фото профиля VK отсутствует',
                flag_type='fact',
                evidence='VK: photo_200 отсутствует',
            ))

        return flags

    # ── Connected Checks Red Flags ──

    def _analyze_connections(self, check):
        flags = []
        connections = self._safe_json_attr(check, 'connected_checks', [])
        if not connections:
            return flags

        for conn in connections:
            risk = conn.get('connected_risk_level', '')
            name = conn.get('connected_name', '')
            if risk in ('high', 'critical'):
                flags.append(self._flag(
                    SEVERITY_MEDIUM, 'connections', 'connected_high_risk',
                    f'Связан с кандидатом высокого риска: {name}',
                    flag_type='suspicion',
                    evidence=f'Общие контакты/бизнес с {name} (риск: {risk})',
                ))

        return flags

    # ── Risk Level Calculation ──

    @staticmethod
    def _calculate_risk_level(red_flags):
        """Legacy severity-based level (kept for backward compat)."""
        if any(f['severity'] == SEVERITY_CRITICAL for f in red_flags):
            return 'critical'

        high_count = sum(1 for f in red_flags if f['severity'] == SEVERITY_HIGH)
        medium_count = sum(1 for f in red_flags if f['severity'] == SEVERITY_MEDIUM)

        if high_count >= 2 or (high_count >= 1 and medium_count >= 2):
            return 'high'

        if high_count >= 1 or medium_count >= 3:
            return 'medium'

        if medium_count >= 1:
            return 'low'

        return 'clean'

    # ── Helpers ──

    _CITY_DISTRICT_MAP = {
        'красная поляна': 'сочи', 'адлер': 'сочи', 'хоста': 'сочи',
        'лазаревское': 'сочи', 'дагомыс': 'сочи',
        'зеленоград': 'москва', 'троицк': 'москва', 'щербинка': 'москва',
        'московский': 'москва', 'коммунарка': 'москва', 'новая москва': 'москва',
        'мытищи': 'москва', 'химки': 'москва', 'люберцы': 'москва',
        'балашиха': 'москва', 'реутов': 'москва', 'долгопрудный': 'москва',
        'красногорск': 'москва',
        'кронштадт': 'санкт-петербург', 'колпино': 'санкт-петербург',
        'пушкин': 'санкт-петербург', 'петергоф': 'санкт-петербург',
        'сестрорецк': 'санкт-петербург', 'ломоносов': 'санкт-петербург',
        'павловск': 'санкт-петербург',
    }

    @staticmethod
    def _cities_are_related(city1: str, city2: str) -> bool:
        m = RiskScorer._CITY_DISTRICT_MAP
        if m.get(city1) == city2 or m.get(city2) == city1:
            return True
        if city1 in m and city2 in m and m[city1] == m[city2]:
            return True
        return False

    @staticmethod
    def _flag(severity, category, code, text, flag_type='fact',
              evidence='', details=''):
        flag = {
            'type': flag_type,
            'severity': severity,
            'category': category,
            'code': code,
            'text': text,
            'description': text,
            'evidence': evidence or details or '',
            'recommendation': RECOMMENDATIONS.get(code, ''),
        }
        if details:
            flag['details'] = details
        return flag

    @staticmethod
    def _safe_number(value):
        if value is None:
            return 0
        if isinstance(value, (int, float)):
            return value
        try:
            return float(value)
        except (ValueError, TypeError):
            return 0

    @staticmethod
    def _safe_json_attr(obj, attr, default):
        """Get a JSON attribute, parsing string if needed."""
        val = getattr(obj, attr, None)
        if val is None:
            return default
        if isinstance(val, str):
            try:
                return json.loads(val)
            except (json.JSONDecodeError, TypeError):
                return default
        return val

    @staticmethod
    def _parse_date(date_str):
        if not date_str:
            return None
        for fmt in ('%d.%m.%Y', '%Y-%m-%d'):
            try:
                return datetime.strptime(date_str.strip(), fmt).date()
            except (ValueError, AttributeError):
                continue
        return None
