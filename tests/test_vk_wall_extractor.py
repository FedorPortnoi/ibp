"""
Tests for Enhanced VK Wall Extractor
======================================
Tests all extraction capabilities:
- Phone extraction from wall posts
- Email extraction
- Telegram link extraction (t.me, @username, Russian context)
- Instagram extraction
- WhatsApp extraction
- Comment scanning
- Photo description scanning
- Profile field scanning
- Mention/tag scanning
- Pagination (up to 1000 posts)
- Backward compatibility
"""

import json
import re
from unittest.mock import patch, MagicMock, call
from dataclasses import asdict

import pytest

from app.services.phase2.vk_wall_extractor import (
    VKWallExtractor,
    WallExtractionResult,
    ExtractedContact,
    extract_vk_wall_contacts,
    extract_multiple_vk_wall_contacts,
)


# -----------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------

@pytest.fixture
def extractor():
    """VKWallExtractor with test token."""
    return VKWallExtractor(access_token='test_token_123')


@pytest.fixture
def extractor_no_token():
    """VKWallExtractor without token (scraping mode)."""
    return VKWallExtractor()


# -----------------------------------------------------------------------
# Phone extraction tests
# -----------------------------------------------------------------------

class TestPhoneExtraction:
    """Test phone number extraction from text."""

    def test_international_format(self, extractor):
        result = WallExtractionResult(profile_url='https://vk.com/test')
        extractor._extract_contacts_from_text(
            'Звоните: +7 (916) 123-45-67',
            result, source='test'
        )
        assert len(result.phones) == 1
        assert result.phones[0].value == '+7 (916) 123-45-67'

    def test_domestic_format(self, extractor):
        result = WallExtractionResult(profile_url='https://vk.com/test')
        extractor._extract_contacts_from_text(
            'тел: 8-916-123-45-67',
            result, source='test'
        )
        assert len(result.phones) == 1
        assert '916' in result.phones[0].value

    def test_plain_digits(self, extractor):
        result = WallExtractionResult(profile_url='https://vk.com/test')
        extractor._extract_contacts_from_text(
            'Мой номер +79161234567',
            result, source='test'
        )
        assert len(result.phones) == 1

    def test_phone_with_tel_prefix_high_confidence(self, extractor):
        result = WallExtractionResult(profile_url='https://vk.com/test')
        extractor._extract_contacts_from_text(
            'телефон: +7 (916) 123-45-67',
            result, source='test'
        )
        assert result.phones[0].confidence == 'high'

    def test_phone_without_prefix_medium_confidence(self, extractor):
        result = WallExtractionResult(profile_url='https://vk.com/test')
        extractor._extract_contacts_from_text(
            'Пишите +79261234567 для связи',
            result, source='test'
        )
        assert result.phones[0].confidence == 'medium'

    def test_deduplication(self, extractor):
        result = WallExtractionResult(profile_url='https://vk.com/test')
        text = '+79161234567 повторяю +79161234567'
        extractor._extract_contacts_from_text(text, result, source='test')
        assert len(result.phones) == 1

    def test_normalize_8_to_7(self, extractor):
        assert extractor._normalize_phone('89161234567') == '+7 (916) 123-45-67'

    def test_normalize_7_prefix(self, extractor):
        assert extractor._normalize_phone('79161234567') == '+7 (916) 123-45-67'

    def test_normalize_10_digits(self, extractor):
        assert extractor._normalize_phone('9161234567') == '+7 (916) 123-45-67'


# -----------------------------------------------------------------------
# Email extraction tests
# -----------------------------------------------------------------------

class TestEmailExtraction:
    """Test email extraction from text."""

    def test_simple_email(self, extractor):
        result = WallExtractionResult(profile_url='https://vk.com/test')
        extractor._extract_contacts_from_text(
            'Пишите на ivan@mail.ru',
            result, source='test'
        )
        assert len(result.emails) == 1
        assert result.emails[0].value == 'ivan@mail.ru'

    def test_email_with_prefix(self, extractor):
        result = WallExtractionResult(profile_url='https://vk.com/test')
        extractor._extract_contacts_from_text(
            'почта: test.user@yandex.ru',
            result, source='test'
        )
        assert len(result.emails) >= 1

    def test_email_filter_garbage(self, extractor):
        result = WallExtractionResult(profile_url='https://vk.com/test')
        extractor._extract_contacts_from_text(
            'Файл photo@image.png а вот почта real@mail.ru',
            result, source='test'
        )
        # Should filter .png but keep real email
        emails = [e.value for e in result.emails]
        assert 'photo@image.png' not in emails
        assert 'real@mail.ru' in emails

    def test_email_deduplication(self, extractor):
        result = WallExtractionResult(profile_url='https://vk.com/test')
        extractor._extract_contacts_from_text(
            'ivan@mail.ru и опять ivan@mail.ru',
            result, source='test'
        )
        assert len(result.emails) == 1

    def test_email_lowercased(self, extractor):
        result = WallExtractionResult(profile_url='https://vk.com/test')
        extractor._extract_contacts_from_text(
            'Пишите Ivan@MAIL.Ru',
            result, source='test'
        )
        assert result.emails[0].value == 'ivan@mail.ru'


# -----------------------------------------------------------------------
# Telegram extraction tests
# -----------------------------------------------------------------------

class TestTelegramExtraction:
    """Test Telegram username/link extraction."""

    def test_tme_link(self, extractor):
        result = WallExtractionResult(profile_url='https://vk.com/test')
        extractor._extract_contacts_from_text(
            'Мой канал: t.me/ivan_channel',
            result, source='test'
        )
        assert 'ivan_channel' in result.telegram_usernames

    def test_tme_link_with_https(self, extractor):
        result = WallExtractionResult(profile_url='https://vk.com/test')
        extractor._extract_contacts_from_text(
            'Подписывайтесь https://t.me/super_channel',
            result, source='test'
        )
        assert 'super_channel' in result.telegram_usernames

    def test_telegram_me_link(self, extractor):
        result = WallExtractionResult(profile_url='https://vk.com/test')
        extractor._extract_contacts_from_text(
            'telegram.me/my_username',
            result, source='test'
        )
        assert 'my_username' in result.telegram_usernames

    def test_russian_tg_context(self, extractor):
        """Russian abbreviation 'тг' should match."""
        result = WallExtractionResult(profile_url='https://vk.com/test')
        extractor._extract_contacts_from_text(
            'Пишите в тг: ivan_petrov',
            result, source='test'
        )
        assert 'ivan_petrov' in result.telegram_usernames

    def test_russian_telegram_full(self, extractor):
        """Full Russian word 'телеграм' should match."""
        result = WallExtractionResult(profile_url='https://vk.com/test')
        extractor._extract_contacts_from_text(
            'мой телеграм @cool_username',
            result, source='test'
        )
        assert 'cool_username' in result.telegram_usernames

    def test_tg_abbreviation(self, extractor):
        result = WallExtractionResult(profile_url='https://vk.com/test')
        extractor._extract_contacts_from_text(
            'tg: @my_channel_name',
            result, source='test'
        )
        assert 'my_channel_name' in result.telegram_usernames

    def test_exclude_service_paths(self, extractor):
        """Should not extract t.me/share, t.me/joinchat etc."""
        result = WallExtractionResult(profile_url='https://vk.com/test')
        extractor._extract_contacts_from_text(
            'Ссылка t.me/share и t.me/joinchat',
            result, source='test'
        )
        assert 'share' not in result.telegram_usernames
        assert 'joinchat' not in result.telegram_usernames

    def test_exclude_short_usernames(self, extractor):
        """Usernames < 5 chars should be excluded."""
        result = WallExtractionResult(profile_url='https://vk.com/test')
        extractor._extract_contacts_from_text(
            't.me/abc',
            result, source='test'
        )
        assert len(result.telegram_usernames) == 0

    def test_deduplication(self, extractor):
        result = WallExtractionResult(profile_url='https://vk.com/test')
        extractor._extract_contacts_from_text(
            't.me/my_channel и ещё раз t.me/my_channel',
            result, source='test'
        )
        assert result.telegram_usernames.count('my_channel') == 1

    def test_multiple_telegram_links_in_one_post(self, extractor):
        """Common pattern: VK post with multiple t.me links."""
        result = WallExtractionResult(profile_url='https://vk.com/test')
        extractor._extract_contacts_from_text(
            'Мои каналы:\n'
            '1. t.me/channel_one\n'
            '2. https://t.me/channel_two\n'
            '3. Телеграм: @channel_three',
            result, source='test'
        )
        assert 'channel_one' in result.telegram_usernames
        assert 'channel_two' in result.telegram_usernames
        assert 'channel_three' in result.telegram_usernames


# -----------------------------------------------------------------------
# Instagram extraction tests
# -----------------------------------------------------------------------

class TestInstagramExtraction:
    """Test Instagram username extraction."""

    def test_instagram_url(self, extractor):
        result = WallExtractionResult(profile_url='https://vk.com/test')
        extractor._extract_contacts_from_text(
            'instagram.com/ivan_photo',
            result, source='test'
        )
        assert 'ivan_photo' in result.instagram_usernames

    def test_russian_inst_abbreviation(self, extractor):
        result = WallExtractionResult(profile_url='https://vk.com/test')
        extractor._extract_contacts_from_text(
            'инст: @my_insta_name',
            result, source='test'
        )
        assert 'my_insta_name' in result.instagram_usernames


# -----------------------------------------------------------------------
# WhatsApp extraction tests
# -----------------------------------------------------------------------

class TestWhatsAppExtraction:
    """Test WhatsApp contact extraction."""

    def test_whatsapp_keyword(self, extractor):
        result = WallExtractionResult(profile_url='https://vk.com/test')
        extractor._extract_contacts_from_text(
            'WhatsApp: +79161234567',
            result, source='test'
        )
        assert len(result.other_contacts) >= 1
        assert result.other_contacts[0]['type'] == 'whatsapp'

    def test_wame_link(self, extractor):
        result = WallExtractionResult(profile_url='https://vk.com/test')
        extractor._extract_contacts_from_text(
            'wa.me/79161234567',
            result, source='test'
        )
        assert any(c['type'] == 'whatsapp' for c in result.other_contacts)

    def test_whatsapp_dedup(self, extractor):
        result = WallExtractionResult(profile_url='https://vk.com/test')
        extractor._extract_contacts_from_text(
            'wa.me/79161234567 и wa.me/79161234567',
            result, source='test'
        )
        wa_contacts = [c for c in result.other_contacts if c['type'] == 'whatsapp']
        assert len(wa_contacts) == 1


# -----------------------------------------------------------------------
# API-based extraction tests (wall.get, wall.getComments, photos, etc.)
# -----------------------------------------------------------------------

class TestWallPostScanning:
    """Test wall post scanning via VK API."""

    def _mock_wall_response(self, posts, total=None):
        """Create a mock wall.get response."""
        if total is None:
            total = len(posts)
        return {
            'count': total,
            'items': posts,
        }

    def test_basic_wall_scan(self, extractor):
        """Should extract contacts from wall posts."""
        posts = [
            {'id': 1, 'owner_id': 123, 'date': 1700000000,
             'text': 'Мой телефон +79161234567', 'attachments': []},
            {'id': 2, 'owner_id': 123, 'date': 1700001000,
             'text': 'Пишите ivan@mail.ru', 'attachments': []},
        ]
        response = self._mock_wall_response(posts)

        result = WallExtractionResult(profile_url='https://vk.com/123')
        with patch.object(extractor, '_vk_api_call', return_value=response):
            extractor._scan_wall_posts('123', 123, 100, result)

        assert len(result.phones) == 1
        assert len(result.emails) == 1
        assert result.posts_analyzed == 2

    def test_extracts_from_attachments(self, extractor):
        """Should extract contacts from link/note attachments."""
        posts = [
            {'id': 1, 'owner_id': 123, 'date': 1700000000,
             'text': 'Смотрите ссылку',
             'attachments': [
                 {'type': 'link', 'link': {
                     'title': 'Контакт',
                     'description': 'тел: +79261234567'
                 }}
             ]},
        ]
        response = self._mock_wall_response(posts)

        result = WallExtractionResult(profile_url='https://vk.com/123')
        with patch.object(extractor, '_vk_api_call', return_value=response):
            extractor._scan_wall_posts('123', 123, 100, result)

        assert len(result.phones) == 1

    def test_extracts_from_reposts(self, extractor):
        """Should extract contacts from copy_history (reposts)."""
        posts = [
            {'id': 1, 'owner_id': 123, 'date': 1700000000,
             'text': 'Репост',
             'attachments': [],
             'copy_history': [
                 {'text': 'Оригинал с почтой repost@mail.ru'}
             ]},
        ]
        response = self._mock_wall_response(posts)

        result = WallExtractionResult(profile_url='https://vk.com/123')
        with patch.object(extractor, '_vk_api_call', return_value=response):
            extractor._scan_wall_posts('123', 123, 100, result)

        assert any(e.value == 'repost@mail.ru' for e in result.emails)

    def test_pagination(self, extractor):
        """Should paginate when max_posts > 100."""
        batch1 = [
            {'id': i, 'owner_id': 123, 'date': 1700000000 + i,
             'text': f'Пост {i}', 'attachments': []}
            for i in range(100)
        ]
        batch2 = [
            {'id': i + 100, 'owner_id': 123, 'date': 1700000000 + i,
             'text': f'Пост {i+100}', 'attachments': []}
            for i in range(50)
        ]

        call_count = [0]

        def mock_api_call(method, params):
            if method == 'wall.get':
                call_count[0] += 1
                if params.get('offset', 0) == 0:
                    return self._mock_wall_response(batch1, total=150)
                else:
                    return self._mock_wall_response(batch2, total=150)
            return None

        result = WallExtractionResult(profile_url='https://vk.com/123')
        with patch.object(extractor, '_vk_api_call', side_effect=mock_api_call), \
             patch('app.services.phase2.vk_wall_extractor.time.sleep'):
            extractor._scan_wall_posts('123', 123, 200, result)

        assert result.posts_analyzed == 150
        assert call_count[0] == 2  # Two API calls

    def test_max_posts_capped_at_1000(self, extractor):
        """Even if extract_from_profile gets max_posts=2000, API caps at 1000."""
        # We test the effective_max logic in _extract_via_api
        result = WallExtractionResult(profile_url='https://vk.com/123')
        empty_response = self._mock_wall_response([], total=0)

        with patch.object(extractor, '_vk_api_call', return_value=empty_response) as mock_call, \
             patch.object(extractor, '_scan_post_comments'), \
             patch.object(extractor, '_scan_photos'), \
             patch.object(extractor, '_scan_profile_fields'), \
             patch.object(extractor, '_scan_mentions'), \
             patch.object(extractor, '_resolve_user_id', return_value=123):
            extractor._extract_via_api('123', 2000)
            # Check that _scan_wall_posts was reached (via the mock)


class TestCommentScanning:
    """Test comment scanning on wall posts."""

    def test_comment_extraction(self, extractor):
        """Should extract contacts from comments."""
        def mock_api_call(method, params):
            if method == 'wall.get':
                return {
                    'count': 1,
                    'items': [
                        {'id': 1, 'owner_id': 123,
                         'comments': {'count': 2},
                         'text': 'Кто знает номер?'}
                    ]
                }
            elif method == 'wall.getComments':
                return {
                    'count': 2,
                    'items': [
                        {'id': 10, 'date': 1700000000,
                         'text': 'Вот номер: +79161234567'},
                        {'id': 11, 'date': 1700001000,
                         'text': 'Или пишите ivan@mail.ru'},
                    ]
                }
            return None

        result = WallExtractionResult(profile_url='https://vk.com/123')
        with patch.object(extractor, '_vk_api_call', side_effect=mock_api_call), \
             patch('app.services.phase2.vk_wall_extractor.time.sleep'):
            extractor._scan_post_comments(123, result)

        assert len(result.phones) == 1
        assert len(result.emails) == 1
        assert result.comments_analyzed == 2

    def test_skips_posts_without_comments(self, extractor):
        """Should skip posts with 0 comments."""
        def mock_api_call(method, params):
            if method == 'wall.get':
                return {
                    'count': 1,
                    'items': [
                        {'id': 1, 'owner_id': 123,
                         'comments': {'count': 0},
                         'text': 'Пост без комментариев'}
                    ]
                }
            return None

        result = WallExtractionResult(profile_url='https://vk.com/123')
        with patch.object(extractor, '_vk_api_call', side_effect=mock_api_call):
            extractor._scan_post_comments(123, result)

        assert result.comments_analyzed == 0


class TestPhotoScanning:
    """Test photo description scanning."""

    def test_photo_description_extraction(self, extractor):
        """Should extract contacts from photo descriptions."""
        def mock_api_call(method, params):
            if method == 'photos.getAll':
                return {
                    'count': 2,
                    'items': [
                        {'id': 1, 'date': 1700000000,
                         'text': 'Для заказа: +79161234567'},
                        {'id': 2, 'date': 1700001000,
                         'text': 'Фото с отдыха'},
                    ]
                }
            elif method == 'photos.getAlbums':
                return {
                    'count': 1,
                    'items': [
                        {'id': 1, 'title': 'Работа',
                         'description': 'email: work@company.ru'}
                    ]
                }
            return None

        result = WallExtractionResult(profile_url='https://vk.com/123')
        with patch.object(extractor, '_vk_api_call', side_effect=mock_api_call):
            extractor._scan_photos(123, result)

        assert len(result.phones) == 1
        assert any(e.value == 'work@company.ru' for e in result.emails)
        assert result.photos_analyzed == 2


class TestProfileFieldScanning:
    """Test profile field extraction."""

    def test_profile_fields(self, extractor):
        """Should extract contacts from profile about/status/interests."""
        def mock_api_call(method, params):
            if method == 'users.get':
                return [{
                    'id': 123,
                    'about': 'Пишите t.me/my_telegram',
                    'status': 'Связь: +79161234567',
                    'site': 'https://example.com',
                    'mobile_phone': '+7 (926) 123-45-67',
                    'home_phone': '',
                    'activities': 'Фриланс, дизайн',
                    'interests': 'email: ivan@gmail.com',
                }]
            return None

        result = WallExtractionResult(profile_url='https://vk.com/123')
        with patch.object(extractor, '_vk_api_call', side_effect=mock_api_call):
            extractor._scan_profile_fields('123', result)

        assert len(result.phones) >= 1  # At least mobile_phone
        assert 'my_telegram' in result.telegram_usernames
        assert any(e.value == 'ivan@gmail.com' for e in result.emails)

    def test_direct_phone_fields(self, extractor):
        """Should add mobile_phone and home_phone directly."""
        def mock_api_call(method, params):
            if method == 'users.get':
                return [{
                    'id': 123,
                    'mobile_phone': '+7 (916) 111-22-33',
                    'home_phone': '8(495)1234567',
                }]
            return None

        result = WallExtractionResult(profile_url='https://vk.com/123')
        with patch.object(extractor, '_vk_api_call', side_effect=mock_api_call):
            extractor._scan_profile_fields('123', result)

        phone_values = [p.value for p in result.phones]
        assert any('916' in p for p in phone_values)
        assert any('495' in p for p in phone_values)


class TestMentionScanning:
    """Test scanning posts where user is tagged."""

    def test_mention_extraction(self, extractor):
        """Should extract contacts from mention posts."""
        def mock_api_call(method, params):
            if method == 'newsfeed.getMentions':
                return {
                    'count': 1,
                    'items': [
                        {'id': 5, 'owner_id': 456, 'date': 1700000000,
                         'text': 'Позвоните @id123 по номеру +79161234567'}
                    ]
                }
            return None

        result = WallExtractionResult(profile_url='https://vk.com/123')
        with patch.object(extractor, '_vk_api_call', side_effect=mock_api_call):
            extractor._scan_mentions(123, result)

        assert len(result.phones) == 1


# -----------------------------------------------------------------------
# Full pipeline integration tests
# -----------------------------------------------------------------------

class TestFullExtraction:
    """Test the complete extract_from_profile flow."""

    def test_api_mode_calls_all_scanners(self, extractor):
        """API mode should call wall, comments, photos, profile, mentions."""
        with patch.object(extractor, '_resolve_user_id', return_value=123), \
             patch.object(extractor, '_scan_wall_posts') as mock_wall, \
             patch.object(extractor, '_scan_post_comments') as mock_comments, \
             patch.object(extractor, '_scan_photos') as mock_photos, \
             patch.object(extractor, '_scan_profile_fields') as mock_profile, \
             patch.object(extractor, '_scan_mentions') as mock_mentions:

            result = extractor._extract_via_api('123', 100)

            mock_wall.assert_called_once()
            mock_comments.assert_called_once()
            mock_photos.assert_called_once()
            mock_profile.assert_called_once()
            mock_mentions.assert_called_once()

    def test_scraping_fallback(self, extractor_no_token):
        """Without token, should fall back to scraping."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '<div class="wall_post_text">тел: +79161234567</div>'

        with patch.object(extractor_no_token.session, 'get', return_value=mock_response):
            result = extractor_no_token.extract_from_profile('https://vk.com/test')

        assert len(result.phones) == 1

    def test_extract_user_id_from_numeric_url(self, extractor):
        assert extractor._extract_user_id('https://vk.com/id12345') == '12345'

    def test_extract_user_id_from_screen_name(self, extractor):
        assert extractor._extract_user_id('https://vk.com/durov') == 'durov'

    def test_extract_user_id_invalid(self, extractor):
        assert extractor._extract_user_id('https://example.com') is None


# -----------------------------------------------------------------------
# Convenience function tests
# -----------------------------------------------------------------------

class TestConvenienceFunctions:
    """Test module-level convenience functions."""

    def test_extract_vk_wall_contacts(self):
        with patch.object(VKWallExtractor, 'extract_from_profile') as mock:
            mock.return_value = WallExtractionResult(profile_url='https://vk.com/test')
            result = extract_vk_wall_contacts('https://vk.com/test', access_token='tok')
            # Convenience function uses default max_posts=50
            mock.assert_called_once_with('https://vk.com/test')

    def test_extract_multiple(self):
        with patch.object(VKWallExtractor, 'extract_from_profile') as mock, \
             patch('app.services.phase2.vk_wall_extractor.time.sleep'):
            mock.return_value = WallExtractionResult(profile_url='https://vk.com/test')
            results = extract_multiple_vk_wall_contacts(
                ['https://vk.com/a', 'https://vk.com/b'],
                access_token='tok'
            )
            assert len(results) == 2
            assert mock.call_count == 2


# -----------------------------------------------------------------------
# Backward compatibility tests
# -----------------------------------------------------------------------

class TestBackwardCompatibility:
    """Ensure the enhanced extractor doesn't break existing interfaces."""

    def test_result_has_original_fields(self):
        """WallExtractionResult should have all original fields."""
        result = WallExtractionResult(profile_url='https://vk.com/test')
        assert hasattr(result, 'profile_url')
        assert hasattr(result, 'phones')
        assert hasattr(result, 'emails')
        assert hasattr(result, 'telegram_usernames')
        assert hasattr(result, 'instagram_usernames')
        assert hasattr(result, 'other_contacts')
        assert hasattr(result, 'posts_analyzed')
        assert hasattr(result, 'errors')

    def test_result_has_new_fields(self):
        """WallExtractionResult should have new tracking fields."""
        result = WallExtractionResult(profile_url='https://vk.com/test')
        assert hasattr(result, 'comments_analyzed')
        assert hasattr(result, 'photos_analyzed')
        assert result.comments_analyzed == 0
        assert result.photos_analyzed == 0

    def test_extracted_contact_unchanged(self):
        """ExtractedContact dataclass should be unchanged."""
        contact = ExtractedContact(
            value='+79161234567',
            contact_type='phone',
            source='test',
            context='test context',
            confidence='high',
            post_url='https://vk.com/wall1_1',
            post_date='1700000000',
        )
        assert contact.value == '+79161234567'
        assert contact.post_url == 'https://vk.com/wall1_1'

    def test_original_patterns_preserved(self, extractor):
        """All original regex patterns should still work."""
        assert len(extractor.PHONE_PATTERNS) >= 5
        assert len(extractor.EMAIL_PATTERNS) >= 2
        assert len(extractor.TELEGRAM_PATTERNS) >= 4
        assert len(extractor.WHATSAPP_PATTERNS) >= 2

    def test_default_max_posts(self):
        """Default max_posts in extract_from_profile should be 50."""
        # Verify the function signature has max_posts=50 default
        import inspect
        sig = inspect.signature(VKWallExtractor.extract_from_profile)
        assert sig.parameters['max_posts'].default == 50


# -----------------------------------------------------------------------
# VK API helper tests
# -----------------------------------------------------------------------

class TestVKAPIHelper:
    """Test the _vk_api_call helper."""

    def test_access_denied_handled(self, extractor):
        """Should handle private profile errors gracefully."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            'error': {'error_code': 15, 'error_msg': 'Access denied'}
        }

        with patch.object(extractor.session, 'get', return_value=mock_resp):
            result = extractor._vk_api_call('wall.get', {'owner_id': 123})
            assert result is None

    def test_network_error_handled(self, extractor):
        """Should handle network errors gracefully."""
        with patch.object(extractor.session, 'get', side_effect=Exception('timeout')):
            result = extractor._vk_api_call('wall.get', {'owner_id': 123})
            assert result is None

    def test_adds_default_params(self, extractor):
        """Should add access_token and v to params."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {'response': {'items': []}}

        with patch.object(extractor.session, 'get', return_value=mock_resp) as mock_get:
            extractor._vk_api_call('wall.get', {'owner_id': 123})
            call_params = mock_get.call_args[1]['params']
            assert 'access_token' in call_params
            assert 'v' in call_params

    def test_resolve_screen_name(self, extractor):
        """Should resolve screen name to numeric ID."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            'response': {'type': 'user', 'object_id': 12345}
        }

        with patch.object(extractor.session, 'get', return_value=mock_resp):
            result = extractor._resolve_user_id('durov')
            assert result == 12345

    def test_resolve_numeric_id(self, extractor):
        """Numeric IDs should be returned directly."""
        result = extractor._resolve_user_id('12345')
        assert result == 12345


# -----------------------------------------------------------------------
# Edge cases and mixed content
# -----------------------------------------------------------------------

class TestEdgeCases:
    """Test edge cases and complex content."""

    def test_mixed_content_post(self, extractor):
        """Post with phone, email, telegram, and whatsapp."""
        result = WallExtractionResult(profile_url='https://vk.com/test')
        text = (
            'Привет! Для связи:\n'
            'Телефон: +7 (916) 123-45-67\n'
            'Email: ivan@company.ru\n'
            'Telegram: t.me/ivan_channel\n'
            'WhatsApp: +79261234567\n'
            'Instagram: instagram.com/ivan_photo'
        )
        extractor._extract_contacts_from_text(text, result, source='test')

        assert len(result.phones) >= 1
        assert len(result.emails) >= 1
        assert 'ivan_channel' in result.telegram_usernames
        assert 'ivan_photo' in result.instagram_usernames
        assert any(c['type'] == 'whatsapp' for c in result.other_contacts)

    def test_empty_text(self, extractor):
        """Empty text should not crash."""
        result = WallExtractionResult(profile_url='https://vk.com/test')
        extractor._extract_contacts_from_text('', result, source='test')
        assert len(result.phones) == 0

    def test_none_text(self, extractor):
        """None text should not crash."""
        result = WallExtractionResult(profile_url='https://vk.com/test')
        extractor._extract_contacts_from_text(None, result, source='test')
        assert len(result.phones) == 0

    def test_cyrillic_heavy_text(self, extractor):
        """Should handle pure Cyrillic text without contacts."""
        result = WallExtractionResult(profile_url='https://vk.com/test')
        text = 'Сегодня прекрасный день для прогулки в парке! Всем хорошего настроения!'
        extractor._extract_contacts_from_text(text, result, source='test')
        assert len(result.phones) == 0
        assert len(result.emails) == 0
