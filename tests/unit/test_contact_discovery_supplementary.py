"""
Tests for ContactDiscoveryService.discover_supplementary()
Stage 4 feedback loop from Stage 5.
"""

import pytest
from unittest.mock import patch, MagicMock
from app.services.candidate.contact_discovery import ContactDiscoveryService


class TestDiscoverSupplementaryStructure:
    """Test return structure."""

    def test_returns_phones_and_emails(self):
        service = ContactDiscoveryService()
        result = service.discover_supplementary([], {})
        assert 'phones' in result
        assert 'emails' in result

    def test_empty_accounts_returns_empty(self):
        service = ContactDiscoveryService()
        result = service.discover_supplementary([], {})
        assert result == {'phones': [], 'emails': []}

    def test_none_accounts_like_empty(self):
        service = ContactDiscoveryService()
        result = service.discover_supplementary([], {'phones': [], 'emails': []})
        assert result == {'phones': [], 'emails': []}


class TestDemoMode:
    """Test demo supplementary results."""

    def test_demo_accounts_trigger_demo_response(self):
        service = ContactDiscoveryService()
        demo_accounts = [
            {'url': 'https://github.com/ivanovdemo', 'username': 'ivanovdemo', 'platform': 'github', 'source': 'snoop'},
        ]
        result = service.discover_supplementary(demo_accounts, {})
        assert len(result['phones']) == 1
        assert len(result['emails']) == 2

    def test_demo_phone_has_number(self):
        service = ContactDiscoveryService()
        demo_accounts = [
            {'url': 'https://github.com/ivanovdemo', 'username': 'ivanovdemo', 'platform': 'github', 'source': 'snoop'},
        ]
        result = service.discover_supplementary(demo_accounts, {})
        assert result['phones'][0]['number'] == '+79161234599'

    def test_demo_emails_have_addresses(self):
        service = ContactDiscoveryService()
        demo_accounts = [
            {'url': 'https://github.com/ivanovdemo', 'username': 'ivanovdemo', 'platform': 'github', 'source': 'snoop'},
        ]
        result = service.discover_supplementary(demo_accounts, {})
        addresses = [e['address'] for e in result['emails']]
        assert 'ivanov.demo@gmail.com' in addresses
        assert 'ivanov.demo@mail.ru' in addresses


class TestDeduplication:
    """Test dedup against existing contacts."""

    def test_skips_existing_emails(self):
        service = ContactDiscoveryService()
        accounts = [
            {'url': 'https://github.com/testuser', 'username': 'testuser', 'platform': 'github', 'source': 'snoop'},
        ]
        existing = {
            'emails': [
                {'email': 'testuser@gmail.com', 'source': 'holehe'},
                {'email': 'testuser@mail.ru', 'source': 'guess'},
            ],
            'phones': [],
        }
        # Patch holehe and breach APIs to avoid real calls
        with patch('app.services.candidate.contact_discovery.ContactDiscoveryService._verify_with_holehe'):
            result = service.discover_supplementary(accounts, existing)
        # Should not include testuser@gmail.com or testuser@mail.ru since they exist
        for email in result['emails']:
            assert email['address'] not in ('testuser@gmail.com', 'testuser@mail.ru')

    def test_skips_existing_phones(self):
        service = ContactDiscoveryService()
        accounts = [
            {'url': 'https://github.com/user1', 'username': 'user1', 'platform': 'github', 'source': 'snoop'},
        ]
        existing = {
            'phones': [{'number': '+79161234567', 'source': 'vk'}],
            'emails': [],
        }
        result = service.discover_supplementary(accounts, existing)
        for phone in result['phones']:
            assert phone['number'] != '+79161234567'


class TestEmailGeneration:
    """Test email pattern generation from new accounts."""

    def test_generates_emails_from_usernames(self):
        service = ContactDiscoveryService()
        accounts = [
            {'url': 'https://github.com/ivan_petrov', 'username': 'ivan_petrov', 'platform': 'github', 'source': 'snoop'},
        ]
        result = service.discover_supplementary(accounts, {})
        # Should have generated email guesses
        addresses = [e['address'] for e in result['emails']]
        assert any('ivan_petrov' in addr for addr in addresses)

    def test_skips_short_usernames(self):
        service = ContactDiscoveryService()
        accounts = [
            {'url': 'https://github.com/ab', 'username': 'ab', 'platform': 'github', 'source': 'snoop'},
        ]
        result = service.discover_supplementary(accounts, {})
        assert result == {'phones': [], 'emails': []}

    def test_skips_vk_id_usernames(self):
        service = ContactDiscoveryService()
        accounts = [
            {'url': 'https://vk.com/id123456', 'username': 'id123456', 'platform': 'vk', 'source': 'face_search'},
        ]
        result = service.discover_supplementary(accounts, {})
        assert result == {'phones': [], 'emails': []}

    def test_multiple_accounts_generate_unique_emails(self):
        service = ContactDiscoveryService()
        accounts = [
            {'url': 'https://github.com/testname', 'username': 'testname', 'platform': 'github', 'source': 'snoop'},
            {'url': 'https://habr.com/testname', 'username': 'testname', 'platform': 'habr', 'source': 'snoop'},
        ]
        result = service.discover_supplementary(accounts, {})
        addresses = [e['address'] for e in result['emails']]
        # Should not have duplicates
        assert len(addresses) == len(set(addresses))
