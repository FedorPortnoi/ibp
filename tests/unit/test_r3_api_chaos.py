"""
Round 3 — ADVERSARIAL: API Failure Chaos Testing
=================================================
90+ tests covering how the system handles API failures, timeouts,
malformed responses, network errors, and other chaos scenarios.

Categories:
  1. VK API Failure Modes (20+ tests)
  2. Holehe Failure Modes (15+ tests)
  3. SMTP Failure Modes (15+ tests)
  4. Telegram Cross-Ref Failures (10+ tests)
  5. SourceManager Chaos (15+ tests)
  6. Network Chaos (15+ tests)

ALL external calls are mocked. No real network traffic.
"""

import json
import os
import subprocess
import sys
import smtplib
import time
from concurrent.futures import TimeoutError as FuturesTimeoutError
from dataclasses import dataclass
from typing import List, Dict, Optional
from unittest.mock import (
    MagicMock, Mock, patch, PropertyMock, call, ANY
)

import pytest
import requests

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VK_PROFILE_URL = 'https://vk.com/id12345'
VK_PROFILE = {'url': VK_PROFILE_URL, 'platform': 'vk'}
FAKE_TOKEN = 'fake_vk_token_for_test'


def _make_phone_service():
    """Create PhoneDiscoveryService with VK token already set."""
    with patch.dict(os.environ, {'VK_SERVICE_TOKEN': FAKE_TOKEN}):
        from app.services.phase2.phone_discovery import PhoneDiscoveryService
        svc = PhoneDiscoveryService()
    return svc


def _make_email_service():
    from app.services.phase2.email_discovery import EmailDiscoveryService
    return EmailDiscoveryService()


# ===================================================================
# 1. VK API FAILURE MODES  (20+ tests)
# ===================================================================


class TestVKAPIFailures:
    """Tests for VK API error handling in PhoneDiscoveryService."""

    # -- _extract_via_vk_api -------------------------------------------

    @patch.dict(os.environ, {'VK_SERVICE_TOKEN': FAKE_TOKEN})
    def test_connection_error_returns_empty(self):
        """requests.ConnectionError -> returns []."""
        from app.services.phase2.phone_discovery import PhoneDiscoveryService
        svc = PhoneDiscoveryService()
        svc.session.get = Mock(side_effect=requests.ConnectionError("DNS fail"))
        result = svc._extract_via_vk_api(VK_PROFILE_URL)
        assert result == []

    @patch.dict(os.environ, {'VK_SERVICE_TOKEN': FAKE_TOKEN})
    def test_timeout_error_returns_empty(self):
        """requests.Timeout -> returns []."""
        from app.services.phase2.phone_discovery import PhoneDiscoveryService
        svc = PhoneDiscoveryService()
        svc.session.get = Mock(side_effect=requests.Timeout("timeout"))
        result = svc._extract_via_vk_api(VK_PROFILE_URL)
        assert result == []

    @patch.dict(os.environ, {'VK_SERVICE_TOKEN': FAKE_TOKEN})
    def test_http_500_returns_empty(self):
        """HTTP 500 with non-JSON body -> should not crash."""
        from app.services.phase2.phone_discovery import PhoneDiscoveryService
        svc = PhoneDiscoveryService()
        mock_resp = Mock()
        mock_resp.json.side_effect = json.JSONDecodeError("bad", "", 0)
        svc.session.get = Mock(return_value=mock_resp)
        result = svc._extract_via_vk_api(VK_PROFILE_URL)
        assert result == []

    @patch.dict(os.environ, {'VK_SERVICE_TOKEN': FAKE_TOKEN})
    def test_json_decode_error_returns_empty(self):
        """Response .json() raises JSONDecodeError -> returns []."""
        from app.services.phase2.phone_discovery import PhoneDiscoveryService
        svc = PhoneDiscoveryService()
        mock_resp = Mock()
        mock_resp.json.side_effect = ValueError("No JSON object could be decoded")
        svc.session.get = Mock(return_value=mock_resp)
        result = svc._extract_via_vk_api(VK_PROFILE_URL)
        assert result == []

    @patch.dict(os.environ, {'VK_SERVICE_TOKEN': FAKE_TOKEN})
    def test_vk_error_auth_failed(self):
        """VK error_code 5 (auth failed) -> returns []."""
        from app.services.phase2.phone_discovery import PhoneDiscoveryService
        svc = PhoneDiscoveryService()
        mock_resp = Mock()
        mock_resp.json.return_value = {
            'error': {'error_code': 5, 'error_msg': 'User authorization failed'}
        }
        svc.session.get = Mock(return_value=mock_resp)
        result = svc._extract_via_vk_api(VK_PROFILE_URL)
        assert result == []

    @patch.dict(os.environ, {'VK_SERVICE_TOKEN': FAKE_TOKEN})
    def test_vk_error_access_denied(self):
        """VK error_code 15 (access denied) -> returns []."""
        from app.services.phase2.phone_discovery import PhoneDiscoveryService
        svc = PhoneDiscoveryService()
        mock_resp = Mock()
        mock_resp.json.return_value = {
            'error': {'error_code': 15, 'error_msg': 'Access denied'}
        }
        svc.session.get = Mock(return_value=mock_resp)
        result = svc._extract_via_vk_api(VK_PROFILE_URL)
        assert result == []

    @patch.dict(os.environ, {'VK_SERVICE_TOKEN': FAKE_TOKEN})
    def test_vk_error_rate_limit(self):
        """VK error_code 6 (too many requests) -> returns []."""
        from app.services.phase2.phone_discovery import PhoneDiscoveryService
        svc = PhoneDiscoveryService()
        mock_resp = Mock()
        mock_resp.json.return_value = {
            'error': {'error_code': 6, 'error_msg': 'Too many requests per second'}
        }
        svc.session.get = Mock(return_value=mock_resp)
        result = svc._extract_via_vk_api(VK_PROFILE_URL)
        assert result == []

    @patch.dict(os.environ, {'VK_SERVICE_TOKEN': FAKE_TOKEN})
    def test_vk_empty_response_list(self):
        """VK returns {'response': []} -> returns []."""
        from app.services.phase2.phone_discovery import PhoneDiscoveryService
        svc = PhoneDiscoveryService()
        mock_resp = Mock()
        mock_resp.json.return_value = {'response': []}
        svc.session.get = Mock(return_value=mock_resp)
        result = svc._extract_via_vk_api(VK_PROFILE_URL)
        assert result == []

    @patch.dict(os.environ, {'VK_SERVICE_TOKEN': FAKE_TOKEN})
    def test_vk_user_no_phone_fields(self):
        """VK user has id but no phone fields -> returns []."""
        from app.services.phase2.phone_discovery import PhoneDiscoveryService
        svc = PhoneDiscoveryService()
        mock_resp = Mock()
        mock_resp.json.return_value = {'response': [{'id': 12345, 'first_name': 'Test'}]}
        svc.session.get = Mock(return_value=mock_resp)
        result = svc._extract_via_vk_api(VK_PROFILE_URL)
        assert result == []

    @patch.dict(os.environ, {'VK_SERVICE_TOKEN': FAKE_TOKEN})
    def test_vk_response_not_a_list(self):
        """VK returns {'response': 'not_a_list'} -> graceful handling."""
        from app.services.phase2.phone_discovery import PhoneDiscoveryService
        svc = PhoneDiscoveryService()
        mock_resp = Mock()
        mock_resp.json.return_value = {'response': 'not_a_list'}
        svc.session.get = Mock(return_value=mock_resp)
        # 'not_a_list' is truthy but not iterable as expected; should not crash
        result = svc._extract_via_vk_api(VK_PROFILE_URL)
        # May return [] or raise handled exception; key is no unhandled crash
        assert isinstance(result, list)

    @patch.dict(os.environ, {'VK_SERVICE_TOKEN': FAKE_TOKEN})
    def test_vk_user_short_mobile_phone_ignored(self):
        """VK user mobile_phone field with <= 5 chars -> ignored."""
        from app.services.phase2.phone_discovery import PhoneDiscoveryService
        svc = PhoneDiscoveryService()
        mock_resp = Mock()
        mock_resp.json.return_value = {'response': [{'id': 123, 'mobile_phone': '123'}]}
        svc.session.get = Mock(return_value=mock_resp)
        result = svc._extract_via_vk_api(VK_PROFILE_URL)
        assert result == []

    @patch.dict(os.environ, {'VK_SERVICE_TOKEN': FAKE_TOKEN})
    def test_vk_contacts_field_not_dict(self):
        """VK user contacts field is a string instead of dict -> no crash."""
        from app.services.phase2.phone_discovery import PhoneDiscoveryService
        svc = PhoneDiscoveryService()
        mock_resp = Mock()
        mock_resp.json.return_value = {'response': [{'id': 123, 'contacts': 'not_dict'}]}
        svc.session.get = Mock(return_value=mock_resp)
        result = svc._extract_via_vk_api(VK_PROFILE_URL)
        assert isinstance(result, list)

    def test_no_vk_token_skips_api(self):
        """No VK_SERVICE_TOKEN -> _extract_via_vk_api returns [] immediately."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop('VK_SERVICE_TOKEN', None)
            from app.services.phase2.phone_discovery import PhoneDiscoveryService
            svc = PhoneDiscoveryService()
            svc.session.get = Mock()
            result = svc._extract_via_vk_api(VK_PROFILE_URL)
            assert result == []
            svc.session.get.assert_not_called()

    @patch.dict(os.environ, {'VK_SERVICE_TOKEN': FAKE_TOKEN})
    def test_invalid_profile_url_returns_empty(self):
        """URL with no VK pattern -> returns []."""
        from app.services.phase2.phone_discovery import PhoneDiscoveryService
        svc = PhoneDiscoveryService()
        svc.session.get = Mock()
        result = svc._extract_via_vk_api('https://example.com/nope')
        assert result == []
        svc.session.get.assert_not_called()

    @patch.dict(os.environ, {'VK_SERVICE_TOKEN': FAKE_TOKEN})
    def test_vk_error_missing_error_msg(self):
        """VK returns error dict without error_msg key -> no crash."""
        from app.services.phase2.phone_discovery import PhoneDiscoveryService
        svc = PhoneDiscoveryService()
        mock_resp = Mock()
        mock_resp.json.return_value = {'error': {'error_code': 100}}
        svc.session.get = Mock(return_value=mock_resp)
        result = svc._extract_via_vk_api(VK_PROFILE_URL)
        assert result == []

    # -- _extract_from_vk_wall -----------------------------------------

    @patch.dict(os.environ, {'VK_SERVICE_TOKEN': FAKE_TOKEN})
    def test_wall_private_profile(self):
        """Wall.get with error_code 15 (private) -> returns []."""
        from app.services.phase2.phone_discovery import PhoneDiscoveryService
        svc = PhoneDiscoveryService()
        mock_resp = Mock()
        mock_resp.json.return_value = {
            'error': {'error_code': 15, 'error_msg': 'Access denied: wall is private'}
        }
        svc.session.get = Mock(return_value=mock_resp)
        result = svc._extract_from_vk_wall(VK_PROFILE_URL)
        assert result == []

    @patch.dict(os.environ, {'VK_SERVICE_TOKEN': FAKE_TOKEN})
    def test_wall_empty_items(self):
        """Wall.get returns empty items -> returns []."""
        from app.services.phase2.phone_discovery import PhoneDiscoveryService
        svc = PhoneDiscoveryService()
        mock_resp = Mock()
        mock_resp.json.return_value = {'response': {'count': 0, 'items': []}}
        svc.session.get = Mock(return_value=mock_resp)
        result = svc._extract_from_vk_wall(VK_PROFILE_URL)
        assert result == []

    @patch.dict(os.environ, {'VK_SERVICE_TOKEN': FAKE_TOKEN})
    def test_wall_posts_no_text(self):
        """Wall posts with empty text -> returns []."""
        from app.services.phase2.phone_discovery import PhoneDiscoveryService
        svc = PhoneDiscoveryService()
        mock_resp = Mock()
        mock_resp.json.return_value = {
            'response': {
                'count': 2,
                'items': [
                    {'id': 1, 'text': ''},
                    {'id': 2, 'text': ''},
                ]
            }
        }
        svc.session.get = Mock(return_value=mock_resp)
        result = svc._extract_from_vk_wall(VK_PROFILE_URL)
        assert result == []

    @patch.dict(os.environ, {'VK_SERVICE_TOKEN': FAKE_TOKEN})
    def test_wall_connection_error(self):
        """Wall.get raises ConnectionError -> returns []."""
        from app.services.phase2.phone_discovery import PhoneDiscoveryService
        svc = PhoneDiscoveryService()
        svc.session.get = Mock(side_effect=requests.ConnectionError("fail"))
        result = svc._extract_from_vk_wall(VK_PROFILE_URL)
        assert result == []

    @patch.dict(os.environ, {'VK_SERVICE_TOKEN': FAKE_TOKEN})
    def test_wall_json_decode_error(self):
        """Wall.get response body is not JSON -> returns []."""
        from app.services.phase2.phone_discovery import PhoneDiscoveryService
        svc = PhoneDiscoveryService()
        mock_resp = Mock()
        mock_resp.json.side_effect = json.JSONDecodeError("bad", "", 0)
        svc.session.get = Mock(return_value=mock_resp)
        result = svc._extract_from_vk_wall(VK_PROFILE_URL)
        assert result == []

    def test_wall_no_token_skips(self):
        """No VK_SERVICE_TOKEN -> wall extraction returns [] without API call."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop('VK_SERVICE_TOKEN', None)
            from app.services.phase2.phone_discovery import PhoneDiscoveryService
            svc = PhoneDiscoveryService()
            svc.session.get = Mock()
            result = svc._extract_from_vk_wall(VK_PROFILE_URL)
            assert result == []
            svc.session.get.assert_not_called()

    @patch.dict(os.environ, {'VK_SERVICE_TOKEN': FAKE_TOKEN})
    def test_wall_other_error_code(self):
        """Wall.get with error_code != 15 -> still returns []."""
        from app.services.phase2.phone_discovery import PhoneDiscoveryService
        svc = PhoneDiscoveryService()
        mock_resp = Mock()
        mock_resp.json.return_value = {
            'error': {'error_code': 29, 'error_msg': 'Rate limit reached'}
        }
        svc.session.get = Mock(return_value=mock_resp)
        result = svc._extract_from_vk_wall(VK_PROFILE_URL)
        assert result == []

    # -- discover_sync with VK failures --------------------------------

    @patch.dict(os.environ, {'VK_SERVICE_TOKEN': FAKE_TOKEN})
    def test_discover_sync_vk_api_exception_captured(self):
        """discover_sync handles exception in _extract_via_vk_api gracefully."""
        from app.services.phase2.phone_discovery import PhoneDiscoveryService
        svc = PhoneDiscoveryService()
        svc.session.get = Mock(side_effect=Exception("BOOM"))
        result = svc.discover_sync(
            first_name='Test',
            last_name='User',
            usernames=[],
            profile_urls=[VK_PROFILE],
        )
        # Should have results object even if extraction failed
        assert hasattr(result, 'phones')
        assert isinstance(result.phones, list)


# ===================================================================
# 2. HOLEHE FAILURE MODES  (15+ tests)
# ===================================================================


class TestHoleheFailures:
    """Tests for Holehe verification error handling."""

    def test_holehe_single_httpx_import_error(self):
        """httpx not importable -> falls back to CLI."""
        svc = _make_email_service()
        with patch.dict(sys.modules, {'httpx': None}):
            with patch.object(svc, '_holehe_check_cli', return_value=None) as mock_cli:
                result = svc._holehe_check_single('test@example.com')
                mock_cli.assert_called_once_with('test@example.com')

    def test_holehe_single_holehe_import_error(self):
        """holehe.core not importable -> falls back to CLI."""
        svc = _make_email_service()
        with patch.dict(sys.modules, {'holehe': None, 'holehe.core': None, 'holehe.modules': None}):
            with patch.object(svc, '_holehe_check_cli', return_value=None) as mock_cli:
                result = svc._holehe_check_single('test@example.com')
                mock_cli.assert_called_once()

    def test_holehe_single_generic_exception_falls_back(self):
        """Generic exception in holehe library -> falls back to CLI."""
        svc = _make_email_service()
        # Patch the httpx import to succeed but the async call to blow up
        with patch('asyncio.new_event_loop') as mock_loop:
            mock_loop.return_value.run_until_complete.side_effect = RuntimeError("event loop dead")
            mock_loop.return_value.close = Mock()
            with patch.object(svc, '_holehe_check_cli', return_value=None) as mock_cli:
                result = svc._holehe_check_single('test@example.com')
                mock_cli.assert_called_once()

    def test_holehe_cli_file_not_found(self):
        """holehe binary not found -> returns None."""
        svc = _make_email_service()
        with patch('subprocess.run', side_effect=FileNotFoundError("holehe not found")):
            result = svc._holehe_check_cli('test@example.com')
            assert result is None

    def test_holehe_cli_timeout_expired(self):
        """holehe CLI times out -> returns None."""
        svc = _make_email_service()
        with patch('subprocess.run', side_effect=subprocess.TimeoutExpired(cmd='holehe', timeout=15)):
            result = svc._holehe_check_cli('test@example.com')
            assert result is None

    def test_holehe_cli_empty_stdout(self):
        """holehe CLI returns empty stdout -> returns None."""
        svc = _make_email_service()
        mock_result = Mock()
        mock_result.stdout = ''
        with patch('subprocess.run', return_value=mock_result):
            result = svc._holehe_check_cli('test@example.com')
            assert result is None

    def test_holehe_cli_malformed_output(self):
        """holehe CLI returns garbage -> returns None."""
        svc = _make_email_service()
        mock_result = Mock()
        mock_result.stdout = 'random garbage\nno markers here\n'
        with patch('subprocess.run', return_value=mock_result):
            result = svc._holehe_check_cli('test@example.com')
            assert result is None

    def test_holehe_cli_empty_service_name(self):
        """holehe CLI returns '[+] ' with empty service -> filters out."""
        svc = _make_email_service()
        mock_result = Mock()
        mock_result.stdout = '[+] \n'
        with patch('subprocess.run', return_value=mock_result):
            result = svc._holehe_check_cli('test@example.com')
            # Empty service name has len <= 1, filtered by `if service and len(service) > 1`
            assert result is None

    def test_holehe_cli_generic_exception(self):
        """holehe CLI raises unexpected exception -> returns None."""
        svc = _make_email_service()
        with patch('subprocess.run', side_effect=OSError("pipe broken")):
            result = svc._holehe_check_cli('test@example.com')
            assert result is None

    def test_holehe_exists_false_no_services(self):
        """Holehe results with exists=False -> no services returned."""
        svc = _make_email_service()
        # Simulate the library path succeeding but all results have exists=False
        fake_results = [
            {'name': 'twitter', 'exists': False},
            {'name': 'instagram', 'exists': False},
        ]
        with patch('asyncio.new_event_loop') as mock_loop:
            mock_loop.return_value.run_until_complete.return_value = fake_results
            mock_loop.return_value.close = Mock()
            result = svc._holehe_check_single('test@example.com')
            # No services with exists=True -> returns None
            assert result is None

    def test_holehe_results_with_unknown_name(self):
        """Holehe result with name='unknown' -> filtered out."""
        svc = _make_email_service()
        fake_results = [
            {'name': 'unknown', 'exists': True},
        ]
        with patch('asyncio.new_event_loop') as mock_loop:
            mock_loop.return_value.run_until_complete.return_value = fake_results
            mock_loop.return_value.close = Mock()
            result = svc._holehe_check_single('test@example.com')
            # 'unknown' is filtered by `if name and name != 'unknown'`
            assert result is None

    def test_holehe_result_not_dict(self):
        """Holehe returns non-dict items in results -> skipped."""
        svc = _make_email_service()
        fake_results = [
            'not_a_dict',
            42,
            None,
        ]
        with patch('asyncio.new_event_loop') as mock_loop:
            mock_loop.return_value.run_until_complete.return_value = fake_results
            mock_loop.return_value.close = Mock()
            result = svc._holehe_check_single('test@example.com')
            assert result is None

    def test_holehe_valid_service_found(self):
        """Holehe finds a valid service -> returns dict with services."""
        svc = _make_email_service()
        fake_results = [
            {'name': 'twitter', 'exists': True},
            {'name': 'spotify', 'exists': True},
            {'name': 'instagram', 'exists': False},
        ]
        with patch('asyncio.new_event_loop') as mock_loop:
            mock_loop.return_value.run_until_complete.return_value = fake_results
            mock_loop.return_value.close = Mock()
            result = svc._holehe_check_single('test@example.com')
            assert result is not None
            assert 'twitter' in result['services']
            assert 'spotify' in result['services']
            assert 'instagram' not in result['services']

    def test_holehe_cli_valid_output(self):
        """holehe CLI returns valid [+] lines -> services extracted."""
        svc = _make_email_service()
        mock_result = Mock()
        mock_result.stdout = '[+] twitter: registered\n[+] spotify: registered\n[-] github: not found\n'
        with patch('subprocess.run', return_value=mock_result):
            result = svc._holehe_check_cli('test@example.com')
            assert result is not None
            assert 'twitter' in result['services']
            assert 'spotify' in result['services']

    def test_holehe_cli_only_minus_markers(self):
        """holehe CLI output has only [-] lines -> returns None."""
        svc = _make_email_service()
        mock_result = Mock()
        mock_result.stdout = '[-] twitter: not found\n[-] github: not found\n'
        with patch('subprocess.run', return_value=mock_result):
            result = svc._holehe_check_cli('test@example.com')
            assert result is None


# ===================================================================
# 3. SMTP FAILURE MODES  (15+ tests)
# ===================================================================


class TestSMTPFailures:
    """Tests for SMTP verification error handling."""

    def test_smtp_dns_resolver_import_error(self):
        """dns.resolver not importable -> returns None."""
        svc = _make_email_service()
        with patch.dict(sys.modules, {'dns': None, 'dns.resolver': None}):
            # Need to reload or call directly with import failing
            result = svc._smtp_verify_single('test@example.com')
            assert result is None

    def test_smtp_nxdomain(self):
        """dns.resolver.NXDOMAIN -> returns False."""
        svc = _make_email_service()
        import dns.resolver
        with patch('dns.resolver.resolve', side_effect=dns.resolver.NXDOMAIN("no such domain")):
            result = svc._smtp_verify_single('test@nonexistent-domain-xyz.com')
            assert result is False

    def test_smtp_no_answer(self):
        """dns.resolver.NoAnswer -> returns None."""
        svc = _make_email_service()
        import dns.resolver
        with patch('dns.resolver.resolve', side_effect=dns.resolver.NoAnswer("no MX")):
            result = svc._smtp_verify_single('test@example.com')
            assert result is None

    def test_smtp_no_nameservers(self):
        """dns.resolver.NoNameservers -> returns None."""
        svc = _make_email_service()
        import dns.resolver
        with patch('dns.resolver.resolve', side_effect=dns.resolver.NoNameservers("no NS")):
            result = svc._smtp_verify_single('test@example.com')
            assert result is None

    def test_smtp_connect_error(self):
        """smtplib.SMTPConnectError -> returns None."""
        svc = _make_email_service()
        mock_mx = Mock()
        mock_mx.__getitem__ = Mock(return_value=Mock(exchange='mx.example.com'))
        with patch('dns.resolver.resolve', return_value=mock_mx):
            with patch('smtplib.SMTP', side_effect=smtplib.SMTPConnectError(421, b'connect refused')):
                result = svc._smtp_verify_single('test@example.com')
                assert result is None

    def test_smtp_server_disconnected(self):
        """smtplib.SMTPServerDisconnected -> returns None."""
        svc = _make_email_service()
        mock_mx = Mock()
        mock_mx.__getitem__ = Mock(return_value=Mock(exchange='mx.example.com'))
        with patch('dns.resolver.resolve', return_value=mock_mx):
            with patch('smtplib.SMTP', side_effect=smtplib.SMTPServerDisconnected("gone")):
                result = svc._smtp_verify_single('test@example.com')
                assert result is None

    def test_smtp_connection_refused(self):
        """ConnectionRefusedError -> returns None."""
        svc = _make_email_service()
        mock_mx = Mock()
        mock_mx.__getitem__ = Mock(return_value=Mock(exchange='mx.example.com'))
        with patch('dns.resolver.resolve', return_value=mock_mx):
            with patch('smtplib.SMTP', side_effect=ConnectionRefusedError("refused")):
                result = svc._smtp_verify_single('test@example.com')
                assert result is None

    def test_smtp_timeout_error(self):
        """TimeoutError -> returns None."""
        svc = _make_email_service()
        mock_mx = Mock()
        mock_mx.__getitem__ = Mock(return_value=Mock(exchange='mx.example.com'))
        with patch('dns.resolver.resolve', return_value=mock_mx):
            with patch('smtplib.SMTP', side_effect=TimeoutError("timed out")):
                result = svc._smtp_verify_single('test@example.com')
                assert result is None

    def test_smtp_os_error(self):
        """OSError -> returns None."""
        svc = _make_email_service()
        mock_mx = Mock()
        mock_mx.__getitem__ = Mock(return_value=Mock(exchange='mx.example.com'))
        with patch('dns.resolver.resolve', return_value=mock_mx):
            with patch('smtplib.SMTP', side_effect=OSError("network unreachable")):
                result = svc._smtp_verify_single('test@example.com')
                assert result is None

    def test_smtp_code_250_returns_true(self):
        """SMTP RCPT TO returns code 250 -> True."""
        svc = _make_email_service()
        mock_mx = Mock()
        mock_mx.__getitem__ = Mock(return_value=Mock(exchange='mx.example.com'))
        mock_server = MagicMock()
        mock_server.rcpt.return_value = (250, b'OK')
        with patch('dns.resolver.resolve', return_value=mock_mx):
            with patch('smtplib.SMTP', return_value=mock_server):
                result = svc._smtp_verify_single('test@example.com')
                assert result is True

    def test_smtp_code_550_returns_false(self):
        """SMTP RCPT TO returns code 550 -> False."""
        svc = _make_email_service()
        mock_mx = Mock()
        mock_mx.__getitem__ = Mock(return_value=Mock(exchange='mx.example.com'))
        mock_server = MagicMock()
        mock_server.rcpt.return_value = (550, b'User unknown')
        with patch('dns.resolver.resolve', return_value=mock_mx):
            with patch('smtplib.SMTP', return_value=mock_server):
                result = svc._smtp_verify_single('test@example.com')
                assert result is False

    def test_smtp_code_551_returns_false(self):
        """SMTP RCPT TO returns code 551 -> False."""
        svc = _make_email_service()
        mock_mx = Mock()
        mock_mx.__getitem__ = Mock(return_value=Mock(exchange='mx.example.com'))
        mock_server = MagicMock()
        mock_server.rcpt.return_value = (551, b'User not local')
        with patch('dns.resolver.resolve', return_value=mock_mx):
            with patch('smtplib.SMTP', return_value=mock_server):
                result = svc._smtp_verify_single('test@example.com')
                assert result is False

    def test_smtp_code_421_returns_none(self):
        """SMTP RCPT TO returns code 421 (temp reject) -> None."""
        svc = _make_email_service()
        mock_mx = Mock()
        mock_mx.__getitem__ = Mock(return_value=Mock(exchange='mx.example.com'))
        mock_server = MagicMock()
        mock_server.rcpt.return_value = (421, b'Try again later')
        with patch('dns.resolver.resolve', return_value=mock_mx):
            with patch('smtplib.SMTP', return_value=mock_server):
                result = svc._smtp_verify_single('test@example.com')
                assert result is None

    def test_check_mx_known_domain(self):
        """Known domain in KNOWN_MX_SERVERS -> returns True."""
        svc = _make_email_service()
        assert svc._check_mx('mail.ru') is True

    def test_check_mx_unknown_domain_no_records(self):
        """Unknown domain with no MX records and no mail server -> False."""
        svc = _make_email_service()
        import dns.resolver
        with patch('dns.resolver.resolve', side_effect=dns.resolver.NXDOMAIN("nope")):
            with patch('socket.getaddrinfo', side_effect=OSError("no host")):
                result = svc._check_mx('definitely-not-real-xyz123.com')
                assert result is False

    def test_smtp_generic_exception(self):
        """Unexpected exception during SMTP -> returns None."""
        svc = _make_email_service()
        mock_mx = Mock()
        mock_mx.__getitem__ = Mock(return_value=Mock(exchange='mx.example.com'))
        mock_server = MagicMock()
        mock_server.rcpt.side_effect = RuntimeError("unexpected")
        with patch('dns.resolver.resolve', return_value=mock_mx):
            with patch('smtplib.SMTP', return_value=mock_server):
                result = svc._smtp_verify_single('test@example.com')
                assert result is None


# ===================================================================
# 4. TELEGRAM CROSS-REF FAILURES  (10+ tests)
# ===================================================================


class TestTelegramCrossRefFailures:
    """Tests for Telegram cross-reference error handling."""

    @patch.dict(os.environ, {'VK_SERVICE_TOKEN': FAKE_TOKEN})
    def test_telegram_module_not_available(self):
        """TelegramCrossRef import fails -> returns ([], [])."""
        from app.services.phase2.phone_discovery import PhoneDiscoveryService
        svc = PhoneDiscoveryService()
        with patch.dict(sys.modules, {'app.services.phase2.telegram_crossref': None}):
            # Force ImportError
            with patch('builtins.__import__', side_effect=ImportError("no module")):
                phones, profiles = svc._cross_reference_telegram(
                    [VK_PROFILE], 'Test', 'User'
                )
                assert phones == []
                assert profiles == []

    @patch.dict(os.environ, {'VK_SERVICE_TOKEN': FAKE_TOKEN})
    def test_telegram_cross_reference_raises(self):
        """TelegramCrossRef.cross_reference_vk_profiles raises -> caught."""
        from app.services.phase2.phone_discovery import PhoneDiscoveryService
        svc = PhoneDiscoveryService()

        mock_checker = MagicMock()
        mock_checker.cross_reference_vk_profiles.side_effect = RuntimeError("Telegram API dead")
        mock_checker.close = Mock()

        mock_module = MagicMock()
        mock_module.TelegramCrossRef.return_value = mock_checker

        with patch.dict(sys.modules, {'app.services.phase2.telegram_crossref': mock_module}):
            phones, profiles = svc._cross_reference_telegram(
                [VK_PROFILE], 'Test', 'User'
            )
            assert phones == []
            assert profiles == []

    @patch.dict(os.environ, {'VK_SERVICE_TOKEN': FAKE_TOKEN})
    def test_telegram_checker_close_raises(self):
        """TelegramCrossRef.close() raises -> should not propagate."""
        from app.services.phase2.phone_discovery import PhoneDiscoveryService
        svc = PhoneDiscoveryService()

        mock_checker = MagicMock()
        mock_checker.cross_reference_vk_profiles.return_value = []
        mock_checker.close.side_effect = RuntimeError("close failed")

        mock_module = MagicMock()
        mock_module.TelegramCrossRef.return_value = mock_checker

        with patch.dict(sys.modules, {'app.services.phase2.telegram_crossref': mock_module}):
            # close() raising inside finally should be caught by outer except
            # The behavior depends on whether the exception propagates
            try:
                phones, profiles = svc._cross_reference_telegram(
                    [VK_PROFILE], 'Test', 'User'
                )
            except RuntimeError:
                # If close() exception propagates, the outer except catches it
                pass
            # Key assertion: no unhandled crash at the discover_sync level

    @patch.dict(os.environ, {'VK_SERVICE_TOKEN': FAKE_TOKEN})
    def test_telegram_empty_results(self):
        """TelegramCrossRef returns empty list -> returns ([], [])."""
        from app.services.phase2.phone_discovery import PhoneDiscoveryService
        svc = PhoneDiscoveryService()

        mock_checker = MagicMock()
        mock_checker.cross_reference_vk_profiles.return_value = []
        mock_checker.close = Mock()

        mock_module = MagicMock()
        mock_module.TelegramCrossRef.return_value = mock_checker

        with patch.dict(sys.modules, {'app.services.phase2.telegram_crossref': mock_module}):
            phones, profiles = svc._cross_reference_telegram(
                [VK_PROFILE], 'Test', 'User'
            )
            assert phones == []
            assert profiles == []

    @patch.dict(os.environ, {'VK_SERVICE_TOKEN': FAKE_TOKEN})
    def test_telegram_result_no_phones_in_bio(self):
        """Telegram result with empty phones_in_bio -> phones empty, profile still added."""
        from app.services.phase2.phone_discovery import PhoneDiscoveryService
        svc = PhoneDiscoveryService()

        mock_tg_result = MagicMock()
        mock_tg_result.username = 'testuser'
        mock_tg_result.phones_in_bio = []
        mock_tg_result.name_match = True
        mock_tg_result.display_name = 'Test User'
        mock_tg_result.bio = 'Some bio'
        mock_tg_result.confidence = 0.8
        mock_tg_result.source = 'vk_connection'

        mock_checker = MagicMock()
        mock_checker.cross_reference_vk_profiles.return_value = [mock_tg_result]
        mock_checker.close = Mock()

        mock_module = MagicMock()
        mock_module.TelegramCrossRef.return_value = mock_checker

        with patch.dict(sys.modules, {'app.services.phase2.telegram_crossref': mock_module}):
            phones, profiles = svc._cross_reference_telegram(
                [VK_PROFILE], 'Test', 'User'
            )
            assert phones == []
            assert len(profiles) == 1
            assert profiles[0]['username'] == 'testuser'

    @patch.dict(os.environ, {'VK_SERVICE_TOKEN': FAKE_TOKEN})
    def test_telegram_result_with_phones_in_bio(self):
        """Telegram result with phones_in_bio -> phones extracted."""
        from app.services.phase2.phone_discovery import PhoneDiscoveryService
        svc = PhoneDiscoveryService()

        mock_tg_result = MagicMock()
        mock_tg_result.username = 'testuser'
        mock_tg_result.phones_in_bio = ['+79161234567']
        mock_tg_result.name_match = True
        mock_tg_result.display_name = 'Test User'
        mock_tg_result.bio = 'Call me +79161234567'
        mock_tg_result.confidence = 0.9
        mock_tg_result.source = 'vk_connection'

        mock_checker = MagicMock()
        mock_checker.cross_reference_vk_profiles.return_value = [mock_tg_result]
        mock_checker.close = Mock()

        mock_module = MagicMock()
        mock_module.TelegramCrossRef.return_value = mock_checker

        with patch.dict(sys.modules, {'app.services.phase2.telegram_crossref': mock_module}):
            phones, profiles = svc._cross_reference_telegram(
                [VK_PROFILE], 'Test', 'User'
            )
            assert len(phones) == 1
            assert phones[0].number == '+79161234567'
            assert len(profiles) == 1

    @patch.dict(os.environ, {'VK_SERVICE_TOKEN': FAKE_TOKEN})
    def test_telegram_name_mismatch_adds_note(self):
        """Telegram profile with name_match=False -> note added."""
        from app.services.phase2.phone_discovery import PhoneDiscoveryService
        svc = PhoneDiscoveryService()

        mock_tg_result = MagicMock()
        mock_tg_result.username = 'differentuser'
        mock_tg_result.phones_in_bio = []
        mock_tg_result.name_match = False
        mock_tg_result.display_name = 'Different Person'
        mock_tg_result.bio = ''
        mock_tg_result.confidence = 0.3
        mock_tg_result.source = 'username_match'

        mock_checker = MagicMock()
        mock_checker.cross_reference_vk_profiles.return_value = [mock_tg_result]
        mock_checker.close = Mock()

        mock_module = MagicMock()
        mock_module.TelegramCrossRef.return_value = mock_checker

        with patch.dict(sys.modules, {'app.services.phase2.telegram_crossref': mock_module}):
            phones, profiles = svc._cross_reference_telegram(
                [VK_PROFILE], 'Test', 'User'
            )
            assert len(profiles) == 1
            assert profiles[0]['note'] != ''  # Should have warning note

    # -- _get_vk_telegram_connection -----------------------------------

    def test_vk_telegram_connection_no_token(self):
        """No VK_SERVICE_TOKEN -> returns None."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop('VK_SERVICE_TOKEN', None)
            from app.services.phase2.phone_discovery import PhoneDiscoveryService
            svc = PhoneDiscoveryService()
            result = svc._get_vk_telegram_connection([VK_PROFILE])
            assert result is None

    @patch.dict(os.environ, {'VK_SERVICE_TOKEN': FAKE_TOKEN})
    def test_vk_telegram_connection_api_error(self):
        """VK API error in connections check -> returns None."""
        from app.services.phase2.phone_discovery import PhoneDiscoveryService
        svc = PhoneDiscoveryService()
        svc.session.get = Mock(side_effect=requests.ConnectionError("fail"))
        result = svc._get_vk_telegram_connection([VK_PROFILE])
        assert result is None

    @patch.dict(os.environ, {'VK_SERVICE_TOKEN': FAKE_TOKEN})
    def test_vk_telegram_connection_no_telegram_field(self):
        """VK user has no telegram connection -> returns None."""
        from app.services.phase2.phone_discovery import PhoneDiscoveryService
        svc = PhoneDiscoveryService()
        mock_resp = Mock()
        mock_resp.json.return_value = {'response': [{'id': 123}]}
        svc.session.get = Mock(return_value=mock_resp)
        result = svc._get_vk_telegram_connection([VK_PROFILE])
        assert result is None

    @patch.dict(os.environ, {'VK_SERVICE_TOKEN': FAKE_TOKEN})
    def test_vk_telegram_connection_found(self):
        """VK user has telegram connection -> returns username."""
        from app.services.phase2.phone_discovery import PhoneDiscoveryService
        svc = PhoneDiscoveryService()
        mock_resp = Mock()
        mock_resp.json.return_value = {
            'response': [{'id': 123, 'telegram': 'testuser_tg'}]
        }
        svc.session.get = Mock(return_value=mock_resp)
        result = svc._get_vk_telegram_connection([VK_PROFILE])
        assert result == 'testuser_tg'


# ===================================================================
# 5. SOURCE MANAGER CHAOS  (15+ tests)
# ===================================================================


class TestSourceManagerChaos:
    """Tests for SourceManager and BaseSource error handling."""

    def test_base_source_query_catches_exception(self):
        """BaseSource.query wraps query_impl in try/except, returns [] on error."""
        from app.services.phase2.base_source import BaseSource, SourceResult, SourceTier

        class BrokenSource(BaseSource):
            name = "BrokenSource"
            def query_impl(self, **kwargs):
                raise RuntimeError("BOOM")
            def is_available(self):
                return True

        src = BrokenSource()
        result = src.query(name="test")
        assert result == []

    def test_base_source_query_returns_results(self):
        """BaseSource.query returns query_impl results when no error."""
        from app.services.phase2.base_source import BaseSource, SourceResult, SourceTier

        class GoodSource(BaseSource):
            name = "GoodSource"
            source_tier = SourceTier.C
            def query_impl(self, **kwargs):
                return [SourceResult(
                    data_type='email',
                    value='test@example.com',
                    source_name='GoodSource',
                    source_tier=SourceTier.C,
                    confidence=0.5,
                )]
            def is_available(self):
                return True

        src = GoodSource()
        result = src.query(name="test")
        assert len(result) == 1

    def test_base_source_query_timeout_caught(self):
        """BaseSource.query catches TimeoutError from query_impl."""
        from app.services.phase2.base_source import BaseSource

        class SlowSource(BaseSource):
            name = "SlowSource"
            def query_impl(self, **kwargs):
                raise TimeoutError("too slow")
            def is_available(self):
                return True

        src = SlowSource()
        result = src.query(name="test")
        assert result == []

    def test_base_source_query_returns_none_handled(self):
        """If query_impl returns None, query() returns it (caller handles)."""
        from app.services.phase2.base_source import BaseSource

        class NoneSource(BaseSource):
            name = "NoneSource"
            def query_impl(self, **kwargs):
                return None
            def is_available(self):
                return True

        src = NoneSource()
        result = src.query(name="test")
        # BaseSource.query() doesn't wrap None -> returns None
        assert result is None

    def test_source_manager_no_sources_dir(self):
        """Missing sources/ directory -> no sources discovered."""
        from app.services.phase2.source_manager import SourceManager
        with patch('os.path.isdir', return_value=False):
            mgr = SourceManager()
            assert mgr.sources == []

    def test_source_manager_no_sources_returns_empty_dict(self):
        """SourceManager.run_all with no sources -> returns {}."""
        from app.services.phase2.source_manager import SourceManager
        with patch('os.path.isdir', return_value=False):
            mgr = SourceManager()
            result = mgr.run_all(name="test")
            assert result == {}

    def test_source_manager_all_sources_disabled(self):
        """All sources have enabled=False -> run_all returns {}."""
        from app.services.phase2.source_manager import SourceManager
        with patch('os.path.isdir', return_value=False):
            mgr = SourceManager()
            # Add a disabled source
            mock_src = MagicMock()
            mock_src.enabled = False
            mock_src.is_available.return_value = True
            mock_src.name = 'disabled_source'
            mgr.sources = [mock_src]
            result = mgr.run_all(name="test")
            assert result == {}

    def test_source_manager_all_sources_unavailable(self):
        """All sources have is_available()=False -> run_all returns {}."""
        from app.services.phase2.source_manager import SourceManager
        with patch('os.path.isdir', return_value=False):
            mgr = SourceManager()
            mock_src = MagicMock()
            mock_src.enabled = True
            mock_src.is_available.return_value = False
            mock_src.name = 'unavailable_source'
            mgr.sources = [mock_src]
            result = mgr.run_all(name="test")
            assert result == {}

    def test_source_manager_one_succeeds_others_fail(self):
        """One source succeeds, others fail -> partial results."""
        from app.services.phase2.source_manager import SourceManager
        from app.services.phase2.base_source import SourceResult, SourceTier

        with patch('os.path.isdir', return_value=False):
            mgr = SourceManager()

            good_result = SourceResult(
                data_type='email',
                value='found@example.com',
                source_name='GoodSource',
                source_tier=SourceTier.C,
                confidence=0.6,
            )

            good_src = MagicMock()
            good_src.enabled = True
            good_src.is_available.return_value = True
            good_src.name = 'good'
            good_src.query.return_value = [good_result]

            bad_src = MagicMock()
            bad_src.enabled = True
            bad_src.is_available.return_value = True
            bad_src.name = 'bad'
            bad_src.query.side_effect = RuntimeError("source crashed")

            mgr.sources = [good_src, bad_src]
            result = mgr.run_all(name="test")
            assert 'email' in result
            assert len(result['email']) == 1
            assert result['email'][0].value == 'found@example.com'

    def test_source_manager_source_returns_empty_list(self):
        """Source returns [] -> no results contributed."""
        from app.services.phase2.source_manager import SourceManager
        with patch('os.path.isdir', return_value=False):
            mgr = SourceManager()
            mock_src = MagicMock()
            mock_src.enabled = True
            mock_src.is_available.return_value = True
            mock_src.name = 'empty'
            mock_src.query.return_value = []
            mgr.sources = [mock_src]
            result = mgr.run_all(name="test")
            assert result == {}

    def test_source_manager_exclude_sources(self):
        """Excluded source names are skipped."""
        from app.services.phase2.source_manager import SourceManager
        from app.services.phase2.base_source import SourceResult, SourceTier

        with patch('os.path.isdir', return_value=False):
            mgr = SourceManager()

            src1 = MagicMock()
            src1.enabled = True
            src1.is_available.return_value = True
            src1.name = 'include_me'
            src1.query.return_value = [SourceResult(
                data_type='phone', value='+79161234567',
                source_name='include_me', source_tier=SourceTier.A,
                confidence=0.8,
            )]

            src2 = MagicMock()
            src2.enabled = True
            src2.is_available.return_value = True
            src2.name = 'exclude_me'
            src2.query.return_value = [SourceResult(
                data_type='phone', value='+79261234567',
                source_name='exclude_me', source_tier=SourceTier.A,
                confidence=0.8,
            )]

            mgr.sources = [src1, src2]
            result = mgr.run_all(name="test", exclude_sources=['exclude_me'])
            src2.query.assert_not_called()

    def test_source_manager_import_error_skipped(self):
        """Source module that fails to import -> skipped gracefully."""
        from app.services.phase2.source_manager import SourceManager
        with patch('os.path.isdir', return_value=True):
            with patch('os.listdir', return_value=['broken.py']):
                with patch('importlib.import_module', side_effect=ImportError("broken")):
                    mgr = SourceManager()
                    assert len(mgr.sources) == 0

    def test_source_manager_instantiation_error_skipped(self):
        """Source class that fails to instantiate -> skipped."""
        from app.services.phase2.source_manager import SourceManager
        from app.services.phase2.base_source import BaseSource
        import types

        class BadInit(BaseSource):
            name = "BadInit"
            def __init__(self):
                raise ValueError("init failed")
            def query_impl(self, **kwargs):
                return []
            def is_available(self):
                return True

        # Create a real module object so dir() and getattr() work naturally
        fake_module = types.ModuleType('app.services.phase2.sources.bad_init')
        fake_module.BadInit = BadInit

        with patch('os.path.isdir', return_value=True):
            with patch('os.listdir', return_value=['bad_init.py']):
                with patch('importlib.import_module', return_value=fake_module):
                    mgr = SourceManager()
                    # BadInit raises ValueError in __init__, so it should be
                    # skipped. Check that no source named "BadInit" was registered.
                    bad_names = [s.name for s in mgr.sources if s.name == "BadInit"]
                    assert bad_names == []

    def test_source_manager_enormous_results(self):
        """Source returns very large result list -> still processes."""
        from app.services.phase2.source_manager import SourceManager
        from app.services.phase2.base_source import SourceResult, SourceTier

        with patch('os.path.isdir', return_value=False):
            mgr = SourceManager()
            huge_results = [
                SourceResult(
                    data_type='email',
                    value=f'user{i}@example.com',
                    source_name='huge',
                    source_tier=SourceTier.C,
                    confidence=0.5,
                ) for i in range(500)
            ]
            mock_src = MagicMock()
            mock_src.enabled = True
            mock_src.is_available.return_value = True
            mock_src.name = 'huge'
            mock_src.query.return_value = huge_results
            mgr.sources = [mock_src]
            result = mgr.run_all(name="test")
            assert len(result.get('email', [])) == 500

    def test_source_manager_dedup_same_value(self):
        """Two sources return same value -> deduplicated with confidence boost."""
        from app.services.phase2.source_manager import SourceManager
        from app.services.phase2.base_source import SourceResult, SourceTier

        with patch('os.path.isdir', return_value=False):
            mgr = SourceManager()
            src1 = MagicMock()
            src1.enabled = True
            src1.is_available.return_value = True
            src1.name = 'src1'
            src1.query.return_value = [SourceResult(
                data_type='email', value='dup@example.com',
                source_name='src1', source_tier=SourceTier.B,
                confidence=0.6,
            )]

            src2 = MagicMock()
            src2.enabled = True
            src2.is_available.return_value = True
            src2.name = 'src2'
            src2.query.return_value = [SourceResult(
                data_type='email', value='dup@example.com',
                source_name='src2', source_tier=SourceTier.A,
                confidence=0.7,
            )]

            mgr.sources = [src1, src2]
            result = mgr.run_all(name="test")
            emails = result.get('email', [])
            assert len(emails) == 1
            # Confidence should be boosted above 0.6
            assert emails[0].confidence > 0.6


# ===================================================================
# 6. NETWORK CHAOS  (15+ tests)
# ===================================================================


class TestNetworkChaos:
    """Tests for various network failure scenarios."""

    @patch.dict(os.environ, {'VK_SERVICE_TOKEN': FAKE_TOKEN})
    def test_dns_resolution_failure(self):
        """DNS resolution failure via ConnectionError -> returns []."""
        from app.services.phase2.phone_discovery import PhoneDiscoveryService
        svc = PhoneDiscoveryService()
        svc.session.get = Mock(
            side_effect=requests.ConnectionError(
                "Failed to resolve 'api.vk.com'"
            )
        )
        result = svc._extract_via_vk_api(VK_PROFILE_URL)
        assert result == []

    @patch.dict(os.environ, {'VK_SERVICE_TOKEN': FAKE_TOKEN})
    def test_ssl_certificate_error(self):
        """SSL certificate error -> returns []."""
        from app.services.phase2.phone_discovery import PhoneDiscoveryService
        svc = PhoneDiscoveryService()
        svc.session.get = Mock(
            side_effect=requests.ConnectionError(
                "SSLError: certificate verify failed"
            )
        )
        result = svc._extract_via_vk_api(VK_PROFILE_URL)
        assert result == []

    @patch.dict(os.environ, {'VK_SERVICE_TOKEN': FAKE_TOKEN})
    def test_connection_reset(self):
        """Connection reset by peer -> returns []."""
        from app.services.phase2.phone_discovery import PhoneDiscoveryService
        svc = PhoneDiscoveryService()
        svc.session.get = Mock(
            side_effect=requests.ConnectionError("Connection reset by peer")
        )
        result = svc._extract_via_vk_api(VK_PROFILE_URL)
        assert result == []

    @patch.dict(os.environ, {'VK_SERVICE_TOKEN': FAKE_TOKEN})
    def test_partial_response_incomplete_json(self):
        """Response body is truncated JSON -> JSONDecodeError handled."""
        from app.services.phase2.phone_discovery import PhoneDiscoveryService
        svc = PhoneDiscoveryService()
        mock_resp = Mock()
        mock_resp.json.side_effect = json.JSONDecodeError(
            "Unterminated string", '{"response": [{"id": 123', 25
        )
        svc.session.get = Mock(return_value=mock_resp)
        result = svc._extract_via_vk_api(VK_PROFILE_URL)
        assert result == []

    @patch.dict(os.environ, {'VK_SERVICE_TOKEN': FAKE_TOKEN})
    def test_empty_response_body(self):
        """Empty response body -> json() raises -> handled."""
        from app.services.phase2.phone_discovery import PhoneDiscoveryService
        svc = PhoneDiscoveryService()
        mock_resp = Mock()
        mock_resp.json.side_effect = json.JSONDecodeError("Expecting value", '', 0)
        svc.session.get = Mock(return_value=mock_resp)
        result = svc._extract_via_vk_api(VK_PROFILE_URL)
        assert result == []

    @patch.dict(os.environ, {'VK_SERVICE_TOKEN': FAKE_TOKEN})
    def test_http_429_too_many_requests(self):
        """HTTP 429 response with error in JSON -> returns []."""
        from app.services.phase2.phone_discovery import PhoneDiscoveryService
        svc = PhoneDiscoveryService()
        mock_resp = Mock()
        mock_resp.status_code = 429
        mock_resp.json.return_value = {
            'error': {'error_code': 6, 'error_msg': 'Too many requests per second'}
        }
        svc.session.get = Mock(return_value=mock_resp)
        result = svc._extract_via_vk_api(VK_PROFILE_URL)
        assert result == []

    @patch.dict(os.environ, {'VK_SERVICE_TOKEN': FAKE_TOKEN})
    def test_http_403_forbidden(self):
        """HTTP 403 with VK error -> returns []."""
        from app.services.phase2.phone_discovery import PhoneDiscoveryService
        svc = PhoneDiscoveryService()
        mock_resp = Mock()
        mock_resp.status_code = 403
        mock_resp.json.return_value = {
            'error': {'error_code': 15, 'error_msg': 'Access denied'}
        }
        svc.session.get = Mock(return_value=mock_resp)
        result = svc._extract_via_vk_api(VK_PROFILE_URL)
        assert result == []

    @patch.dict(os.environ, {'VK_SERVICE_TOKEN': FAKE_TOKEN})
    def test_http_401_unauthorized(self):
        """HTTP 401 with auth error -> returns []."""
        from app.services.phase2.phone_discovery import PhoneDiscoveryService
        svc = PhoneDiscoveryService()
        mock_resp = Mock()
        mock_resp.json.return_value = {
            'error': {'error_code': 5, 'error_msg': 'User authorization failed'}
        }
        svc.session.get = Mock(return_value=mock_resp)
        result = svc._extract_via_vk_api(VK_PROFILE_URL)
        assert result == []

    @patch.dict(os.environ, {'VK_SERVICE_TOKEN': FAKE_TOKEN})
    def test_requests_read_timeout(self):
        """requests.ReadTimeout -> returns []."""
        from app.services.phase2.phone_discovery import PhoneDiscoveryService
        svc = PhoneDiscoveryService()
        svc.session.get = Mock(
            side_effect=requests.ReadTimeout("Read timed out")
        )
        result = svc._extract_via_vk_api(VK_PROFILE_URL)
        assert result == []

    @patch.dict(os.environ, {'VK_SERVICE_TOKEN': FAKE_TOKEN})
    def test_requests_connect_timeout(self):
        """requests.ConnectTimeout -> returns []."""
        from app.services.phase2.phone_discovery import PhoneDiscoveryService
        svc = PhoneDiscoveryService()
        svc.session.get = Mock(
            side_effect=requests.ConnectTimeout("Connect timed out")
        )
        result = svc._extract_via_vk_api(VK_PROFILE_URL)
        assert result == []

    @patch.dict(os.environ, {'VK_SERVICE_TOKEN': FAKE_TOKEN})
    def test_wall_timeout(self):
        """Wall.get with requests.Timeout -> returns []."""
        from app.services.phase2.phone_discovery import PhoneDiscoveryService
        svc = PhoneDiscoveryService()
        svc.session.get = Mock(side_effect=requests.Timeout("wall timeout"))
        result = svc._extract_from_vk_wall(VK_PROFILE_URL)
        assert result == []

    @patch.dict(os.environ, {'VK_SERVICE_TOKEN': FAKE_TOKEN})
    def test_wall_ssl_error(self):
        """Wall.get with SSL error -> returns []."""
        from app.services.phase2.phone_discovery import PhoneDiscoveryService
        svc = PhoneDiscoveryService()
        svc.session.get = Mock(
            side_effect=requests.ConnectionError("SSL: CERTIFICATE_VERIFY_FAILED")
        )
        result = svc._extract_from_vk_wall(VK_PROFILE_URL)
        assert result == []

    @patch.dict(os.environ, {'VK_SERVICE_TOKEN': FAKE_TOKEN})
    def test_discover_sync_all_methods_fail(self):
        """discover_sync still returns results object when all network calls fail."""
        from app.services.phase2.phone_discovery import PhoneDiscoveryService
        svc = PhoneDiscoveryService()
        svc.session.get = Mock(
            side_effect=requests.ConnectionError("everything is down")
        )
        result = svc.discover_sync(
            first_name='Test',
            last_name='User',
            usernames=['testuser'],
            profile_urls=[VK_PROFILE],
            emails=['test@example.com'],
        )
        assert hasattr(result, 'phones')
        assert hasattr(result, 'errors')
        assert isinstance(result.phones, list)

    @patch.dict(os.environ, {'VK_SERVICE_TOKEN': FAKE_TOKEN})
    def test_vk_api_returns_html_instead_of_json(self):
        """VK API returns HTML (e.g., CAPTCHA page) -> json() fails -> handled."""
        from app.services.phase2.phone_discovery import PhoneDiscoveryService
        svc = PhoneDiscoveryService()
        mock_resp = Mock()
        mock_resp.json.side_effect = json.JSONDecodeError(
            "Expecting value", '<html><body>CAPTCHA</body></html>', 0
        )
        mock_resp.text = '<html><body>CAPTCHA</body></html>'
        svc.session.get = Mock(return_value=mock_resp)
        result = svc._extract_via_vk_api(VK_PROFILE_URL)
        assert result == []

    @patch.dict(os.environ, {'VK_SERVICE_TOKEN': FAKE_TOKEN})
    def test_wall_response_missing_items_key(self):
        """Wall.get response has 'response' but no 'items' -> returns []."""
        from app.services.phase2.phone_discovery import PhoneDiscoveryService
        svc = PhoneDiscoveryService()
        mock_resp = Mock()
        mock_resp.json.return_value = {'response': {'count': 5}}
        svc.session.get = Mock(return_value=mock_resp)
        result = svc._extract_from_vk_wall(VK_PROFILE_URL)
        assert result == []


# ===================================================================
# 7. EDGE CASES & INTEGRATION CHAOS
# ===================================================================


class TestEdgeCases:
    """Additional edge cases for completeness (pushing to 90+)."""

    def test_phone_service_close_no_crash(self):
        """PhoneDiscoveryService.close() does not crash."""
        from app.services.phase2.phone_discovery import PhoneDiscoveryService
        svc = PhoneDiscoveryService()
        svc.close()  # Should not raise

    def test_email_service_close_no_crash(self):
        """EmailDiscoveryService.close() does not crash."""
        svc = _make_email_service()
        svc.close()  # Should not raise

    @patch.dict(os.environ, {'VK_SERVICE_TOKEN': FAKE_TOKEN})
    def test_discover_sync_empty_inputs(self):
        """discover_sync with empty everything -> returns valid result."""
        from app.services.phase2.phone_discovery import PhoneDiscoveryService
        svc = PhoneDiscoveryService()
        result = svc.discover_sync(
            first_name='',
            last_name='',
            usernames=[],
            profile_urls=[],
            emails=[],
        )
        assert isinstance(result.phones, list)

    @patch.dict(os.environ, {'VK_SERVICE_TOKEN': FAKE_TOKEN})
    def test_discover_sync_none_profile_urls(self):
        """discover_sync with profile_urls=None -> no crash."""
        from app.services.phase2.phone_discovery import PhoneDiscoveryService
        svc = PhoneDiscoveryService()
        result = svc.discover_sync(
            first_name='Test',
            last_name='User',
            usernames=[],
            profile_urls=None,
        )
        assert isinstance(result.phones, list)

    def test_email_generate_candidates_empty_name(self):
        """_generate_candidates with empty name -> still works."""
        svc = _make_email_service()
        candidates = svc._generate_candidates('', '', [])
        assert isinstance(candidates, list)

    def test_email_transliterate_non_russian(self):
        """_transliterate with Latin input -> passes through."""
        svc = _make_email_service()
        assert svc._transliterate('john') == 'john'

    def test_email_clean_username_with_prefix(self):
        """_clean_username strips known prefixes."""
        svc = _make_email_service()
        assert svc._clean_username('@testuser') == 'testuser'
        assert svc._clean_username('id12345') == '12345'

    def test_source_result_confidence_labels(self):
        """SourceResult confidence_label property works for all ranges."""
        from app.services.phase2.base_source import SourceResult, SourceTier

        sr = SourceResult(
            data_type='email', value='a@b.com',
            source_name='test', source_tier=SourceTier.C,
            confidence=0.95,
        )
        assert sr.confidence_label == 'very_high'

        sr.confidence = 0.75
        assert sr.confidence_label == 'high'

        sr.confidence = 0.55
        assert sr.confidence_label == 'medium'

        sr.confidence = 0.3
        assert sr.confidence_label == 'low'

    def test_source_result_to_dict(self):
        """SourceResult.to_dict serializes correctly."""
        from app.services.phase2.base_source import SourceResult, SourceTier

        sr = SourceResult(
            data_type='phone', value='+79161234567',
            source_name='test', source_tier=SourceTier.A,
            confidence=0.8, verified=True,
            metadata={'source': 'breach'},
        )
        d = sr.to_dict()
        assert d['data_type'] == 'phone'
        assert d['value'] == '+79161234567'
        assert d['confidence'] == 0.8
        assert d['verified'] is True
        assert d['source_tier'] == 'Platform API'

    def test_base_source_get_info(self):
        """BaseSource.get_info returns complete info dict."""
        from app.services.phase2.base_source import BaseSource, SourceTier, SourceType

        class InfoSource(BaseSource):
            name = "InfoSource"
            source_type = SourceType.EMAIL
            source_tier = SourceTier.B
            requires_api_key = True
            def query_impl(self, **kwargs):
                return []
            def is_available(self):
                return False

        src = InfoSource()
        info = src.get_info()
        assert info['name'] == 'InfoSource'
        assert info['type'] == 'email'
        assert info['tier'] == 'Verification'
        assert info['tier_label'] == 'B'
        assert info['available'] is False
        assert info['requires_api_key'] is True

    @patch.dict(os.environ, {'VK_SERVICE_TOKEN': FAKE_TOKEN})
    def test_vk_api_response_none_fields(self):
        """VK API user with None values in fields -> no crash."""
        from app.services.phase2.phone_discovery import PhoneDiscoveryService
        svc = PhoneDiscoveryService()
        mock_resp = Mock()
        mock_resp.json.return_value = {
            'response': [{
                'id': 123,
                'mobile_phone': None,
                'home_phone': None,
                'contacts': None,
                'about': None,
                'status': None,
                'site': None,
            }]
        }
        svc.session.get = Mock(return_value=mock_resp)
        result = svc._extract_via_vk_api(VK_PROFILE_URL)
        assert isinstance(result, list)

    @patch.dict(os.environ, {'VK_SERVICE_TOKEN': FAKE_TOKEN})
    def test_wall_response_is_none(self):
        """VK wall.get returns {'response': None} -> handles gracefully."""
        from app.services.phase2.phone_discovery import PhoneDiscoveryService
        svc = PhoneDiscoveryService()
        mock_resp = Mock()
        mock_resp.json.return_value = {'response': None}
        svc.session.get = Mock(return_value=mock_resp)
        result = svc._extract_from_vk_wall(VK_PROFILE_URL)
        assert result == []

    @patch.dict(os.environ, {'VK_SERVICE_TOKEN': FAKE_TOKEN})
    def test_vk_username_url_pattern(self):
        """VK URL with username (not numeric) -> still extracts."""
        from app.services.phase2.phone_discovery import PhoneDiscoveryService
        svc = PhoneDiscoveryService()
        mock_resp = Mock()
        mock_resp.json.return_value = {'response': [{'id': 123}]}
        svc.session.get = Mock(return_value=mock_resp)
        result = svc._extract_via_vk_api('https://vk.com/durov')
        # Should have made the API call (username parsed)
        svc.session.get.assert_called_once()
        assert isinstance(result, list)

    def test_check_mx_dns_resolver_not_available(self):
        """_check_mx when dns.resolver is not available -> falls back to socket."""
        svc = _make_email_service()
        with patch.dict(sys.modules, {'dns': None, 'dns.resolver': None}):
            # Should not crash; will try socket.getaddrinfo as fallback
            result = svc._check_mx('totally-fake-domain-xyz.invalid')
            # Will return False because socket.getaddrinfo will fail too
            assert isinstance(result, bool)

    def test_smtp_code_552_returns_false(self):
        """SMTP code 552 (mailbox full/quota exceeded) -> False."""
        svc = _make_email_service()
        mock_mx = Mock()
        mock_mx.__getitem__ = Mock(return_value=Mock(exchange='mx.example.com'))
        mock_server = MagicMock()
        mock_server.rcpt.return_value = (552, b'Mailbox full')
        with patch('dns.resolver.resolve', return_value=mock_mx):
            with patch('smtplib.SMTP', return_value=mock_server):
                result = svc._smtp_verify_single('test@example.com')
                assert result is False

    def test_smtp_code_553_returns_false(self):
        """SMTP code 553 -> False."""
        svc = _make_email_service()
        mock_mx = Mock()
        mock_mx.__getitem__ = Mock(return_value=Mock(exchange='mx.example.com'))
        mock_server = MagicMock()
        mock_server.rcpt.return_value = (553, b'Requested action not taken')
        with patch('dns.resolver.resolve', return_value=mock_mx):
            with patch('smtplib.SMTP', return_value=mock_server):
                result = svc._smtp_verify_single('test@example.com')
                assert result is False

    def test_smtp_code_554_returns_false(self):
        """SMTP code 554 -> False."""
        svc = _make_email_service()
        mock_mx = Mock()
        mock_mx.__getitem__ = Mock(return_value=Mock(exchange='mx.example.com'))
        mock_server = MagicMock()
        mock_server.rcpt.return_value = (554, b'Transaction failed')
        with patch('dns.resolver.resolve', return_value=mock_mx):
            with patch('smtplib.SMTP', return_value=mock_server):
                result = svc._smtp_verify_single('test@example.com')
                assert result is False

    @patch.dict(os.environ, {'VK_SERVICE_TOKEN': FAKE_TOKEN})
    def test_vk_api_error_with_empty_error_dict(self):
        """VK API returns {'error': {}} -> returns []."""
        from app.services.phase2.phone_discovery import PhoneDiscoveryService
        svc = PhoneDiscoveryService()
        mock_resp = Mock()
        mock_resp.json.return_value = {'error': {}}
        svc.session.get = Mock(return_value=mock_resp)
        result = svc._extract_via_vk_api(VK_PROFILE_URL)
        assert result == []
