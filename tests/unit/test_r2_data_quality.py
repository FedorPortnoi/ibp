"""
Round 2 TDD Sprint — Data Quality Validation Tests
====================================================
150+ tests verifying data normalization, formatting consistency,
confidence scoring, deduplication, cross-validation, serialization,
and edge-case handling across all Phase 2 services.

Tests ONLY existing functionality — no source modifications.
"""

import json
import os
import re
import pytest

os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-unit-tests')

from app.utils.phone import normalize_phone
from app.services.phase2.russian_phone_validator import (
    RussianPhoneValidator,
    PhoneInfo,
    CARRIER_PREFIXES,
    CITY_CODES,
    validate_phone,
    extract_phones_from_text,
)
from app.services.phase2.email_discovery import (
    EmailDiscoveryService,
    DiscoveredEmail,
    RUSSIAN_EMAIL_DOMAINS,
    SMTP_BLOCKED_DOMAINS,
    CATCH_ALL_DOMAINS,
)
from app.services.phase2.base_source import (
    SourceResult,
    SourceTier,
    SourceType,
)
from app.services.phase2.source_manager import SourceManager
from app.services.phase2.phone_discovery import (
    PhoneDiscoveryService,
    DiscoveredPhone,
)


# =====================================================================
# 1. Phone Display Format Consistency  (25+ tests)
# =====================================================================

class TestPhoneDisplayFormatConsistency:
    """All validated phones must produce consistent display formatting."""

    DISPLAY_PATTERN = re.compile(r'^\+7 \(\d{3}\) \d{3}-\d{2}-\d{2}$')

    def setup_method(self):
        self.validator = RussianPhoneValidator()

    # -- Various input formats all produce same display output --

    def test_display_from_plus7_parentheses(self):
        info = self.validator.validate("+7 (916) 123-45-67")
        assert self.DISPLAY_PATTERN.match(info.display_format)
        assert info.display_format == "+7 (916) 123-45-67"

    def test_display_from_eight_dashes(self):
        info = self.validator.validate("8-916-123-45-67")
        assert self.DISPLAY_PATTERN.match(info.display_format)
        assert info.display_format == "+7 (916) 123-45-67"

    def test_display_from_plus7_spaces(self):
        info = self.validator.validate("+7 916 1234567")
        assert self.DISPLAY_PATTERN.match(info.display_format)

    def test_display_from_raw_digits_11(self):
        info = self.validator.validate("89161234567")
        assert self.DISPLAY_PATTERN.match(info.display_format)
        assert info.display_format == "+7 (916) 123-45-67"

    def test_display_from_raw_digits_10(self):
        info = self.validator.validate("9161234567")
        assert self.DISPLAY_PATTERN.match(info.display_format)
        assert info.display_format == "+7 (916) 123-45-67"

    def test_display_from_already_normalized(self):
        info = self.validator.validate("+79161234567")
        assert self.DISPLAY_PATTERN.match(info.display_format)

    def test_display_from_mixed_separators(self):
        info = self.validator.validate("+7(916)123 45 67")
        assert self.DISPLAY_PATTERN.match(info.display_format)

    def test_display_from_seven_prefix_no_plus(self):
        info = self.validator.validate("79161234567")
        assert self.DISPLAY_PATTERN.match(info.display_format)

    def test_all_formats_produce_identical_display(self):
        """Multiple input formats must converge to the exact same display string."""
        formats = [
            "+7 (916) 123-45-67",
            "8-916-123-45-67",
            "89161234567",
            "+79161234567",
            "79161234567",
            "9161234567",
            "+7-916-123-45-67",
            "8(916)1234567",
        ]
        displays = set()
        for fmt in formats:
            info = self.validator.validate(fmt)
            if info.is_valid:
                displays.add(info.display_format)
        assert len(displays) == 1, f"Expected one display, got {displays}"

    # -- Carrier detection consistency --

    def test_carrier_consistent_for_mts_prefix(self):
        """All MTS prefixes must produce carrier_hint='MTS'."""
        for prefix in CARRIER_PREFIXES['MTS']:
            info = self.validator.validate(f"+7{prefix}1234567")
            assert info.carrier_hint == 'MTS', f"Prefix {prefix} expected MTS, got {info.carrier_hint}"

    def test_carrier_consistent_for_beeline_prefix(self):
        for prefix in CARRIER_PREFIXES['Beeline']:
            info = self.validator.validate(f"+7{prefix}1234567")
            assert info.carrier_hint == 'Beeline', f"Prefix {prefix} expected Beeline"

    def test_carrier_consistent_for_megafon_prefix(self):
        for prefix in CARRIER_PREFIXES['Megafon']:
            info = self.validator.validate(f"+7{prefix}1234567")
            assert info.carrier_hint == 'Megafon', f"Prefix {prefix} expected Megafon"

    def test_carrier_consistent_for_tele2_prefix(self):
        for prefix in CARRIER_PREFIXES['Tele2']:
            info = self.validator.validate(f"+7{prefix}1234567")
            assert info.carrier_hint == 'Tele2', f"Prefix {prefix} expected Tele2"

    def test_carrier_consistent_for_yota_prefix(self):
        for prefix in CARRIER_PREFIXES['Yota']:
            info = self.validator.validate(f"+7{prefix}1234567")
            assert info.carrier_hint == 'Yota', f"Prefix {prefix} expected Yota"

    def test_carrier_consistent_for_rostelecom_prefix(self):
        for prefix in CARRIER_PREFIXES['Rostelecom']:
            info = self.validator.validate(f"+7{prefix}1234567")
            assert info.carrier_hint == 'Rostelecom', f"Prefix {prefix} expected Rostelecom"

    # -- Region consistency for landlines --

    def test_region_moscow_495(self):
        info = self.validator.validate("+74951234567")
        assert info.region == 'Moscow'
        assert info.format_type == 'landline'
        assert info.is_mobile is False

    def test_region_moscow_499(self):
        info = self.validator.validate("+74991234567")
        assert info.region == 'Moscow'

    def test_region_spb_812(self):
        info = self.validator.validate("+78121234567")
        assert info.region == 'Saint Petersburg'

    def test_region_consistent_regardless_of_input_format(self):
        """Same city code via different formats yields same region."""
        formats = ["+74951234567", "84951234567", "4951234567"]
        regions = set()
        for fmt in formats:
            info = self.validator.validate(fmt)
            if info.is_valid:
                regions.add(info.region)
        assert regions == {'Moscow'}

    def test_mobile_has_no_region(self):
        info = self.validator.validate("+79161234567")
        assert info.region is None
        assert info.is_mobile is True

    def test_landline_without_known_city_code_has_no_region(self):
        """Landline prefix not in CITY_CODES returns region=None."""
        info = self.validator.validate("+71001234567")
        assert info.is_mobile is False
        assert info.region is None  # 100 not in CITY_CODES

    # -- Format type field consistency --

    def test_format_type_mobile(self):
        info = self.validator.validate("+79161234567")
        assert info.format_type == 'mobile'

    def test_format_type_landline(self):
        info = self.validator.validate("+74951234567")
        assert info.format_type == 'landline'

    def test_format_type_unknown_for_invalid(self):
        info = self.validator.validate("123")
        assert info.format_type == 'unknown'

    def test_invalid_phone_returns_original_as_display(self):
        info = self.validator.validate("not-a-phone")
        assert info.display_format == "not-a-phone"
        assert info.is_valid is False


# =====================================================================
# 2. Email Normalization Quality  (25+ tests)
# =====================================================================

class TestEmailNormalizationQuality:
    """Email generation/validation produces clean, consistent output."""

    def setup_method(self):
        self.service = EmailDiscoveryService()

    # -- All emails must be lowercase --

    def test_candidates_are_lowercase(self):
        candidates = self.service._generate_candidates("Иван", "Петров", [])
        for c in candidates:
            assert c == c.lower(), f"Candidate not lowercase: {c}"

    def test_candidates_lowercase_with_mixed_case_input(self):
        candidates = self.service._generate_candidates("МАРИЯ", "ИВАНОВА", [])
        for c in candidates:
            assert c == c.lower()

    # -- Username cleaning --

    def test_clean_username_strips_id_prefix(self):
        assert self.service._clean_username("id12345") == "12345"

    def test_clean_username_strips_user_prefix(self):
        assert self.service._clean_username("user_john") == "_john"

    def test_clean_username_strips_profile_prefix(self):
        assert self.service._clean_username("profiletest") == "test"

    def test_clean_username_strips_at_prefix(self):
        assert self.service._clean_username("@johndoe") == "johndoe"

    def test_clean_username_removes_special_chars(self):
        assert self.service._clean_username("john!@#doe") == "johndoe"

    def test_clean_username_keeps_dots_and_underscores(self):
        result = self.service._clean_username("john.doe_123")
        assert result == "john.doe_123"

    def test_clean_username_lowercases(self):
        assert self.service._clean_username("JohnDoe") == "johndoe"

    def test_clean_username_cyrillic_removed(self):
        """Cyrillic chars should be removed since regex keeps only [a-z0-9_.]."""
        result = self.service._clean_username("иван123")
        assert result == "123"

    # -- Transliteration consistency --

    def test_transliterate_basic_name(self):
        assert self.service._transliterate("иван") == "ivan"

    def test_transliterate_complex_chars(self):
        result = self.service._transliterate("щука")
        assert result == "schuka"

    def test_transliterate_yo(self):
        """Ё should transliterate to 'e'."""
        assert self.service._transliterate("ё") == "e"

    def test_transliterate_soft_hard_signs(self):
        """Ъ and Ь should transliterate to empty string."""
        assert self.service._transliterate("ъ") == ""
        assert self.service._transliterate("ь") == ""

    def test_transliterate_passes_through_latin(self):
        assert self.service._transliterate("john") == "john"

    def test_transliterate_passes_through_digits(self):
        assert self.service._transliterate("иван123") == "ivan123"

    def test_transliterate_mixed_cyrillic_latin(self):
        result = self.service._transliterate("ivan иван")
        assert result == "ivan ivan"

    def test_transliterate_idempotent_on_latin(self):
        """Double-transliterating Latin text should not change it."""
        text = "alexey"
        assert self.service._transliterate(self.service._transliterate(text)) == text

    def test_transliterate_all_33_cyrillic_chars(self):
        """Every Cyrillic character must have a mapping."""
        cyrillic = "абвгдеёжзийклмнопрстуфхцчшщъыьэюя"
        result = self.service._transliterate(cyrillic)
        # No original Cyrillic characters should remain
        for ch in result:
            assert ch not in cyrillic, f"Char '{ch}' not transliterated"

    # -- Email validation --

    def test_valid_email_accepted(self):
        assert self.service._is_valid_email("test@mail.ru") is True

    def test_valid_email_with_dots(self):
        assert self.service._is_valid_email("first.last@gmail.com") is True

    def test_valid_email_with_hyphens(self):
        assert self.service._is_valid_email("first-last@mail.ru") is True

    def test_valid_email_with_underscore(self):
        assert self.service._is_valid_email("first_last@mail.ru") is True

    def test_invalid_email_no_at(self):
        assert self.service._is_valid_email("testmail.ru") is False

    def test_invalid_email_no_domain(self):
        assert self.service._is_valid_email("test@") is False

    def test_invalid_email_no_tld(self):
        assert self.service._is_valid_email("test@mail") is False

    def test_invalid_email_single_char_tld(self):
        assert self.service._is_valid_email("test@mail.r") is False

    def test_invalid_email_starts_with_dot(self):
        assert self.service._is_valid_email(".test@mail.ru") is False

    def test_invalid_email_starts_with_hyphen(self):
        assert self.service._is_valid_email("-test@mail.ru") is False

    def test_invalid_email_too_long(self):
        """Email exceeding 254 chars should be rejected."""
        # 254 - len("@mail.ru") = 246; use 247 chars to exceed 254 total
        local = "a" * 247
        email = f"{local}@mail.ru"  # 247 + 8 = 255 > 254
        assert self.service._is_valid_email(email) is False

    def test_valid_email_at_254_chars(self):
        """Email at exactly 254 chars should be accepted."""
        local = "a" * (254 - len("@mail.ru"))  # 246 chars
        email = f"{local}@mail.ru"  # 246 + 8 = 254
        assert len(email) == 254
        assert self.service._is_valid_email(email) is True

    # -- No duplicate candidates for same name --

    def test_no_duplicate_candidates(self):
        candidates = self.service._generate_candidates("Иван", "Петров", ["ivanpetrov"])
        assert len(candidates) == len(set(candidates))

    def test_candidates_cover_all_russian_domains(self):
        """At least some candidates should cover popular Russian domains."""
        candidates = self.service._generate_candidates("Иван", "Петров", [])
        domains = {c.split("@")[1] for c in candidates}
        # Should cover at least a few of the RUSSIAN_EMAIL_DOMAINS
        assert len(domains) >= 3


# =====================================================================
# 3. Confidence Score Quality  (25+ tests)
# =====================================================================

class TestConfidenceScoreQuality:
    """Confidence must be 0.0-1.0, labels correct at boundaries."""

    def _make_result(self, confidence, **kwargs):
        return SourceResult(
            data_type=kwargs.get('data_type', 'email'),
            value=kwargs.get('value', 'test@mail.ru'),
            source_name=kwargs.get('source_name', 'Test Source'),
            source_tier=kwargs.get('source_tier', SourceTier.B),
            confidence=confidence,
        )

    # -- confidence_label boundary tests --

    def test_label_very_high_at_1_0(self):
        assert self._make_result(1.0).confidence_label == "very_high"

    def test_label_very_high_at_0_9(self):
        assert self._make_result(0.9).confidence_label == "very_high"

    def test_label_very_high_at_0_95(self):
        assert self._make_result(0.95).confidence_label == "very_high"

    def test_label_high_at_0_89999(self):
        assert self._make_result(0.89999).confidence_label == "high"

    def test_label_high_at_0_7(self):
        assert self._make_result(0.7).confidence_label == "high"

    def test_label_high_at_0_85(self):
        assert self._make_result(0.85).confidence_label == "high"

    def test_label_medium_at_0_69999(self):
        assert self._make_result(0.69999).confidence_label == "medium"

    def test_label_medium_at_0_5(self):
        assert self._make_result(0.5).confidence_label == "medium"

    def test_label_medium_at_0_6(self):
        assert self._make_result(0.6).confidence_label == "medium"

    def test_label_low_at_0_49999(self):
        assert self._make_result(0.49999).confidence_label == "low"

    def test_label_low_at_0_0(self):
        assert self._make_result(0.0).confidence_label == "low"

    def test_label_low_at_0_1(self):
        assert self._make_result(0.1).confidence_label == "low"

    def test_label_low_at_0_3(self):
        assert self._make_result(0.3).confidence_label == "low"

    # -- Range enforcement --

    def test_confidence_at_exact_zero(self):
        r = self._make_result(0.0)
        assert r.confidence == 0.0
        assert r.confidence_label == "low"

    def test_confidence_at_exact_one(self):
        r = self._make_result(1.0)
        assert r.confidence == 1.0
        assert r.confidence_label == "very_high"

    # -- Dedup boost never exceeds 1.0 --

    def test_dedup_boost_caps_at_1_0(self):
        """Deduplication with high initial confidence must not exceed 1.0."""
        mgr = SourceManager.__new__(SourceManager)
        mgr.sources = []

        results = [
            self._make_result(0.95, value='test@mail.ru', source_name='Source1'),
            self._make_result(0.95, value='test@mail.ru', source_name='Source2'),
            self._make_result(0.95, value='test@mail.ru', source_name='Source3'),
            self._make_result(0.95, value='test@mail.ru', source_name='Source4'),
        ]
        deduped = mgr._deduplicate(results)
        assert len(deduped) == 1
        assert deduped[0].confidence <= 1.0

    def test_dedup_multiple_boosts_still_capped(self):
        """Even with 10 sources, confidence must not exceed 1.0."""
        mgr = SourceManager.__new__(SourceManager)
        mgr.sources = []

        results = [
            self._make_result(0.8, value='phone@test.ru', source_name=f'Source{i}')
            for i in range(10)
        ]
        deduped = mgr._deduplicate(results)
        assert len(deduped) == 1
        assert deduped[0].confidence <= 1.0

    def test_dedup_boost_increases_confidence(self):
        """Second source should increase confidence above original."""
        mgr = SourceManager.__new__(SourceManager)
        mgr.sources = []

        original_conf = 0.5
        results = [
            self._make_result(original_conf, value='x@mail.ru', source_name='Src1'),
            self._make_result(0.5, value='x@mail.ru', source_name='Src2'),
        ]
        deduped = mgr._deduplicate(results)
        assert deduped[0].confidence > original_conf

    def test_dedup_boost_formula_correct(self):
        """Verify the boost formula: min(0.15, (1.0 - existing) * 0.5)."""
        mgr = SourceManager.__new__(SourceManager)
        mgr.sources = []

        results = [
            self._make_result(0.6, value='a@b.ru', source_name='S1'),
            self._make_result(0.6, value='a@b.ru', source_name='S2'),
        ]
        deduped = mgr._deduplicate(results)
        # boost = min(0.15, (1.0 - 0.6) * 0.5) = min(0.15, 0.2) = 0.15
        expected = min(1.0, 0.6 + 0.15)
        assert abs(deduped[0].confidence - expected) < 1e-9

    def test_dedup_boost_small_when_confidence_high(self):
        """When confidence is 0.95, boost = min(0.15, 0.05*0.5) = 0.025."""
        mgr = SourceManager.__new__(SourceManager)
        mgr.sources = []

        results = [
            self._make_result(0.95, value='a@b.ru', source_name='S1'),
            self._make_result(0.95, value='a@b.ru', source_name='S2'),
        ]
        deduped = mgr._deduplicate(results)
        expected = min(1.0, 0.95 + min(0.15, (1.0 - 0.95) * 0.5))
        assert abs(deduped[0].confidence - expected) < 1e-9

    def test_zero_confidence_boost(self):
        """Even zero-confidence result should get boosted by second source."""
        mgr = SourceManager.__new__(SourceManager)
        mgr.sources = []

        results = [
            self._make_result(0.0, value='a@b.ru', source_name='S1'),
            self._make_result(0.0, value='a@b.ru', source_name='S2'),
        ]
        deduped = mgr._deduplicate(results)
        # boost = min(0.15, (1.0 - 0.0) * 0.5) = 0.15
        assert abs(deduped[0].confidence - 0.15) < 1e-9

    def test_confidence_label_after_boost(self):
        """Boosted confidence should change label appropriately."""
        mgr = SourceManager.__new__(SourceManager)
        mgr.sources = []

        results = [
            self._make_result(0.45, value='a@b.ru', source_name='S1'),
            self._make_result(0.45, value='a@b.ru', source_name='S2'),
        ]
        deduped = mgr._deduplicate(results)
        # 0.45 + 0.15 = 0.60 -> "medium"
        assert deduped[0].confidence_label == "medium"


# =====================================================================
# 4. Deduplication Quality  (25+ tests)
# =====================================================================

class TestDeduplicationQuality:
    """Dedup must be case-insensitive, whitespace-tolerant, and track sources."""

    def _make_result(self, data_type, value, source_name, confidence=0.7, tier=SourceTier.B):
        return SourceResult(
            data_type=data_type,
            value=value,
            source_name=source_name,
            source_tier=tier,
            confidence=confidence,
        )

    def _deduplicate(self, results):
        mgr = SourceManager.__new__(SourceManager)
        mgr.sources = []
        return mgr._deduplicate(results)

    # -- Case-insensitive dedup --

    def test_email_case_insensitive_dedup(self):
        results = [
            self._make_result('email', 'Test@Gmail.COM', 'Src1'),
            self._make_result('email', 'test@gmail.com', 'Src2'),
        ]
        deduped = self._deduplicate(results)
        assert len(deduped) == 1

    def test_email_mixed_case_produces_single_result(self):
        results = [
            self._make_result('email', 'USER@MAIL.RU', 'A'),
            self._make_result('email', 'User@Mail.Ru', 'B'),
            self._make_result('email', 'user@mail.ru', 'C'),
        ]
        deduped = self._deduplicate(results)
        assert len(deduped) == 1

    # -- Whitespace handling --

    def test_whitespace_stripped_in_dedup_key(self):
        results = [
            self._make_result('email', ' test@gmail.com ', 'A'),
            self._make_result('email', 'test@gmail.com', 'B'),
        ]
        deduped = self._deduplicate(results)
        assert len(deduped) == 1

    def test_leading_trailing_whitespace_dedup(self):
        results = [
            self._make_result('phone', '  +79161234567  ', 'A'),
            self._make_result('phone', '+79161234567', 'B'),
        ]
        deduped = self._deduplicate(results)
        assert len(deduped) == 1

    # -- Phone dedup via normalize_key --

    def test_phone_normalize_key_strips_formatting(self):
        """PhoneDiscoveryService._normalize_key extracts last 10 digits."""
        service = PhoneDiscoveryService.__new__(PhoneDiscoveryService)
        key1 = service._normalize_key("+7 (916) 123-45-67")
        key2 = service._normalize_key("89161234567")
        key3 = service._normalize_key("+79161234567")
        assert key1 == key2 == key3

    def test_phone_normalize_key_ten_digit_input(self):
        service = PhoneDiscoveryService.__new__(PhoneDiscoveryService)
        key = service._normalize_key("9161234567")
        assert key == "9161234567"

    def test_phone_normalize_key_with_spaces(self):
        service = PhoneDiscoveryService.__new__(PhoneDiscoveryService)
        key = service._normalize_key("+7 916 123 45 67")
        assert key == "9161234567"

    # -- Source tracking after dedup --

    def test_sources_list_populated_after_dedup(self):
        results = [
            self._make_result('email', 'test@mail.ru', 'LeakCheck'),
            self._make_result('email', 'test@mail.ru', 'Holehe'),
        ]
        deduped = self._deduplicate(results)
        sources = deduped[0].metadata.get('sources', [])
        assert 'LeakCheck' in sources
        assert 'Holehe' in sources

    def test_source_count_accurate(self):
        results = [
            self._make_result('email', 'test@mail.ru', 'A'),
            self._make_result('email', 'test@mail.ru', 'B'),
            self._make_result('email', 'test@mail.ru', 'C'),
        ]
        deduped = self._deduplicate(results)
        assert deduped[0].metadata['source_count'] == 3

    def test_source_count_no_double_counting(self):
        """Same source name appearing twice should not be counted twice."""
        results = [
            self._make_result('email', 'test@mail.ru', 'SameSource'),
            self._make_result('email', 'test@mail.ru', 'SameSource'),
        ]
        deduped = self._deduplicate(results)
        assert deduped[0].metadata['source_count'] == 1

    def test_single_source_has_count_one(self):
        results = [self._make_result('email', 'solo@mail.ru', 'OnlyOne')]
        deduped = self._deduplicate(results)
        assert deduped[0].metadata['source_count'] == 1
        assert deduped[0].metadata['sources'] == ['OnlyOne']

    # -- Tier promotion --

    def test_higher_tier_wins_on_dedup(self):
        results = [
            self._make_result('email', 'test@mail.ru', 'A', tier=SourceTier.C),
            self._make_result('email', 'test@mail.ru', 'B', tier=SourceTier.S),
        ]
        deduped = self._deduplicate(results)
        assert deduped[0].source_tier == SourceTier.S

    def test_tier_stays_if_lower_tier_arrives_second(self):
        results = [
            self._make_result('email', 'test@mail.ru', 'A', tier=SourceTier.S),
            self._make_result('email', 'test@mail.ru', 'B', tier=SourceTier.C),
        ]
        deduped = self._deduplicate(results)
        assert deduped[0].source_tier == SourceTier.S

    # -- Different data types not merged --

    def test_different_data_types_not_merged(self):
        results = [
            self._make_result('email', 'test@mail.ru', 'A'),
            self._make_result('phone', 'test@mail.ru', 'B'),
        ]
        deduped = self._deduplicate(results)
        assert len(deduped) == 2

    def test_different_values_not_merged(self):
        results = [
            self._make_result('email', 'a@mail.ru', 'A'),
            self._make_result('email', 'b@mail.ru', 'A'),
        ]
        deduped = self._deduplicate(results)
        assert len(deduped) == 2

    # -- Metadata merging --

    def test_metadata_merged_from_second_source(self):
        r1 = self._make_result('email', 'test@mail.ru', 'A')
        r1.metadata['breach_name'] = 'LinkedIn'
        r2 = self._make_result('email', 'test@mail.ru', 'B')
        r2.metadata['breach_date'] = '2021-06-05'
        deduped = self._deduplicate([r1, r2])
        assert deduped[0].metadata.get('breach_name') == 'LinkedIn'
        assert deduped[0].metadata.get('breach_date') == '2021-06-05'

    def test_raw_data_merged_from_second_source(self):
        r1 = self._make_result('email', 'test@mail.ru', 'A')
        r1.raw_data['response1'] = 'data1'
        r2 = self._make_result('email', 'test@mail.ru', 'B')
        r2.raw_data['response2'] = 'data2'
        deduped = self._deduplicate([r1, r2])
        assert 'response1' in deduped[0].raw_data
        assert 'response2' in deduped[0].raw_data

    def test_empty_list_dedup(self):
        deduped = self._deduplicate([])
        assert deduped == []

    def test_single_item_dedup(self):
        results = [self._make_result('email', 'x@y.ru', 'A')]
        deduped = self._deduplicate(results)
        assert len(deduped) == 1


# =====================================================================
# 5. Cross-Validation Data Integrity  (20+ tests)
# =====================================================================

class TestCrossValidationIntegrity:
    """Cross-validation sets correct verified flags and metadata."""

    def _make_result(self, data_type, value, source_name, tier=SourceTier.B, confidence=0.7):
        return SourceResult(
            data_type=data_type,
            value=value,
            source_name=source_name,
            source_tier=tier,
            confidence=confidence,
        )

    def _cross_validate(self, results):
        mgr = SourceManager.__new__(SourceManager)
        mgr.sources = []
        return mgr._cross_validate(results)

    def _deduplicate_and_validate(self, results):
        mgr = SourceManager.__new__(SourceManager)
        mgr.sources = []
        deduped = mgr._deduplicate(results)
        return mgr._cross_validate(deduped)

    # -- Tier S cross-validation --

    def test_tier_s_phone_and_email_both_verified(self):
        results = [
            self._make_result('phone', '+79161234567', 'Breach1', tier=SourceTier.S),
            self._make_result('email', 'test@mail.ru', 'Breach2', tier=SourceTier.S),
        ]
        validated = self._cross_validate(results)
        phone = [r for r in validated if r.data_type == 'phone'][0]
        email = [r for r in validated if r.data_type == 'email'][0]
        assert phone.verified is True
        assert email.verified is True

    def test_tier_s_cross_validated_with_metadata(self):
        results = [
            self._make_result('phone', '+79161234567', 'B1', tier=SourceTier.S),
            self._make_result('email', 'x@mail.ru', 'B2', tier=SourceTier.S),
        ]
        validated = self._cross_validate(results)
        phone = [r for r in validated if r.data_type == 'phone'][0]
        email = [r for r in validated if r.data_type == 'email'][0]
        assert phone.metadata.get('cross_validated_with') == 'email_breach'
        assert email.metadata.get('cross_validated_with') == 'phone_breach'

    def test_tier_a_not_cross_validated(self):
        """Tier A phone + email should NOT trigger cross-validation."""
        results = [
            self._make_result('phone', '+79161234567', 'B1', tier=SourceTier.A),
            self._make_result('email', 'x@mail.ru', 'B2', tier=SourceTier.A),
        ]
        validated = self._cross_validate(results)
        phone = [r for r in validated if r.data_type == 'phone'][0]
        assert 'cross_validated_with' not in phone.metadata

    def test_mixed_tier_s_and_a_no_cross_validation(self):
        """One Tier S + one Tier A should NOT trigger Tier S cross-validation."""
        results = [
            self._make_result('phone', '+79161234567', 'B1', tier=SourceTier.S),
            self._make_result('email', 'x@mail.ru', 'B2', tier=SourceTier.A),
        ]
        validated = self._cross_validate(results)
        phone = [r for r in validated if r.data_type == 'phone'][0]
        # phone from tier S but email from tier A -> no email_breach cross-validation
        assert phone.metadata.get('cross_validated_with') is None

    # -- Multi-source confirmation --

    def test_three_sources_verified(self):
        r = self._make_result('email', 'test@mail.ru', 'A', confidence=0.5)
        r.metadata['source_count'] = 3
        validated = self._cross_validate([r])
        assert r.verified is True
        assert r.metadata['verified_reason'] == 'confirmed_by_3_sources'

    def test_five_sources_verified(self):
        r = self._make_result('email', 'test@mail.ru', 'A', confidence=0.5)
        r.metadata['source_count'] = 5
        validated = self._cross_validate([r])
        assert r.verified is True
        assert r.metadata['verified_reason'] == 'confirmed_by_5_sources'

    def test_two_sources_high_confidence_verified(self):
        r = self._make_result('email', 'test@mail.ru', 'A', confidence=0.7)
        r.metadata['source_count'] = 2
        validated = self._cross_validate([r])
        assert r.verified is True
        assert r.metadata['verified_reason'] == 'dual_source_high_confidence'

    def test_two_sources_low_confidence_not_verified(self):
        r = self._make_result('email', 'test@mail.ru', 'A', confidence=0.5)
        r.metadata['source_count'] = 2
        validated = self._cross_validate([r])
        assert r.verified is False

    def test_two_sources_at_boundary_0_7_verified(self):
        r = self._make_result('email', 'test@mail.ru', 'A', confidence=0.7)
        r.metadata['source_count'] = 2
        validated = self._cross_validate([r])
        assert r.verified is True

    def test_two_sources_at_0_69_not_verified(self):
        r = self._make_result('email', 'test@mail.ru', 'A', confidence=0.69)
        r.metadata['source_count'] = 2
        validated = self._cross_validate([r])
        assert r.verified is False

    def test_one_source_not_verified_by_count(self):
        r = self._make_result('email', 'test@mail.ru', 'A', confidence=0.99)
        r.metadata['source_count'] = 1
        validated = self._cross_validate([r])
        # Should not be verified by source count alone (only 1 source)
        assert r.metadata.get('verified_reason') is None

    def test_no_source_count_not_verified(self):
        """Result without source_count metadata defaults to 1."""
        r = self._make_result('email', 'test@mail.ru', 'A', confidence=0.99)
        # No source_count in metadata
        validated = self._cross_validate([r])
        assert r.metadata.get('verified_reason') is None

    def test_cross_validate_preserves_all_results(self):
        """Cross-validation should not drop any results."""
        results = [
            self._make_result('phone', '+79161234567', 'A'),
            self._make_result('email', 'a@b.ru', 'B'),
            self._make_result('phone', '+79262345678', 'C'),
        ]
        validated = self._cross_validate(results)
        assert len(validated) == 3

    # -- Full pipeline: dedup + cross-validate --

    def test_full_pipeline_three_sources_same_email(self):
        """Three different sources for same email -> verified after dedup + cross-validate."""
        results = [
            self._make_result('email', 'test@mail.ru', 'Source1', confidence=0.5),
            self._make_result('email', 'test@mail.ru', 'Source2', confidence=0.5),
            self._make_result('email', 'test@mail.ru', 'Source3', confidence=0.5),
        ]
        validated = self._deduplicate_and_validate(results)
        assert len(validated) == 1
        assert validated[0].verified is True
        assert validated[0].metadata['source_count'] == 3

    def test_full_pipeline_two_sources_boosted_past_0_7(self):
        """Two sources at 0.6: after dedup boost -> 0.75 -> dual_source_high_confidence."""
        results = [
            self._make_result('email', 'test@mail.ru', 'S1', confidence=0.6),
            self._make_result('email', 'test@mail.ru', 'S2', confidence=0.6),
        ]
        validated = self._deduplicate_and_validate(results)
        assert len(validated) == 1
        # 0.6 + 0.15 = 0.75 >= 0.7 and source_count=2
        assert validated[0].verified is True

    def test_only_phone_tier_s_no_email_no_cross_validation(self):
        """Only phone from Tier S, no email -> no cross_validated_with."""
        results = [
            self._make_result('phone', '+79161234567', 'B1', tier=SourceTier.S),
        ]
        validated = self._cross_validate(results)
        phone = validated[0]
        assert phone.metadata.get('cross_validated_with') is None


# =====================================================================
# 6. Serialization Quality  (15+ tests)
# =====================================================================

class TestSerializationQuality:
    """SourceResult.to_dict() must produce valid, complete, JSON-serializable output."""

    def _make_result(self, **kwargs):
        defaults = {
            'data_type': 'email',
            'value': 'test@mail.ru',
            'source_name': 'TestSource',
            'source_tier': SourceTier.B,
            'confidence': 0.8,
        }
        defaults.update(kwargs)
        return SourceResult(**defaults)

    def test_to_dict_is_json_serializable(self):
        r = self._make_result()
        d = r.to_dict()
        serialized = json.dumps(d)
        assert isinstance(serialized, str)

    def test_to_dict_has_all_required_fields(self):
        d = self._make_result().to_dict()
        required = ['data_type', 'value', 'source_name', 'source_tier',
                     'confidence', 'confidence_label', 'verified', 'metadata']
        for field in required:
            assert field in d, f"Missing field: {field}"

    def test_source_tier_serializes_to_string(self):
        """source_tier should be the .value string, not the enum."""
        d = self._make_result(source_tier=SourceTier.S).to_dict()
        assert d['source_tier'] == 'Breach Database'
        assert isinstance(d['source_tier'], str)

    def test_source_tier_a_serializes(self):
        d = self._make_result(source_tier=SourceTier.A).to_dict()
        assert d['source_tier'] == 'Platform API'

    def test_source_tier_b_serializes(self):
        d = self._make_result(source_tier=SourceTier.B).to_dict()
        assert d['source_tier'] == 'Verification'

    def test_source_tier_c_serializes(self):
        d = self._make_result(source_tier=SourceTier.C).to_dict()
        assert d['source_tier'] == 'Pattern Generation'

    def test_confidence_label_in_to_dict(self):
        d = self._make_result(confidence=0.95).to_dict()
        assert d['confidence_label'] == 'very_high'

    def test_verified_default_false(self):
        d = self._make_result().to_dict()
        assert d['verified'] is False

    def test_verified_true_serializes(self):
        r = self._make_result()
        r.verified = True
        d = r.to_dict()
        assert d['verified'] is True

    def test_metadata_preserved(self):
        r = self._make_result()
        r.metadata = {'breach_name': 'LinkedIn', 'count': 42}
        d = r.to_dict()
        assert d['metadata']['breach_name'] == 'LinkedIn'
        assert d['metadata']['count'] == 42

    def test_special_chars_in_value_preserved(self):
        r = self._make_result(value="user+tag@mail.ru")
        d = r.to_dict()
        assert d['value'] == "user+tag@mail.ru"

    def test_unicode_in_metadata_preserved(self):
        r = self._make_result()
        r.metadata = {'name': 'Иван Петров', 'city': 'Москва'}
        d = r.to_dict()
        serialized = json.dumps(d, ensure_ascii=False)
        assert 'Иван Петров' in serialized
        assert 'Москва' in serialized

    def test_empty_metadata_serializes(self):
        d = self._make_result().to_dict()
        assert d['metadata'] == {}

    def test_raw_data_not_in_to_dict(self):
        """raw_data is intentionally excluded from to_dict for API responses."""
        r = self._make_result()
        r.raw_data = {'secret': 'data'}
        d = r.to_dict()
        assert 'raw_data' not in d

    def test_to_dict_roundtrip_json(self):
        """Serialize to JSON and parse back, values should match."""
        r = self._make_result(confidence=0.75)
        r.metadata = {'key': 'val'}
        d = r.to_dict()
        json_str = json.dumps(d)
        parsed = json.loads(json_str)
        assert parsed['confidence'] == 0.75
        assert parsed['metadata']['key'] == 'val'


# =====================================================================
# 7. Edge Cases in Data Quality  (20+ tests)
# =====================================================================

class TestEdgeCasesDataQuality:
    """Empty strings, None values, long strings, Unicode handling."""

    # -- Empty strings --

    def test_normalize_phone_empty_string(self):
        assert normalize_phone("") == ""

    def test_normalize_phone_none(self):
        assert normalize_phone(None) == ""

    def test_phone_validator_empty_string(self):
        info = validate_phone("")
        assert info.is_valid is False

    def test_phone_validator_whitespace_only(self):
        info = validate_phone("   ")
        assert info.is_valid is False

    def test_email_validation_empty(self):
        svc = EmailDiscoveryService()
        assert svc._is_valid_email("") is False

    def test_email_transliterate_empty(self):
        svc = EmailDiscoveryService()
        assert svc._transliterate("") == ""

    def test_clean_username_empty(self):
        svc = EmailDiscoveryService()
        assert svc._clean_username("") == ""

    # -- Very long strings --

    def test_normalize_phone_very_long_string(self):
        long_str = "8" * 1000
        result = normalize_phone(long_str)
        # Should not crash, returns original since it's not 10 or 11 digits after stripping
        assert isinstance(result, str)

    def test_phone_validator_very_long_string(self):
        info = validate_phone("+" + "7" * 500)
        assert info.is_valid is False

    def test_email_validation_long_local_part(self):
        svc = EmailDiscoveryService()
        long_email = "a" * 300 + "@mail.ru"
        assert svc._is_valid_email(long_email) is False

    def test_transliterate_very_long_string(self):
        svc = EmailDiscoveryService()
        long_cyrillic = "абвгд" * 200  # 1000 chars
        result = svc._transliterate(long_cyrillic)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_extract_phones_from_long_text(self):
        text = "no phones here " * 500
        result = extract_phones_from_text(text)
        assert result == []

    # -- Unicode edge cases --

    def test_transliterate_with_emoji(self):
        svc = EmailDiscoveryService()
        result = svc._transliterate("иван 😀")
        # Emoji should pass through (not in translit_map)
        assert "ivan" in result

    def test_email_with_special_chars_rejected(self):
        svc = EmailDiscoveryService()
        assert svc._is_valid_email("usér@mail.ru") is False

    def test_email_with_umlaut_rejected(self):
        svc = EmailDiscoveryService()
        assert svc._is_valid_email("über@mail.ru") is False

    def test_email_with_tilde_rejected(self):
        svc = EmailDiscoveryService()
        assert svc._is_valid_email("señor@mail.ru") is False

    def test_transliterate_digits_pass_through(self):
        svc = EmailDiscoveryService()
        assert svc._transliterate("12345") == "12345"

    def test_transliterate_punctuation_pass_through(self):
        svc = EmailDiscoveryService()
        result = svc._transliterate("...")
        assert result == "..."

    # -- SourceResult edge cases --

    def test_source_result_empty_value(self):
        r = SourceResult(
            data_type='email', value='', source_name='Test',
            source_tier=SourceTier.C, confidence=0.5,
        )
        d = r.to_dict()
        assert d['value'] == ''

    def test_source_result_confidence_negative_still_labels_low(self):
        """Negative confidence (shouldn't happen but shouldn't crash)."""
        r = SourceResult(
            data_type='email', value='x@y.ru', source_name='Test',
            source_tier=SourceTier.C, confidence=-0.5,
        )
        assert r.confidence_label == "low"

    def test_source_result_confidence_above_one_labels_very_high(self):
        """Confidence > 1.0 (shouldn't happen but shouldn't crash)."""
        r = SourceResult(
            data_type='email', value='x@y.ru', source_name='Test',
            source_tier=SourceTier.C, confidence=1.5,
        )
        assert r.confidence_label == "very_high"

    # -- Phone extraction from text edge cases --

    def test_extract_phones_deduplicates(self):
        """Same phone number in different formats in text yields one result."""
        text = "Call +7 (916) 123-45-67 or 89161234567"
        results = extract_phones_from_text(text)
        normalized = {r.normalized for r in results}
        assert len(normalized) == 1

    def test_extract_phones_from_usernames_empty(self):
        svc = PhoneDiscoveryService.__new__(PhoneDiscoveryService)
        svc.validator = RussianPhoneValidator()
        result = svc._extract_from_usernames([])
        assert result == []

    def test_extract_phones_from_emails_no_phone_in_email(self):
        svc = PhoneDiscoveryService.__new__(PhoneDiscoveryService)
        svc.validator = RussianPhoneValidator()
        result = svc._extract_from_emails(["user@mail.ru"])
        assert result == []

    def test_extract_phones_from_emails_phone_local_part(self):
        """Email like 9161234567@mail.ru should extract a phone."""
        svc = PhoneDiscoveryService.__new__(PhoneDiscoveryService)
        svc.validator = RussianPhoneValidator()
        result = svc._extract_from_emails(["9161234567@mail.ru"])
        assert len(result) == 1
        assert result[0].number == "+79161234567"

    def test_extract_phones_from_emails_11_digit_local(self):
        svc = PhoneDiscoveryService.__new__(PhoneDiscoveryService)
        svc.validator = RussianPhoneValidator()
        result = svc._extract_from_emails(["89161234567@mail.ru"])
        assert len(result) == 1
        assert result[0].number == "+79161234567"

    def test_extract_phones_from_emails_no_at_skipped(self):
        svc = PhoneDiscoveryService.__new__(PhoneDiscoveryService)
        svc.validator = RussianPhoneValidator()
        result = svc._extract_from_emails(["not-an-email"])
        assert result == []

    # -- Phone variant generation --

    def test_generate_variants_valid_phone(self):
        validator = RussianPhoneValidator()
        variants = validator.generate_variants("+79161234567")
        # Should contain multiple format variants
        assert len(variants) >= 5
        # Should include normalized form
        assert "+79161234567" in variants

    def test_generate_variants_invalid_phone(self):
        validator = RussianPhoneValidator()
        variants = validator.generate_variants("123")
        assert variants == ["123"]

    # -- is_russian_mobile static method --

    def test_is_russian_mobile_plus7_9(self):
        assert RussianPhoneValidator.is_russian_mobile("+79161234567") is True

    def test_is_russian_mobile_8_9(self):
        assert RussianPhoneValidator.is_russian_mobile("89161234567") is True

    def test_is_russian_mobile_10_digit(self):
        assert RussianPhoneValidator.is_russian_mobile("9161234567") is True

    def test_is_russian_mobile_landline_false(self):
        assert RussianPhoneValidator.is_russian_mobile("+74951234567") is False

    def test_is_russian_mobile_short_false(self):
        assert RussianPhoneValidator.is_russian_mobile("123") is False


# =====================================================================
# 8. Group By Type Quality  (bonus)
# =====================================================================

class TestGroupByTypeQuality:
    """_group_by_type correctly partitions results."""

    def _make_result(self, data_type, value):
        return SourceResult(
            data_type=data_type, value=value,
            source_name='Test', source_tier=SourceTier.B, confidence=0.7,
        )

    def _group(self, results):
        mgr = SourceManager.__new__(SourceManager)
        mgr.sources = []
        return mgr._group_by_type(results)

    def test_groups_emails_and_phones_separately(self):
        results = [
            self._make_result('email', 'a@b.ru'),
            self._make_result('phone', '+79161234567'),
        ]
        grouped = self._group(results)
        assert 'email' in grouped
        assert 'phone' in grouped
        assert len(grouped['email']) == 1
        assert len(grouped['phone']) == 1

    def test_groups_multiple_same_type(self):
        results = [
            self._make_result('email', 'a@b.ru'),
            self._make_result('email', 'c@d.ru'),
        ]
        grouped = self._group(results)
        assert len(grouped['email']) == 2

    def test_empty_results_empty_groups(self):
        grouped = self._group([])
        assert grouped == {}

    def test_single_type_single_group(self):
        results = [self._make_result('phone', '+79161234567')]
        grouped = self._group(results)
        assert list(grouped.keys()) == ['phone']

    def test_custom_data_type_grouped(self):
        results = [self._make_result('address', '123 Main St')]
        grouped = self._group(results)
        assert 'address' in grouped


# =====================================================================
# 9. DiscoveredPhone / DiscoveredEmail Dataclass Quality
# =====================================================================

class TestDataclassQuality:
    """Verify dataclass defaults and field integrity."""

    def test_discovered_phone_defaults(self):
        dp = DiscoveredPhone(number="+79161234567", source="Test", confidence="high")
        assert dp.verified is False
        assert dp.carrier is None
        assert dp.region is None
        assert dp.telegram_url is None

    def test_discovered_phone_with_carrier(self):
        dp = DiscoveredPhone(
            number="+79161234567", source="Test", confidence="high",
            carrier="MTS", region=None
        )
        assert dp.carrier == "MTS"

    def test_discovered_email_defaults(self):
        de = DiscoveredEmail(email="test@mail.ru", source="Test", confidence="high")
        assert de.verified is False
        assert de.verified_on == []
        assert de.verification == 'unverified'

    def test_discovered_email_verified(self):
        de = DiscoveredEmail(
            email="test@mail.ru", source="Holehe", confidence="high",
            verified=True, verified_on=['holehe:github'], verification='holehe_confirmed'
        )
        assert de.verified is True
        assert 'holehe:github' in de.verified_on

    def test_discovered_email_verified_on_is_independent_list(self):
        """Each instance should have its own verified_on list."""
        de1 = DiscoveredEmail(email="a@b.ru", source="T", confidence="low")
        de2 = DiscoveredEmail(email="c@d.ru", source="T", confidence="low")
        de1.verified_on.append("smtp")
        assert de2.verified_on == []


# =====================================================================
# 10. Domain Lists Consistency
# =====================================================================

class TestDomainListsConsistency:
    """Verify domain lists contain expected entries and no overlaps."""

    def test_russian_email_domains_not_empty(self):
        assert len(RUSSIAN_EMAIL_DOMAINS) >= 7

    def test_smtp_blocked_domains_subset_of_known(self):
        """All SMTP-blocked domains should be recognized domains."""
        for d in SMTP_BLOCKED_DOMAINS:
            assert '.' in d  # Basic format check

    def test_catch_all_domains_are_international(self):
        """Catch-all domains should include major international providers."""
        assert 'gmail.com' in CATCH_ALL_DOMAINS
        assert 'outlook.com' in CATCH_ALL_DOMAINS

    def test_no_overlap_smtp_blocked_and_catch_all(self):
        """No domain should be in both SMTP_BLOCKED and CATCH_ALL."""
        overlap = SMTP_BLOCKED_DOMAINS & CATCH_ALL_DOMAINS
        assert overlap == set(), f"Overlapping domains: {overlap}"

    def test_source_tier_enum_values(self):
        assert SourceTier.S.value == "Breach Database"
        assert SourceTier.A.value == "Platform API"
        assert SourceTier.B.value == "Verification"
        assert SourceTier.C.value == "Pattern Generation"

    def test_source_type_enum_values(self):
        assert SourceType.EMAIL.value == "email"
        assert SourceType.PHONE.value == "phone"
        assert SourceType.BOTH.value == "both"
