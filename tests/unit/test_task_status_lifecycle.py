"""Unit tests for CandidateTaskStatus lifecycle.

Verifies:
- .update() sets stage, step, percent, adds message, calls _sync_to_db()
- .to_dict() returns correct `status` field for each state
- .is_complete is set to True by to_dict() when status is complete/error/cancelled
- bind_check() wires up DB persistence
- add_message() records messages with required keys
"""

import datetime
import sys
import os
from unittest.mock import MagicMock, patch, call

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
os.environ.setdefault('SECRET_KEY', 'test-secret-key-lifecycle')

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_task(task_id='t1', check_id='c1', name='Иванов Иван'):
    from app.services.candidate.pipeline import CandidateTaskStatus
    return CandidateTaskStatus(task_id, check_id, name)


# ---------------------------------------------------------------------------
# Initial state
# ---------------------------------------------------------------------------

class TestInitialState:
    def test_task_id_stored(self):
        t = _make_task('my_task', 'my_check')
        assert t.task_id == 'my_task'

    def test_check_id_stored(self):
        t = _make_task('my_task', 'my_check')
        assert t.check_id == 'my_check'

    def test_full_name_stored(self):
        t = _make_task(name='Петров Петр Петрович')
        assert t.full_name == 'Петров Петр Петрович'

    def test_initial_stage_is_initializing(self):
        t = _make_task()
        assert t.current_stage == 'initializing'

    def test_initial_percent_is_zero(self):
        t = _make_task()
        assert t.percent_complete == 0

    def test_initial_messages_is_empty_list(self):
        t = _make_task()
        assert t.messages == []

    def test_initial_is_complete_is_false(self):
        t = _make_task()
        assert t.is_complete is False

    def test_initial_error_is_none(self):
        t = _make_task()
        assert t.error is None

    def test_initial_completed_at_is_none(self):
        t = _make_task()
        assert t.completed_at is None

    def test_initial_cancelled_is_false(self):
        t = _make_task()
        assert t.cancelled is False

    def test_initial_check_binding_is_none(self):
        t = _make_task()
        assert t._check is None

    def test_started_at_is_datetime(self):
        t = _make_task()
        assert isinstance(t.started_at, datetime.datetime)


# ---------------------------------------------------------------------------
# add_message()
# ---------------------------------------------------------------------------

class TestAddMessage:
    def test_add_message_appends_to_messages(self):
        t = _make_task()
        t.add_message('Test message', 'info')
        assert len(t.messages) == 1

    def test_add_message_stores_text(self):
        t = _make_task()
        t.add_message('Hello', 'info')
        assert t.messages[0]['text'] == 'Hello'

    def test_add_message_stores_type(self):
        t = _make_task()
        t.add_message('Error occurred', 'error')
        assert t.messages[0]['type'] == 'error'

    def test_add_message_has_time_key(self):
        t = _make_task()
        t.add_message('Something', 'warning')
        assert 'time' in t.messages[0]

    def test_add_multiple_messages(self):
        t = _make_task()
        t.add_message('First', 'info')
        t.add_message('Second', 'success')
        assert len(t.messages) == 2
        assert t.messages[0]['text'] == 'First'
        assert t.messages[1]['text'] == 'Second'


# ---------------------------------------------------------------------------
# update()
# ---------------------------------------------------------------------------

class TestUpdate:
    def test_update_sets_current_stage(self):
        t = _make_task()
        t.update('identity', 'Проверка ИНН', 5)
        assert t.current_stage == 'identity'

    def test_update_sets_current_step(self):
        t = _make_task()
        t.update('identity', 'Проверка ИНН', 5)
        assert t.current_step == 'Проверка ИНН'

    def test_update_sets_percent(self):
        t = _make_task()
        t.update('gov_registries', 'Реестры', 18)
        assert t.percent_complete == 18

    def test_update_appends_message_with_step_text(self):
        t = _make_task()
        t.update('social', 'VK поиск', 30)
        assert any(m['text'] == 'VK поиск' for m in t.messages)

    def test_update_calls_sync_to_db(self):
        t = _make_task()
        t._sync_to_db = MagicMock()
        t.update('risk', 'Расчёт рисков', 86)
        t._sync_to_db.assert_called_once()

    def test_update_overwrites_previous_stage(self):
        t = _make_task()
        t.update('identity', 'Step 1', 5)
        t.update('security', 'Step 2', 20)
        assert t.current_stage == 'security'
        assert t.percent_complete == 20

    def test_update_zero_percent(self):
        t = _make_task()
        t.update('init', 'Start', 0)
        assert t.percent_complete == 0

    def test_update_hundred_percent(self):
        t = _make_task()
        t.update('complete', 'Done', 100)
        assert t.percent_complete == 100


# ---------------------------------------------------------------------------
# _sync_to_db()
# ---------------------------------------------------------------------------

class TestSyncToDb:
    def test_sync_is_no_op_without_bound_check(self):
        """No check bound — _sync_to_db must not raise."""
        t = _make_task()
        t._sync_to_db()  # must not raise

    def test_sync_updates_check_fields(self, tmp_path):
        """With a mock check, _sync_to_db must update task_progress etc."""
        t = _make_task()
        mock_check = MagicMock()
        t._check = mock_check
        t.percent_complete = 42
        t.current_stage = 'risk'
        t.current_step = 'Scoring'
        t.error = None

        # db is imported inside _sync_to_db via 'from app import db'
        with patch('app.db') as mock_db:
            t._sync_to_db()

        assert mock_check.task_progress == 42
        assert mock_check.task_stage == 'risk'
        assert mock_check.task_message == 'Scoring'

    def test_sync_calls_db_session_commit(self):
        t = _make_task()
        mock_check = MagicMock()
        t._check = mock_check

        # db is imported inside _sync_to_db via 'from app import db'
        with patch('app.db') as mock_db:
            t._sync_to_db()
            mock_db.session.commit.assert_called_once()


# ---------------------------------------------------------------------------
# to_dict()
# ---------------------------------------------------------------------------

class TestToDict:
    def test_running_status_when_no_completion_no_error(self):
        t = _make_task()
        d = t.to_dict()
        assert d['status'] == 'running'

    def test_complete_status_when_completed_at_set(self):
        t = _make_task()
        t.completed_at = datetime.datetime.now()
        d = t.to_dict()
        assert d['status'] == 'complete'

    def test_error_status_when_error_set(self):
        t = _make_task()
        t.error = 'Pipeline crashed'
        d = t.to_dict()
        assert d['status'] == 'error'

    def test_cancelled_status_when_cancelled_true(self):
        t = _make_task()
        t.cancelled = True
        d = t.to_dict()
        assert d['status'] == 'cancelled'

    def test_error_takes_priority_over_completed_at(self):
        """error is checked first in to_dict(), so error wins over completed_at."""
        t = _make_task()
        t.error = 'Boom'
        t.completed_at = datetime.datetime.now()
        d = t.to_dict()
        assert d['status'] == 'error'

    def test_is_complete_set_to_true_for_complete(self):
        t = _make_task()
        t.completed_at = datetime.datetime.now()
        assert t.is_complete is False  # before
        t.to_dict()
        assert t.is_complete is True   # after

    def test_is_complete_set_to_true_for_error(self):
        t = _make_task()
        t.error = 'Something failed'
        t.to_dict()
        assert t.is_complete is True

    def test_is_complete_set_to_true_for_cancelled(self):
        t = _make_task()
        t.cancelled = True
        t.to_dict()
        assert t.is_complete is True

    def test_is_complete_not_set_for_running(self):
        """Running tasks must not flip is_complete to True via to_dict."""
        t = _make_task()
        t.to_dict()
        assert t.is_complete is False

    def test_dict_contains_task_id(self):
        t = _make_task('abc', 'def')
        assert t.to_dict()['task_id'] == 'abc'

    def test_dict_contains_check_id(self):
        t = _make_task('abc', 'def')
        assert t.to_dict()['check_id'] == 'def'

    def test_dict_contains_percent_complete(self):
        t = _make_task()
        t.percent_complete = 55
        assert t.to_dict()['percent_complete'] == 55

    def test_dict_messages_limited_to_40(self):
        t = _make_task()
        for i in range(50):
            t.add_message(f'msg {i}', 'info')
        d = t.to_dict()
        assert len(d['messages']) <= 40


# ---------------------------------------------------------------------------
# bind_check()
# ---------------------------------------------------------------------------

class TestBindCheck:
    def test_bind_check_sets_check(self):
        t = _make_task()
        mock_check = MagicMock()
        t.bind_check(mock_check)
        assert t._check is mock_check

    def test_bind_check_enables_sync(self):
        t = _make_task()
        mock_check = MagicMock()
        t.bind_check(mock_check)
        t.percent_complete = 77

        # db is imported inside _sync_to_db via 'from app import db'
        with patch('app.db') as mock_db:
            t._sync_to_db()
        assert mock_check.task_progress == 77
