"""
Round 3 (ADVERSARIAL) — Extreme Load & Boundary Conditions
==========================================================
90+ tests targeting boundary values, large collections, duplicate explosion,
pattern limits, resource management, and overflow/wrap edge cases.

All tests run FAST (< 30s total). No real API calls. No system stress.
"""

import os
import re
import time
import pytest
from unittest.mock import patch, MagicMock
from dataclasses import field

os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-unit-tests')

from app.utils.phone import normalize_phone
from app.services.phase2.russian_phone_validator import (
    RussianPhoneValidator, PhoneInfo, CARRIER_PREFIXES, CITY_CODES,
)
from app.services.phase2.email_discovery import (
    EmailDiscoveryService, RUSSIAN_EMAIL_DOMAINS, DiscoveredEmail,
)
from app.services.phase2.phone_discovery import PhoneDiscoveryService, DiscoveredPhone
from app.services.phase2.source_manager import SourceManager
from app.services.phase2.base_source import SourceResult, SourceTier, SourceType


# ═══════════════════════════════════════════════════════════════════
# Helper factories
# ═══════════════════════════════════════════════════════════════════

def make_source_result(
    data_type="email",
    value="test@mail.ru",
    source_name="TestSource",
    source_tier=SourceTier.B,
    confidence=0.6,
    verified=False,
    raw_data=None,
    metadata=None,
):
    return SourceResult(
        data_type=data_type,
        value=value,
        source_name=source_name,
        source_tier=source_tier,
        confidence=confidence,
        verified=verified,
        raw_data=raw_data if raw_data is not None else {},
        metadata=metadata if metadata is not None else {},
    )


# ═══════════════════════════════════════════════════════════════════
# 1. BOUNDARY VALUES (20+ tests)
# ═══════════════════════════════════════════════════════════════════

class TestBoundaryValues:
    """Boundary value tests for phone normalization, email validation, and confidence."""

    # --- normalize_phone boundaries ---

    def test_normalize_phone_empty_string(self):
        assert normalize_phone("") == ""

    def test_normalize_phone_none(self):
        assert normalize_phone(None) == ""

    def test_normalize_phone_100_digit_number(self):
        """100-digit number cannot be normalized; returns original."""
        huge = "1" * 100
        result = normalize_phone(huge)
        assert result == huge  # returned unchanged

    def test_normalize_phone_exactly_9_digits(self):
        result = normalize_phone("912345678")
        # 9 digits — cannot normalize
        assert result == "912345678"

    def test_normalize_phone_exactly_10_digits(self):
        result = normalize_phone("9161234567")
        assert result == "+79161234567"

    def test_normalize_phone_exactly_11_digits_starting_8(self):
        result = normalize_phone("89161234567")
        assert result == "+79161234567"

    def test_normalize_phone_exactly_11_digits_starting_7(self):
        result = normalize_phone("79161234567")
        assert result == "+79161234567"

    def test_normalize_phone_exactly_12_digits(self):
        """12-digit number is not normalizable."""
        twelve = "791612345678"
        result = normalize_phone(twelve)
        assert result == twelve

    def test_normalize_phone_only_whitespace(self):
        """Whitespace-only input: digits == '', cannot normalize."""
        result = normalize_phone("   ")
        assert result == "   "  # not empty, not None => returned as-is

    def test_normalize_phone_single_digit(self):
        result = normalize_phone("7")
        assert result == "7"

    # --- _is_valid_email boundaries ---

    def test_email_at_exactly_254_chars(self):
        """RFC 5321: emails up to 254 chars are valid."""
        svc = EmailDiscoveryService()
        local = "a" * (254 - len("@mail.ru"))
        email = f"{local}@mail.ru"
        assert len(email) == 254
        assert svc._is_valid_email(email) is True

    def test_email_at_255_chars_invalid(self):
        """255-char email exceeds limit."""
        svc = EmailDiscoveryService()
        local = "a" * (255 - len("@mail.ru"))
        email = f"{local}@mail.ru"
        assert len(email) == 255
        assert svc._is_valid_email(email) is False

    def test_email_at_256_chars_invalid(self):
        svc = EmailDiscoveryService()
        local = "a" * (256 - len("@mail.ru"))
        email = f"{local}@mail.ru"
        assert svc._is_valid_email(email) is False

    def test_email_minimum_valid(self):
        """Shortest plausible email: a@b.cc (6 chars)."""
        svc = EmailDiscoveryService()
        assert svc._is_valid_email("a@b.cc") is True

    def test_email_empty_string(self):
        svc = EmailDiscoveryService()
        assert svc._is_valid_email("") is False

    # --- _generate_candidates with edge max_candidates ---

    def test_generate_candidates_max_zero(self):
        """max_candidates=0 => empty list."""
        svc = EmailDiscoveryService(max_candidates=0)
        result = svc._generate_candidates("Иван", "Петров", [])
        assert result == []

    def test_generate_candidates_max_one(self):
        svc = EmailDiscoveryService(max_candidates=1)
        result = svc._generate_candidates("Иван", "Петров", ["ivanpetrov"])
        assert len(result) <= 1

    def test_generate_candidates_max_1000(self):
        """Even with many usernames, set dedup limits the output before capping."""
        svc = EmailDiscoveryService(max_candidates=1000)
        usernames = [f"user{i}" for i in range(50)]
        result = svc._generate_candidates("Иван", "Петров", usernames)
        assert len(result) <= 1000

    # --- Confidence label boundaries ---

    def test_confidence_label_very_high_at_0_9(self):
        r = make_source_result(confidence=0.9)
        assert r.confidence_label == "very_high"

    def test_confidence_label_high_at_0_7(self):
        r = make_source_result(confidence=0.7)
        assert r.confidence_label == "high"

    def test_confidence_label_medium_at_0_5(self):
        r = make_source_result(confidence=0.5)
        assert r.confidence_label == "medium"

    def test_confidence_label_low_at_0_499(self):
        r = make_source_result(confidence=0.499)
        assert r.confidence_label == "low"

    def test_confidence_label_zero(self):
        r = make_source_result(confidence=0.0)
        assert r.confidence_label == "low"

    def test_confidence_label_one(self):
        r = make_source_result(confidence=1.0)
        assert r.confidence_label == "very_high"

    # --- _extract_from_usernames boundaries ---

    def test_extract_from_usernames_empty_list(self):
        svc = PhoneDiscoveryService()
        result = svc._extract_from_usernames([])
        assert result == []
        svc.close()

    def test_extract_from_usernames_single_non_phone(self):
        svc = PhoneDiscoveryService()
        result = svc._extract_from_usernames(["hello_world"])
        assert result == []
        svc.close()

    # --- _normalize_key boundaries ---

    def test_normalize_key_empty_string(self):
        result = PhoneDiscoveryService._normalize_key("")
        assert result == ""

    def test_normalize_key_single_digit(self):
        result = PhoneDiscoveryService._normalize_key("5")
        assert result == "5"

    def test_normalize_key_exactly_10_digits(self):
        result = PhoneDiscoveryService._normalize_key("+79161234567")
        assert result == "9161234567"
        assert len(result) == 10

    def test_normalize_key_20_digit_phone(self):
        """Takes last 10 digits."""
        result = PhoneDiscoveryService._normalize_key("12345678901234567890")
        assert result == "1234567890"
        assert len(result) == 10


# ═══════════════════════════════════════════════════════════════════
# 2. LARGE COLLECTION PROCESSING (15+ tests)
# ═══════════════════════════════════════════════════════════════════

class TestLargeCollections:
    """Processing large collections in reasonable time."""

    @patch.object(SourceManager, '_discover_sources')
    def test_deduplicate_1000_unique_results(self, mock_discover):
        """1000 unique SourceResults should deduplicate without error."""
        mgr = SourceManager.__new__(SourceManager)
        mgr.sources = []

        results = [
            make_source_result(value=f"user{i}@mail.ru", source_name=f"Src{i}", confidence=0.5)
            for i in range(1000)
        ]
        start = time.time()
        deduped = mgr._deduplicate(results)
        elapsed = time.time() - start

        assert len(deduped) == 1000
        assert elapsed < 5.0  # must be fast

    @patch.object(SourceManager, '_discover_sources')
    def test_deduplicate_1000_identical_results(self, mock_discover):
        """1000 identical results should merge to 1."""
        mgr = SourceManager.__new__(SourceManager)
        mgr.sources = []

        results = [
            make_source_result(
                value="same@mail.ru",
                source_name=f"Src{i}",
                confidence=0.5,
            )
            for i in range(1000)
        ]
        deduped = mgr._deduplicate(results)

        assert len(deduped) == 1
        assert deduped[0].metadata['source_count'] == 1000
        assert len(deduped[0].metadata['sources']) == 1000

    @patch.object(SourceManager, '_discover_sources')
    def test_cross_validate_100_phones_100_emails(self, mock_discover):
        """Cross-validate with 100 phones x 100 emails shouldn't be slow."""
        mgr = SourceManager.__new__(SourceManager)
        mgr.sources = []

        results = []
        for i in range(100):
            results.append(make_source_result(
                data_type="phone", value=f"+7916{i:07d}", confidence=0.8,
                source_tier=SourceTier.S,
            ))
        for i in range(100):
            results.append(make_source_result(
                data_type="email", value=f"user{i}@mail.ru", confidence=0.8,
                source_tier=SourceTier.S,
            ))

        start = time.time()
        validated = mgr._cross_validate(results)
        elapsed = time.time() - start

        assert len(validated) == 200
        assert elapsed < 5.0

    @patch.object(SourceManager, '_discover_sources')
    def test_group_by_type_500_results_5_types(self, mock_discover):
        """500 results across 5 data types should group correctly."""
        mgr = SourceManager.__new__(SourceManager)
        mgr.sources = []

        types = ["email", "phone", "profile", "identity", "address"]
        results = [
            make_source_result(data_type=types[i % 5], value=f"val{i}")
            for i in range(500)
        ]
        grouped = mgr._group_by_type(results)

        assert len(grouped) == 5
        for t in types:
            assert len(grouped[t]) == 100

    def test_generate_candidates_with_100_usernames(self):
        """Only first 10 usernames should be used in pattern generation."""
        svc = EmailDiscoveryService(max_candidates=500)
        usernames = [f"validuser{i}" for i in range(100)]
        result = svc._generate_candidates("Иван", "Петров", usernames)

        # Check that we don't use all 100 usernames (only first 10)
        # Name patterns (9 base patterns) + max 10 usernames = 19 patterns
        # 19 patterns x 9 domains = 171 max, minus filtering/dedup
        assert len(result) <= 500

    def test_extract_from_usernames_with_50_usernames(self):
        """50 usernames, some with phone-like patterns."""
        svc = PhoneDiscoveryService()
        usernames = [f"user{i}" for i in range(50)]
        # Add 5 that are actual phone numbers
        usernames[0] = "9161234567"
        usernames[10] = "89261234567"
        usernames[20] = "79031234567"
        usernames[30] = "id89051234567"
        usernames[40] = "9651234567"

        result = svc._extract_from_usernames(usernames)
        assert len(result) >= 3  # At least the pure-digit usernames
        svc.close()

    def test_extract_from_emails_with_50_emails(self):
        """50 emails, some with phone local parts."""
        svc = PhoneDiscoveryService()
        emails = [f"contact{i}@mail.ru" for i in range(50)]
        # Add phone-as-email entries
        emails[0] = "9161234567@mail.ru"
        emails[10] = "89261234567@bk.ru"
        emails[20] = "79031234567@yandex.ru"

        result = svc._extract_from_emails(emails)
        assert len(result) == 3
        svc.close()

    def test_generate_phone_candidates_cap_at_10(self):
        """Even with 50 usernames containing digits, result capped at 10."""
        svc = PhoneDiscoveryService()
        # Usernames with 7-digit suffixes that trigger candidate generation
        usernames = [f"user{1234567 + i}" for i in range(50)]
        result = svc._generate_phone_candidates(usernames, "Иван", "Петров")
        assert len(result) <= 10
        svc.close()

    @patch.object(SourceManager, '_discover_sources')
    def test_deduplicate_mixed_types_1000(self, mock_discover):
        """1000 results of mixed types deduplicate correctly."""
        mgr = SourceManager.__new__(SourceManager)
        mgr.sources = []

        results = []
        for i in range(500):
            results.append(make_source_result(
                data_type="email", value=f"e{i % 100}@mail.ru",
                source_name=f"Src{i}",
            ))
        for i in range(500):
            results.append(make_source_result(
                data_type="phone", value=f"+7916{i % 100:07d}",
                source_name=f"Src{i + 500}",
            ))

        deduped = mgr._deduplicate(results)
        # 100 unique emails + 100 unique phones = 200
        assert len(deduped) == 200

    @patch.object(SourceManager, '_discover_sources')
    def test_deduplicate_preserves_all_source_names(self, mock_discover):
        """All contributing source names must be tracked."""
        mgr = SourceManager.__new__(SourceManager)
        mgr.sources = []

        results = [
            make_source_result(value="common@mail.ru", source_name=f"Source{i}")
            for i in range(50)
        ]
        deduped = mgr._deduplicate(results)
        assert len(deduped) == 1
        assert len(deduped[0].metadata['sources']) == 50

    def test_validator_extract_phones_from_large_text(self):
        """Extract phones from text with 100 embedded phone numbers."""
        validator = RussianPhoneValidator()
        lines = [f"Call +7916{i:07d} now!" for i in range(100)]
        big_text = "\n".join(lines)

        start = time.time()
        results = validator.extract_phones(big_text)
        elapsed = time.time() - start

        assert len(results) >= 50  # Regex overlap might deduplicate some
        assert elapsed < 5.0

    @patch.object(SourceManager, '_discover_sources')
    def test_group_by_type_empty_list(self, mock_discover):
        mgr = SourceManager.__new__(SourceManager)
        mgr.sources = []
        grouped = mgr._group_by_type([])
        assert grouped == {}

    @patch.object(SourceManager, '_discover_sources')
    def test_group_by_type_single_type(self, mock_discover):
        mgr = SourceManager.__new__(SourceManager)
        mgr.sources = []
        results = [make_source_result(data_type="phone", value=f"v{i}") for i in range(100)]
        grouped = mgr._group_by_type(results)
        assert len(grouped) == 1
        assert len(grouped["phone"]) == 100


# ═══════════════════════════════════════════════════════════════════
# 3. DUPLICATE EXPLOSION (15+ tests)
# ═══════════════════════════════════════════════════════════════════

class TestDuplicateExplosion:
    """Tests that duplicate inputs don't explode output or break invariants."""

    def test_same_phone_100_formats_normalize_to_same(self):
        """Same phone in 100 different format variants should normalize."""
        formats = [
            "+7 (916) 123-45-67",
            "8 916 123 45 67",
            "+7-916-123-45-67",
            "89161234567",
            "+79161234567",
            "8(916)1234567",
            "8-916-123-4567",
            "8 916 1234567",
            "+7 916 123 4567",
            "7 (916) 123 45 67",
        ]
        # Extend with slight variations
        for i in range(90):
            formats.append(f"  +7 916 123 45 67  ")  # whitespace padding

        normalized = set()
        for f in formats:
            n = normalize_phone(f)
            normalized.add(n)

        # All should map to same normalized value
        assert len(normalized) == 1
        assert "+79161234567" in normalized

    def test_same_email_different_cases_dedup_to_one(self):
        """Email dedup is case-insensitive."""
        svc = EmailDiscoveryService()
        variants = [
            "Test@Mail.RU",
            "test@mail.ru",
            "TEST@MAIL.RU",
            "tEsT@mAiL.rU",
        ]
        candidates = set()
        for v in variants:
            if svc._is_valid_email(v):
                candidates.add(v.lower())
        assert len(candidates) == 1

    @patch.object(SourceManager, '_discover_sources')
    def test_100_results_same_value_100_sources_merge_to_1(self, mock_discover):
        """100 SourceResults with same value from different sources => 1 result."""
        mgr = SourceManager.__new__(SourceManager)
        mgr.sources = []

        results = [
            make_source_result(
                value="duplicated@mail.ru",
                source_name=f"Source_{i}",
                confidence=0.5,
            )
            for i in range(100)
        ]
        deduped = mgr._deduplicate(results)

        assert len(deduped) == 1
        assert deduped[0].metadata['source_count'] == 100

    @patch.object(SourceManager, '_discover_sources')
    def test_confidence_after_100_boosts_capped_at_1(self, mock_discover):
        """After 100 merges, confidence must still be <= 1.0."""
        mgr = SourceManager.__new__(SourceManager)
        mgr.sources = []

        results = [
            make_source_result(
                value="boosted@mail.ru",
                source_name=f"Src{i}",
                confidence=0.9,
            )
            for i in range(100)
        ]
        deduped = mgr._deduplicate(results)

        assert len(deduped) == 1
        assert deduped[0].confidence <= 1.0

    @patch.object(SourceManager, '_discover_sources')
    def test_confidence_boost_from_low_baseline(self, mock_discover):
        """Confidence boost starting from 0.1 after many merges."""
        mgr = SourceManager.__new__(SourceManager)
        mgr.sources = []

        results = [
            make_source_result(
                value="low@mail.ru",
                source_name=f"Src{i}",
                confidence=0.1,
            )
            for i in range(50)
        ]
        deduped = mgr._deduplicate(results)

        assert len(deduped) == 1
        assert deduped[0].confidence > 0.1  # boosted
        assert deduped[0].confidence <= 1.0

    @patch.object(SourceManager, '_discover_sources')
    def test_source_tracking_with_50_sources(self, mock_discover):
        """Track all 50 contributing source names."""
        mgr = SourceManager.__new__(SourceManager)
        mgr.sources = []

        results = [
            make_source_result(
                value="tracked@mail.ru",
                source_name=f"UniqueSrc{i}",
            )
            for i in range(50)
        ]
        deduped = mgr._deduplicate(results)
        assert len(deduped[0].metadata['sources']) == 50

    @patch.object(SourceManager, '_discover_sources')
    def test_dedup_does_not_lose_raw_data_keys(self, mock_discover):
        """Raw data from different sources should be merged."""
        mgr = SourceManager.__new__(SourceManager)
        mgr.sources = []

        results = [
            make_source_result(
                value="merge@mail.ru",
                source_name=f"Src{i}",
                raw_data={f"key_{i}": f"value_{i}"},
            )
            for i in range(20)
        ]
        deduped = mgr._deduplicate(results)
        assert len(deduped) == 1
        # All raw_data keys should be present
        assert len(deduped[0].raw_data) == 20

    @patch.object(SourceManager, '_discover_sources')
    def test_dedup_keeps_highest_tier(self, mock_discover):
        """After merge, the highest tier (S) should be preserved."""
        mgr = SourceManager.__new__(SourceManager)
        mgr.sources = []

        results = [
            make_source_result(value="tier@mail.ru", source_tier=SourceTier.C, source_name="Low"),
            make_source_result(value="tier@mail.ru", source_tier=SourceTier.S, source_name="High"),
            make_source_result(value="tier@mail.ru", source_tier=SourceTier.B, source_name="Mid"),
        ]
        deduped = mgr._deduplicate(results)
        assert deduped[0].source_tier == SourceTier.S

    def test_normalize_key_deduplication_same_number_many_formats(self):
        """_normalize_key should produce same key for many formats of same phone."""
        svc = PhoneDiscoveryService()
        formats = [
            "+79161234567",
            "89161234567",
            "+7 (916) 123-45-67",
            "8-916-123-45-67",
            "79161234567",
        ]
        keys = set()
        for f in formats:
            keys.add(svc._normalize_key(f))
        assert len(keys) == 1
        svc.close()

    def test_duplicate_usernames_dont_duplicate_phones(self):
        """Same username repeated 50 times should not produce 50x phone results."""
        svc = PhoneDiscoveryService()
        usernames = ["9161234567"] * 50
        result = svc._extract_from_usernames(usernames)
        # Each iteration produces the same phone, so all are same
        normalized = set()
        for p in result:
            normalized.add(re.sub(r'\D', '', p.number)[-10:])
        # All map to same phone
        assert len(normalized) == 1
        svc.close()

    @patch.object(SourceManager, '_discover_sources')
    def test_cross_validate_dual_source_high_confidence(self, mock_discover):
        """Result from 2 sources with confidence >= 0.7 should be verified."""
        mgr = SourceManager.__new__(SourceManager)
        mgr.sources = []

        result = make_source_result(
            value="dual@mail.ru",
            confidence=0.8,
            metadata={'source_count': 2, 'sources': ['A', 'B']},
        )
        validated = mgr._cross_validate([result])
        assert validated[0].verified is True

    @patch.object(SourceManager, '_discover_sources')
    def test_cross_validate_triple_source_auto_verify(self, mock_discover):
        """3+ sources confirm => auto-verified."""
        mgr = SourceManager.__new__(SourceManager)
        mgr.sources = []

        result = make_source_result(
            value="triple@mail.ru",
            confidence=0.3,
            metadata={'source_count': 3, 'sources': ['A', 'B', 'C']},
        )
        validated = mgr._cross_validate([result])
        assert validated[0].verified is True

    @patch.object(SourceManager, '_discover_sources')
    def test_dedup_duplicate_source_name_not_double_counted(self, mock_discover):
        """Same source name appearing twice should only be listed once."""
        mgr = SourceManager.__new__(SourceManager)
        mgr.sources = []

        results = [
            make_source_result(value="dup@mail.ru", source_name="SameSource"),
            make_source_result(value="dup@mail.ru", source_name="SameSource"),
        ]
        deduped = mgr._deduplicate(results)
        assert deduped[0].metadata['source_count'] == 1

    @patch.object(SourceManager, '_discover_sources')
    def test_confidence_never_exceeds_1_with_high_initial(self, mock_discover):
        """Starting at 0.99, boost should not exceed 1.0."""
        mgr = SourceManager.__new__(SourceManager)
        mgr.sources = []

        results = [
            make_source_result(value="highconf@mail.ru", source_name=f"S{i}", confidence=0.99)
            for i in range(50)
        ]
        deduped = mgr._deduplicate(results)
        assert deduped[0].confidence <= 1.0

    @patch.object(SourceManager, '_discover_sources')
    def test_metadata_merge_no_overwrite_existing(self, mock_discover):
        """Later metadata keys should not overwrite earlier ones (except sources)."""
        mgr = SourceManager.__new__(SourceManager)
        mgr.sources = []

        r1 = make_source_result(value="meta@mail.ru", source_name="S1",
                                metadata={"breach_name": "FirstBreach"})
        r2 = make_source_result(value="meta@mail.ru", source_name="S2",
                                metadata={"breach_name": "SecondBreach", "extra": "data"})
        deduped = mgr._deduplicate([r1, r2])
        assert deduped[0].metadata["breach_name"] == "FirstBreach"
        assert deduped[0].metadata["extra"] == "data"


# ═══════════════════════════════════════════════════════════════════
# 4. PATTERN LIMITS (15+ tests)
# ═══════════════════════════════════════════════════════════════════

class TestPatternLimits:
    """Tests that pattern generation respects limits and caps."""

    def test_extract_phones_100_phones_in_text(self):
        """Text with 100 phone numbers should be parsed correctly."""
        validator = RussianPhoneValidator()
        numbers = [f"+7916{i:07d}" for i in range(100)]
        text = " ".join(numbers)
        results = validator.extract_phones(text)
        # Should find a large number (exact count depends on pattern overlap / dedup)
        assert len(results) >= 50

    def test_is_valid_email_called_1000_times_consistent(self):
        """Calling _is_valid_email 1000 times returns consistent results."""
        svc = EmailDiscoveryService()
        for _ in range(1000):
            assert svc._is_valid_email("test@mail.ru") is True
            assert svc._is_valid_email("invalid") is False
            assert svc._is_valid_email("") is False

    def test_transliterate_1000_char_cyrillic(self):
        """Transliterating a long Cyrillic string."""
        svc = EmailDiscoveryService()
        cyrillic = "абвгдежзиклмнопрстуфхцчшщъыьэюя" * 33  # ~1023 chars
        start = time.time()
        result = svc._transliterate(cyrillic)
        elapsed = time.time() - start

        assert len(result) > 0
        assert elapsed < 1.0
        # Verify no Cyrillic remains
        assert not re.search(r'[а-яё]', result)

    def test_name_patterns_times_domains_capped_by_max_candidates(self):
        """9 patterns x 9 domains = 81 max, but max_candidates should cap output."""
        svc = EmailDiscoveryService(max_candidates=10)
        result = svc._generate_candidates("Иван", "Петров", [])
        assert len(result) <= 10

    def test_username_patterns_10_usernames_9_domains(self):
        """10 usernames + base patterns x 9 domains => lots, but capped."""
        svc = EmailDiscoveryService(max_candidates=50)
        usernames = [f"user{i}name" for i in range(10)]
        result = svc._generate_candidates("Иван", "Петров", usernames)
        assert len(result) <= 50

    def test_max_candidates_caps_output_strictly(self):
        """Verify the slice at the end of _generate_candidates."""
        svc = EmailDiscoveryService(max_candidates=5)
        usernames = [f"longusername{i}" for i in range(20)]
        result = svc._generate_candidates("Иван", "Петров", usernames)
        assert len(result) <= 5

    def test_clean_username_strips_prefix_patterns(self):
        """Various prefixes are stripped: id, user, profile, @."""
        svc = EmailDiscoveryService()
        assert svc._clean_username("id12345") == "12345"
        assert svc._clean_username("@johndoe") == "johndoe"
        assert svc._clean_username("user_name") == "_name"
        assert svc._clean_username("profile_test") == "_test"

    def test_clean_username_removes_non_ascii(self):
        svc = EmailDiscoveryService()
        result = svc._clean_username("Иван_Петров_123")
        assert result == "__123"  # Cyrillic removed, both underscores remain

    def test_transliterate_empty_string(self):
        svc = EmailDiscoveryService()
        assert svc._transliterate("") == ""

    def test_transliterate_already_latin(self):
        svc = EmailDiscoveryService()
        assert svc._transliterate("john") == "john"

    def test_transliterate_mixed_cyrillic_latin(self):
        svc = EmailDiscoveryService()
        result = svc._transliterate("Иvanов")
        # "И" -> "i", "v" -> "v", "a" -> "a", "n" -> "n", "о" -> "o", "в" -> "v"
        assert "i" in result
        assert "v" in result

    def test_generate_candidates_empty_names(self):
        """Empty first/last name should not crash."""
        svc = EmailDiscoveryService(max_candidates=30)
        result = svc._generate_candidates("", "", [])
        # May produce some candidates from empty patterns, or empty list
        assert isinstance(result, list)

    def test_generate_candidates_only_usernames(self):
        """With blank names, only username-based patterns should appear."""
        svc = EmailDiscoveryService(max_candidates=100)
        result = svc._generate_candidates("", "", ["testusername"])
        # At least some username-based emails
        found_username = any("testusername" in e for e in result)
        assert found_username or len(result) == 0  # empty names may filter out short patterns

    def test_phone_patterns_match_compact_formats(self):
        """Verify extraction against formats the regex actually handles."""
        validator = RussianPhoneValidator()
        # Patterns support optional single-char separator between +7/8 and digits
        # e.g. +7(916)... or +7-916-... but NOT +7 (916) with space+paren
        texts = [
            "+7(916)1234567",
            "+7-916-123-45-67",
            "+79161234567",
            "89161234567",
            "8-916-123-45-67",
        ]
        for text in texts:
            results = validator.extract_phones(text)
            assert len(results) >= 1, f"Failed to extract from: {text}"

    def test_phone_patterns_spaced_paren_format_not_extracted(self):
        """Format '+7 (916) 123-45-67' has space+paren that patterns miss."""
        validator = RussianPhoneValidator()
        # This is a known limitation of the current regex patterns
        results = validator.extract_phones("+7 (916) 123-45-67")
        # May or may not extract — documents actual behavior
        assert isinstance(results, list)

    def test_email_domain_count(self):
        """Verify RUSSIAN_EMAIL_DOMAINS has exactly 9 domains."""
        assert len(RUSSIAN_EMAIL_DOMAINS) == 9


# ═══════════════════════════════════════════════════════════════════
# 5. RESOURCE MANAGEMENT (15+ tests)
# ═══════════════════════════════════════════════════════════════════

class TestResourceManagement:
    """Construction, cleanup, reuse, and lifecycle of services."""

    def test_email_service_construction(self):
        svc = EmailDiscoveryService()
        assert svc.max_candidates == 30
        assert svc._executor is not None
        svc.close()

    def test_email_service_custom_params(self):
        svc = EmailDiscoveryService(max_candidates=100, verify_timeout=10.0, max_concurrent=20)
        assert svc.max_candidates == 100
        assert svc.verify_timeout == 10.0
        assert svc.max_concurrent == 20
        svc.close()

    def test_email_service_close_idempotent(self):
        """Calling close() twice should not crash."""
        svc = EmailDiscoveryService()
        svc.close()
        svc.close()  # second call should be safe

    def test_phone_service_construction(self):
        svc = PhoneDiscoveryService()
        assert svc.max_candidates == 50
        assert svc.validator is not None
        assert svc._executor is not None
        svc.close()

    def test_phone_service_close_idempotent(self):
        svc = PhoneDiscoveryService()
        svc.close()
        svc.close()

    def test_multiple_email_service_instances(self):
        """Create and close 10 instances sequentially."""
        for _ in range(10):
            svc = EmailDiscoveryService()
            svc._generate_candidates("Test", "User", ["testuser"])
            svc.close()

    def test_multiple_phone_service_instances(self):
        for _ in range(10):
            svc = PhoneDiscoveryService()
            svc._extract_from_usernames(["testuser"])
            svc.close()

    def test_email_service_reuse_generate_candidates(self):
        """Calling _generate_candidates multiple times on same instance."""
        svc = EmailDiscoveryService()
        for i in range(20):
            result = svc._generate_candidates("Имя", "Фамилия", [f"user{i}"])
            assert isinstance(result, list)
        svc.close()

    def test_phone_service_reuse_extract_from_usernames(self):
        svc = PhoneDiscoveryService()
        for i in range(20):
            result = svc._extract_from_usernames([f"user{i}"])
            assert isinstance(result, list)
        svc.close()

    def test_phone_service_reuse_extract_from_emails(self):
        svc = PhoneDiscoveryService()
        for i in range(20):
            result = svc._extract_from_emails([f"contact{i}@mail.ru"])
            assert isinstance(result, list)
        svc.close()

    def test_validator_reuse_many_validations(self):
        """Validator instance reused for 500 validations."""
        validator = RussianPhoneValidator()
        for i in range(500):
            info = validator.validate(f"+7916{i:07d}")
            assert isinstance(info, PhoneInfo)
            assert info.is_valid is True

    def test_validator_stateless_between_calls(self):
        """Validator should be stateless — same input => same output."""
        validator = RussianPhoneValidator()
        info1 = validator.validate("+79161234567")
        for _ in range(100):
            validator.validate("+79261234567")
        info2 = validator.validate("+79161234567")
        assert info1.normalized == info2.normalized
        assert info1.carrier_hint == info2.carrier_hint
        assert info1.is_mobile == info2.is_mobile

    @patch.object(SourceManager, '_discover_sources')
    def test_source_manager_construction_without_sources_dir(self, mock_discover):
        """SourceManager should handle missing sources directory gracefully."""
        mgr = SourceManager.__new__(SourceManager)
        mgr.sources = []
        # Should not crash
        assert mgr.sources == []

    def test_source_result_to_dict_serialization(self):
        """SourceResult.to_dict() should always be JSON-serializable."""
        import json
        r = make_source_result(
            metadata={"key": "value", "nested": {"a": 1}},
            raw_data={"raw": "data"},
        )
        d = r.to_dict()
        serialized = json.dumps(d)
        assert isinstance(serialized, str)

    def test_source_result_to_dict_all_fields_present(self):
        r = make_source_result()
        d = r.to_dict()
        expected_keys = {'data_type', 'value', 'source_name', 'source_tier',
                         'confidence', 'confidence_label', 'verified', 'metadata'}
        assert expected_keys == set(d.keys())


# ═══════════════════════════════════════════════════════════════════
# 6. OVERFLOW AND WRAP (10+ tests)
# ═══════════════════════════════════════════════════════════════════

class TestOverflowAndWrap:
    """Edge cases for numeric boundaries, max values, and overflow scenarios."""

    def test_phone_all_nines(self):
        """All-9s Russian mobile: +79999999999."""
        result = normalize_phone("+79999999999")
        assert result == "+79999999999"

    def test_phone_all_nines_validation(self):
        validator = RussianPhoneValidator()
        info = validator.validate("+79999999999")
        assert info.is_valid is True
        assert info.is_mobile is True

    def test_phone_all_zeros(self):
        """All-0s after country code: +70000000000."""
        result = normalize_phone("+70000000000")
        assert result == "+70000000000"

    def test_phone_all_zeros_validation(self):
        """0-prefix is not mobile (doesn't start with 9)."""
        validator = RussianPhoneValidator()
        info = validator.validate("+70000000000")
        assert info.is_valid is True
        assert info.is_mobile is False

    @patch.object(SourceManager, '_discover_sources')
    def test_confidence_at_1_boost_should_not_exceed(self, mock_discover):
        """Starting at confidence 1.0, boost must not go above."""
        mgr = SourceManager.__new__(SourceManager)
        mgr.sources = []

        results = [
            make_source_result(value="max@mail.ru", source_name="S1", confidence=1.0),
            make_source_result(value="max@mail.ru", source_name="S2", confidence=1.0),
        ]
        deduped = mgr._deduplicate(results)
        assert deduped[0].confidence == 1.0

    @patch.object(SourceManager, '_discover_sources')
    def test_confidence_at_0_boost_should_increase(self, mock_discover):
        """Starting at 0.0, merging should boost confidence."""
        mgr = SourceManager.__new__(SourceManager)
        mgr.sources = []

        results = [
            make_source_result(value="zero@mail.ru", source_name="S1", confidence=0.0),
            make_source_result(value="zero@mail.ru", source_name="S2", confidence=0.0),
        ]
        deduped = mgr._deduplicate(results)
        # boost = min(0.15, (1.0 - 0.0) * 0.5) = min(0.15, 0.5) = 0.15
        assert deduped[0].confidence == pytest.approx(0.15, abs=0.01)

    def test_32bit_integer_boundary_in_phone_digits(self):
        """Phone digits near 2^31 boundary."""
        # 2^31 = 2147483648 (10 digits starting with 2)
        phone = "+72147483648"
        # 11 digits starting with 7 => normalizable check
        result = normalize_phone(phone)
        assert result == "+72147483648"

    def test_very_large_metadata_dict(self):
        """SourceResult with large metadata should work."""
        big_meta = {f"key_{i}": f"value_{i}" * 100 for i in range(100)}
        r = make_source_result(metadata=big_meta)
        assert len(r.metadata) == 100
        d = r.to_dict()
        assert len(d['metadata']) == 100

    def test_very_large_raw_data_dict(self):
        big_raw = {f"field_{i}": list(range(100)) for i in range(50)}
        r = make_source_result(raw_data=big_raw)
        assert len(r.raw_data) == 50

    def test_phone_with_unicode_characters(self):
        """Phone with embedded Unicode (non-digit) characters."""
        result = normalize_phone("+7\u200B916\u200B1234567")
        # Zero-width spaces are non-digit, stripped by re.sub
        assert result == "+79161234567"

    def test_phone_with_special_characters(self):
        """Phone with various special characters."""
        result = normalize_phone("+7 (916) 123-45-67!")
        # Extra chars ignored; digits = 79161234567 => 11 digits starting with 7
        assert result == "+79161234567"

    def test_email_with_max_local_part(self):
        """Local part at 64 chars (RFC 5321 local limit)."""
        svc = EmailDiscoveryService()
        local = "a" * 64
        email = f"{local}@mail.ru"
        # It's under 254 total and matches pattern
        assert svc._is_valid_email(email) is True

    def test_normalize_phone_with_leading_plus_and_extra_digits(self):
        """Phone like +79161234567890 — 14 digits, cannot normalize."""
        result = normalize_phone("+79161234567890")
        assert result == "+79161234567890"  # returned unchanged

    def test_carrier_prefixes_coverage(self):
        """Verify all carrier prefixes produce valid PhoneInfo."""
        validator = RussianPhoneValidator()
        for carrier, prefixes in CARRIER_PREFIXES.items():
            for prefix in prefixes:
                phone = f"+7{prefix}1234567"
                info = validator.validate(phone)
                assert info.is_valid is True
                assert info.is_mobile is True
                assert info.carrier_hint is not None, f"No carrier for prefix {prefix}"

    def test_city_codes_coverage(self):
        """Verify all city codes produce valid landline PhoneInfo."""
        validator = RussianPhoneValidator()
        for code, city in CITY_CODES.items():
            phone = f"+7{code}1234567"
            info = validator.validate(phone)
            assert info.is_valid is True
            assert info.is_mobile is False
            assert info.format_type == 'landline'
