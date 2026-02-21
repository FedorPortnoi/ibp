"""
Unit tests for ContactDiscoveryService (Stage 4).

Tests contact extraction from VK, Telegram, business records,
email guessing, deduplication, and Holehe verification — all with mocks.
"""

import os
import pytest
from unittest.mock import patch, MagicMock

os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-unit-tests')

from app.services.candidate.contact_discovery import (
    ContactDiscoveryService,
    DiscoveredPhone,
    DiscoveredEmail,
    _confidence_rank,
    PHONE_PATTERN,
    EMAIL_PATTERN,
)


# ── Helpers ──────────────────────────────────────────────────────────

class FakeCheck:
    """Minimal mock of CandidateCheck for unit tests."""

    def __init__(self, **kwargs):
        self.full_name = kwargs.get('full_name', 'Иванов Иван Иванович')
        self.inn = kwargs.get('inn', None)
        self.date_of_birth = kwargs.get('date_of_birth', None)
        self.phone = kwargs.get('phone', None)
        self.email = kwargs.get('email', None)
        self.social_media_profiles = kwargs.get('social_media_profiles', [])
        self.business_records = kwargs.get('business_records', [])
        self.fssp_records = kwargs.get('fssp_records', [])


# ── VK Extraction Tests ─────────────────────────────────────────────

class TestVKExtraction:

    @patch.dict(os.environ, {'VK_SERVICE_TOKEN': 'test_token'})
    @patch('app.services.candidate.contact_discovery.ContactDiscoveryService._vk_api_get_contacts')
    def test_vk_profile_with_mobile_phone(self, mock_vk_api):
        """VK profile with visible mobile_phone field → phone extracted."""
        mock_vk_api.return_value = [{
            'mobile_phone': '+7 (916) 123-45-67',
            'home_phone': '',
            'site': '',
            'about': '',
            'status': '',
        }]

        check = FakeCheck(
            social_media_profiles=[{
                'platform': 'vk',
                'url': 'https://vk.com/id12345',
                'display_name': 'Иван Иванов',
                'username': 'id12345',
            }],
        )

        svc = ContactDiscoveryService()
        result = svc.discover(check)
        phones = result['phones']

        assert len(phones) >= 1
        phone_numbers = [p['number'] for p in phones]
        assert '+79161234567' in phone_numbers

        # Check confidence
        for p in phones:
            if p['number'] == '+79161234567':
                assert p['confidence'] == 'высокая'
                assert p['source'] == 'vk_profile'

    @patch.dict(os.environ, {'VK_SERVICE_TOKEN': 'test_token'})
    @patch('app.services.candidate.contact_discovery.ContactDiscoveryService._vk_api_get_contacts')
    def test_vk_profile_phone_in_bio(self, mock_vk_api):
        """VK profile with phone embedded in about text → regex extraction."""
        mock_vk_api.return_value = [{
            'mobile_phone': '',
            'home_phone': '',
            'site': '',
            'about': 'Звоните: +7-916-123-45-67, пишите на почту',
            'status': '',
        }]

        check = FakeCheck(
            social_media_profiles=[{
                'platform': 'vk',
                'url': 'https://vk.com/testuser',
                'display_name': 'Тест Тестов',
                'username': 'testuser',
            }],
        )

        svc = ContactDiscoveryService()
        result = svc.discover(check)
        phones = result['phones']
        phone_numbers = [p['number'] for p in phones]
        assert '+79161234567' in phone_numbers

    @patch.dict(os.environ, {'VK_SERVICE_TOKEN': 'test_token'})
    @patch('app.services.candidate.contact_discovery.ContactDiscoveryService._vk_api_get_contacts')
    def test_vk_profile_email_in_site(self, mock_vk_api):
        """VK profile with email in site field → email extracted."""
        mock_vk_api.return_value = [{
            'mobile_phone': '',
            'home_phone': '',
            'site': 'test@gmail.com',
            'about': '',
            'status': '',
        }]

        check = FakeCheck(
            social_media_profiles=[{
                'platform': 'vk',
                'url': 'https://vk.com/testuser',
                'display_name': 'Тест',
                'username': 'testuser',
            }],
        )

        svc = ContactDiscoveryService()
        result = svc.discover(check)
        emails = result['emails']
        email_addrs = [e['email'] for e in emails]
        assert 'test@gmail.com' in email_addrs

    @patch.dict(os.environ, {}, clear=False)
    def test_missing_vk_token_skips(self):
        """Missing VK token → VK step skipped, no crash."""
        # Remove token if set
        env = os.environ.copy()
        env.pop('VK_SERVICE_TOKEN', None)
        env.pop('VK_TOKEN', None)

        with patch.dict(os.environ, env, clear=True):
            check = FakeCheck(
                social_media_profiles=[{
                    'platform': 'vk',
                    'url': 'https://vk.com/id12345',
                    'display_name': 'Test',
                    'username': 'id12345',
                }],
            )

            svc = ContactDiscoveryService()
            svc.vk_token = None  # Force no token
            result = svc.discover(check)

            # Should not crash, just return empty
            assert 'phones' in result
            assert 'emails' in result


# ── Telegram Extraction Tests ────────────────────────────────────────

class TestTelegramExtraction:

    def test_telegram_profile_with_phone(self):
        """Telegram profile with phone field → phone extracted."""
        check = FakeCheck(
            social_media_profiles=[{
                'platform': 'telegram',
                'display_name': 'Иван Иванов',
                'username': 'ivanov',
                'phone': '+79161234567',
            }],
        )

        svc = ContactDiscoveryService()
        svc.vk_token = None  # Skip VK
        result = svc.discover(check)

        phones = result['phones']
        phone_numbers = [p['number'] for p in phones]
        assert '+79161234567' in phone_numbers

        for p in phones:
            if p['number'] == '+79161234567':
                assert p['source'] == 'telegram'
                assert p['confidence'] == 'высокая'

    def test_telegram_bio_with_contacts(self):
        """Telegram profile with phone/email in bio → extracted via regex."""
        check = FakeCheck(
            social_media_profiles=[{
                'platform': 'telegram',
                'display_name': 'Тест',
                'username': 'testuser',
                'bio': 'Контакт: 8-916-111-22-33, email: hello@example.com',
            }],
        )

        svc = ContactDiscoveryService()
        svc.vk_token = None
        result = svc.discover(check)

        phones = result['phones']
        emails = result['emails']
        phone_numbers = [p['number'] for p in phones]
        email_addrs = [e['email'] for e in emails]
        assert '+79161112233' in phone_numbers
        assert 'hello@example.com' in email_addrs


# ── Business Record Tests ────────────────────────────────────────────

class TestBusinessExtraction:

    def test_business_record_with_phone(self):
        """Business record with company phone → added with low confidence."""
        check = FakeCheck(
            business_records=[{
                'name': 'ООО Ромашка',
                'phone': '+7 (495) 123-45-67',
                'inn': '7712345678',
            }],
        )

        svc = ContactDiscoveryService()
        svc.vk_token = None
        result = svc.discover(check)

        phones = result['phones']
        assert len(phones) >= 1
        biz_phones = [p for p in phones if p['source'] == 'egrul']
        assert len(biz_phones) >= 1
        assert biz_phones[0]['confidence'] == 'низкая'

    def test_business_record_with_email(self):
        """Business record with email → added with low confidence."""
        check = FakeCheck(
            business_records=[{
                'name': 'ООО Ромашка',
                'email': 'info@romashka.ru',
            }],
        )

        svc = ContactDiscoveryService()
        svc.vk_token = None
        result = svc.discover(check)

        emails = result['emails']
        email_addrs = [e['email'] for e in emails]
        assert 'info@romashka.ru' in email_addrs

        for e in emails:
            if e['email'] == 'info@romashka.ru':
                assert e['confidence'] == 'низкая'
                assert e['source'] == 'egrul'


# ── FSSP Extraction Tests ───────────────────────────────────────────

class TestFSSPExtraction:

    def test_fssp_manual_record_skipped(self):
        """FSSP manual records (CAPTCHA fallback) are skipped."""
        check = FakeCheck(
            fssp_records=[{
                'source': 'manual',
                'phone': '+79161234567',
            }],
        )

        svc = ContactDiscoveryService()
        svc.vk_token = None
        result = svc.discover(check)
        fssp_phones = [p for p in result['phones'] if p['source'] == 'fssp']
        assert len(fssp_phones) == 0

    def test_fssp_record_with_phone(self):
        """FSSP record with debtor phone → extracted."""
        check = FakeCheck(
            fssp_records=[{
                'debtor_phone': '+7 (916) 555-44-33',
                'proceedings_number': '12345/22/77000-ИП',
            }],
        )

        svc = ContactDiscoveryService()
        svc.vk_token = None
        result = svc.discover(check)
        fssp_phones = [p for p in result['phones'] if p['source'] == 'fssp']
        assert len(fssp_phones) >= 1


# ── Email Guessing Tests ────────────────────────────────────────────

class TestEmailGuessing:

    def test_username_generates_guesses(self):
        """Username 'ivanov.ivan' generates email guesses for each domain."""
        check = FakeCheck(
            full_name='Иванов Иван',
            social_media_profiles=[{
                'platform': 'vk',
                'username': 'ivanov.ivan',
                'display_name': 'Иван Иванов',
            }],
        )

        svc = ContactDiscoveryService()
        svc.vk_token = None
        # Skip VK API, Holehe
        with patch.object(svc, '_extract_from_vk'), \
             patch.object(svc, '_verify_with_holehe'):
            result = svc.discover(check)

        emails = result['emails']
        email_addrs = [e['email'] for e in emails]

        # Should have username@domain guesses
        assert 'ivanov.ivan@gmail.com' in email_addrs
        assert 'ivanov.ivan@mail.ru' in email_addrs
        assert 'ivanov.ivan@yandex.ru' in email_addrs

        # All guesses should be low confidence
        guess_emails = [e for e in emails if e['source'] == 'email_guess']
        assert all(e['confidence'] == 'низкая' for e in guess_emails)

    def test_default_vk_id_skipped(self):
        """VK default ID like 'id12345' should NOT generate email guesses."""
        check = FakeCheck(
            full_name='Иванов Иван',
            social_media_profiles=[{
                'platform': 'vk',
                'username': 'id12345',
                'display_name': 'Иван Иванов',
            }],
        )

        svc = ContactDiscoveryService()
        svc.vk_token = None
        with patch.object(svc, '_extract_from_vk'), \
             patch.object(svc, '_verify_with_holehe'):
            result = svc.discover(check)

        emails = result['emails']
        # Should not have id12345@gmail.com etc.
        email_addrs = [e['email'] for e in emails]
        assert 'id12345@gmail.com' not in email_addrs

    def test_name_transliteration_guesses(self):
        """Name-based email guesses use transliteration."""
        check = FakeCheck(
            full_name='Иванов Иван',
            social_media_profiles=[],
        )

        svc = ContactDiscoveryService()
        svc.vk_token = None
        with patch.object(svc, '_verify_with_holehe'):
            result = svc.discover(check)

        emails = result['emails']
        email_addrs = [e['email'] for e in emails]

        # Should contain transliterated name guesses
        assert any('ivanov' in addr and '@' in addr for addr in email_addrs), \
            f"Expected transliterated name guesses, got: {email_addrs[:5]}"


# ── Deduplication Tests ──────────────────────────────────────────────

class TestDeduplication:

    def test_same_phone_two_sources_keeps_highest_confidence(self):
        """Same phone from two sources → keeps highest confidence version."""
        svc = ContactDiscoveryService()
        svc.found_phones = [
            DiscoveredPhone('+79161234567', 'egrul', 'низкая', 'ООО Ромашка', '+7 916 123-45-67'),
            DiscoveredPhone('+79161234567', 'vk_profile', 'высокая', 'Иван Иванов', '+79161234567'),
        ]
        svc.found_emails = []
        svc._deduplicate_contacts()

        assert len(svc.found_phones) == 1
        assert svc.found_phones[0].confidence == 'высокая'
        assert svc.found_phones[0].source == 'vk_profile'

    def test_same_email_guess_and_holehe_keeps_verified(self):
        """Same email from guess and Holehe → keeps verified version."""
        svc = ContactDiscoveryService()
        svc.found_phones = []
        svc.found_emails = [
            DiscoveredEmail('test@gmail.com', 'email_guess', 'низкая', False, '@testuser'),
            DiscoveredEmail('test@gmail.com', 'holehe_verified', 'высокая', True, 'Holehe',
                            services=['instagram', 'twitter']),
        ]
        svc._deduplicate_contacts()

        assert len(svc.found_emails) == 1
        assert svc.found_emails[0].verified is True
        assert svc.found_emails[0].source == 'holehe_verified'

    def test_dedup_different_phones_preserved(self):
        """Different phone numbers are all preserved after dedup."""
        svc = ContactDiscoveryService()
        svc.found_phones = [
            DiscoveredPhone('+79161234567', 'vk_profile', 'высокая', 'Иван', '+79161234567'),
            DiscoveredPhone('+79169876543', 'telegram', 'высокая', 'Иван', '+79169876543'),
        ]
        svc.found_emails = []
        svc._deduplicate_contacts()
        assert len(svc.found_phones) == 2

    def test_dedup_different_emails_preserved(self):
        """Different emails are all preserved after dedup."""
        svc = ContactDiscoveryService()
        svc.found_phones = []
        svc.found_emails = [
            DiscoveredEmail('a@gmail.com', 'vk_profile', 'высокая', False, 'Иван'),
            DiscoveredEmail('b@mail.ru', 'email_guess', 'низкая', False, '@test'),
        ]
        svc._deduplicate_contacts()
        assert len(svc.found_emails) == 2


# ── Empty / Edge Cases ───────────────────────────────────────────────

class TestEdgeCases:

    def test_empty_profiles_no_crash(self):
        """Empty social profiles → no phones, name guesses only for emails, no crash."""
        check = FakeCheck(
            social_media_profiles=[],
            business_records=[],
            fssp_records=[],
        )

        svc = ContactDiscoveryService()
        svc.vk_token = None
        with patch.object(svc, '_verify_with_holehe'):
            result = svc.discover(check)

        assert result['phones'] == []
        # Name-based guessing still produces emails (from full_name transliteration)
        assert isinstance(result['emails'], list)
        # All should be low-confidence guesses
        for e in result['emails']:
            assert e['source'] == 'email_guess'
            assert e['confidence'] == 'низкая'

    def test_truly_empty_check_no_crash(self):
        """Check with minimal name that can't be transliterated → empty results."""
        check = FakeCheck(full_name='Тест Т')
        check.social_media_profiles = []
        check.business_records = []
        check.fssp_records = []

        svc = ContactDiscoveryService()
        svc.vk_token = None
        with patch.object(svc, '_verify_with_holehe'):
            result = svc.discover(check)

        assert result['phones'] == []
        assert isinstance(result['emails'], list)

    def test_none_profiles_no_crash(self):
        """None social profiles → no crash."""
        check = FakeCheck()
        check.social_media_profiles = None
        check.business_records = None
        check.fssp_records = None

        svc = ContactDiscoveryService()
        svc.vk_token = None
        with patch.object(svc, '_verify_with_holehe'):
            result = svc.discover(check)

        assert result['phones'] == []
        assert isinstance(result['emails'], list)

    def test_input_phone_preserved(self):
        """Phone from form input is included in results."""
        check = FakeCheck(phone='+79161234567')

        svc = ContactDiscoveryService()
        svc.vk_token = None
        with patch.object(svc, '_verify_with_holehe'):
            result = svc.discover(check)

        phone_numbers = [p['number'] for p in result['phones']]
        assert '+79161234567' in phone_numbers

    def test_input_email_preserved(self):
        """Email from form input is included in results."""
        check = FakeCheck(email='test@example.com')

        svc = ContactDiscoveryService()
        svc.vk_token = None
        with patch.object(svc, '_verify_with_holehe'):
            result = svc.discover(check)

        email_addrs = [e['email'] for e in result['emails']]
        assert 'test@example.com' in email_addrs

    def test_to_dict_serialization(self):
        """DiscoveredPhone and DiscoveredEmail serialize to dict."""
        phone = DiscoveredPhone('+79161234567', 'vk_profile', 'высокая', 'Иван', '+7 916 123')
        d = phone.to_dict()
        assert d['number'] == '+79161234567'
        assert d['source'] == 'vk_profile'
        assert d['confidence'] == 'высокая'

        email = DiscoveredEmail('test@gmail.com', 'holehe_verified', 'высокая', True, 'Holehe',
                                services=['instagram'])
        d = email.to_dict()
        assert d['email'] == 'test@gmail.com'
        assert d['verified'] is True
        assert d['services'] == ['instagram']


# ── Holehe Verification Tests ────────────────────────────────────────

class TestHolehe:

    @patch('app.services.phase2.email_discovery.verify_emails_with_holehe')
    def test_holehe_upgrades_confidence(self, mock_holehe):
        """Holehe verification upgrades email confidence to высокая."""
        mock_holehe.return_value = [{
            'email': 'test@gmail.com',
            'services': ['instagram', 'twitter'],
            'verified': True,
        }]

        svc = ContactDiscoveryService()
        svc.found_emails = [
            DiscoveredEmail('test@gmail.com', 'email_guess', 'низкая', False, '@testuser'),
        ]
        svc._verify_with_holehe()

        assert svc.found_emails[0].verified is True
        assert svc.found_emails[0].confidence == 'высокая'
        assert svc.found_emails[0].source == 'holehe_verified'

    @patch('app.services.phase2.email_discovery.verify_emails_with_holehe')
    def test_holehe_no_results_keeps_original(self, mock_holehe):
        """Holehe finds nothing → email keeps original confidence."""
        mock_holehe.return_value = [{
            'email': 'test@gmail.com',
            'services': [],
            'verified': False,
        }]

        svc = ContactDiscoveryService()
        svc.found_emails = [
            DiscoveredEmail('test@gmail.com', 'email_guess', 'низкая', False, '@testuser'),
        ]
        svc._verify_with_holehe()

        assert svc.found_emails[0].verified is False
        assert svc.found_emails[0].confidence == 'низкая'

    @patch('app.services.phase2.email_discovery.verify_emails_with_holehe',
           side_effect=Exception("Connection error"))
    def test_holehe_exception_no_crash(self, mock_holehe):
        """Holehe raising an exception → step skipped, no crash."""
        svc = ContactDiscoveryService()
        svc.found_emails = [
            DiscoveredEmail('test@gmail.com', 'email_guess', 'низкая', False, '@testuser'),
        ]

        # The outer try/except in discover() catches this
        # But _verify_with_holehe itself lets the exception propagate
        # It will be caught by the discover() method's try/except
        try:
            svc._verify_with_holehe()
        except Exception:
            pass
        # Email should remain unchanged
        assert svc.found_emails[0].verified is False
        assert svc.found_emails[0].confidence == 'низкая'


# ── Confidence Rank Tests ────────────────────────────────────────────

class TestConfidenceRank:

    def test_rank_order(self):
        assert _confidence_rank('высокая') > _confidence_rank('средняя')
        assert _confidence_rank('средняя') > _confidence_rank('низкая')
        assert _confidence_rank('низкая') > _confidence_rank('unknown')

    def test_unknown_confidence(self):
        assert _confidence_rank('') == 0
        assert _confidence_rank('invalid') == 0


# ── Regex Pattern Tests ─────────────────────────────────────────────

class TestRegexPatterns:

    @pytest.mark.parametrize('phone_str', [
        '+7 (916) 123-45-67',
        '8-916-123-45-67',
        '+7 916 1234567',
        '+79161234567',
        '89161234567',
    ])
    def test_phone_pattern_matches(self, phone_str):
        """Phone regex matches various Russian phone formats."""
        assert PHONE_PATTERN.search(phone_str), f"Pattern should match: {phone_str}"

    @pytest.mark.parametrize('email_str', [
        'test@gmail.com',
        'user.name@mail.ru',
        'user+tag@example.com',
    ])
    def test_email_pattern_matches(self, email_str):
        """Email regex matches valid email formats."""
        assert EMAIL_PATTERN.search(email_str), f"Pattern should match: {email_str}"


# ── Full Integration Tests (mocked) ─────────────────────────────────

class TestFullDiscovery:

    @patch.dict(os.environ, {'VK_SERVICE_TOKEN': 'test_token'})
    @patch('app.services.candidate.contact_discovery.ContactDiscoveryService._vk_api_get_contacts')
    @patch('app.services.phase2.email_discovery.verify_emails_with_holehe')
    def test_full_pipeline_mock(self, mock_holehe, mock_vk_api):
        """Full pipeline with VK phone, Telegram phone, email guesses, Holehe."""
        mock_vk_api.return_value = [{
            'mobile_phone': '+7 (916) 111-22-33',
            'home_phone': '',
            'site': '',
            'about': '',
            'status': '',
        }]
        mock_holehe.return_value = []

        check = FakeCheck(
            full_name='Иванов Иван Иванович',
            social_media_profiles=[
                {
                    'platform': 'vk',
                    'url': 'https://vk.com/ivanov',
                    'display_name': 'Иван Иванов',
                    'username': 'ivanov',
                },
                {
                    'platform': 'telegram',
                    'display_name': 'Иван Иванов',
                    'username': 'ivanov_ivan',
                    'phone': '+79169876543',
                },
            ],
            business_records=[{
                'name': 'ООО Ромашка',
                'phone': '+7 (495) 555-66-77',
            }],
        )

        svc = ContactDiscoveryService()
        result = svc.discover(check)

        phones = result['phones']
        emails = result['emails']

        # Should have multiple phones from different sources
        assert len(phones) >= 2
        phone_numbers = [p['number'] for p in phones]
        assert '+79161112233' in phone_numbers  # VK
        assert '+79169876543' in phone_numbers  # Telegram

        # Should have email guesses
        assert len(emails) >= 1

    def test_discover_returns_correct_structure(self):
        """discover() returns dict with 'phones' and 'emails' lists."""
        check = FakeCheck()

        svc = ContactDiscoveryService()
        svc.vk_token = None
        with patch.object(svc, '_verify_with_holehe'):
            result = svc.discover(check)

        assert isinstance(result, dict)
        assert 'phones' in result
        assert 'emails' in result
        assert isinstance(result['phones'], list)
        assert isinstance(result['emails'], list)

        # Each entry should be a dict (serialized dataclass)
        for p in result['phones']:
            assert isinstance(p, dict)
            assert 'number' in p
            assert 'source' in p
            assert 'confidence' in p
        for e in result['emails']:
            assert isinstance(e, dict)
            assert 'email' in e
            assert 'source' in e
            assert 'confidence' in e
