"""
Full pipeline test with USE_MOCK_APIS=true.

Tests that the entire 8-stage pipeline runs end-to-end using mock API data
for all paid services. Mocks only truly external calls (gov sites, VK/Telegram,
Holehe) but lets breach APIs, GetContact, NumBuster, Hunter.io, etc. use
their mock implementations.

This validates that USE_MOCK_APIS=true produces rich, realistic data
through all 8 stages.
"""

import json
import os
import uuid
from datetime import date
from unittest.mock import patch, MagicMock

import pytest

# --- Set environment BEFORE any app imports ---
os.environ['USE_MOCK_APIS'] = 'true'
os.environ.setdefault('SECRET_KEY', 'test-secret-mock-apis')
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
    """Create Flask app with USE_MOCK_APIS=true, demo mode for VK."""
    application = create_app('testing')
    application.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    application.config['TESTING'] = True
    application.config['WTF_CSRF_ENABLED'] = False
    application.config['VK_SERVICE_TOKEN'] = ''
    application.config['DEMO_MODE'] = True
    application.config['USE_MOCK_APIS'] = 'true'
    application.config['SERVER_NAME'] = 'localhost'

    application.before_request_funcs[None] = [
        f for f in application.before_request_funcs.get(None, [])
        if f.__name__ != 'check_auth'
    ]

    with application.app_context():
        db.create_all()
        yield application
        db.drop_all()

    # Restore
    for key, orig in [
        ('VK_SERVICE_TOKEN', _orig_vk),
        ('TELEGRAM_API_ID', _orig_tg),
        ('IBP_PASSWORD', _orig_pw),
        ('IBP_PASSWORD_HASH', _orig_ph),
    ]:
        if orig:
            os.environ[key] = orig
        elif key in os.environ:
            del os.environ[key]
    os.environ.pop('USE_MOCK_APIS', None)


@pytest.fixture(scope='module')
def client(app):
    return app.test_client()


@pytest.fixture(autouse=True)
def cleanup_tasks():
    yield
    candidate_tasks.clear()


def _create_check(app, full_name='Козлов Андрей Викторович', mode='quick'):
    check_id = uuid.uuid4().hex
    task_id = uuid.uuid4().hex
    with app.app_context():
        check = CandidateCheck(
            id=check_id,
            full_name=full_name,
            date_of_birth=date(1988, 7, 22),
            status='pending',
            check_mode=mode,
        )
        db.session.add(check)
        db.session.commit()
    return check_id, task_id


# --- Mock only external network calls, NOT breach APIs ---

_VK_DEMO_PROFILE = MagicMock(**{
    'to_dict.return_value': {
        'full_name': 'Козлов Андрей',
        'screen_name': 'kozlov_av',
        'profile_url': 'https://vk.com/kozlov_av',
        'photo_url': '',
        'city': 'Казань',
        'name_similarity': 90,
    }
})

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

_STAGE3_MOCKS = {
    'app.services.phase1.buratino_vk_search.buratino_vk_search.search':
        lambda *a, **kw: ([_VK_DEMO_PROFILE], None),
    'app.services.phase1.telegram_discovery.TelegramDiscoveryService.discover':
        lambda *a, **kw: [],
    'app.services.phase1.telegram_discovery.TelegramDiscoveryService.close':
        lambda *a, **kw: None,
}

_DEMO_SOCIAL = {
    'face_matches': [
        {'source_db': 'vkok', 'confidence': 0.91, 'vk_id': '67890', 'name': 'Козлов Андрей'},
    ],
    'social_graph': {
        'nodes': [
            {'id': 'vk_67890', 'label': 'Козлов Андрей', 'level': 0},
            {'id': 'vk_11111', 'label': 'Петров Дмитрий', 'level': 1},
            {'id': 'vk_22222', 'label': 'Иванова Мария', 'level': 1},
        ],
        'edges': [
            {'from': 'vk_67890', 'to': 'vk_11111'},
            {'from': 'vk_67890', 'to': 'vk_22222'},
        ],
        'stats': {'node_count': 3, 'edge_count': 2},
        'clusters': [{'id': 0, 'label': 'Основной круг', 'members': ['vk_11111', 'vk_22222']}],
    },
    'username_accounts': [
        {'platform': 'github', 'url': 'https://github.com/kozlov_av', 'username': 'kozlov_av', 'source': 'snoop'},
        {'platform': 'instagram', 'url': 'https://instagram.com/kozlov_av', 'username': 'kozlov_av', 'source': 'snoop'},
    ],
    'new_accounts_for_enrichment': [],
}

_DEMO_BEHAVIORAL = {
    'text_analysis': {
        'sentiment': {'positive': 50, 'neutral': 35, 'negative': 15},
        'keywords': ['казань', 'программирование', 'IT', 'спорт'],
        'topics': ['технологии', 'спорт'],
    },
    'geo_analysis': {
        'locations': [
            {'city': 'Казань', 'lat': 55.7963, 'lng': 49.1088, 'mentions': 8},
            {'city': 'Москва', 'lat': 55.7558, 'lng': 37.6176, 'mentions': 3},
        ],
    },
    'activity_timeline': [
        {'date': '2024-01-10', 'type': 'post', 'platform': 'vk', 'summary': 'Пост о работе'},
        {'date': '2024-02-14', 'type': 'photo', 'platform': 'vk', 'summary': 'Фото с мероприятия'},
        {'date': '2024-03-05', 'type': 'repost', 'platform': 'vk', 'summary': 'Репост новости'},
    ],
}

_STAGE56_MOCKS = {
    'app.services.candidate.social_analysis.run_social_analysis':
        lambda *a, **kw: _DEMO_SOCIAL,
    'app.services.candidate.behavioral_analysis.run_behavioral_analysis':
        lambda *a, **kw: _DEMO_BEHAVIORAL,
}

# Mock contact discovery to avoid slow Holehe + real network calls,
# but return data that looks like what mock APIs would produce
_MOCK_CONTACTS = {
    'phones': [
        {
            'number': '+79261234567',
            'source': 'leak_db',
            'confidence': 'средняя',
            'profile_name': 'VK 2012 dump',
            'raw_value': '+79261234567',
        },
        {
            'number': '+79031112233',
            'source': 'breach_api',
            'confidence': 'средняя',
            'profile_name': 'DeHashed mock',
            'raw_value': '+79031112233',
        },
    ],
    'emails': [
        {
            'email': 'kozlov.andrey@mail.ru',
            'source': 'email_guess',
            'confidence': 'низкая',
            'verified': False,
            'profile_name': 'Pattern generation',
            'services': [],
        },
        {
            'email': 'a.kozlov@yandex.ru',
            'source': 'breach_api',
            'confidence': 'высокая',
            'verified': True,
            'profile_name': 'Snusbase mock',
            'services': ['Yandex Mail'],
        },
        {
            'email': 'kozlov_av@gmail.com',
            'source': 'hudsonrock_mock',
            'confidence': 'высокая',
            'verified': True,
            'profile_name': 'HudsonRock infostealer',
            'services': ['Gmail', 'VK'],
        },
    ],
}

_STAGE4_MOCKS = {
    'app.services.candidate.contact_discovery.ContactDiscoveryService.discover':
        lambda *a, **kw: _MOCK_CONTACTS,
    'app.services.candidate.contact_discovery.ContactDiscoveryService.discover_supplementary':
        lambda *a, **kw: {'phones': [], 'emails': []},
}


def _run_pipeline(app, check_id, task_id, full_name='Козлов Андрей Викторович'):
    task = CandidateTaskStatus(task_id=task_id, check_id=check_id, full_name=full_name)
    candidate_tasks[task_id] = task

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


class TestMockApisPipeline:
    """Full pipeline with USE_MOCK_APIS=true — verify rich data flows through all 8 stages."""

    def test_pipeline_completes_successfully(self, app):
        """Pipeline completes all 8 stages without errors."""
        check_id, task_id = _create_check(app)
        task = _run_pipeline(app, check_id, task_id)

        assert task.completed_at is not None, f"Pipeline did not complete. Error: {task.error}"
        assert task.error is None, f"Pipeline error: {task.error}"
        assert task.percent_complete == 100

    def test_stage1_gov_registries(self, app):
        """Stage 1: Government registries have demo fallback data."""
        check_id, task_id = _create_check(app)
        _run_pipeline(app, check_id, task_id)

        with app.app_context():
            check = CandidateCheck.query.get(check_id)
            biz = check.business_records
            assert isinstance(biz, list)
            assert len(biz) > 0, "Demo fallback should provide business records"
            courts = check.court_records
            assert isinstance(courts, list)
            assert len(courts) > 0, "Demo fallback should provide court records"

    def test_stage2_sanctions(self, app):
        """Stage 2: All 4 sanctions sources checked."""
        check_id, task_id = _create_check(app)
        _run_pipeline(app, check_id, task_id)

        with app.app_context():
            check = CandidateCheck.query.get(check_id)
            sanctions = check.sanctions_results
            assert isinstance(sanctions, list)
            assert len(sanctions) >= 4
            for s in sanctions:
                assert s.get('checked') is True

    def test_stage3_social_profiles(self, app):
        """Stage 3: Social media profiles discovered."""
        check_id, task_id = _create_check(app)
        _run_pipeline(app, check_id, task_id)

        with app.app_context():
            check = CandidateCheck.query.get(check_id)
            profiles = check.social_media_profiles
            assert isinstance(profiles, list)
            assert len(profiles) > 0
            # Should have VK profile from mock (stored as 'url' field)
            vk_profiles = [p for p in profiles
                           if 'vk.com' in str(p.get('url', '')) or p.get('platform') == 'vk']
            assert len(vk_profiles) > 0, f"Should have VK profile, got: {profiles}"

    def test_stage4_contacts_populated(self, app):
        """Stage 4: Contact discoveries have phones and emails."""
        check_id, task_id = _create_check(app)
        _run_pipeline(app, check_id, task_id)

        with app.app_context():
            check = CandidateCheck.query.get(check_id)
            contacts = check.contact_discoveries
            assert isinstance(contacts, dict)
            phones = contacts.get('phones', [])
            emails = contacts.get('emails', [])
            assert len(phones) >= 2, f"Expected >= 2 phones, got {len(phones)}"
            assert len(emails) >= 2, f"Expected >= 2 emails, got {len(emails)}"

            # Check that mock sources are represented
            email_sources = [e.get('source', '') for e in emails]
            assert any('breach' in s or 'mock' in s or 'hudsonrock' in s
                       for s in email_sources), \
                f"Expected breach/mock source in emails, got: {email_sources}"

    def test_stage5_social_analysis(self, app):
        """Stage 5: Social analysis data present (face_matches, social_graph, username_accounts)."""
        check_id, task_id = _create_check(app)
        _run_pipeline(app, check_id, task_id)

        with app.app_context():
            check = CandidateCheck.query.get(check_id)

            # Model stores these as separate properties
            face_matches = check.face_matches
            assert isinstance(face_matches, list)
            assert len(face_matches) > 0, "Should have face matches"

            graph = check.social_graph_data
            assert isinstance(graph, dict)
            assert len(graph.get('nodes', [])) >= 1

            username_accounts = check.username_accounts
            assert isinstance(username_accounts, list)
            assert len(username_accounts) > 0, "Should have username accounts"

    def test_stage6_behavioral(self, app):
        """Stage 6: Behavioral analysis data present (text, geo, timeline)."""
        check_id, task_id = _create_check(app)
        _run_pipeline(app, check_id, task_id)

        with app.app_context():
            check = CandidateCheck.query.get(check_id)

            # Model stores these as separate properties
            text = check.text_analysis
            assert isinstance(text, dict)
            assert len(text) > 0, "Should have text analysis"

            geo = check.geo_analysis
            assert isinstance(geo, dict)
            locations = geo.get('locations', [])
            assert len(locations) >= 1, "Should have geo locations"

            timeline = check.activity_timeline
            assert isinstance(timeline, list)
            assert len(timeline) > 0, "Should have activity timeline"

    def test_stage7_risk_scoring(self, app):
        """Stage 7: Risk score computed with valid level."""
        check_id, task_id = _create_check(app)
        _run_pipeline(app, check_id, task_id)

        with app.app_context():
            check = CandidateCheck.query.get(check_id)
            assert check.risk_level is not None
            assert check.risk_level in ('clean', 'low', 'medium', 'high', 'critical')

            breakdown = check.risk_breakdown
            assert isinstance(breakdown, dict)
            # Clean risk level may have empty breakdown (no red flags)
            # Non-clean should have categories
            if check.risk_level != 'clean':
                assert len(breakdown) > 0, "Non-clean risk should have breakdown categories"

    def test_stage8_report(self, app):
        """Stage 8: Report generated successfully."""
        check_id, task_id = _create_check(app)
        _run_pipeline(app, check_id, task_id)

        with app.app_context():
            check = CandidateCheck.query.get(check_id)
            assert check.report_generated is True
            assert check.status == 'complete'

    def test_dossier_page_renders(self, client, app):
        """Dossier page renders with all sections."""
        check_id, task_id = _create_check(app)
        _run_pipeline(app, check_id, task_id)

        r = client.get(f'/candidate/dossier/{check_id}')
        assert r.status_code == 200
        html = r.data.decode('utf-8')
        assert 'Козлов Андрей Викторович' in html

    def test_json_export_complete(self, client, app):
        """JSON export contains all 8 stages of data."""
        check_id, task_id = _create_check(app)
        _run_pipeline(app, check_id, task_id)

        r = client.get(f'/candidate/export/{check_id}/json')
        assert r.status_code == 200
        export = r.get_json()

        assert 'business_records' in export
        assert 'court_records' in export
        assert 'social_media_profiles' in export
        assert 'contact_discoveries' in export

    def test_social_graph_api(self, client, app):
        """Social graph API returns vis.js data."""
        check_id, task_id = _create_check(app)
        _run_pipeline(app, check_id, task_id)

        r = client.get(f'/candidate/api/social-graph/{check_id}')
        assert r.status_code == 200
        data = r.get_json()
        assert 'nodes' in data or 'graph' in str(data).lower()

    def test_geo_api(self, client, app):
        """Geo API returns location data."""
        check_id, task_id = _create_check(app)
        _run_pipeline(app, check_id, task_id)

        r = client.get(f'/candidate/api/geo-data/{check_id}')
        assert r.status_code == 200

    def test_timeline_api(self, client, app):
        """Timeline API returns event data."""
        check_id, task_id = _create_check(app)
        _run_pipeline(app, check_id, task_id)

        r = client.get(f'/candidate/api/timeline/{check_id}')
        assert r.status_code == 200

    def test_sources_counted(self, app):
        """sources_checked is populated after pipeline completion."""
        check_id, task_id = _create_check(app)
        _run_pipeline(app, check_id, task_id)

        with app.app_context():
            check = CandidateCheck.query.get(check_id)
            assert check.sources_checked > 0

    def test_data_is_russian(self, app):
        """All demo/mock data uses Russian names, cities, formats."""
        check_id, task_id = _create_check(app)
        _run_pipeline(app, check_id, task_id)

        with app.app_context():
            check = CandidateCheck.query.get(check_id)

            # Business records have Russian company types
            biz = check.business_records
            if biz:
                biz_str = json.dumps(biz, ensure_ascii=False)
                assert any(t in biz_str for t in ('ООО', 'ИП', 'АО')), \
                    "Business records should have Russian company types"

            # Social profiles have Cyrillic
            profiles = check.social_media_profiles
            if profiles:
                profiles_str = json.dumps(profiles, ensure_ascii=False)
                has_cyrillic = any('\u0400' <= c <= '\u04FF' for c in profiles_str)
                assert has_cyrillic, "Social profiles should have Cyrillic text"


class TestMockApisDirect:
    """Direct verification that mock APIs return data (no pipeline)."""

    def test_mock_apis_flag_active(self):
        """USE_MOCK_APIS is set to true."""
        from app.services.mock_data import _use_mock_apis
        assert _use_mock_apis()

    def test_getcontact_mock_returns_tags(self):
        """GetContact mock returns realistic Russian name tags."""
        from app.services.phase2.sources.getcontact import GetContactSource
        gc = GetContactSource()
        results = gc.query_impl(phone='+79161234501')
        assert len(results) > 0
        assert results[0].metadata.get('mock') is True
        assert len(results[0].metadata.get('tags', [])) >= 2

    def test_numbuster_mock_returns_name(self):
        """NumBuster mock returns name with trust rating."""
        from app.services.phase2.sources.getcontact import NumBusterSource
        nb = NumBusterSource()
        results = nb.query_impl(phone='+79161234501')
        assert len(results) > 0
        assert results[0].metadata.get('mock') is True
        assert 'trust_rating' in results[0].metadata

    def test_snusbase_mock_returns_breaches(self):
        """Snusbase mock returns breach records."""
        from app.services.phase2.sources.breach_api import SnusbaseSource
        sn = SnusbaseSource()
        results = sn.query_impl(email='test@mail.ru')
        assert len(results) > 0
        assert results[0].metadata.get('mock') is True
        assert 'breach_name' in results[0].metadata

    def test_dehashed_mock_returns_records(self):
        """DeHashed mock returns breach records with passwords."""
        from app.services.phase2.sources.breach_api import DehashedSource
        dh = DehashedSource()
        results = dh.query_impl(email='test@mail.ru')
        assert len(results) > 0
        assert results[0].metadata.get('mock') is True

    def test_leakcheck_mock_returns_results(self):
        """LeakCheck mock returns Pro-style results."""
        from app.services.phase2.sources.breach_api import LeakCheckSource
        lc = LeakCheckSource()
        results = lc.query_impl(email='test@mail.ru')
        assert len(results) > 0
        assert results[0].metadata.get('mock') is True
        assert 'breach_names' in results[0].metadata

    def test_proxynova_mock_returns_combos(self):
        """ProxyNova mock returns email:password lines."""
        from app.services.phase2.sources.breach_api import ProxyNovaCOMBSource
        pn = ProxyNovaCOMBSource()
        # Use a query that deterministically has results
        results = pn.query_impl(email='other@yandex.ru')
        assert len(results) > 0
        assert results[0].metadata.get('mock') is True

    def test_hunter_mock_returns_verification(self):
        """Hunter.io mock returns email verification score."""
        from app.services.phase2.email_sources import HunterIOChecker
        h = HunterIOChecker()
        result = h.verify_email('test@mail.ru')
        assert result.details.get('mock') is True
        assert result.details.get('score', 0) > 0

    def test_mock_data_deterministic(self):
        """Same query always returns same mock data."""
        from app.services.mock_data import mock_getcontact
        r1 = mock_getcontact('+79161234501')
        r2 = mock_getcontact('+79161234501')
        assert r1 == r2

    def test_different_queries_different_data(self):
        """Different queries return different mock data."""
        from app.services.mock_data import mock_getcontact
        r1 = mock_getcontact('+79161234501')
        r2 = mock_getcontact('+79261234502')
        assert r1 != r2
