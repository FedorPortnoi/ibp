"""
Risk Scorer for Candidate Pipeline
===================================
Analyzes all collected data from all pipeline stages,
detects red flags with cross-referencing, assigns severity levels,
calculates overall risk level, and produces a final red flag summary.
"""

import logging
import re
from collections import Counter
from datetime import datetime, date

logger = logging.getLogger(__name__)

SEVERITY_CRITICAL = "critical"   # Auto-disqualifier
SEVERITY_HIGH = "high"           # Serious, likely disqualifier
SEVERITY_MEDIUM = "medium"       # Warning, needs review
SEVERITY_LOW = "low"             # Informational


class RiskScorer:
    """Centralized risk analysis for candidate background checks."""

    def analyze(self, check):
        """
        Analyze a CandidateCheck and return (risk_level, red_flags).

        Args:
            check: CandidateCheck object with populated fields

        Returns:
            tuple: (risk_level_str, list_of_red_flag_dicts)
        """
        red_flags = []

        red_flags.extend(self._analyze_identity(check))
        red_flags.extend(self._analyze_business(check))
        red_flags.extend(self._analyze_courts(check))
        red_flags.extend(self._analyze_fssp(check))
        red_flags.extend(self._analyze_bankruptcy(check))
        red_flags.extend(self._analyze_sanctions(check))
        red_flags.extend(self._analyze_social(check))
        red_flags.extend(self._analyze_social_behavior(check))
        red_flags.extend(self._analyze_behavioral_patterns(check))

        risk_level = self._calculate_risk_level(red_flags)

        severity_order = {
            SEVERITY_CRITICAL: 0,
            SEVERITY_HIGH: 1,
            SEVERITY_MEDIUM: 2,
            SEVERITY_LOW: 3,
        }
        red_flags.sort(key=lambda f: severity_order.get(f['severity'], 99))

        return risk_level, red_flags

    # ── Identity Red Flags (Stage 0) ──

    def _analyze_identity(self, check):
        """Analyze identity confirmation results from Stage 0."""
        flags = []
        identity = getattr(check, 'identity_confirmation', None) or {}

        # Name discrepancy: EGRUL name differs from user input
        if identity.get('name_discrepancy'):
            egrul_name = identity.get('egrul_name', '')
            flags.append(self._flag(
                SEVERITY_MEDIUM, 'identity', 'name_discrepancy',
                'Расхождение ФИО: введённое имя отличается от данных ЕГРЮЛ',
                details=f'ЕГРЮЛ: {egrul_name}' if egrul_name else '',
            ))

        # Identity not confirmed via INN
        if hasattr(check, 'identity_confirmed') and check.identity_confirmed is False:
            # Only flag if INN was provided (it should be, since it's required)
            if check.inn:
                flags.append(self._flag(
                    SEVERITY_LOW, 'identity', 'identity_not_confirmed',
                    'ИНН не подтверждён через ЕГРЮЛ (нет записей)',
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

        # mass_director — 5+ companies where person is director/founder
        director_roles = ['директор', 'руководитель', 'учредитель', 'генеральный директор']
        director_count = sum(
            1 for r in real_records
            if any(role in (r.get('role', '') or '').lower() for role in director_roles)
        )
        if director_count >= 5:
            flags.append(self._flag(
                SEVERITY_MEDIUM, 'business', 'mass_director',
                'Руководитель/учредитель 5+ компаний (возможный массовый директор)',
                details=f'Руководящая роль в {director_count} организациях',
            ))

        # liquidated_companies — 3+ liquidated
        liquidated = [
            r for r in real_records
            if 'ликвид' in (r.get('status', '') or '').lower()
            or r.get('end_date')
        ]
        if len(liquidated) >= 3:
            flags.append(self._flag(
                SEVERITY_MEDIUM, 'business', 'liquidated_companies',
                f'{len(liquidated)} ликвидированных компании',
            ))

        # recent_liquidation — liquidated within last 12 months
        for r in liquidated:
            end_date_str = r.get('end_date', '') or ''
            end_date = self._parse_date(end_date_str)
            if end_date:
                days_ago = (date.today() - end_date).days
                if days_ago <= 365:
                    flags.append(self._flag(
                        SEVERITY_MEDIUM, 'business', 'recent_liquidation',
                        'Недавно ликвидированная компания',
                        details=f'{r.get("name", r.get("company_name", ""))} — ликвидирована {end_date_str}',
                    ))
                    break

        # mass_registration_address — multiple companies at same address
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
                        details=f'{count} компаний по адресу: {addr[:80]}',
                    ))
                    break

        # address_match — company at candidate's personal address
        candidate_addr = (getattr(check, 'registered_address', '') or '').strip().lower()
        if candidate_addr and len(candidate_addr) > 10:
            for r in real_records:
                biz_addr = (r.get('address', '') or '').strip().lower()
                if biz_addr and (candidate_addr in biz_addr or biz_addr in candidate_addr):
                    flags.append(self._flag(
                        SEVERITY_MEDIUM, 'business', 'address_match',
                        'Компания зарегистрирована по адресу проживания кандидата',
                        details=r.get('name', r.get('company_name', '')),
                    ))
                    break

        return flags

    # ── Court Red Flags ──

    def _analyze_courts(self, check):
        flags = []
        records = getattr(check, 'court_records', None) or []
        if not records:
            return flags

        real_records = [r for r in records if r.get('source') != 'manual']
        if not real_records:
            return flags

        # criminal_case — criminal article references
        criminal_pattern = re.compile(
            r'ст\.\s*1[5-6][0-9]|уголовн|УК\s+РФ|'
            r'ст\.\s*159|ст\.\s*160|ст\.\s*158',
            re.IGNORECASE,
        )
        for r in real_records:
            text = ' '.join(filter(None, [
                r.get('category', ''),
                r.get('article', ''),
                r.get('text', ''),
                r.get('title', ''),
            ]))
            if criminal_pattern.search(text):
                flags.append(self._flag(
                    SEVERITY_HIGH, 'courts', 'criminal_case',
                    'Уголовное дело',
                    details=r.get('case_number', ''),
                ))
                break

        # fraud_case — fraud/embezzlement keywords
        fraud_keywords = ['мошенничество', 'хищение', 'растрата', 'присвоение']
        for r in real_records:
            text = ' '.join(filter(None, [
                r.get('category', ''),
                r.get('text', ''),
                r.get('title', ''),
            ])).lower()
            if any(kw in text for kw in fraud_keywords):
                flags.append(self._flag(
                    SEVERITY_HIGH, 'courts', 'fraud_case',
                    'Судебное дело о мошенничестве/хищении',
                    details=r.get('case_number', ''),
                ))
                break

        # many_cases — 5+
        if len(real_records) >= 5:
            flags.append(self._flag(
                SEVERITY_MEDIUM, 'courts', 'many_cases',
                f'Повышенная судебная активность ({len(real_records)} дел)',
            ))

        # defendant_cases — defendant in 3+
        defendant_keywords = ['ответчик', 'defendant', 'обвиняем', 'подсудим']
        defendant_count = sum(
            1 for r in real_records
            if any(kw in (r.get('role', '') or '').lower() for kw in defendant_keywords)
        )
        if defendant_count >= 3:
            flags.append(self._flag(
                SEVERITY_MEDIUM, 'courts', 'defendant_cases',
                f'Ответчик в {defendant_count} делах',
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

        # active_debts
        if active:
            flags.append(self._flag(
                SEVERITY_MEDIUM, 'fssp', 'active_debts',
                f'Активные исполнительные производства ({len(active)})',
            ))

        # multiple_active — 3+
        if len(active) >= 3:
            flags.append(self._flag(
                SEVERITY_HIGH, 'fssp', 'multiple_active',
                f'Множественные активные производства ({len(active)})',
            ))

        # Total active debt
        total_active_debt = sum(self._safe_number(r.get('amount')) for r in active)

        # critical_debt > large_debt > medium_debt
        if total_active_debt > 1_000_000:
            flags.append(self._flag(
                SEVERITY_HIGH, 'fssp', 'critical_debt',
                'Критическая задолженность (>1 000 000\u20bd)',
                details=f'Общая сумма: {total_active_debt:,.0f}\u20bd по {len(active)} производствам',
            ))
        elif total_active_debt > 500_000:
            flags.append(self._flag(
                SEVERITY_HIGH, 'fssp', 'large_debt',
                'Крупная задолженность (>500 000\u20bd)',
                details=f'Общая сумма: {total_active_debt:,.0f}\u20bd по {len(active)} производствам',
            ))
        elif total_active_debt > 100_000:
            flags.append(self._flag(
                SEVERITY_MEDIUM, 'fssp', 'medium_debt',
                'Задолженность >100 000\u20bd',
                details=f'Общая сумма: {total_active_debt:,.0f}\u20bd',
            ))

        # alimony_debt
        for r in real_records:
            if 'алимент' in (r.get('subject') or '').lower():
                flags.append(self._flag(
                    SEVERITY_MEDIUM, 'fssp', 'alimony_debt',
                    'Задолженность по алиментам',
                ))
                break

        # tax_debt
        for r in real_records:
            if 'налог' in (r.get('subject') or '').lower():
                flags.append(self._flag(
                    SEVERITY_HIGH, 'fssp', 'tax_debt',
                    'Налоговая задолженность (критично для финансового сектора)',
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

        # active_bankruptcy
        for r in real_records:
            if r.get('is_active'):
                flags.append(self._flag(
                    SEVERITY_HIGH, 'bankruptcy', 'active_bankruptcy',
                    'Активное банкротство — запрет на руководящие должности',
                ))
                break

        # recent_bankruptcy — completed within 3 years
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
                        ))
                        break

        return flags

    # ── Sanctions Red Flags ──

    def _analyze_sanctions(self, check):
        flags = []
        results = getattr(check, 'sanctions_results', None)
        if not results:
            return flags

        # Handle both list and dict formats
        if isinstance(results, dict):
            results_list = list(results.values()) if results else []
        elif isinstance(results, list):
            results_list = results
        else:
            return flags

        # sanctions_match
        for r in results_list:
            if isinstance(r, dict) and r.get('checked') and r.get('found'):
                source = r.get('source_name', 'Неизвестный источник')
                details = r.get('match_details', '')
                flags.append(self._flag(
                    SEVERITY_CRITICAL, 'sanctions', 'sanctions_match',
                    f'Найден в санкционном/розыскном списке: {source}',
                    details=details,
                ))

        # sanctions_unchecked — unable to check 2+ sources
        unchecked = [
            r for r in results_list
            if isinstance(r, dict) and not r.get('checked')
        ]
        if len(unchecked) >= 2:
            sources = ', '.join(r.get('source_name', '?') for r in unchecked)
            flags.append(self._flag(
                SEVERITY_MEDIUM, 'sanctions', 'sanctions_unchecked',
                'Не удалось проверить санкционные списки — рекомендуется ручная проверка',
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
            ))

        return flags

    # ── Social Behavior Red Flags (Stage 5) ──

    def _analyze_social_behavior(self, check):
        """Category 7: Social behavior analysis from Stage 5 data."""
        flags = []

        graph = getattr(check, 'social_graph_data', None)
        if isinstance(graph, str):
            try:
                import json
                graph = json.loads(graph)
            except (json.JSONDecodeError, TypeError):
                graph = {}
        if not graph or not isinstance(graph, dict):
            graph = {}

        face_matches = getattr(check, 'face_matches', None)
        if isinstance(face_matches, str):
            try:
                import json
                face_matches = json.loads(face_matches)
            except (json.JSONDecodeError, TypeError):
                face_matches = []
        if not face_matches or not isinstance(face_matches, list):
            face_matches = []

        username_accounts = getattr(check, 'username_accounts', None)
        if isinstance(username_accounts, str):
            try:
                import json
                username_accounts = json.loads(username_accounts)
            except (json.JSONDecodeError, TypeError):
                username_accounts = []
        if not username_accounts or not isinstance(username_accounts, list):
            username_accounts = []

        # no_friends: social graph has 0 nodes (beyond center)
        stats = graph.get('stats', {})
        node_count = stats.get('node_count', 0)
        if graph and node_count == 0:
            flags.append(self._flag(
                SEVERITY_LOW, 'social_behavior', 'no_friends',
                'Социальный граф пуст — нет друзей в VK',
            ))

        # isolated_graph: graph exists but 0 edges
        edge_count = stats.get('edge_count', 0)
        if graph and node_count > 0 and edge_count == 0:
            flags.append(self._flag(
                SEVERITY_MEDIUM, 'social_behavior', 'isolated_graph',
                'Изолированный граф — нет связей между контактами',
            ))

        # fake_profile_indicators: found on social but suspicious signs
        profiles = getattr(check, 'social_media_profiles', None) or []
        if isinstance(profiles, str):
            try:
                import json
                profiles = json.loads(profiles)
            except (json.JSONDecodeError, TypeError):
                profiles = []
        for p in profiles:
            if isinstance(p, dict):
                # Check for recent creation + no photos + no posts
                has_no_photos = not p.get('photo_url') and not p.get('photo_100')
                has_no_posts = p.get('post_count', -1) == 0
                # If profile explicitly has 0 posts and no photo
                if has_no_photos and has_no_posts:
                    flags.append(self._flag(
                        SEVERITY_MEDIUM, 'social_behavior', 'fake_profile_indicators',
                        'Подозрительный профиль: нет фото и постов',
                        details=p.get('username', ''),
                    ))
                    break

        # established_identity: found on 5+ platforms (positive indicator)
        platform_count = len(username_accounts)
        if platform_count >= 5:
            flags.append(self._flag(
                SEVERITY_LOW, 'social_behavior', 'established_identity',
                f'Установленная личность: найден на {platform_count} платформах',
            ))

        return flags

    # ── Behavioral Patterns Red Flags (Stage 6) ──

    def _analyze_behavioral_patterns(self, check):
        """Category 8: Behavioral patterns from Stage 6 data."""
        flags = []

        text_analysis = getattr(check, 'text_analysis', None)
        if isinstance(text_analysis, str):
            try:
                import json
                text_analysis = json.loads(text_analysis)
            except (json.JSONDecodeError, TypeError):
                text_analysis = {}
        if not text_analysis or not isinstance(text_analysis, dict):
            text_analysis = {}

        geo_analysis = getattr(check, 'geo_analysis', None)
        if isinstance(geo_analysis, str):
            try:
                import json
                geo_analysis = json.loads(geo_analysis)
            except (json.JSONDecodeError, TypeError):
                geo_analysis = {}
        if not geo_analysis or not isinstance(geo_analysis, dict):
            geo_analysis = {}

        activity_timeline = getattr(check, 'activity_timeline', None)
        if isinstance(activity_timeline, str):
            try:
                import json
                activity_timeline = json.loads(activity_timeline)
            except (json.JSONDecodeError, TypeError):
                activity_timeline = []
        if not activity_timeline or not isinstance(activity_timeline, list):
            activity_timeline = []

        # negative_sentiment: sentiment score < -0.3
        sentiment = text_analysis.get('sentiment', {})
        if isinstance(sentiment, dict):
            score = sentiment.get('score', 0)
            if isinstance(score, (int, float)) and score < -0.3:
                flags.append(self._flag(
                    SEVERITY_LOW, 'behavioral', 'negative_sentiment',
                    'Преимущественно негативный тон публикаций',
                    details=f'Sentiment score: {score:.2f}',
                ))

        # risk_keywords: posts contain risk-related words
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
                details=', '.join(found_risk_words),
            ))

        # night_activity: >50% posts between 2-5 AM
        posting_times = text_analysis.get('posting_times', [])
        if posting_times and len(posting_times) >= 5:
            night_count = sum(1 for h in posting_times if 2 <= h <= 5)
            night_ratio = night_count / len(posting_times)
            if night_ratio > 0.5:
                flags.append(self._flag(
                    SEVERITY_LOW, 'behavioral', 'night_activity',
                    'Ночная активность: >50% постов между 2-5 утра',
                    details=f'{night_ratio:.0%} ночных постов',
                ))

        # geo_discrepancy: claimed city differs from most frequent geo
        profiles = getattr(check, 'social_media_profiles', None) or []
        if isinstance(profiles, str):
            try:
                import json
                profiles = json.loads(profiles)
            except (json.JSONDecodeError, TypeError):
                profiles = []

        claimed_city = ''
        for p in profiles:
            if isinstance(p, dict) and p.get('city'):
                claimed_city = p['city'].lower().strip()
                break

        home_location = geo_analysis.get('home_location')
        if isinstance(home_location, dict):
            geo_city = (home_location.get('city') or '').lower().strip()
            if claimed_city and geo_city and claimed_city != geo_city:
                # Check if they're really different (not substring)
                if claimed_city not in geo_city and geo_city not in claimed_city:
                    flags.append(self._flag(
                        SEVERITY_MEDIUM, 'behavioral', 'geo_discrepancy',
                        'Расхождение геолокации: заявленный город отличается от фактического',
                        details=f'Профиль: {claimed_city}, Геолокация: {geo_city}',
                    ))

        # inactive_profile: no posts in 12+ months
        if activity_timeline:
            # Find most recent post event
            post_events = [
                e for e in activity_timeline
                if isinstance(e, dict) and e.get('type') == 'post'
            ]
            if post_events:
                try:
                    from datetime import datetime
                    newest = max(
                        e.get('timestamp', '') for e in post_events
                    )
                    if newest:
                        newest_dt = datetime.fromisoformat(newest.replace('Z', '+00:00'))
                        days_since = (datetime.now() - newest_dt.replace(tzinfo=None)).days
                        if days_since > 365:
                            flags.append(self._flag(
                                SEVERITY_LOW, 'behavioral', 'inactive_profile',
                                'Неактивный профиль: нет постов более 12 месяцев',
                                details=f'Последний пост: {days_since} дней назад',
                            ))
                except Exception:
                    pass

        return flags

    # ── Risk Level Calculation ──

    @staticmethod
    def _calculate_risk_level(red_flags):
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

    @staticmethod
    def _flag(severity, category, code, text, details=''):
        flag = {
            'severity': severity,
            'category': category,
            'code': code,
            'text': text,
        }
        if details:
            flag['details'] = details
        return flag

    @staticmethod
    def _safe_number(value):
        """Safely coerce a value to a number for summation. Returns 0 for non-numeric."""
        if value is None:
            return 0
        if isinstance(value, (int, float)):
            return value
        try:
            return float(value)
        except (ValueError, TypeError):
            return 0

    @staticmethod
    def _parse_date(date_str):
        """Parse a date string in DD.MM.YYYY or YYYY-MM-DD format."""
        if not date_str:
            return None
        for fmt in ('%d.%m.%Y', '%Y-%m-%d'):
            try:
                return datetime.strptime(date_str.strip(), fmt).date()
            except (ValueError, AttributeError):
                continue
        return None
