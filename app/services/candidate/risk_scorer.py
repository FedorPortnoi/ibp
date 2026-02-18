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

        red_flags.extend(self._analyze_business(check))
        red_flags.extend(self._analyze_courts(check))
        red_flags.extend(self._analyze_fssp(check))
        red_flags.extend(self._analyze_bankruptcy(check))
        red_flags.extend(self._analyze_sanctions(check))
        red_flags.extend(self._analyze_social(check))

        risk_level = self._calculate_risk_level(red_flags)

        severity_order = {
            SEVERITY_CRITICAL: 0,
            SEVERITY_HIGH: 1,
            SEVERITY_MEDIUM: 2,
            SEVERITY_LOW: 3,
        }
        red_flags.sort(key=lambda f: severity_order.get(f['severity'], 99))

        return risk_level, red_flags

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
        total_active_debt = sum((r.get('amount') or 0) for r in active)

        # large_debt vs medium_debt
        if total_active_debt > 500_000:
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
