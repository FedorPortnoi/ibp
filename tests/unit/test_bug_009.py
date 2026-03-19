"""
Tests for BUG-009: VK contact extraction finds VK profile but extracts 0 phones and 0 emails.

Verifies:
1. Direct phone fields (mobile_phone, home_phone, phone) are extracted
2. Emails in site/about/status fields are extracted
3. Social link fields (twitter, instagram, facebook, skype) with emails are extracted
4. Personal section emails are extracted
5. Telegram handles from text fields are detected
"""

import re
from unittest.mock import patch, MagicMock

import pytest


# ---------------------------------------------------------------------------
# Helpers – we test _extract_from_vk in isolation, bypassing __init__ imports
# ---------------------------------------------------------------------------

def _make_service(vk_token='fake_token'):
    """Create a ContactDiscoveryService with mocked __init__."""
    with patch('app.services.candidate.contact_discovery.ContactDiscoveryService.__init__',
               lambda self: None):
        from app.services.candidate.contact_discovery import ContactDiscoveryService
        svc = ContactDiscoveryService()
        svc.vk_token = vk_token
        svc.vk_user_token = vk_token
        svc.found_phones = []
        svc.found_emails = []
        svc._oracle_results = []
        return svc


def _fake_vk_user(**overrides):
    """Build a fake VK user dict with sensible defaults."""
    user = {
        'id': 123456,
        'first_name': 'Иван',
        'last_name': 'Иванов',
        'mobile_phone': '+7 916 123-45-67',
        'home_phone': '',
        'phone': '+79031234567',
        'site': 'ivan@example.com',
        'about': 'Пишите в телеграм: t.me/ivan_test',
        'status': '',
        'twitter': '',
        'instagram': '',
        'facebook': '',
        'skype': '',
        'personal': {},
    }
    user.update(overrides)
    return user


# ============================  TESTS  =====================================

class TestVKPhoneExtraction:
    """Fix 1+2: phones from mobile_phone, home_phone, and direct 'phone' field."""

    def test_mobile_phone_extracted(self):
        svc = _make_service()
        user = _fake_vk_user(phone='', site='', about='')  # only mobile_phone
        profiles = [{'platform': 'vk', 'url': 'https://vk.com/id123456', 'display_name': 'Иван'}]

        with patch.object(svc, '_vk_api_get_contacts', return_value=[user]):
            svc._extract_from_vk(profiles)

        assert len(svc.found_phones) >= 1
        numbers = [p.number for p in svc.found_phones]
        assert '+79161234567' in numbers

    def test_direct_phone_field_extracted(self):
        """The 'phone' field (not mobile_phone) should also be extracted."""
        svc = _make_service()
        user = _fake_vk_user(mobile_phone='', home_phone='', site='', about='')
        profiles = [{'platform': 'vk', 'url': 'https://vk.com/id123456', 'display_name': 'Иван'}]

        with patch.object(svc, '_vk_api_get_contacts', return_value=[user]):
            svc._extract_from_vk(profiles)

        assert len(svc.found_phones) >= 1
        numbers = [p.number for p in svc.found_phones]
        assert '+79031234567' in numbers

    def test_both_mobile_and_direct_phone(self):
        """Both mobile_phone and phone fields should yield results."""
        svc = _make_service()
        user = _fake_vk_user(site='', about='')
        profiles = [{'platform': 'vk', 'url': 'https://vk.com/id123456', 'display_name': 'Иван'}]

        with patch.object(svc, '_vk_api_get_contacts', return_value=[user]):
            svc._extract_from_vk(profiles)

        numbers = [p.number for p in svc.found_phones]
        assert '+79161234567' in numbers
        assert '+79031234567' in numbers
        assert len(svc.found_phones) >= 2


class TestVKEmailExtraction:
    """Emails from site/about/status fields."""

    def test_email_in_site_field(self):
        svc = _make_service()
        user = _fake_vk_user(
            mobile_phone='', phone='', about='',
            site='ivan@example.com',
        )
        profiles = [{'platform': 'vk', 'url': 'https://vk.com/id123456', 'display_name': 'Иван'}]

        with patch.object(svc, '_vk_api_get_contacts', return_value=[user]):
            svc._extract_from_vk(profiles)

        assert len(svc.found_emails) >= 1
        emails = [e.email for e in svc.found_emails]
        assert 'ivan@example.com' in emails

    def test_email_in_about_field(self):
        svc = _make_service()
        user = _fake_vk_user(
            mobile_phone='', phone='', site='',
            about='Контакт: work@company.ru',
        )
        profiles = [{'platform': 'vk', 'url': 'https://vk.com/id123456', 'display_name': 'Иван'}]

        with patch.object(svc, '_vk_api_get_contacts', return_value=[user]):
            svc._extract_from_vk(profiles)

        emails = [e.email for e in svc.found_emails]
        assert 'work@company.ru' in emails


class TestVKSocialLinkExtraction:
    """Fix 3: social link fields (twitter, instagram, facebook, skype)."""

    def test_email_in_twitter_field(self):
        svc = _make_service()
        user = _fake_vk_user(
            mobile_phone='', phone='', site='', about='',
            twitter='ivan_tw@gmail.com',
        )
        profiles = [{'platform': 'vk', 'url': 'https://vk.com/id123456', 'display_name': 'Иван'}]

        with patch.object(svc, '_vk_api_get_contacts', return_value=[user]):
            svc._extract_from_vk(profiles)

        emails = [e.email for e in svc.found_emails]
        assert 'ivan_tw@gmail.com' in emails
        # Check profile_name includes the social type
        matching = [e for e in svc.found_emails if e.email == 'ivan_tw@gmail.com']
        assert any('twitter' in e.profile_name for e in matching)

    def test_email_in_instagram_field(self):
        svc = _make_service()
        user = _fake_vk_user(
            mobile_phone='', phone='', site='', about='',
            instagram='photographer@studio.com',
        )
        profiles = [{'platform': 'vk', 'url': 'https://vk.com/id123456', 'display_name': 'Иван'}]

        with patch.object(svc, '_vk_api_get_contacts', return_value=[user]):
            svc._extract_from_vk(profiles)

        emails = [e.email for e in svc.found_emails]
        assert 'photographer@studio.com' in emails

    def test_email_in_skype_field(self):
        svc = _make_service()
        user = _fake_vk_user(
            mobile_phone='', phone='', site='', about='',
            skype='live:user@outlook.com',
        )
        profiles = [{'platform': 'vk', 'url': 'https://vk.com/id123456', 'display_name': 'Иван'}]

        with patch.object(svc, '_vk_api_get_contacts', return_value=[user]):
            svc._extract_from_vk(profiles)

        emails = [e.email for e in svc.found_emails]
        assert 'user@outlook.com' in emails

    def test_personal_section_email(self):
        svc = _make_service()
        user = _fake_vk_user(
            mobile_phone='', phone='', site='', about='',
            personal={'langs': 'en', 'employer_info': 'ceo@startup.io'},
        )
        profiles = [{'platform': 'vk', 'url': 'https://vk.com/id123456', 'display_name': 'Иван'}]

        with patch.object(svc, '_vk_api_get_contacts', return_value=[user]):
            svc._extract_from_vk(profiles)

        emails = [e.email for e in svc.found_emails]
        assert 'ceo@startup.io' in emails
        matching = [e for e in svc.found_emails if e.email == 'ceo@startup.io']
        assert any('personal' in e.profile_name for e in matching)


class TestVKTelegramHandleExtraction:
    """Fix 4: Telegram handles from about/status/site fields."""

    def test_telegram_handle_in_about(self):
        svc = _make_service()
        user = _fake_vk_user(
            mobile_phone='', phone='', site='',
            about='Пишите в телеграм: t.me/ivan_test',
        )
        profiles = [{'platform': 'vk', 'url': 'https://vk.com/id123456', 'display_name': 'Иван'}]

        with patch.object(svc, '_vk_api_get_contacts', return_value=[user]):
            svc._extract_from_vk(profiles)

        assert hasattr(svc, '_telegram_hints')
        assert len(svc._telegram_hints) >= 1
        usernames = [h['username'] for h in svc._telegram_hints]
        assert 'ivan_test' in usernames
        assert svc._telegram_hints[0]['source'] == 'vk_profile_field'

    def test_telegram_at_handle_in_status(self):
        svc = _make_service()
        user = _fake_vk_user(
            mobile_phone='', phone='', site='', about='',
            status='@my_telegram_bot для связи',
        )
        profiles = [{'platform': 'vk', 'url': 'https://vk.com/id123456', 'display_name': 'Иван'}]

        with patch.object(svc, '_vk_api_get_contacts', return_value=[user]):
            svc._extract_from_vk(profiles)

        assert hasattr(svc, '_telegram_hints')
        usernames = [h['username'] for h in svc._telegram_hints]
        assert 'my_telegram_bot' in usernames

    def test_telegram_handle_in_site(self):
        svc = _make_service()
        user = _fake_vk_user(
            mobile_phone='', phone='', about='',
            site='t.me/cool_channel',
        )
        profiles = [{'platform': 'vk', 'url': 'https://vk.com/id123456', 'display_name': 'Иван'}]

        with patch.object(svc, '_vk_api_get_contacts', return_value=[user]):
            svc._extract_from_vk(profiles)

        assert hasattr(svc, '_telegram_hints')
        usernames = [h['username'] for h in svc._telegram_hints]
        assert 'cool_channel' in usernames


class TestVKExpandedFields:
    """Fix 1: verify expanded fields string in _vk_api_get_contacts."""

    def test_fields_include_social_and_personal(self):
        """The VK API request must include social link fields."""
        svc = _make_service()

        with patch('app.services.candidate.contact_discovery.requests.get') as mock_get:
            mock_resp = MagicMock()
            mock_resp.json.return_value = {'response': [_fake_vk_user()]}
            mock_get.return_value = mock_resp

            svc._vk_api_get_contacts('123456')

            call_args = mock_get.call_args
            fields = call_args.kwargs.get('params', call_args[1].get('params', {}))['fields']

            for expected in ['twitter', 'facebook', 'instagram', 'skype',
                             'occupation', 'personal', 'domain']:
                assert expected in fields, f"'{expected}' missing from VK API fields"


class TestVKFullIntegration:
    """Integration: a realistic VK user with phones AND emails should yield both."""

    def test_full_user_extraction(self):
        svc = _make_service()
        user = _fake_vk_user(
            mobile_phone='+7 (916) 123-45-67',
            phone='+79031112233',
            site='https://ivan.dev — ivan@ivan.dev',
            about='Telegram: t.me/ivan_dev | WhatsApp: +7 903 111 22 33',
            twitter='ivan_twitter@gmail.com',
            personal={'notes': 'Рабочая почта: hr@bigcorp.ru'},
        )
        profiles = [{'platform': 'vk', 'url': 'https://vk.com/ivan_dev', 'display_name': 'Иван Иванов'}]

        with patch.object(svc, '_vk_api_get_contacts', return_value=[user]):
            svc._extract_from_vk(profiles)

        assert len(svc.found_phones) >= 1, f"Expected >=1 phones, got {len(svc.found_phones)}"
        assert len(svc.found_emails) >= 1, f"Expected >=1 emails, got {len(svc.found_emails)}"

        emails = [e.email for e in svc.found_emails]
        assert 'ivan@ivan.dev' in emails
        assert 'ivan_twitter@gmail.com' in emails
        assert 'hr@bigcorp.ru' in emails

        # Telegram hints
        assert hasattr(svc, '_telegram_hints')
        tg_usernames = [h['username'] for h in svc._telegram_hints]
        assert 'ivan_dev' in tg_usernames


class TestNoVKToken:
    """Edge case: no VK token should skip gracefully."""

    def test_no_token_skips(self):
        svc = _make_service(vk_token=None)
        profiles = [{'platform': 'vk', 'url': 'https://vk.com/id123456', 'display_name': 'Иван'}]

        svc._extract_from_vk(profiles)

        assert len(svc.found_phones) == 0
        assert len(svc.found_emails) == 0


class TestEmptyVKResponse:
    """Edge case: VK API returns empty/None."""

    def test_empty_response(self):
        svc = _make_service()
        profiles = [{'platform': 'vk', 'url': 'https://vk.com/id123456', 'display_name': 'Иван'}]

        with patch.object(svc, '_vk_api_get_contacts', return_value=None):
            svc._extract_from_vk(profiles)

        assert len(svc.found_phones) == 0
        assert len(svc.found_emails) == 0

    def test_empty_fields(self):
        """All phone/email fields are empty strings."""
        svc = _make_service()
        user = _fake_vk_user(
            mobile_phone='', home_phone='', phone='',
            site='', about='', status='',
            twitter='', instagram='', facebook='', skype='',
            personal={},
        )
        profiles = [{'platform': 'vk', 'url': 'https://vk.com/id123456', 'display_name': 'Иван'}]

        with patch.object(svc, '_vk_api_get_contacts', return_value=[user]):
            svc._extract_from_vk(profiles)

        assert len(svc.found_phones) == 0
        assert len(svc.found_emails) == 0
