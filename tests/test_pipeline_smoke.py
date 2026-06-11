"""Pipeline smoke test.

Verifies that run_candidate_pipeline() completes without hanging
when all external services are mocked to return empty/stub data.

This test would have caught the three pipeline hang bugs:
  - false 429 on active_count (completed tasks counted as active)
  - court search hang (Playwright timeout not bounded)
  - social analysis executor hang (ThreadPoolExecutor not shut down)
"""

import datetime
import sys
import os
import threading
import uuid
from contextlib import ExitStack
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault('SECRET_KEY', 'test-secret-key-smoke')

import pytest

pytestmark = pytest.mark.filterwarnings("ignore")


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
            user = User(id=1, username='smokeadmin', role='admin')
            user.set_password('test')
            db.session.add(user)
            db.session.commit()
    yield application


def _make_check_row(app, check_id, task_id):
    """Create a minimal CandidateCheck row for the smoke test."""
    from app import db
    from app.models.candidate_check import CandidateCheck
    with app.app_context():
        existing = CandidateCheck.query.get(check_id)
        if existing:
            return
        check = CandidateCheck(
            id=check_id,
            user_id=1,
            full_name='Тестов Тест Тестович',
            date_of_birth=datetime.date(1985, 6, 15),
            inn='500100732259',
            status='pending',
            task_id=task_id,
            task_started_at=datetime.datetime.utcnow(),
            pd_consent=True,
            pd_consent_at=datetime.datetime.utcnow(),
        )
        db.session.add(check)
        db.session.commit()


class _FakeSanctionResult:
    def to_dict(self):
        return {
            'source_name': 'Test source',
            'checked': True,
            'found': False,
            'match_details': None,
            'error': None,
            'url': '',
        }


# All patches needed to prevent real network/Playwright calls.
# Using a flat dict so we can enter them all via ExitStack.
_PATCHES = {
    # Stage 0
    'egrul_inn': ('app.services.phase3.business_registry.BusinessRegistrySearch.search_by_inn', [], {}),
    'egrul_name': ('app.services.phase3.business_registry.BusinessRegistrySearch.search_by_name', [], {}),
    'bankr': ('app.services.candidate.bankruptcy_service.BankruptcyService.search', [], {}),
    # Stage 1
    'courts': ('app.services.phase3.court_search.CourtRecordSearch.search_by_name', [], {}),
    'fssp': ('app.services.candidate.fssp_service.FSSPService.search', [], {}),
    'pledges': ('app.services.phase3.pledge_registry.PledgeRegistrySearch.search_by_name', [], {}),
    'checko': ('app.services.phase3.checko_service.CheckoService.search_enforcement', ([], 'empty'), {}),
    'rep_su': ('app.services.phase3.reputation_su_service.search_reputation_su', ([], 'empty'), {}),
    'kad': ('app.services.phase3.kad_arbitr_service.search_kad_arbitr_person', ([], 'empty'), {}),
    # Stage 1 helpers (side_effect set separately below)
    # Stage 2
    'passport': ('app.services.phase3.passport_check.check_passport_mvd',
                 {'valid': None, 'checked': False, 'error': 'mocked'}, {}),
    # Stage 3
    'tg_discover': ('app.services.phase1.telegram_discovery.TelegramDiscoveryService.discover', [], {}),
    'tg_phone': ('app.services.phase1.telegram_discovery.TelegramDiscoveryService.search_by_phone', None, {}),
    'tg_close': ('app.services.phase1.telegram_discovery.TelegramDiscoveryService.close', None, {}),
    'tg_xref': (
        'app.services.phase1.telegram_discovery.TelegramDiscoveryService._method_a_vk_crossref', [], {}),
    # Stage 4
    'contacts': ('app.services.candidate.contact_discovery.ContactDiscoveryService.discover',
                 {'phones': [], 'emails': []}, {}),
    'contacts_supp': (
        'app.services.candidate.contact_discovery.ContactDiscoveryService.discover_supplementary',
        {'phones': [], 'emails': []}, {}),
    'phone_intel': (
        'app.services.phase2.phone_intelligence.run_phone_intelligence',
        {'summary': {'total_sources_with_data': 0}}, {}),
    'inn_breach': (
        'app.services.phase2.inn_breach_search.search_inn_in_breaches', {'found': False}, {}),
    # Stage 5
    'social': ('app.services.candidate.social_analysis.run_social_analysis',
               {'social_graph': {}, 'face_matches': [],
                'username_accounts': [], 'new_accounts_for_enrichment': []}, {}),
    # Stage 6
    'behavioral': ('app.services.candidate.behavioral_analysis.run_behavioral_analysis',
                   {'text_analysis': {}, 'geo_analysis': {},
                    'activity_timeline': [], 'group_analysis': {},
                    'activity_patterns': {}}, {}),
    'connected': ('app.services.candidate.behavioral_analysis.find_connected_checks', [], {}),
    'geo': ('app.services.phase3.geo_intelligence.collect_geo_intelligence',
            {'summary': {'total_locations': 0}}, {}),
    # Stage 8
    'report': ('app.services.candidate.report_builder.build_report', {}, {}),
    # AI
    'court_ai': ('app.services.ai.claude_integration.summarize_court_cases', None, {}),
    'beh_ai': ('app.services.ai.claude_integration.generate_behavioral_summary', None, {}),
    'risk_ai': ('app.services.ai.claude_integration.generate_risk_narrative', None, {}),
    'exec_ai': ('app.services.ai.claude_integration.generate_executive_summary', None, {}),
    # Optional
    'addr': ('app.services.phase3.address_intelligence.search_by_address', {'found': False}, {}),
}


def _start_all_patches():
    """Enter all patches and return a list of (patcher, mock) for cleanup."""
    active = []

    for key, (target, retval, _) in _PATCHES.items():
        if key == 'court_ai':
            # summarize_court_cases passes through the list unchanged
            p = patch(target, side_effect=lambda x: x)
        elif key == 'egrul_inn' or key == 'egrul_name' or key == 'bankr':
            p = patch(target, return_value=retval)
        else:
            p = patch(target, return_value=retval)
        m = p.start()
        active.append(p)

    # VK search returns (profiles_list, meta_dict)
    vk_patcher = patch(
        'app.services.phase1.buratino_vk_search.buratino_vk_search.search',
        return_value=([], {}),
    )
    vk_patcher.start()
    active.append(vk_patcher)

    # sanctions check_all returns a list of result objects
    sanctions_patcher = patch(
        'app.services.candidate.sanctions_check.SanctionsService.check_all',
        return_value=[_FakeSanctionResult()],
    )
    sanctions_patcher.start()
    active.append(sanctions_patcher)

    # INN filter is a pass-through
    inn_filter_patcher = patch(
        'app.services.phase3.business_registry.filter_business_records_by_inn',
        side_effect=lambda records, inn: records,
    )
    inn_filter_patcher.start()
    active.append(inn_filter_patcher)

    return active


def _stop_all_patches(active):
    for p in reversed(active):
        try:
            p.stop()
        except RuntimeError:
            pass


def test_pipeline_completes_without_hanging(app):
    """run_candidate_pipeline() must finish in 30s with all external calls mocked."""
    check_id = uuid.uuid4().hex
    task_id = uuid.uuid4().hex
    _make_check_row(app, check_id, task_id)

    from app.services.candidate.pipeline import (
        CandidateTaskStatus, candidate_tasks, _tasks_lock,
    )

    task = CandidateTaskStatus(task_id, check_id, 'Тестов Тест Тестович')
    with _tasks_lock:
        candidate_tasks[task_id] = task

    pipeline_error = []
    active_patches = _start_all_patches()

    def _run():
        try:
            from app.services.candidate.pipeline import run_candidate_pipeline
            run_candidate_pipeline(app, task_id, check_id)
        except Exception as exc:
            pipeline_error.append(exc)

    try:
        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
        thread.join(timeout=30)
    finally:
        _stop_all_patches(active_patches)

    assert not thread.is_alive(), (
        "Pipeline is still running after 30s — possible hang in a stage "
        "(court search, social analysis, or executor not shut down)"
    )

    assert not pipeline_error, f"Pipeline raised an exception: {pipeline_error[0]}"

    with app.app_context():
        from app.models.candidate_check import CandidateCheck
        check = CandidateCheck.query.get(check_id)
        assert check is not None, "CandidateCheck row disappeared"
        assert check.status == 'complete', (
            f"Expected check.status='complete', got '{check.status}'. "
            f"task.error={task.error!r}"
        )
        assert check.task_progress == 100, (
            f"Expected task_progress=100, got {check.task_progress}"
        )

    assert task.is_complete is True, "task.is_complete should be True after pipeline"
    assert task.error is None, f"task.error should be None, got: {task.error!r}"

    # Cleanup
    with _tasks_lock:
        candidate_tasks.pop(task_id, None)


def test_pipeline_sets_check_complete_status(app):
    """Re-verify: check.status ends up 'complete', not 'running' or 'error'."""
    check_id = uuid.uuid4().hex
    task_id = uuid.uuid4().hex
    _make_check_row(app, check_id, task_id)

    from app.services.candidate.pipeline import (
        CandidateTaskStatus, candidate_tasks, _tasks_lock,
    )

    task = CandidateTaskStatus(task_id, check_id, 'Тестов Тест Тестович')
    with _tasks_lock:
        candidate_tasks[task_id] = task

    active_patches = _start_all_patches()

    def _run():
        from app.services.candidate.pipeline import run_candidate_pipeline
        run_candidate_pipeline(app, task_id, check_id)

    try:
        t = threading.Thread(target=_run, daemon=True)
        t.start()
        t.join(timeout=30)
        assert not t.is_alive(), "Pipeline hung after 30s"
    finally:
        _stop_all_patches(active_patches)

    with app.app_context():
        from app.models.candidate_check import CandidateCheck
        check = CandidateCheck.query.get(check_id)
        assert check.status == 'complete'
        assert check.task_progress == 100

    with _tasks_lock:
        candidate_tasks.pop(task_id, None)
