"""
Edge-case and boundary-condition tests for RiskScorer.

Tests threshold boundaries (>=5, >=3, >500k, >100k, etc.),
case sensitivity, format handling, empty inputs, and sorting.

This file must NOT modify any existing test file.
"""

import pytest
from datetime import date, timedelta

from app.services.candidate.risk_scorer import RiskScorer


class MockCheck:
    """Mock CandidateCheck for testing edge cases."""
    def __init__(self, **kwargs):
        self.business_records = kwargs.get('business_records', [])
        self.court_records = kwargs.get('court_records', [])
        self.fssp_records = kwargs.get('fssp_records', [])
        self.bankruptcy_records = kwargs.get('bankruptcy_records', [])
        self.sanctions_results = kwargs.get('sanctions_results', [])
        self.social_media_profiles = kwargs.get('social_media_profiles', [])
        self.registered_address = kwargs.get('registered_address', '')


# =========================================================================
#  Business Edge Cases
# =========================================================================

class TestBusinessEdgeCases:
    @pytest.fixture
    def scorer(self):
        return RiskScorer()

    def test_exactly_5_companies_triggers_mass_director(self, scorer):
        """Threshold is >=5, so exactly 5 should trigger."""
        records = [{'role': 'директор', 'source': 'api'} for _ in range(5)]
        check = MockCheck(business_records=records)
        flags = scorer._analyze_business(check)
        assert any(f['code'] == 'mass_director' for f in flags)

    def test_exactly_4_companies_no_mass_director(self, scorer):
        """4 is below the >=5 threshold."""
        records = [{'role': 'директор', 'source': 'api'} for _ in range(4)]
        check = MockCheck(business_records=records)
        flags = scorer._analyze_business(check)
        assert not any(f['code'] == 'mass_director' for f in flags)

    def test_director_roles_case_insensitive(self, scorer):
        """Director role matching uses .lower(), so mixed case should work."""
        records = [{'role': 'Директор', 'source': 'api'} for _ in range(5)]
        check = MockCheck(business_records=records)
        flags = scorer._analyze_business(check)
        assert any(f['code'] == 'mass_director' for f in flags)

    def test_general_director_role_counted(self, scorer):
        """'генеральный директор' is in the director_roles list."""
        records = [{'role': 'генеральный директор', 'source': 'api'} for _ in range(5)]
        check = MockCheck(business_records=records)
        flags = scorer._analyze_business(check)
        assert any(f['code'] == 'mass_director' for f in flags)

    def test_founder_role_counted(self, scorer):
        """'учредитель' is in the director_roles list."""
        records = [{'role': 'учредитель', 'source': 'api'} for _ in range(5)]
        check = MockCheck(business_records=records)
        flags = scorer._analyze_business(check)
        assert any(f['code'] == 'mass_director' for f in flags)

    def test_non_director_role_not_counted(self, scorer):
        """Roles like 'бухгалтер' should not count as director."""
        records = [{'role': 'бухгалтер', 'source': 'api'} for _ in range(10)]
        check = MockCheck(business_records=records)
        flags = scorer._analyze_business(check)
        assert not any(f['code'] == 'mass_director' for f in flags)

    def test_liquidated_status_triggers_flag(self, scorer):
        """3+ records with 'ликвид' in status trigger liquidated_companies."""
        records = [
            {'status': 'ликвидация', 'source': 'api'},
            {'status': 'ликвидировано', 'source': 'api'},
            {'status': 'в процессе ликвидации', 'source': 'api'},
        ]
        check = MockCheck(business_records=records)
        flags = scorer._analyze_business(check)
        assert any(f['code'] == 'liquidated_companies' for f in flags)

    def test_2_liquidated_no_flag(self, scorer):
        """Only 2 liquidated -- below threshold of >=3."""
        records = [
            {'status': 'ликвидация', 'source': 'api'},
            {'status': 'ликвидировано', 'source': 'api'},
        ]
        check = MockCheck(business_records=records)
        flags = scorer._analyze_business(check)
        assert not any(f['code'] == 'liquidated_companies' for f in flags)

    def test_end_date_counts_as_liquidated(self, scorer):
        """Records with end_date but no 'ликвид' in status still count as liquidated."""
        records = [
            {'status': 'действующая', 'end_date': '01.01.2020', 'source': 'api'},
            {'status': 'действующая', 'end_date': '01.06.2020', 'source': 'api'},
            {'status': 'действующая', 'end_date': '01.12.2020', 'source': 'api'},
        ]
        check = MockCheck(business_records=records)
        flags = scorer._analyze_business(check)
        assert any(f['code'] == 'liquidated_companies' for f in flags)

    def test_active_status_no_liquidation_flag(self, scorer):
        """Active records with no end_date should not trigger liquidation."""
        records = [{'status': 'действующее', 'source': 'api'} for _ in range(3)]
        check = MockCheck(business_records=records)
        flags = scorer._analyze_business(check)
        assert not any(f['code'] == 'liquidated_companies' for f in flags)

    def test_manual_source_ignored(self, scorer):
        """Records with source='manual' are filtered out entirely."""
        records = [{'role': 'директор', 'source': 'manual'} for _ in range(10)]
        check = MockCheck(business_records=records)
        flags = scorer._analyze_business(check)
        assert len(flags) == 0

    def test_mass_registration_3_same_address(self, scorer):
        """3 companies at the same address triggers mass_registration_address."""
        records = [
            {'address': 'Москва, ул. Ленина, 1', 'source': 'api'},
            {'address': 'Москва, ул. Ленина, 1', 'source': 'api'},
            {'address': 'Москва, ул. Ленина, 1', 'source': 'api'},
        ]
        check = MockCheck(business_records=records)
        flags = scorer._analyze_business(check)
        assert any(f['code'] == 'mass_registration_address' for f in flags)

    def test_mass_registration_2_same_address_no_flag(self, scorer):
        """Only 2 at same address -- below >=3 threshold."""
        records = [
            {'address': 'Москва, ул. Ленина, 1', 'source': 'api'},
            {'address': 'Москва, ул. Ленина, 1', 'source': 'api'},
        ]
        check = MockCheck(business_records=records)
        flags = scorer._analyze_business(check)
        assert not any(f['code'] == 'mass_registration_address' for f in flags)

    def test_mass_registration_case_insensitive(self, scorer):
        """Address comparison is case-insensitive (.lower())."""
        records = [
            {'address': 'Москва, Ул. Ленина, 1', 'source': 'api'},
            {'address': 'москва, ул. ленина, 1', 'source': 'api'},
            {'address': 'МОСКВА, УЛ. ЛЕНИНА, 1', 'source': 'api'},
        ]
        check = MockCheck(business_records=records)
        flags = scorer._analyze_business(check)
        assert any(f['code'] == 'mass_registration_address' for f in flags)

    def test_address_match_with_candidate(self, scorer):
        """Business address matching candidate's personal address."""
        records = [{'address': 'Москва, ул. Ленина, д. 15, кв. 42', 'source': 'api'}]
        check = MockCheck(
            business_records=records,
            registered_address='Москва, ул. Ленина, д. 15, кв. 42',
        )
        flags = scorer._analyze_business(check)
        assert any(f['code'] == 'address_match' for f in flags)

    def test_address_match_requires_min_length(self, scorer):
        """Candidate address must be >10 chars to trigger address_match."""
        records = [{'address': 'Москва', 'source': 'api'}]
        check = MockCheck(
            business_records=records,
            registered_address='Москва',  # only 6 chars
        )
        flags = scorer._analyze_business(check)
        assert not any(f['code'] == 'address_match' for f in flags)

    def test_empty_business_records_no_flags(self, scorer):
        """Empty list should produce no flags."""
        check = MockCheck(business_records=[])
        flags = scorer._analyze_business(check)
        assert len(flags) == 0

    def test_none_business_records_no_flags(self, scorer):
        """None should produce no flags."""
        check = MockCheck(business_records=None)
        flags = scorer._analyze_business(check)
        assert len(flags) == 0

    def test_records_with_none_role(self, scorer):
        """Records with role=None should not crash."""
        records = [{'role': None, 'source': 'api'} for _ in range(5)]
        check = MockCheck(business_records=records)
        flags = scorer._analyze_business(check)
        assert not any(f['code'] == 'mass_director' for f in flags)

    def test_records_with_missing_role_key(self, scorer):
        """Records missing 'role' key entirely should not crash."""
        records = [{'source': 'api'} for _ in range(5)]
        check = MockCheck(business_records=records)
        flags = scorer._analyze_business(check)
        assert not any(f['code'] == 'mass_director' for f in flags)


# =========================================================================
#  Court Edge Cases
# =========================================================================

class TestCourtEdgeCases:
    @pytest.fixture
    def scorer(self):
        return RiskScorer()

    def test_criminal_article_159_detected(self, scorer):
        """Article 159 (мошенничество) triggers criminal_case."""
        records = [{'article': 'ст. 159 УК РФ', 'source': 'api'}]
        check = MockCheck(court_records=records)
        flags = scorer._analyze_courts(check)
        assert any(f['code'] == 'criminal_case' for f in flags)

    def test_criminal_keyword_uk_rf(self, scorer):
        """'УК РФ' in text triggers criminal_case."""
        records = [{'text': 'Рассмотрено по УК РФ', 'source': 'api'}]
        check = MockCheck(court_records=records)
        flags = scorer._analyze_courts(check)
        assert any(f['code'] == 'criminal_case' for f in flags)

    def test_fraud_keyword_case_insensitive(self, scorer):
        """Fraud keywords checked with .lower()."""
        records = [{'title': 'МОШЕННИЧЕСТВО', 'source': 'api'}]
        check = MockCheck(court_records=records)
        flags = scorer._analyze_courts(check)
        assert any(f['code'] == 'fraud_case' for f in flags)

    def test_many_cases_exactly_5(self, scorer):
        """5 cases triggers many_cases (threshold >=5)."""
        records = [{'category': 'гражданское', 'source': 'api'} for _ in range(5)]
        check = MockCheck(court_records=records)
        flags = scorer._analyze_courts(check)
        assert any(f['code'] == 'many_cases' for f in flags)

    def test_many_cases_exactly_4_no_flag(self, scorer):
        """4 cases does not trigger many_cases."""
        records = [{'category': 'гражданское', 'source': 'api'} for _ in range(4)]
        check = MockCheck(court_records=records)
        flags = scorer._analyze_courts(check)
        assert not any(f['code'] == 'many_cases' for f in flags)

    def test_defendant_cases_exactly_3(self, scorer):
        """3 defendant cases triggers defendant_cases (threshold >=3)."""
        records = [{'role': 'ответчик', 'source': 'api'} for _ in range(3)]
        check = MockCheck(court_records=records)
        flags = scorer._analyze_courts(check)
        assert any(f['code'] == 'defendant_cases' for f in flags)

    def test_defendant_cases_exactly_2_no_flag(self, scorer):
        """2 defendant cases does not trigger."""
        records = [{'role': 'ответчик', 'source': 'api'} for _ in range(2)]
        check = MockCheck(court_records=records)
        flags = scorer._analyze_courts(check)
        assert not any(f['code'] == 'defendant_cases' for f in flags)

    def test_manual_court_records_ignored(self, scorer):
        """Manual source records are filtered out."""
        records = [{'category': 'уголовное', 'text': 'УК РФ', 'source': 'manual'} for _ in range(10)]
        check = MockCheck(court_records=records)
        flags = scorer._analyze_courts(check)
        assert len(flags) == 0

    def test_none_fields_no_crash(self, scorer):
        """Records with None fields should not crash."""
        records = [{'category': None, 'text': None, 'title': None, 'role': None, 'source': 'api'}]
        check = MockCheck(court_records=records)
        flags = scorer._analyze_courts(check)
        # Should just produce no flags, no crash
        assert isinstance(flags, list)


# =========================================================================
#  FSSP Edge Cases
# =========================================================================

class TestFSSPEdgeCases:
    @pytest.fixture
    def scorer(self):
        return RiskScorer()

    def test_debt_exactly_500000_no_large_debt(self, scorer):
        """500,000 exactly should NOT trigger large_debt (threshold is >500k)."""
        records = [{'amount': 500_000, 'is_active': True, 'source': 'api'}]
        check = MockCheck(fssp_records=records)
        flags = scorer._analyze_fssp(check)
        assert not any(f['code'] == 'large_debt' for f in flags)

    def test_debt_500001_triggers_large_debt(self, scorer):
        """500,001 is >500k, should trigger large_debt."""
        records = [{'amount': 500_001, 'is_active': True, 'source': 'api'}]
        check = MockCheck(fssp_records=records)
        flags = scorer._analyze_fssp(check)
        assert any(f['code'] == 'large_debt' for f in flags)

    def test_debt_exactly_100000_no_medium_debt(self, scorer):
        """100,000 exactly should NOT trigger medium_debt (threshold is >100k)."""
        records = [{'amount': 100_000, 'is_active': True, 'source': 'api'}]
        check = MockCheck(fssp_records=records)
        flags = scorer._analyze_fssp(check)
        assert not any(f['code'] == 'medium_debt' for f in flags)

    def test_debt_100001_triggers_medium_debt(self, scorer):
        """100,001 is >100k, should trigger medium_debt."""
        records = [{'amount': 100_001, 'is_active': True, 'source': 'api'}]
        check = MockCheck(fssp_records=records)
        flags = scorer._analyze_fssp(check)
        assert any(f['code'] == 'medium_debt' for f in flags)

    def test_debt_499999_triggers_medium_not_large(self, scorer):
        """499,999 is >100k but <=500k, should trigger medium_debt only."""
        records = [{'amount': 499_999, 'is_active': True, 'source': 'api'}]
        check = MockCheck(fssp_records=records)
        flags = scorer._analyze_fssp(check)
        assert any(f['code'] == 'medium_debt' for f in flags)
        assert not any(f['code'] == 'large_debt' for f in flags)

    def test_large_debt_excludes_medium(self, scorer):
        """When >500k, large_debt fires but medium_debt should NOT (elif)."""
        records = [{'amount': 600_000, 'is_active': True, 'source': 'api'}]
        check = MockCheck(fssp_records=records)
        flags = scorer._analyze_fssp(check)
        assert any(f['code'] == 'large_debt' for f in flags)
        assert not any(f['code'] == 'medium_debt' for f in flags)

    def test_alimony_subject_lowercase(self, scorer):
        """Lowercase 'алименты' triggers alimony_debt."""
        records = [{'subject': 'алименты на содержание', 'source': 'api'}]
        check = MockCheck(fssp_records=records)
        flags = scorer._analyze_fssp(check)
        assert any(f['code'] == 'alimony_debt' for f in flags)

    def test_alimony_subject_uppercase(self, scorer):
        """Uppercase АЛИМЕНТЫ should also trigger (case-insensitive via .lower())."""
        records = [{'subject': 'АЛИМЕНТЫ', 'source': 'api'}]
        check = MockCheck(fssp_records=records)
        flags = scorer._analyze_fssp(check)
        assert any(f['code'] == 'alimony_debt' for f in flags)

    def test_alimony_mixed_case(self, scorer):
        """Mixed case 'Алименты' should also trigger."""
        records = [{'subject': 'Взыскание Алиментов', 'source': 'api'}]
        check = MockCheck(fssp_records=records)
        flags = scorer._analyze_fssp(check)
        assert any(f['code'] == 'alimony_debt' for f in flags)

    def test_tax_debt_keyword(self, scorer):
        """'налог' in subject triggers tax_debt."""
        records = [{'subject': 'налоговая задолженность', 'source': 'api'}]
        check = MockCheck(fssp_records=records)
        flags = scorer._analyze_fssp(check)
        assert any(f['code'] == 'tax_debt' for f in flags)

    def test_tax_debt_uppercase(self, scorer):
        """Uppercase НАЛОГ should trigger (case-insensitive)."""
        records = [{'subject': 'НАЛОГОВЫЙ СБОР', 'source': 'api'}]
        check = MockCheck(fssp_records=records)
        flags = scorer._analyze_fssp(check)
        assert any(f['code'] == 'tax_debt' for f in flags)

    def test_inactive_debts_not_counted_for_amount(self, scorer):
        """Only active debts should count toward total for debt thresholds."""
        records = [{'amount': 600_000, 'is_active': False, 'source': 'api'}]
        check = MockCheck(fssp_records=records)
        flags = scorer._analyze_fssp(check)
        assert not any(f['code'] == 'large_debt' for f in flags)
        assert not any(f['code'] == 'active_debts' for f in flags)

    def test_multiple_active_threshold_3(self, scorer):
        """3 active debts should trigger multiple_active (threshold >=3)."""
        records = [
            {'amount': 10_000, 'is_active': True, 'source': 'api'},
            {'amount': 10_000, 'is_active': True, 'source': 'api'},
            {'amount': 10_000, 'is_active': True, 'source': 'api'},
        ]
        check = MockCheck(fssp_records=records)
        flags = scorer._analyze_fssp(check)
        assert any(f['code'] == 'multiple_active' for f in flags)

    def test_two_active_no_multiple(self, scorer):
        """2 active debts does not trigger multiple_active."""
        records = [
            {'amount': 10_000, 'is_active': True, 'source': 'api'},
            {'amount': 10_000, 'is_active': True, 'source': 'api'},
        ]
        check = MockCheck(fssp_records=records)
        flags = scorer._analyze_fssp(check)
        assert not any(f['code'] == 'multiple_active' for f in flags)

    def test_one_active_triggers_active_debts(self, scorer):
        """Even 1 active debt triggers active_debts flag."""
        records = [{'amount': 5_000, 'is_active': True, 'source': 'api'}]
        check = MockCheck(fssp_records=records)
        flags = scorer._analyze_fssp(check)
        assert any(f['code'] == 'active_debts' for f in flags)

    def test_no_active_debts_no_flag(self, scorer):
        """All inactive debts should not trigger active_debts."""
        records = [
            {'amount': 100_000, 'is_active': False, 'source': 'api'},
            {'amount': 200_000, 'is_active': False, 'source': 'api'},
        ]
        check = MockCheck(fssp_records=records)
        flags = scorer._analyze_fssp(check)
        assert not any(f['code'] == 'active_debts' for f in flags)

    def test_none_amount_treated_as_zero(self, scorer):
        """None amount should be treated as 0 (via `or 0`)."""
        records = [
            {'amount': None, 'is_active': True, 'source': 'api'},
            {'amount': None, 'is_active': True, 'source': 'api'},
            {'amount': None, 'is_active': True, 'source': 'api'},
        ]
        check = MockCheck(fssp_records=records)
        flags = scorer._analyze_fssp(check)
        # Should have active_debts and multiple_active but NOT large/medium debt
        assert any(f['code'] == 'active_debts' for f in flags)
        assert any(f['code'] == 'multiple_active' for f in flags)
        assert not any(f['code'] == 'large_debt' for f in flags)
        assert not any(f['code'] == 'medium_debt' for f in flags)

    def test_manual_fssp_records_ignored(self, scorer):
        """Manual source records are filtered out."""
        records = [{'amount': 999_999, 'is_active': True, 'source': 'manual'}]
        check = MockCheck(fssp_records=records)
        flags = scorer._analyze_fssp(check)
        assert len(flags) == 0

    def test_none_subject_no_crash(self, scorer):
        """None subject should not crash alimony/tax check."""
        records = [{'subject': None, 'source': 'api'}]
        check = MockCheck(fssp_records=records)
        flags = scorer._analyze_fssp(check)
        assert not any(f['code'] == 'alimony_debt' for f in flags)
        assert not any(f['code'] == 'tax_debt' for f in flags)

    def test_cumulative_debt_across_records(self, scorer):
        """Multiple active debts should sum for threshold checks."""
        records = [
            {'amount': 200_000, 'is_active': True, 'source': 'api'},
            {'amount': 200_000, 'is_active': True, 'source': 'api'},
            {'amount': 200_000, 'is_active': True, 'source': 'api'},
        ]
        check = MockCheck(fssp_records=records)
        flags = scorer._analyze_fssp(check)
        # Total = 600k > 500k
        assert any(f['code'] == 'large_debt' for f in flags)


# =========================================================================
#  Bankruptcy Edge Cases
# =========================================================================

class TestBankruptcyEdgeCases:
    @pytest.fixture
    def scorer(self):
        return RiskScorer()

    def test_active_bankruptcy_flag(self, scorer):
        """Active bankruptcy triggers active_bankruptcy (HIGH)."""
        records = [{'is_active': True, 'source': 'api'}]
        check = MockCheck(bankruptcy_records=records)
        flags = scorer._analyze_bankruptcy(check)
        assert any(f['code'] == 'active_bankruptcy' for f in flags)
        assert any(f['severity'] == 'high' for f in flags if f['code'] == 'active_bankruptcy')

    def test_recent_bankruptcy_within_3_years(self, scorer):
        """Completed 1 year ago -- should trigger recent_bankruptcy."""
        one_year_ago = date.today() - timedelta(days=365)
        records = [{
            'stage': 'завершено',
            'publication_date': one_year_ago.strftime('%d.%m.%Y'),
            'source': 'api',
        }]
        check = MockCheck(bankruptcy_records=records)
        flags = scorer._analyze_bankruptcy(check)
        assert any(f['code'] == 'recent_bankruptcy' for f in flags)

    def test_old_bankruptcy_no_flag(self, scorer):
        """Completed 4 years ago -- should NOT trigger recent_bankruptcy."""
        four_years_ago = date.today() - timedelta(days=4 * 365)
        records = [{
            'stage': 'завершено',
            'publication_date': four_years_ago.strftime('%d.%m.%Y'),
            'source': 'api',
        }]
        check = MockCheck(bankruptcy_records=records)
        flags = scorer._analyze_bankruptcy(check)
        assert not any(f['code'] == 'recent_bankruptcy' for f in flags)

    def test_bankruptcy_exactly_3_years_no_flag(self, scorer):
        """Just over 3 years ago -- threshold is < 3 so should NOT trigger.
        Code uses years_ago = days / 365.25, so 1096 days = 3.0006 years >= 3."""
        # 1096 / 365.25 = 3.0006... which is >= 3, so NOT recent
        over_3_years_ago = date.today() - timedelta(days=1096)
        records = [{
            'stage': 'завершено',
            'publication_date': over_3_years_ago.strftime('%d.%m.%Y'),
            'source': 'api',
        }]
        check = MockCheck(bankruptcy_records=records)
        flags = scorer._analyze_bankruptcy(check)
        assert not any(f['code'] == 'recent_bankruptcy' for f in flags)

    def test_bankruptcy_just_under_3_years(self, scorer):
        """Just under 3 years ago -- should trigger recent_bankruptcy."""
        just_under = date.today() - timedelta(days=int(3 * 365.25) - 10)
        records = [{
            'stage': 'завершено',
            'publication_date': just_under.strftime('%d.%m.%Y'),
            'source': 'api',
        }]
        check = MockCheck(bankruptcy_records=records)
        flags = scorer._analyze_bankruptcy(check)
        assert any(f['code'] == 'recent_bankruptcy' for f in flags)

    def test_stage_prekrashcheno_triggers_recent(self, scorer):
        """'прекращено' stage also counts as completed."""
        one_year_ago = date.today() - timedelta(days=365)
        records = [{
            'stage': 'Дело прекращено',
            'publication_date': one_year_ago.strftime('%d.%m.%Y'),
            'source': 'api',
        }]
        check = MockCheck(bankruptcy_records=records)
        flags = scorer._analyze_bankruptcy(check)
        assert any(f['code'] == 'recent_bankruptcy' for f in flags)

    def test_manual_bankruptcy_records_ignored(self, scorer):
        """Manual source records are filtered out."""
        records = [{'is_active': True, 'source': 'manual'}]
        check = MockCheck(bankruptcy_records=records)
        flags = scorer._analyze_bankruptcy(check)
        assert len(flags) == 0

    def test_no_publication_date_no_recent_flag(self, scorer):
        """Completed bankruptcy without date should not trigger recent."""
        records = [{
            'stage': 'завершено',
            'publication_date': '',
            'source': 'api',
        }]
        check = MockCheck(bankruptcy_records=records)
        flags = scorer._analyze_bankruptcy(check)
        assert not any(f['code'] == 'recent_bankruptcy' for f in flags)

    def test_invalid_date_format_no_crash(self, scorer):
        """Invalid date format should not crash, just skip."""
        records = [{
            'stage': 'завершено',
            'publication_date': 'not-a-date',
            'source': 'api',
        }]
        check = MockCheck(bankruptcy_records=records)
        flags = scorer._analyze_bankruptcy(check)
        assert not any(f['code'] == 'recent_bankruptcy' for f in flags)


# =========================================================================
#  Sanctions Edge Cases
# =========================================================================

class TestSanctionsEdgeCases:
    @pytest.fixture
    def scorer(self):
        return RiskScorer()

    def test_one_found_is_critical(self, scorer):
        """A single sanctions match should produce a CRITICAL flag."""
        results = [
            {'checked': True, 'found': True, 'source_name': 'SDN List'},
            {'checked': False, 'found': False, 'source_name': 'EU List'},
        ]
        check = MockCheck(sanctions_results=results)
        flags = scorer._analyze_sanctions(check)
        assert any(f['severity'] == 'critical' for f in flags)
        assert any(f['code'] == 'sanctions_match' for f in flags)

    def test_all_unchecked_triggers_warning(self, scorer):
        """3 unchecked sources (>=2) triggers sanctions_unchecked."""
        results = [
            {'checked': False, 'found': False, 'source_name': 'SDN List'},
            {'checked': False, 'found': False, 'source_name': 'EU List'},
            {'checked': False, 'found': False, 'source_name': 'UN List'},
        ]
        check = MockCheck(sanctions_results=results)
        flags = scorer._analyze_sanctions(check)
        assert any(f['code'] == 'sanctions_unchecked' for f in flags)

    def test_two_unchecked_triggers_warning(self, scorer):
        """Exactly 2 unchecked (>=2 threshold) triggers sanctions_unchecked."""
        results = [
            {'checked': True, 'found': False, 'source_name': 'SDN List'},
            {'checked': False, 'found': False, 'source_name': 'EU List'},
            {'checked': False, 'found': False, 'source_name': 'UN List'},
        ]
        check = MockCheck(sanctions_results=results)
        flags = scorer._analyze_sanctions(check)
        assert any(f['code'] == 'sanctions_unchecked' for f in flags)

    def test_one_unchecked_no_warning(self, scorer):
        """Only 1 unchecked should NOT trigger (threshold is >=2)."""
        results = [
            {'checked': True, 'found': False, 'source_name': 'SDN List'},
            {'checked': False, 'found': False, 'source_name': 'EU List'},
        ]
        check = MockCheck(sanctions_results=results)
        flags = scorer._analyze_sanctions(check)
        assert not any(f['code'] == 'sanctions_unchecked' for f in flags)

    def test_dict_format_sanctions(self, scorer):
        """Sanctions can come as a dict of dicts (keyed by source)."""
        results = {
            'sdn': {'checked': True, 'found': True, 'source_name': 'SDN'},
            'eu': {'checked': True, 'found': False, 'source_name': 'EU'},
        }
        check = MockCheck(sanctions_results=results)
        flags = scorer._analyze_sanctions(check)
        assert any(f['severity'] == 'critical' for f in flags)

    def test_dict_format_unchecked(self, scorer):
        """Dict format with unchecked sources."""
        results = {
            'sdn': {'checked': False, 'found': False, 'source_name': 'SDN'},
            'eu': {'checked': False, 'found': False, 'source_name': 'EU'},
        }
        check = MockCheck(sanctions_results=results)
        flags = scorer._analyze_sanctions(check)
        assert any(f['code'] == 'sanctions_unchecked' for f in flags)

    def test_empty_list_no_flags(self, scorer):
        """Empty list should produce no flags."""
        check = MockCheck(sanctions_results=[])
        flags = scorer._analyze_sanctions(check)
        assert len(flags) == 0

    def test_none_sanctions_no_flags(self, scorer):
        """None should produce no flags."""
        check = MockCheck(sanctions_results=None)
        flags = scorer._analyze_sanctions(check)
        assert len(flags) == 0

    def test_multiple_sanctions_matches(self, scorer):
        """Multiple found sanctions should each produce a flag."""
        results = [
            {'checked': True, 'found': True, 'source_name': 'SDN'},
            {'checked': True, 'found': True, 'source_name': 'EU'},
        ]
        check = MockCheck(sanctions_results=results)
        flags = scorer._analyze_sanctions(check)
        match_flags = [f for f in flags if f['code'] == 'sanctions_match']
        assert len(match_flags) == 2


# =========================================================================
#  Social Media Edge Cases
# =========================================================================

class TestSocialEdgeCases:
    @pytest.fixture
    def scorer(self):
        return RiskScorer()

    def test_no_profiles_triggers_flag(self, scorer):
        """No social profiles triggers no_social_presence."""
        check = MockCheck(social_media_profiles=[])
        flags = scorer._analyze_social(check)
        assert any(f['code'] == 'no_social_presence' for f in flags)

    def test_none_profiles_triggers_flag(self, scorer):
        """None profiles triggers no_social_presence."""
        check = MockCheck(social_media_profiles=None)
        flags = scorer._analyze_social(check)
        assert any(f['code'] == 'no_social_presence' for f in flags)

    def test_one_profile_no_flag(self, scorer):
        """At least one profile means no no_social_presence flag."""
        check = MockCheck(social_media_profiles=[{'platform': 'vk'}])
        flags = scorer._analyze_social(check)
        assert not any(f['code'] == 'no_social_presence' for f in flags)


# =========================================================================
#  Risk Level Calculation
# =========================================================================

class TestRiskLevelCalculation:
    @pytest.fixture
    def scorer(self):
        return RiskScorer()

    def test_no_flags_clean(self, scorer):
        assert scorer._calculate_risk_level([]) == 'clean'

    def test_one_medium_is_low(self, scorer):
        flags = [{'severity': 'medium'}]
        assert scorer._calculate_risk_level(flags) == 'low'

    def test_two_medium_is_low(self, scorer):
        flags = [{'severity': 'medium'}, {'severity': 'medium'}]
        assert scorer._calculate_risk_level(flags) == 'low'

    def test_three_medium_is_medium(self, scorer):
        flags = [{'severity': 'medium'}] * 3
        assert scorer._calculate_risk_level(flags) == 'medium'

    def test_four_medium_is_medium(self, scorer):
        """4 medium -- still medium (would need high flags for 'high')."""
        flags = [{'severity': 'medium'}] * 4
        assert scorer._calculate_risk_level(flags) == 'medium'

    def test_one_high_is_medium(self, scorer):
        flags = [{'severity': 'high'}]
        assert scorer._calculate_risk_level(flags) == 'medium'

    def test_one_high_one_medium_is_medium(self, scorer):
        flags = [{'severity': 'high'}, {'severity': 'medium'}]
        assert scorer._calculate_risk_level(flags) == 'medium'

    def test_one_high_two_medium_is_high(self, scorer):
        """high>=1 AND medium>=2 triggers 'high'."""
        flags = [{'severity': 'high'}, {'severity': 'medium'}, {'severity': 'medium'}]
        assert scorer._calculate_risk_level(flags) == 'high'

    def test_two_high_is_high(self, scorer):
        """high>=2 triggers 'high'."""
        flags = [{'severity': 'high'}, {'severity': 'high'}]
        assert scorer._calculate_risk_level(flags) == 'high'

    def test_two_high_one_medium_is_high(self, scorer):
        flags = [{'severity': 'high'}, {'severity': 'high'}, {'severity': 'medium'}]
        assert scorer._calculate_risk_level(flags) == 'high'

    def test_critical_always_critical(self, scorer):
        flags = [{'severity': 'critical'}]
        assert scorer._calculate_risk_level(flags) == 'critical'

    def test_critical_with_others(self, scorer):
        flags = [{'severity': 'critical'}, {'severity': 'high'}, {'severity': 'medium'}]
        assert scorer._calculate_risk_level(flags) == 'critical'

    def test_low_severity_ignored_for_level(self, scorer):
        """Low severity flags should NOT affect risk level calculation."""
        flags = [{'severity': 'low'}, {'severity': 'low'}, {'severity': 'low'}]
        assert scorer._calculate_risk_level(flags) == 'clean'

    def test_low_with_medium_still_low(self, scorer):
        """Low flags don't add to medium count."""
        flags = [{'severity': 'low'}, {'severity': 'medium'}]
        assert scorer._calculate_risk_level(flags) == 'low'

    def test_many_low_still_clean(self, scorer):
        """Even 10 low severity flags should produce 'clean'."""
        flags = [{'severity': 'low'}] * 10
        assert scorer._calculate_risk_level(flags) == 'clean'


# =========================================================================
#  Full analyze() Integration
# =========================================================================

class TestFullAnalyze:
    @pytest.fixture
    def scorer(self):
        return RiskScorer()

    def test_empty_check_with_social_is_clean(self, scorer):
        """Empty check with just social profiles should be clean."""
        check = MockCheck(social_media_profiles=[{'platform': 'vk'}])
        level, flags = scorer.analyze(check)
        assert level == 'clean'
        assert flags == []

    def test_completely_empty_check(self, scorer):
        """Completely empty check should have no_social_presence flag -> low."""
        check = MockCheck()
        level, flags = scorer.analyze(check)
        assert any(f['code'] == 'no_social_presence' for f in flags)
        assert level == 'low'  # one medium flag -> low

    def test_flags_sorted_by_severity(self, scorer):
        """Red flags should be sorted critical > high > medium > low."""
        check = MockCheck(
            fssp_records=[
                {'amount': 600_000, 'is_active': True, 'source': 'api'},
                {'amount': 10_000, 'is_active': True, 'source': 'api'},
                {'amount': 10_000, 'is_active': True, 'source': 'api'},
            ],
            sanctions_results=[
                {'checked': True, 'found': True, 'source_name': 'SDN'},
            ],
        )
        level, flags = scorer.analyze(check)
        severities = [f['severity'] for f in flags]
        severity_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
        for i in range(len(severities) - 1):
            assert severity_order.get(severities[i], 99) <= severity_order.get(severities[i + 1], 99)

    def test_analyze_returns_tuple(self, scorer):
        """analyze() must return a (str, list) tuple."""
        check = MockCheck(social_media_profiles=[{'platform': 'vk'}])
        result = scorer.analyze(check)
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], str)
        assert isinstance(result[1], list)

    def test_risk_level_valid_values(self, scorer):
        """Risk level must be one of the defined values."""
        valid_levels = {'clean', 'low', 'medium', 'high', 'critical'}
        check = MockCheck(social_media_profiles=[{'platform': 'vk'}])
        level, _ = scorer.analyze(check)
        assert level in valid_levels

    def test_flag_structure(self, scorer):
        """Each flag must have severity, category, code, text keys."""
        check = MockCheck()  # triggers no_social_presence
        _, flags = scorer.analyze(check)
        assert len(flags) > 0
        for flag in flags:
            assert 'severity' in flag
            assert 'category' in flag
            assert 'code' in flag
            assert 'text' in flag

    def test_combined_business_and_fssp(self, scorer):
        """Multiple categories can produce flags simultaneously."""
        check = MockCheck(
            business_records=[
                {'role': 'директор', 'source': 'api'} for _ in range(6)
            ],
            fssp_records=[
                {'amount': 600_000, 'is_active': True, 'source': 'api'},
            ],
            social_media_profiles=[{'platform': 'vk'}],
        )
        level, flags = scorer.analyze(check)
        categories = {f['category'] for f in flags}
        assert 'business' in categories
        assert 'fssp' in categories

    def test_all_none_fields_no_crash(self, scorer):
        """Check with all None fields should not crash."""
        check = MockCheck(
            business_records=None,
            court_records=None,
            fssp_records=None,
            bankruptcy_records=None,
            sanctions_results=None,
            social_media_profiles=None,
        )
        level, flags = scorer.analyze(check)
        assert isinstance(level, str)
        assert isinstance(flags, list)
