"""
Tests for GetContact API Integration
======================================
Tests the GetContactSource with two modes:
1. Real API mode (with credentials — uses mocked HTTP)
2. Demo mode (no credentials — returns empty list)

Also tests the low-level GetContactAPI encryption/signing.
"""

import base64
import binascii
import hashlib
import hmac
import json
import os
import re
from unittest.mock import patch, MagicMock, PropertyMock

import pytest


# -----------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """Ensure no real credentials leak into tests."""
    for key in ('GETCONTACT_API_KEY', 'GETCONTACT_TOKEN', 'GETCONTACT_AES_KEY',
                'GETCONTACT_DEVICE_ID'):
        monkeypatch.delenv(key, raising=False)


# -----------------------------------------------------------------------
# GetContactAPI low-level tests
# -----------------------------------------------------------------------

class TestGetContactAPIEncryption:
    """Test AES-256-ECB encryption / decryption and HMAC signing."""

    def _make_api(self):
        from app.services.phase2.sources.getcontact import GetContactAPI
        # Use a known 256-bit key (64 hex chars)
        test_aes_key = 'a' * 64  # 32 bytes of 0xAA
        return GetContactAPI(
            token='test_token_123',
            aes_key=test_aes_key,
            device_id='test_device_456',
        )

    def test_encrypt_decrypt_roundtrip(self):
        """Encrypt then decrypt should return original plaintext."""
        api = self._make_api()
        plaintext = '{"countryCode":"RU","source":"search","token":"tok","phoneNumber":"+79161234567"}'
        encrypted = api._encrypt(plaintext)
        decrypted = api._decrypt(encrypted)
        assert decrypted == plaintext

    def test_encrypt_produces_base64(self):
        """Encrypted output should be valid base64."""
        api = self._make_api()
        encrypted = api._encrypt('hello world test')
        # Should not raise
        decoded = base64.b64decode(encrypted)
        assert len(decoded) > 0

    def test_decrypt_handles_padding(self):
        """Decryption should correctly strip PKCS7 padding."""
        api = self._make_api()
        for text in ['a', 'ab', 'abc', '0123456789abcdef', 'x' * 31, 'y' * 48]:
            encrypted = api._encrypt(text)
            decrypted = api._decrypt(encrypted)
            assert decrypted == text, f"Roundtrip failed for text of length {len(text)}"

    def test_sign_request_deterministic(self):
        """Same inputs should produce same signature."""
        api = self._make_api()
        sig1 = api._sign_request('1700000000', '{"test":"data"}')
        sig2 = api._sign_request('1700000000', '{"test":"data"}')
        assert sig1 == sig2

    def test_sign_request_different_timestamps(self):
        """Different timestamps should produce different signatures."""
        api = self._make_api()
        sig1 = api._sign_request('1700000000', '{"test":"data"}')
        sig2 = api._sign_request('1700000001', '{"test":"data"}')
        assert sig1 != sig2

    def test_sign_request_produces_base64(self):
        """Signature should be valid base64."""
        api = self._make_api()
        sig = api._sign_request('1700000000', '{"test":"data"}')
        decoded = base64.b64decode(sig)
        assert len(decoded) == 32  # SHA-256 produces 32 bytes

    def test_aes_not_available_flag(self):
        """API should detect when pycryptodome is not available."""
        api = self._make_api()
        assert api._aes_available is True

    def test_make_request_without_aes(self):
        """_make_request should return None if AES unavailable."""
        api = self._make_api()
        api._aes_available = False
        result = api._make_request('https://example.com', {'test': 'data'})
        assert result is None


class TestGetContactAPIHTTP:
    """Test HTTP request/response handling with mocked network."""

    def _make_api(self):
        from app.services.phase2.sources.getcontact import GetContactAPI
        return GetContactAPI(
            token='test_token',
            aes_key='a' * 64,
            device_id='test_device',
        )

    def test_search_phone_sends_correct_payload(self):
        """search_phone should send correct payload structure."""
        api = self._make_api()

        with patch.object(api, '_make_request', return_value={'result': {'profile': {'displayName': 'Test'}}}) as mock_req:
            api.search_phone('+79161234567', 'RU')
            mock_req.assert_called_once()
            call_args = mock_req.call_args
            url = call_args[0][0]
            payload = call_args[0][1]

            assert 'search' in url
            assert payload['countryCode'] == 'RU'
            assert payload['source'] == 'search'
            assert payload['token'] == 'test_token'
            assert payload['phoneNumber'] == '+79161234567'

    def test_get_tags_sends_correct_payload(self):
        """get_tags should send details request."""
        api = self._make_api()

        with patch.object(api, '_make_request', return_value={'result': {'tags': []}}) as mock_req:
            api.get_tags('+79161234567', 'RU')
            mock_req.assert_called_once()
            payload = mock_req.call_args[0][1]
            assert payload['source'] == 'details'
            assert 'number-detail' in mock_req.call_args[0][0]

    def test_make_request_handles_403(self):
        """Should return None on 403 (CAPTCHA/rate limit)."""
        api = self._make_api()
        mock_resp = MagicMock()
        mock_resp.status_code = 403

        with patch.object(api.session, 'post', return_value=mock_resp):
            result = api._make_request('https://example.com', {'test': True})
            assert result is None

    def test_make_request_handles_500(self):
        """Should return None on server errors."""
        api = self._make_api()
        mock_resp = MagicMock()
        mock_resp.status_code = 500

        with patch.object(api.session, 'post', return_value=mock_resp):
            result = api._make_request('https://example.com', {'test': True})
            assert result is None

    def test_make_request_handles_api_error(self):
        """Should return None when meta contains error."""
        api = self._make_api()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            'meta': {'errorCode': '403021', 'errorMessage': 'Token is dead'},
        }

        with patch.object(api.session, 'post', return_value=mock_resp):
            result = api._make_request('https://example.com', {'test': True})
            assert result is None

    def test_make_request_decrypts_response(self):
        """Should decrypt 'data' field in response."""
        api = self._make_api()

        # Create an encrypted response
        response_json = '{"result":{"profile":{"displayName":"Иван"}}}'
        encrypted_resp = api._encrypt(response_json)

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            'meta': {},
            'data': encrypted_resp,
        }

        with patch.object(api.session, 'post', return_value=mock_resp):
            result = api._make_request('https://example.com', {'test': True})
            assert result is not None
            assert result['result']['profile']['displayName'] == 'Иван'

    def test_make_request_handles_network_error(self):
        """Should return None on network errors."""
        import requests as req_lib
        api = self._make_api()

        with patch.object(api.session, 'post', side_effect=req_lib.ConnectionError('timeout')):
            result = api._make_request('https://example.com', {'test': True})
            assert result is None


# -----------------------------------------------------------------------
# GetContactSource integration tests
# -----------------------------------------------------------------------

class TestGetContactSourceDemoMode:
    """Test GetContactSource demo mode (no credentials)."""

    def test_demo_mode_returns_empty(self):
        """Without any credentials, should return empty list."""
        from app.services.phase2.sources.getcontact import GetContactSource
        source = GetContactSource()
        results = source.query(phone='+79161234567')
        assert results == []


class TestGetContactSourceRealMode:
    """Test GetContactSource with mocked API calls."""

    def test_api_key_compact_format(self, monkeypatch):
        """GETCONTACT_API_KEY in TOKEN|AES_KEY|DEVICE_ID format."""
        aes_key = 'a' * 64
        monkeypatch.setenv('GETCONTACT_API_KEY', f'test_token|{aes_key}|test_device')

        from app.services.phase2.sources.getcontact import GetContactSource
        source = GetContactSource()
        creds = source._get_credentials()
        assert creds is not None
        assert creds[0] == 'test_token'
        assert creds[1] == aes_key
        assert creds[2] == 'test_device'

    def test_api_key_two_part_format(self, monkeypatch):
        """GETCONTACT_API_KEY with just TOKEN|AES_KEY uses default device ID."""
        aes_key = 'b' * 64
        monkeypatch.setenv('GETCONTACT_API_KEY', f'my_token|{aes_key}')

        from app.services.phase2.sources.getcontact import GetContactSource
        source = GetContactSource()
        creds = source._get_credentials()
        assert creds is not None
        assert creds[0] == 'my_token'
        assert creds[1] == aes_key
        assert creds[2] == '14130e29cebe9c39'  # default

    def test_legacy_credentials(self, monkeypatch):
        """Individual GETCONTACT_TOKEN + AES_KEY env vars."""
        monkeypatch.setenv('GETCONTACT_TOKEN', 'legacy_token')
        monkeypatch.setenv('GETCONTACT_AES_KEY', 'c' * 64)
        monkeypatch.setenv('GETCONTACT_DEVICE_ID', 'legacy_device')

        from app.services.phase2.sources.getcontact import GetContactSource
        source = GetContactSource()
        creds = source._get_credentials()
        assert creds is not None
        assert creds[0] == 'legacy_token'

    def test_real_api_with_display_name(self, monkeypatch):
        """Real API returning display name and tags."""
        aes_key = 'a' * 64
        monkeypatch.setenv('GETCONTACT_API_KEY', f'tok|{aes_key}|dev')

        from app.services.phase2.sources.getcontact import GetContactSource, GetContactAPI

        search_response = {
            'result': {
                'profile': {'displayName': 'Иван Петров', 'countryCode': 'RU'},
                'remainCount': 25,
            }
        }
        tags_response = {
            'result': {
                'tags': [
                    {'tag': 'Ваня работа'},
                    {'tag': 'Иван Петрович'},
                    {'tag': 'Ivan P'},
                ],
            }
        }

        with patch.object(GetContactAPI, 'search_phone', return_value=search_response), \
             patch.object(GetContactAPI, 'get_tags', return_value=tags_response):
            source = GetContactSource()
            results = source.query(phone='+79161234567')

        assert len(results) == 1
        assert results[0].value == 'Иван Петров'
        assert results[0].confidence == 0.85
        assert results[0].metadata['tag_count'] == 3
        assert 'Ваня работа' in results[0].metadata['tags']

    def test_real_api_tags_only(self, monkeypatch):
        """API returns tags but no display name."""
        aes_key = 'a' * 64
        monkeypatch.setenv('GETCONTACT_API_KEY', f'tok|{aes_key}|dev')

        from app.services.phase2.sources.getcontact import GetContactSource, GetContactAPI

        search_response = {'result': {'profile': {}}}
        tags_response = {
            'result': {'tags': [{'tag': 'Сосед Коля'}]}
        }

        with patch.object(GetContactAPI, 'search_phone', return_value=search_response), \
             patch.object(GetContactAPI, 'get_tags', return_value=tags_response):
            source = GetContactSource()
            results = source.query(phone='+79161234567')

        assert len(results) == 1
        assert results[0].value == 'Сосед Коля'
        assert results[0].confidence == 0.75

    def test_real_api_no_results(self, monkeypatch):
        """API returns nothing for unknown number."""
        aes_key = 'a' * 64
        monkeypatch.setenv('GETCONTACT_API_KEY', f'tok|{aes_key}|dev')

        from app.services.phase2.sources.getcontact import GetContactSource, GetContactAPI

        with patch.object(GetContactAPI, 'search_phone', return_value=None), \
             patch.object(GetContactAPI, 'get_tags', return_value=None):
            source = GetContactSource()
            results = source.query(phone='+79161234567')

        assert results == []

    def test_real_api_error_graceful(self, monkeypatch):
        """API errors should be caught by BaseSource wrapper."""
        aes_key = 'a' * 64
        monkeypatch.setenv('GETCONTACT_API_KEY', f'tok|{aes_key}|dev')

        from app.services.phase2.sources.getcontact import GetContactSource, GetContactAPI

        with patch.object(GetContactAPI, 'search_phone', side_effect=Exception('Connection failed')), \
             patch.object(GetContactAPI, 'get_tags', side_effect=Exception('Connection failed')):
            source = GetContactSource()
            # query() wraps query_impl() and catches exceptions
            results = source.query(phone='+79161234567')
            assert results == []


# -----------------------------------------------------------------------
# Phone normalization and country detection
# -----------------------------------------------------------------------

class TestPhoneNormalization:
    """Test phone number normalization for GetContact API."""

    def test_normalize_russian_plus7(self):
        from app.services.phase2.sources.getcontact import _normalize_phone_for_gc
        assert _normalize_phone_for_gc('+79161234567') == '+79161234567'

    def test_normalize_russian_8(self):
        from app.services.phase2.sources.getcontact import _normalize_phone_for_gc
        result = _normalize_phone_for_gc('89161234567')
        assert result == '+79161234567'

    def test_normalize_10_digits(self):
        from app.services.phase2.sources.getcontact import _normalize_phone_for_gc
        result = _normalize_phone_for_gc('9161234567')
        assert result == '+79161234567'

    def test_normalize_with_formatting(self):
        from app.services.phase2.sources.getcontact import _normalize_phone_for_gc
        result = _normalize_phone_for_gc('+7 (916) 123-45-67')
        assert result == '+79161234567'

    def test_detect_russia(self):
        from app.services.phase2.sources.getcontact import _detect_country_code
        assert _detect_country_code('+79161234567') == 'RU'

    def test_detect_ukraine(self):
        from app.services.phase2.sources.getcontact import _detect_country_code
        assert _detect_country_code('+380501234567') == 'UA'

    def test_detect_belarus(self):
        from app.services.phase2.sources.getcontact import _detect_country_code
        assert _detect_country_code('+375291234567') == 'BY'

    def test_detect_kazakhstan(self):
        from app.services.phase2.sources.getcontact import _detect_country_code
        assert _detect_country_code('+77011234567') == 'KZ'


# -----------------------------------------------------------------------
# NumBusterSource tests (ensure no regression)
# -----------------------------------------------------------------------

class TestNumBusterSource:
    """Ensure NumBuster still works in both modes."""

    def test_demo_mode_returns_empty(self):
        """Without API key, should return empty list."""
        from app.services.phase2.sources.getcontact import NumBusterSource
        source = NumBusterSource()
        results = source.query(phone='+79161234567')
        assert results == []

    def test_no_phone_returns_empty(self):
        from app.services.phase2.sources.getcontact import NumBusterSource
        source = NumBusterSource()
        assert source.query(email='test@mail.ru') == []

    def test_is_available(self):
        from app.services.phase2.sources.getcontact import NumBusterSource
        assert NumBusterSource().is_available() is True


# -----------------------------------------------------------------------
# Source metadata tests
# -----------------------------------------------------------------------

class TestGetContactMetadata:
    """Test source metadata and info."""

    def test_source_info(self):
        from app.services.phase2.sources.getcontact import GetContactSource
        source = GetContactSource()
        info = source.get_info()
        assert info['name'] == 'GetContact Lookup'
        assert info['type'] == 'phone'
        assert info['tier'] == 'Platform API'
        assert info['available'] is True

    def test_source_tier(self):
        from app.services.phase2.sources.getcontact import GetContactSource, SourceTier
        source = GetContactSource()
        assert source.source_tier == SourceTier.A
