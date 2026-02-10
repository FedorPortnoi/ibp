"""
Tests for Professional Dossier Generator
==========================================
Comprehensive tests covering:
- Dossier generation with full/minimal data
- JSON export format and keys
- Route endpoints (HTML, JSON, PDF)
- Edge cases: Cyrillic, no photo, long text, nonexistent ID
- Executive summary, timeline, methodology sections
"""

import json
import uuid
import os
from datetime import datetime, timedelta

import pytest

from app import create_app, db
from app.models import (
    Investigation, SocialProfile, Friend,
    BusinessRecord, CourtRecord, Connection,
)


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture(scope='module')
def app():
    """Create application for testing with in-memory DB."""
    os.environ.pop('IBP_PASSWORD', None)
    os.environ.pop('IBP_PASSWORD_HASH', None)
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


def _make_id():
    return str(uuid.uuid4())


# ============================================================
# Helper: create minimal investigation (name only)
# ============================================================

def _create_minimal_investigation(app, name='Иванов Иван Иванович'):
    """Investigation with only a name."""
    inv_id = _make_id()
    with app.app_context():
        inv = Investigation(id=inv_id, input_name=name, status='phase_1')
        db.session.add(inv)
        db.session.commit()
    return inv_id


# ============================================================
# Helper: create fully populated investigation
# ============================================================

def _create_full_investigation(app):
    """Investigation with all phases populated and related records."""
    inv_id = _make_id()
    now = datetime.utcnow()

    with app.app_context():
        inv = Investigation(
            id=inv_id,
            input_name='Кузнецов Дмитрий Сергеевич',
            status='complete',
            confirmed_email='dmitry@example.com',
            confirmed_phone='+79161234567',
        )
        inv.discovered_emails = [
            {'email': 'dmitry@example.com', 'source': 'VK', 'confidence': 'high',
             'services': ['vk.com', 'mail.ru']},
            {'email': 'dima.k@gmail.com', 'source': 'Holehe', 'confidence': 'medium',
             'services': ['gmail']},
        ]
        inv.discovered_phones = [
            {'number': '+79161234567', 'source': 'VK API', 'confidence': 'high'},
            {'phone': '+79037654321', 'source': 'Wall regex', 'confidence': 'low'},
        ]
        inv.discovered_usernames = ['dm_kuznetsov', 'dima_k2000']
        inv.risk_indicators = [
            {'severity': 'high', 'category': 'Судебные дела',
             'description': 'Ответчик по гражданскому иску'},
            {'severity': 'medium', 'category': 'Финансы',
             'description': 'Связь с ликвидированной компанией'},
            {'severity': 'low', 'category': 'Социальные сети',
             'description': 'Закрытый профиль'},
        ]
        inv.property_records = [
            {'debtor_name': 'Кузнецов Д.С.', 'amount': '50000',
             'status': 'Активно', 'department': 'ОСП г. Москвы'},
        ]
        inv.group_memberships = [
            {'name': 'Python Developers'},
            {'name': 'Москва Новости'},
        ]

        db.session.add(inv)
        db.session.flush()

        # Confirmed VK profile
        profile = SocialProfile(
            investigation_id=inv_id,
            platform='vk',
            platform_id='12345678',
            username='dm_kuznetsov',
            profile_url='https://vk.com/id12345678',
            first_name='Дмитрий',
            last_name='Кузнецов',
            display_name='Дмитрий Кузнецов',
            photo_url='https://example.com/photo.jpg',
            bio='Программист, люблю Python и кошек',
            city='Москва',
            country='Россия',
            birth_date='15.3.1990',
            age=36,
            gender='male',
            friends_count=350,
            followers_count=120,
            is_confirmed=True,
            confirmed_at=now - timedelta(hours=2),
            discovered_at=now - timedelta(hours=3),
            confidence_score=85.0,
        )
        profile.education = [
            {'university': 'МГУ', 'faculty': 'ВМК', 'graduation': 2012},
        ]
        profile.career = [
            {'company': 'Яндекс', 'position': 'Разработчик'},
        ]
        db.session.add(profile)
        db.session.flush()

        # Unconfirmed profile
        profile2 = SocialProfile(
            investigation_id=inv_id,
            platform='ok',
            platform_id='9999999',
            username='dima_k2000',
            profile_url='https://ok.ru/profile/9999999',
            first_name='Дмитрий',
            last_name='К.',
            display_name='Дмитрий К.',
            city='Москва',
            is_confirmed=False,
            is_rejected=False,
            discovered_at=now - timedelta(hours=2),
            confidence_score=40.0,
        )
        db.session.add(profile2)

        # Friends
        for i in range(20):
            friend = Friend(
                investigation_id=inv_id,
                parent_profile_id=profile.id,
                platform='vk',
                platform_id=str(100000 + i),
                first_name=f'Друг_{i}',
                last_name=f'Фамилия_{i}',
                city='Москва' if i < 10 else 'Санкт-Петербург',
                centrality_score=0.5 - i * 0.02,
                community_id=i % 3,
                is_flagged=(i == 0),
                discovered_at=now - timedelta(hours=1),
            )
            db.session.add(friend)

        # Business records
        br1 = BusinessRecord(
            investigation_id=inv_id,
            inn='7712345678',
            ogrn='1177700000001',
            company_name='ООО "ТехноПлюс"',
            short_name='ТехноПлюс',
            company_type='ooo',
            status='Действующая',
            registration_date=datetime(2017, 5, 15).date(),
            legal_address='г. Москва, ул. Ленина, д. 10',
            person_name='Кузнецов Дмитрий Сергеевич',
            role='director',
            source='nalog.ru',
            discovered_at=now - timedelta(minutes=30),
        )
        br2 = BusinessRecord(
            investigation_id=inv_id,
            inn='7798765432',
            ogrn='1177700000002',
            company_name='ООО "СтройМастер"',
            short_name='СтройМастер',
            company_type='ooo',
            status='Ликвидирована',
            registration_date=datetime(2015, 1, 20).date(),
            liquidation_date=datetime(2020, 6, 30).date(),
            legal_address='г. Москва, ул. Строителей, д. 5',
            person_name='Кузнецов Дмитрий Сергеевич',
            role='founder',
            source='nalog.ru',
            discovered_at=now - timedelta(minutes=25),
        )
        db.session.add_all([br1, br2])

        # Court records
        cr1 = CourtRecord(
            investigation_id=inv_id,
            case_number='2-1234/2024',
            category='civil',
            status='Рассмотрено',
            court_name='Тверской районный суд г. Москвы',
            person_name='Кузнецов Д.С.',
            person_role='defendant',
            subject='Взыскание задолженности по договору',
            claim_amount=500000.0,
            decision_date=datetime(2024, 3, 15).date(),
            source='sudact.ru',
            source_url='https://sudact.ru/doc/12345',
            is_defendant=True,
            is_negative=True,
            risk_score=40.0,
            discovered_at=now - timedelta(minutes=20),
        )
        db.session.add(cr1)

        # Connections
        conn = Connection(
            investigation_id=inv_id,
            source_type='person',
            source_id='vk_12345678',
            source_name='Кузнецов Дмитрий',
            target_type='company',
            target_id='inn_7712345678',
            target_name='ООО "ТехноПлюс"',
            connection_type='colleague',
            strength=0.9,
            platform='vk',
        )
        db.session.add(conn)

        db.session.commit()

    return inv_id


# ============================================================
# 1. Full dossier generation — all 9 sections present
# ============================================================

class TestFullDossierGeneration:
    """Test dossier generation with fully populated investigation."""

    def test_all_sections_present_in_html(self, app, client):
        """Verify all 9 sections appear in the rendered HTML."""
        inv_id = _create_full_investigation(app)

        with app.app_context():
            resp = client.get(f'/dossier/{inv_id}')

        assert resp.status_code == 200
        html = resp.data.decode('utf-8')

        # Section headers (numbered 1-9 in template)
        assert 'Резюме расследования' in html       # Section 1
        assert 'Персональные данные' in html         # Section 2
        assert 'Цифровое присутствие' in html        # Section 3
        assert 'Контактная информация' in html       # Section 4
        assert 'Социальные связи' in html            # Section 5
        assert 'Оценка рисков' in html               # Section 6
        assert 'Бизнес и юридические связи' in html  # Section 7
        assert 'Хронология расследования' in html    # Section 8
        assert 'Методология и источники' in html     # Section 9

    def test_cover_page_data(self, app, client):
        """Cover page shows target name, stats, and confidence."""
        inv_id = _create_full_investigation(app)

        with app.app_context():
            resp = client.get(f'/dossier/{inv_id}')

        html = resp.data.decode('utf-8')

        assert 'Кузнецов Дмитрий Сергеевич' in html
        assert 'КОНФИДЕНЦИАЛЬНО' in html
        assert 'Досье расследования' in html
        # Stats area
        assert 'Профили' in html
        assert 'Контакты' in html
        assert 'Связи' in html
        assert 'Компании' in html
        assert 'Суд. дела' in html

    def test_profiles_section_has_confirmed_badge(self, app, client):
        """Confirmed profiles show the confirmation badge."""
        inv_id = _create_full_investigation(app)

        with app.app_context():
            resp = client.get(f'/dossier/{inv_id}')

        html = resp.data.decode('utf-8')
        assert 'Подтверждён' in html

    def test_contacts_section_shows_phones_and_emails(self, app, client):
        """Phones and emails render in the contacts section."""
        inv_id = _create_full_investigation(app)

        with app.app_context():
            resp = client.get(f'/dossier/{inv_id}')

        html = resp.data.decode('utf-8')
        assert '+79161234567' in html
        assert '+79037654321' in html
        assert 'dmitry@example.com' in html
        assert 'dima.k@gmail.com' in html

    def test_business_records_render(self, app, client):
        """Business records show company names, INN, roles."""
        inv_id = _create_full_investigation(app)

        with app.app_context():
            resp = client.get(f'/dossier/{inv_id}')

        html = resp.data.decode('utf-8')
        assert 'ТехноПлюс' in html
        assert 'СтройМастер' in html
        assert '7712345678' in html
        assert 'Директор' in html  # role_display for 'director'

    def test_court_records_render(self, app, client):
        """Court records show case number, court, details."""
        inv_id = _create_full_investigation(app)

        with app.app_context():
            resp = client.get(f'/dossier/{inv_id}')

        html = resp.data.decode('utf-8')
        assert '2-1234/2024' in html
        assert 'Тверской районный суд' in html

    def test_risk_level_high(self, app, client):
        """Risk assessment shows HIGH when high-severity indicators exist."""
        inv_id = _create_full_investigation(app)

        with app.app_context():
            resp = client.get(f'/dossier/{inv_id}')

        html = resp.data.decode('utf-8')
        assert 'ВЫСОКИЙ' in html

    def test_friends_sample_in_social(self, app, client):
        """Social section shows top friends by centrality."""
        inv_id = _create_full_investigation(app)

        with app.app_context():
            resp = client.get(f'/dossier/{inv_id}')

        html = resp.data.decode('utf-8')
        # First friend is flagged
        assert '[ОТМЕЧЕН]' in html
        assert 'Друг_0' in html

    def test_enforcement_records_render(self, app, client):
        """Enforcement records (FSSP) render in business/legal section."""
        inv_id = _create_full_investigation(app)

        with app.app_context():
            resp = client.get(f'/dossier/{inv_id}')

        html = resp.data.decode('utf-8')
        assert 'Исполнительные производства' in html
        assert '50000' in html


# ============================================================
# 2. Minimal dossier — empty sections show placeholder
# ============================================================

class TestMinimalDossier:
    """Test dossier with minimal data (name only)."""

    def test_minimal_returns_200(self, app, client):
        """Even minimal investigation produces a valid dossier."""
        inv_id = _create_minimal_investigation(app)

        with app.app_context():
            resp = client.get(f'/dossier/{inv_id}')

        assert resp.status_code == 200

    def test_empty_sections_show_placeholder(self, app, client):
        """Empty sections display 'Данные не обнаружены'."""
        inv_id = _create_minimal_investigation(app)

        with app.app_context():
            resp = client.get(f'/dossier/{inv_id}')

        html = resp.data.decode('utf-8')
        # Expect multiple "Данные не обнаружены" for empty sections
        assert html.count('Данные не обнаружены') >= 3

    def test_minimal_has_all_section_headers(self, app, client):
        """Even with no data, all section headers should appear."""
        inv_id = _create_minimal_investigation(app)

        with app.app_context():
            resp = client.get(f'/dossier/{inv_id}')

        html = resp.data.decode('utf-8')
        assert 'Резюме расследования' in html
        assert 'Персональные данные' in html
        assert 'Цифровое присутствие' in html
        assert 'Контактная информация' in html
        assert 'Социальные связи' in html
        assert 'Оценка рисков' in html
        assert 'Бизнес и юридические связи' in html
        assert 'Хронология расследования' in html
        assert 'Методология и источники' in html

    def test_minimal_confidence_low(self, app):
        """Minimal investigation yields low confidence score."""
        inv_id = _create_minimal_investigation(app)

        with app.app_context():
            from app.services.dossier_generator import dossier_generator
            dossier = dossier_generator.generate_dossier(inv_id)

        assert dossier['confidence'] < 30

    def test_minimal_risk_none(self, app):
        """Minimal investigation yields no risk."""
        inv_id = _create_minimal_investigation(app)

        with app.app_context():
            from app.services.dossier_generator import dossier_generator
            dossier = dossier_generator.generate_dossier(inv_id)

        assert dossier['risk_level'] == 'none'
        assert dossier['risk_label'] == 'НЕ ВЫЯВЛЕН'


# ============================================================
# 3. JSON export
# ============================================================

class TestJSONExport:
    """Test JSON dossier export."""

    def test_json_valid_structure(self, app):
        """JSON export has all expected top-level keys."""
        inv_id = _create_full_investigation(app)

        with app.app_context():
            from app.services.dossier_generator import dossier_generator
            data = dossier_generator.generate_json(inv_id)

        expected_keys = {
            'meta', 'executive_summary', 'personal_data',
            'profiles', 'contacts', 'social_network',
            'risk_assessment', 'business_records', 'court_records',
            'enforcement_records', 'methodology',
        }
        assert expected_keys.issubset(set(data.keys())), \
            f"Missing keys: {expected_keys - set(data.keys())}"

    def test_json_meta_fields(self, app):
        """Meta section has required fields."""
        inv_id = _create_full_investigation(app)

        with app.app_context():
            from app.services.dossier_generator import dossier_generator
            data = dossier_generator.generate_json(inv_id)

        meta = data['meta']
        assert meta['investigation_id'] == inv_id
        assert meta['target_name'] == 'Кузнецов Дмитрий Сергеевич'
        assert meta['status'] == 'complete'
        assert 'confidence' in meta
        assert 'risk_level' in meta
        assert meta['source'] == 'IBP - Identity-Based Profiler'

    def test_json_contacts_section(self, app):
        """Contacts section has phones and emails."""
        inv_id = _create_full_investigation(app)

        with app.app_context():
            from app.services.dossier_generator import dossier_generator
            data = dossier_generator.generate_json(inv_id)

        contacts = data['contacts']
        assert len(contacts['phones']) >= 2
        assert len(contacts['emails']) >= 2

    def test_json_business_records_serializable(self, app):
        """Business records convert to dicts (to_dict called)."""
        inv_id = _create_full_investigation(app)

        with app.app_context():
            from app.services.dossier_generator import dossier_generator
            data = dossier_generator.generate_json(inv_id)

        assert len(data['business_records']) >= 1
        first_br = data['business_records'][0]
        assert isinstance(first_br, dict)
        assert 'inn' in first_br

    def test_json_court_records_serializable(self, app):
        """Court records convert to dicts."""
        inv_id = _create_full_investigation(app)

        with app.app_context():
            from app.services.dossier_generator import dossier_generator
            data = dossier_generator.generate_json(inv_id)

        assert len(data['court_records']) >= 1
        first_cr = data['court_records'][0]
        assert isinstance(first_cr, dict)
        assert 'case_number' in first_cr

    def test_json_nonexistent_returns_error(self, app):
        """JSON export for nonexistent investigation returns error."""
        with app.app_context():
            from app.services.dossier_generator import dossier_generator
            data = dossier_generator.generate_json('nonexistent-id-12345')

        assert 'error' in data

    def test_json_is_valid_json(self, app):
        """Full JSON export can be serialized to valid JSON string."""
        inv_id = _create_full_investigation(app)

        with app.app_context():
            from app.services.dossier_generator import dossier_generator
            data = dossier_generator.generate_json(inv_id)

        # Should not raise
        json_str = json.dumps(data, ensure_ascii=False, indent=2, default=str)
        parsed = json.loads(json_str)
        assert parsed['meta']['investigation_id'] == inv_id


# ============================================================
# 4. Route: GET /dossier/<id> returns 200
# ============================================================

class TestDossierRoutes:
    """Test dossier HTTP routes."""

    def test_view_returns_200(self, app, client):
        """GET /dossier/<valid_id> returns 200."""
        inv_id = _create_full_investigation(app)

        with app.app_context():
            resp = client.get(f'/dossier/{inv_id}')

        assert resp.status_code == 200

    def test_view_content_type_html(self, app, client):
        """View route returns HTML content type."""
        inv_id = _create_full_investigation(app)

        with app.app_context():
            resp = client.get(f'/dossier/{inv_id}')

        assert 'text/html' in resp.content_type


# ============================================================
# 5. Route: GET /dossier/<id>/json returns valid JSON
# ============================================================

class TestJSONRoute:
    """Test JSON export route."""

    def test_json_route_returns_json(self, app, client):
        """GET /dossier/<id>/json returns JSON content type."""
        inv_id = _create_full_investigation(app)

        with app.app_context():
            resp = client.get(f'/dossier/{inv_id}/json')

        assert resp.status_code == 200
        assert 'application/json' in resp.content_type

    def test_json_route_parseable(self, app, client):
        """JSON response is parseable."""
        inv_id = _create_full_investigation(app)

        with app.app_context():
            resp = client.get(f'/dossier/{inv_id}/json')

        data = json.loads(resp.data.decode('utf-8'))
        assert 'meta' in data
        assert data['meta']['investigation_id'] == inv_id

    def test_json_route_has_content_disposition(self, app, client):
        """JSON route sets Content-Disposition for download."""
        inv_id = _create_full_investigation(app)

        with app.app_context():
            resp = client.get(f'/dossier/{inv_id}/json')

        cd = resp.headers.get('Content-Disposition', '')
        assert 'attachment' in cd
        assert 'dossier_' in cd
        assert '.json' in cd


# ============================================================
# 6. Route: GET /dossier/<id>/pdf returns 200
# ============================================================

class TestPDFRoute:
    """Test PDF export route (WeasyPrint or HTML fallback)."""

    def test_pdf_route_returns_200(self, app, client):
        """PDF route returns 200 (WeasyPrint or fallback)."""
        inv_id = _create_full_investigation(app)

        with app.app_context():
            resp = client.get(f'/dossier/{inv_id}/pdf')

        assert resp.status_code == 200

    def test_pdf_route_content_type(self, app, client):
        """PDF route returns either PDF or HTML content type."""
        inv_id = _create_full_investigation(app)

        with app.app_context():
            resp = client.get(f'/dossier/{inv_id}/pdf')

        ct = resp.content_type
        assert 'application/pdf' in ct or 'text/html' in ct

    def test_pdf_fallback_has_print_trigger(self, app, client):
        """If fallback to HTML, it should have print trigger script."""
        inv_id = _create_full_investigation(app)

        with app.app_context():
            resp = client.get(f'/dossier/{inv_id}/pdf')

        if 'text/html' in resp.content_type:
            html = resp.data.decode('utf-8')
            assert 'window.print()' in html


# ============================================================
# 7. Route: GET /dossier/nonexistent-id returns 404
# ============================================================

class TestNonexistentDossier:
    """Test 404 handling."""

    def test_view_nonexistent_returns_404(self, app, client):
        """GET /dossier/<invalid_id> returns 404."""
        with app.app_context():
            resp = client.get('/dossier/nonexistent-uuid-12345')

        assert resp.status_code == 404

    def test_json_nonexistent_returns_404(self, app, client):
        """GET /dossier/<invalid_id>/json returns 404."""
        with app.app_context():
            resp = client.get('/dossier/nonexistent-uuid-12345/json')

        assert resp.status_code == 404

    def test_pdf_nonexistent_returns_404(self, app, client):
        """GET /dossier/<invalid_id>/pdf returns 404."""
        with app.app_context():
            resp = client.get('/dossier/nonexistent-uuid-12345/pdf')

        assert resp.status_code == 404


# ============================================================
# 8. Edge case: Cyrillic names and special characters
# ============================================================

class TestCyrillicAndSpecialChars:
    """Test Cyrillic names render correctly."""

    def test_cyrillic_name_renders(self, app, client):
        """Cyrillic name displays without encoding issues."""
        inv_id = _create_minimal_investigation(app, name='Ёлкина Анастасия Юрьевна')

        with app.app_context():
            resp = client.get(f'/dossier/{inv_id}')

        html = resp.data.decode('utf-8')
        assert 'Ёлкина Анастасия Юрьевна' in html

    def test_special_chars_in_name(self, app, client):
        """Names with hyphens, apostrophes render correctly."""
        inv_id = _create_minimal_investigation(app, name="Салтыков-Щедрин Михаил О'Браен")

        with app.app_context():
            resp = client.get(f'/dossier/{inv_id}')

        html = resp.data.decode('utf-8')
        # HTML escaping of apostrophe: &#39; or &#x27; or literal '
        assert 'Салтыков-Щедрин' in html

    def test_xss_safe_name(self, app, client):
        """XSS payloads in name are escaped."""
        inv_id = _create_minimal_investigation(app, name='<script>alert("xss")</script>')

        with app.app_context():
            resp = client.get(f'/dossier/{inv_id}')

        html = resp.data.decode('utf-8')
        # Jinja2 auto-escapes by default
        assert '<script>alert("xss")</script>' not in html
        assert '&lt;script&gt;' in html


# ============================================================
# 9. Edge case: no photo — placeholder handling
# ============================================================

class TestNoPhoto:
    """Test investigation with no profile photo."""

    def test_no_photo_shows_placeholder(self, app, client):
        """When no photo, cover shows placeholder text."""
        inv_id = _create_minimal_investigation(app)

        with app.app_context():
            resp = client.get(f'/dossier/{inv_id}')

        html = resp.data.decode('utf-8')
        assert 'НЕТ ФОТО' in html

    def test_no_confirmed_profile_graceful(self, app):
        """Dossier generates without confirmed profile."""
        inv_id = _create_minimal_investigation(app)

        with app.app_context():
            from app.services.dossier_generator import dossier_generator
            dossier = dossier_generator.generate_dossier(inv_id)

        assert dossier['confirmed_profile'] is None
        assert 'error' not in dossier


# ============================================================
# 10. Edge case: very long text fields — no 500 error
# ============================================================

class TestLongTextFields:
    """Test that very long text fields don't break rendering."""

    def test_long_name_no_500(self, app, client):
        """Very long name doesn't cause a server error."""
        long_name = 'А' * 500
        inv_id = _create_minimal_investigation(app, name=long_name)

        with app.app_context():
            resp = client.get(f'/dossier/{inv_id}')

        assert resp.status_code == 200

    def test_long_bio_no_500(self, app):
        """Very long bio field doesn't cause errors."""
        inv_id = _make_id()
        with app.app_context():
            inv = Investigation(id=inv_id, input_name='Тест', status='phase_1')
            db.session.add(inv)
            db.session.flush()

            profile = SocialProfile(
                investigation_id=inv_id,
                platform='vk',
                platform_id='11111',
                first_name='Тест',
                last_name='Тестов',
                bio='Б' * 5000,
                is_confirmed=True,
                confirmed_at=datetime.utcnow(),
            )
            db.session.add(profile)
            db.session.commit()

            from app.services.dossier_generator import dossier_generator
            dossier = dossier_generator.generate_dossier(inv_id)

        assert 'error' not in dossier

    def test_long_bio_renders_html(self, app, client):
        """Very long bio renders without 500 in HTTP."""
        inv_id = _make_id()
        with app.app_context():
            inv = Investigation(id=inv_id, input_name='Тест', status='phase_1')
            db.session.add(inv)
            db.session.flush()

            profile = SocialProfile(
                investigation_id=inv_id,
                platform='vk',
                platform_id='22222',
                first_name='Тест',
                last_name='Длинный',
                bio='Я ' * 3000,
                is_confirmed=True,
                confirmed_at=datetime.utcnow(),
            )
            db.session.add(profile)
            db.session.commit()

            resp = client.get(f'/dossier/{inv_id}')

        assert resp.status_code == 200


# ============================================================
# 11. Executive summary generation
# ============================================================

class TestExecutiveSummary:
    """Test executive summary content."""

    def test_summary_non_empty(self, app):
        """Executive summary is non-empty Russian text."""
        inv_id = _create_full_investigation(app)

        with app.app_context():
            from app.services.dossier_generator import dossier_generator
            dossier = dossier_generator.generate_dossier(inv_id)

        summary = dossier['summary']
        assert len(summary) > 50
        assert 'расследования' in summary.lower() or 'анализ' in summary.lower()

    def test_summary_mentions_target_name(self, app):
        """Summary includes the target's name."""
        inv_id = _create_full_investigation(app)

        with app.app_context():
            from app.services.dossier_generator import dossier_generator
            dossier = dossier_generator.generate_dossier(inv_id)

        assert 'Кузнецов Дмитрий Сергеевич' in dossier['summary']

    def test_summary_mentions_confirmed_profile(self, app):
        """Summary mentions confirmed profile when one exists."""
        inv_id = _create_full_investigation(app)

        with app.app_context():
            from app.services.dossier_generator import dossier_generator
            dossier = dossier_generator.generate_dossier(inv_id)

        summary = dossier['summary']
        assert 'Подтверждён профиль' in summary or 'ВКонтакте' in summary

    def test_summary_mentions_contacts(self, app):
        """Summary mentions discovered contacts."""
        inv_id = _create_full_investigation(app)

        with app.app_context():
            from app.services.dossier_generator import dossier_generator
            dossier = dossier_generator.generate_dossier(inv_id)

        summary = dossier['summary']
        assert 'телефон' in summary.lower() or 'почт' in summary.lower()

    def test_summary_mentions_risk(self, app):
        """Summary mentions risk level."""
        inv_id = _create_full_investigation(app)

        with app.app_context():
            from app.services.dossier_generator import dossier_generator
            dossier = dossier_generator.generate_dossier(inv_id)

        assert 'ВЫСОКИЙ' in dossier['summary']

    def test_summary_minimal_investigation(self, app):
        """Summary works for minimal investigation too."""
        inv_id = _create_minimal_investigation(app)

        with app.app_context():
            from app.services.dossier_generator import dossier_generator
            dossier = dossier_generator.generate_dossier(inv_id)

        summary = dossier['summary']
        assert len(summary) > 20
        assert 'Иванов Иван Иванович' in summary


# ============================================================
# 12. Timeline section
# ============================================================

class TestTimeline:
    """Test timeline section generation."""

    def test_timeline_has_investigation_start(self, app):
        """Timeline includes investigation creation event."""
        inv_id = _create_full_investigation(app)

        with app.app_context():
            from app.services.dossier_generator import dossier_generator
            dossier = dossier_generator.generate_dossier(inv_id)

        timeline = dossier['timeline']
        labels = [e['label'] for e in timeline]
        assert 'Начало расследования' in labels

    def test_timeline_has_profile_discovery(self, app):
        """Timeline includes profile discovery event."""
        inv_id = _create_full_investigation(app)

        with app.app_context():
            from app.services.dossier_generator import dossier_generator
            dossier = dossier_generator.generate_dossier(inv_id)

        timeline = dossier['timeline']
        labels = [e['label'] for e in timeline]
        has_profile = any('профиль' in l.lower() for l in labels)
        assert has_profile, f"No profile event in timeline: {labels}"

    def test_timeline_sorted_by_date(self, app):
        """Timeline events are sorted chronologically."""
        inv_id = _create_full_investigation(app)

        with app.app_context():
            from app.services.dossier_generator import dossier_generator
            dossier = dossier_generator.generate_dossier(inv_id)

        timeline = dossier['timeline']
        dates = [e['date'] for e in timeline if e.get('date')]
        for i in range(len(dates) - 1):
            assert dates[i] <= dates[i + 1], "Timeline not sorted"

    def test_timeline_renders_in_html(self, app, client):
        """Timeline section renders dates in HTML."""
        inv_id = _create_full_investigation(app)

        with app.app_context():
            resp = client.get(f'/dossier/{inv_id}')

        html = resp.data.decode('utf-8')
        assert 'Начало расследования' in html

    def test_minimal_timeline(self, app):
        """Minimal investigation still has at least one timeline event."""
        inv_id = _create_minimal_investigation(app)

        with app.app_context():
            from app.services.dossier_generator import dossier_generator
            dossier = dossier_generator.generate_dossier(inv_id)

        timeline = dossier['timeline']
        assert len(timeline) >= 1


# ============================================================
# 13. Methodology section
# ============================================================

class TestMethodology:
    """Test methodology section listing tools/sources."""

    def test_methodology_lists_used_tools(self, app):
        """Methodology includes tools that were used."""
        inv_id = _create_full_investigation(app)

        with app.app_context():
            from app.services.dossier_generator import dossier_generator
            dossier = dossier_generator.generate_dossier(inv_id)

        methodology = dossier['methodology']
        used_tools = [m['tool'] for m in methodology if m['used']]
        assert len(used_tools) > 0, "No used tools in methodology"

    def test_methodology_includes_vk_search(self, app):
        """VK People Search marked as used when profiles exist."""
        inv_id = _create_full_investigation(app)

        with app.app_context():
            from app.services.dossier_generator import dossier_generator
            dossier = dossier_generator.generate_dossier(inv_id)

        methodology = dossier['methodology']
        vk_method = next((m for m in methodology if 'VK People Search' in m['tool']), None)
        assert vk_method is not None
        assert vk_method['used'] is True

    def test_methodology_includes_egrul(self, app):
        """EGRUL marked as used when business records exist."""
        inv_id = _create_full_investigation(app)

        with app.app_context():
            from app.services.dossier_generator import dossier_generator
            dossier = dossier_generator.generate_dossier(inv_id)

        methodology = dossier['methodology']
        egrul = next((m for m in methodology if 'ЕГРЮЛ' in m['tool'] or 'nalog' in m['tool'].lower()), None)
        assert egrul is not None
        assert egrul['used'] is True

    def test_methodology_includes_sudact(self, app):
        """Sudact marked as used when court records exist."""
        inv_id = _create_full_investigation(app)

        with app.app_context():
            from app.services.dossier_generator import dossier_generator
            dossier = dossier_generator.generate_dossier(inv_id)

        methodology = dossier['methodology']
        sudact = next((m for m in methodology if 'sudact' in m['tool'].lower() or 'Судебные' in m['description']), None)
        assert sudact is not None
        assert sudact['used'] is True

    def test_methodology_includes_network_analysis(self, app):
        """NetworkX/Louvain marked as used when friends exist."""
        inv_id = _create_full_investigation(app)

        with app.app_context():
            from app.services.dossier_generator import dossier_generator
            dossier = dossier_generator.generate_dossier(inv_id)

        methodology = dossier['methodology']
        network = next((m for m in methodology if 'NetworkX' in m['tool']), None)
        assert network is not None
        assert network['used'] is True

    def test_methodology_renders_in_html(self, app, client):
        """Methodology section shows tools in HTML."""
        inv_id = _create_full_investigation(app)

        with app.app_context():
            resp = client.get(f'/dossier/{inv_id}')

        html = resp.data.decode('utf-8')
        assert 'VK People Search' in html
        assert 'nalog.ru' in html or 'ЕГРЮЛ' in html

    def test_minimal_methodology_all_unused(self, app):
        """Minimal investigation has all tools marked as unused."""
        inv_id = _create_minimal_investigation(app)

        with app.app_context():
            from app.services.dossier_generator import dossier_generator
            dossier = dossier_generator.generate_dossier(inv_id)

        methodology = dossier['methodology']
        used_tools = [m for m in methodology if m['used']]
        assert len(used_tools) == 0


# ============================================================
# 14. Confidence scoring
# ============================================================

class TestConfidenceScoring:
    """Test confidence calculation logic."""

    def test_full_investigation_high_confidence(self, app):
        """Full investigation has high confidence."""
        inv_id = _create_full_investigation(app)

        with app.app_context():
            from app.services.dossier_generator import dossier_generator
            dossier = dossier_generator.generate_dossier(inv_id)

        # With confirmed profile + photo + city + phones + emails + business + court + friends
        assert dossier['confidence'] >= 50

    def test_confidence_capped_at_100(self, app):
        """Confidence never exceeds 100."""
        inv_id = _create_full_investigation(app)

        with app.app_context():
            from app.services.dossier_generator import dossier_generator
            dossier = dossier_generator.generate_dossier(inv_id)

        assert dossier['confidence'] <= 100


# ============================================================
# 15. DossierGenerator unit tests
# ============================================================

class TestDossierGeneratorUnit:
    """Unit tests for DossierGenerator methods."""

    def test_generate_dossier_nonexistent(self, app):
        """generate_dossier returns error for nonexistent investigation."""
        with app.app_context():
            from app.services.dossier_generator import dossier_generator
            result = dossier_generator.generate_dossier('does-not-exist-123')

        assert 'error' in result
        assert 'не найдено' in result['error'].lower() or 'Расследование' in result['error']

    def test_generate_dossier_returns_all_keys(self, app):
        """generate_dossier returns dict with all expected keys."""
        inv_id = _create_full_investigation(app)

        with app.app_context():
            from app.services.dossier_generator import dossier_generator
            dossier = dossier_generator.generate_dossier(inv_id)

        expected = {
            'investigation', 'investigation_id', 'target_name', 'status',
            'created_at', 'confirmed_profile', 'profiles', 'all_profiles',
            'phones', 'emails', 'aliases', 'business_records',
            'active_business_count', 'court_records', 'enforcement_records',
            'group_memberships', 'friends', 'friends_sample', 'friends_count',
            'connections', 'risk_indicators', 'risk_level', 'risk_label',
            'confidence', 'summary', 'timeline', 'methodology', 'generated_at',
        }
        assert expected.issubset(set(dossier.keys())), \
            f"Missing: {expected - set(dossier.keys())}"

    def test_phones_normalized_from_dict(self, app):
        """Phone dicts normalize to number/source/confidence."""
        inv_id = _create_full_investigation(app)

        with app.app_context():
            from app.services.dossier_generator import dossier_generator
            dossier = dossier_generator.generate_dossier(inv_id)

        phones = dossier['phones']
        assert len(phones) >= 2
        for p in phones:
            assert 'number' in p
            assert p['number']  # non-empty

    def test_emails_normalized_from_dict(self, app):
        """Email dicts normalize to email/source/confidence/services."""
        inv_id = _create_full_investigation(app)

        with app.app_context():
            from app.services.dossier_generator import dossier_generator
            dossier = dossier_generator.generate_dossier(inv_id)

        emails = dossier['emails']
        assert len(emails) >= 2
        for e in emails:
            assert 'email' in e
            assert e['email']

    def test_friends_sample_max_15(self, app):
        """Friends sample limited to top 15 by centrality."""
        inv_id = _create_full_investigation(app)

        with app.app_context():
            from app.services.dossier_generator import dossier_generator
            dossier = dossier_generator.generate_dossier(inv_id)

        assert len(dossier['friends_sample']) <= 15
        assert dossier['friends_count'] == 20  # We created 20

    def test_active_business_count(self, app):
        """Active business count reflects is_active property."""
        inv_id = _create_full_investigation(app)

        with app.app_context():
            from app.services.dossier_generator import dossier_generator
            dossier = dossier_generator.generate_dossier(inv_id)

        # One active ('Действующая'), one liquidated ('Ликвидирована')
        assert dossier['active_business_count'] == 1
