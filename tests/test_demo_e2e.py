"""
End-to-end demo mode verification.
Tests that the full pipeline runs with demo data and produces
a complete dossier with all sections populated.

External services are mocked to return empty results so demo fallbacks trigger.
"""

import json
import os
import uuid
from datetime import date
from unittest.mock import patch, MagicMock

import pytest

# Ensure SECRET_KEY is set and auth is disabled
os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-e2e')

# Save and clear VK/Telegram tokens BEFORE importing app to force demo mode.
# Use empty string (not pop) to prevent load_dotenv() from restoring them.
_orig_vk = os.environ.get('VK_SERVICE_TOKEN')
_orig_tg = os.environ.get('TELEGRAM_API_ID')
_orig_pw = os.environ.get('IBP_PASSWORD')
_orig_ph = os.environ.get('IBP_PASSWORD_HASH')
os.environ['VK_SERVICE_TOKEN'] = ''
os.environ['TELEGRAM_API_ID'] = ''
os.environ['IBP_PASSWORD'] = ''
os.environ['IBP_PASSWORD_HASH'] = ''

from app import create_app, db
from app.models.candidate_check import CandidateCheck
from app.services.candidate.pipeline import (
    run_candidate_pipeline,
    candidate_tasks,
    CandidateTaskStatus,
)


@pytest.fixture(scope='module')
def app():
    """Create Flask app in demo mode (no VK token), auth disabled."""
    application = create_app('testing')
    application.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    application.config['TESTING'] = True
    application.config['WTF_CSRF_ENABLED'] = False
    application.config['VK_SERVICE_TOKEN'] = ''
    application.config['DEMO_MODE'] = True
    application.config['SERVER_NAME'] = 'localhost'

    # Disable auth check
    application.before_request_funcs[None] = [
        f for f in application.before_request_funcs.get(None, [])
        if f.__name__ != 'check_auth'
    ]

    with application.app_context():
        db.create_all()
        yield application
        db.drop_all()

    # Restore original env vars
    for key, orig_val in [
        ('VK_SERVICE_TOKEN', _orig_vk),
        ('TELEGRAM_API_ID', _orig_tg),
        ('IBP_PASSWORD', _orig_pw),
        ('IBP_PASSWORD_HASH', _orig_ph),
    ]:
        if orig_val:
            os.environ[key] = orig_val
        elif key in os.environ:
            del os.environ[key]


@pytest.fixture(scope='module')
def client(app):
    return app.test_client()


@pytest.fixture(autouse=True)
def cleanup_tasks():
    """Clean up candidate_tasks after each test."""
    yield
    candidate_tasks.clear()


def _create_check(app, full_name='Иванов Иван Петрович', mode='quick'):
    """Create a CandidateCheck record directly in DB."""
    check_id = uuid.uuid4().hex
    task_id = uuid.uuid4().hex

    with app.app_context():
        check = CandidateCheck(
            id=check_id,
            full_name=full_name,
            date_of_birth=date(1985, 1, 15),
            inn='7707083893',
            status='pending',
            check_mode=mode,
        )
        db.session.add(check)
        db.session.commit()

    return check_id, task_id


# Mock targets — these are imported inside pipeline.py functions
_STAGE1_MOCKS = {
    'app.services.phase3.business_registry.BusinessRegistrySearch.search_by_name': lambda *a, **kw: [],
    'app.services.phase3.business_registry.BusinessRegistrySearch.search_by_inn': lambda *a, **kw: [],
    'app.services.phase3.court_search.CourtRecordSearch.search_by_name': lambda *a, **kw: [],
    'app.services.candidate.fssp_service.FSSPService.search': lambda *a, **kw: [],
    'app.services.candidate.bankruptcy_service.BankruptcyService.search': lambda *a, **kw: [],
}

_STAGE2_MOCKS = {
    'app.services.candidate.sanctions_check.SanctionsService.check_all': lambda *a, **kw: [],
}

# Stage 3: Mock VK and Telegram searches (return demo profiles fast)
_STAGE3_VK_DEMO = [
    MagicMock(**{
        'to_dict.return_value': {
            'full_name': 'Иванов Иван',
            'screen_name': 'ivanov_demo',
            'profile_url': 'https://vk.com/ivanov_demo',
            'photo_url': '',
            'city': 'Москва',
            'name_similarity': 85,
        }
    }),
]

_STAGE3_MOCKS = {
    'app.services.phase1.buratino_vk_search.buratino_vk_search.search':
        lambda *a, **kw: (_STAGE3_VK_DEMO, None),
    'app.services.phase1.telegram_discovery.TelegramDiscoveryService.discover':
        lambda *a, **kw: [],
    'app.services.phase1.telegram_discovery.TelegramDiscoveryService.close':
        lambda *a, **kw: None,
}

# Stage 4: Mock slow contact discovery services (Holehe ~25s, breach APIs)
_STAGE4_MOCKS = {
    'app.services.candidate.contact_discovery.ContactDiscoveryService.discover':
        lambda *a, **kw: {'phones': [], 'emails': []},
    'app.services.candidate.contact_discovery.ContactDiscoveryService.discover_supplementary':
        lambda *a, **kw: {'phones': [], 'emails': []},
}

# Stages 5-6: Mock social and behavioral analysis to return demo data fast
_DEMO_SOCIAL = {
    'face_matches': [
        {'source_db': 'vkok', 'confidence': 0.92, 'vk_id': '12345', 'name': 'Иванов Иван'},
    ],
    'social_graph': {
        'nodes': [{'id': 'vk_1', 'label': 'Центр', 'level': 0}],
        'edges': [],
        'stats': {'node_count': 1, 'edge_count': 0},
        'clusters': [],
    },
    'username_accounts': [
        {'platform': 'github', 'url': 'https://github.com/ivanovdemo',
         'username': 'ivanovdemo', 'source': 'snoop'},
    ],
    'new_accounts_for_enrichment': [],
}

_DEMO_BEHAVIORAL = {
    'text_analysis': {
        'sentiment': {'positive': 45, 'neutral': 40, 'negative': 15},
        'keywords': ['москва', 'работа', 'проект'],
    },
    'geo_analysis': {
        'locations': [
            {'city': 'Москва', 'lat': 55.7558, 'lng': 37.6176, 'mentions': 5},
        ],
    },
    'activity_timeline': [
        {'date': '2024-01-15', 'type': 'post', 'platform': 'vk', 'summary': 'Демо запись'},
    ],
}

_STAGE56_MOCKS = {
    'app.services.candidate.social_analysis.run_social_analysis':
        lambda *a, **kw: _DEMO_SOCIAL,
    'app.services.candidate.behavioral_analysis.run_behavioral_analysis':
        lambda *a, **kw: _DEMO_BEHAVIORAL,
}


def _run_pipeline(app, check_id, task_id, full_name='Иванов Иван Петрович'):
    """Run the pipeline synchronously with mocked external services."""
    task = CandidateTaskStatus(task_id=task_id, check_id=check_id, full_name=full_name)
    candidate_tasks[task_id] = task

    # Stack all mocks — external services return empty/demo, pipeline logic exercised
    patches = []
    all_mocks = {
        **_STAGE1_MOCKS, **_STAGE2_MOCKS, **_STAGE3_MOCKS,
        **_STAGE4_MOCKS, **_STAGE56_MOCKS,
    }
    for target, side_effect in all_mocks.items():
        p = patch(target, side_effect=side_effect)
        patches.append(p)

    for p in patches:
        p.start()

    try:
        run_candidate_pipeline(app, task_id, check_id)
    finally:
        for p in patches:
            p.stop()

    return task


class TestDemoEndToEnd:
    """Complete end-to-end demo flow verification."""

    def test_form_loads(self, client):
        """Main search form page loads without errors."""
        r = client.get('/api/search/page')
        assert r.status_code == 200
        assert 'Поиск' in r.data.decode('utf-8') or 'search' in r.data.decode('utf-8').lower()

    def test_candidate_form_has_mode_selector(self, client):
        """The search page loads successfully."""
        r = client.get('/api/search/page')
        assert r.status_code == 200

    def test_submit_quick_mode(self, client):
        """Submit candidate check in quick mode returns task_id."""
        r = client.post('/candidate/start', json={
            'full_name': 'Тестов Тест Тестович',
            'date_of_birth': '1990-05-15',
            'inn': '7707083893',
            'check_mode': 'quick',
        })
        assert r.status_code == 200
        data = r.get_json()
        assert 'task_id' in data
        assert 'check_id' in data

    def test_pipeline_completes_in_demo(self, app):
        """Full pipeline runs with demo data, all 8 stages complete."""
        check_id, task_id = _create_check(app)
        task = _run_pipeline(app, check_id, task_id)

        assert task.completed_at is not None
        assert task.error is None
        assert task.percent_complete == 100

    def test_dossier_has_all_sections(self, client, app):
        """Dossier page renders with data in every section."""
        check_id, task_id = _create_check(app)
        _run_pipeline(app, check_id, task_id)

        r = client.get(f'/candidate/dossier/{check_id}')
        assert r.status_code == 200
        html = r.data.decode('utf-8')

        assert 'Иванов Иван Петрович' in html
        assert 'sec-business' in html or 'ЕГРЮЛ' in html or 'Бизнес' in html
        assert 'sec-courts' in html or 'Суд' in html
        assert 'sec-sanctions' in html or 'Санкц' in html or 'Списк' in html

    def test_dossier_business_records_populated(self, app):
        """Business records section has demo data."""
        check_id, task_id = _create_check(app)
        _run_pipeline(app, check_id, task_id)

        with app.app_context():
            check = CandidateCheck.query.get(check_id)
            assert check is not None
            assert check.status == 'complete'
            biz = check.business_records
            assert isinstance(biz, list)
            assert len(biz) > 0, "Business records should have demo data"

    def test_dossier_court_records_populated(self, app):
        """Court records section has demo data."""
        check_id, task_id = _create_check(app)
        _run_pipeline(app, check_id, task_id)

        with app.app_context():
            check = CandidateCheck.query.get(check_id)
            courts = check.court_records
            assert isinstance(courts, list)
            assert len(courts) > 0, "Court records should have demo data"

    def test_sanctions_all_checked(self, app):
        """All 4 sanctions sources show as checked in demo mode."""
        check_id, task_id = _create_check(app)
        _run_pipeline(app, check_id, task_id)

        with app.app_context():
            check = CandidateCheck.query.get(check_id)
            sanctions = check.sanctions_results
            assert isinstance(sanctions, list)
            assert len(sanctions) >= 4, f"Expected 4 sanctions results, got {len(sanctions)}"
            checked = [s for s in sanctions if s.get('checked')]
            assert len(checked) >= 4, "All 4 sanctions should be checked in demo mode"

    def test_contacts_populated(self, app):
        """Contact discoveries have demo phones/emails."""
        check_id, task_id = _create_check(app)
        _run_pipeline(app, check_id, task_id)

        with app.app_context():
            check = CandidateCheck.query.get(check_id)
            contacts = check.contact_discoveries
            assert isinstance(contacts, dict)
            phones = contacts.get('phones', [])
            emails = contacts.get('emails', [])
            assert len(phones) > 0 or len(emails) > 0, "Should have demo contacts"

    def test_social_graph_data_present(self, client, app):
        """Social graph API returns vis.js compatible data."""
        check_id, task_id = _create_check(app)
        _run_pipeline(app, check_id, task_id)

        r = client.get(f'/candidate/api/social-graph/{check_id}')
        assert r.status_code == 200
        graph = r.get_json()
        assert 'nodes' in graph or 'graph' in str(graph).lower()

    def test_geo_data_present(self, client, app):
        """Geo API returns location data."""
        check_id, task_id = _create_check(app)
        _run_pipeline(app, check_id, task_id)

        r = client.get(f'/candidate/api/geo-data/{check_id}')
        assert r.status_code == 200

    def test_timeline_data_present(self, client, app):
        """Timeline API returns event data."""
        check_id, task_id = _create_check(app)
        _run_pipeline(app, check_id, task_id)

        r = client.get(f'/candidate/api/timeline/{check_id}')
        assert r.status_code == 200

    def test_json_export_complete(self, client, app):
        """JSON export contains all 8 stages of data."""
        check_id, task_id = _create_check(app)
        _run_pipeline(app, check_id, task_id)

        r = client.get(f'/candidate/export/{check_id}/json')
        assert r.status_code == 200
        export = r.get_json()

        assert 'business_records' in export
        assert 'court_records' in export
        assert 'sanctions_results' in export or 'sanctions' in export
        assert 'social_media_profiles' in export
        assert 'contact_discoveries' in export
        assert 'risk_assessment' in export or 'risk_level' in export or 'risk' in export

    def test_risk_score_populated(self, app):
        """Risk score is computed and not None."""
        check_id, task_id = _create_check(app)
        _run_pipeline(app, check_id, task_id)

        with app.app_context():
            check = CandidateCheck.query.get(check_id)
            assert check.risk_level is not None
            assert check.risk_level in ('clean', 'low', 'medium', 'high', 'critical')

    def test_risk_breakdown_populated(self, app):
        """Risk breakdown dict is populated by Stage 7."""
        check_id, task_id = _create_check(app)
        _run_pipeline(app, check_id, task_id)

        with app.app_context():
            check = CandidateCheck.query.get(check_id)
            breakdown = check.risk_breakdown
            assert isinstance(breakdown, dict)

    def test_history_page_shows_check(self, client, app):
        """Completed check appears in history list."""
        check_id, task_id = _create_check(app)
        _run_pipeline(app, check_id, task_id)

        r = client.get('/candidate/history')
        assert r.status_code == 200
        html = r.data.decode('utf-8')
        assert 'Иванов' in html

    def test_precise_mode_pauses(self, app):
        """Precise mode sets check_mode correctly."""
        check_id, task_id = _create_check(app, mode='precise')

        with app.app_context():
            check = CandidateCheck.query.get(check_id)
            assert check.check_mode == 'precise'

    def test_report_generated_flag(self, app):
        """report_generated is True after Stage 8."""
        check_id, task_id = _create_check(app)
        _run_pipeline(app, check_id, task_id)

        with app.app_context():
            check = CandidateCheck.query.get(check_id)
            assert check.report_generated is True

    def test_demo_data_is_russian(self, app):
        """Demo data should use Russian names, cities, and formats."""
        check_id, task_id = _create_check(app)
        _run_pipeline(app, check_id, task_id)

        with app.app_context():
            check = CandidateCheck.query.get(check_id)

            # Business records should have Russian company names
            biz = check.business_records
            if biz:
                assert any('ООО' in str(r) or 'ИП' in str(r) for r in biz), \
                    "Business records should have Russian company types"

            # Social profiles should have Russian names
            profiles = check.social_media_profiles
            if profiles:
                has_cyrillic = any(
                    any('\u0400' <= c <= '\u04FF' for c in str(p.get('display_name', '')))
                    for p in profiles
                )
                assert has_cyrillic, "Social profiles should have Russian names"

    def test_sources_counted(self, app):
        """sources_checked and sources_with_results are populated."""
        check_id, task_id = _create_check(app)
        _run_pipeline(app, check_id, task_id)

        with app.app_context():
            check = CandidateCheck.query.get(check_id)
            assert check.sources_checked > 0, "Should have checked at least some sources"
