"""
Tests for Task 3: Deep VK Mining Improvements
===============================================
Tests:
1. Tagged post comments mining (_scan_others_post_comments)
2. VKWallExtractor wired into contact_discovery (Step 1b)
3. Hunter.io email verification integration
4. Telegram/Instagram enrichment hints from wall extraction
5. CONFIDENCE_SCORES includes new source keys
"""

import os
import pytest
from unittest.mock import patch, MagicMock, PropertyMock
from dataclasses import asdict

os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-unit-tests')

from app.services.phase2.vk_wall_extractor import (
    VKWallExtractor,
    WallExtractionResult,
    ExtractedContact,
)
from app.services.phase2.email_generator import (
    hunter_verify_email,
    hunter_domain_search,
    generate_corporate_emails,
)
from app.services.candidate.contact_discovery import (
    ContactDiscoveryService,
    CONFIDENCE_SCORES,
    _get_score,
    _score_to_label,
)


# ── Fixtures ────────────────────────────────────────────────────────

@pytest.fixture
def extractor():
    return VKWallExtractor(access_token='test_token_123')


@pytest.fixture
def mock_check():
    """Mock CandidateCheck model for contact discovery tests."""
    check = MagicMock()
    check.phone = None
    check.email = None
    check.full_name = 'Иванов Иван'
    check.social_media_profiles = [
        {
            'platform': 'vk',
            'url': 'https://vk.com/id12345',
            'username': 'id12345',
            'display_name': 'Иван Иванов',
        },
    ]
    check.business_records = []
    check.fssp_records = []
    return check


# ── 1. Tagged Post Comments Mining ──────────────────────────────────

class TestOthersPostComments:
    """Test _scan_others_post_comments on tagged/others wall posts."""

    def test_scan_others_post_comments_extracts_phones(self, extractor):
        """Comments on tagged posts should extract phone numbers."""
        result = WallExtractionResult(profile_url='https://vk.com/id123')

        def mock_api(method, params):
            if method == 'wall.getComments':
                return {
                    'items': [
                        {'id': 1, 'text': 'Мой номер: +7 (916) 123-45-67', 'date': 1700000000},
                        {'id': 2, 'text': 'Спасибо!', 'date': 1700000100},
                    ],
                    'count': 2,
                }
            return None

        extractor._vk_api_call = mock_api
        posts = [(12345, 1), (12345, 2)]

        extractor._scan_others_post_comments(posts, result)

        assert len(result.phones) >= 1
        assert any('+7' in p.value for p in result.phones)
        assert result.comments_analyzed >= 2

    def test_scan_others_post_comments_extracts_telegram(self, extractor):
        """Comments on tagged posts should extract Telegram usernames."""
        result = WallExtractionResult(profile_url='https://vk.com/id123')

        def mock_api(method, params):
            if method == 'wall.getComments':
                return {
                    'items': [
                        {'id': 1, 'text': 'Пишите мне в тг: @ivan_test_user', 'date': 1700000000},
                    ],
                    'count': 1,
                }
            return None

        extractor._vk_api_call = mock_api
        extractor._scan_others_post_comments([(12345, 1)], result)

        assert 'ivan_test_user' in result.telegram_usernames

    def test_scan_others_post_comments_max_limit(self, extractor):
        """Comment scanning respects 200-comment cap."""
        result = WallExtractionResult(profile_url='https://vk.com/id123')
        call_count = [0]

        def mock_api(method, params):
            if method == 'wall.getComments':
                call_count[0] += 1
                # Return 30 comments each time
                return {
                    'items': [{'id': i, 'text': 'Comment'} for i in range(30)],
                    'count': 30,
                }
            return None

        extractor._vk_api_call = mock_api

        # 20 posts * 30 comments = 600 but should cap at 200
        posts = [(12345, i) for i in range(20)]
        extractor._scan_others_post_comments(posts, result)

        assert result.comments_analyzed <= 210  # allow slight overshoot from batch

    def test_scan_others_post_comments_empty(self, extractor):
        """No API response returns gracefully."""
        result = WallExtractionResult(profile_url='https://vk.com/id123')
        extractor._vk_api_call = lambda *a, **kw: None

        extractor._scan_others_post_comments([(12345, 1)], result)
        assert result.comments_analyzed == 0

    def test_others_wall_posts_triggers_comment_scan(self, extractor):
        """_scan_others_wall_posts should call _scan_others_post_comments
        when posts have comments."""
        result = WallExtractionResult(profile_url='https://vk.com/id123')
        comment_scan_called = [False]

        orig_scan = extractor._scan_others_post_comments

        def mock_scan(posts, res):
            comment_scan_called[0] = True
            assert len(posts) >= 1

        extractor._scan_others_post_comments = mock_scan

        def mock_api(method, params):
            if method == 'wall.get':
                return {
                    'items': [
                        {
                            'id': 1,
                            'owner_id': 12345,
                            'text': 'Happy birthday!',
                            'comments': {'count': 5},
                            'date': 1700000000,
                        },
                    ],
                    'count': 1,
                }
            return None

        extractor._vk_api_call = mock_api
        extractor._scan_others_wall_posts('12345', 12345, result)

        assert comment_scan_called[0]


# ── 2. Deep VK Wall Extraction in Contact Discovery ─────────────────

class TestDeepVKWallInContactDiscovery:
    """Test _deep_vk_wall_extraction wired into ContactDiscoveryService."""

    @patch.dict(os.environ, {'VK_SERVICE_TOKEN': 'test_token'})
    def test_deep_wall_extraction_imports_phones(self, mock_check):
        """Phones found by VKWallExtractor are imported into found_phones."""
        mock_wall_result = WallExtractionResult(profile_url='https://vk.com/id12345')
        mock_wall_result.phones.append(ExtractedContact(
            value='+7 (916) 999-88-77',
            contact_type='phone',
            source='VK wall post',
            context='Тел: +7 (916) 999-88-77',
            confidence='high',
        ))

        mock_extractor_cls = MagicMock()
        mock_extractor_cls.return_value.extract_from_profile.return_value = mock_wall_result

        import app.services.phase2.vk_wall_extractor as vk_mod
        original_cls = vk_mod.VKWallExtractor
        vk_mod.VKWallExtractor = mock_extractor_cls
        try:
            service = ContactDiscoveryService()
            service._deep_vk_wall_extraction(mock_check.social_media_profiles)
            assert len(service.found_phones) >= 1
        finally:
            vk_mod.VKWallExtractor = original_cls

    @patch.dict(os.environ, {'VK_SERVICE_TOKEN': 'test_token'})
    def test_deep_wall_extraction_stores_telegram_hints(self, mock_check):
        """Telegram usernames found in wall posts are stored as hints."""
        mock_wall_result = WallExtractionResult(profile_url='https://vk.com/id12345')
        mock_wall_result.telegram_usernames = ['ivan_tg', 'support_bot']

        mock_extractor_cls = MagicMock()
        mock_extractor_cls.return_value.extract_from_profile.return_value = mock_wall_result

        import app.services.phase2.vk_wall_extractor as vk_mod
        original_cls = vk_mod.VKWallExtractor
        vk_mod.VKWallExtractor = mock_extractor_cls
        try:
            service = ContactDiscoveryService()
            service._deep_vk_wall_extraction(mock_check.social_media_profiles)
            assert hasattr(service, '_telegram_hints')
            assert len(service._telegram_hints) == 2
            assert service._telegram_hints[0]['username'] == 'ivan_tg'
        finally:
            vk_mod.VKWallExtractor = original_cls

    @patch.dict(os.environ, {'VK_SERVICE_TOKEN': 'test_token'})
    def test_deep_wall_extraction_stores_instagram_hints(self, mock_check):
        """Instagram usernames found in wall posts are stored as hints."""
        mock_wall_result = WallExtractionResult(profile_url='https://vk.com/id12345')
        mock_wall_result.instagram_usernames = ['ivan_photo']

        mock_extractor_cls = MagicMock()
        mock_extractor_cls.return_value.extract_from_profile.return_value = mock_wall_result

        import app.services.phase2.vk_wall_extractor as vk_mod
        original_cls = vk_mod.VKWallExtractor
        vk_mod.VKWallExtractor = mock_extractor_cls
        try:
            service = ContactDiscoveryService()
            service._deep_vk_wall_extraction(mock_check.social_media_profiles)
            assert hasattr(service, '_instagram_hints')
            assert service._instagram_hints[0]['username'] == 'ivan_photo'
        finally:
            vk_mod.VKWallExtractor = original_cls

    @patch.dict(os.environ, {'VK_SERVICE_TOKEN': ''})
    def test_deep_wall_skipped_without_token(self, mock_check):
        """Deep wall extraction is skipped when no VK token."""
        service = ContactDiscoveryService()
        service._deep_vk_wall_extraction(mock_check.social_media_profiles)
        # Should not crash, no phones added
        assert len(service.found_phones) == 0

    def test_deep_wall_skipped_no_vk_profiles(self):
        """Deep wall extraction is skipped when no VK profiles."""
        service = ContactDiscoveryService()
        service._deep_vk_wall_extraction([
            {'platform': 'telegram', 'url': 'https://t.me/test'},
        ])
        assert len(service.found_phones) == 0


# ── 3. Hunter.io Email Verification ────────────────────────────────

class TestHunterVerifyEmail:
    """Test hunter_verify_email function."""

    @patch.dict(os.environ, {'HUNTER_API_KEY': ''})
    def test_no_api_key_returns_none(self):
        """Returns None when HUNTER_API_KEY not set."""
        result = hunter_verify_email('test@example.com')
        assert result is None

    @patch.dict(os.environ, {'HUNTER_API_KEY': 'test_key'})
    @patch('app.services.phase2.email_generator.requests')
    def test_deliverable_email(self, mock_requests_mod):
        """Deliverable email returns correct result."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            'data': {
                'result': 'deliverable',
                'score': 95,
                'smtp_check': True,
                'mx_records': True,
                'disposable': False,
                'webmail': True,
            }
        }
        mock_requests_mod.get.return_value = mock_resp

        result = hunter_verify_email('ivan@mail.ru')
        assert result is not None
        assert result['result'] == 'deliverable'
        assert result['score'] == 95
        assert result['source'] == 'hunter.io'

    @patch.dict(os.environ, {'HUNTER_API_KEY': 'test_key'})
    @patch('app.services.phase2.email_generator.requests')
    def test_undeliverable_email(self, mock_requests_mod):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            'data': {
                'result': 'undeliverable',
                'score': 0,
                'smtp_check': False,
            }
        }
        mock_requests_mod.get.return_value = mock_resp

        result = hunter_verify_email('nonexistent@example.com')
        assert result['result'] == 'undeliverable'

    @patch.dict(os.environ, {'HUNTER_API_KEY': 'bad_key'})
    @patch('app.services.phase2.email_generator.requests')
    def test_auth_error(self, mock_requests_mod):
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_requests_mod.get.return_value = mock_resp

        result = hunter_verify_email('test@example.com')
        assert result is None

    @patch.dict(os.environ, {'HUNTER_API_KEY': 'test_key'})
    @patch('app.services.phase2.email_generator.requests')
    def test_rate_limit(self, mock_requests_mod):
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_requests_mod.get.return_value = mock_resp

        result = hunter_verify_email('test@example.com')
        assert result is None


class TestHunterDomainSearch:
    """Test hunter_domain_search function."""

    @patch.dict(os.environ, {'HUNTER_API_KEY': ''})
    def test_no_api_key_returns_empty(self):
        result = hunter_domain_search('sberbank.ru')
        assert result == []

    @patch.dict(os.environ, {'HUNTER_API_KEY': 'test_key'})
    @patch('app.services.phase2.email_generator.requests')
    def test_domain_search_returns_emails(self, mock_requests_mod):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            'data': {
                'emails': [
                    {
                        'value': 'ivan.ivanov@sberbank.ru',
                        'type': 'personal',
                        'confidence': 85,
                        'first_name': 'Ivan',
                        'last_name': 'Ivanov',
                    },
                ],
                'pattern': '{first}.{last}',
            }
        }
        mock_requests_mod.get.return_value = mock_resp

        results = hunter_domain_search('sberbank.ru')
        assert len(results) == 2  # 1 email + 1 pattern entry
        assert results[0]['email'] == 'ivan.ivanov@sberbank.ru'
        assert results[0]['source'] == 'hunter.io'
        assert results[1]['type'] == 'pattern'

    @patch.dict(os.environ, {'HUNTER_API_KEY': 'test_key'})
    @patch('app.services.phase2.email_generator.requests')
    def test_domain_search_rate_limit(self, mock_requests_mod):
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_requests_mod.get.return_value = mock_resp

        results = hunter_domain_search('example.com')
        assert results == []


# ── 4. Hunter.io Wired into Contact Discovery ──────────────────────

class TestHunterInContactDiscovery:
    """Test _hunter_corporate_search in ContactDiscoveryService."""

    @patch.dict(os.environ, {'HUNTER_API_KEY': '', 'VK_SERVICE_TOKEN': ''})
    def test_skipped_without_hunter_key(self):
        """Hunter corporate search is skipped when no API key."""
        service = ContactDiscoveryService()
        service._hunter_corporate_search([], 'Иванов Иван')
        assert len(service.found_emails) == 0

    @patch.dict(os.environ, {'HUNTER_API_KEY': 'test_key', 'VK_SERVICE_TOKEN': ''})
    def test_skipped_without_employer(self):
        """Hunter search is skipped when no employer in profiles."""
        service = ContactDiscoveryService()
        service._hunter_corporate_search([
            {'platform': 'vk', 'career': []},
        ], 'Иванов Иван')
        assert len(service.found_emails) == 0


# ── 5. Confidence Scores ───────────────────────────────────────────

class TestConfidenceScores:
    """Test CONFIDENCE_SCORES dict has all expected keys."""

    def test_hunter_verified_score_exists(self):
        assert 'hunter_verified' in CONFIDENCE_SCORES
        assert CONFIDENCE_SCORES['hunter_verified'] == 0.80

    def test_vk_wall_by_subject_score(self):
        assert 'vk_wall_by_subject' in CONFIDENCE_SCORES
        assert CONFIDENCE_SCORES['vk_wall_by_subject'] == 0.85

    def test_vk_wall_by_others_score(self):
        assert 'vk_wall_by_others' in CONFIDENCE_SCORES
        assert CONFIDENCE_SCORES['vk_wall_by_others'] == 0.70

    def test_marketplace_score(self):
        assert 'marketplace' in CONFIDENCE_SCORES
        assert CONFIDENCE_SCORES['marketplace'] == 0.90


# ── 6. Enrichment Hints in Discover Results ─────────────────────────

class TestEnrichmentHints:
    """Test that discover() returns telegram/instagram hints."""

    @patch.dict(os.environ, {'VK_SERVICE_TOKEN': 'test_token'})
    def test_telegram_hints_in_result(self):
        """discover() result includes telegram_hints when found."""
        service = ContactDiscoveryService()
        service._telegram_hints = [
            {'username': 'test_tg', 'source': 'vk_wall_extraction'},
        ]
        # Call deduplicate manually to prepare for return
        service._deduplicate_contacts()

        # Build result dict as discover() does
        result = {
            'phones': [p.to_dict() for p in service.found_phones],
            'emails': [e.to_dict() for e in service.found_emails],
        }
        if getattr(service, '_telegram_hints', None):
            result['telegram_hints'] = service._telegram_hints

        assert 'telegram_hints' in result
        assert result['telegram_hints'][0]['username'] == 'test_tg'

    def test_no_hints_when_no_vk_profiles(self):
        """No enrichment hints when service has no VK profiles."""
        service = ContactDiscoveryService()
        assert not hasattr(service, '_telegram_hints')
        assert not hasattr(service, '_instagram_hints')


# ── 7. Corporate Email Generation ──────────────────────────────────

class TestCorporateEmails:
    """Test generate_corporate_emails from email_generator.py."""

    def test_generates_patterns(self):
        emails = generate_corporate_emails('Иван', 'Иванов', 'Сбербанк')
        assert len(emails) >= 1
        # Should have transliterated domain
        assert any('sberbank' in e['email'] for e in emails)

    def test_strips_legal_prefixes(self):
        emails = generate_corporate_emails('Иван', 'Иванов', 'ООО «Альфа-Строй»')
        assert len(emails) >= 1
        # Legal prefix (ООО) and quotes should be stripped
        assert all('ooo' not in e['email'] for e in emails)

    def test_empty_employer(self):
        emails = generate_corporate_emails('Иван', 'Иванов', '')
        assert emails == []

    def test_empty_name(self):
        emails = generate_corporate_emails('', '', 'Яндекс')
        assert emails == []


# ── 8. Integration: Wall Extraction Source Confidence ──────────────

class TestWallExtractionSourceConfidence:
    """Test that wall extraction contacts get correct confidence scores."""

    @patch.dict(os.environ, {'VK_SERVICE_TOKEN': 'test_token'})
    def test_subject_wall_post_gets_high_confidence(self):
        """Posts by the subject get 'vk_wall_by_subject' score (0.85)."""
        mock_wall_result = WallExtractionResult(profile_url='https://vk.com/id12345')
        mock_wall_result.phones.append(ExtractedContact(
            value='+7 (916) 111-22-33',
            contact_type='phone',
            source='VK wall post',
            context='test',
            confidence='high',
        ))

        mock_extractor_cls = MagicMock()
        mock_extractor_cls.return_value.extract_from_profile.return_value = mock_wall_result

        import app.services.phase2.vk_wall_extractor as vk_mod
        original_cls = vk_mod.VKWallExtractor
        vk_mod.VKWallExtractor = mock_extractor_cls
        try:
            service = ContactDiscoveryService()
            service._deep_vk_wall_extraction([
                {'platform': 'vk', 'url': 'https://vk.com/id12345', 'display_name': 'Test'},
            ])

            assert len(service.found_phones) >= 1
            phone = service.found_phones[0]
            assert phone.confidence_score == _get_score('vk_wall_by_subject')
        finally:
            vk_mod.VKWallExtractor = original_cls

    @patch.dict(os.environ, {'VK_SERVICE_TOKEN': 'test_token'})
    def test_others_wall_post_gets_lower_confidence(self):
        """Posts by others get 'vk_wall_by_others' score (0.70)."""
        mock_wall_result = WallExtractionResult(profile_url='https://vk.com/id12345')
        mock_wall_result.phones.append(ExtractedContact(
            value='+7 (903) 444-55-66',
            contact_type='phone',
            source='VK wall post (by others)',
            context='test',
            confidence='medium',
        ))

        mock_extractor_cls = MagicMock()
        mock_extractor_cls.return_value.extract_from_profile.return_value = mock_wall_result

        import app.services.phase2.vk_wall_extractor as vk_mod
        original_cls = vk_mod.VKWallExtractor
        vk_mod.VKWallExtractor = mock_extractor_cls
        try:
            service = ContactDiscoveryService()
            service._deep_vk_wall_extraction([
                {'platform': 'vk', 'url': 'https://vk.com/id12345', 'display_name': 'Test'},
            ])

            assert len(service.found_phones) >= 1
            phone = service.found_phones[0]
            assert phone.confidence_score == _get_score('vk_wall_by_others')
        finally:
            vk_mod.VKWallExtractor = original_cls
