"""
Tests for Risk Scoring Engine
==============================
Comprehensive tests covering:
- Score calculation with various data levels
- Individual dimension scoring
- Score boundaries and categories
- API endpoints
- Edge cases and monotonicity
"""

import json
import uuid
import pytest

from app import create_app, db
from app.models import Investigation, SocialProfile, BusinessRecord, CourtRecord


@pytest.fixture(scope='module')
def app():
    """Create application for testing with in-memory DB."""
    import os
    os.environ['IBP_PASSWORD'] = ''
    os.environ['IBP_PASSWORD_HASH'] = ''
    os.environ['DATABASE_URL'] = 'sqlite:///:memory:'

    test_app = create_app('testing')
    test_app.config['TESTING'] = True
    test_app.config['SERVER_NAME'] = 'localhost'

    yield test_app

    with test_app.app_context():
        db.drop_all()
    os.environ.pop('DATABASE_URL', None)


@pytest.fixture(autouse=True)
def clean_db(app):
    """Clean database between tests."""
    with app.app_context():
        db.session.rollback()
        for table in reversed(db.metadata.sorted_tables):
            db.session.execute(table.delete())
        db.session.commit()
    yield


@pytest.fixture
def client(app):
    return app.test_client()


def _make_investigation_id():
    return str(uuid.uuid4())


def _create_minimal_investigation(app):
    """Investigation with only a name — minimal data."""
    inv_id = _make_investigation_id()
    with app.app_context():
        inv = Investigation(id=inv_id, input_name='Иванов Иван Иванович', status='phase_1')
        db.session.add(inv)
        db.session.commit()
    return inv_id


def _create_full_investigation(app):
    """Investigation with all phases populated — maximum data."""
    inv_id = _make_investigation_id()
    with app.app_context():
        inv = Investigation(
            id=inv_id,
            input_name='Кузнецов Дмитрий Сергеевич',
            status='complete',
            confirmed_email='dmitry@example.com',
            confirmed_phone='+79161234567',
        )
        inv.discovered_emails = [
            {'email': 'dmitry@example.com', 'source': 'holehe'},
            {'email': 'dkuz@mail.ru', 'source': 'smtp'},
        ]
        inv.discovered_phones = [
            {'phone': '+79161234567', 'source': 'vk_api'},
            {'phone': '+79031112233', 'source': 'wall_regex'},
        ]
        inv.social_graph = {
            'nodes': [{'id': i} for i in range(30)],
            'edges': [{'from': 0, 'to': i} for i in range(1, 30)],
        }
        db.session.add(inv)

        # Confirmed profile with rich data
        profile = SocialProfile(
            investigation_id=inv_id,
            platform='vk',
            platform_id='123456',
            username='dkuznetsov',
            first_name='Дмитрий',
            last_name='Кузнецов',
            photo_url='https://vk.com/photo.jpg',
            is_confirmed=True,
            is_closed=False,
            friends_count=600,
            followers_count=150,
            photos_count=120,
            groups_count=25,
            phone='+79161234567',
            email='dmitry@example.com',
        )
        profile.education = [{'university': 'МГУ', 'faculty': 'ВМК'}]
        profile.career = [{'company': 'Яндекс', 'position': 'Разработчик'}]
        db.session.add(profile)

        # Additional profiles
        profile2 = SocialProfile(
            investigation_id=inv_id,
            platform='ok',
            platform_id='654321',
            first_name='Дмитрий',
            last_name='Кузнецов',
            is_confirmed=False,
        )
        db.session.add(profile2)

        profile3 = SocialProfile(
            investigation_id=inv_id,
            platform='telegram',
            platform_id='111222',
            first_name='Дмитрий',
            last_name='Кузнецов',
            is_confirmed=False,
        )
        db.session.add(profile3)

        # Business records
        for i in range(6):
            biz = BusinessRecord(
                investigation_id=inv_id,
                company_name=f'ООО Компания-{i+1}',
                inn=f'770000000{i}',
                status='active' if i < 4 else 'liquidated',
                role='director' if i < 2 else 'founder',
                source='nalog.ru',
            )
            db.session.add(biz)

        # Court records
        for i in range(6):
            court = CourtRecord(
                investigation_id=inv_id,
                case_number=f'2-{1000+i}/2025',
                category='civil',
                court_name=f'Суд-{i+1}',
                person_role='defendant' if i < 3 else 'plaintiff',
                is_defendant=(i < 3),
                source='sudact.ru',
            )
            db.session.add(court)

        db.session.commit()
    return inv_id


# ========== Test 1: Fully populated → HIGH ==========

class TestFullInvestigationScore:
    def test_full_data_high_score(self, app):
        """Fully populated investigation should produce HIGH score (76+)."""
        inv_id = _create_full_investigation(app)
        with app.app_context():
            from app.services.risk_scoring import calculate_risk_score
            result = calculate_risk_score(inv_id)

            assert result is not None
            assert result['score'] >= 76, f"Expected HIGH (76+), got {result['score']}"
            assert result['category'] == 'HIGH'
            assert result['category_ru'] == 'Высокий'

    def test_full_data_all_dimensions_present(self, app):
        """Full investigation breakdown should have all 7 dimensions with scores > 0."""
        inv_id = _create_full_investigation(app)
        with app.app_context():
            from app.services.risk_scoring import calculate_risk_score
            result = calculate_risk_score(inv_id)

            expected_keys = [
                'profile_completeness', 'digital_footprint', 'social_exposure',
                'contact_exposure', 'business_ties', 'behavioral_patterns',
                'opsec_assessment',
            ]
            for key in expected_keys:
                assert key in result['breakdown'], f"Missing dimension: {key}"
                dim = result['breakdown'][key]
                assert dim['score'] > 0, f"Dimension {key} should be > 0 for full data, got {dim['score']}"


# ========== Test 2: Minimal data → LOW ==========

class TestMinimalInvestigationScore:
    def test_minimal_data_low_score(self, app):
        """Investigation with only a name should produce LOW score (0-25)."""
        inv_id = _create_minimal_investigation(app)
        with app.app_context():
            from app.services.risk_scoring import calculate_risk_score
            result = calculate_risk_score(inv_id)

            assert result is not None
            assert result['score'] <= 25, f"Expected LOW (0-25), got {result['score']}"
            assert result['category'] == 'LOW'


# ========== Test 3: Each dimension independently ==========

class TestDimensionsIndependently:
    def test_profile_completeness_only(self, app):
        """Profile with photo+phone+email+career+education → profile_completeness max 15."""
        inv_id = _make_investigation_id()
        with app.app_context():
            inv = Investigation(id=inv_id, input_name='Тест Тестович', status='phase_2')
            inv.discovered_emails = []
            inv.discovered_phones = []
            db.session.add(inv)

            profile = SocialProfile(
                investigation_id=inv_id,
                platform='vk',
                platform_id='100',
                is_confirmed=True,
                photo_url='https://vk.com/photo.jpg',
                phone='+79001234567',
                email='test@mail.ru',
            )
            profile.career = [{'company': 'Яндекс'}]
            profile.education = [{'university': 'МГУ'}]
            db.session.add(profile)
            db.session.commit()

            from app.services.risk_scoring import calculate_risk_score
            result = calculate_risk_score(inv_id)
            assert result['breakdown']['profile_completeness']['score'] == 15

    def test_digital_footprint_only(self, app):
        """Multiple profiles with high friends/photos → digital_footprint scores high."""
        inv_id = _make_investigation_id()
        with app.app_context():
            inv = Investigation(id=inv_id, input_name='Тест', status='phase_2')
            db.session.add(inv)

            for i, platform in enumerate(['vk', 'ok', 'telegram']):
                p = SocialProfile(
                    investigation_id=inv_id,
                    platform=platform,
                    platform_id=str(200 + i),
                    friends_count=600 if i == 0 else None,
                    photos_count=150 if i == 0 else None,
                    is_confirmed=(i == 0),
                )
                db.session.add(p)
            db.session.commit()

            from app.services.risk_scoring import calculate_risk_score
            result = calculate_risk_score(inv_id)
            assert result['breakdown']['digital_footprint']['score'] == 20

    def test_social_exposure_only(self, app):
        """Profile with many friends+groups+social_graph → social_exposure scores high."""
        inv_id = _make_investigation_id()
        with app.app_context():
            inv = Investigation(id=inv_id, input_name='Тест', status='phase_2')
            inv.social_graph = {'nodes': [{'id': i} for i in range(25)]}
            db.session.add(inv)

            p = SocialProfile(
                investigation_id=inv_id,
                platform='vk',
                platform_id='300',
                is_confirmed=True,
                friends_count=250,
                groups_count=30,
            )
            db.session.add(p)
            db.session.commit()

            from app.services.risk_scoring import calculate_risk_score
            result = calculate_risk_score(inv_id)
            assert result['breakdown']['social_exposure']['score'] == 15

    def test_contact_exposure_only(self, app):
        """Discovered phones+emails → contact_exposure max 15."""
        inv_id = _make_investigation_id()
        with app.app_context():
            inv = Investigation(id=inv_id, input_name='Тест', status='phase_2')
            inv.discovered_phones = [{'phone': '+79001111111'}]
            inv.discovered_emails = [{'email': 'a@b.com'}]
            db.session.add(inv)
            db.session.commit()

            from app.services.risk_scoring import calculate_risk_score
            result = calculate_risk_score(inv_id)
            assert result['breakdown']['contact_exposure']['score'] == 15

    def test_business_ties_only(self, app):
        """Many business + court records → business_ties scores high."""
        inv_id = _make_investigation_id()
        with app.app_context():
            inv = Investigation(id=inv_id, input_name='Тест', status='phase_3')
            db.session.add(inv)

            for i in range(6):
                biz = BusinessRecord(
                    investigation_id=inv_id,
                    company_name=f'ООО-{i}',
                    inn=f'77000000{i:02d}',
                    status='active',
                    source='nalog.ru',
                )
                db.session.add(biz)

            for i in range(6):
                court = CourtRecord(
                    investigation_id=inv_id,
                    case_number=f'A-{i}/2025',
                    category='civil',
                    source='sudact.ru',
                )
                db.session.add(court)

            db.session.commit()

            from app.services.risk_scoring import calculate_risk_score
            result = calculate_risk_score(inv_id)
            assert result['breakdown']['business_ties']['score'] == 15

    def test_behavioral_patterns_only(self, app):
        """Active posting + groups + followers → behavioral_patterns max 10."""
        inv_id = _make_investigation_id()
        with app.app_context():
            inv = Investigation(id=inv_id, input_name='Тест', status='phase_2')
            db.session.add(inv)

            p = SocialProfile(
                investigation_id=inv_id,
                platform='vk',
                platform_id='400',
                is_confirmed=True,
                photos_count=60,
                groups_count=15,
                followers_count=200,
            )
            db.session.add(p)
            db.session.commit()

            from app.services.risk_scoring import calculate_risk_score
            result = calculate_risk_score(inv_id)
            assert result['breakdown']['behavioral_patterns']['score'] == 10

    def test_opsec_assessment_only(self, app):
        """Open profile with real name and visible contacts → opsec max 10."""
        inv_id = _make_investigation_id()
        with app.app_context():
            inv = Investigation(id=inv_id, input_name='Тест', status='phase_2')
            db.session.add(inv)

            p = SocialProfile(
                investigation_id=inv_id,
                platform='vk',
                platform_id='500',
                is_confirmed=True,
                first_name='Иван',
                last_name='Иванов',
                is_closed=False,
                phone='+79001111111',
            )
            db.session.add(p)
            db.session.commit()

            from app.services.risk_scoring import calculate_risk_score
            result = calculate_risk_score(inv_id)
            assert result['breakdown']['opsec_assessment']['score'] == 10


# ========== Test 4: Score boundaries ==========

class TestScoreBoundaries:
    def test_minimum_score_is_zero(self, app):
        """With no data at all, total score should be 0."""
        inv_id = _make_investigation_id()
        with app.app_context():
            inv = Investigation(id=inv_id, input_name='Пусто', status='phase_1')
            db.session.add(inv)
            db.session.commit()

            from app.services.risk_scoring import calculate_risk_score
            result = calculate_risk_score(inv_id)
            assert result['score'] == 0

    def test_no_negative_scores(self, app):
        """No dimension should ever produce a negative score."""
        inv_id = _make_investigation_id()
        with app.app_context():
            inv = Investigation(id=inv_id, input_name='Отрицание', status='phase_1')
            db.session.add(inv)
            db.session.commit()

            from app.services.risk_scoring import calculate_risk_score
            result = calculate_risk_score(inv_id)
            assert result['score'] >= 0
            for key, dim in result['breakdown'].items():
                assert dim['score'] >= 0, f"Dimension {key} has negative score: {dim['score']}"

    def test_maximum_score_capped_at_100(self, app):
        """Total score should not exceed 100 (sum of all maxes = 100)."""
        inv_id = _create_full_investigation(app)
        with app.app_context():
            from app.services.risk_scoring import calculate_risk_score
            result = calculate_risk_score(inv_id)
            assert result['score'] <= 100
            assert result['max_score'] == 100

    def test_each_dimension_capped(self, app):
        """Each dimension score should not exceed its max."""
        inv_id = _create_full_investigation(app)
        with app.app_context():
            from app.services.risk_scoring import calculate_risk_score
            result = calculate_risk_score(inv_id)
            for key, dim in result['breakdown'].items():
                assert dim['score'] <= dim['max'], \
                    f"Dimension {key}: score {dim['score']} exceeds max {dim['max']}"


# ========== Test 5: Risk categories match score ranges ==========

class TestRiskCategories:
    def test_low_range(self, app):
        from app.services.risk_scoring import get_risk_category
        with app.app_context():
            for score in [0, 10, 25]:
                cat, color, cat_ru = get_risk_category(score)
                assert cat == 'LOW', f"Score {score} should be LOW, got {cat}"

    def test_moderate_range(self, app):
        from app.services.risk_scoring import get_risk_category
        with app.app_context():
            for score in [26, 35, 50]:
                cat, color, cat_ru = get_risk_category(score)
                assert cat == 'MODERATE', f"Score {score} should be MODERATE, got {cat}"

    def test_elevated_range(self, app):
        from app.services.risk_scoring import get_risk_category
        with app.app_context():
            for score in [51, 65, 75]:
                cat, color, cat_ru = get_risk_category(score)
                assert cat == 'ELEVATED', f"Score {score} should be ELEVATED, got {cat}"

    def test_high_range(self, app):
        from app.services.risk_scoring import get_risk_category
        with app.app_context():
            for score in [76, 90, 100]:
                cat, color, cat_ru = get_risk_category(score)
                assert cat == 'HIGH', f"Score {score} should be HIGH, got {cat}"

    def test_category_boundaries_exact(self, app):
        """Test exact boundary values."""
        from app.services.risk_scoring import get_risk_category
        with app.app_context():
            assert get_risk_category(25)[0] == 'LOW'
            assert get_risk_category(26)[0] == 'MODERATE'
            assert get_risk_category(50)[0] == 'MODERATE'
            assert get_risk_category(51)[0] == 'ELEVATED'
            assert get_risk_category(75)[0] == 'ELEVATED'
            assert get_risk_category(76)[0] == 'HIGH'

    def test_category_colors(self, app):
        """Each category should have a distinct color."""
        from app.services.risk_scoring import get_risk_category
        with app.app_context():
            colors = set()
            for score in [10, 30, 60, 80]:
                _, color, _ = get_risk_category(score)
                colors.add(color)
            assert len(colors) == 4, "Each category should have a unique color"


# ========== Test 6: Integration — DB round-trip ==========

class TestIntegration:
    def test_create_and_score(self, app):
        """Create investigation in DB, calculate score, verify result structure."""
        inv_id = _create_full_investigation(app)
        with app.app_context():
            from app.services.risk_scoring import calculate_risk_score
            result = calculate_risk_score(inv_id)

            assert result is not None
            assert 'score' in result
            assert 'category' in result
            assert 'breakdown' in result
            assert 'data_summary' in result
            assert 'calculated_at' in result
            assert result['investigation_id'] == inv_id
            assert result['target_name'] == 'Кузнецов Дмитрий Сергеевич'

    def test_score_stored_in_risk_indicators(self, app):
        """After scoring, risk_indicators on Investigation should contain the auto_scoring entry."""
        inv_id = _create_full_investigation(app)
        with app.app_context():
            from app.services.risk_scoring import calculate_risk_score
            result = calculate_risk_score(inv_id)

            inv = Investigation.query.get(inv_id)
            indicators = inv.risk_indicators
            assert len(indicators) >= 1
            auto = [i for i in indicators if i.get('type') == 'auto_scoring']
            assert len(auto) == 1
            assert auto[0]['score'] == result['score']
            assert auto[0]['category'] == result['category']

    def test_data_summary_counts(self, app):
        """data_summary should reflect actual counts of profiles, emails, phones, etc."""
        inv_id = _create_full_investigation(app)
        with app.app_context():
            from app.services.risk_scoring import calculate_risk_score
            result = calculate_risk_score(inv_id)

            summary = result['data_summary']
            assert summary['profiles_found'] == 3
            assert summary['emails_found'] == 2
            assert summary['phones_found'] == 2
            assert summary['business_records'] == 6
            assert summary['court_records'] == 6

    def test_nonexistent_investigation_returns_none(self, app):
        """Scoring a nonexistent investigation should return None."""
        with app.app_context():
            from app.services.risk_scoring import calculate_risk_score
            result = calculate_risk_score('nonexistent-uuid')
            assert result is None


# ========== Test 7: API POST /api/scoring/calculate ==========

class TestCalculateAPI:
    def test_calculate_valid(self, app, client):
        """POST /api/scoring/calculate with valid ID returns score."""
        inv_id = _create_full_investigation(app)
        with app.app_context():
            resp = client.post(
                '/api/scoring/calculate',
                json={'investigation_id': inv_id},
                content_type='application/json',
            )
            assert resp.status_code == 200
            data = resp.get_json()
            assert 'score' in data
            assert 'category' in data
            assert 'breakdown' in data

    def test_calculate_missing_id(self, app, client):
        """POST /api/scoring/calculate without investigation_id returns 400."""
        with app.app_context():
            resp = client.post(
                '/api/scoring/calculate',
                json={},
                content_type='application/json',
            )
            assert resp.status_code == 400
            data = resp.get_json()
            assert 'error' in data

    def test_calculate_no_body(self, app, client):
        """POST /api/scoring/calculate with no body returns 400."""
        with app.app_context():
            resp = client.post(
                '/api/scoring/calculate',
                content_type='application/json',
            )
            assert resp.status_code == 400

    def test_calculate_nonexistent_id(self, app, client):
        """POST /api/scoring/calculate with unknown ID returns 404."""
        with app.app_context():
            resp = client.post(
                '/api/scoring/calculate',
                json={'investigation_id': 'does-not-exist'},
                content_type='application/json',
            )
            assert resp.status_code == 404
            data = resp.get_json()
            assert 'error' in data


# ========== Test 8: API GET /api/scoring/breakdown/<id> ==========

class TestBreakdownAPI:
    def test_breakdown_valid(self, app, client):
        """GET /api/scoring/breakdown/<id> returns JSON with all 7 dimension keys."""
        inv_id = _create_full_investigation(app)
        with app.app_context():
            resp = client.get(f'/api/scoring/breakdown/{inv_id}')
            assert resp.status_code == 200
            data = resp.get_json()

            expected_dimensions = [
                'profile_completeness', 'digital_footprint', 'social_exposure',
                'contact_exposure', 'business_ties', 'behavioral_patterns',
                'opsec_assessment',
            ]
            for dim in expected_dimensions:
                assert dim in data['breakdown'], f"Missing dimension {dim} in breakdown"
                assert 'score' in data['breakdown'][dim]
                assert 'max' in data['breakdown'][dim]
                assert 'label' in data['breakdown'][dim]
                assert 'factors' in data['breakdown'][dim]

    def test_breakdown_nonexistent(self, app, client):
        """GET /api/scoring/breakdown/<id> with unknown ID returns 404."""
        with app.app_context():
            resp = client.get('/api/scoring/breakdown/fake-id-123')
            assert resp.status_code == 404


# ========== Test 9: Partial investigation (no Phase 2/3 data) ==========

class TestPartialInvestigation:
    def test_no_phase2_data(self, app):
        """Investigation with confirmed profile but no email/phone/graph."""
        inv_id = _make_investigation_id()
        with app.app_context():
            inv = Investigation(id=inv_id, input_name='Частичный Тест', status='phase_1_complete')
            db.session.add(inv)

            profile = SocialProfile(
                investigation_id=inv_id,
                platform='vk',
                platform_id='900',
                first_name='Частичный',
                last_name='Тест',
                is_confirmed=True,
                friends_count=50,
            )
            db.session.add(profile)
            db.session.commit()

            from app.services.risk_scoring import calculate_risk_score
            result = calculate_risk_score(inv_id)

            assert result is not None
            assert result['score'] >= 0
            assert result['breakdown']['contact_exposure']['score'] == 0
            assert result['breakdown']['business_ties']['score'] == 0

    def test_no_phase3_data(self, app):
        """Investigation after Phase 2 but with no business/court records."""
        inv_id = _make_investigation_id()
        with app.app_context():
            inv = Investigation(id=inv_id, input_name='Частичный Тест 2', status='phase_2_complete')
            inv.discovered_emails = [{'email': 'a@b.com'}]
            inv.discovered_phones = [{'phone': '+79001112233'}]
            db.session.add(inv)

            profile = SocialProfile(
                investigation_id=inv_id,
                platform='vk',
                platform_id='901',
                is_confirmed=True,
                first_name='Тест',
                last_name='Тестов',
            )
            db.session.add(profile)
            db.session.commit()

            from app.services.risk_scoring import calculate_risk_score
            result = calculate_risk_score(inv_id)

            assert result['breakdown']['business_ties']['score'] == 0
            assert result['breakdown']['contact_exposure']['score'] > 0
            assert result['data_summary']['business_records'] == 0
            assert result['data_summary']['court_records'] == 0

    def test_no_confirmed_profile(self, app):
        """Investigation with profiles but none confirmed."""
        inv_id = _make_investigation_id()
        with app.app_context():
            inv = Investigation(id=inv_id, input_name='Без подтверждения', status='phase_1')
            db.session.add(inv)

            profile = SocialProfile(
                investigation_id=inv_id,
                platform='vk',
                platform_id='902',
                first_name='Тест',
                last_name='Тестов',
                is_confirmed=False,
                friends_count=500,
                photos_count=100,
            )
            db.session.add(profile)
            db.session.commit()

            from app.services.risk_scoring import calculate_risk_score
            result = calculate_risk_score(inv_id)

            # Profile completeness depends on confirmed profile — should be 0
            assert result['breakdown']['profile_completeness']['score'] == 0
            # Digital footprint still counts unconfirmed profiles for platform count
            assert result['breakdown']['digital_footprint']['score'] > 0
            # Social/behavioral/opsec depend on confirmed — should be 0
            assert result['breakdown']['social_exposure']['score'] == 0
            assert result['breakdown']['behavioral_patterns']['score'] == 0
            assert result['breakdown']['opsec_assessment']['score'] == 0


# ========== Test 10: Monotonicity — more data >= higher score ==========

class TestMonotonicity:
    def test_adding_profile_increases_score(self, app):
        """Adding a confirmed profile should increase or maintain score."""
        inv_id = _make_investigation_id()
        with app.app_context():
            inv = Investigation(id=inv_id, input_name='Моно Тест', status='phase_1')
            db.session.add(inv)
            db.session.commit()

            from app.services.risk_scoring import calculate_risk_score
            score_before = calculate_risk_score(inv_id)['score']

            # Add a confirmed profile
            profile = SocialProfile(
                investigation_id=inv_id,
                platform='vk',
                platform_id='700',
                first_name='Моно',
                last_name='Тест',
                is_confirmed=True,
                photo_url='https://vk.com/photo.jpg',
                friends_count=300,
            )
            db.session.add(profile)
            db.session.commit()

            # Clear risk_indicators to avoid double-appending issue
            inv_fresh = Investigation.query.get(inv_id)
            inv_fresh.risk_indicators = []
            db.session.commit()

            score_after = calculate_risk_score(inv_id)['score']
            assert score_after >= score_before, \
                f"Adding profile should not decrease score: {score_before} -> {score_after}"

    def test_adding_contacts_increases_score(self, app):
        """Adding discovered contacts should increase or maintain score."""
        inv_id = _make_investigation_id()
        with app.app_context():
            inv = Investigation(id=inv_id, input_name='Контакт Тест', status='phase_2')
            db.session.add(inv)
            db.session.commit()

            from app.services.risk_scoring import calculate_risk_score
            score_before = calculate_risk_score(inv_id)['score']

            inv_fresh = Investigation.query.get(inv_id)
            inv_fresh.discovered_phones = [{'phone': '+79001234567'}]
            inv_fresh.discovered_emails = [{'email': 'x@y.com'}]
            inv_fresh.risk_indicators = []
            db.session.commit()

            score_after = calculate_risk_score(inv_id)['score']
            assert score_after >= score_before, \
                f"Adding contacts should not decrease score: {score_before} -> {score_after}"

    def test_adding_business_records_increases_score(self, app):
        """Adding business records should increase or maintain score."""
        inv_id = _make_investigation_id()
        with app.app_context():
            inv = Investigation(id=inv_id, input_name='Бизнес Тест', status='phase_3')
            db.session.add(inv)
            db.session.commit()

            from app.services.risk_scoring import calculate_risk_score
            score_before = calculate_risk_score(inv_id)['score']

            for i in range(3):
                biz = BusinessRecord(
                    investigation_id=inv_id,
                    company_name=f'ООО-{i}',
                    inn=f'770099000{i}',
                    status='active',
                    source='nalog.ru',
                )
                db.session.add(biz)

            inv_fresh = Investigation.query.get(inv_id)
            inv_fresh.risk_indicators = []
            db.session.commit()

            score_after = calculate_risk_score(inv_id)['score']
            assert score_after >= score_before, \
                f"Adding business records should not decrease score: {score_before} -> {score_after}"

    def test_adding_court_records_increases_score(self, app):
        """Adding court records should increase or maintain score."""
        inv_id = _make_investigation_id()
        with app.app_context():
            inv = Investigation(id=inv_id, input_name='Суд Тест', status='phase_3')
            db.session.add(inv)
            db.session.commit()

            from app.services.risk_scoring import calculate_risk_score
            score_before = calculate_risk_score(inv_id)['score']

            for i in range(3):
                court = CourtRecord(
                    investigation_id=inv_id,
                    case_number=f'C-{i}/2025',
                    category='civil',
                    source='sudact.ru',
                )
                db.session.add(court)

            inv_fresh = Investigation.query.get(inv_id)
            inv_fresh.risk_indicators = []
            db.session.commit()

            score_after = calculate_risk_score(inv_id)['score']
            assert score_after >= score_before, \
                f"Adding court records should not decrease score: {score_before} -> {score_after}"


# ========== Test: get_score_breakdown alias ==========

class TestGetScoreBreakdown:
    def test_alias_returns_same_structure(self, app):
        """get_score_breakdown should return same structure as calculate_risk_score."""
        inv_id = _create_minimal_investigation(app)
        with app.app_context():
            from app.services.risk_scoring import calculate_risk_score, get_score_breakdown
            result = get_score_breakdown(inv_id)
            assert result is not None
            assert 'score' in result
            assert 'breakdown' in result

    def test_alias_nonexistent(self, app):
        """get_score_breakdown with bad ID returns None."""
        with app.app_context():
            from app.services.risk_scoring import get_score_breakdown
            assert get_score_breakdown('nope') is None


# ========== Test: Closed profile → better OPSEC ==========

class TestClosedProfile:
    def test_closed_profile_lower_opsec_score(self, app):
        """Closed profile should have lower OPSEC score than open profile."""
        # Open profile
        open_id = _make_investigation_id()
        with app.app_context():
            inv_open = Investigation(id=open_id, input_name='Открытый', status='phase_2')
            db.session.add(inv_open)
            p_open = SocialProfile(
                investigation_id=open_id,
                platform='vk',
                platform_id='800',
                is_confirmed=True,
                first_name='Тест',
                last_name='Открытый',
                is_closed=False,
                phone='+79001111111',
            )
            db.session.add(p_open)
            db.session.commit()

            from app.services.risk_scoring import calculate_risk_score
            open_result = calculate_risk_score(open_id)
            open_opsec = open_result['breakdown']['opsec_assessment']['score']

        # Closed profile
        closed_id = _make_investigation_id()
        with app.app_context():
            inv_closed = Investigation(id=closed_id, input_name='Закрытый', status='phase_2')
            db.session.add(inv_closed)
            p_closed = SocialProfile(
                investigation_id=closed_id,
                platform='vk',
                platform_id='801',
                is_confirmed=True,
                first_name='Тест',
                last_name='Закрытый',
                is_closed=True,
                # No phone/email visible
            )
            db.session.add(p_closed)
            db.session.commit()

            from app.services.risk_scoring import calculate_risk_score
            closed_result = calculate_risk_score(closed_id)
            closed_opsec = closed_result['breakdown']['opsec_assessment']['score']

        assert closed_opsec < open_opsec, \
            f"Closed profile opsec ({closed_opsec}) should be less than open ({open_opsec})"
