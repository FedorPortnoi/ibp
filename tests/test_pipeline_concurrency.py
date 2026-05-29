"""Pipeline concurrency and active_count gate tests.

Verifies:
1. CandidateTaskStatus.is_complete starts as False.
2. The active_count logic in start_check(): completed tasks do NOT count
   toward the active limit.  The gate fires at exactly 10 active (incomplete)
   tasks, NOT at 10 total tasks.
3. cleanup_old_tasks() removes tasks with completed_at older than max_age.
"""

import datetime
import sys
import os
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault('SECRET_KEY', 'test-secret-key-concurrency')

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope='module')
def app():
    from dotenv import load_dotenv
    load_dotenv()
    from app import create_app
    application = create_app('testing')
    with application.app_context():
        from app import db
        from app.models.user import User
        db.create_all()
        user = User.query.get(1)
        if not user:
            user = User(id=1, username='concurrencyadmin', role='admin')
            user.set_password('test')
            db.session.add(user)
            db.session.commit()
    yield application


@pytest.fixture
def client(app):
    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess['user_id'] = 1
            sess['username'] = 'concurrencyadmin'
            sess['role'] = 'admin'
            sess['last_active'] = datetime.datetime.now(
                datetime.timezone.utc
            ).isoformat()
        yield c


# ---------------------------------------------------------------------------
# Test 1: CandidateTaskStatus lifecycle
# ---------------------------------------------------------------------------

class TestCandidateTaskStatusIsComplete:
    """CandidateTaskStatus.is_complete defaults to False and can be set."""

    def test_is_complete_defaults_to_false(self):
        from app.services.candidate.pipeline import CandidateTaskStatus
        task = CandidateTaskStatus('t1', 'c1', 'Иванов Иван')
        assert task.is_complete is False

    def test_is_complete_can_be_set_to_true(self):
        from app.services.candidate.pipeline import CandidateTaskStatus
        task = CandidateTaskStatus('t2', 'c2', 'Иванов Иван')
        task.is_complete = True
        assert task.is_complete is True

    def test_error_is_none_by_default(self):
        from app.services.candidate.pipeline import CandidateTaskStatus
        task = CandidateTaskStatus('t3', 'c3', 'Иванов Иван')
        assert task.error is None

    def test_completed_at_is_none_by_default(self):
        from app.services.candidate.pipeline import CandidateTaskStatus
        task = CandidateTaskStatus('t4', 'c4', 'Иванов Иван')
        assert task.completed_at is None

    def test_cancelled_is_false_by_default(self):
        from app.services.candidate.pipeline import CandidateTaskStatus
        task = CandidateTaskStatus('t5', 'c5', 'Иванов Иван')
        assert task.cancelled is False


# ---------------------------------------------------------------------------
# Test 2: to_dict() status field and is_complete side-effect
# ---------------------------------------------------------------------------

class TestCandidateTaskStatusToDict:
    """to_dict() returns correct status and sets is_complete as a side-effect."""

    def test_running_status_when_no_error_no_complete(self):
        from app.services.candidate.pipeline import CandidateTaskStatus
        task = CandidateTaskStatus('td1', 'cd1', 'Петров Петр')
        d = task.to_dict()
        assert d['status'] == 'running'
        # Running tasks must NOT flip is_complete to True
        # (is_complete should still be False for a genuinely running task)

    def test_complete_status_when_completed_at_set(self):
        from app.services.candidate.pipeline import CandidateTaskStatus
        task = CandidateTaskStatus('td2', 'cd2', 'Петров Петр')
        task.completed_at = datetime.datetime.now()
        d = task.to_dict()
        assert d['status'] == 'complete'
        assert task.is_complete is True

    def test_error_status_when_error_set(self):
        from app.services.candidate.pipeline import CandidateTaskStatus
        task = CandidateTaskStatus('td3', 'cd3', 'Петров Петр')
        task.error = 'Something went wrong'
        d = task.to_dict()
        assert d['status'] == 'error'
        assert task.is_complete is True

    def test_cancelled_status_when_cancelled_set(self):
        from app.services.candidate.pipeline import CandidateTaskStatus
        task = CandidateTaskStatus('td4', 'cd4', 'Петров Петр')
        task.cancelled = True
        d = task.to_dict()
        assert d['status'] == 'cancelled'
        assert task.is_complete is True

    def test_is_complete_set_by_to_dict_for_complete(self):
        from app.services.candidate.pipeline import CandidateTaskStatus
        task = CandidateTaskStatus('td5', 'cd5', 'Петров Петр')
        task.completed_at = datetime.datetime.now()
        assert task.is_complete is False  # before to_dict
        task.to_dict()
        assert task.is_complete is True   # after to_dict

    def test_to_dict_includes_required_keys(self):
        from app.services.candidate.pipeline import CandidateTaskStatus
        task = CandidateTaskStatus('td6', 'cd6', 'Петров Петр')
        d = task.to_dict()
        required_keys = {
            'task_id', 'check_id', 'status', 'full_name',
            'current_stage', 'current_step', 'percent_complete',
            'messages', 'error', 'is_complete',
        }
        assert required_keys.issubset(d.keys())


# ---------------------------------------------------------------------------
# Test 3: update() method
# ---------------------------------------------------------------------------

class TestCandidateTaskStatusUpdate:
    """update() sets stage/step/percent, adds a message, and calls _sync_to_db."""

    def test_update_sets_fields(self):
        from app.services.candidate.pipeline import CandidateTaskStatus
        task = CandidateTaskStatus('u1', 'cu1', 'Сидоров Сидор')
        task.update('identity', 'Подтверждение личности', 10)
        assert task.current_stage == 'identity'
        assert task.current_step == 'Подтверждение личности'
        assert task.percent_complete == 10

    def test_update_adds_message(self):
        from app.services.candidate.pipeline import CandidateTaskStatus
        task = CandidateTaskStatus('u2', 'cu2', 'Сидоров Сидор')
        task.update('gov_registries', 'Проверка реестров', 15)
        assert any(m['text'] == 'Проверка реестров' for m in task.messages)

    def test_update_sync_to_db_skipped_without_check(self):
        """_sync_to_db is a no-op when no check is bound — must not raise."""
        from app.services.candidate.pipeline import CandidateTaskStatus
        task = CandidateTaskStatus('u3', 'cu3', 'Сидоров Сидор')
        # No bound check — should not raise
        task.update('security', 'Санкции', 25)
        assert task.percent_complete == 25


# ---------------------------------------------------------------------------
# Test 4: active_count logic — direct unit test
# ---------------------------------------------------------------------------

class TestActiveCountLogic:
    """Test the active_count calculation used in start_check().

    The rule: active_count = count of tasks where is_complete=False.
    Completed tasks (is_complete=True) must NOT count.
    """

    def _count_active(self, task_store):
        """Mirror the exact expression from start_check()."""
        return sum(1 for t in task_store.values() if not t.is_complete)

    def test_empty_store_has_zero_active(self):
        assert self._count_active({}) == 0

    def test_ten_completed_tasks_have_zero_active(self):
        from app.services.candidate.pipeline import CandidateTaskStatus
        store = {}
        for i in range(10):
            t = CandidateTaskStatus(f'task_{i}', f'check_{i}', 'Test')
            t.is_complete = True
            t.completed_at = datetime.datetime.now()
            store[f'task_{i}'] = t
        assert self._count_active(store) == 0

    def test_nine_complete_plus_one_active_equals_one(self):
        """Nine completed + 1 active = 1 active, well below the 10-task limit."""
        from app.services.candidate.pipeline import CandidateTaskStatus
        store = {}
        for i in range(9):
            t = CandidateTaskStatus(f'task_c{i}', f'check_c{i}', 'Test')
            t.is_complete = True
            t.completed_at = datetime.datetime.now()
            store[f'task_c{i}'] = t
        active = CandidateTaskStatus('task_active', 'check_active', 'Test')
        store['task_active'] = active
        assert self._count_active(store) == 1

    def test_ten_active_tasks_trigger_limit(self):
        """Ten incomplete tasks should hit the >= 10 gate."""
        from app.services.candidate.pipeline import CandidateTaskStatus
        store = {}
        for i in range(10):
            t = CandidateTaskStatus(f'task_a{i}', f'check_a{i}', 'Test')
            # is_complete stays False (default)
            store[f'task_a{i}'] = t
        assert self._count_active(store) >= 10

    def test_nine_active_tasks_do_not_trigger_limit(self):
        """Nine incomplete tasks must be below the >= 10 gate."""
        from app.services.candidate.pipeline import CandidateTaskStatus
        store = {}
        for i in range(9):
            t = CandidateTaskStatus(f'task_b{i}', f'check_b{i}', 'Test')
            store[f'task_b{i}'] = t
        assert self._count_active(store) < 10


# ---------------------------------------------------------------------------
# Test 5: start_check() HTTP gate — 429 vs 200
# ---------------------------------------------------------------------------

def _valid_start_payload():
    return {
        'full_name': 'Тестов Тест Тестович',
        'date_of_birth': '1985-06-15',
        'inn': '500100732259',
        'pd_consent': '1',
    }


def _register_candidate_check_module_patches():
    """Return a list of (module_attr, patch_target) tuples for pipeline isolation."""
    return []


class TestStartCheckActiveCountGate:
    """POST /candidate/start should return 429 when 10+ active tasks exist."""

    def _inject_active_tasks(self, app, count, completed=False):
        """Populate candidate_tasks with `count` tasks (complete or active)."""
        from app.services.candidate.pipeline import (
            CandidateTaskStatus, candidate_tasks, _tasks_lock,
        )
        injected = []
        with _tasks_lock:
            for i in range(count):
                tid = f'gate_test_task_{uuid.uuid4().hex}'
                t = CandidateTaskStatus(tid, f'gate_check_{i}', 'Test')
                if completed:
                    t.is_complete = True
                    t.completed_at = datetime.datetime.now()
                candidate_tasks[tid] = t
                injected.append(tid)
        return injected

    def _cleanup_tasks(self, task_ids):
        from app.services.candidate.pipeline import candidate_tasks, _tasks_lock
        with _tasks_lock:
            for tid in task_ids:
                candidate_tasks.pop(tid, None)

    def test_ten_active_tasks_returns_429(self, app, client):
        """With 10 active tasks already running, start_check must return 429."""
        from unittest.mock import patch

        injected = self._inject_active_tasks(app, 10, completed=False)
        try:
            resp = client.post(
                '/candidate/start',
                data=_valid_start_payload(),
                follow_redirects=False,
            )
            assert resp.status_code == 429, (
                f"Expected 429 with 10 active tasks, got {resp.status_code}"
            )
        finally:
            self._cleanup_tasks(injected)

    def test_nine_complete_and_zero_active_returns_not_429(self, app, client):
        """Nine completed tasks + 0 active must NOT trigger 429."""
        from unittest.mock import patch

        injected = self._inject_active_tasks(app, 9, completed=True)
        try:
            with (
                patch('app.services.candidate.pipeline.run_candidate_pipeline',
                      return_value=None),
                patch('threading.Thread.start', return_value=None),
            ):
                resp = client.post(
                    '/candidate/start',
                    data=_valid_start_payload(),
                    follow_redirects=False,
                )
            # Should redirect (302) or succeed (200/201), NOT 429
            assert resp.status_code != 429, (
                f"Got 429 with only completed tasks — active_count bug still present! "
                f"status={resp.status_code}"
            )
        finally:
            self._cleanup_tasks(injected)

    def test_nine_complete_and_one_active_is_not_429(self, app, client):
        """9 completed + 1 active = 1 active total, must NOT return 429."""
        from unittest.mock import patch

        completed = self._inject_active_tasks(app, 9, completed=True)
        active = self._inject_active_tasks(app, 1, completed=False)
        try:
            with (
                patch('app.services.candidate.pipeline.run_candidate_pipeline',
                      return_value=None),
                patch('threading.Thread.start', return_value=None),
            ):
                resp = client.post(
                    '/candidate/start',
                    data=_valid_start_payload(),
                    follow_redirects=False,
                )
            assert resp.status_code != 429, (
                f"Expected non-429 with only 1 active task, got {resp.status_code}"
            )
        finally:
            self._cleanup_tasks(completed + active)


# ---------------------------------------------------------------------------
# Test 6: cleanup_old_tasks()
# ---------------------------------------------------------------------------

class TestCleanupOldTasks:
    """cleanup_old_tasks() removes tasks whose completed_at is past max_age."""

    def test_removes_old_completed_tasks(self):
        from app.services.candidate.pipeline import CandidateTaskStatus, cleanup_old_tasks

        store = {}
        old_task = CandidateTaskStatus('old_task', 'old_check', 'Test')
        old_task.is_complete = True
        old_task.completed_at = datetime.datetime.now() - datetime.timedelta(seconds=7200)
        store['old_task'] = old_task

        cleanup_old_tasks(store, max_age_seconds=3600)
        assert 'old_task' not in store, "Old completed task should have been removed"

    def test_keeps_recently_completed_tasks(self):
        from app.services.candidate.pipeline import CandidateTaskStatus, cleanup_old_tasks

        store = {}
        recent_task = CandidateTaskStatus('recent_task', 'recent_check', 'Test')
        recent_task.is_complete = True
        recent_task.completed_at = datetime.datetime.now() - datetime.timedelta(seconds=60)
        store['recent_task'] = recent_task

        cleanup_old_tasks(store, max_age_seconds=3600)
        assert 'recent_task' in store, "Recently completed task should be kept"

    def test_keeps_running_tasks(self):
        from app.services.candidate.pipeline import CandidateTaskStatus, cleanup_old_tasks

        store = {}
        running_task = CandidateTaskStatus('running_task', 'run_check', 'Test')
        # No completed_at, not stale
        store['running_task'] = running_task

        cleanup_old_tasks(store, max_age_seconds=3600)
        assert 'running_task' in store, "Running task should be kept"

    def test_removes_multiple_old_tasks(self):
        from app.services.candidate.pipeline import CandidateTaskStatus, cleanup_old_tasks

        store = {}
        for i in range(5):
            t = CandidateTaskStatus(f'old_{i}', f'check_{i}', 'Test')
            t.is_complete = True
            t.completed_at = datetime.datetime.now() - datetime.timedelta(seconds=7200)
            store[f'old_{i}'] = t

        # One fresh task
        fresh = CandidateTaskStatus('fresh', 'fresh_check', 'Test')
        fresh.is_complete = True
        fresh.completed_at = datetime.datetime.now()
        store['fresh'] = fresh

        cleanup_old_tasks(store, max_age_seconds=3600)
        assert len([k for k in store if k.startswith('old_')]) == 0
        assert 'fresh' in store
