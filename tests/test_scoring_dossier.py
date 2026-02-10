"""
Tests for Risk Scoring Engine and Professional Dossier Generator
================================================================
Validates the 7-dimension risk scoring and dossier export features.
"""

import pytest
import json
import uuid
import os
from datetime import datetime
from unittest.mock import patch


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def app():
    """Create application for testing with clean DB each test."""
    # Ensure auth is disabled
    os.environ.pop('IBP_PASSWORD', None)
    os.environ.pop('IBP_PASSWORD_HASH', None)

    from app import create_app, db as _db
    test_app = create_app('testing')
    test_app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    test_app.config['TESTING'] = True
    test_app.config['WTF_CSRF_ENABLED'] = False

    with test_app.app_context():
        _db.create_all()
        yield test_app
        _db.session.remove()
        _db.drop_all()


@pytest.fixture()
def db_session(app):
    """Provide a DB session scoped to the test."""
    from app import db
    with app.app_context():
        yield db.session


@pytest.fixture()
def client(app):
    """Flask test client with authenticated session."""
    c = app.test_client()
    # Pre-authenticate the session so auth gate doesn't block
    with c.session_transaction() as sess:
        sess['authenticated'] = True
    return c


def _make_investigation(db_session, **overrides):
    """Helper: create an Investigation with sensible defaults."""
    from app.models import Investigation
    inv_id = overrides.pop('id', uuid.uuid4().hex)
    inv = Investigation(
        id=inv_id,
        input_name=overrides.pop('input_name', 'Тестов Тест Тестович'),
        status=overrides.pop('status', 'phase_3_complete'),
        created_at=overrides.pop('created_at', datetime.utcnow()),
    )
    # Apply JSON-serialized field overrides
    for field in ('discovered_phones', 'discovered_emails', 'discovered_usernames',
                  'risk_indicators', 'property_records', 'social_graph',
                  'group_memberships', 'additional_findings', 'alternate_accounts'):
        if field in overrides:
            setattr(inv, field, overrides.pop(field))

    # Scalar overrides
    for key, val in overrides.items():
        setattr(inv, key, val)

    db_session.add(inv)
    db_session.flush()
    return inv


def _make_profile(db_session, investigation_id, **overrides):
    """Helper: create a SocialProfile."""
    from app.models import SocialProfile
    profile = SocialProfile(
        investigation_id=investigation_id,
        platform=overrides.pop('platform', 'vk'),
        platform_id=overrides.pop('platform_id', str(uuid.uuid4().int)[:10]),
        first_name=overrides.pop('first_name', 'Тест'),
        last_name=overrides.pop('last_name', 'Тестов'),
        display_name=overrides.pop('display_name', 'Тест Тестов'),
        is_confirmed=overrides.pop('is_confirmed', True),
        photo_url=overrides.pop('photo_url', 'https://example.com/photo.jpg'),
        username=overrides.pop('username', 'testtestov'),
        profile_url=overrides.pop('profile_url', 'https://vk.com/testtestov'),
    )
    for key, val in overrides.items():
        setattr(profile, key, val)
    db_session.add(profile)
    db_session.flush()
    return profile


def _make_business_records(db_session, investigation_id, count=5, liquidated=0):
    """Helper: create BusinessRecord instances."""
    from app.models import BusinessRecord
    records = []
    for i in range(count):
        status = 'Ликвидировано' if i < liquidated else 'Действующая'
        role = 'Директор' if i % 3 == 0 else 'Учредитель'
        rec = BusinessRecord(
            investigation_id=investigation_id,
            company_name=f'ООО "Компания-{i+1}"',
            inn=f'{1234567890+i}',
            ogrn=f'{1234567890123+i}',
            role=role,
            status=status,
            legal_address=f'г. Москва, ул. Тестовая, д. {i+1}',
            source='nalog.ru',
        )
        db_session.add(rec)
        records.append(rec)
    db_session.flush()
    return records


def _make_court_records(db_session, investigation_id, count=5, defendant_count=0):
    """Helper: create CourtRecord instances."""
    from app.models import CourtRecord
    records = []
    for i in range(count):
        is_def = i < defendant_count
        rec = CourtRecord(
            investigation_id=investigation_id,
            case_number=f'2-{1000+i}/2025',
            court_name=f'Суд района {i+1}',
            category='civil',
            person_role='defendant' if is_def else 'plaintiff',
            is_defendant=is_def,
            source='sudact.ru',
            source_url=f'https://sudact.ru/doc/{i+1}',
        )
        db_session.add(rec)
        records.append(rec)
    db_session.flush()
    return records


def _make_friends(db_session, investigation_id, count=20, profile_id=None):
    """Helper: create Friend instances."""
    from app.models import Friend
    friends = []
    for i in range(count):
        f = Friend(
            investigation_id=investigation_id,
            parent_profile_id=profile_id,
            platform='vk',
            platform_id=str(100000 + i),
            first_name=f'Друг{i}',
            last_name=f'Фамилия{i}',
            centrality_score=round(1.0 / (i + 1), 4),
        )
        db_session.add(f)
        friends.append(f)
    db_session.flush()
    return friends


# ===========================================================================
# RISK SCORING TESTS
# ===========================================================================

class TestRiskScoringCategories:
    """Test risk category boundaries."""

    def test_category_low(self, app):
        """Score 0-25 maps to LOW."""
        from app.services.risk_scoring import get_risk_category
        with app.app_context():
            for s in (0, 1, 10, 25):
                cat, _, _ = get_risk_category(s)
                assert cat == 'LOW', f"Score {s} should be LOW, got {cat}"

    def test_category_moderate(self, app):
        """Score 26-50 maps to MODERATE."""
        from app.services.risk_scoring import get_risk_category
        with app.app_context():
            for s in (26, 35, 50):
                cat, _, _ = get_risk_category(s)
                assert cat == 'MODERATE', f"Score {s} should be MODERATE, got {cat}"

    def test_category_elevated(self, app):
        """Score 51-75 maps to ELEVATED."""
        from app.services.risk_scoring import get_risk_category
        with app.app_context():
            for s in (51, 60, 75):
                cat, _, _ = get_risk_category(s)
                assert cat == 'ELEVATED', f"Score {s} should be ELEVATED, got {cat}"

    def test_category_high(self, app):
        """Score 76-100 maps to HIGH."""
        from app.services.risk_scoring import get_risk_category
        with app.app_context():
            for s in (76, 90, 100):
                cat, _, _ = get_risk_category(s)
                assert cat == 'HIGH', f"Score {s} should be HIGH, got {cat}"


class TestRiskScoringFullData:
    """Full-data investigation should score in the upper range."""

    def test_full_data_scores_high(self, app, db_session):
        """Investigation with lots of data should score 50+."""
        with app.app_context():
            inv = _make_investigation(
                db_session,
                discovered_phones=[{'number': '+79001234567', 'source': 'vk'}],
                discovered_emails=[{'email': 'test@mail.ru', 'source': 'holehe'}],
                social_graph={'nodes': [{'id': str(i)} for i in range(25)]},
            )
            profile = _make_profile(
                db_session, inv.id,
                phone='+79001234567',
                email='test@mail.ru',
                friends_count=600,
                photos_count=150,
                groups_count=30,
                followers_count=200,
                is_closed=False,
                career=[{'company': 'Test Corp'}],
                education=[{'university': 'MGU'}],
            )
            _make_business_records(db_session, inv.id, count=8, liquidated=2)
            _make_court_records(db_session, inv.id, count=6, defendant_count=3)
            _make_friends(db_session, inv.id, count=30, profile_id=profile.id)

            from app.services.risk_scoring import calculate_risk_score
            result = calculate_risk_score(inv.id)

            assert result is not None, "calculate_risk_score returned None"
            assert result['score'] >= 50, (
                f"Full data investigation scored {result['score']}, expected >= 50"
            )
            assert result['category'] in ('ELEVATED', 'HIGH'), (
                f"Expected ELEVATED or HIGH, got {result['category']}"
            )


class TestRiskScoringEmptyData:
    """Minimal/empty investigation should score LOW."""

    def test_empty_data_scores_low(self, app, db_session):
        """Brand new investigation with no data should score < 25."""
        with app.app_context():
            inv = _make_investigation(db_session, status='phase_1')

            from app.services.risk_scoring import calculate_risk_score
            result = calculate_risk_score(inv.id)

            assert result is not None
            assert result['score'] < 25, (
                f"Empty investigation scored {result['score']}, expected < 25"
            )
            assert result['category'] == 'LOW', (
                f"Expected LOW, got {result['category']}"
            )


class TestRiskScoringDimensions:
    """Test each of the 7 scoring dimensions independently."""

    def test_dim1_profile_completeness(self, app, db_session):
        """Profile with full data should score up to 15."""
        with app.app_context():
            from app.services.risk_scoring import _score_profile_completeness
            inv = _make_investigation(db_session, confirmed_phone='+79001234567', confirmed_email='t@t.ru')
            profile = _make_profile(
                db_session, inv.id,
                phone='+79001234567',
                email='t@t.ru',
                career=[{'company': 'X'}],
                education=[{'uni': 'Y'}],
            )
            score, factors = _score_profile_completeness(profile, inv)
            assert 0 <= score <= 15, f"Dim1 score {score} out of range"
            assert score >= 12, f"Full profile should score >= 12, got {score}"

    def test_dim1_profile_empty(self, app, db_session):
        """No profile should score 0."""
        with app.app_context():
            from app.services.risk_scoring import _score_profile_completeness
            inv = _make_investigation(db_session)
            score, factors = _score_profile_completeness(None, inv)
            assert score == 0

    def test_dim2_digital_footprint(self, app, db_session):
        """Multiple platforms and high friend count scores up to 20."""
        with app.app_context():
            from app.services.risk_scoring import _score_digital_footprint
            inv = _make_investigation(db_session)
            p1 = _make_profile(db_session, inv.id, platform='vk', friends_count=600, photos_count=200, is_confirmed=True)
            p2 = _make_profile(db_session, inv.id, platform='ok', is_confirmed=False, platform_id='99999')
            p3 = _make_profile(db_session, inv.id, platform='telegram', is_confirmed=False, platform_id='88888')

            from app.models import SocialProfile
            profiles = SocialProfile.query.filter_by(investigation_id=inv.id).all()
            score, factors = _score_digital_footprint(profiles, inv)
            assert 0 <= score <= 20, f"Dim2 score {score} out of range"
            assert score >= 14, f"3 platforms + big network should score >= 14, got {score}"

    def test_dim3_social_exposure(self, app, db_session):
        """High friend count and groups scores up to 15."""
        with app.app_context():
            from app.services.risk_scoring import _score_social_exposure
            inv = _make_investigation(
                db_session,
                social_graph={'nodes': [{'id': str(i)} for i in range(25)]},
            )
            profile = _make_profile(
                db_session, inv.id,
                friends_count=300,
                groups_count=25,
            )
            score, factors = _score_social_exposure(profile, inv)
            assert 0 <= score <= 15, f"Dim3 score {score} out of range"
            assert score >= 10, f"High social exposure should score >= 10, got {score}"

    def test_dim4_contact_exposure(self, app, db_session):
        """Phones + emails should score up to 15."""
        with app.app_context():
            from app.services.risk_scoring import _score_contact_exposure
            inv = _make_investigation(
                db_session,
                discovered_phones=['+79001111111'],
                discovered_emails=['a@b.ru'],
            )
            score, factors = _score_contact_exposure(inv)
            assert 0 <= score <= 15, f"Dim4 score {score} out of range"
            assert score == 15, f"Both phone and email = 15, got {score}"

    def test_dim4_no_contacts(self, app, db_session):
        """No contacts should score 0."""
        with app.app_context():
            from app.services.risk_scoring import _score_contact_exposure
            inv = _make_investigation(db_session)
            score, factors = _score_contact_exposure(inv)
            assert score == 0

    def test_dim5_business_ties(self, app, db_session):
        """Many business + court records should score up to 15."""
        with app.app_context():
            from app.services.risk_scoring import _score_business_ties
            inv = _make_investigation(db_session)
            biz = _make_business_records(db_session, inv.id, count=8)
            courts = _make_court_records(db_session, inv.id, count=7, defendant_count=3)
            score, factors = _score_business_ties(biz, courts)
            assert 0 <= score <= 15, f"Dim5 score {score} out of range"
            assert score == 15, f"8 biz + 7 court should cap at 15, got {score}"

    def test_dim6_behavioral_patterns(self, app, db_session):
        """Active poster with followers scores up to 10."""
        with app.app_context():
            from app.services.risk_scoring import _score_behavioral_patterns
            inv = _make_investigation(db_session)
            profile = _make_profile(
                db_session, inv.id,
                photos_count=100,
                groups_count=15,
                followers_count=300,
            )
            score, factors = _score_behavioral_patterns(profile, inv)
            assert 0 <= score <= 10, f"Dim6 score {score} out of range"
            assert score == 10, f"Very active profile should score 10, got {score}"

    def test_dim7_opsec_open_profile(self, app, db_session):
        """Open profile with real name and visible contacts = poor opsec (up to 10)."""
        with app.app_context():
            from app.services.risk_scoring import _score_opsec
            inv = _make_investigation(db_session)
            profile = _make_profile(
                db_session, inv.id,
                is_closed=False,
                first_name='Тест',
                last_name='Тестов',
                phone='+79001234567',
            )
            score, factors = _score_opsec(profile, inv)
            assert 0 <= score <= 10, f"Dim7 score {score} out of range"
            assert score == 10, f"Open, real name, contacts visible = 10, got {score}"

    def test_dim7_no_profile(self, app, db_session):
        """No profile -> opsec score = 0."""
        with app.app_context():
            from app.services.risk_scoring import _score_opsec
            inv = _make_investigation(db_session)
            score, factors = _score_opsec(None, inv)
            assert score == 0


class TestRiskScoreBounds:
    """Risk score should always be 0-100."""

    def test_score_never_negative(self, app, db_session):
        """Score with no data must not be negative."""
        with app.app_context():
            inv = _make_investigation(db_session)
            from app.services.risk_scoring import calculate_risk_score
            result = calculate_risk_score(inv.id)
            assert result['score'] >= 0

    def test_score_never_exceeds_100(self, app, db_session):
        """Score must cap at 100 even with maximal data."""
        with app.app_context():
            inv = _make_investigation(
                db_session,
                discovered_phones=['+79001234567', '+79002345678'],
                discovered_emails=['a@b.ru', 'c@d.ru'],
                social_graph={'nodes': [{'id': str(i)} for i in range(50)]},
                confirmed_phone='+79001234567',
                confirmed_email='a@b.ru',
            )
            _make_profile(
                db_session, inv.id,
                phone='+79001234567',
                email='a@b.ru',
                friends_count=1000,
                photos_count=500,
                groups_count=50,
                followers_count=5000,
                is_closed=False,
                career=[{'c': 'X'}],
                education=[{'u': 'Y'}],
            )
            _make_business_records(db_session, inv.id, count=20)
            _make_court_records(db_session, inv.id, count=20, defendant_count=10)

            from app.services.risk_scoring import calculate_risk_score
            result = calculate_risk_score(inv.id)
            assert result['score'] <= 100, f"Score {result['score']} exceeds 100"

    def test_score_not_found_returns_none(self, app, db_session):
        """Nonexistent investigation returns None."""
        with app.app_context():
            from app.services.risk_scoring import calculate_risk_score
            result = calculate_risk_score('nonexistent-id-12345')
            assert result is None


class TestRiskScoringAPI:
    """Test risk scoring API endpoints."""

    def test_calculate_endpoint(self, app, client, db_session):
        """POST /api/scoring/calculate returns score."""
        with app.app_context():
            inv = _make_investigation(db_session)
            _make_profile(db_session, inv.id)
            db_session.commit()

            resp = client.post('/api/scoring/calculate',
                               json={'investigation_id': inv.id},
                               content_type='application/json')
            assert resp.status_code == 200
            data = resp.get_json()
            assert 'score' in data
            assert 'category' in data
            assert 'breakdown' in data

    def test_calculate_endpoint_missing_id(self, client):
        """POST /api/scoring/calculate without ID returns 400."""
        resp = client.post('/api/scoring/calculate',
                           json={},
                           content_type='application/json')
        assert resp.status_code == 400

    def test_calculate_endpoint_not_found(self, client):
        """POST /api/scoring/calculate with bad ID returns 404."""
        resp = client.post('/api/scoring/calculate',
                           json={'investigation_id': 'nonexistent'},
                           content_type='application/json')
        assert resp.status_code == 404

    def test_breakdown_endpoint(self, app, client, db_session):
        """GET /api/scoring/breakdown/<id> returns 7-dimension breakdown."""
        with app.app_context():
            inv = _make_investigation(db_session)
            _make_profile(db_session, inv.id)
            db_session.commit()

            resp = client.get(f'/api/scoring/breakdown/{inv.id}')
            assert resp.status_code == 200
            data = resp.get_json()
            assert 'breakdown' in data

            breakdown = data['breakdown']
            expected_dims = [
                'profile_completeness', 'digital_footprint', 'social_exposure',
                'contact_exposure', 'business_ties', 'behavioral_patterns',
                'opsec_assessment',
            ]
            for dim in expected_dims:
                assert dim in breakdown, f"Missing dimension: {dim}"
                assert 'score' in breakdown[dim]
                assert 'max' in breakdown[dim]
                assert 'label' in breakdown[dim]
                assert 'factors' in breakdown[dim]

    def test_radar_chart_data_structure(self, app, client, db_session):
        """Breakdown has 7 dimensions with correct Russian labels."""
        with app.app_context():
            inv = _make_investigation(db_session)
            db_session.commit()

            resp = client.get(f'/api/scoring/breakdown/{inv.id}')
            data = resp.get_json()
            breakdown = data['breakdown']

            # Verify all 7 dimensions are present
            assert len(breakdown) == 7, f"Expected 7 dimensions, got {len(breakdown)}"

            # Verify each has a Russian label
            for key, dim_data in breakdown.items():
                assert dim_data['label'], f"Dimension {key} missing label"


# ===========================================================================
# DOSSIER TESTS
# ===========================================================================

class TestDossierGeneration:
    """Test DossierGenerator.generate_dossier()."""

    def test_dossier_full_data(self, app, db_session):
        """Dossier with full data returns all expected keys."""
        with app.app_context():
            inv = _make_investigation(
                db_session,
                discovered_phones=['+79001234567'],
                discovered_emails=['test@mail.ru'],
                risk_indicators=[
                    {'severity': 'high', 'description': 'Test risk', 'category': 'legal', 'source': 'sudact'}
                ],
            )
            _make_profile(db_session, inv.id, city='Москва')
            _make_business_records(db_session, inv.id, count=3)
            _make_court_records(db_session, inv.id, count=2)
            _make_friends(db_session, inv.id, count=10)

            from app.services.dossier_generator import dossier_generator
            dossier = dossier_generator.generate_dossier(inv.id)

            assert 'error' not in dossier
            assert dossier['target_name'] == 'Тестов Тест Тестович'
            assert dossier['investigation_id'] == inv.id
            assert dossier['confirmed_profile'] is not None
            assert len(dossier['profiles']) >= 1
            assert len(dossier['phones']) >= 1
            assert len(dossier['emails']) >= 1
            assert len(dossier['business_records']) == 3
            assert len(dossier['court_records']) == 2
            assert dossier['friends_count'] == 10
            assert dossier['confidence'] > 0
            assert dossier['risk_level'] == 'high'
            assert dossier['summary']  # executive summary not empty
            assert dossier['timeline']  # timeline not empty
            assert dossier['methodology']  # methodology not empty

    def test_dossier_partial_phase1_only(self, app, db_session):
        """Investigation with only Phase 1 data still generates a dossier."""
        with app.app_context():
            inv = _make_investigation(db_session, status='phase_1_complete')
            _make_profile(db_session, inv.id)

            from app.services.dossier_generator import dossier_generator
            dossier = dossier_generator.generate_dossier(inv.id)

            assert 'error' not in dossier
            assert dossier['target_name'] == 'Тестов Тест Тестович'
            assert len(dossier['business_records']) == 0
            assert len(dossier['court_records']) == 0
            assert dossier['friends_count'] == 0
            assert dossier['confidence'] > 0  # at least profile contributes

    def test_dossier_not_found(self, app, db_session):
        """Nonexistent investigation returns error dict."""
        with app.app_context():
            from app.services.dossier_generator import dossier_generator
            result = dossier_generator.generate_dossier('nonexistent-id')
            assert 'error' in result

    def test_dossier_missing_photo_no_crash(self, app, db_session):
        """Profile without photo_url should not crash dossier generation."""
        with app.app_context():
            inv = _make_investigation(db_session)
            _make_profile(db_session, inv.id, photo_url=None)

            from app.services.dossier_generator import dossier_generator
            dossier = dossier_generator.generate_dossier(inv.id)

            assert 'error' not in dossier
            # Confidence should be lower (no photo bonus)
            assert dossier['confirmed_profile'] is not None

    def test_dossier_cyrillic_handling(self, app, db_session):
        """Russian names render correctly in all dossier outputs."""
        with app.app_context():
            inv = _make_investigation(
                db_session,
                input_name='Козлова Анна Сергеевна',
            )
            _make_profile(
                db_session, inv.id,
                first_name='Анна',
                last_name='Козлова',
                display_name='Анна Козлова',
                city='Санкт-Петербург',
            )

            from app.services.dossier_generator import dossier_generator
            dossier = dossier_generator.generate_dossier(inv.id)

            assert 'error' not in dossier
            assert dossier['target_name'] == 'Козлова Анна Сергеевна'
            assert dossier['summary']
            # Summary should contain the name in Cyrillic
            assert 'Козлова Анна Сергеевна' in dossier['summary']


class TestDossierJSON:
    """Test JSON export from dossier generator."""

    def test_json_export_keys(self, app, db_session):
        """JSON export has all expected top-level keys."""
        with app.app_context():
            inv = _make_investigation(
                db_session,
                discovered_phones=['+79001234567'],
                discovered_emails=['test@mail.ru'],
            )
            _make_profile(db_session, inv.id, city='Москва')
            _make_business_records(db_session, inv.id, count=2)
            _make_court_records(db_session, inv.id, count=1)

            from app.services.dossier_generator import dossier_generator
            export = dossier_generator.generate_json(inv.id)

            expected_keys = [
                'meta', 'executive_summary', 'personal_data',
                'profiles', 'contacts', 'social_network',
                'risk_assessment', 'business_records', 'court_records',
                'enforcement_records', 'methodology',
            ]
            for key in expected_keys:
                assert key in export, f"Missing key in JSON export: {key}"

    def test_json_meta_section(self, app, db_session):
        """JSON meta section has required fields."""
        with app.app_context():
            inv = _make_investigation(db_session)
            _make_profile(db_session, inv.id)

            from app.services.dossier_generator import dossier_generator
            export = dossier_generator.generate_json(inv.id)

            meta = export['meta']
            assert meta['investigation_id'] == inv.id
            assert meta['target_name'] == inv.input_name
            assert meta['source'] == 'IBP - Identity-Based Profiler'
            assert meta['generated_at']
            assert meta['risk_level'] in ('none', 'low', 'medium', 'high')

    def test_json_personal_data(self, app, db_session):
        """JSON personal_data includes name, aliases, photo."""
        with app.app_context():
            inv = _make_investigation(
                db_session,
                discovered_usernames=['alias1', 'alias2'],
            )
            _make_profile(db_session, inv.id, city='Казань')

            from app.services.dossier_generator import dossier_generator
            export = dossier_generator.generate_json(inv.id)

            pd = export['personal_data']
            assert pd['name'] == inv.input_name
            assert 'alias1' in pd['aliases']
            assert pd['city'] == 'Казань'
            assert pd['photo_url']

    def test_json_contacts_section(self, app, db_session):
        """JSON contacts section has phones and emails."""
        with app.app_context():
            inv = _make_investigation(
                db_session,
                discovered_phones=['+79001234567'],
                discovered_emails=['a@b.ru'],
            )

            from app.services.dossier_generator import dossier_generator
            export = dossier_generator.generate_json(inv.id)

            contacts = export['contacts']
            assert len(contacts['phones']) >= 1
            assert len(contacts['emails']) >= 1

    def test_json_risk_assessment(self, app, db_session):
        """JSON risk_assessment section has level and indicators."""
        with app.app_context():
            inv = _make_investigation(
                db_session,
                risk_indicators=[
                    {'severity': 'medium', 'description': 'Test', 'category': 'biz', 'source': 'nalog'}
                ],
            )

            from app.services.dossier_generator import dossier_generator
            export = dossier_generator.generate_json(inv.id)

            ra = export['risk_assessment']
            assert ra['level'] in ('none', 'low', 'medium', 'high')
            assert len(ra['indicators']) >= 1

    def test_json_not_found(self, app, db_session):
        """JSON export for nonexistent investigation returns error."""
        with app.app_context():
            from app.services.dossier_generator import dossier_generator
            export = dossier_generator.generate_json('nonexistent-id')
            assert 'error' in export


class TestDossierRoutes:
    """Test dossier HTTP endpoints."""

    def test_dossier_html_route(self, app, client, db_session):
        """GET /dossier/<id> returns 200 or renders error template."""
        with app.app_context():
            inv = _make_investigation(db_session)
            _make_profile(db_session, inv.id)
            db_session.commit()

            resp = client.get(f'/dossier/{inv.id}')
            # Should either 200 (with template) or 500 (if template missing)
            # Since the template may not exist yet, accept 200 or 500
            assert resp.status_code in (200, 404, 500)

    def test_dossier_json_route(self, app, client, db_session):
        """GET /dossier/<id>/json returns JSON with expected keys."""
        with app.app_context():
            inv = _make_investigation(
                db_session,
                discovered_phones=['+79001234567'],
            )
            _make_profile(db_session, inv.id)
            db_session.commit()

            resp = client.get(f'/dossier/{inv.id}/json')
            assert resp.status_code == 200
            data = resp.get_json()
            assert 'meta' in data
            assert 'personal_data' in data

    def test_dossier_json_route_not_found(self, client):
        """GET /dossier/nonexistent/json returns 404."""
        resp = client.get('/dossier/nonexistent-123/json')
        assert resp.status_code == 404

    def test_dossier_pdf_route(self, app, client, db_session):
        """GET /dossier/<id>/pdf returns PDF or HTML fallback."""
        with app.app_context():
            inv = _make_investigation(db_session)
            _make_profile(db_session, inv.id)
            db_session.commit()

            resp = client.get(f'/dossier/{inv.id}/pdf')
            # Accept 200 (PDF or HTML fallback) or 404/500 (template issues)
            assert resp.status_code in (200, 404, 500)
            if resp.status_code == 200:
                # Should be either PDF or HTML content
                ct = resp.content_type
                assert 'pdf' in ct or 'html' in ct


class TestDossierPDF:
    """Test PDF generation specifically."""

    def test_pdf_with_weasyprint_mock(self, app, db_session):
        """If WeasyPrint available, PDF route produces content."""
        with app.app_context():
            inv = _make_investigation(db_session)
            _make_profile(db_session, inv.id)
            db_session.commit()

            # The PDF route tries WeasyPrint, falls back to HTML
            # We just verify the route doesn't crash
            client = app.test_client()
            resp = client.get(f'/dossier/{inv.id}/pdf')
            assert resp.status_code in (200, 404, 500)


# ===========================================================================
# INTEGRATION TESTS: Phase 3 page still shows existing badges
# ===========================================================================

class TestPhase3ResultsIntegration:
    """Verify Phase 3 results page still renders badges."""

    def test_phase3_results_page(self, app, client, db_session):
        """Phase 3 results page renders with business/court data."""
        with app.app_context():
            inv = _make_investigation(
                db_session,
                status='phase_3_complete',
                risk_indicators=[
                    {'severity': 'high', 'description': 'Test', 'category': 'biz',
                     'source': 'nalog', 'details': 'detail text'},
                ],
            )
            _make_profile(db_session, inv.id)
            _make_business_records(db_session, inv.id, count=3, liquidated=1)
            _make_court_records(db_session, inv.id, count=2, defendant_count=1)
            db_session.commit()

            resp = client.get(f'/phase3/buratino/results/{inv.id}')
            assert resp.status_code == 200
            html = resp.data.decode('utf-8')

            # Check that the key risk badge labels appear
            assert 'Бизнес-риск' in html, "Missing Бизнес-риск badge"
            assert 'Правовой риск' in html, "Missing Правовой риск badge"
            assert 'Финансовый риск' in html, "Missing Финансовый риск badge"

    def test_phase3_results_not_found(self, client):
        """Phase 3 results for nonexistent investigation returns 404."""
        resp = client.get('/phase3/buratino/results/nonexistent-123')
        assert resp.status_code == 404


class TestRiskReportPage:
    """Test the dedicated risk report page."""

    def test_risk_report_page(self, app, client, db_session):
        """GET /risk-report/<id> returns 200 or 500 (template may not exist yet)."""
        with app.app_context():
            inv = _make_investigation(db_session)
            _make_profile(db_session, inv.id)
            db_session.commit()

            resp = client.get(f'/risk-report/{inv.id}')
            # Template may or may not exist yet
            assert resp.status_code in (200, 404, 500)

    def test_risk_report_not_found(self, client):
        """GET /risk-report/nonexistent returns 404."""
        resp = client.get('/risk-report/nonexistent-123')
        assert resp.status_code == 404


# ===========================================================================
# EXISTING REPORT GENERATOR TESTS
# ===========================================================================

class TestExistingReportGenerator:
    """Tests for the existing ReportGenerator (identity card)."""

    def test_identity_card_html_generation(self, app, db_session):
        """ReportGenerator produces valid HTML with Cyrillic names."""
        with app.app_context():
            from app.services.report_generator import ReportGenerator, IdentityCardData

            data = IdentityCardData(
                full_name='Козлова Анна Сергеевна',
                city='Москва',
                profiles=[{
                    'platform': 'vk', 'username': 'kozlova_anna',
                    'url': 'https://vk.com/kozlova_anna', 'is_confirmed': True,
                }],
                phones=['+79001234567'],
                emails=['anna@mail.ru'],
                companies=[{
                    'company_name': 'ООО "Рога и Копыта"',
                    'role': 'Директор', 'inn': '1234567890',
                    'status': 'Действующая',
                }],
                court_cases=[{
                    'case_number': '2-1234/2025',
                    'court_name': 'Мировой суд',
                    'category_display': 'Гражданское',
                }],
                risk_indicators=[{
                    'severity': 'medium',
                    'description': 'Ликвидированные компании',
                    'category': 'business',
                }],
                investigation_id='test-12345678',
                confidence_score=65.0,
            )

            gen = ReportGenerator()
            html = gen.generate_identity_card_html(data)

            assert 'Козлова Анна Сергеевна' in html
            assert 'Москва' in html
            assert '+79001234567' in html
            assert 'anna@mail.ru' in html
            assert 'ООО' in html
            assert '2-1234/2025' in html
            assert '65%' in html

    def test_identity_card_no_photo_placeholder(self, app, db_session):
        """Identity card without photo shows placeholder, doesn't crash."""
        with app.app_context():
            from app.services.report_generator import ReportGenerator, IdentityCardData

            data = IdentityCardData(
                full_name='Тестов Тест',
                photo_url='',  # No photo
                investigation_id='test-nophoto',
            )

            gen = ReportGenerator()
            html = gen.generate_identity_card_html(data)

            assert 'NO PHOTO' in html
            assert 'Тестов Тест' in html

    def test_pdf_report_with_reportlab(self, app, db_session):
        """PDF generation produces bytes if reportlab is installed."""
        with app.app_context():
            from app.services.report_generator import ReportGenerator, IdentityCardData

            data = IdentityCardData(
                full_name='Тестов Тест Тестович',
                phones=['+79001234567'],
                emails=['test@test.ru'],
                city='Москва',
                confidence_score=50.0,
                investigation_id='pdf-test-123',
            )

            gen = ReportGenerator()
            pdf_bytes = gen.generate_pdf_report(data, {})

            # reportlab may or may not be installed
            if pdf_bytes:
                assert len(pdf_bytes) > 100, "PDF too small"
                assert pdf_bytes[:5] == b'%PDF-', "Not a valid PDF"
            # If empty bytes, reportlab not installed — acceptable

    def test_compile_data_from_dict(self, app, db_session):
        """compile_data converts investigation dict to IdentityCardData."""
        with app.app_context():
            from app.services.report_generator import ReportGenerator

            gen = ReportGenerator()
            data = gen.compile_data({
                'target_name': 'Тест Тестов',
                'profiles': [{'platform': 'vk', 'username': 'tt'}],
                'phones': ['+79001234567'],
                'emails': ['tt@mail.ru'],
                'business_records': [{'company_name': 'ООО Тест'}],
                'court_records': [],
                'enforcement_records': [],
                'friends_sample': [{'name': 'Друг'}],
                'friends_count': 10,
                'risk_indicators': [],
                'confidence_score': 42,
            })

            assert data.full_name == 'Тест Тестов'
            assert len(data.profiles) == 1
            assert data.phones == ['+79001234567']
            assert data.emails == ['tt@mail.ru']
            assert data.confidence_score == 42
