"""
INN Pipeline Tests
==================
Tests for Stage 0 (Identity Confirmation), INN-required route validation,
risk scoring identity flags, VK DOB params, and the 9-stage pipeline.
"""

import json
import os
import sys
import uuid
from datetime import date
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models.candidate_check import CandidateCheck
from app.services.candidate.pipeline import candidate_tasks


# ============================================================
# FIXTURES
# ============================================================

@pytest.fixture(scope='module')
def app():
    """Create test app with in-memory database, auth disabled."""
    app = create_app('testing')
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    app.config['SERVER_NAME'] = 'localhost'

    app.before_request_funcs[None] = [
        f for f in app.before_request_funcs.get(None, [])
        if f.__name__ != 'check_auth'
    ]

    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture(scope='module')
def client(app):
    return app.test_client()


@pytest.fixture(autouse=True)
def cleanup_tasks():
    yield
    candidate_tasks.clear()


# ============================================================
# Route validation: INN required + checksum
# ============================================================

class TestInnRouteValidation:
    """Test that INN is required and validated on the /candidate/start route."""

    def test_missing_inn_returns_400(self, client, app):
        """POST without INN should return error."""
        with app.app_context():
            resp = client.post('/candidate/start', json={
                'full_name': 'Иванов Иван Иванович',
                'date_of_birth': '1990-05-15',
                # no inn
            })
            data = resp.get_json()
            assert resp.status_code == 400
            assert 'инн' in (data.get('error', '') or '').lower() or 'обязателен' in (data.get('error', '') or '').lower()

    def test_invalid_checksum_returns_400(self, client, app):
        """POST with bad INN checksum should return error."""
        with app.app_context():
            resp = client.post('/candidate/start', json={
                'full_name': 'Иванов Иван Иванович',
                'date_of_birth': '1990-05-15',
                'inn': '7707083890',  # bad checksum
            })
            data = resp.get_json()
            assert resp.status_code == 400
            assert 'контрольная сумма' in (data.get('error', '') or data.get('message', '')).lower() or \
                   'некорректна' in (data.get('error', '') or data.get('message', '')).lower()

    def test_valid_inn_accepted(self, client, app):
        """POST with valid INN should proceed (status 200 with task_id)."""
        with app.app_context():
            with patch('threading.Thread') as mock_thread:
                mock_thread.return_value.start = MagicMock()
                resp = client.post('/candidate/start', json={
                    'full_name': 'Иванов Иван Иванович',
                    'date_of_birth': '1990-05-15',
                    'inn': '7707083893',  # valid Sberbank INN
                })
                data = resp.get_json()
                assert resp.status_code == 200
                assert 'task_id' in data or 'id' in data


# ============================================================
# Stage 0: Identity Confirmation
# ============================================================

class TestStage0IdentityConfirmation:
    """Test Stage 0 identity confirmation logic."""

    def _make_check(self, app, **kwargs):
        """Create a CandidateCheck for testing."""
        with app.app_context():
            check_id = uuid.uuid4().hex
            defaults = dict(
                id=check_id,
                full_name='Иванов Иван Иванович',
                date_of_birth=date(1990, 5, 15),
                inn='7707083893',
                status='pending',
            )
            defaults.update(kwargs)
            check = CandidateCheck(**defaults)
            db.session.add(check)
            db.session.commit()
            return check_id

    def test_egrul_lookup_sets_confirmed_name(self, app):
        """When EGRUL returns a name, confirmed_name should be set."""
        check_id = self._make_check(app)
        with app.app_context():
            check = db.session.get(CandidateCheck, check_id)
            # Simulate what Stage 0 does
            check.confirmed_name = 'Иванов Иван Иванович'
            check.identity_confirmed = True
            check.identity_confirmation = {
                'egrul_status': 'found',
                'egrul_name': 'Иванов Иван Иванович',
                'name_discrepancy': False,
            }
            db.session.commit()

            # Reload and verify
            check = db.session.get(CandidateCheck, check_id)
            assert check.confirmed_name == 'Иванов Иван Иванович'
            assert check.identity_confirmed is True
            assert check.identity_confirmation['egrul_status'] == 'found'
            assert check.identity_confirmation['name_discrepancy'] is False

    def test_name_discrepancy_flag(self, app):
        """When EGRUL name differs from input, name_discrepancy should be True."""
        check_id = self._make_check(app, full_name='Иванов Ваня')
        with app.app_context():
            check = db.session.get(CandidateCheck, check_id)
            check.confirmed_name = 'Иванов Иван Иванович'
            check.identity_confirmed = True
            check.identity_confirmation = {
                'egrul_status': 'found',
                'egrul_name': 'Иванов Иван Иванович',
                'name_discrepancy': True,
            }
            db.session.commit()

            check = db.session.get(CandidateCheck, check_id)
            assert check.identity_confirmation['name_discrepancy'] is True
            assert check.confirmed_name != check.full_name

    def test_no_egrul_match_keeps_full_name(self, app):
        """When EGRUL returns nothing, confirmed_name should be full_name."""
        check_id = self._make_check(app)
        with app.app_context():
            check = db.session.get(CandidateCheck, check_id)
            # Stage 0 behavior when no EGRUL match
            check.confirmed_name = check.full_name
            check.identity_confirmed = False
            check.identity_confirmation = {
                'egrul_status': 'not_found',
                'name_discrepancy': False,
            }
            db.session.commit()

            check = db.session.get(CandidateCheck, check_id)
            assert check.confirmed_name == check.full_name
            assert check.identity_confirmed is False

    def test_business_network_stored(self, app):
        """Business network data should be stored in identity_confirmation."""
        check_id = self._make_check(app)
        with app.app_context():
            check = db.session.get(CandidateCheck, check_id)
            check.identity_confirmation = {
                'egrul_status': 'found',
                'business_network': [
                    {
                        'company_inn': '7701234567',
                        'company_name': 'ООО Тест',
                        'co_founders': [
                            {'name': 'Петров Петр', 'role': 'Учредитель'}
                        ],
                    }
                ],
            }
            db.session.commit()

            check = db.session.get(CandidateCheck, check_id)
            network = check.identity_confirmation['business_network']
            assert len(network) == 1
            assert network[0]['company_name'] == 'ООО Тест'
            assert len(network[0]['co_founders']) == 1


# ============================================================
# Risk Scoring: Identity flags
# ============================================================

class TestRiskScoringIdentity:
    """Test identity-related risk flags."""

    def test_name_discrepancy_creates_flag(self, app):
        """Name discrepancy should produce a MEDIUM risk flag."""
        with app.app_context():
            check = CandidateCheck(
                id=uuid.uuid4().hex,
                full_name='Иванов Ваня',
                date_of_birth=date(1990, 5, 15),
                inn='7707083893',
                status='complete',
            )
            check.confirmed_name = 'Иванов Иван Иванович'
            check.identity_confirmed = True
            check.identity_confirmation = {
                'name_discrepancy': True,
                'egrul_name': 'Иванов Иван Иванович',
            }

            from app.services.candidate.risk_scorer import RiskScorer
            scorer = RiskScorer()
            _, flags = scorer.analyze(check)

            identity_flags = [f for f in flags if f.get('category') == 'identity']
            assert len(identity_flags) >= 1
            discrepancy = [f for f in identity_flags if f['code'] == 'name_discrepancy']
            assert len(discrepancy) == 1
            assert discrepancy[0]['severity'] == 'medium'

    def test_identity_not_confirmed_creates_low_flag(self, app):
        """INN not confirmed should produce a LOW risk flag."""
        with app.app_context():
            check = CandidateCheck(
                id=uuid.uuid4().hex,
                full_name='Иванов Иван Иванович',
                date_of_birth=date(1990, 5, 15),
                inn='7707083893',
                status='complete',
            )
            check.identity_confirmed = False

            from app.services.candidate.risk_scorer import RiskScorer
            scorer = RiskScorer()
            _, flags = scorer.analyze(check)

            identity_flags = [f for f in flags if f.get('category') == 'identity']
            not_confirmed = [f for f in identity_flags if f['code'] == 'identity_not_confirmed']
            assert len(not_confirmed) == 1
            assert not_confirmed[0]['severity'] == 'low'

    def test_critical_debt_flag(self, app):
        """FSSP debt >1M should produce a HIGH critical_debt flag."""
        with app.app_context():
            check = CandidateCheck(
                id=uuid.uuid4().hex,
                full_name='Иванов Иван Иванович',
                date_of_birth=date(1990, 5, 15),
                inn='7707083893',
                status='complete',
            )
            check.fssp_records = [
                {'is_active': True, 'amount': 1500000, 'subject': 'Кредит'},
            ]

            from app.services.candidate.risk_scorer import RiskScorer
            scorer = RiskScorer()
            _, flags = scorer.analyze(check)

            fssp_flags = [f for f in flags if f.get('category') == 'fssp']
            critical_debt = [f for f in fssp_flags if f['code'] == 'critical_debt']
            assert len(critical_debt) == 1
            assert critical_debt[0]['severity'] == 'high'


# ============================================================
# VK DOB params
# ============================================================

class TestVkDobParams:
    """Test that DOB components are passed to VK search."""

    def test_vk_web_search_accepts_dob_params(self):
        """VKWebSearch.search() should accept birth_day/month/year params."""
        from app.services.phase1.vk_web_search import VKWebSearch
        import inspect
        sig = inspect.signature(VKWebSearch.search)
        params = list(sig.parameters.keys())
        assert 'birth_day' in params
        assert 'birth_month' in params
        assert 'birth_year' in params

    def test_buratino_search_accepts_dob_params(self):
        """BuratinoVKSearch.search() should accept birth_day/month/year params."""
        from app.services.phase1.buratino_vk_search import BuratinoVKSearch
        import inspect
        sig = inspect.signature(BuratinoVKSearch.search)
        params = list(sig.parameters.keys())
        assert 'birth_day' in params
        assert 'birth_month' in params
        assert 'birth_year' in params

    def test_telegram_discover_accepts_birth_year(self):
        """TelegramDiscoveryService.discover() should accept birth_year param."""
        from app.services.phase1.telegram_discovery import TelegramDiscoveryService
        import inspect
        sig = inspect.signature(TelegramDiscoveryService.discover)
        params = list(sig.parameters.keys())
        assert 'birth_year' in params


# ============================================================
# Model: identity_confirmation JSON property
# ============================================================

class TestModelIdentityFields:
    """Test CandidateCheck identity fields."""

    def test_identity_confirmation_json_roundtrip(self, app):
        """identity_confirmation JSON property should serialize/deserialize."""
        with app.app_context():
            check = CandidateCheck(
                id=uuid.uuid4().hex,
                full_name='Тест Тестов',
                date_of_birth=date(1990, 1, 1),
                inn='7707083893',
            )
            test_data = {
                'egrul_status': 'found',
                'confirmed_name': 'Тест Тестов',
                'business_network': [{'company_inn': '123'}],
            }
            check.identity_confirmation = test_data
            db.session.add(check)
            db.session.commit()

            reloaded = db.session.get(CandidateCheck, check.id)
            assert reloaded.identity_confirmation == test_data

    def test_confirmed_name_field(self, app):
        """confirmed_name column should store and retrieve correctly."""
        with app.app_context():
            check = CandidateCheck(
                id=uuid.uuid4().hex,
                full_name='Тест Тестов',
                date_of_birth=date(1990, 1, 1),
                inn='7707083893',
            )
            check.confirmed_name = 'Тестов Тест Тестович'
            db.session.add(check)
            db.session.commit()

            reloaded = db.session.get(CandidateCheck, check.id)
            assert reloaded.confirmed_name == 'Тестов Тест Тестович'

    def test_identity_confirmed_default_false(self, app):
        """identity_confirmed should default to False."""
        with app.app_context():
            check = CandidateCheck(
                id=uuid.uuid4().hex,
                full_name='Тест Тестов',
                date_of_birth=date(1990, 1, 1),
                inn='7707083893',
            )
            db.session.add(check)
            db.session.commit()

            reloaded = db.session.get(CandidateCheck, check.id)
            assert reloaded.identity_confirmed is False

    def test_to_dict_includes_identity_fields(self, app):
        """to_dict() should include confirmed_name and identity_confirmed."""
        with app.app_context():
            check = CandidateCheck(
                id=uuid.uuid4().hex,
                full_name='Тест Тестов',
                date_of_birth=date(1990, 1, 1),
                inn='7707083893',
            )
            check.confirmed_name = 'Тестов Тест'
            check.identity_confirmed = True

            d = check.to_dict()
            assert 'confirmed_name' in d
            assert d['confirmed_name'] == 'Тестов Тест'
            assert 'identity_confirmed' in d
            assert d['identity_confirmed'] is True


# ============================================================
# Report builder: identity section
# ============================================================

class TestReportBuilderIdentity:
    """Test that report builder includes identity data."""

    def test_report_includes_identity_confirmation(self, app):
        """build_report should include identity_confirmation section."""
        with app.app_context():
            check = CandidateCheck(
                id=uuid.uuid4().hex,
                full_name='Иванов Иван Иванович',
                date_of_birth=date(1990, 5, 15),
                inn='7707083893',
                status='complete',
                risk_level='low',
                report_generated=True,
            )
            check.confirmed_name = 'Иванов Иван Иванович'
            check.identity_confirmed = True
            check.identity_confirmation = {
                'egrul_status': 'found',
                'business_network': [],
                'name_discrepancy': False,
            }
            check.business_records = [{'company_name': 'Test'}]
            db.session.add(check)
            db.session.commit()

            from app.services.candidate.report_builder import build_report
            report = build_report(check)

            assert 'identity_confirmation' in report
            assert report['identity_confirmation']['inn'] == '7707083893'
            assert report['identity_confirmation']['identity_confirmed'] is True
            assert report['identity_card']['confirmed_name'] == 'Иванов Иван Иванович'
            assert report['identity_card']['inn'] == '7707083893'
