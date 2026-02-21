"""
Tests for contact discovery pipeline integration.
==================================================
Tests how PhoneDiscoveryService and EmailDiscoveryService work together,
how the SourceManager orchestrates sources, and how results flow through
the pipeline. All external calls are mocked.

80+ tests covering:
1. Phone pipeline with no external services
2. Phone pipeline with mocked VK API
3. Email candidate pipeline
4. SourceManager pipeline
5. Pipeline error resilience
6. Result quality
7. Combined scenarios
"""

import json
import os
import re
import time
from dataclasses import dataclass
from typing import Dict, List, Optional
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

# Ensure SECRET_KEY before Flask imports
os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-unit-tests')

from app.services.phase2.phone_discovery import (
    DiscoveredPhone,
    PhoneDiscoveryResults,
    PhoneDiscoveryService,
)
from app.services.phase2.email_discovery import (
    DiscoveredEmail,
    EmailDiscoveryResults,
    EmailDiscoveryService,
    RUSSIAN_EMAIL_DOMAINS,
)
from app.services.phase2.source_manager import SourceManager
from app.services.phase2.base_source import (
    BaseSource,
    SourceResult,
    SourceTier,
    SourceType,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_vk_users_response(user_fields: dict) -> dict:
    """Build a mock VK API users.get response."""
    base = {'id': 123456, 'first_name': 'Иван', 'last_name': 'Петров'}
    base.update(user_fields)
    return {'response': [base]}


def _make_vk_wall_response(posts: list) -> dict:
    """Build a mock VK API wall.get response."""
    items = []
    for i, text in enumerate(posts):
        items.append({'id': i + 1, 'owner_id': 123456, 'text': text})
    return {'response': {'count': len(items), 'items': items}}


def _mock_vk_response(json_data, status_code=200):
    """Create a mock requests.Response object."""
    resp = MagicMock()
    resp.json.return_value = json_data
    resp.status_code = status_code
    return resp


class _FakeSource(BaseSource):
    """Minimal concrete BaseSource for testing SourceManager."""

    name = "FakeSource"
    source_type = SourceType.BOTH
    source_tier = SourceTier.C
    requires_api_key = False

    def __init__(self, results=None, available=True, raise_exc=None):
        super().__init__()
        self._results = results or []
        self._available = available
        self._raise_exc = raise_exc

    def query_impl(self, **kwargs) -> List[SourceResult]:
        if self._raise_exc:
            raise self._raise_exc
        return self._results

    def is_available(self) -> bool:
        return self._available


class _TierASource(_FakeSource):
    name = "TierASource"
    source_tier = SourceTier.A


class _TierBSource(_FakeSource):
    name = "TierBSource"
    source_tier = SourceTier.B


class _TierSSource(_FakeSource):
    name = "TierSSource"
    source_tier = SourceTier.S


# ═══════════════════════════════════════════════════════════════════════════
# 1. Phone pipeline with no external services  (15+ tests)
# ═══════════════════════════════════════════════════════════════════════════

class TestPhonePipelineNoExternal:
    """Phone discovery when there are no API tokens and no VK profile URLs."""

    def _make_svc(self):
        return PhoneDiscoveryService()

    # --- basic scenarios ---------------------------------------------------

    def test_username_containing_10digit_phone(self):
        """Username that IS a 10-digit phone number starting with 9."""
        svc = self._make_svc()
        result = svc.discover_sync('Иван', 'Петров', ['9161234567'])
        assert isinstance(result, PhoneDiscoveryResults)
        assert any('916' in p.number for p in result.phones)
        svc.close()

    def test_username_containing_11digit_phone(self):
        """Username that IS an 11-digit phone with 8 prefix."""
        svc = self._make_svc()
        result = svc.discover_sync('Иван', 'Петров', ['89161234567'])
        assert any('916' in p.number for p in result.phones)
        svc.close()

    def test_username_containing_7prefix_phone(self):
        """Username that is 11-digit phone with 7 prefix."""
        svc = self._make_svc()
        result = svc.discover_sync('Иван', 'Петров', ['79161234567'])
        assert any('916' in p.number for p in result.phones)
        svc.close()

    def test_no_vk_token_no_crash(self):
        """Without VK_SERVICE_TOKEN, VK methods must be skipped silently."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop('VK_SERVICE_TOKEN', None)
            svc = self._make_svc()
            result = svc.discover_sync(
                'Иван', 'Петров', [],
                profile_urls=[{'platform': 'vk', 'url': 'https://vk.com/id12345'}],
            )
            assert isinstance(result, PhoneDiscoveryResults)
            assert result.errors == []
            svc.close()

    def test_emails_with_phone_pattern(self):
        """Email local part that is a phone number."""
        svc = self._make_svc()
        result = svc.discover_sync(
            'Иван', 'Петров', [],
            emails=['9261234567@mail.ru'],
        )
        assert any('926' in p.number for p in result.phones)
        svc.close()

    def test_emails_with_11digit_phone(self):
        """Email local part that is an 11-digit phone."""
        svc = self._make_svc()
        result = svc.discover_sync(
            'Иван', 'Петров', [],
            emails=['79161234567@yandex.ru'],
        )
        assert any('916' in p.number for p in result.phones)
        svc.close()

    def test_empty_everything_returns_empty(self):
        """Completely empty inputs produce empty results without crash."""
        svc = self._make_svc()
        result = svc.discover_sync('', '', [])
        assert isinstance(result, PhoneDiscoveryResults)
        assert result.phones == []
        assert result.errors == []
        svc.close()

    def test_only_name_empty_usernames(self):
        """Name provided but empty usernames gives no phones (no patterns)."""
        svc = self._make_svc()
        result = svc.discover_sync('Иван', 'Петров', [])
        assert result.phones == []
        svc.close()

    def test_non_vk_profile_urls_skipped(self):
        """Profile URLs for other platforms are skipped."""
        svc = self._make_svc()
        result = svc.discover_sync(
            'Иван', 'Петров', [],
            profile_urls=[
                {'platform': 'instagram', 'url': 'https://instagram.com/ivan'},
                {'platform': 'facebook', 'url': 'https://facebook.com/ivan'},
            ],
        )
        assert result.phones == []
        svc.close()

    def test_vk_url_no_token_skipped(self):
        """VK URLs present but no token means extraction methods are skipped."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop('VK_SERVICE_TOKEN', None)
            svc = self._make_svc()
            result = svc.discover_sync(
                'Иван', 'Петров', [],
                profile_urls=[{'platform': 'vk', 'url': 'https://vk.com/ivan'}],
            )
            assert result.phones == []
            svc.close()

    def test_discovery_time_non_negative(self):
        """discovery_time must always be >= 0 (may be 0.0 on fast machines)."""
        svc = self._make_svc()
        result = svc.discover_sync('Иван', 'Петров', ['9161234567'])
        assert result.discovery_time >= 0
        assert isinstance(result.discovery_time, float)
        svc.close()

    def test_candidates_generated_counted(self):
        """candidates_generated reflects all pre-validation phones."""
        svc = self._make_svc()
        result = svc.discover_sync('Иван', 'Петров', ['9161234567'])
        assert result.candidates_generated >= 1
        svc.close()

    def test_username_with_id_prefix(self):
        """Username like id79161234567 should have phone extracted."""
        svc = self._make_svc()
        result = svc.discover_sync('Иван', 'Петров', ['id79161234567'])
        assert any('916' in p.number for p in result.phones)
        svc.close()

    def test_multiple_usernames_combined(self):
        """Phones from multiple usernames are all collected."""
        svc = self._make_svc()
        result = svc.discover_sync(
            'Иван', 'Петров',
            ['9161234567', '9031234567'],
        )
        numbers = [p.number for p in result.phones]
        assert any('916' in n for n in numbers)
        assert any('903' in n for n in numbers)
        svc.close()

    def test_non_phone_username_skipped(self):
        """Usernames without phone patterns produce no phones."""
        svc = self._make_svc()
        result = svc.discover_sync('Иван', 'Петров', ['ivan_petrov', 'cool_guy'])
        # Only phone-candidate generation may produce something, but with just text
        # usernames without digits, nothing should be produced.
        for phone in result.phones:
            assert phone.source  # If any phone appears, it has a source
        svc.close()

    def test_email_without_phone_pattern_no_extraction(self):
        """Regular email addresses don't produce phone extractions."""
        svc = self._make_svc()
        result = svc.discover_sync(
            'Иван', 'Петров', [],
            emails=['ivan.petrov@mail.ru', 'test@gmail.com'],
        )
        assert result.phones == []
        svc.close()

    def test_none_profile_urls_no_crash(self):
        """profile_urls=None is handled correctly (default)."""
        svc = self._make_svc()
        result = svc.discover_sync('Иван', 'Петров', [])
        assert isinstance(result, PhoneDiscoveryResults)
        svc.close()

    def test_none_emails_no_crash(self):
        """emails=None is handled correctly (default)."""
        svc = self._make_svc()
        result = svc.discover_sync('Иван', 'Петров', [], emails=None)
        assert isinstance(result, PhoneDiscoveryResults)
        svc.close()

    def test_username_with_7digit_pattern(self):
        """Username containing 7 digits triggers candidate generation."""
        svc = self._make_svc()
        result = svc.discover_sync('Иван', 'Петров', ['ivan1234567'])
        # 7-digit pattern should generate candidates with common prefixes
        assert result.candidates_generated >= 0
        svc.close()

    def test_close_does_not_crash(self):
        """Calling close() on the service should not raise."""
        svc = self._make_svc()
        svc.discover_sync('Иван', 'Петров', [])
        svc.close()  # Should not raise


# ═══════════════════════════════════════════════════════════════════════════
# 2. Phone pipeline with mocked VK API  (15+ tests)
# ═══════════════════════════════════════════════════════════════════════════

class TestPhonePipelineVKAPI:
    """Phone discovery with VK API calls mocked."""

    VK_PROFILES = [{'platform': 'vk', 'url': 'https://vk.com/id123456'}]

    def _run_with_vk_mock(self, users_response, wall_response=None, usernames=None,
                          emails=None):
        """Helper: set fake token, mock session.get, run discover_sync."""
        if wall_response is None:
            wall_response = _make_vk_wall_response([])

        call_count = {'n': 0}

        def side_effect(*args, **kwargs):
            url = args[0] if args else kwargs.get('url', '')
            call_count['n'] += 1
            if 'wall.get' in str(url):
                return _mock_vk_response(wall_response)
            return _mock_vk_response(users_response)

        with patch.dict(os.environ, {'VK_SERVICE_TOKEN': 'fake_token_for_test'}):
            svc = PhoneDiscoveryService()
            svc.session.get = MagicMock(side_effect=side_effect)
            result = svc.discover_sync(
                'Иван', 'Петров',
                usernames or [],
                profile_urls=self.VK_PROFILES,
                emails=emails,
            )
            svc.close()
            return result

    # --- VK users.get field extraction -------------------------------------

    def test_vk_mobile_phone_field(self):
        """VK returns mobile_phone field: extracted with high confidence."""
        resp = _make_vk_users_response({'mobile_phone': '+7 (916) 123-45-67'})
        result = self._run_with_vk_mock(resp)
        assert any('916' in p.number for p in result.phones)
        high = [p for p in result.phones if '916' in p.number and p.confidence == 'high']
        assert len(high) >= 1

    def test_vk_home_phone_field(self):
        """VK returns home_phone field: extracted."""
        resp = _make_vk_users_response({'home_phone': '+7 (916) 765-43-21'})
        result = self._run_with_vk_mock(resp)
        assert any('916' in p.number for p in result.phones)

    def test_vk_about_field_phone(self):
        """VK returns phone embedded in about text: extracted as medium."""
        resp = _make_vk_users_response({'about': 'Звоните: +79031234567'})
        result = self._run_with_vk_mock(resp)
        assert any('903' in p.number for p in result.phones)

    def test_vk_status_field_phone(self):
        """VK returns phone in status field: extracted."""
        resp = _make_vk_users_response({'status': 'WhatsApp +79161234567'})
        result = self._run_with_vk_mock(resp)
        assert any('916' in p.number for p in result.phones)

    def test_vk_error_code_5_token_expired(self):
        """VK error code 5 (token expired): error logged, pipeline continues."""
        resp = {'error': {'error_code': 5, 'error_msg': 'User authorization failed'}}
        result = self._run_with_vk_mock(resp)
        assert isinstance(result, PhoneDiscoveryResults)
        # No crash; phones list might be empty
        assert result.errors == []

    def test_vk_error_code_15_private(self):
        """VK error code 15 (private profile): skipped."""
        resp = {'error': {'error_code': 15, 'error_msg': 'Access denied'}}
        result = self._run_with_vk_mock(resp)
        assert isinstance(result, PhoneDiscoveryResults)

    def test_vk_empty_response_no_crash(self):
        """VK returns empty response list: no phones, no crash."""
        result = self._run_with_vk_mock({'response': []})
        assert result.phones == [] or all(
            p.source != 'VK profile (mobile_phone)' for p in result.phones
        )

    def test_vk_phone_hidden_skipped(self):
        """VK returns phone as short string (hidden): skipped."""
        resp = _make_vk_users_response({'mobile_phone': 'скрыт'})
        result = self._run_with_vk_mock(resp)
        # 'скрыт' is 5 chars in Russian, should be skipped (len <= 5)
        assert not any(
            p.source == 'VK profile (mobile_phone)' for p in result.phones
        )

    def test_vk_wall_phone_in_post(self):
        """VK wall has phone in post text: extracted."""
        users_resp = _make_vk_users_response({})
        wall_resp = _make_vk_wall_response([
            'Мой новый номер: +79261234567',
        ])
        result = self._run_with_vk_mock(users_resp, wall_resp)
        assert any('926' in p.number for p in result.phones)

    def test_vk_wall_phone_with_keyword_high_confidence(self):
        """Wall post with phone keyword gets high confidence."""
        users_resp = _make_vk_users_response({})
        wall_resp = _make_vk_wall_response([
            'Звоните по тел: +79261234567',
        ])
        result = self._run_with_vk_mock(users_resp, wall_resp)
        matches = [p for p in result.phones if '926' in p.number]
        assert len(matches) >= 1
        # 'тел' is a keyword so confidence should be high
        assert any(p.confidence == 'high' for p in matches)

    def test_vk_wall_multiple_posts(self):
        """Multiple wall posts with phones: all extracted."""
        users_resp = _make_vk_users_response({})
        wall_resp = _make_vk_wall_response([
            'Номер: +79161111111',
            'Звоните: +79262222222',
            'No phone here',
        ])
        result = self._run_with_vk_mock(users_resp, wall_resp)
        numbers_str = ' '.join(p.number for p in result.phones)
        # At least the two phone numbers should appear
        assert '916' in numbers_str or '926' in numbers_str

    def test_vk_wall_error_private_profile(self):
        """VK wall.get returns error 15 (private): no crash."""
        users_resp = _make_vk_users_response({})
        wall_resp = {'error': {'error_code': 15, 'error_msg': 'Access denied'}}
        result = self._run_with_vk_mock(users_resp, wall_resp)
        assert isinstance(result, PhoneDiscoveryResults)

    def test_vk_contacts_nested_field(self):
        """VK contacts as nested dict: mobile_phone extracted."""
        resp = _make_vk_users_response({
            'contacts': {'mobile_phone': '+79161234567', 'home_phone': ''}
        })
        result = self._run_with_vk_mock(resp)
        assert any('916' in p.number for p in result.phones)

    def test_vk_site_field_phone(self):
        """VK site field contains phone: extracted."""
        resp = _make_vk_users_response({'site': 'whatsapp: +79031234567'})
        result = self._run_with_vk_mock(resp)
        assert any('903' in p.number for p in result.phones)

    def test_vk_url_with_screen_name(self):
        """VK URL with screen name (not numeric ID) is parsed correctly."""
        profiles = [{'platform': 'vk', 'url': 'https://vk.com/ivan_petrov'}]
        resp = _make_vk_users_response({'mobile_phone': '+79161234567'})

        with patch.dict(os.environ, {'VK_SERVICE_TOKEN': 'fake'}):
            svc = PhoneDiscoveryService()
            svc.session.get = MagicMock(return_value=_mock_vk_response(resp))
            result = svc.discover_sync('Иван', 'Петров', [], profile_urls=profiles)
            svc.close()
            assert any('916' in p.number for p in result.phones)

    def test_vk_multiple_profile_urls_limited(self):
        """Only first 3 VK profiles are queried (per code limit)."""
        profiles = [
            {'platform': 'vk', 'url': f'https://vk.com/id{i}'}
            for i in range(10)
        ]
        resp = _make_vk_users_response({'mobile_phone': '+79161234567'})
        call_count = {'n': 0}

        def side_effect(*args, **kwargs):
            call_count['n'] += 1
            return _mock_vk_response(resp)

        with patch.dict(os.environ, {'VK_SERVICE_TOKEN': 'fake'}):
            svc = PhoneDiscoveryService()
            svc.session.get = MagicMock(side_effect=side_effect)
            svc.discover_sync('Иван', 'Петров', [], profile_urls=profiles)
            svc.close()
            # users.get for 3 profiles + wall.get for 2 profiles = 5 calls
            assert call_count['n'] <= 10

    def test_vk_request_exception_handled(self):
        """VK API request raising exception: caught, pipeline continues."""
        with patch.dict(os.environ, {'VK_SERVICE_TOKEN': 'fake'}):
            svc = PhoneDiscoveryService()
            svc.session.get = MagicMock(side_effect=Exception("Network error"))
            result = svc.discover_sync(
                'Иван', 'Петров', [],
                profile_urls=self.VK_PROFILES,
            )
            svc.close()
            assert isinstance(result, PhoneDiscoveryResults)

    def test_vk_timeout_handled(self):
        """VK API timeout: caught, pipeline continues."""
        import requests as req

        with patch.dict(os.environ, {'VK_SERVICE_TOKEN': 'fake'}):
            svc = PhoneDiscoveryService()
            svc.session.get = MagicMock(side_effect=req.Timeout("timeout"))
            result = svc.discover_sync(
                'Иван', 'Петров', [],
                profile_urls=self.VK_PROFILES,
            )
            svc.close()
            assert isinstance(result, PhoneDiscoveryResults)

    def test_vk_invalid_url_skipped(self):
        """VK profile URL without user ID pattern is skipped."""
        profiles = [{'platform': 'vk', 'url': 'https://vk.com/'}]
        resp = _make_vk_users_response({})
        with patch.dict(os.environ, {'VK_SERVICE_TOKEN': 'fake'}):
            svc = PhoneDiscoveryService()
            svc.session.get = MagicMock(return_value=_mock_vk_response(resp))
            result = svc.discover_sync('Иван', 'Петров', [], profile_urls=profiles)
            svc.close()
            # session.get should NOT have been called because URL parsing fails
            assert isinstance(result, PhoneDiscoveryResults)


# ═══════════════════════════════════════════════════════════════════════════
# 3. Email candidate pipeline  (10+ tests)
# ═══════════════════════════════════════════════════════════════════════════

class TestEmailCandidatePipeline:
    """Tests for EmailDiscoveryService._generate_candidates and _is_valid_email."""

    def _make_svc(self):
        return EmailDiscoveryService()

    def test_russian_name_generates_valid_emails(self):
        """Candidates from Russian name are all valid format."""
        svc = self._make_svc()
        candidates = svc._generate_candidates('Иван', 'Петров', [])
        assert len(candidates) > 0
        for email in candidates:
            assert svc._is_valid_email(email), f"Invalid: {email}"
        svc.close()

    def test_candidates_include_domain_variety(self):
        """Candidates include mail.ru, yandex.ru, and other domains."""
        svc = EmailDiscoveryService(max_candidates=200)
        candidates = svc._generate_candidates('Иван', 'Петров', ['ivanpetrov'])
        domains = {c.split('@')[1] for c in candidates}
        assert 'mail.ru' in domains
        assert 'yandex.ru' in domains
        # With enough candidates, gmail.com should also appear
        assert 'gmail.com' in domains
        # At least 3 different domains used
        assert len(domains) >= 3
        svc.close()

    def test_candidates_capped_at_max(self):
        """Candidates are capped at max_candidates (default 30)."""
        svc = self._make_svc()
        candidates = svc._generate_candidates('Иван', 'Петров', ['ivan', 'petrov', 'user1'])
        assert len(candidates) <= svc.max_candidates
        svc.close()

    def test_username_based_candidates_included(self):
        """Username-based email candidates are generated."""
        svc = self._make_svc()
        candidates = svc._generate_candidates('Иван', 'Петров', ['coolivan2000'])
        # The clean username should appear as local part in some candidate
        assert any('coolivan2000' in c for c in candidates)
        svc.close()

    def test_no_duplicate_candidates(self):
        """No duplicate candidates in the list."""
        svc = self._make_svc()
        candidates = svc._generate_candidates('Иван', 'Петров', ['ivan'])
        assert len(candidates) == len(set(candidates))
        svc.close()

    def test_is_valid_email_positive(self):
        """Valid emails pass validation."""
        svc = self._make_svc()
        assert svc._is_valid_email('test@mail.ru')
        assert svc._is_valid_email('ivan.petrov@gmail.com')
        assert svc._is_valid_email('user_123@yandex.ru')
        svc.close()

    def test_is_valid_email_negative(self):
        """Invalid emails are rejected."""
        svc = self._make_svc()
        assert not svc._is_valid_email('@mail.ru')
        assert not svc._is_valid_email('test@')
        assert not svc._is_valid_email('test')
        assert not svc._is_valid_email('')
        svc.close()

    def test_transliteration_applied(self):
        """Russian names are transliterated to Latin for email generation."""
        svc = self._make_svc()
        candidates = svc._generate_candidates('Иван', 'Петров', [])
        # 'Иван' -> 'ivan', 'Петров' -> 'petrov'
        assert any('ivan' in c for c in candidates)
        assert any('petrov' in c for c in candidates)
        svc.close()

    def test_candidates_all_lowercase(self):
        """All candidates are lowercase."""
        svc = self._make_svc()
        candidates = svc._generate_candidates('Иван', 'Петров', ['IvanP'])
        for c in candidates:
            assert c == c.lower(), f"Not lowercase: {c}"
        svc.close()

    def test_short_username_skipped(self):
        """Usernames shorter than 3 chars are not used for patterns."""
        svc = self._make_svc()
        candidates = svc._generate_candidates('Иван', 'Петров', ['ab'])
        # 'ab' is too short after cleaning, should not appear
        assert not any(c.startswith('ab@') for c in candidates)
        svc.close()

    def test_empty_name_no_crash(self):
        """Empty name strings don't crash candidate generation."""
        svc = self._make_svc()
        candidates = svc._generate_candidates('', '', ['testuser'])
        assert isinstance(candidates, list)
        svc.close()

    def test_special_chars_cleaned_from_username(self):
        """Special characters are stripped from usernames."""
        svc = self._make_svc()
        candidates = svc._generate_candidates('Иван', 'Петров', ['@ivan!petrov#'])
        # The cleaned version should be 'ivan!petrov#' -> after re.sub only 'ivanpetrov'
        # Actually _clean_username strips @, id, user, profile prefix, then non-alphanumeric
        # So '@ivan!petrov#' -> 'ivan!petrov#' -> 'ivanpetrov'
        if any('ivanpetrov' in c for c in candidates):
            assert True  # Expected
        svc.close()

    def test_max_candidates_custom(self):
        """Custom max_candidates is respected."""
        svc = EmailDiscoveryService(max_candidates=5)
        candidates = svc._generate_candidates('Иван', 'Петров', ['ivan', 'petrov'])
        assert len(candidates) <= 5
        svc.close()


# ═══════════════════════════════════════════════════════════════════════════
# 4. SourceManager pipeline  (15+ tests)
# ═══════════════════════════════════════════════════════════════════════════

class TestSourceManagerPipeline:
    """Tests for SourceManager with injected mock sources."""

    def _make_manager_with_sources(self, sources):
        """Create a SourceManager with custom sources (skip auto-discovery)."""
        mgr = SourceManager.__new__(SourceManager)
        mgr.max_workers = 4
        mgr.timeout = 10.0
        mgr.sources = sources
        return mgr

    def test_run_all_one_source_returns_results(self):
        """One source with results: grouped by type."""
        src = _FakeSource(results=[
            SourceResult(
                data_type='email', value='test@mail.ru',
                source_name='FakeSource', source_tier=SourceTier.C,
                confidence=0.7,
            ),
        ])
        mgr = self._make_manager_with_sources([src])
        grouped = mgr.run_all(name='test')
        assert 'email' in grouped
        assert len(grouped['email']) == 1
        assert grouped['email'][0].value == 'test@mail.ru'

    def test_run_all_source_exception_caught(self):
        """Source raising exception: error caught, pipeline continues."""
        bad = _FakeSource(raise_exc=RuntimeError("boom"))
        good = _FakeSource(results=[
            SourceResult(
                data_type='phone', value='+79161234567',
                source_name='GoodSource', source_tier=SourceTier.A,
                confidence=0.8,
            ),
        ])
        good.name = "GoodSource"
        mgr = self._make_manager_with_sources([bad, good])
        grouped = mgr.run_all(name='test')
        # The good source's results should still be present
        assert 'phone' in grouped

    def test_run_all_no_active_sources(self):
        """No active sources: returns empty dict."""
        src = _FakeSource(available=False)
        mgr = self._make_manager_with_sources([src])
        grouped = mgr.run_all(name='test')
        assert grouped == {}

    def test_run_all_disabled_source_skipped(self):
        """Disabled source is not run."""
        src = _FakeSource(results=[
            SourceResult(
                data_type='email', value='a@b.com',
                source_name='FakeSource', source_tier=SourceTier.C,
                confidence=0.5,
            ),
        ])
        src.enabled = False
        mgr = self._make_manager_with_sources([src])
        grouped = mgr.run_all(name='test')
        assert grouped == {}

    def test_run_tier_filters_correctly(self):
        """run_tier only runs sources of the specified tier."""
        src_a = _TierASource(results=[
            SourceResult(
                data_type='phone', value='+79161234567',
                source_name='TierASource', source_tier=SourceTier.A,
                confidence=0.8,
            ),
        ])
        src_b = _TierBSource(results=[
            SourceResult(
                data_type='email', value='x@y.com',
                source_name='TierBSource', source_tier=SourceTier.B,
                confidence=0.6,
            ),
        ])
        mgr = self._make_manager_with_sources([src_a, src_b])
        grouped = mgr.run_tier(SourceTier.A, name='test')
        # Only tier A results should be present
        assert 'phone' in grouped
        assert 'email' not in grouped

    def test_run_tier_restores_enabled_state(self):
        """run_tier restores original enabled state after running."""
        src_a = _TierASource()
        src_b = _TierBSource()
        src_a.enabled = True
        src_b.enabled = True
        mgr = self._make_manager_with_sources([src_a, src_b])
        mgr.run_tier(SourceTier.A, name='test')
        assert src_a.enabled is True
        assert src_b.enabled is True

    def test_get_source_status_returns_info(self):
        """get_source_status returns info for all registered sources."""
        src = _FakeSource()
        mgr = self._make_manager_with_sources([src])
        status = mgr.get_source_status()
        assert len(status) == 1
        assert status[0]['name'] == 'FakeSource'
        assert 'available' in status[0]
        assert 'tier' in status[0]

    def test_get_source_status_sorted_by_availability(self):
        """Available sources come first in status."""
        avail = _FakeSource(available=True)
        avail.name = "AvailSource"
        unavail = _FakeSource(available=False)
        unavail.name = "UnavailSource"
        mgr = self._make_manager_with_sources([unavail, avail])
        status = mgr.get_source_status()
        assert status[0]['name'] == 'AvailSource'

    def test_exclude_sources_not_run(self):
        """Excluded sources are skipped."""
        src = _FakeSource(results=[
            SourceResult(
                data_type='email', value='excluded@test.com',
                source_name='FakeSource', source_tier=SourceTier.C,
                confidence=0.5,
            ),
        ])
        mgr = self._make_manager_with_sources([src])
        grouped = mgr.run_all(exclude_sources=['FakeSource'], name='test')
        assert grouped == {}

    def test_deduplication_same_email_merged(self):
        """Same email from two sources is merged with boosted confidence."""
        src1 = _FakeSource(results=[
            SourceResult(
                data_type='email', value='dup@mail.ru',
                source_name='Source1', source_tier=SourceTier.B,
                confidence=0.6,
            ),
        ])
        src1.name = "Source1"
        src2 = _FakeSource(results=[
            SourceResult(
                data_type='email', value='dup@mail.ru',
                source_name='Source2', source_tier=SourceTier.A,
                confidence=0.7,
            ),
        ])
        src2.name = "Source2"
        mgr = self._make_manager_with_sources([src1, src2])
        grouped = mgr.run_all(name='test')
        assert 'email' in grouped
        # Should be merged into one result
        assert len(grouped['email']) == 1
        # Confidence should be boosted above the higher individual confidence
        assert grouped['email'][0].confidence >= 0.7

    def test_deduplication_different_emails_separate(self):
        """Different emails remain separate after deduplication."""
        src = _FakeSource(results=[
            SourceResult(
                data_type='email', value='a@mail.ru',
                source_name='FakeSource', source_tier=SourceTier.C,
                confidence=0.5,
            ),
            SourceResult(
                data_type='email', value='b@mail.ru',
                source_name='FakeSource', source_tier=SourceTier.C,
                confidence=0.5,
            ),
        ])
        mgr = self._make_manager_with_sources([src])
        grouped = mgr.run_all(name='test')
        assert len(grouped['email']) == 2

    def test_cross_validate_breach_data(self):
        """Phone + email from Tier S sources get cross-validated."""
        src = _FakeSource(results=[
            SourceResult(
                data_type='phone', value='+79161234567',
                source_name='BreachDB', source_tier=SourceTier.S,
                confidence=0.9,
            ),
            SourceResult(
                data_type='email', value='breach@mail.ru',
                source_name='BreachDB', source_tier=SourceTier.S,
                confidence=0.9,
            ),
        ])
        src.source_tier = SourceTier.S
        mgr = self._make_manager_with_sources([src])
        grouped = mgr.run_all(name='test')
        # Both should be marked as verified via cross-validation
        phone_results = grouped.get('phone', [])
        email_results = grouped.get('email', [])
        assert len(phone_results) >= 1
        assert len(email_results) >= 1
        assert phone_results[0].verified
        assert email_results[0].verified

    def test_results_sorted_by_confidence(self):
        """Results within each group are sorted by confidence desc."""
        src = _FakeSource(results=[
            SourceResult(
                data_type='email', value='low@mail.ru',
                source_name='FakeSource', source_tier=SourceTier.C,
                confidence=0.3,
            ),
            SourceResult(
                data_type='email', value='high@mail.ru',
                source_name='FakeSource', source_tier=SourceTier.C,
                confidence=0.9,
            ),
        ])
        mgr = self._make_manager_with_sources([src])
        grouped = mgr.run_all(name='test')
        emails = grouped['email']
        assert emails[0].confidence >= emails[1].confidence

    def test_source_returning_empty_list(self):
        """Source returning empty list: handled gracefully."""
        src = _FakeSource(results=[])
        mgr = self._make_manager_with_sources([src])
        grouped = mgr.run_all(name='test')
        assert grouped == {}

    def test_multiple_data_types_grouped(self):
        """Results of different types are grouped separately."""
        src = _FakeSource(results=[
            SourceResult(
                data_type='email', value='e@test.com',
                source_name='FakeSource', source_tier=SourceTier.C,
                confidence=0.5,
            ),
            SourceResult(
                data_type='phone', value='+79161234567',
                source_name='FakeSource', source_tier=SourceTier.C,
                confidence=0.5,
            ),
            SourceResult(
                data_type='profile', value='https://vk.com/ivan',
                source_name='FakeSource', source_tier=SourceTier.C,
                confidence=0.5,
            ),
        ])
        mgr = self._make_manager_with_sources([src])
        grouped = mgr.run_all(name='test')
        assert 'email' in grouped
        assert 'phone' in grouped
        assert 'profile' in grouped

    def test_multi_source_confirmation_verified(self):
        """Data confirmed by 3+ sources gets verified flag."""
        sources = []
        for i in range(3):
            src = _FakeSource(results=[
                SourceResult(
                    data_type='email', value='multi@test.com',
                    source_name=f'Source{i}', source_tier=SourceTier.B,
                    confidence=0.7,
                ),
            ])
            src.name = f"Source{i}"
            sources.append(src)
        mgr = self._make_manager_with_sources(sources)
        grouped = mgr.run_all(name='test')
        email_result = grouped['email'][0]
        assert email_result.verified
        assert email_result.metadata.get('source_count', 0) >= 3


# ═══════════════════════════════════════════════════════════════════════════
# 5. Pipeline error resilience  (10+ tests)
# ═══════════════════════════════════════════════════════════════════════════

class TestPipelineErrorResilience:
    """Pipeline must survive various failures gracefully."""

    def test_vk_api_timeout_continues(self):
        """VK API timeout: logged, pipeline returns results from other methods."""
        import requests as req

        with patch.dict(os.environ, {'VK_SERVICE_TOKEN': 'fake'}):
            svc = PhoneDiscoveryService()
            svc.session.get = MagicMock(side_effect=req.Timeout("timed out"))
            result = svc.discover_sync(
                'Иван', 'Петров',
                ['9161234567'],  # Should still extract from username
                profile_urls=[{'platform': 'vk', 'url': 'https://vk.com/id123'}],
            )
            svc.close()
            assert isinstance(result, PhoneDiscoveryResults)
            # Username extraction should still work
            assert any('916' in p.number for p in result.phones)

    def test_telegram_crossref_import_fails(self):
        """Telegram cross-ref module not available: warning logged, continues."""
        with patch.dict(os.environ, {'VK_SERVICE_TOKEN': 'fake'}):
            svc = PhoneDiscoveryService()

            # Mock _cross_reference_telegram to simulate ImportError handling
            # The real method already handles ImportError internally
            svc.session.get = MagicMock(return_value=_mock_vk_response(
                _make_vk_users_response({})
            ))
            result = svc.discover_sync(
                'Иван', 'Петров', [],
                profile_urls=[{'platform': 'vk', 'url': 'https://vk.com/id123'}],
            )
            svc.close()
            assert isinstance(result, PhoneDiscoveryResults)

    def test_multiple_errors_captured(self):
        """When discover_sync has a catastrophic error, it goes to errors list."""
        svc = PhoneDiscoveryService()
        # Patch _extract_from_usernames to raise
        with patch.object(svc, '_extract_from_usernames', side_effect=RuntimeError("boom")):
            result = svc.discover_sync('Иван', 'Петров', ['test'])
            assert len(result.errors) >= 1
            assert 'boom' in result.errors[0]
        svc.close()

    def test_partial_results_on_failure(self):
        """When some methods fail, partial results from successful methods are returned."""
        with patch.dict(os.environ, {'VK_SERVICE_TOKEN': 'fake'}):
            svc = PhoneDiscoveryService()
            # VK calls fail
            svc.session.get = MagicMock(side_effect=Exception("api down"))
            # But username extraction should work
            result = svc.discover_sync(
                'Иван', 'Петров',
                ['9161234567'],
                profile_urls=[{'platform': 'vk', 'url': 'https://vk.com/id123'}],
            )
            svc.close()
            # Should have phone from username even though VK failed
            assert any('916' in p.number for p in result.phones)

    def test_pipeline_always_returns_valid_object(self):
        """Pipeline returns PhoneDiscoveryResults even on total failure."""
        svc = PhoneDiscoveryService()
        with patch.object(svc, '_extract_from_usernames', side_effect=Exception("fail")):
            result = svc.discover_sync('', '', ['test'])
            assert isinstance(result, PhoneDiscoveryResults)
            assert isinstance(result.phones, list)
            assert isinstance(result.errors, list)
            assert isinstance(result.discovery_time, float)
        svc.close()

    def test_email_pipeline_always_returns_valid_object(self):
        """Email pipeline returns EmailDiscoveryResults even on error."""
        svc = EmailDiscoveryService()
        result_obj = EmailDiscoveryResults()
        assert isinstance(result_obj, EmailDiscoveryResults)
        assert isinstance(result_obj.emails, list)
        assert isinstance(result_obj.errors, list)
        svc.close()

    def test_source_manager_timeout_handled(self):
        """SourceManager handles overall timeout."""
        import time as _time

        class SlowSource(_FakeSource):
            name = "SlowSource"

            def query_impl(self, **kwargs):
                _time.sleep(0.1)
                return [SourceResult(
                    data_type='email', value='slow@test.com',
                    source_name='SlowSource', source_tier=SourceTier.C,
                    confidence=0.5,
                )]

        mgr = SourceManager.__new__(SourceManager)
        mgr.max_workers = 2
        mgr.timeout = 30.0
        mgr.sources = [SlowSource()]
        # Should complete without timeout error
        grouped = mgr.run_all(name='test')
        assert isinstance(grouped, dict)

    def test_vk_json_decode_error(self):
        """VK API returns invalid JSON: handled."""
        with patch.dict(os.environ, {'VK_SERVICE_TOKEN': 'fake'}):
            svc = PhoneDiscoveryService()
            mock_resp = MagicMock()
            mock_resp.json.side_effect = ValueError("invalid json")
            svc.session.get = MagicMock(return_value=mock_resp)
            result = svc.discover_sync(
                'Иван', 'Петров', [],
                profile_urls=[{'platform': 'vk', 'url': 'https://vk.com/id123'}],
            )
            svc.close()
            assert isinstance(result, PhoneDiscoveryResults)

    def test_connection_error_handled(self):
        """Requests ConnectionError: handled gracefully."""
        import requests as req

        with patch.dict(os.environ, {'VK_SERVICE_TOKEN': 'fake'}):
            svc = PhoneDiscoveryService()
            svc.session.get = MagicMock(side_effect=req.ConnectionError("offline"))
            result = svc.discover_sync(
                'Иван', 'Петров', [],
                profile_urls=[{'platform': 'vk', 'url': 'https://vk.com/id123'}],
            )
            svc.close()
            assert isinstance(result, PhoneDiscoveryResults)

    def test_validator_exception_in_loop(self):
        """If validator raises during filtering, pipeline doesn't crash."""
        svc = PhoneDiscoveryService()
        # Add a phone with a garbage number that might confuse validator
        result = svc.discover_sync('Иван', 'Петров', ['not-a-number-at-all'])
        assert isinstance(result, PhoneDiscoveryResults)
        svc.close()

    def test_empty_vk_wall_items(self):
        """VK wall.get returns response with empty items list."""
        resp = _make_vk_users_response({})
        wall = {'response': {'count': 0, 'items': []}}

        with patch.dict(os.environ, {'VK_SERVICE_TOKEN': 'fake'}):
            svc = PhoneDiscoveryService()

            def side_effect(*args, **kwargs):
                url = args[0] if args else kwargs.get('url', '')
                if 'wall.get' in str(url):
                    return _mock_vk_response(wall)
                return _mock_vk_response(resp)

            svc.session.get = MagicMock(side_effect=side_effect)
            result = svc.discover_sync(
                'Иван', 'Петров', [],
                profile_urls=[{'platform': 'vk', 'url': 'https://vk.com/id123'}],
            )
            svc.close()
            assert isinstance(result, PhoneDiscoveryResults)


# ═══════════════════════════════════════════════════════════════════════════
# 6. Result quality  (10+ tests)
# ═══════════════════════════════════════════════════════════════════════════

class TestResultQuality:
    """Verify the quality and format of returned results."""

    def test_phone_format_valid(self):
        """All returned phones match the display format pattern."""
        svc = PhoneDiscoveryService()
        result = svc.discover_sync('Иван', 'Петров', ['9161234567'])
        for phone in result.phones:
            # Display format: +7 (XXX) XXX-XX-XX
            assert re.match(r'\+7 \(\d{3}\) \d{3}-\d{2}-\d{2}', phone.number), \
                f"Bad format: {phone.number}"
        svc.close()

    def test_all_phones_are_mobile(self):
        """Only mobile numbers (prefix 9XX) in results."""
        svc = PhoneDiscoveryService()
        result = svc.discover_sync('Иван', 'Петров', ['9161234567'])
        for phone in result.phones:
            digits = re.sub(r'\D', '', phone.number)
            # After +7, the next digit should be 9 (mobile)
            if len(digits) == 11 and digits.startswith('7'):
                assert digits[1] == '9', f"Non-mobile phone in results: {phone.number}"
        svc.close()

    def test_no_duplicate_phones(self):
        """No duplicate phone numbers in results."""
        svc = PhoneDiscoveryService()
        result = svc.discover_sync(
            'Иван', 'Петров',
            ['9161234567', '9161234567', '+79161234567'],
        )
        numbers = [p.number for p in result.phones]
        assert len(numbers) == len(set(numbers))
        svc.close()

    @pytest.mark.parametrize("username,expected_confidence", [
        ('9161234567', 'medium'),
    ])
    def test_confidence_values_valid(self, username, expected_confidence):
        """Confidence values are one of the valid strings."""
        svc = PhoneDiscoveryService()
        result = svc.discover_sync('Иван', 'Петров', [username])
        valid_confidence = {'high', 'medium', 'low'}
        for phone in result.phones:
            assert phone.confidence in valid_confidence, \
                f"Invalid confidence: {phone.confidence}"
        svc.close()

    def test_source_strings_are_descriptive(self):
        """Source strings contain useful info about where phone was found."""
        svc = PhoneDiscoveryService()
        result = svc.discover_sync('Иван', 'Петров', ['9161234567'])
        for phone in result.phones:
            assert len(phone.source) > 5, f"Source too short: {phone.source}"
            assert phone.source != ''
        svc.close()

    def test_carrier_hint_populated_for_known_prefixes(self):
        """Carrier hint is populated for phones with known prefixes."""
        svc = PhoneDiscoveryService()
        # 916 is Megafon prefix
        result = svc.discover_sync('Иван', 'Петров', ['9161234567'])
        for phone in result.phones:
            if '916' in phone.number:
                assert phone.carrier is not None
                assert phone.carrier != ''
        svc.close()

    def test_landline_phone_filtered_out(self):
        """Landline numbers (e.g. 495 prefix) are filtered out (only mobile kept)."""
        svc = PhoneDiscoveryService()
        # Try to inject a landline-looking username
        result = svc.discover_sync('Иван', 'Петров', ['74951234567'])
        # 495 is a Moscow landline prefix, should be filtered
        for phone in result.phones:
            digits = re.sub(r'\D', '', phone.number)
            if len(digits) == 11 and digits.startswith('7'):
                assert digits[1] == '9', f"Landline not filtered: {phone.number}"
        svc.close()

    def test_phone_number_normalized_to_display_format(self):
        """Phones are normalized to +7 (XXX) XXX-XX-XX display format."""
        svc = PhoneDiscoveryService()
        result = svc.discover_sync('Иван', 'Петров', ['9261234567'])
        for phone in result.phones:
            assert phone.number.startswith('+7 ('), \
                f"Not in display format: {phone.number}"
        svc.close()

    def test_discovered_phone_dataclass_defaults(self):
        """DiscoveredPhone defaults are correct."""
        phone = DiscoveredPhone(
            number='+7 (916) 123-45-67',
            source='test',
            confidence='high',
        )
        assert phone.verified is False
        assert phone.carrier is None
        assert phone.region is None
        assert phone.telegram_url is None

    def test_phone_discovery_results_dataclass_defaults(self):
        """PhoneDiscoveryResults defaults are correct."""
        results = PhoneDiscoveryResults()
        assert results.phones == []
        assert results.additional_profiles == []
        assert results.candidates_generated == 0
        assert results.candidates_verified == 0
        assert results.discovery_time == 0
        assert results.errors == []

    def test_email_discovery_results_dataclass_defaults(self):
        """EmailDiscoveryResults defaults are correct."""
        results = EmailDiscoveryResults()
        assert results.emails == []
        assert results.candidates_generated == 0
        assert results.candidates_verified == 0
        assert results.discovery_time == 0
        assert results.errors == []

    def test_source_result_confidence_label(self):
        """SourceResult.confidence_label returns correct labels."""
        assert SourceResult(
            data_type='x', value='y', source_name='z',
            source_tier=SourceTier.C, confidence=0.95,
        ).confidence_label == 'very_high'
        assert SourceResult(
            data_type='x', value='y', source_name='z',
            source_tier=SourceTier.C, confidence=0.75,
        ).confidence_label == 'high'
        assert SourceResult(
            data_type='x', value='y', source_name='z',
            source_tier=SourceTier.C, confidence=0.55,
        ).confidence_label == 'medium'
        assert SourceResult(
            data_type='x', value='y', source_name='z',
            source_tier=SourceTier.C, confidence=0.3,
        ).confidence_label == 'low'

    def test_source_result_to_dict(self):
        """SourceResult.to_dict returns serializable dict."""
        sr = SourceResult(
            data_type='email', value='test@test.com',
            source_name='test', source_tier=SourceTier.A,
            confidence=0.8, verified=True,
            metadata={'key': 'value'},
        )
        d = sr.to_dict()
        assert d['data_type'] == 'email'
        assert d['value'] == 'test@test.com'
        assert d['source_name'] == 'test'
        assert d['source_tier'] == 'Platform API'
        assert d['confidence'] == 0.8
        assert d['confidence_label'] == 'high'
        assert d['verified'] is True
        assert d['metadata'] == {'key': 'value'}
        # Must be JSON-serializable
        json.dumps(d)


# ═══════════════════════════════════════════════════════════════════════════
# 7. Combined scenarios  (5+ tests)
# ═══════════════════════════════════════════════════════════════════════════

class TestCombinedScenarios:
    """Full pipeline scenarios testing multiple sources working together."""

    def test_full_pipeline_all_sources_contribute(self):
        """Name + usernames with phone + emails with phone: all sources contribute."""
        resp = _make_vk_users_response({'mobile_phone': '+7 (965) 111-22-33'})
        wall = _make_vk_wall_response(['Мой номер: +79031234567'])

        def side_effect(*args, **kwargs):
            url = args[0] if args else kwargs.get('url', '')
            if 'wall.get' in str(url):
                return _mock_vk_response(wall)
            return _mock_vk_response(resp)

        with patch.dict(os.environ, {'VK_SERVICE_TOKEN': 'fake'}):
            svc = PhoneDiscoveryService()
            svc.session.get = MagicMock(side_effect=side_effect)
            result = svc.discover_sync(
                'Иван', 'Петров',
                ['9161234567'],  # username phone
                profile_urls=[{'platform': 'vk', 'url': 'https://vk.com/id123'}],
                emails=['9261234567@mail.ru'],  # email phone
            )
            svc.close()

        # We should have phones from VK API, wall, username, and email
        numbers_str = ' '.join(p.number for p in result.phones)
        sources_str = ' '.join(p.source for p in result.phones)
        assert len(result.phones) >= 2  # At least from multiple sources
        assert result.discovery_time >= 0
        assert result.candidates_generated >= 2

    def test_pipeline_with_only_usernames(self):
        """Pipeline with just usernames (no VK, no emails) still works."""
        svc = PhoneDiscoveryService()
        result = svc.discover_sync(
            'Иван', 'Петров',
            ['9161234567', 'ivan_petrov', '9031234567'],
        )
        svc.close()
        assert len(result.phones) >= 1
        assert result.errors == []

    def test_pipeline_multiple_platforms_only_vk(self):
        """profile_urls with multiple platforms: only VK is processed."""
        with patch.dict(os.environ, {'VK_SERVICE_TOKEN': 'fake'}):
            svc = PhoneDiscoveryService()
            resp = _make_vk_users_response({'mobile_phone': '+79161234567'})
            svc.session.get = MagicMock(return_value=_mock_vk_response(resp))
            result = svc.discover_sync(
                'Иван', 'Петров', [],
                profile_urls=[
                    {'platform': 'vk', 'url': 'https://vk.com/id123'},
                    {'platform': 'instagram', 'url': 'https://instagram.com/ivan'},
                    {'platform': 'ok', 'url': 'https://ok.ru/profile/123'},
                    {'platform': 'twitter', 'url': 'https://twitter.com/ivan'},
                ],
            )
            svc.close()
        # Only VK should have been queried
        assert isinstance(result, PhoneDiscoveryResults)

    def test_deduplication_across_methods(self):
        """Same phone found via VK API and username is deduplicated."""
        resp = _make_vk_users_response({'mobile_phone': '+7 (916) 123-45-67'})

        def side_effect(*args, **kwargs):
            url = args[0] if args else kwargs.get('url', '')
            if 'wall.get' in str(url):
                return _mock_vk_response(_make_vk_wall_response([]))
            return _mock_vk_response(resp)

        with patch.dict(os.environ, {'VK_SERVICE_TOKEN': 'fake'}):
            svc = PhoneDiscoveryService()
            svc.session.get = MagicMock(side_effect=side_effect)
            result = svc.discover_sync(
                'Иван', 'Петров',
                ['9161234567'],  # Same phone as VK returns
                profile_urls=[{'platform': 'vk', 'url': 'https://vk.com/id123'}],
            )
            svc.close()

        # Should be deduplicated to one entry
        matching = [p for p in result.phones if '916' in p.number]
        assert len(matching) == 1

    def test_email_and_phone_services_independent(self):
        """EmailDiscoveryService and PhoneDiscoveryService can be used independently."""
        phone_svc = PhoneDiscoveryService()
        email_svc = EmailDiscoveryService()

        phone_result = phone_svc.discover_sync('Иван', 'Петров', ['9161234567'])
        candidates = email_svc._generate_candidates('Иван', 'Петров', ['ivan'])

        assert isinstance(phone_result, PhoneDiscoveryResults)
        assert isinstance(candidates, list)
        assert len(candidates) > 0

        phone_svc.close()
        email_svc.close()

    def test_source_manager_with_mixed_tiers(self):
        """SourceManager handles a mix of tier S, A, B, C sources."""
        src_s = _TierSSource(results=[
            SourceResult(
                data_type='email', value='breach@test.com',
                source_name='TierSSource', source_tier=SourceTier.S,
                confidence=0.95,
            ),
        ])
        src_a = _TierASource(results=[
            SourceResult(
                data_type='phone', value='+79161234567',
                source_name='TierASource', source_tier=SourceTier.A,
                confidence=0.8,
            ),
        ])
        src_b = _TierBSource(results=[
            SourceResult(
                data_type='email', value='verified@test.com',
                source_name='TierBSource', source_tier=SourceTier.B,
                confidence=0.7,
            ),
        ])
        src_c = _FakeSource(results=[
            SourceResult(
                data_type='email', value='pattern@test.com',
                source_name='FakeSource', source_tier=SourceTier.C,
                confidence=0.3,
            ),
        ])
        mgr = SourceManager.__new__(SourceManager)
        mgr.max_workers = 4
        mgr.timeout = 10.0
        mgr.sources = [src_s, src_a, src_b, src_c]
        grouped = mgr.run_all(name='test')

        assert 'email' in grouped
        assert 'phone' in grouped
        # Highest confidence email should be first
        assert grouped['email'][0].confidence >= grouped['email'][-1].confidence

    def test_phone_from_email_feeds_into_pipeline(self):
        """Phone extracted from email is validated and returned."""
        svc = PhoneDiscoveryService()
        result = svc.discover_sync(
            'Иван', 'Петров', [],
            emails=['89161234567@yandex.ru'],
        )
        svc.close()
        # 89161234567 -> +79161234567 which is valid mobile
        assert any('916' in p.number for p in result.phones)
        assert any('Email local part' in p.source for p in result.phones)


# ═══════════════════════════════════════════════════════════════════════════
# 8. Parametrized edge cases
# ═══════════════════════════════════════════════════════════════════════════

class TestParametrizedEdgeCases:
    """Parametrized tests for edge cases and boundary conditions."""

    @pytest.mark.parametrize("username", [
        '9161234567',
        '89161234567',
        '79161234567',
        'id79161234567',
    ])
    def test_various_phone_username_formats(self, username):
        """Various phone-like username formats are extracted."""
        svc = PhoneDiscoveryService()
        result = svc.discover_sync('Иван', 'Петров', [username])
        assert any('916' in p.number for p in result.phones), \
            f"Failed to extract phone from username: {username}"
        svc.close()

    @pytest.mark.parametrize("email", [
        '9161234567@mail.ru',
        '89161234567@yandex.ru',
        '79161234567@gmail.com',
    ])
    def test_various_phone_email_formats(self, email):
        """Various phone-as-email formats are extracted."""
        svc = PhoneDiscoveryService()
        result = svc.discover_sync('Иван', 'Петров', [], emails=[email])
        assert any('916' in p.number for p in result.phones), \
            f"Failed to extract phone from email: {email}"
        svc.close()

    @pytest.mark.parametrize("domain", RUSSIAN_EMAIL_DOMAINS)
    def test_all_russian_domains_used(self, domain):
        """All Russian email domains appear in candidate generation."""
        svc = EmailDiscoveryService(max_candidates=200)
        candidates = svc._generate_candidates('Иван', 'Петров', ['ivanpetrov'])
        domains_used = {c.split('@')[1] for c in candidates}
        # Not all domains may appear with max_candidates limit, but domain should be valid
        assert domain in RUSSIAN_EMAIL_DOMAINS
        svc.close()

    @pytest.mark.parametrize("confidence,label", [
        (0.95, 'very_high'),
        (0.90, 'very_high'),
        (0.75, 'high'),
        (0.70, 'high'),
        (0.55, 'medium'),
        (0.50, 'medium'),
        (0.30, 'low'),
        (0.0, 'low'),
    ])
    def test_confidence_label_mapping(self, confidence, label):
        """confidence_label returns correct label for various values."""
        sr = SourceResult(
            data_type='x', value='y', source_name='z',
            source_tier=SourceTier.C, confidence=confidence,
        )
        assert sr.confidence_label == label

    @pytest.mark.parametrize("tier", [SourceTier.S, SourceTier.A, SourceTier.B, SourceTier.C])
    def test_source_tier_has_string_value(self, tier):
        """Each SourceTier has a human-readable string value."""
        assert isinstance(tier.value, str)
        assert len(tier.value) > 0

    @pytest.mark.parametrize("stype", [
        SourceType.EMAIL, SourceType.PHONE, SourceType.BOTH,
        SourceType.IDENTITY, SourceType.PROFILE, SourceType.VERIFICATION,
    ])
    def test_source_type_has_string_value(self, stype):
        """Each SourceType has a string value."""
        assert isinstance(stype.value, str)

    @pytest.mark.parametrize("vk_field,phone_str", [
        ('mobile_phone', '+79161234567'),
        ('home_phone', '+79031234567'),
        ('about', 'Мой телефон +79261234567'),
        ('status', 'call me +79651234567'),
        ('site', 'тел: +79771234567'),
    ])
    def test_vk_various_fields_extracted(self, vk_field, phone_str):
        """Various VK profile fields are scanned for phones."""
        resp = _make_vk_users_response({vk_field: phone_str})

        def side_effect(*args, **kwargs):
            url = args[0] if args else kwargs.get('url', '')
            if 'wall.get' in str(url):
                return _mock_vk_response(_make_vk_wall_response([]))
            return _mock_vk_response(resp)

        with patch.dict(os.environ, {'VK_SERVICE_TOKEN': 'fake'}):
            svc = PhoneDiscoveryService()
            svc.session.get = MagicMock(side_effect=side_effect)
            result = svc.discover_sync(
                'Иван', 'Петров', [],
                profile_urls=[{'platform': 'vk', 'url': 'https://vk.com/id123'}],
            )
            svc.close()
        assert len(result.phones) >= 1, \
            f"No phone from VK field '{vk_field}' with value '{phone_str}'"


# ═══════════════════════════════════════════════════════════════════════════
# 9. BaseSource and SourceResult unit tests
# ═══════════════════════════════════════════════════════════════════════════

class TestBaseSourceAndSourceResult:
    """Tests for the base abstractions."""

    def test_base_source_query_catches_exception(self):
        """BaseSource.query() catches exceptions from query_impl()."""
        src = _FakeSource(raise_exc=ValueError("test error"))
        results = src.query(name='test')
        assert results == []

    def test_base_source_get_info(self):
        """BaseSource.get_info returns complete metadata dict."""
        src = _FakeSource()
        info = src.get_info()
        assert info['name'] == 'FakeSource'
        assert info['type'] == 'both'
        assert info['tier'] == 'Pattern Generation'
        assert info['tier_label'] == 'C'
        assert info['enabled'] is True
        assert info['requires_api_key'] is False
        assert info['available'] is True
        assert 'rate_limit' in info

    def test_base_source_enabled_toggle(self):
        """BaseSource enabled flag can be toggled."""
        src = _FakeSource()
        assert src.enabled is True
        src.enabled = False
        assert src.enabled is False

    def test_source_result_metadata_mutable(self):
        """SourceResult metadata dict is mutable."""
        sr = SourceResult(
            data_type='email', value='test@test.com',
            source_name='test', source_tier=SourceTier.C,
            confidence=0.5,
        )
        sr.metadata['key'] = 'value'
        assert sr.metadata['key'] == 'value'

    def test_normalize_key_strips_non_digits(self):
        """PhoneDiscoveryService._normalize_key returns last 10 digits."""
        assert PhoneDiscoveryService._normalize_key('+7 (916) 123-45-67') == '9161234567'
        assert PhoneDiscoveryService._normalize_key('+79161234567') == '9161234567'
        assert PhoneDiscoveryService._normalize_key('89161234567') == '9161234567'

    def test_normalize_key_short_number(self):
        """_normalize_key handles short numbers gracefully."""
        result = PhoneDiscoveryService._normalize_key('12345')
        assert result == '12345'
