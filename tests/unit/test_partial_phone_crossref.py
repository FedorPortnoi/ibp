"""
Tests for Step 8.5: Partial Phone Cross-Reference
===================================================
Tests the cross-referencing of masked phone hints from the forgot-password
oracle against breach databases and GetContact to complete partial numbers.
"""

import re
from unittest.mock import patch, MagicMock

import pytest

from app.services.candidate.contact_discovery import (
    ContactDiscoveryService,
    DiscoveredEmail,
    DiscoveredPhone,
    CONFIDENCE_SCORES,
    _get_score,
    _score_to_label,
)


# ---------------------------------------------------------------------------
# _build_phone_pattern
# ---------------------------------------------------------------------------

class TestBuildPhonePattern:
    """Test regex pattern generation from masked phone strings."""

    def test_pattern_from_area_code_and_last_two(self):
        pattern = ContactDiscoveryService._build_phone_pattern('+7 916 ***-**-67')
        assert pattern is not None
        assert pattern.match('79161234567')
        assert pattern.match('79160000067')
        assert not pattern.match('79171234567')  # wrong area code
        assert not pattern.match('79161234568')  # wrong last digit

    def test_pattern_from_merged_hints(self):
        """Merged: VK shows +7 916 ***-**-67 + Yandex shows +7 *** ***-45-**."""
        pattern = ContactDiscoveryService._build_phone_pattern('+7 916 ***-45-67')
        assert pattern is not None
        assert pattern.match('79161114567')
        assert pattern.match('79169994567')
        assert not pattern.match('79161114568')

    def test_pattern_fully_known(self):
        pattern = ContactDiscoveryService._build_phone_pattern('+7 916 123-45-67')
        assert pattern is not None
        assert pattern.match('79161234567')
        assert not pattern.match('79161234568')

    def test_pattern_too_short_returns_none(self):
        pattern = ContactDiscoveryService._build_phone_pattern('+7 9')
        assert pattern is None

    def test_pattern_no_area_code(self):
        """All area code digits masked."""
        pattern = ContactDiscoveryService._build_phone_pattern('+7 *** ***-45-67')
        assert pattern is not None
        assert pattern.match('79161114567')
        assert pattern.match('79261114567')

    def test_pattern_empty_string(self):
        pattern = ContactDiscoveryService._build_phone_pattern('')
        assert pattern is None


# ---------------------------------------------------------------------------
# _generate_phone_candidates
# ---------------------------------------------------------------------------

class TestGeneratePhoneCandidates:
    """Test candidate phone number generation from masked patterns."""

    def test_one_unknown_gives_10(self):
        candidates = ContactDiscoveryService._generate_phone_candidates(
            '+7 916 123-45-6*'
        )
        assert len(candidates) == 10
        assert '+79161234560' in candidates
        assert '+79161234569' in candidates

    def test_two_unknowns_gives_100(self):
        candidates = ContactDiscoveryService._generate_phone_candidates(
            '+7 916 123-45-**', max_candidates=200,
        )
        assert len(candidates) == 100
        assert '+79161234500' in candidates
        assert '+79161234599' in candidates

    def test_three_unknowns_returns_empty(self):
        """3+ unknowns is too many for brute force."""
        candidates = ContactDiscoveryService._generate_phone_candidates(
            '+7 916 123-**-**'
        )
        assert candidates == []

    def test_zero_unknowns_returns_empty(self):
        candidates = ContactDiscoveryService._generate_phone_candidates(
            '+7 916 123-45-67'
        )
        assert candidates == []

    def test_max_candidates_limit(self):
        candidates = ContactDiscoveryService._generate_phone_candidates(
            '+7 916 123-45-**', max_candidates=20,
        )
        assert len(candidates) <= 20

    def test_candidates_are_valid_format(self):
        candidates = ContactDiscoveryService._generate_phone_candidates(
            '+7 916 123-45-6*'
        )
        for c in candidates:
            assert c.startswith('+7')
            digits = re.sub(r'\D', '', c)
            assert len(digits) == 11


# ---------------------------------------------------------------------------
# _add_completed_phone
# ---------------------------------------------------------------------------

class TestAddCompletedPhone:
    """Test phone addition and deduplication logic."""

    def test_adds_new_phone(self):
        svc = ContactDiscoveryService()
        svc._add_completed_phone(
            '+79161234567', '+7 916 ***-**-67',
            'partial_phone_breach', 'LeakDB',
        )
        assert len(svc.found_phones) == 1
        assert svc.found_phones[0].number == '+79161234567'
        assert svc.found_phones[0].source == 'partial_phone_breach'
        assert svc.found_phones[0].confidence_score == _get_score('partial_phone_breach')

    def test_upgrades_existing_phone_confidence(self):
        svc = ContactDiscoveryService()
        # Add a lower-confidence phone first
        svc.found_phones.append(DiscoveredPhone(
            number='+79161234567',
            source='forgot_password',
            confidence='высокая',
            profile_name='Oracle',
            raw_value='+7 916 ***-**-67',
            confidence_score=0.78,
            sources=['forgot_password'],
        ))
        # Upgrade via breach match
        svc._add_completed_phone(
            '+79161234567', '+7 916 ***-**-67',
            'partial_phone_breach', 'LeakDB',
        )
        assert len(svc.found_phones) == 1  # no duplicate
        assert svc.found_phones[0].confidence_score == _get_score('partial_phone_breach')
        assert 'partial_phone_breach' in svc.found_phones[0].sources

    def test_invalid_phone_not_added(self):
        svc = ContactDiscoveryService()
        svc._add_completed_phone('', '+7 ***', 'partial_phone_breach', 'Test')
        assert len(svc.found_phones) == 0


# ---------------------------------------------------------------------------
# _breach_db_phone_match
# ---------------------------------------------------------------------------

class TestBreachDBPhoneMatch:
    """Test breach database cross-referencing for partial phone completion."""

    LEAK_DB_PATCH = 'app.services.phase2.sources.leak_sources.LeakDB'

    def test_breach_match_by_email(self):
        """LeakDB returns a phone that matches the partial pattern."""
        svc = ContactDiscoveryService()
        svc.found_emails.append(DiscoveredEmail(
            email='test@mail.ru',
            source='vk_profile',
            confidence='высокая',
            verified=False,
            profile_name='Test',
            confidence_score=0.95,
            sources=['vk_profile'],
        ))

        mock_db = MagicMock()
        mock_db.query_email.return_value = [
            {'phone': '+79161234567', 'email': 'test@mail.ru', 'source': 'vk_2012'},
        ]
        mock_db.query_name.return_value = []

        mock_check = MagicMock()
        mock_check.full_name = 'Иванов Иван'

        pattern = ContactDiscoveryService._build_phone_pattern('+7 916 ***-**-67')

        with patch(self.LEAK_DB_PATCH) as MockLeakDB:
            MockLeakDB.get_instance.return_value = mock_db
            result = svc._breach_db_phone_match(mock_check, pattern, '+7 916 ***-**-67')

        assert result == '+79161234567'
        assert len(svc.found_phones) == 1
        assert svc.found_phones[0].source == 'partial_phone_breach'

    def test_breach_no_match_returns_none(self):
        """LeakDB returns phones that don't match the pattern."""
        svc = ContactDiscoveryService()
        svc.found_emails.append(DiscoveredEmail(
            email='test@mail.ru',
            source='vk_profile',
            confidence='высокая',
            verified=False,
            profile_name='Test',
            confidence_score=0.95,
            sources=['vk_profile'],
        ))

        mock_db = MagicMock()
        mock_db.query_email.return_value = [
            {'phone': '+79171234567', 'email': 'test@mail.ru'},  # 917 not 916
        ]
        mock_db.query_name.return_value = []

        mock_check = MagicMock()
        mock_check.full_name = 'Иванов Иван'

        pattern = ContactDiscoveryService._build_phone_pattern('+7 916 ***-**-67')

        with patch(self.LEAK_DB_PATCH) as MockLeakDB:
            MockLeakDB.get_instance.return_value = mock_db
            result = svc._breach_db_phone_match(mock_check, pattern, '+7 916 ***-**-67')

        assert result is None
        assert len(svc.found_phones) == 0

    def test_breach_match_by_name(self):
        """LeakDB name query returns matching phone when email query doesn't."""
        svc = ContactDiscoveryService()

        mock_db = MagicMock()
        mock_db.query_email.return_value = []
        mock_db.query_name.return_value = [
            {'phone': '+79161114567', 'name': 'Иванов Иван', 'source': 'getcontact'},
        ]

        mock_check = MagicMock()
        mock_check.full_name = 'Иванов Иван'

        pattern = ContactDiscoveryService._build_phone_pattern('+7 916 ***-45-67')

        with patch(self.LEAK_DB_PATCH) as MockLeakDB:
            MockLeakDB.get_instance.return_value = mock_db
            result = svc._breach_db_phone_match(mock_check, pattern, '+7 916 ***-45-67')

        assert result == '+79161114567'


# ---------------------------------------------------------------------------
# _getcontact_phone_match
# ---------------------------------------------------------------------------

class TestGetContactPhoneMatch:
    """Test GetContact cross-referencing for partial phone completion."""

    GC_SOURCE_PATCH = 'app.services.phase2.sources.getcontact.GetContactSource'
    GC_API_PATCH = 'app.services.phase2.sources.getcontact.GetContactAPI'

    def test_getcontact_not_configured_returns_none(self):
        svc = ContactDiscoveryService()
        mock_check = MagicMock()
        mock_check.full_name = 'Иванов Иван'
        pattern = ContactDiscoveryService._build_phone_pattern('+7 916 123-45-6*')

        with patch(
            self.GC_SOURCE_PATCH
        ) as MockGC:
            mock_gc = MagicMock()
            mock_gc._get_credentials.return_value = None
            MockGC.return_value = mock_gc

            result = svc._getcontact_phone_match(mock_check, pattern, '+7 916 123-45-6*')

        assert result is None

    def test_getcontact_name_match_confirms_phone(self):
        svc = ContactDiscoveryService()
        mock_check = MagicMock()
        mock_check.full_name = 'Иванов Иван'

        pattern = ContactDiscoveryService._build_phone_pattern('+7 916 123-45-6*')

        with patch(
            self.GC_SOURCE_PATCH
        ) as MockGC, patch(
            self.GC_API_PATCH
        ) as MockAPI:
            mock_gc = MagicMock()
            mock_gc._get_credentials.return_value = ('token', 'aes_key', 'device_id')
            MockGC.return_value = mock_gc

            mock_api = MagicMock()
            # Only the correct phone returns a matching name
            def search_phone_side_effect(phone):
                if phone == '+79161234567':
                    return {
                        'result': {
                            'profile': {'displayName': 'Иванов Иван Петрович'},
                        },
                    }
                return None

            mock_api.search_phone.side_effect = search_phone_side_effect
            MockAPI.return_value = mock_api

            result = svc._getcontact_phone_match(mock_check, pattern, '+7 916 123-45-6*')

        assert result == '+79161234567'
        assert len(svc.found_phones) == 1
        assert svc.found_phones[0].source == 'partial_phone_getcontact'

    def test_getcontact_no_name_match_returns_none(self):
        svc = ContactDiscoveryService()
        mock_check = MagicMock()
        mock_check.full_name = 'Иванов Иван'

        pattern = ContactDiscoveryService._build_phone_pattern('+7 916 123-45-6*')

        with patch(
            self.GC_SOURCE_PATCH
        ) as MockGC, patch(
            self.GC_API_PATCH
        ) as MockAPI:
            mock_gc = MagicMock()
            mock_gc._get_credentials.return_value = ('token', 'aes_key', 'device_id')
            MockGC.return_value = mock_gc

            mock_api = MagicMock()
            # All phones return a different name
            mock_api.search_phone.return_value = {
                'result': {
                    'profile': {'displayName': 'Петров Сергей'},
                },
            }
            MockAPI.return_value = mock_api

            result = svc._getcontact_phone_match(mock_check, pattern, '+7 916 123-45-6*')

        assert result is None

    def test_getcontact_too_many_unknowns_returns_none(self):
        """3+ unknown digits → no candidates → returns None."""
        svc = ContactDiscoveryService()
        mock_check = MagicMock()
        mock_check.full_name = 'Иванов Иван'

        pattern = ContactDiscoveryService._build_phone_pattern('+7 916 ***-**-67')

        with patch(
            self.GC_SOURCE_PATCH
        ) as MockGC:
            mock_gc = MagicMock()
            mock_gc._get_credentials.return_value = ('token', 'aes_key', 'device_id')
            MockGC.return_value = mock_gc

            result = svc._getcontact_phone_match(mock_check, pattern, '+7 916 ***-**-67')

        assert result is None


# ---------------------------------------------------------------------------
# _cross_reference_partial_phones (full integration)
# ---------------------------------------------------------------------------

class TestCrossReferencePartialPhones:
    """Test the full step 8.5 cross-reference flow."""

    def test_no_oracle_results_skips(self):
        svc = ContactDiscoveryService()
        mock_check = MagicMock()
        mock_check.full_name = 'Иванов Иван'
        # No oracle results → should not crash
        svc._cross_reference_partial_phones(mock_check)
        assert len(svc.found_phones) == 0

    def test_no_partial_hints_skips(self):
        """Oracle results with no masked hints → skip."""
        svc = ContactDiscoveryService()
        svc._oracle_results = [
            {'service': 'vk', 'exists': True, 'hint_type': 'email',
             'masked_hint': 'i***v@mail.ru', 'error': None},
        ]
        mock_check = MagicMock()
        mock_check.full_name = 'Иванов Иван'
        svc._cross_reference_partial_phones(mock_check)
        assert len(svc.found_phones) == 0

    def test_fully_merged_phone_added_directly(self):
        """All digits known from merging → add without DB lookup."""
        svc = ContactDiscoveryService()
        # 11 unique hints that together reveal all digits
        svc._oracle_results = [
            {'service': 'vk', 'exists': True, 'hint_type': 'phone',
             'masked_hint': '+7 916 123-45-67', 'error': None, 'confidence': 0.85},
        ]
        # Even though the hint has no stars, let's use a hint with all digits:
        # This won't have '*' so it will be skipped... let's test with actual partial
        svc._oracle_results = [
            {'service': 'vk', 'exists': True, 'hint_type': 'phone',
             'masked_hint': '+7 916 ***-**-67', 'error': None, 'confidence': 0.85},
            {'service': 'yandex', 'exists': True, 'hint_type': 'phone',
             'masked_hint': '+7 *** 123-45-**', 'error': None, 'confidence': 0.83},
        ]
        # Merged = +7 916 123-45-67 (all 11 digits known, no stars)

        mock_check = MagicMock()
        mock_check.full_name = 'Иванов Иван'

        svc._cross_reference_partial_phones(mock_check)

        assert len(svc.found_phones) == 1
        assert svc.found_phones[0].number == '+79161234567'
        assert svc.found_phones[0].source == 'partial_phone_breach'

    def test_breach_db_completes_partial(self):
        """Breach DB returns a phone matching the partial pattern."""
        svc = ContactDiscoveryService()
        svc._oracle_results = [
            {'service': 'vk', 'exists': True, 'hint_type': 'phone',
             'masked_hint': '+7 916 ***-**-67', 'error': None, 'confidence': 0.85},
            {'service': 'mailru', 'exists': True, 'hint_type': 'phone',
             'masked_hint': '+7 916 ***-**-67', 'error': None, 'confidence': 0.80},
        ]
        svc.found_emails.append(DiscoveredEmail(
            email='test@mail.ru', source='input', confidence='высокая',
            verified=False, profile_name='Input',
            confidence_score=0.99, sources=['input'],
        ))

        mock_check = MagicMock()
        mock_check.full_name = 'Иванов Иван'

        mock_db = MagicMock()
        mock_db.query_email.return_value = [
            {'phone': '+79161234567', 'email': 'test@mail.ru'},
        ]
        mock_db.query_name.return_value = []

        with patch(
            'app.services.phase2.sources.leak_sources.LeakDB'
        ) as MockLeakDB:
            MockLeakDB.get_instance.return_value = mock_db
            svc._cross_reference_partial_phones(mock_check)

        assert any(
            p.number == '+79161234567' and p.source == 'partial_phone_breach'
            for p in svc.found_phones
        )


# ---------------------------------------------------------------------------
# Confidence scores
# ---------------------------------------------------------------------------

class TestConfidenceScores:
    """Test that new confidence score keys exist and are correct."""

    def test_partial_phone_breach_score(self):
        assert CONFIDENCE_SCORES['partial_phone_breach'] == 0.95

    def test_partial_phone_getcontact_score(self):
        assert CONFIDENCE_SCORES['partial_phone_getcontact'] == 0.90

    def test_breach_higher_than_getcontact(self):
        assert CONFIDENCE_SCORES['partial_phone_breach'] > CONFIDENCE_SCORES['partial_phone_getcontact']

    def test_breach_lower_than_input(self):
        assert CONFIDENCE_SCORES['partial_phone_breach'] < CONFIDENCE_SCORES['input']
