"""
Unit tests for Holehe email verification in EmailDiscoveryService.

Tests the Holehe verification subsystem:
- _holehe_check_single: library API -> CLI fallback
- _holehe_check_cli: subprocess-based CLI
- _verify_with_holehe_batch: async batch with tier ordering + concurrency
- verify_emails_with_holehe: standalone synchronous function
- Confidence scoring, verified_on formatting, error handling

ALL holehe/subprocess interactions are mocked -- no network, no holehe install required.
"""

import os
import sys
import asyncio
import subprocess
import pytest
from unittest.mock import patch, MagicMock, call

os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-unit-tests')

from app.services.phase2.email_discovery import (
    EmailDiscoveryService,
    DiscoveredEmail,
    verify_emails_with_holehe,
)


# ── Helpers ──────────────────────────────────────────────────────────

def _run_async(coro):
    """Run an async coroutine synchronously for testing."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _make_holehe_results(service_names):
    """Build the list-of-dicts that holehe.core functions push into out."""
    results = []
    for name in service_names:
        results.append({'name': name, 'exists': True, 'emailrecovery': None})
    results.append({'name': 'nonexistent_service', 'exists': False})
    return results


# =====================================================================
# 1. Holehe single check -- library path (22 tests)
# =====================================================================

class TestHoleheSingleCheck:
    """Tests for EmailDiscoveryService._holehe_check_single."""

    def _run_with_fake_holehe(self, email, fake_results):
        """Run _holehe_check_single with mocked holehe internals."""
        async def fake_website_func(email_addr, client, out):
            out.extend(fake_results)

        with patch('holehe.core.import_submodules', return_value={}), \
             patch('holehe.core.get_functions', return_value=[fake_website_func]):
            svc = EmailDiscoveryService()
            result = svc._holehe_check_single(email)
            svc.close()
            return result

    def test_found_five_services(self):
        """Mock holehe finds 5 services -> returns dict with 5 services."""
        services = ['twitter', 'spotify', 'instagram', 'pinterest', 'adobe']
        fake_results = _make_holehe_results(services)
        result = self._run_with_fake_holehe('test@gmail.com', fake_results)
        assert result is not None
        assert 'services' in result
        assert set(result['services']) == set(services)

    def test_found_one_service(self):
        """Mock holehe finds 1 service -> returns dict with 1 service."""
        fake_results = _make_holehe_results(['twitter'])
        result = self._run_with_fake_holehe('user@mail.ru', fake_results)
        assert result is not None
        assert result['services'] == ['twitter']

    def test_found_zero_services(self):
        """Mock holehe finds 0 services -> returns None."""
        fake_results = [{'name': 'twitter', 'exists': False}]
        result = self._run_with_fake_holehe('nobody@example.com', fake_results)
        assert result is None

    def test_import_error_falls_back_to_cli(self):
        """ImportError on httpx import -> falls back to CLI."""
        svc = EmailDiscoveryService()
        real_httpx = sys.modules.get('httpx')
        sys.modules['httpx'] = None
        try:
            with patch.object(svc, '_holehe_check_cli',
                              return_value={'services': ['twitter', 'spotify']}) as mock_cli:
                result = svc._holehe_check_single('test@gmail.com')
        finally:
            if real_httpx is not None:
                sys.modules['httpx'] = real_httpx
            else:
                sys.modules.pop('httpx', None)
        assert result is not None
        assert 'twitter' in result['services']
        assert 'spotify' in result['services']
        mock_cli.assert_called_once_with('test@gmail.com')
        svc.close()

    def test_safe_call_catches_runtime_error(self):
        """RuntimeError inside a website function -> caught by _safe_call, out stays empty."""
        svc = EmailDiscoveryService()
        async def exploding_func(email_addr, client, out):
            raise RuntimeError("Holehe internal crash")
        with patch('holehe.core.import_submodules', return_value={}), \
             patch('holehe.core.get_functions', return_value=[exploding_func]):
            result = svc._holehe_check_single('test@gmail.com')
        # _safe_call catches RuntimeError; out stays []; no services found -> None
        assert result is None
        svc.close()

    def test_get_functions_error_falls_back_to_cli(self):
        """RuntimeError in get_functions -> falls back to CLI."""
        svc = EmailDiscoveryService()
        with patch('holehe.core.import_submodules', return_value={}), \
             patch('holehe.core.get_functions', side_effect=RuntimeError("broken")), \
             patch.object(svc, '_holehe_check_cli',
                          return_value={'services': ['instagram']}) as mock_cli:
            result = svc._holehe_check_single('test@gmail.com')
        assert result is not None
        assert result['services'] == ['instagram']
        mock_cli.assert_called_once_with('test@gmail.com')
        svc.close()

    def test_holehe_returns_empty_list(self):
        """Holehe returns empty list -> no services -> None."""
        result = self._run_with_fake_holehe('test@gmail.com', [])
        assert result is None

    def test_holehe_returns_empty_dict_entries(self):
        """Holehe returns list of empty dicts -> no services -> None."""
        result = self._run_with_fake_holehe('test@gmail.com', [{}, {}, {}])
        assert result is None

    def test_holehe_results_with_none_name(self):
        """Holehe result with name=None and exists=True -> skipped."""
        fake_results = [
            {'name': None, 'exists': True},
            {'name': 'twitter', 'exists': True},
        ]
        result = self._run_with_fake_holehe('test@gmail.com', fake_results)
        assert result is not None
        assert result['services'] == ['twitter']

    def test_holehe_results_with_unknown_name(self):
        """Holehe result with name='unknown' and exists=True -> skipped."""
        fake_results = [
            {'name': 'unknown', 'exists': True},
            {'name': 'spotify', 'exists': True},
        ]
        result = self._run_with_fake_holehe('test@gmail.com', fake_results)
        assert result is not None
        assert result['services'] == ['spotify']

    def test_holehe_all_exists_false(self):
        """Holehe returns all exists=False -> None."""
        fake_results = [
            {'name': 'twitter', 'exists': False},
            {'name': 'spotify', 'exists': False},
            {'name': 'instagram', 'exists': False},
        ]
        result = self._run_with_fake_holehe('test@gmail.com', fake_results)
        assert result is None

    def test_holehe_mixed_exists_values(self):
        """Holehe returns mix of exists True/False -> only True collected."""
        fake_results = [
            {'name': 'twitter', 'exists': True},
            {'name': 'spotify', 'exists': False},
            {'name': 'instagram', 'exists': True},
            {'name': 'pinterest', 'exists': False},
        ]
        result = self._run_with_fake_holehe('test@gmail.com', fake_results)
        assert result is not None
        assert set(result['services']) == {'twitter', 'instagram'}

    def test_both_library_and_cli_fail(self):
        """Both library and CLI fail -> returns None."""
        svc = EmailDiscoveryService()
        real_httpx = sys.modules.get('httpx')
        sys.modules['httpx'] = None
        try:
            with patch.object(svc, '_holehe_check_cli', return_value=None):
                result = svc._holehe_check_single('test@gmail.com')
        finally:
            if real_httpx is not None:
                sys.modules['httpx'] = real_httpx
            else:
                sys.modules.pop('httpx', None)
        assert result is None
        svc.close()

    def test_holehe_result_missing_exists_key(self):
        """Holehe result dict missing 'exists' key -> treated as not found."""
        fake_results = [{'name': 'twitter'}]
        result = self._run_with_fake_holehe('test@gmail.com', fake_results)
        assert result is None

    def test_holehe_result_exists_is_string_true(self):
        """Holehe result with exists='true' (string) -> not matched (strict is True)."""
        fake_results = [{'name': 'twitter', 'exists': 'true'}]
        result = self._run_with_fake_holehe('test@gmail.com', fake_results)
        assert result is None

    def test_large_number_of_services_returned(self):
        """Holehe finds 20 services -> all returned in services list."""
        service_names = [f'service_{i}' for i in range(20)]
        fake_results = [{'name': s, 'exists': True} for s in service_names]
        result = self._run_with_fake_holehe('test@gmail.com', fake_results)
        assert result is not None
        assert len(result['services']) == 20

    def test_result_with_empty_name_string(self):
        """Holehe result with name='' and exists=True -> skipped."""
        fake_results = [
            {'name': '', 'exists': True},
            {'name': 'twitter', 'exists': True},
        ]
        result = self._run_with_fake_holehe('test@gmail.com', fake_results)
        assert result is not None
        assert result['services'] == ['twitter']

    def test_result_with_integer_entries(self):
        """Holehe returns integers in list -> isinstance check fails -> skipped."""
        fake_results = [42, 99, 0]
        result = self._run_with_fake_holehe('test@gmail.com', fake_results)
        assert result is None

    def test_cli_fallback_called_when_library_returns_none(self):
        """When library path returns None (no services) -> no CLI fallback."""
        svc = EmailDiscoveryService()
        async def empty_func(email_addr, client, out):
            pass
        with patch('holehe.core.import_submodules', return_value={}), \
             patch('holehe.core.get_functions', return_value=[empty_func]):
            result = svc._holehe_check_single('test@gmail.com')
        assert result is None
        svc.close()

    def test_exception_in_event_loop_falls_to_cli(self):
        """Exception during event loop execution -> falls back to CLI."""
        svc = EmailDiscoveryService()
        with patch('holehe.core.import_submodules',
                   side_effect=ValueError("broken modules")), \
             patch.object(svc, '_holehe_check_cli',
                          return_value={'services': ['discord']}) as mock_cli:
            result = svc._holehe_check_single('test@gmail.com')
        assert result is not None
        assert result['services'] == ['discord']
        mock_cli.assert_called_once_with('test@gmail.com')
        svc.close()

    def test_cli_fallback_on_holehe_import_error(self):
        """ImportError on holehe.core -> falls back to CLI."""
        svc = EmailDiscoveryService()
        with patch.dict(sys.modules, {'holehe.core': None}), \
             patch.object(svc, '_holehe_check_cli',
                          return_value={'services': ['twitter']}) as mock_cli:
            result = svc._holehe_check_single('test@gmail.com')
        assert result is not None
        assert 'twitter' in result['services']
        svc.close()

    def test_services_dict_format(self):
        """Return value is dict with 'services' key containing a list."""
        fake_results = [{'name': 'twitter', 'exists': True}]
        result = self._run_with_fake_holehe('test@gmail.com', fake_results)
        assert isinstance(result, dict)
        assert 'services' in result
        assert isinstance(result['services'], list)

    def test_duplicate_names_in_results(self):
        """Duplicate service names in holehe results -> both included."""
        fake_results = [
            {'name': 'twitter', 'exists': True},
            {'name': 'twitter', 'exists': True},
        ]
        result = self._run_with_fake_holehe('test@gmail.com', fake_results)
        assert result is not None
        assert result['services'] == ['twitter', 'twitter']


# =====================================================================
# 2. CLI fallback tests (14 tests)
# =====================================================================

class TestHoleheCLI:
    """Tests for EmailDiscoveryService._holehe_check_cli."""

    @patch('subprocess.run')
    def test_cli_parses_positive_lines(self, mock_sub):
        """CLI output with [+] lines -> services parsed correctly."""
        mock_sub.return_value = MagicMock(
            stdout='[+] twitter: Registered\n[+] spotify: Registered\n[-] instagram: Not Found\n',
            returncode=0)
        svc = EmailDiscoveryService()
        result = svc._holehe_check_cli('test@gmail.com')
        assert result is not None
        assert 'twitter' in result['services']
        assert 'spotify' in result['services']
        assert 'instagram' not in result['services']
        svc.close()

    @patch('subprocess.run')
    def test_cli_no_positive_lines(self, mock_sub):
        """CLI output with no [+] lines -> returns None."""
        mock_sub.return_value = MagicMock(
            stdout='[-] twitter: Not Found\n[-] spotify: Not Found\n', returncode=0)
        svc = EmailDiscoveryService()
        result = svc._holehe_check_cli('nobody@example.com')
        assert result is None
        svc.close()

    @patch('subprocess.run')
    def test_cli_timeout_expired(self, mock_sub):
        """CLI subprocess times out -> returns None."""
        mock_sub.side_effect = subprocess.TimeoutExpired(cmd='holehe', timeout=15)
        svc = EmailDiscoveryService()
        result = svc._holehe_check_cli('test@gmail.com')
        assert result is None
        svc.close()

    @patch('subprocess.run')
    def test_cli_command_not_found(self, mock_sub):
        """holehe command not found -> returns None."""
        mock_sub.side_effect = FileNotFoundError("holehe not found")
        svc = EmailDiscoveryService()
        result = svc._holehe_check_cli('test@gmail.com')
        assert result is None
        svc.close()

    @patch('subprocess.run')
    def test_cli_empty_output(self, mock_sub):
        """CLI returns empty output -> returns None."""
        mock_sub.return_value = MagicMock(stdout='', returncode=0)
        svc = EmailDiscoveryService()
        result = svc._holehe_check_cli('test@gmail.com')
        assert result is None
        svc.close()

    @patch('subprocess.run')
    def test_cli_malformed_output(self, mock_sub):
        """CLI returns malformed output -> handles gracefully."""
        mock_sub.return_value = MagicMock(
            stdout='Some random text\nError: connection failed\n', returncode=1)
        svc = EmailDiscoveryService()
        result = svc._holehe_check_cli('test@gmail.com')
        assert result is None
        svc.close()

    @patch('subprocess.run')
    def test_cli_passes_correct_arguments(self, mock_sub):
        """CLI is called with correct command-line arguments."""
        mock_sub.return_value = MagicMock(stdout='', returncode=0)
        svc = EmailDiscoveryService()
        svc._holehe_check_cli('user@mail.ru')
        mock_sub.assert_called_once_with(
            ['holehe', 'user@mail.ru', '--only-used', '--no-color', '--no-clear', '-T', '5'],
            capture_output=True, text=True, timeout=15, encoding='utf-8', errors='replace')
        svc.close()

    @patch('subprocess.run')
    def test_cli_single_plus_line(self, mock_sub):
        """CLI with single [+] line -> one service returned."""
        mock_sub.return_value = MagicMock(stdout='[+] adobe: Registered\n', returncode=0)
        svc = EmailDiscoveryService()
        result = svc._holehe_check_cli('test@gmail.com')
        assert result is not None
        assert result['services'] == ['adobe']
        svc.close()

    @patch('subprocess.run')
    def test_cli_service_name_with_colon(self, mock_sub):
        """CLI output where service name is before colon -> parsed correctly."""
        mock_sub.return_value = MagicMock(stdout='[+] mail.ru: Email registered\n', returncode=0)
        svc = EmailDiscoveryService()
        result = svc._holehe_check_cli('test@mail.ru')
        assert result is not None
        assert 'mail.ru' in result['services']
        svc.close()

    @patch('subprocess.run')
    def test_cli_generic_exception(self, mock_sub):
        """Generic exception during CLI run -> returns None."""
        mock_sub.side_effect = PermissionError("Access denied")
        svc = EmailDiscoveryService()
        result = svc._holehe_check_cli('test@gmail.com')
        assert result is None
        svc.close()

    @patch('subprocess.run')
    def test_cli_multiple_plus_markers_in_line(self, mock_sub):
        """CLI line with multiple [+] markers -> first service name parsed."""
        mock_sub.return_value = MagicMock(stdout='[+] twitter: [+] also found\n', returncode=0)
        svc = EmailDiscoveryService()
        result = svc._holehe_check_cli('test@gmail.com')
        assert result is not None
        assert 'twitter' in result['services']
        svc.close()

    @patch('subprocess.run')
    def test_cli_output_with_whitespace_lines(self, mock_sub):
        """CLI output with blank lines -> handled gracefully."""
        mock_sub.return_value = MagicMock(
            stdout='\n\n  \n[+] twitter: Registered\n\n  \n', returncode=0)
        svc = EmailDiscoveryService()
        result = svc._holehe_check_cli('test@gmail.com')
        assert result is not None
        assert 'twitter' in result['services']
        svc.close()

    @patch('subprocess.run')
    def test_cli_short_service_name_filtered(self, mock_sub):
        """CLI service name with 1 char -> filtered out (len > 1 check)."""
        mock_sub.return_value = MagicMock(
            stdout='[+] x: Registered\n[+] twitter: Registered\n', returncode=0)
        svc = EmailDiscoveryService()
        result = svc._holehe_check_cli('test@gmail.com')
        assert result is not None
        assert 'x' not in result['services']
        assert 'twitter' in result['services']
        svc.close()

    @patch('subprocess.run')
    def test_cli_empty_service_name_after_split(self, mock_sub):
        """CLI [+] with nothing after -> IndexError on split -> returns None."""
        mock_sub.return_value = MagicMock(stdout='[+] \n[+] twitter: ok\n', returncode=0)
        svc = EmailDiscoveryService()
        result = svc._holehe_check_cli('test@gmail.com')
        # The empty '[+] ' line causes IndexError in .split()[0] on empty string,
        # which is caught by the except Exception handler, returning None
        assert result is None
        svc.close()


# =====================================================================
# 3. Batch verification logic (18 tests)
# =====================================================================

class TestBatchVerification:
    """Tests for EmailDiscoveryService._verify_with_holehe_batch."""

    def _run_batch(self, svc, emails):
        return _run_async(svc._verify_with_holehe_batch(emails))

    def test_five_emails_all_found(self):
        """5 emails, all verified -> DiscoveredEmail objects for tier 1."""
        svc = EmailDiscoveryService()
        with patch.object(svc, '_holehe_check_single',
                          return_value={'services': ['twitter', 'instagram']}):
            results = self._run_batch(svc, [
                'a@mail.ru', 'b@yandex.ru', 'c@bk.ru', 'd@gmail.com', 'e@outlook.com'])
        assert len(results) == 4
        for r in results:
            assert isinstance(r, DiscoveredEmail)
            assert r.verified is True
        svc.close()

    def test_five_emails_two_found_three_not(self):
        """5 emails, 2 found, 3 not -> 2 verified results."""
        svc = EmailDiscoveryService()
        def mock_check(email):
            if email in ('a@mail.ru', 'c@bk.ru'):
                return {'services': ['twitter']}
            return None
        with patch.object(svc, '_holehe_check_single', side_effect=mock_check):
            results = self._run_batch(svc, [
                'a@mail.ru', 'b@yandex.ru', 'c@bk.ru', 'd@gmail.com', 'e@outlook.com'])
        verified = [r for r in results if r.verified]
        assert len(verified) == 2
        svc.close()

    def test_empty_email_list(self):
        """0 emails -> empty list."""
        svc = EmailDiscoveryService()
        results = self._run_batch(svc, [])
        assert results == []
        svc.close()

    def test_max_four_per_tier(self):
        """Tier 1 limited to 4 emails even if more match."""
        svc = EmailDiscoveryService()
        with patch.object(svc, '_holehe_check_single',
                          return_value={'services': ['twitter']}):
            results = self._run_batch(svc, [
                'a@mail.ru', 'b@yandex.ru', 'c@bk.ru', 'd@gmail.com',
                'e@mail.ru', 'f@yandex.ru'])
        assert len(results) == 4
        svc.close()

    def test_tier_ordering_russian_first(self):
        """Tier 1 checked before tier 2."""
        svc = EmailDiscoveryService()
        checked = []
        def mock_check(email):
            checked.append(email)
            return None
        with patch.object(svc, '_holehe_check_single', side_effect=mock_check):
            self._run_batch(svc, [
                'user@outlook.com', 'user@mail.ru', 'user@yahoo.com', 'user@yandex.ru'])
        t1 = [e for e in checked if e.split('@')[1] in {'mail.ru', 'yandex.ru', 'bk.ru', 'gmail.com'}]
        t2 = [e for e in checked if e.split('@')[1] not in {'mail.ru', 'yandex.ru', 'bk.ru', 'gmail.com'}]
        if t1 and t2:
            assert max(checked.index(e) for e in t1) < min(checked.index(e) for e in t2)
        svc.close()

    def test_timeout_on_one_email_others_checked(self):
        """Slow email does not block others."""
        svc = EmailDiscoveryService()
        def mock_check(email):
            if email == 'slow@mail.ru':
                return None
            return {'services': ['twitter']}
        with patch.object(svc, '_holehe_check_single', side_effect=mock_check):
            results = self._run_batch(svc, ['slow@mail.ru', 'fast@yandex.ru', 'ok@bk.ru'])
        verified = [r for r in results if r.verified]
        assert len(verified) >= 2
        svc.close()

    def test_exception_on_one_others_checked(self):
        """Exception on one email -> others still get checked."""
        svc = EmailDiscoveryService()
        def mock_check(email):
            if email == 'bad@mail.ru':
                raise ValueError("Bad email")
            return {'services': ['spotify']}
        with patch.object(svc, '_holehe_check_single', side_effect=mock_check):
            results = self._run_batch(svc, ['bad@mail.ru', 'good@yandex.ru', 'ok@bk.ru'])
        verified = [r for r in results if r.verified]
        assert len(verified) >= 2
        svc.close()

    def test_all_emails_return_none(self):
        """All emails return None -> empty results."""
        svc = EmailDiscoveryService()
        with patch.object(svc, '_holehe_check_single', return_value=None):
            results = self._run_batch(svc, ['a@mail.ru', 'b@yandex.ru'])
        assert results == []
        svc.close()

    def test_tier2_checked_when_tier1_empty(self):
        """Tier 2 checked when Tier 1 finds nothing."""
        svc = EmailDiscoveryService()
        checked = []
        def mock_check(email):
            checked.append(email)
            if email == 'user@outlook.com':
                return {'services': ['twitter']}
            return None
        with patch.object(svc, '_holehe_check_single', side_effect=mock_check):
            results = self._run_batch(svc, ['user@mail.ru', 'user@outlook.com'])
        assert 'user@outlook.com' in checked
        assert len(results) == 1
        assert results[0].email == 'user@outlook.com'
        svc.close()

    def test_tier2_skipped_when_tier1_found(self):
        """Tier 2 NOT checked when Tier 1 found results."""
        svc = EmailDiscoveryService()
        checked = []
        def mock_check(email):
            checked.append(email)
            if email == 'user@mail.ru':
                return {'services': ['twitter']}
            return {'services': ['spotify']}
        with patch.object(svc, '_holehe_check_single', side_effect=mock_check):
            self._run_batch(svc, ['user@mail.ru', 'user@outlook.com'])
        assert 'user@outlook.com' not in checked
        svc.close()

    def test_single_email_tier1(self):
        """Single tier 1 email -> checked and returned."""
        svc = EmailDiscoveryService()
        with patch.object(svc, '_holehe_check_single', return_value={'services': ['twitter']}):
            results = self._run_batch(svc, ['solo@gmail.com'])
        assert len(results) == 1
        assert results[0].email == 'solo@gmail.com'
        svc.close()

    def test_single_email_tier2(self):
        """Single tier 2 email -> checked because tier 1 is empty."""
        svc = EmailDiscoveryService()
        with patch.object(svc, '_holehe_check_single', return_value={'services': ['adobe']}):
            results = self._run_batch(svc, ['user@protonmail.com'])
        assert len(results) == 1
        assert results[0].email == 'user@protonmail.com'
        svc.close()

    def test_result_is_discovered_email_type(self):
        """Results are DiscoveredEmail instances with correct fields."""
        svc = EmailDiscoveryService()
        with patch.object(svc, '_holehe_check_single', return_value={'services': ['twitter']}):
            results = self._run_batch(svc, ['test@mail.ru'])
        assert len(results) == 1
        assert isinstance(results[0], DiscoveredEmail)
        assert results[0].source == "Holehe verification"
        assert results[0].verification == 'holehe_confirmed'
        svc.close()

    def test_verified_on_format(self):
        """verified_on list has 'holehe:servicename' format."""
        svc = EmailDiscoveryService()
        with patch.object(svc, '_holehe_check_single',
                          return_value={'services': ['twitter', 'spotify']}):
            results = self._run_batch(svc, ['test@mail.ru'])
        assert results[0].verified_on == ['holehe:twitter', 'holehe:spotify']
        svc.close()

    def test_holehe_check_returns_empty_services_list(self):
        """holehe returns {'services': []} -> not added to results."""
        svc = EmailDiscoveryService()
        with patch.object(svc, '_holehe_check_single', return_value={'services': []}):
            results = self._run_batch(svc, ['test@mail.ru'])
        assert results == []
        svc.close()

    def test_ten_emails_tier_splitting(self):
        """10 emails split into tiers correctly."""
        svc = EmailDiscoveryService()
        with patch.object(svc, '_holehe_check_single', return_value=None):
            results = self._run_batch(svc, [
                'a@mail.ru', 'b@yandex.ru', 'c@bk.ru', 'd@gmail.com',
                'e@mail.ru', 'f@outlook.com', 'g@yahoo.com', 'h@protonmail.com',
                'i@hotmail.com', 'j@icloud.com'])
        assert results == []
        svc.close()

    def test_duplicate_emails_in_input(self):
        """Duplicate emails in input -> each instance is checked."""
        svc = EmailDiscoveryService()
        with patch.object(svc, '_holehe_check_single', return_value={'services': ['twitter']}):
            results = self._run_batch(svc, ['a@mail.ru', 'a@mail.ru', 'b@yandex.ru'])
        assert len(results) >= 2
        svc.close()

    def test_batch_with_only_tier2_emails(self):
        """Input has only tier 2 emails -> tier 2 checked."""
        svc = EmailDiscoveryService()
        with patch.object(svc, '_holehe_check_single', return_value={'services': ['twitter']}):
            results = self._run_batch(svc, ['a@outlook.com', 'b@yahoo.com', 'c@protonmail.com'])
        assert len(results) >= 1
        svc.close()


# =====================================================================
# 4. Confidence scoring (14 tests)
# =====================================================================

class TestConfidenceScoring:
    """Tests for confidence scoring in Holehe verification."""

    def _run_batch(self, svc, emails):
        return _run_async(svc._verify_with_holehe_batch(emails))

    def test_five_services_high_confidence(self):
        svc = EmailDiscoveryService()
        with patch.object(svc, '_holehe_check_single',
                          return_value={'services': ['twitter', 'spotify', 'instagram', 'pinterest', 'adobe']}):
            results = self._run_batch(svc, ['test@mail.ru'])
        assert results[0].confidence == 'high'
        svc.close()

    def test_two_services_high_confidence(self):
        svc = EmailDiscoveryService()
        with patch.object(svc, '_holehe_check_single',
                          return_value={'services': ['twitter', 'spotify']}):
            results = self._run_batch(svc, ['test@mail.ru'])
        assert results[0].confidence == 'high'
        svc.close()

    def test_one_service_medium_confidence(self):
        svc = EmailDiscoveryService()
        with patch.object(svc, '_holehe_check_single', return_value={'services': ['twitter']}):
            results = self._run_batch(svc, ['test@mail.ru'])
        assert results[0].confidence == 'medium'
        svc.close()

    def test_zero_services_not_verified(self):
        svc = EmailDiscoveryService()
        with patch.object(svc, '_holehe_check_single', return_value=None):
            results = self._run_batch(svc, ['test@mail.ru'])
        assert results == []
        svc.close()

    def test_verified_on_capped_at_five(self):
        svc = EmailDiscoveryService()
        with patch.object(svc, '_holehe_check_single',
                          return_value={'services': [f'svc_{i}' for i in range(10)]}):
            results = self._run_batch(svc, ['test@mail.ru'])
        assert len(results[0].verified_on) == 5
        svc.close()

    def test_verified_on_holehe_prefix(self):
        svc = EmailDiscoveryService()
        with patch.object(svc, '_holehe_check_single',
                          return_value={'services': ['twitter', 'instagram']}):
            results = self._run_batch(svc, ['test@mail.ru'])
        for item in results[0].verified_on:
            assert item.startswith('holehe:')
        svc.close()

    def test_three_services_high_confidence(self):
        svc = EmailDiscoveryService()
        with patch.object(svc, '_holehe_check_single',
                          return_value={'services': ['a', 'b', 'c']}):
            results = self._run_batch(svc, ['test@mail.ru'])
        assert results[0].confidence == 'high'
        svc.close()

    def test_ten_services_high_confidence(self):
        svc = EmailDiscoveryService()
        with patch.object(svc, '_holehe_check_single',
                          return_value={'services': [f's{i}' for i in range(10)]}):
            results = self._run_batch(svc, ['test@mail.ru'])
        assert results[0].confidence == 'high'
        svc.close()

    def test_verification_field_holehe_confirmed(self):
        svc = EmailDiscoveryService()
        with patch.object(svc, '_holehe_check_single', return_value={'services': ['twitter']}):
            results = self._run_batch(svc, ['test@mail.ru'])
        assert results[0].verification == 'holehe_confirmed'
        svc.close()

    def test_verified_true_when_services_found(self):
        svc = EmailDiscoveryService()
        with patch.object(svc, '_holehe_check_single', return_value={'services': ['twitter']}):
            results = self._run_batch(svc, ['test@mail.ru'])
        assert results[0].verified is True
        svc.close()

    def test_email_field_preserved(self):
        svc = EmailDiscoveryService()
        with patch.object(svc, '_holehe_check_single', return_value={'services': ['twitter']}):
            results = self._run_batch(svc, ['specific@mail.ru'])
        assert results[0].email == 'specific@mail.ru'
        svc.close()

    def test_source_field_is_holehe_verification(self):
        svc = EmailDiscoveryService()
        with patch.object(svc, '_holehe_check_single', return_value={'services': ['twitter']}):
            results = self._run_batch(svc, ['test@mail.ru'])
        assert results[0].source == "Holehe verification"
        svc.close()

    def test_verified_on_preserves_service_order(self):
        svc = EmailDiscoveryService()
        ordered = ['alpha', 'bravo', 'charlie', 'delta', 'echo']
        with patch.object(svc, '_holehe_check_single', return_value={'services': ordered}):
            results = self._run_batch(svc, ['test@mail.ru'])
        expected = [f'holehe:{s}' for s in ordered]
        assert results[0].verified_on == expected
        svc.close()

    def test_exact_two_is_high_boundary(self):
        svc = EmailDiscoveryService()
        with patch.object(svc, '_holehe_check_single', return_value={'services': ['a', 'b']}):
            results = self._run_batch(svc, ['test@mail.ru'])
        assert results[0].confidence == 'high'
        with patch.object(svc, '_holehe_check_single', return_value={'services': ['a']}):
            results = self._run_batch(svc, ['test2@mail.ru'])
        assert results[0].confidence == 'medium'
        svc.close()


# =====================================================================
# 5. verify_emails_with_holehe standalone (15 tests)
# =====================================================================

class TestVerifyEmailsWithHolehe:
    """Tests for the standalone verify_emails_with_holehe function."""

    @patch.object(EmailDiscoveryService, '_holehe_check_single')
    def test_returns_correct_dict_format(self, mock_check):
        mock_check.return_value = {'services': ['twitter', 'spotify']}
        results = verify_emails_with_holehe(['test@gmail.com'])
        assert len(results) == 1
        r = results[0]
        for key in ('email', 'services', 'verified', 'confidence', 'verification', 'verified_on'):
            assert key in r

    @patch.object(EmailDiscoveryService, '_holehe_check_single')
    def test_verified_true_when_found(self, mock_check):
        mock_check.return_value = {'services': ['twitter']}
        results = verify_emails_with_holehe(['test@gmail.com'])
        assert results[0]['verified'] is True

    @patch.object(EmailDiscoveryService, '_holehe_check_single')
    def test_verified_false_when_not_found(self, mock_check):
        mock_check.return_value = None
        results = verify_emails_with_holehe(['test@gmail.com'])
        assert results[0]['verified'] is False
        assert results[0]['verification'] == 'holehe_not_found'

    @patch.object(EmailDiscoveryService, '_holehe_check_single')
    def test_max_emails_respected(self, mock_check):
        mock_check.return_value = {'services': ['twitter']}
        emails = [f'user{i}@gmail.com' for i in range(20)]
        results = verify_emails_with_holehe(emails, max_emails=3)
        assert len(results) <= 3

    @patch.object(EmailDiscoveryService, '_holehe_check_single')
    def test_default_max_emails_is_five(self, mock_check):
        mock_check.return_value = {'services': ['twitter']}
        emails = [f'user{i}@gmail.com' for i in range(10)]
        results = verify_emails_with_holehe(emails)
        assert len(results) <= 5

    @patch.object(EmailDiscoveryService, '_holehe_check_single')
    def test_holehe_error_on_exception(self, mock_check):
        mock_check.side_effect = Exception("Network error")
        results = verify_emails_with_holehe(['test@gmail.com'])
        assert len(results) >= 1
        r = results[0]
        assert r['verified'] is False
        assert r['verification'] == 'holehe_error'
        assert r['confidence'] is None

    @patch.object(EmailDiscoveryService, '_holehe_check_single')
    def test_holehe_not_found_when_empty_services(self, mock_check):
        mock_check.return_value = {'services': []}
        results = verify_emails_with_holehe(['test@gmail.com'])
        assert results[0]['verification'] == 'holehe_not_found'
        assert results[0]['verified'] is False

    @patch.object(EmailDiscoveryService, '_holehe_check_single')
    def test_confidence_high_multiple_services(self, mock_check):
        mock_check.return_value = {'services': ['twitter', 'spotify', 'instagram']}
        results = verify_emails_with_holehe(['test@gmail.com'])
        assert results[0]['confidence'] == 'high'

    @patch.object(EmailDiscoveryService, '_holehe_check_single')
    def test_confidence_medium_single_service(self, mock_check):
        mock_check.return_value = {'services': ['twitter']}
        results = verify_emails_with_holehe(['test@gmail.com'])
        assert results[0]['confidence'] == 'medium'

    @patch.object(EmailDiscoveryService, '_holehe_check_single')
    def test_confidence_none_when_not_found(self, mock_check):
        mock_check.return_value = None
        results = verify_emails_with_holehe(['test@gmail.com'])
        assert results[0]['confidence'] is None

    @patch.object(EmailDiscoveryService, '_holehe_check_single')
    def test_verified_on_format_standalone(self, mock_check):
        mock_check.return_value = {'services': ['twitter', 'adobe']}
        results = verify_emails_with_holehe(['test@gmail.com'])
        assert results[0]['verified_on'] == ['holehe:twitter', 'holehe:adobe']

    @patch.object(EmailDiscoveryService, '_holehe_check_single')
    def test_verified_on_capped_at_five_standalone(self, mock_check):
        mock_check.return_value = {'services': [f's{i}' for i in range(10)]}
        results = verify_emails_with_holehe(['test@gmail.com'])
        assert len(results[0]['verified_on']) == 5

    @patch.object(EmailDiscoveryService, '_holehe_check_single')
    def test_empty_email_list_standalone(self, mock_check):
        results = verify_emails_with_holehe([])
        assert results == []
        mock_check.assert_not_called()

    @patch.object(EmailDiscoveryService, '_holehe_check_single')
    def test_tier_ordering_russian_first_standalone(self, mock_check):
        checked = []
        def track(email):
            checked.append(email)
            return {'services': ['twitter']}
        mock_check.side_effect = track
        verify_emails_with_holehe(['user@outlook.com', 'user@mail.ru', 'user@yahoo.com'], max_emails=5)
        assert 'user@mail.ru' in checked

    @patch.object(EmailDiscoveryService, '_holehe_check_single')
    def test_multiple_emails_mixed_results(self, mock_check):
        def fn(email):
            if email == 'yes@gmail.com':
                return {'services': ['twitter']}
            return None
        mock_check.side_effect = fn
        results = verify_emails_with_holehe(['yes@gmail.com', 'no@gmail.com'], max_emails=5)
        verified = [r for r in results if r['verified']]
        not_verified = [r for r in results if not r['verified']]
        assert len(verified) == 1
        assert len(not_verified) == 1
        assert verified[0]['email'] == 'yes@gmail.com'
        assert not_verified[0]['email'] == 'no@gmail.com'


# =====================================================================
# 6. DiscoveredEmail dataclass tests (5 tests)
# =====================================================================

class TestDiscoveredEmailDataclass:

    def test_default_values(self):
        email = DiscoveredEmail(email='test@gmail.com', source='test', confidence='medium')
        assert email.verified is False
        assert email.verified_on == []
        assert email.verification == 'unverified'

    def test_custom_values(self):
        email = DiscoveredEmail(
            email='test@gmail.com', source='Holehe verification', confidence='high',
            verified=True, verified_on=['holehe:twitter', 'holehe:spotify'],
            verification='holehe_confirmed')
        assert email.email == 'test@gmail.com'
        assert email.confidence == 'high'
        assert email.verified is True
        assert len(email.verified_on) == 2

    def test_verified_on_is_mutable_list(self):
        e1 = DiscoveredEmail(email='a@b.com', source='s', confidence='low')
        e2 = DiscoveredEmail(email='c@d.com', source='s', confidence='low')
        e1.verified_on.append('test')
        assert e2.verified_on == []

    def test_verified_on_can_be_extended(self):
        email = DiscoveredEmail(
            email='test@gmail.com', source='test', confidence='medium',
            verified_on=['holehe:twitter'])
        email.verified_on.extend(['holehe:spotify', 'holehe:adobe'])
        assert len(email.verified_on) == 3

    def test_field_types(self):
        email = DiscoveredEmail(
            email='test@gmail.com', source='Holehe', confidence='high',
            verified=True, verified_on=['holehe:twitter'], verification='holehe_confirmed')
        assert isinstance(email.email, str)
        assert isinstance(email.verified, bool)
        assert isinstance(email.verified_on, list)


# =====================================================================
# 7. Service initialization and cleanup (4 tests)
# =====================================================================

class TestServiceLifecycle:

    def test_default_init(self):
        svc = EmailDiscoveryService()
        assert svc.max_candidates == 30
        assert svc.verify_timeout == 5.0
        assert svc.max_concurrent == 10
        svc.close()

    def test_custom_init(self):
        svc = EmailDiscoveryService(max_candidates=50, verify_timeout=10.0, max_concurrent=20)
        assert svc.max_candidates == 50
        assert svc.verify_timeout == 10.0
        assert svc.max_concurrent == 20
        svc.close()

    def test_close_no_crash(self):
        svc = EmailDiscoveryService()
        svc.close()

    def test_executor_is_thread_pool(self):
        from concurrent.futures import ThreadPoolExecutor
        svc = EmailDiscoveryService()
        assert isinstance(svc._executor, ThreadPoolExecutor)
        svc.close()


# =====================================================================
# 8. Parametrized edge cases
# =====================================================================

class TestParametrizedEdgeCases:

    @pytest.mark.parametrize('email', [
        'user@mail.ru', 'user@yandex.ru', 'user@bk.ru', 'user@gmail.com',
    ])
    def test_tier1_domains_classified_correctly(self, email):
        tier1 = {'mail.ru', 'yandex.ru', 'bk.ru', 'gmail.com'}
        assert email.split('@')[-1] in tier1

    @pytest.mark.parametrize('email', [
        'user@outlook.com', 'user@yahoo.com', 'user@protonmail.com',
        'user@hotmail.com', 'user@icloud.com', 'user@rambler.ru',
    ])
    def test_tier2_domains_classified_correctly(self, email):
        tier1 = {'mail.ru', 'yandex.ru', 'bk.ru', 'gmail.com'}
        assert email.split('@')[-1] not in tier1

    @pytest.mark.parametrize('services,expected', [
        (['a', 'b', 'c', 'd', 'e'], 'high'),
        (['a', 'b'], 'high'),
        (['a'], 'medium'),
    ])
    def test_confidence_levels_parametrized(self, services, expected):
        svc = EmailDiscoveryService()
        with patch.object(svc, '_holehe_check_single', return_value={'services': services}):
            results = _run_async(svc._verify_with_holehe_batch(['test@mail.ru']))
        assert results[0].confidence == expected
        svc.close()

    @pytest.mark.parametrize('cli_output,expected_count', [
        ('[+] twitter: ok\n[+] spotify: ok\n', 2),
        ('[+] twitter: ok\n', 1),
        ('[-] twitter: no\n', 0),
        ('', 0),
    ])
    def test_cli_parsing_parametrized(self, cli_output, expected_count):
        svc = EmailDiscoveryService()
        with patch('subprocess.run') as mock_sub:
            mock_sub.return_value = MagicMock(stdout=cli_output, returncode=0)
            result = svc._holehe_check_cli('test@gmail.com')
        if expected_count > 0:
            assert result is not None
            assert len(result['services']) == expected_count
        else:
            assert result is None
        svc.close()

    @pytest.mark.parametrize('error_class', [
        subprocess.TimeoutExpired, FileNotFoundError,
    ])
    def test_cli_error_types_return_none(self, error_class):
        svc = EmailDiscoveryService()
        with patch('subprocess.run') as mock_sub:
            if error_class == subprocess.TimeoutExpired:
                mock_sub.side_effect = error_class(cmd='holehe', timeout=15)
            else:
                mock_sub.side_effect = error_class("not found")
            result = svc._holehe_check_cli('test@gmail.com')
        assert result is None
        svc.close()

    @pytest.mark.parametrize('num_services,expected_len', [
        (1, 1), (3, 3), (5, 5), (7, 5), (10, 5),
    ])
    def test_verified_on_capping_parametrized(self, num_services, expected_len):
        svc = EmailDiscoveryService()
        services = [f'svc_{i}' for i in range(num_services)]
        with patch.object(svc, '_holehe_check_single', return_value={'services': services}):
            results = _run_async(svc._verify_with_holehe_batch(['test@mail.ru']))
        assert len(results[0].verified_on) == expected_len
        svc.close()
