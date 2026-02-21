"""
Pipeline Error Resilience Tests
================================
Tests proving the candidate pipeline handles individual stage failures gracefully.
Focus on RiskScorer resilience, CandidateTaskStatus, cleanup, and
ThreadPoolExecutor exception handling patterns used by the pipeline.
"""

import pytest
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

os.environ.setdefault('SECRET_KEY', 'test-secret-key')

from app.services.candidate.risk_scorer import RiskScorer
from app.services.candidate.pipeline import CandidateTaskStatus, cleanup_old_tasks


class MockCheck:
    """Mock CandidateCheck for testing RiskScorer with arbitrary field values."""

    def __init__(self, **kwargs):
        self.business_records = kwargs.get('business_records')
        self.court_records = kwargs.get('court_records')
        self.fssp_records = kwargs.get('fssp_records')
        self.bankruptcy_records = kwargs.get('bankruptcy_records')
        self.sanctions_results = kwargs.get('sanctions_results')
        self.social_media_profiles = kwargs.get('social_media_profiles')
        self.registered_address = kwargs.get('registered_address', '')


# ══════════════════════════════════════════════════════════════════════
# RISK SCORER RESILIENCE
# ══════════════════════════════════════════════════════════════════════

class TestRiskScorerResilience:
    """Test that RiskScorer handles all kinds of bad/missing data without crashing."""

    @pytest.fixture
    def scorer(self):
        return RiskScorer()

    def test_all_none_fields(self, scorer):
        """All fields None -- should return a valid level, no crash."""
        check = MockCheck()
        level, flags = scorer.analyze(check)
        assert isinstance(level, str)
        assert isinstance(flags, list)

    def test_business_records_none(self, scorer):
        check = MockCheck(business_records=None)
        flags = scorer._analyze_business(check)
        assert flags == []

    def test_business_records_empty(self, scorer):
        check = MockCheck(business_records=[])
        flags = scorer._analyze_business(check)
        assert flags == []

    def test_court_records_none(self, scorer):
        check = MockCheck(court_records=None)
        flags = scorer._analyze_courts(check)
        assert flags == []

    def test_court_records_empty(self, scorer):
        check = MockCheck(court_records=[])
        flags = scorer._analyze_courts(check)
        assert flags == []

    def test_fssp_records_none(self, scorer):
        check = MockCheck(fssp_records=None)
        flags = scorer._analyze_fssp(check)
        assert flags == []

    def test_fssp_records_empty(self, scorer):
        check = MockCheck(fssp_records=[])
        flags = scorer._analyze_fssp(check)
        assert flags == []

    def test_bankruptcy_records_none(self, scorer):
        check = MockCheck(bankruptcy_records=None)
        flags = scorer._analyze_bankruptcy(check)
        assert flags == []

    def test_bankruptcy_records_empty(self, scorer):
        check = MockCheck(bankruptcy_records=[])
        flags = scorer._analyze_bankruptcy(check)
        assert flags == []

    def test_sanctions_results_none(self, scorer):
        check = MockCheck(sanctions_results=None)
        flags = scorer._analyze_sanctions(check)
        assert flags == []

    def test_sanctions_results_empty_dict(self, scorer):
        check = MockCheck(sanctions_results={})
        flags = scorer._analyze_sanctions(check)
        assert flags == []

    def test_sanctions_results_empty_list(self, scorer):
        check = MockCheck(sanctions_results=[])
        flags = scorer._analyze_sanctions(check)
        assert flags == []


class TestRiskScorerBadRecordFields:
    """Test RiskScorer with records that have missing or None sub-fields."""

    @pytest.fixture
    def scorer(self):
        return RiskScorer()

    def test_business_record_missing_all_fields(self, scorer):
        """A record with only 'source' -- no role, status, address, etc."""
        records = [{'source': 'api'}]
        check = MockCheck(business_records=records)
        flags = scorer._analyze_business(check)
        assert isinstance(flags, list)

    def test_business_record_none_role(self, scorer):
        """Role field explicitly set to None."""
        records = [{'role': None, 'status': None, 'source': 'nalog'}]
        check = MockCheck(business_records=records)
        flags = scorer._analyze_business(check)
        assert isinstance(flags, list)

    def test_business_record_none_status(self, scorer):
        records = [{'role': 'директор', 'status': None, 'source': 'nalog'}]
        check = MockCheck(business_records=records)
        flags = scorer._analyze_business(check)
        assert isinstance(flags, list)

    def test_business_record_none_address(self, scorer):
        records = [{'address': None, 'source': 'nalog'}]
        check = MockCheck(business_records=records)
        flags = scorer._analyze_business(check)
        assert isinstance(flags, list)

    def test_business_record_none_end_date(self, scorer):
        """end_date is None -- should not crash date parsing."""
        records = [{'status': 'ликвидирована', 'end_date': None, 'source': 'nalog'}]
        check = MockCheck(business_records=records)
        flags = scorer._analyze_business(check)
        assert isinstance(flags, list)

    def test_court_record_missing_all_text_fields(self, scorer):
        """Court record with no category, article, text, or title."""
        records = [{'source': 'api'}]
        check = MockCheck(court_records=records)
        flags = scorer._analyze_courts(check)
        assert isinstance(flags, list)

    def test_court_record_none_text_fields(self, scorer):
        """All text fields explicitly None."""
        records = [{'category': None, 'article': None, 'text': None, 'title': None, 'source': 'api'}]
        check = MockCheck(court_records=records)
        flags = scorer._analyze_courts(check)
        assert isinstance(flags, list)

    def test_court_record_none_role(self, scorer):
        """Role field is None."""
        records = [{'role': None, 'source': 'api'}]
        check = MockCheck(court_records=records)
        flags = scorer._analyze_courts(check)
        assert isinstance(flags, list)

    def test_fssp_record_missing_amount(self, scorer):
        """FSSP record without amount field."""
        records = [{'is_active': True, 'source': 'api'}]
        check = MockCheck(fssp_records=records)
        flags = scorer._analyze_fssp(check)
        assert isinstance(flags, list)

    def test_fssp_record_none_amount(self, scorer):
        """FSSP record with None amount."""
        records = [{'amount': None, 'is_active': True, 'source': 'api'}]
        check = MockCheck(fssp_records=records)
        flags = scorer._analyze_fssp(check)
        assert isinstance(flags, list)

    def test_fssp_record_string_amount(self, scorer):
        """FSSP record with string amount -- should not crash sum()."""
        records = [{'amount': '50000', 'is_active': True, 'source': 'api'}]
        check = MockCheck(fssp_records=records)
        flags = scorer._analyze_fssp(check)
        assert isinstance(flags, list)

    def test_fssp_record_none_subject(self, scorer):
        """FSSP record with None subject."""
        records = [{'subject': None, 'source': 'api'}]
        check = MockCheck(fssp_records=records)
        flags = scorer._analyze_fssp(check)
        assert isinstance(flags, list)

    def test_fssp_record_missing_subject(self, scorer):
        """FSSP record with no subject key at all."""
        records = [{'source': 'api', 'is_active': False}]
        check = MockCheck(fssp_records=records)
        flags = scorer._analyze_fssp(check)
        assert isinstance(flags, list)

    def test_bankruptcy_record_missing_stage(self, scorer):
        """Bankruptcy record without stage field."""
        records = [{'source': 'api'}]
        check = MockCheck(bankruptcy_records=records)
        flags = scorer._analyze_bankruptcy(check)
        assert isinstance(flags, list)

    def test_bankruptcy_record_none_stage(self, scorer):
        """Bankruptcy record with None stage."""
        records = [{'stage': None, 'source': 'api'}]
        check = MockCheck(bankruptcy_records=records)
        flags = scorer._analyze_bankruptcy(check)
        assert isinstance(flags, list)

    def test_bankruptcy_record_none_publication_date(self, scorer):
        records = [{'stage': 'завершено', 'publication_date': None, 'source': 'api'}]
        check = MockCheck(bankruptcy_records=records)
        flags = scorer._analyze_bankruptcy(check)
        assert isinstance(flags, list)

    def test_bankruptcy_record_invalid_date(self, scorer):
        """Non-date string in publication_date -- should handle gracefully."""
        records = [{'stage': 'завершено', 'publication_date': 'not-a-date', 'source': 'api'}]
        check = MockCheck(bankruptcy_records=records)
        flags = scorer._analyze_bankruptcy(check)
        assert isinstance(flags, list)

    def test_bankruptcy_record_integer_date(self, scorer):
        """Integer publication_date -- should not crash."""
        records = [{'stage': 'завершено', 'publication_date': 20250101, 'source': 'api'}]
        check = MockCheck(bankruptcy_records=records)
        flags = scorer._analyze_bankruptcy(check)
        assert isinstance(flags, list)


class TestRiskScorerSanctionsEdgeCases:
    """Test sanctions analysis with unusual data shapes."""

    @pytest.fixture
    def scorer(self):
        return RiskScorer()

    def test_sanctions_non_dict_items(self, scorer):
        """Sanctions list with non-dict items -- isinstance check should skip them."""
        results = ['some string', 123, None]
        check = MockCheck(sanctions_results=results)
        flags = scorer._analyze_sanctions(check)
        assert isinstance(flags, list)

    def test_sanctions_mixed_dict_and_non_dict(self, scorer):
        """Mix of valid dicts and non-dicts."""
        results = [
            {'source_name': 'SDN', 'checked': True, 'found': False},
            'invalid entry',
            None,
            {'source_name': 'EU', 'checked': True, 'found': True, 'match_details': 'Match'},
        ]
        check = MockCheck(sanctions_results=results)
        flags = scorer._analyze_sanctions(check)
        assert any(f['code'] == 'sanctions_match' for f in flags)

    def test_sanctions_dict_missing_checked_field(self, scorer):
        """Dict without 'checked' key."""
        results = [{'source_name': 'SDN'}]
        check = MockCheck(sanctions_results=results)
        flags = scorer._analyze_sanctions(check)
        assert isinstance(flags, list)

    def test_sanctions_dict_missing_found_field(self, scorer):
        """Dict with 'checked' but no 'found' key."""
        results = [{'source_name': 'SDN', 'checked': True}]
        check = MockCheck(sanctions_results=results)
        flags = scorer._analyze_sanctions(check)
        assert isinstance(flags, list)

    def test_sanctions_as_nested_dict(self, scorer):
        """Sanctions results as dict-of-dicts (keyed by source name)."""
        results = {
            'sdn': {'source_name': 'SDN', 'checked': True, 'found': True, 'match_details': 'Match'},
            'eu': {'source_name': 'EU', 'checked': True, 'found': False},
        }
        check = MockCheck(sanctions_results=results)
        flags = scorer._analyze_sanctions(check)
        assert any(f['code'] == 'sanctions_match' for f in flags)

    def test_sanctions_integer_type(self, scorer):
        """Sanctions results is an integer -- should return empty."""
        check = MockCheck(sanctions_results=42)
        flags = scorer._analyze_sanctions(check)
        assert flags == []


class TestRiskScorerSocialEdgeCases:
    """Test social media analysis edge cases."""

    @pytest.fixture
    def scorer(self):
        return RiskScorer()

    def test_social_media_profiles_none(self, scorer):
        """None social profiles -- should trigger no_social_presence."""
        check = MockCheck(social_media_profiles=None)
        flags = scorer._analyze_social(check)
        assert any(f['code'] == 'no_social_presence' for f in flags)

    def test_social_media_profiles_empty(self, scorer):
        """Empty list -- should trigger no_social_presence."""
        check = MockCheck(social_media_profiles=[])
        flags = scorer._analyze_social(check)
        assert any(f['code'] == 'no_social_presence' for f in flags)

    def test_social_media_profiles_present(self, scorer):
        """With profiles -- no_social_presence should NOT appear."""
        check = MockCheck(social_media_profiles=[{'platform': 'vk'}])
        flags = scorer._analyze_social(check)
        assert not any(f['code'] == 'no_social_presence' for f in flags)


class TestRiskScorerAnalyzeFullPath:
    """Test full analyze() call with combinations of bad data."""

    @pytest.fixture
    def scorer(self):
        return RiskScorer()

    def test_all_empty_lists(self, scorer):
        """All record fields are empty lists -- clean except social."""
        check = MockCheck(
            business_records=[],
            court_records=[],
            fssp_records=[],
            bankruptcy_records=[],
            sanctions_results=[],
            social_media_profiles=[],
        )
        level, flags = scorer.analyze(check)
        assert level in ('clean', 'low', 'medium', 'high', 'critical')
        assert isinstance(flags, list)

    def test_all_manual_source_records(self, scorer):
        """All records are manual source -- should be filtered out."""
        check = MockCheck(
            business_records=[{'source': 'manual'}] * 10,
            court_records=[{'source': 'manual'}] * 10,
            fssp_records=[{'source': 'manual'}] * 10,
            bankruptcy_records=[{'source': 'manual'}] * 10,
            sanctions_results=[],
            social_media_profiles=[{'platform': 'vk'}],
        )
        level, flags = scorer.analyze(check)
        assert level == 'clean'

    def test_mixed_none_and_valid(self, scorer):
        """Some fields None, some valid -- should not crash."""
        check = MockCheck(
            business_records=None,
            court_records=[{'category': 'civil', 'source': 'api'}],
            fssp_records=None,
            bankruptcy_records=[],
            sanctions_results={'sdn': {'checked': True, 'found': False, 'source_name': 'SDN'}},
            social_media_profiles=[{'platform': 'telegram'}],
        )
        level, flags = scorer.analyze(check)
        assert isinstance(level, str)
        assert isinstance(flags, list)

    def test_red_flags_sorted_by_severity(self, scorer):
        """Verify flags are returned sorted critical > high > medium > low."""
        check = MockCheck(
            business_records=[
                {'name': f'C{i}', 'role': 'директор', 'status': 'действующая', 'source': 'n'}
                for i in range(6)
            ],
            court_records=[
                {'category': 'уголовное', 'text': 'ст. 159 УК РФ мошенничество', 'source': 'api'}
            ],
            fssp_records=[
                {'amount': 600000, 'is_active': True, 'source': 'api'},
                {'amount': 100000, 'is_active': True, 'source': 'api'},
                {'amount': 50000, 'is_active': True, 'source': 'api'},
            ],
            sanctions_results=[
                {'source_name': 'SDN', 'checked': True, 'found': True, 'match_details': 'match'},
            ],
            social_media_profiles=[{'platform': 'vk'}],
        )
        level, flags = scorer.analyze(check)
        assert level == 'critical'
        severities = [f['severity'] for f in flags]
        severity_rank = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
        ranks = [severity_rank.get(s, 99) for s in severities]
        assert ranks == sorted(ranks), f"Flags not sorted by severity: {severities}"


# ══════════════════════════════════════════════════════════════════════
# CANDIDATE TASK STATUS
# ══════════════════════════════════════════════════════════════════════

class TestCandidateTaskStatus:
    """Test CandidateTaskStatus tracking object."""

    def test_create_task(self):
        task = CandidateTaskStatus('task-1', 'check-1', 'Иванов Иван')
        assert task.task_id == 'task-1'
        assert task.check_id == 'check-1'
        assert task.full_name == 'Иванов Иван'
        assert task.current_stage == 'initializing'
        assert task.percent_complete == 0
        assert task.completed_at is None
        assert task.error is None
        assert task.cancelled is False

    def test_update_task(self):
        task = CandidateTaskStatus('task-1', 'check-1', 'Иванов Иван')
        task.update('gov_registries', 'Checking...', 25)
        assert task.current_stage == 'gov_registries'
        assert task.current_step == 'Checking...'
        assert task.percent_complete == 25

    def test_add_message(self):
        task = CandidateTaskStatus('task-1', 'check-1', 'Иванов Иван')
        task.add_message('Test message', 'info')
        assert len(task.messages) == 1
        assert task.messages[0]['text'] == 'Test message'
        assert task.messages[0]['type'] == 'info'
        assert 'time' in task.messages[0]

    def test_add_message_default_type(self):
        task = CandidateTaskStatus('task-1', 'check-1', 'Test')
        task.add_message('Hello')
        assert task.messages[0]['type'] == 'info'

    def test_update_also_adds_message(self):
        """update() should also add a message with the step text."""
        task = CandidateTaskStatus('task-1', 'check-1', 'Test')
        task.update('stage', 'Step description', 50)
        assert len(task.messages) == 1
        assert task.messages[0]['text'] == 'Step description'

    def test_to_dict_running(self):
        task = CandidateTaskStatus('task-1', 'check-1', 'Иванов Иван')
        d = task.to_dict()
        assert d['status'] == 'running'
        assert d['is_complete'] is False
        assert d['task_id'] == 'task-1'
        assert d['check_id'] == 'check-1'
        assert d['full_name'] == 'Иванов Иван'

    def test_to_dict_complete(self):
        task = CandidateTaskStatus('task-1', 'check-1', 'Иванов Иван')
        task.completed_at = datetime.now()
        d = task.to_dict()
        assert d['status'] == 'complete'
        assert d['is_complete'] is True

    def test_to_dict_error(self):
        task = CandidateTaskStatus('task-1', 'check-1', 'Иванов Иван')
        task.error = 'Something failed'
        d = task.to_dict()
        assert d['status'] == 'error'
        assert d['is_complete'] is True
        assert d['error'] == 'Something failed'

    def test_to_dict_cancelled(self):
        task = CandidateTaskStatus('task-1', 'check-1', 'Иванов Иван')
        task.cancelled = True
        d = task.to_dict()
        assert d['status'] == 'cancelled'
        assert d['is_complete'] is True

    def test_to_dict_error_takes_priority_over_complete(self):
        """If both error and completed_at are set, status should be 'error'."""
        task = CandidateTaskStatus('task-1', 'check-1', 'Test')
        task.error = 'fail'
        task.completed_at = datetime.now()
        d = task.to_dict()
        assert d['status'] == 'error'

    def test_to_dict_error_takes_priority_over_cancelled(self):
        """If both error and cancelled are set, status should be 'error'."""
        task = CandidateTaskStatus('task-1', 'check-1', 'Test')
        task.error = 'fail'
        task.cancelled = True
        d = task.to_dict()
        assert d['status'] == 'error'

    def test_messages_limited_to_last_40(self):
        task = CandidateTaskStatus('task-1', 'check-1', 'Иванов Иван')
        for i in range(60):
            task.add_message(f'Message {i}')
        d = task.to_dict()
        assert len(d['messages']) <= 40
        # Should be the LAST 40 messages
        assert d['messages'][0]['text'] == 'Message 20'
        assert d['messages'][-1]['text'] == 'Message 59'

    def test_started_at_set_on_creation(self):
        before = datetime.now()
        task = CandidateTaskStatus('task-1', 'check-1', 'Test')
        after = datetime.now()
        assert before <= task.started_at <= after


# ══════════════════════════════════════════════════════════════════════
# CLEANUP OLD TASKS
# ══════════════════════════════════════════════════════════════════════

class TestCleanupOldTasks:
    """Test the cleanup_old_tasks utility."""

    def test_cleanup_removes_old_completed(self):
        task = CandidateTaskStatus('old-task', 'check-1', 'Test')
        task.completed_at = datetime.now() - timedelta(seconds=7200)
        store = {'old-task': task}
        cleanup_old_tasks(store, max_age_seconds=3600)
        assert 'old-task' not in store

    def test_cleanup_keeps_recent_completed(self):
        task = CandidateTaskStatus('recent-task', 'check-1', 'Test')
        task.completed_at = datetime.now() - timedelta(seconds=1800)
        store = {'recent-task': task}
        cleanup_old_tasks(store, max_age_seconds=3600)
        assert 'recent-task' in store

    def test_cleanup_keeps_running_tasks(self):
        """Running tasks (completed_at is None) should never be cleaned up."""
        task = CandidateTaskStatus('running-task', 'check-1', 'Test')
        store = {'running-task': task}
        cleanup_old_tasks(store, max_age_seconds=3600)
        assert 'running-task' in store

    def test_cleanup_empty_store(self):
        """Empty store should not crash."""
        store = {}
        cleanup_old_tasks(store, max_age_seconds=3600)
        assert store == {}

    def test_cleanup_mixed_store(self):
        """Mix of old, recent, and running tasks."""
        old = CandidateTaskStatus('old', 'c1', 'Old')
        old.completed_at = datetime.now() - timedelta(seconds=7200)

        recent = CandidateTaskStatus('recent', 'c2', 'Recent')
        recent.completed_at = datetime.now() - timedelta(seconds=100)

        running = CandidateTaskStatus('running', 'c3', 'Running')

        store = {'old': old, 'recent': recent, 'running': running}
        cleanup_old_tasks(store, max_age_seconds=3600)

        assert 'old' not in store
        assert 'recent' in store
        assert 'running' in store


# ══════════════════════════════════════════════════════════════════════
# THREADPOOLEXECUTOR ERROR HANDLING PATTERNS
# ══════════════════════════════════════════════════════════════════════

class TestThreadPoolErrorHandling:
    """
    Test that the ThreadPoolExecutor exception handling patterns used
    by the pipeline work correctly -- one worker crash should not
    affect others.
    """

    def test_one_future_crash_others_complete(self):
        """One worker crashing should not affect others."""
        def good_task():
            return "ok"

        def bad_task():
            raise ConnectionError("Network timeout")

        results = {}
        errors = {}

        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                executor.submit(good_task): 'good1',
                executor.submit(bad_task): 'bad',
                executor.submit(good_task): 'good2',
            }

            for future in as_completed(futures):
                name = futures[future]
                try:
                    results[name] = future.result()
                except Exception as e:
                    errors[name] = str(e)

        assert 'good1' in results
        assert 'good2' in results
        assert results['good1'] == 'ok'
        assert results['good2'] == 'ok'
        assert 'bad' in errors
        assert 'Network timeout' in errors['bad']

    def test_all_futures_crash(self):
        """All workers crashing should be caught -- not propagated."""
        def bad_task(msg):
            raise RuntimeError(msg)

        errors = []
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [
                executor.submit(bad_task, f"error-{i}")
                for i in range(3)
            ]
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    errors.append(str(e))

        assert len(errors) == 3

    def test_timeout_in_as_completed(self):
        """Timeout in as_completed should raise TimeoutError."""
        def slow_task():
            time.sleep(10)
            return "done"

        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(slow_task)
            timed_out = False
            try:
                for f in as_completed([future], timeout=0.1):
                    f.result()
            except TimeoutError:
                timed_out = True

            assert timed_out
            future.cancel()

    def test_exception_types_preserved(self):
        """Verify the exception type is preserved through future.result()."""
        def raise_value_error():
            raise ValueError("bad value")

        def raise_connection_error():
            raise ConnectionError("no network")

        with ThreadPoolExecutor(max_workers=2) as executor:
            f1 = executor.submit(raise_value_error)
            f2 = executor.submit(raise_connection_error)

            for future in as_completed([f1, f2]):
                try:
                    future.result()
                except ValueError as e:
                    assert "bad value" in str(e)
                except ConnectionError as e:
                    assert "no network" in str(e)


# ══════════════════════════════════════════════════════════════════════
# PARSE DATE RESILIENCE
# ══════════════════════════════════════════════════════════════════════

class TestParseDateResilience:
    """Test the _parse_date helper with edge-case inputs."""

    @pytest.fixture
    def scorer(self):
        return RiskScorer()

    def test_none(self, scorer):
        assert scorer._parse_date(None) is None

    def test_empty_string(self, scorer):
        assert scorer._parse_date('') is None

    def test_valid_dd_mm_yyyy(self, scorer):
        result = scorer._parse_date('15.03.2024')
        assert result is not None
        assert result.year == 2024
        assert result.month == 3
        assert result.day == 15

    def test_valid_yyyy_mm_dd(self, scorer):
        result = scorer._parse_date('2024-03-15')
        assert result is not None
        assert result.year == 2024

    def test_invalid_date_string(self, scorer):
        assert scorer._parse_date('not-a-date') is None

    def test_integer_input(self, scorer):
        """Integer input -- _parse_date calls .strip() which needs a string."""
        assert scorer._parse_date(20250101) is None

    def test_float_input(self, scorer):
        assert scorer._parse_date(3.14) is None

    def test_whitespace_string(self, scorer):
        assert scorer._parse_date('   ') is None

    def test_partial_date(self, scorer):
        assert scorer._parse_date('2024-03') is None

    def test_date_with_extra_whitespace(self, scorer):
        """Date with leading/trailing whitespace should still parse."""
        result = scorer._parse_date('  15.03.2024  ')
        assert result is not None
        assert result.year == 2024
