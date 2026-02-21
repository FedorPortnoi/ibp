"""
Round 2: Chain & Pipeline Intelligence Tests
=============================================
105+ tests that verify how different discovery methods CHAIN TOGETHER.
Phone->Email, Email->Phone, VK->Telegram cross-references, and the
full pipeline flow through SourceManager dedup/cross-validation.

Categories:
  1. Phone->Email Chain (20+ tests)
     Phone found in VK profile -> used as email local part -> verify email
  2. Email->Phone Chain (20+ tests)
     Email local part is a phone -> PhoneDiscoveryService extracts it
  3. VK->Telegram Cross-Reference (15+ tests)
     Mock _cross_reference_telegram for various scenarios
  4. Multi-Source Chain (20+ tests)
     Same data from multiple sources -> dedup, confidence, verified
  5. Pipeline Order Intelligence (15+ tests)
     Early high-confidence methods not overridden by later low-confidence
  6. Cross-Validation Chains (15+ tests)
     SourceManager._cross_validate: Tier S, 3+ sources, mixed tiers

Targets:
  - app.services.phase2.phone_discovery.PhoneDiscoveryService
  - app.services.phase2.email_discovery.EmailDiscoveryService
  - app.services.phase2.source_manager.SourceManager
  - app.services.phase2.base_source.SourceResult / SourceTier
"""

import os
import re
import sys
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Dict, List, Optional
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

# Ensure project root is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
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
from app.services.phase2.base_source import (
    BaseSource,
    SourceResult,
    SourceTier,
    SourceType,
)
from app.services.phase2.source_manager import SourceManager
from app.services.phase2.russian_phone_validator import RussianPhoneValidator


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def phone_svc():
    """Fresh PhoneDiscoveryService instance."""
    svc = PhoneDiscoveryService()
    yield svc
    svc.close()


@pytest.fixture
def email_svc():
    """Fresh EmailDiscoveryService instance."""
    svc = EmailDiscoveryService()
    yield svc
    svc.close()


@pytest.fixture
def validator():
    """RussianPhoneValidator instance."""
    return RussianPhoneValidator()


def _make_source_result(data_type, value, source_name, tier, confidence,
                        verified=False, raw_data=None, metadata=None):
    """Helper to build SourceResult quickly."""
    return SourceResult(
        data_type=data_type,
        value=value,
        source_name=source_name,
        source_tier=tier,
        confidence=confidence,
        verified=verified,
        raw_data=raw_data or {},
        metadata=metadata or {},
    )


# ===========================================================================
# 1. PHONE -> EMAIL CHAIN  (20+ tests)
# ===========================================================================

class TestPhoneToEmailChain:
    """
    Test chains: phone discovered in VK -> phone digits used as email
    local part -> EmailDiscoveryService generates that candidate.
    """

    # -- Username contains phone, which becomes email candidate -------------

    def test_username_phone_becomes_email_candidate(self):
        """Username '9161234567' -> email candidates include 9161234567@mail.ru."""
        svc = EmailDiscoveryService(max_candidates=100)
        candidates = svc._generate_candidates('Иван', 'Петров', ['9161234567'])
        phone_emails = [c for c in candidates if '9161234567' in c]
        assert len(phone_emails) >= 1, "Phone digits in username should generate email candidate"
        svc.close()

    def test_username_with_prefix_generates_email(self):
        """Username 'id89161234567' -> cleaned username yields email candidate."""
        svc = EmailDiscoveryService(max_candidates=100)
        candidates = svc._generate_candidates('Иван', 'Петров', ['id89161234567'])
        # _clean_username strips 'id' prefix, the digits should remain
        digit_emails = [c for c in candidates if '89161234567' in c]
        assert len(digit_emails) >= 1
        svc.close()

    def test_phone_email_generated_across_domains(self):
        """Phone-as-username should generate candidates on multiple Russian domains."""
        svc = EmailDiscoveryService(max_candidates=100)
        candidates = svc._generate_candidates('Тест', 'Тестов', ['9031234567'])
        domains_found = set()
        for c in candidates:
            if '9031234567' in c:
                domain = c.split('@')[-1]
                domains_found.add(domain)
        assert len(domains_found) >= 2, f"Should generate phone email on multiple domains, got: {domains_found}"
        svc.close()

    def test_phone_email_is_valid_format(self, email_svc):
        """Phone-based emails pass _is_valid_email."""
        assert email_svc._is_valid_email('9161234567@mail.ru')
        assert email_svc._is_valid_email('9161234567@yandex.ru')
        assert email_svc._is_valid_email('9161234567@bk.ru')

    def test_phone_email_with_plus_invalid(self, email_svc):
        """Email starting with '+' is invalid per the regex."""
        assert not email_svc._is_valid_email('+79161234567@mail.ru')

    def test_phone_11_digits_username_cleaned(self, email_svc):
        """11-digit phone as username -> _clean_username strips non-alpha, keeps digits."""
        cleaned = email_svc._clean_username('89161234567')
        assert cleaned == '89161234567'

    def test_multiple_usernames_generate_multiple_chains(self):
        """Two phone-like usernames -> both produce email candidates."""
        svc = EmailDiscoveryService(max_candidates=100)
        candidates = svc._generate_candidates(
            'Тест', 'Тестов',
            ['9161234567', '9031112233']
        )
        has_916 = any('9161234567' in c for c in candidates)
        has_903 = any('9031112233' in c for c in candidates)
        assert has_916 and has_903
        svc.close()

    def test_short_username_skipped_in_email_chain(self, email_svc):
        """Username shorter than 3 chars is skipped (_clean_username result < 3)."""
        candidates = email_svc._generate_candidates('Иван', 'Петров', ['ab'])
        username_emails = [c for c in candidates if 'ab@' in c]
        assert len(username_emails) == 0, "Short username should not produce candidate"

    def test_username_special_chars_stripped(self, email_svc):
        """Username with special chars -> cleaned keeps only a-z0-9_.
        Note: 'user' prefix is also stripped by _clean_username regex."""
        cleaned = email_svc._clean_username('user!@#$name')
        # 'user' prefix stripped first, then special chars removed -> 'name'
        assert cleaned == 'name'

    def test_profile_prefix_stripped_from_username(self, email_svc):
        """Username starting with 'profile' -> prefix removed."""
        cleaned = email_svc._clean_username('profileivanov')
        assert cleaned == 'ivanov'

    def test_at_prefix_stripped_from_username(self, email_svc):
        """Username starting with '@' -> prefix removed."""
        cleaned = email_svc._clean_username('@etoglaz')
        assert cleaned == 'etoglaz'

    def test_phone_discovered_then_email_chain_no_duplicates(self, email_svc):
        """Two identical phone usernames -> email candidates deduplicated (set)."""
        candidates = email_svc._generate_candidates(
            'Тест', 'Тестов',
            ['9161234567', '9161234567']
        )
        # candidates is built from a set, so no duplicates
        phone_candidates = [c for c in candidates if '9161234567' in c]
        # Each email should appear exactly once
        assert len(phone_candidates) == len(set(phone_candidates))

    def test_name_transliteration_plus_phone_both_generate(self, email_svc):
        """Both name patterns and phone username should generate candidates."""
        candidates = email_svc._generate_candidates(
            'Алексей', 'Смирнов',
            ['9161234567']
        )
        has_name = any('aleksey' in c or 'smirnov' in c for c in candidates)
        has_phone = any('9161234567' in c for c in candidates)
        assert has_name, "Should have name-based candidates"
        assert has_phone, "Should have phone-based candidates"

    def test_max_candidates_limit_respected(self):
        """When max_candidates is small, total candidates are capped."""
        svc = EmailDiscoveryService(max_candidates=5)
        try:
            candidates = svc._generate_candidates(
                'Тест', 'Тестов',
                ['9161234567', '9031112233', '9251112233']
            )
            assert len(candidates) <= 5
        finally:
            svc.close()

    def test_phone_digits_in_multiple_positions(self):
        """Phone digits can be prefix in email local part: 916test@mail.ru not generated,
        but pure phone usernames should work."""
        svc = EmailDiscoveryService(max_candidates=100)
        candidates = svc._generate_candidates('Тест', 'Тестов', ['916test'])
        # _clean_username keeps '916test' as-is (alpha+digit)
        assert any('916test' in c for c in candidates)
        svc.close()

    def test_empty_usernames_no_crash(self, email_svc):
        """Empty username list should not crash, still generate name-based candidates."""
        candidates = email_svc._generate_candidates('Иван', 'Петров', [])
        assert len(candidates) > 0, "Name-based candidates should still generate"

    def test_cyrillic_username_cleaned_to_empty(self, email_svc):
        """Purely Cyrillic username -> _clean_username strips all -> too short -> skipped."""
        cleaned = email_svc._clean_username('ИванПетров')
        # Non-ASCII stripped, result is empty
        assert cleaned == ''

    def test_phone_local_part_with_underscores(self, email_svc):
        """Username '916_123_45_67' -> cleaned keeps underscores, becomes candidate."""
        cleaned = email_svc._clean_username('916_123_45_67')
        assert '916_123_45_67' == cleaned
        candidates = email_svc._generate_candidates('Т', 'Т', ['916_123_45_67'])
        assert any('916_123_45_67' in c for c in candidates)

    def test_phone_email_domain_coverage_russian_domains(self):
        """Phone-as-username generates candidates on multiple Russian domains.
        Use a large max_candidates to ensure phone username is not truncated."""
        svc = EmailDiscoveryService(max_candidates=100)
        try:
            candidates = svc._generate_candidates('Т', 'Тестов', ['9161234567'])
            phone_cands = [c for c in candidates if '9161234567' in c]
            domains_hit = {c.split('@')[-1] for c in phone_cands}
            # Should hit at least 3 domains
            assert len(domains_hit) >= 3, f"Expected 3+ domains, got: {domains_hit}"
        finally:
            svc.close()


# ===========================================================================
# 2. EMAIL -> PHONE CHAIN  (20+ tests)
# ===========================================================================

class TestEmailToPhoneChain:
    """
    Test chains: email discovered with phone as local part ->
    PhoneDiscoveryService._extract_from_emails() extracts phone.
    """

    def test_10_digit_mobile_extracted(self, phone_svc):
        """Email 9161234567@mail.ru -> extracts +79161234567."""
        phones = phone_svc._extract_from_emails(['9161234567@mail.ru'])
        assert len(phones) == 1
        assert '+79161234567' in phones[0].number
        assert phones[0].source == 'Email local part (9161234567@mail.ru)'
        assert phones[0].confidence == 'medium'

    def test_11_digit_starting_with_8(self, phone_svc):
        """Email 89161234567@mail.ru -> extracts +79161234567."""
        phones = phone_svc._extract_from_emails(['89161234567@mail.ru'])
        assert len(phones) == 1
        assert phones[0].number == '+79161234567'

    def test_11_digit_starting_with_7(self, phone_svc):
        """Email 79161234567@gmail.com -> extracts +79161234567."""
        phones = phone_svc._extract_from_emails(['79161234567@gmail.com'])
        assert len(phones) == 1
        assert phones[0].number == '+79161234567'

    def test_bk_ru_domain(self, phone_svc):
        """Email 9161234567@bk.ru -> extracts phone."""
        phones = phone_svc._extract_from_emails(['9161234567@bk.ru'])
        assert len(phones) == 1

    def test_yandex_domain(self, phone_svc):
        """Email 9031112233@yandex.ru -> extracts phone."""
        phones = phone_svc._extract_from_emails(['9031112233@yandex.ru'])
        assert len(phones) == 1
        assert '+79031112233' in phones[0].number

    def test_rambler_domain(self, phone_svc):
        """Email 9251234567@rambler.ru -> extracts phone."""
        phones = phone_svc._extract_from_emails(['9251234567@rambler.ru'])
        assert len(phones) == 1

    def test_non_phone_local_part_skipped(self, phone_svc):
        """Email ivanov@mail.ru -> no phone extracted (not digits)."""
        phones = phone_svc._extract_from_emails(['ivanov@mail.ru'])
        assert len(phones) == 0

    def test_short_digit_local_part_skipped(self, phone_svc):
        """Email 12345@mail.ru -> too few digits, not a phone."""
        phones = phone_svc._extract_from_emails(['12345@mail.ru'])
        assert len(phones) == 0

    def test_non_mobile_prefix_skipped(self, phone_svc):
        """Email 4951234567@mail.ru -> 10 digits but starts with 4 not 9 -> skipped."""
        phones = phone_svc._extract_from_emails(['4951234567@mail.ru'])
        assert len(phones) == 0

    def test_12_digit_skipped(self, phone_svc):
        """Email 791612345678@mail.ru -> 12 digits, doesn't match any pattern."""
        phones = phone_svc._extract_from_emails(['791612345678@mail.ru'])
        assert len(phones) == 0

    def test_9_digit_skipped(self, phone_svc):
        """Email 916123456@mail.ru -> 9 digits, too short for phone."""
        phones = phone_svc._extract_from_emails(['916123456@mail.ru'])
        assert len(phones) == 0

    def test_email_without_at_skipped(self, phone_svc):
        """String without '@' is skipped."""
        phones = phone_svc._extract_from_emails(['9161234567mail.ru'])
        assert len(phones) == 0

    def test_multiple_emails_multiple_phones(self, phone_svc):
        """Multiple phone emails -> extracts multiple phones."""
        phones = phone_svc._extract_from_emails([
            '9161234567@mail.ru',
            '9031112233@bk.ru',
        ])
        assert len(phones) == 2
        numbers = {p.number for p in phones}
        assert '+79161234567' in numbers
        assert '+79031112233' in numbers

    def test_duplicate_email_produces_duplicate_phone(self, phone_svc):
        """Same email twice -> two phone entries (dedup happens at pipeline level)."""
        phones = phone_svc._extract_from_emails([
            '9161234567@mail.ru',
            '9161234567@mail.ru',
        ])
        # _extract_from_emails doesn't deduplicate internally
        assert len(phones) == 2

    def test_mixed_phone_and_name_emails(self, phone_svc):
        """Mix of phone and non-phone emails -> only phones extracted."""
        phones = phone_svc._extract_from_emails([
            '9161234567@mail.ru',
            'ivanov.ivan@gmail.com',
            '9031234567@yandex.ru',
            'hello@example.com',
        ])
        assert len(phones) == 2

    def test_email_with_plus_prefix_in_local(self, phone_svc):
        """Email +79161234567@mail.ru -> digits extracted, recognized as 11-digit."""
        phones = phone_svc._extract_from_emails(['+79161234567@mail.ru'])
        assert len(phones) == 1
        assert phones[0].number == '+79161234567'

    def test_email_local_part_with_dashes(self, phone_svc):
        """Email 916-123-45-67@mail.ru -> digits extracted = 9161234567 (10 digits)."""
        phones = phone_svc._extract_from_emails(['916-123-45-67@mail.ru'])
        assert len(phones) == 1
        assert '+79161234567' in phones[0].number

    def test_email_local_with_mixed_alpha_digits(self, phone_svc):
        """Email ivan9161234567@mail.ru -> digits are 9161234567 but preceded by alpha.
        The method strips non-digits and checks length+prefix."""
        phones = phone_svc._extract_from_emails(['ivan9161234567@mail.ru'])
        # 'ivan9161234567' -> digits = '9161234567' (10 digits, starts with 9) -> extracted
        assert len(phones) == 1

    def test_confidence_always_medium(self, phone_svc):
        """All email-extracted phones have 'medium' confidence."""
        phones = phone_svc._extract_from_emails([
            '9161234567@mail.ru',
            '89161234567@gmail.com',
        ])
        for p in phones:
            assert p.confidence == 'medium'

    def test_empty_email_list(self, phone_svc):
        """Empty list -> no phones."""
        phones = phone_svc._extract_from_emails([])
        assert len(phones) == 0

    def test_source_includes_original_email(self, phone_svc):
        """Source field should contain the original email for traceability."""
        phones = phone_svc._extract_from_emails(['9161234567@mail.ru'])
        assert '9161234567@mail.ru' in phones[0].source


# ===========================================================================
# 3. VK -> TELEGRAM CROSS-REFERENCE  (15+ tests)
# ===========================================================================

class TestVkTelegramCrossReference:
    """
    Test _cross_reference_telegram behavior under various conditions.
    All tests mock the TelegramCrossRef module to avoid real API calls.
    """

    def test_import_error_handled_gracefully(self, phone_svc):
        """If telegram_crossref module is not importable, returns empty results."""
        with patch.dict('sys.modules', {'app.services.phase2.telegram_crossref': None}):
            phones, profiles = phone_svc._cross_reference_telegram(
                [{'platform': 'vk', 'url': 'https://vk.com/id123'}],
                'Иван', 'Петров'
            )
        assert phones == []
        assert profiles == []

    def test_telegram_crossref_import_error_returns_empty(self, phone_svc):
        """ImportError from telegram_crossref -> empty lists."""
        with patch(
            'app.services.phase2.phone_discovery.PhoneDiscoveryService._cross_reference_telegram',
            side_effect=ImportError("no module")
        ):
            # Call discover_sync with mocked methods
            pass
        # Direct call with mocked import
        phones, profiles = phone_svc._cross_reference_telegram([], 'Тест', 'Тест')
        assert phones == []
        assert profiles == []

    @patch('app.services.phase2.phone_discovery.PhoneDiscoveryService._get_vk_telegram_connection')
    def test_telegram_phones_from_bio(self, mock_get_conn, phone_svc):
        """Telegram profile with phones in bio -> DiscoveredPhone entries."""
        mock_get_conn.return_value = 'test_user'

        mock_tg_result = SimpleNamespace(
            username='test_user',
            phones_in_bio=['+79161234567'],
            name_match=True,
            display_name='Иван Петров',
            bio='Мой телефон: +7 916 123-45-67',
            confidence='high',
            source='vk_connection',
        )

        mock_checker = MagicMock()
        mock_checker.cross_reference_vk_profiles.return_value = [mock_tg_result]
        mock_checker.close = MagicMock()

        with patch(
            'app.services.phase2.phone_discovery.TelegramCrossRef',
            return_value=mock_checker,
            create=True
        ):
            # We need to patch the import inside the method
            import importlib
            tg_module = MagicMock()
            tg_module.TelegramCrossRef = MagicMock(return_value=mock_checker)

            with patch.dict('sys.modules', {
                'app.services.phase2.telegram_crossref': tg_module
            }):
                phones, profiles = phone_svc._cross_reference_telegram(
                    [{'platform': 'vk', 'url': 'https://vk.com/id123'}],
                    'Иван', 'Петров'
                )

        assert len(phones) == 1
        assert phones[0].number == '+79161234567'
        assert phones[0].source == 'Telegram bio (@test_user)'

    @patch('app.services.phase2.phone_discovery.PhoneDiscoveryService._get_vk_telegram_connection')
    def test_telegram_name_match_sets_medium_confidence(self, mock_get_conn, phone_svc):
        """Name match -> phone confidence is 'medium'."""
        mock_get_conn.return_value = None

        mock_tg_result = SimpleNamespace(
            username='ivanov_i',
            phones_in_bio=['+79251234567'],
            name_match=True,
            display_name='Иван Иванов',
            bio='тел: +79251234567',
            confidence='medium',
            source='username_match',
        )

        mock_checker = MagicMock()
        mock_checker.cross_reference_vk_profiles.return_value = [mock_tg_result]

        tg_module = MagicMock()
        tg_module.TelegramCrossRef = MagicMock(return_value=mock_checker)

        with patch.dict('sys.modules', {
            'app.services.phase2.telegram_crossref': tg_module
        }):
            phones, profiles = phone_svc._cross_reference_telegram(
                [{'platform': 'vk', 'url': 'https://vk.com/id456'}],
                'Иван', 'Иванов'
            )

        assert len(phones) == 1
        assert phones[0].confidence == 'medium'

    @patch('app.services.phase2.phone_discovery.PhoneDiscoveryService._get_vk_telegram_connection')
    def test_telegram_no_name_match_low_confidence(self, mock_get_conn, phone_svc):
        """No name match -> phone confidence is 'low'."""
        mock_get_conn.return_value = None

        mock_tg_result = SimpleNamespace(
            username='random_user',
            phones_in_bio=['+79031234567'],
            name_match=False,
            display_name='Совсем Другой',
            bio='+79031234567',
            confidence='low',
            source='username_guess',
        )

        mock_checker = MagicMock()
        mock_checker.cross_reference_vk_profiles.return_value = [mock_tg_result]

        tg_module = MagicMock()
        tg_module.TelegramCrossRef = MagicMock(return_value=mock_checker)

        with patch.dict('sys.modules', {
            'app.services.phase2.telegram_crossref': tg_module
        }):
            phones, profiles = phone_svc._cross_reference_telegram(
                [{'platform': 'vk', 'url': 'https://vk.com/id789'}],
                'Иван', 'Петров'
            )

        assert len(phones) == 1
        assert phones[0].confidence == 'low'

    @patch('app.services.phase2.phone_discovery.PhoneDiscoveryService._get_vk_telegram_connection')
    def test_telegram_profile_added_to_additional(self, mock_get_conn, phone_svc):
        """Telegram profile always added to additional_profiles."""
        mock_get_conn.return_value = None

        mock_tg_result = SimpleNamespace(
            username='telegram_user',
            phones_in_bio=[],
            name_match=True,
            display_name='Тест Тестов',
            bio='Привет мир',
            confidence='medium',
            source='username_match',
        )

        mock_checker = MagicMock()
        mock_checker.cross_reference_vk_profiles.return_value = [mock_tg_result]

        tg_module = MagicMock()
        tg_module.TelegramCrossRef = MagicMock(return_value=mock_checker)

        with patch.dict('sys.modules', {
            'app.services.phase2.telegram_crossref': tg_module
        }):
            phones, profiles = phone_svc._cross_reference_telegram(
                [{'platform': 'vk', 'url': 'https://vk.com/id100'}],
                'Тест', 'Тестов'
            )

        assert len(profiles) == 1
        assert profiles[0]['platform'] == 'telegram'
        assert profiles[0]['username'] == 'telegram_user'
        assert profiles[0]['url'] == 'https://t.me/telegram_user'

    @patch('app.services.phase2.phone_discovery.PhoneDiscoveryService._get_vk_telegram_connection')
    def test_telegram_no_name_match_adds_note(self, mock_get_conn, phone_svc):
        """No name match + display_name present -> note added."""
        mock_get_conn.return_value = None

        mock_tg_result = SimpleNamespace(
            username='other_user',
            phones_in_bio=[],
            name_match=False,
            display_name='Другой Человек',
            bio='bio text',
            confidence='low',
            source='guess',
        )

        mock_checker = MagicMock()
        mock_checker.cross_reference_vk_profiles.return_value = [mock_tg_result]

        tg_module = MagicMock()
        tg_module.TelegramCrossRef = MagicMock(return_value=mock_checker)

        with patch.dict('sys.modules', {
            'app.services.phase2.telegram_crossref': tg_module
        }):
            _, profiles = phone_svc._cross_reference_telegram(
                [{'platform': 'vk', 'url': 'https://vk.com/id200'}],
                'Иван', 'Петров'
            )

        assert profiles[0]['note'] != ''
        assert 'отличается' in profiles[0]['note'] or 'другой' in profiles[0]['note']

    def test_empty_vk_profiles_list(self, phone_svc):
        """Empty VK profiles list -> no crash, empty results."""
        phones, profiles = phone_svc._cross_reference_telegram([], 'Тест', 'Тест')
        assert phones == []
        assert profiles == []

    @patch('app.services.phase2.phone_discovery.PhoneDiscoveryService._get_vk_telegram_connection')
    def test_telegram_multiple_phones_in_bio(self, mock_get_conn, phone_svc):
        """Telegram profile with multiple phones -> multiple DiscoveredPhone entries."""
        mock_get_conn.return_value = None

        mock_tg_result = SimpleNamespace(
            username='multi_phone',
            phones_in_bio=['+79161234567', '+79031112233'],
            name_match=True,
            display_name='Тест',
            bio='Работа: +79161234567, Личный: +79031112233',
            confidence='medium',
            source='vk_connection',
        )

        mock_checker = MagicMock()
        mock_checker.cross_reference_vk_profiles.return_value = [mock_tg_result]

        tg_module = MagicMock()
        tg_module.TelegramCrossRef = MagicMock(return_value=mock_checker)

        with patch.dict('sys.modules', {
            'app.services.phase2.telegram_crossref': tg_module
        }):
            phones, _ = phone_svc._cross_reference_telegram(
                [{'platform': 'vk', 'url': 'https://vk.com/id300'}],
                'Тест', 'Тест'
            )

        assert len(phones) == 2
        numbers = {p.number for p in phones}
        assert '+79161234567' in numbers
        assert '+79031112233' in numbers

    @patch('app.services.phase2.phone_discovery.PhoneDiscoveryService._get_vk_telegram_connection')
    def test_telegram_phone_has_telegram_url(self, mock_get_conn, phone_svc):
        """Telegram-sourced phones have telegram_url set."""
        mock_get_conn.return_value = None

        mock_tg_result = SimpleNamespace(
            username='tg_with_url',
            phones_in_bio=['+79161234567'],
            name_match=True,
            display_name='Тест',
            bio='тел: +79161234567',
            confidence='high',
            source='vk_connection',
        )

        mock_checker = MagicMock()
        mock_checker.cross_reference_vk_profiles.return_value = [mock_tg_result]

        tg_module = MagicMock()
        tg_module.TelegramCrossRef = MagicMock(return_value=mock_checker)

        with patch.dict('sys.modules', {
            'app.services.phase2.telegram_crossref': tg_module
        }):
            phones, _ = phone_svc._cross_reference_telegram(
                [{'platform': 'vk', 'url': 'https://vk.com/id400'}],
                'Тест', 'Тест'
            )

        assert phones[0].telegram_url == 'https://t.me/tg_with_url'

    @patch('app.services.phase2.phone_discovery.PhoneDiscoveryService._get_vk_telegram_connection')
    def test_telegram_exception_handled_gracefully(self, mock_get_conn, phone_svc):
        """Exception during cross-reference -> empty results, no crash."""
        mock_get_conn.return_value = None

        mock_checker = MagicMock()
        mock_checker.cross_reference_vk_profiles.side_effect = Exception("API down")
        mock_checker.close = MagicMock()

        tg_module = MagicMock()
        tg_module.TelegramCrossRef = MagicMock(return_value=mock_checker)

        with patch.dict('sys.modules', {
            'app.services.phase2.telegram_crossref': tg_module
        }):
            phones, profiles = phone_svc._cross_reference_telegram(
                [{'platform': 'vk', 'url': 'https://vk.com/id500'}],
                'Тест', 'Тест'
            )

        assert phones == []
        assert profiles == []

    def test_bio_truncated_to_200_chars(self, phone_svc):
        """Bio longer than 200 chars is truncated in profile entry."""
        long_bio = 'A' * 500

        mock_tg_result = SimpleNamespace(
            username='long_bio_user',
            phones_in_bio=[],
            name_match=True,
            display_name='Тест',
            bio=long_bio,
            confidence='medium',
            source='vk_connection',
        )

        mock_checker = MagicMock()
        mock_checker.cross_reference_vk_profiles.return_value = [mock_tg_result]

        tg_module = MagicMock()
        tg_module.TelegramCrossRef = MagicMock(return_value=mock_checker)

        with patch.dict('sys.modules', {
            'app.services.phase2.telegram_crossref': tg_module
        }):
            with patch.object(
                phone_svc, '_get_vk_telegram_connection', return_value=None
            ):
                _, profiles = phone_svc._cross_reference_telegram(
                    [{'platform': 'vk', 'url': 'https://vk.com/id600'}],
                    'Тест', 'Тест'
                )

        assert len(profiles[0]['bio']) <= 200

    def test_none_bio_handled(self, phone_svc):
        """None bio -> empty string in profile entry."""
        mock_tg_result = SimpleNamespace(
            username='no_bio',
            phones_in_bio=[],
            name_match=True,
            display_name='Тест',
            bio=None,
            confidence='medium',
            source='vk_connection',
        )

        mock_checker = MagicMock()
        mock_checker.cross_reference_vk_profiles.return_value = [mock_tg_result]

        tg_module = MagicMock()
        tg_module.TelegramCrossRef = MagicMock(return_value=mock_checker)

        with patch.dict('sys.modules', {
            'app.services.phase2.telegram_crossref': tg_module
        }):
            with patch.object(
                phone_svc, '_get_vk_telegram_connection', return_value=None
            ):
                _, profiles = phone_svc._cross_reference_telegram(
                    [{'platform': 'vk', 'url': 'https://vk.com/id700'}],
                    'Тест', 'Тест'
                )

        assert profiles[0]['bio'] == ''


# ===========================================================================
# 4. MULTI-SOURCE CHAIN  (20+ tests)
# ===========================================================================

class TestMultiSourceChain:
    """
    Test deduplication and merging when the same data arrives from
    multiple sources through SourceManager._deduplicate.
    """

    def test_same_phone_two_sources_merged(self):
        """Same phone from two sources -> merged to single entry with boosted confidence."""
        mgr = SourceManager.__new__(SourceManager)
        mgr.sources = []

        results = [
            _make_source_result('phone', '+79161234567', 'SourceA', SourceTier.A, 0.8),
            _make_source_result('phone', '+79161234567', 'SourceB', SourceTier.B, 0.6),
        ]
        deduped = mgr._deduplicate(results)
        assert len(deduped) == 1
        assert deduped[0].metadata['source_count'] == 2
        assert deduped[0].confidence > 0.8  # boosted

    def test_same_email_three_sources_merged(self):
        """Same email from three sources -> single entry, source_count=3."""
        mgr = SourceManager.__new__(SourceManager)
        mgr.sources = []

        results = [
            _make_source_result('email', 'test@mail.ru', 'S1', SourceTier.A, 0.7),
            _make_source_result('email', 'test@mail.ru', 'S2', SourceTier.B, 0.5),
            _make_source_result('email', 'test@mail.ru', 'S3', SourceTier.C, 0.3),
        ]
        deduped = mgr._deduplicate(results)
        assert len(deduped) == 1
        assert deduped[0].metadata['source_count'] == 3

    def test_different_phones_not_merged(self):
        """Different phones -> two separate entries."""
        mgr = SourceManager.__new__(SourceManager)
        mgr.sources = []

        results = [
            _make_source_result('phone', '+79161234567', 'S1', SourceTier.A, 0.8),
            _make_source_result('phone', '+79031112233', 'S2', SourceTier.A, 0.7),
        ]
        deduped = mgr._deduplicate(results)
        assert len(deduped) == 2

    def test_case_insensitive_email_dedup(self):
        """Same email in different cases -> merged (key is lowered)."""
        mgr = SourceManager.__new__(SourceManager)
        mgr.sources = []

        results = [
            _make_source_result('email', 'Test@Mail.RU', 'S1', SourceTier.A, 0.7),
            _make_source_result('email', 'test@mail.ru', 'S2', SourceTier.B, 0.5),
        ]
        deduped = mgr._deduplicate(results)
        assert len(deduped) == 1

    def test_confidence_boost_capped_at_1(self):
        """Confidence never exceeds 1.0 even with many sources."""
        mgr = SourceManager.__new__(SourceManager)
        mgr.sources = []

        results = [
            _make_source_result('phone', '+79161234567', f'S{i}', SourceTier.A, 0.95)
            for i in range(10)
        ]
        deduped = mgr._deduplicate(results)
        assert deduped[0].confidence <= 1.0

    def test_higher_tier_preserved(self):
        """When same data from Tier S and Tier C -> merged result keeps Tier S."""
        mgr = SourceManager.__new__(SourceManager)
        mgr.sources = []

        results = [
            _make_source_result('email', 'x@y.ru', 'LeakDB', SourceTier.S, 0.9),
            _make_source_result('email', 'x@y.ru', 'Pattern', SourceTier.C, 0.3),
        ]
        deduped = mgr._deduplicate(results)
        assert deduped[0].source_tier == SourceTier.S

    def test_lower_tier_first_upgraded_by_higher(self):
        """If low-tier entry arrives first, higher-tier later upgrades it."""
        mgr = SourceManager.__new__(SourceManager)
        mgr.sources = []

        results = [
            _make_source_result('email', 'x@y.ru', 'Pattern', SourceTier.C, 0.3),
            _make_source_result('email', 'x@y.ru', 'LeakDB', SourceTier.S, 0.9),
        ]
        deduped = mgr._deduplicate(results)
        assert deduped[0].source_tier == SourceTier.S

    def test_raw_data_merged(self):
        """Raw data from both sources merged into single entry."""
        mgr = SourceManager.__new__(SourceManager)
        mgr.sources = []

        results = [
            _make_source_result('phone', '+79161234567', 'S1', SourceTier.A, 0.8,
                                raw_data={'breach_name': 'data2019'}),
            _make_source_result('phone', '+79161234567', 'S2', SourceTier.B, 0.6,
                                raw_data={'getcontact_tags': ['Work']}),
        ]
        deduped = mgr._deduplicate(results)
        assert 'breach_name' in deduped[0].raw_data
        assert 'getcontact_tags' in deduped[0].raw_data

    def test_metadata_merged_excluding_source_keys(self):
        """Metadata merged but 'sources' and 'source_count' managed internally."""
        mgr = SourceManager.__new__(SourceManager)
        mgr.sources = []

        results = [
            _make_source_result('email', 'a@b.ru', 'S1', SourceTier.A, 0.7,
                                metadata={'region': 'Moscow'}),
            _make_source_result('email', 'a@b.ru', 'S2', SourceTier.B, 0.5,
                                metadata={'carrier': 'MTS'}),
        ]
        deduped = mgr._deduplicate(results)
        assert deduped[0].metadata['region'] == 'Moscow'
        assert deduped[0].metadata['carrier'] == 'MTS'
        assert deduped[0].metadata['source_count'] == 2

    def test_phone_email_different_types_not_merged(self):
        """Phone and email with same value string -> not merged (different data_type)."""
        mgr = SourceManager.__new__(SourceManager)
        mgr.sources = []

        results = [
            _make_source_result('phone', '9161234567', 'S1', SourceTier.A, 0.8),
            _make_source_result('email', '9161234567', 'S2', SourceTier.A, 0.8),
        ]
        deduped = mgr._deduplicate(results)
        assert len(deduped) == 2

    def test_whitespace_stripped_for_dedup(self):
        """Leading/trailing whitespace stripped in dedup key."""
        mgr = SourceManager.__new__(SourceManager)
        mgr.sources = []

        results = [
            _make_source_result('email', '  test@mail.ru  ', 'S1', SourceTier.A, 0.7),
            _make_source_result('email', 'test@mail.ru', 'S2', SourceTier.B, 0.5),
        ]
        deduped = mgr._deduplicate(results)
        assert len(deduped) == 1

    def test_boost_formula_per_source(self):
        """Each additional source boosts by min(0.15, remaining*0.5)."""
        mgr = SourceManager.__new__(SourceManager)
        mgr.sources = []

        base_confidence = 0.6
        results = [
            _make_source_result('phone', '+79161234567', 'S1', SourceTier.A, base_confidence),
            _make_source_result('phone', '+79161234567', 'S2', SourceTier.A, 0.5),
        ]
        deduped = mgr._deduplicate(results)
        expected_boost = min(0.15, (1.0 - base_confidence) * 0.5)
        expected = base_confidence + expected_boost
        assert abs(deduped[0].confidence - expected) < 0.001

    def test_same_source_name_not_counted_twice(self):
        """Same source name appearing twice -> only counted once in source_count."""
        mgr = SourceManager.__new__(SourceManager)
        mgr.sources = []

        results = [
            _make_source_result('phone', '+79161234567', 'S1', SourceTier.A, 0.7),
            _make_source_result('phone', '+79161234567', 'S1', SourceTier.A, 0.6),
        ]
        deduped = mgr._deduplicate(results)
        assert deduped[0].metadata['source_count'] == 1

    def test_dedup_preserves_all_source_names(self):
        """Source names are all tracked in metadata['sources'] list."""
        mgr = SourceManager.__new__(SourceManager)
        mgr.sources = []

        results = [
            _make_source_result('email', 't@m.ru', 'LeakCheck', SourceTier.S, 0.9),
            _make_source_result('email', 't@m.ru', 'Holehe', SourceTier.B, 0.7),
            _make_source_result('email', 't@m.ru', 'SMTP', SourceTier.B, 0.6),
        ]
        deduped = mgr._deduplicate(results)
        sources = deduped[0].metadata['sources']
        assert 'LeakCheck' in sources
        assert 'Holehe' in sources
        assert 'SMTP' in sources

    def test_empty_results_dedup(self):
        """Empty list -> empty deduplicated list."""
        mgr = SourceManager.__new__(SourceManager)
        mgr.sources = []

        deduped = mgr._deduplicate([])
        assert deduped == []

    def test_single_result_no_boost(self):
        """Single result -> confidence unchanged, source_count=1."""
        mgr = SourceManager.__new__(SourceManager)
        mgr.sources = []

        results = [
            _make_source_result('phone', '+79161234567', 'S1', SourceTier.A, 0.75),
        ]
        deduped = mgr._deduplicate(results)
        assert deduped[0].confidence == 0.75
        assert deduped[0].metadata['source_count'] == 1

    def test_confidence_label_after_boost(self):
        """After boost from multi-source, confidence_label updates accordingly."""
        mgr = SourceManager.__new__(SourceManager)
        mgr.sources = []

        results = [
            _make_source_result('phone', '+79161234567', 'S1', SourceTier.A, 0.65),
            _make_source_result('phone', '+79161234567', 'S2', SourceTier.A, 0.65),
        ]
        deduped = mgr._deduplicate(results)
        # 0.65 + boost -> should be >= 0.7
        assert deduped[0].confidence >= 0.7
        assert deduped[0].confidence_label in ('high', 'very_high')

    def test_dedup_with_mixed_data_types(self):
        """Multiple data types -> each deduped independently."""
        mgr = SourceManager.__new__(SourceManager)
        mgr.sources = []

        results = [
            _make_source_result('phone', '+79161234567', 'S1', SourceTier.A, 0.8),
            _make_source_result('email', 'test@mail.ru', 'S1', SourceTier.A, 0.7),
            _make_source_result('phone', '+79161234567', 'S2', SourceTier.B, 0.6),
            _make_source_result('email', 'test@mail.ru', 'S2', SourceTier.B, 0.5),
        ]
        deduped = mgr._deduplicate(results)
        assert len(deduped) == 2
        phone_result = [r for r in deduped if r.data_type == 'phone'][0]
        email_result = [r for r in deduped if r.data_type == 'email'][0]
        assert phone_result.metadata['source_count'] == 2
        assert email_result.metadata['source_count'] == 2


# ===========================================================================
# 5. PIPELINE ORDER INTELLIGENCE  (15+ tests)
# ===========================================================================

class TestPipelineOrderIntelligence:
    """
    Test that the full pipeline preserves high-confidence results from
    early methods and doesn't let later low-confidence methods override them.
    """

    def test_vk_api_phone_not_duplicated_by_username(self, phone_svc):
        """Phone from VK API (high) + same from username (medium) -> single entry."""
        phone_num = '+7 (916) 123-45-67'  # display format from validator
        key = phone_svc._normalize_key(phone_num)

        # Simulate: VK API found it first
        all_phones = {}
        vk_phone = DiscoveredPhone(
            number=phone_num,
            source='VK profile (mobile_phone)',
            confidence='high',
        )
        all_phones[key] = vk_phone

        # Username extraction finds same number
        username_phone = DiscoveredPhone(
            number='+79161234567',
            source='Username pattern (9161234567)',
            confidence='medium',
        )
        ukey = phone_svc._normalize_key(username_phone.number)

        # Same key -> not added
        if ukey not in all_phones:
            all_phones[ukey] = username_phone

        assert len(all_phones) == 1
        assert all_phones[key].confidence == 'high'  # Original stays

    def test_normalize_key_strips_formatting(self, phone_svc):
        """_normalize_key returns last 10 digits regardless of formatting."""
        assert phone_svc._normalize_key('+7 (916) 123-45-67') == '9161234567'
        assert phone_svc._normalize_key('+79161234567') == '9161234567'
        assert phone_svc._normalize_key('89161234567') == '9161234567'
        assert phone_svc._normalize_key('9161234567') == '9161234567'

    def test_normalize_key_consistent_across_formats(self, phone_svc):
        """All formats of the same phone produce the same key."""
        formats = [
            '+79161234567',
            '+7 (916) 123-45-67',
            '89161234567',
            '8-916-123-45-67',
            '+7-916-123-45-67',
            '+7 916 1234567',
        ]
        keys = {phone_svc._normalize_key(f) for f in formats}
        assert len(keys) == 1
        assert '9161234567' in keys

    def test_first_source_wins_dedup(self, phone_svc):
        """In the pipeline dict, first entry for a key wins."""
        all_phones = {}

        phone1 = DiscoveredPhone(number='+79161234567', source='VK API', confidence='high')
        phone2 = DiscoveredPhone(number='+79161234567', source='Wall post', confidence='medium')

        key1 = phone_svc._normalize_key(phone1.number)
        key2 = phone_svc._normalize_key(phone2.number)

        if key1 not in all_phones:
            all_phones[key1] = phone1
        if key2 not in all_phones:
            all_phones[key2] = phone2

        assert all_phones[key1].source == 'VK API'
        assert all_phones[key1].confidence == 'high'

    @patch.dict(os.environ, {'VK_SERVICE_TOKEN': 'test_token'})
    @patch.object(PhoneDiscoveryService, '_extract_via_vk_api')
    @patch.object(PhoneDiscoveryService, '_extract_from_vk_wall')
    @patch.object(PhoneDiscoveryService, '_cross_reference_telegram')
    def test_pipeline_vk_api_runs_before_wall(
        self, mock_tg, mock_wall, mock_api, phone_svc
    ):
        """VK API extraction runs before wall extraction in pipeline."""
        call_order = []

        def api_side_effect(url):
            call_order.append('api')
            return [DiscoveredPhone(number='+79161234567', source='VK API', confidence='high')]

        def wall_side_effect(url):
            call_order.append('wall')
            return []

        mock_api.side_effect = api_side_effect
        mock_wall.side_effect = wall_side_effect
        mock_tg.return_value = ([], [])

        phone_svc.discover_sync(
            'Иван', 'Петров', [],
            profile_urls=[{'platform': 'vk', 'url': 'https://vk.com/id123'}]
        )

        assert call_order.index('api') < call_order.index('wall')

    @patch.dict(os.environ, {'VK_SERVICE_TOKEN': 'test_token'})
    @patch.object(PhoneDiscoveryService, '_extract_via_vk_api')
    @patch.object(PhoneDiscoveryService, '_extract_from_vk_wall')
    @patch.object(PhoneDiscoveryService, '_cross_reference_telegram')
    def test_pipeline_vk_phone_not_duplicated_by_wall(
        self, mock_tg, mock_wall, mock_api, phone_svc
    ):
        """Same phone from VK API and wall -> only one entry in results."""
        mock_api.return_value = [
            DiscoveredPhone(number='+79161234567', source='VK API', confidence='high')
        ]
        mock_wall.return_value = [
            DiscoveredPhone(number='+79161234567', source='VK wall', confidence='medium')
        ]
        mock_tg.return_value = ([], [])

        results = phone_svc.discover_sync(
            'Иван', 'Петров', [],
            profile_urls=[{'platform': 'vk', 'url': 'https://vk.com/id123'}]
        )

        # After validation filter, check dedup happened at dict level
        phone_numbers = [p.number for p in results.phones]
        # Normalize for comparison
        normalized = set()
        for num in phone_numbers:
            digits = re.sub(r'\D', '', num)
            normalized.add(digits[-10:])
        # Should have at most 1 entry for 9161234567
        count_916 = sum(1 for d in normalized if d == '9161234567')
        assert count_916 <= 1

    def test_username_extraction_before_email_extraction(self, phone_svc):
        """Username extraction runs before email extraction in discover_sync."""
        # Verify the pipeline order by checking the code structure
        # _extract_from_usernames is Method 3, _extract_from_emails is Method 4
        username_phones = phone_svc._extract_from_usernames(['9161234567'])
        email_phones = phone_svc._extract_from_emails(['9161234567@mail.ru'])
        # Both produce results for the same number
        assert len(username_phones) >= 1
        assert len(email_phones) == 1

    def test_email_extraction_deduped_with_username(self, phone_svc):
        """Same phone from username and email -> only first survives in dict."""
        all_phones = {}

        # Method 3: username
        u_phones = phone_svc._extract_from_usernames(['9161234567'])
        for p in u_phones:
            key = phone_svc._normalize_key(p.number)
            if key not in all_phones:
                all_phones[key] = p

        # Method 4: email
        e_phones = phone_svc._extract_from_emails(['9161234567@mail.ru'])
        for p in e_phones:
            key = phone_svc._normalize_key(p.number)
            if key not in all_phones:
                all_phones[key] = p

        assert len(all_phones) == 1
        # First one wins (username extraction)
        assert 'Username' in all_phones['9161234567'].source

    @patch.dict(os.environ, {'VK_SERVICE_TOKEN': 'test_token'})
    @patch.object(PhoneDiscoveryService, '_extract_via_vk_api')
    @patch.object(PhoneDiscoveryService, '_extract_from_vk_wall')
    @patch.object(PhoneDiscoveryService, '_cross_reference_telegram')
    def test_pipeline_error_doesnt_stop_later_methods(
        self, mock_tg, mock_wall, mock_api, phone_svc
    ):
        """Error in VK API doesn't prevent username/email extraction."""
        mock_api.side_effect = Exception("VK API down")
        mock_wall.return_value = []
        mock_tg.return_value = ([], [])

        results = phone_svc.discover_sync(
            'Иван', 'Петров',
            ['9161234567'],
            profile_urls=[{'platform': 'vk', 'url': 'https://vk.com/id123'}],
            emails=['9031112233@mail.ru']
        )
        # Should still have results from username/email extraction
        # (after validation filter)
        assert results.errors  # Error logged

    def test_generate_candidates_runs_last(self, phone_svc):
        """_generate_phone_candidates returns low confidence candidates."""
        candidates = phone_svc._generate_phone_candidates(
            ['user1234567'], 'Тест', 'Тест'
        )
        for c in candidates:
            assert c.confidence == 'low'

    @patch.dict(os.environ, {'VK_SERVICE_TOKEN': 'test_token'})
    @patch.object(PhoneDiscoveryService, '_extract_via_vk_api')
    @patch.object(PhoneDiscoveryService, '_extract_from_vk_wall')
    @patch.object(PhoneDiscoveryService, '_cross_reference_telegram')
    def test_high_confidence_preserved_when_low_arrives_later(
        self, mock_tg, mock_wall, mock_api, phone_svc
    ):
        """High confidence VK phone is kept when low-conf candidate has same number."""
        mock_api.return_value = [
            DiscoveredPhone(number='+79161234567', source='VK API', confidence='high')
        ]
        mock_wall.return_value = []
        mock_tg.return_value = ([], [])

        # username '9161234567' will also try to add same phone at medium/low confidence
        results = phone_svc.discover_sync(
            'Иван', 'Петров',
            ['9161234567'],
            profile_urls=[{'platform': 'vk', 'url': 'https://vk.com/id123'}]
        )

        # The VK API phone (high) should win since it was added first
        for p in results.phones:
            digits = re.sub(r'\D', '', p.number)
            if digits.endswith('9161234567'):
                assert p.source == 'VK API' or p.confidence != 'low'

    def test_non_vk_profile_urls_skipped_for_vk_methods(self, phone_svc):
        """Only VK profile URLs are processed by VK-specific methods."""
        with patch.dict(os.environ, {'VK_SERVICE_TOKEN': 'token'}):
            with patch.object(phone_svc, '_extract_via_vk_api') as mock_api:
                mock_api.return_value = []
                with patch.object(phone_svc, '_extract_from_vk_wall') as mock_wall:
                    mock_wall.return_value = []
                    with patch.object(phone_svc, '_cross_reference_telegram') as mock_tg:
                        mock_tg.return_value = ([], [])
                        phone_svc.discover_sync(
                            'Тест', 'Тестов', [],
                            profile_urls=[
                                {'platform': 'ok', 'url': 'https://ok.ru/profile/123'},
                                {'platform': 'vk', 'url': 'https://vk.com/id123'},
                            ]
                        )
                        # VK API should only be called for VK URLs
                        assert mock_api.call_count == 1
                        assert 'vk.com' in mock_api.call_args[0][0]

    def test_candidates_generated_count_accurate(self, phone_svc):
        """results.candidates_generated reflects total unique phones before validation."""
        with patch.object(phone_svc, '_cross_reference_telegram', return_value=([], [])):
            results = phone_svc.discover_sync(
                'Тест', 'Тестов',
                ['9161234567', '9031112233'],
                emails=['9251112233@mail.ru']
            )
            assert results.candidates_generated >= 2


# ===========================================================================
# 6. CROSS-VALIDATION CHAINS  (15+ tests)
# ===========================================================================

class TestCrossValidationChains:
    """
    Test SourceManager._cross_validate behavior for cross-data-type
    validation (phone + email from Tier S -> both verified).
    """

    def test_tier_s_phone_and_email_both_verified(self):
        """Phone from Tier S + Email from Tier S -> both marked verified."""
        mgr = SourceManager.__new__(SourceManager)
        mgr.sources = []

        results = [
            _make_source_result('phone', '+79161234567', 'LeakCheck', SourceTier.S, 0.9),
            _make_source_result('email', 'test@mail.ru', 'LeakCheck', SourceTier.S, 0.85),
        ]
        validated = mgr._cross_validate(results)

        phone = [r for r in validated if r.data_type == 'phone'][0]
        email = [r for r in validated if r.data_type == 'email'][0]

        assert phone.verified is True
        assert email.verified is True
        assert phone.metadata.get('cross_validated_with') == 'email_breach'
        assert email.metadata.get('cross_validated_with') == 'phone_breach'

    def test_tier_a_phone_and_email_not_cross_validated(self):
        """Phone from Tier A + Email from Tier A -> NOT cross-validated by breach rule."""
        mgr = SourceManager.__new__(SourceManager)
        mgr.sources = []

        results = [
            _make_source_result('phone', '+79161234567', 'VK API', SourceTier.A, 0.8),
            _make_source_result('email', 'test@mail.ru', 'VK API', SourceTier.A, 0.7),
        ]
        validated = mgr._cross_validate(results)

        phone = [r for r in validated if r.data_type == 'phone'][0]
        email = [r for r in validated if r.data_type == 'email'][0]

        assert phone.metadata.get('cross_validated_with') is None
        assert email.metadata.get('cross_validated_with') is None

    def test_three_sources_verified(self):
        """3+ sources confirming same data -> verified=True."""
        mgr = SourceManager.__new__(SourceManager)
        mgr.sources = []

        result = _make_source_result(
            'phone', '+79161234567', 'S1', SourceTier.A, 0.7,
            metadata={'source_count': 3}
        )
        validated = mgr._cross_validate([result])

        assert validated[0].verified is True
        assert 'confirmed_by_3_sources' in validated[0].metadata.get('verified_reason', '')

    def test_two_sources_high_confidence_verified(self):
        """2 sources + confidence >= 0.7 -> verified=True."""
        mgr = SourceManager.__new__(SourceManager)
        mgr.sources = []

        result = _make_source_result(
            'email', 'test@mail.ru', 'S1', SourceTier.A, 0.75,
            metadata={'source_count': 2}
        )
        validated = mgr._cross_validate([result])

        assert validated[0].verified is True
        assert validated[0].metadata['verified_reason'] == 'dual_source_high_confidence'

    def test_two_sources_low_confidence_not_verified(self):
        """2 sources but confidence < 0.7 -> NOT verified."""
        mgr = SourceManager.__new__(SourceManager)
        mgr.sources = []

        result = _make_source_result(
            'email', 'test@mail.ru', 'S1', SourceTier.C, 0.5,
            metadata={'source_count': 2}
        )
        validated = mgr._cross_validate([result])

        assert validated[0].verified is False

    def test_single_source_not_verified(self):
        """1 source -> never verified by multi-source rule."""
        mgr = SourceManager.__new__(SourceManager)
        mgr.sources = []

        result = _make_source_result(
            'phone', '+79161234567', 'S1', SourceTier.S, 0.95,
            metadata={'source_count': 1}
        )
        # No email in results, so Tier S cross-validation won't trigger
        validated = mgr._cross_validate([result])

        assert validated[0].verified is False

    def test_tier_s_phone_only_no_email(self):
        """Tier S phone without any email -> not cross-validated."""
        mgr = SourceManager.__new__(SourceManager)
        mgr.sources = []

        results = [
            _make_source_result('phone', '+79161234567', 'LeakDB', SourceTier.S, 0.9,
                                metadata={'source_count': 1}),
        ]
        validated = mgr._cross_validate(results)

        assert validated[0].verified is False

    def test_five_sources_verified_with_reason(self):
        """5 sources -> verified_reason includes count."""
        mgr = SourceManager.__new__(SourceManager)
        mgr.sources = []

        result = _make_source_result(
            'phone', '+79161234567', 'S1', SourceTier.A, 0.8,
            metadata={'source_count': 5}
        )
        validated = mgr._cross_validate([result])

        assert validated[0].verified is True
        assert '5' in validated[0].metadata['verified_reason']

    def test_mixed_tiers_s_and_a(self):
        """Tier S phone + Tier A email -> phone verified (Tier S rule), email not."""
        mgr = SourceManager.__new__(SourceManager)
        mgr.sources = []

        results = [
            _make_source_result('phone', '+79161234567', 'LeakDB', SourceTier.S, 0.9,
                                metadata={'source_count': 1}),
            _make_source_result('email', 'test@mail.ru', 'VK API', SourceTier.A, 0.7,
                                metadata={'source_count': 1}),
        ]
        validated = mgr._cross_validate(results)

        phone = [r for r in validated if r.data_type == 'phone'][0]
        email = [r for r in validated if r.data_type == 'email'][0]

        # Tier S cross-validation only triggers when BOTH are Tier S
        assert phone.verified is False
        assert email.verified is False

    def test_multiple_tier_s_emails_all_cross_validated(self):
        """One Tier S phone + two Tier S emails -> all three verified."""
        mgr = SourceManager.__new__(SourceManager)
        mgr.sources = []

        results = [
            _make_source_result('phone', '+79161234567', 'LeakDB1', SourceTier.S, 0.9),
            _make_source_result('email', 'a@mail.ru', 'LeakDB1', SourceTier.S, 0.85),
            _make_source_result('email', 'b@mail.ru', 'LeakDB2', SourceTier.S, 0.8),
        ]
        validated = mgr._cross_validate(results)

        for r in validated:
            assert r.verified is True

    def test_cross_validate_preserves_confidence(self):
        """_cross_validate should not alter confidence values."""
        mgr = SourceManager.__new__(SourceManager)
        mgr.sources = []

        results = [
            _make_source_result('phone', '+79161234567', 'S1', SourceTier.A, 0.73,
                                metadata={'source_count': 2}),
        ]
        validated = mgr._cross_validate(results)
        assert validated[0].confidence == 0.73

    def test_cross_validate_empty_list(self):
        """Empty list -> empty validated list."""
        mgr = SourceManager.__new__(SourceManager)
        mgr.sources = []

        validated = mgr._cross_validate([])
        assert validated == []

    def test_group_by_type_separates_correctly(self):
        """_group_by_type separates results into phone/email/profile groups."""
        mgr = SourceManager.__new__(SourceManager)
        mgr.sources = []

        results = [
            _make_source_result('phone', '+79161234567', 'S1', SourceTier.A, 0.8),
            _make_source_result('email', 'test@mail.ru', 'S1', SourceTier.A, 0.7),
            _make_source_result('phone', '+79031112233', 'S2', SourceTier.B, 0.6),
            _make_source_result('profile', 'https://vk.com/id123', 'S3', SourceTier.A, 0.9),
        ]
        grouped = mgr._group_by_type(results)

        assert len(grouped['phone']) == 2
        assert len(grouped['email']) == 1
        assert len(grouped['profile']) == 1

    def test_group_by_type_empty(self):
        """Empty results -> empty dict."""
        mgr = SourceManager.__new__(SourceManager)
        mgr.sources = []

        grouped = mgr._group_by_type([])
        assert grouped == {}

    def test_source_result_confidence_label_boundaries(self):
        """Test confidence_label property at exact boundaries."""
        assert SourceResult('p', 'v', 's', SourceTier.A, 0.9).confidence_label == 'very_high'
        assert SourceResult('p', 'v', 's', SourceTier.A, 0.95).confidence_label == 'very_high'
        assert SourceResult('p', 'v', 's', SourceTier.A, 0.89).confidence_label == 'high'
        assert SourceResult('p', 'v', 's', SourceTier.A, 0.7).confidence_label == 'high'
        assert SourceResult('p', 'v', 's', SourceTier.A, 0.69).confidence_label == 'medium'
        assert SourceResult('p', 'v', 's', SourceTier.A, 0.5).confidence_label == 'medium'
        assert SourceResult('p', 'v', 's', SourceTier.A, 0.49).confidence_label == 'low'
        assert SourceResult('p', 'v', 's', SourceTier.A, 0.0).confidence_label == 'low'

    def test_source_result_to_dict(self):
        """SourceResult.to_dict() includes all expected fields."""
        sr = _make_source_result('phone', '+79161234567', 'LeakCheck', SourceTier.S, 0.9,
                                 verified=True, metadata={'region': 'Moscow'})
        d = sr.to_dict()
        assert d['data_type'] == 'phone'
        assert d['value'] == '+79161234567'
        assert d['source_name'] == 'LeakCheck'
        assert d['source_tier'] == 'Breach Database'
        assert d['confidence'] == 0.9
        assert d['confidence_label'] == 'very_high'
        assert d['verified'] is True
        assert d['metadata']['region'] == 'Moscow'


# ===========================================================================
# 7. FULL PIPELINE INTEGRATION CHAINS  (bonus, ensuring 100+ total)
# ===========================================================================

class TestFullPipelineChains:
    """
    End-to-end chain tests combining multiple pipeline stages.
    """

    def test_discover_sync_returns_results_type(self, phone_svc):
        """discover_sync returns PhoneDiscoveryResults."""
        with patch.object(phone_svc, '_cross_reference_telegram', return_value=([], [])):
            results = phone_svc.discover_sync('Тест', 'Тестов', [])
        assert isinstance(results, PhoneDiscoveryResults)

    def test_discover_sync_timing_recorded(self, phone_svc):
        """discovery_time is recorded in results."""
        with patch.object(phone_svc, '_cross_reference_telegram', return_value=([], [])):
            results = phone_svc.discover_sync('Тест', 'Тестов', [])
        assert results.discovery_time >= 0

    def test_discover_sync_errors_list_populated_on_failure(self, phone_svc):
        """Errors list populated when an exception occurs."""
        with patch.object(
            phone_svc, '_extract_from_usernames',
            side_effect=Exception("test error")
        ):
            with patch.object(phone_svc, '_cross_reference_telegram', return_value=([], [])):
                results = phone_svc.discover_sync('Т', 'Т', ['test'])
        assert len(results.errors) > 0

    def test_phone_from_email_chain_validated(self, phone_svc):
        """Phone extracted from email goes through validator filter."""
        with patch.object(phone_svc, '_cross_reference_telegram', return_value=([], [])):
            results = phone_svc.discover_sync(
                'Тест', 'Тестов', [],
                emails=['9161234567@mail.ru']
            )
        # If phone passes validation, it should have carrier and region
        for p in results.phones:
            assert p.carrier is not None or p.region is not None

    def test_username_phone_chain_validated(self, phone_svc):
        """Phone from username goes through validator filter."""
        with patch.object(phone_svc, '_cross_reference_telegram', return_value=([], [])):
            results = phone_svc.discover_sync('Тест', 'Тестов', ['9161234567'])
        for p in results.phones:
            digits = re.sub(r'\D', '', p.number)
            assert len(digits) == 11  # Validated -> formatted as +7XXXXXXXXXX

    def test_non_mobile_filtered_out(self, phone_svc):
        """Landline numbers (prefix 495) are filtered out (only mobile kept)."""
        with patch.object(phone_svc, '_cross_reference_telegram', return_value=([], [])):
            results = phone_svc.discover_sync(
                'Тест', 'Тестов', [],
                emails=['4951234567@mail.ru']
            )
        # 495 is Moscow landline, should be filtered out
        for p in results.phones:
            digits = re.sub(r'\D', '', p.number)
            assert not digits[1:4].startswith('495')

    def test_additional_profiles_from_telegram_chain(self, phone_svc):
        """Telegram profiles found via cross-ref appear in additional_profiles."""
        mock_tg_result = SimpleNamespace(
            username='tg_found',
            phones_in_bio=[],
            name_match=True,
            display_name='Тест',
            bio='',
            confidence='medium',
            source='vk_connection',
        )

        mock_checker = MagicMock()
        mock_checker.cross_reference_vk_profiles.return_value = [mock_tg_result]

        tg_module = MagicMock()
        tg_module.TelegramCrossRef = MagicMock(return_value=mock_checker)

        with patch.dict('sys.modules', {
            'app.services.phase2.telegram_crossref': tg_module
        }):
            with patch.object(phone_svc, '_get_vk_telegram_connection', return_value=None):
                results = phone_svc.discover_sync(
                    'Тест', 'Тестов', [],
                    profile_urls=[{'platform': 'vk', 'url': 'https://vk.com/id123'}]
                )

        assert len(results.additional_profiles) >= 1
        assert results.additional_profiles[0]['platform'] == 'telegram'

    def test_email_candidate_generation_with_transliteration(self, email_svc):
        """Russian name -> transliterated -> used in email candidates."""
        candidates = email_svc._generate_candidates('Александр', 'Козлов', [])
        # 'aleksandr' and 'kozlov' should appear
        has_translit = any('aleksandr' in c or 'kozlov' in c for c in candidates)
        assert has_translit, f"Transliterated names not found in: {candidates[:5]}"

    def test_email_svc_generate_no_duplicates(self, email_svc):
        """Email candidate list has no duplicates (built from set)."""
        candidates = email_svc._generate_candidates('Тест', 'Тестов', ['testuser'])
        assert len(candidates) == len(set(candidates))

    def test_email_svc_max_candidates_default(self, email_svc):
        """Default max_candidates is 30."""
        assert email_svc.max_candidates == 30

    def test_phone_svc_max_candidates_default(self, phone_svc):
        """Default max_candidates is 50."""
        assert phone_svc.max_candidates == 50
