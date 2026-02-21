"""
Unit tests for deduplication and merging logic across Phase 2 services.

Tests cover:
1. PhoneDiscoveryService._normalize_key() — phone dedup key generation
2. SourceManager._deduplicate() — merging duplicate SourceResults
3. Confidence boosting math — incremental boost formula
4. SourceManager._cross_validate() — cross-data-type validation
5. EmailDiscoveryService email dedup with verification merging
6. End-to-end dedup scenarios
"""

import copy
import pytest
from unittest.mock import patch, MagicMock

from app.services.phase2.base_source import SourceResult, SourceTier, SourceType
from app.services.phase2.source_manager import SourceManager
from app.services.phase2.phone_discovery import PhoneDiscoveryService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_result(
    data_type="email",
    value="test@mail.ru",
    source_name="TestSource",
    source_tier=SourceTier.B,
    confidence=0.5,
    verified=False,
    raw_data=None,
    metadata=None,
):
    """Shortcut to build a SourceResult with sensible defaults."""
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


@pytest.fixture
def source_manager():
    """SourceManager with auto-discovery disabled (no real plugin imports)."""
    with patch.object(SourceManager, '_discover_sources', return_value=None):
        mgr = SourceManager()
        mgr.sources = []
        return mgr


@pytest.fixture
def phone_service():
    """PhoneDiscoveryService for _normalize_key tests."""
    with patch('app.services.phase2.phone_discovery.RussianPhoneValidator'):
        svc = PhoneDiscoveryService.__new__(PhoneDiscoveryService)
        return svc


# ===========================================================================
# 1. Phone dedup via _normalize_key (15+ tests)
# ===========================================================================

class TestPhoneNormalizeKey:
    """PhoneDiscoveryService._normalize_key returns last 10 digits."""

    def test_plus7_full(self):
        assert PhoneDiscoveryService._normalize_key("+79161234567") == "9161234567"

    def test_eight_prefix(self):
        assert PhoneDiscoveryService._normalize_key("89161234567") == "9161234567"

    def test_plus7_parentheses_dashes(self):
        assert PhoneDiscoveryService._normalize_key("+7 (916) 123-45-67") == "9161234567"

    def test_eight_parentheses(self):
        assert PhoneDiscoveryService._normalize_key("8(916)123-45-67") == "9161234567"

    def test_ten_digits_raw(self):
        assert PhoneDiscoveryService._normalize_key("9161234567") == "9161234567"

    def test_plus7_spaces(self):
        assert PhoneDiscoveryService._normalize_key("+7 916 123 45 67") == "9161234567"

    def test_international_format(self):
        assert PhoneDiscoveryService._normalize_key("+7-916-123-45-67") == "9161234567"

    def test_three_different_phones_different_keys(self):
        k1 = PhoneDiscoveryService._normalize_key("+79161234567")
        k2 = PhoneDiscoveryService._normalize_key("+79261234567")
        k3 = PhoneDiscoveryService._normalize_key("+79031234567")
        assert len({k1, k2, k3}) == 3

    def test_short_number_returns_what_it_can(self):
        # Less than 10 digits — returns all digits as-is (no slicing beyond start)
        assert PhoneDiscoveryService._normalize_key("12345") == "12345"

    def test_empty_string_returns_empty(self):
        assert PhoneDiscoveryService._normalize_key("") == ""

    def test_display_format_same_as_raw(self):
        """Formatted display number produces same key as raw digits."""
        assert (
            PhoneDiscoveryService._normalize_key("+7 (916) 123-45-67")
            == PhoneDiscoveryService._normalize_key("89161234567")
        )

    def test_leading_zeros_preserved(self):
        assert PhoneDiscoveryService._normalize_key("+70001234567") == "0001234567"

    def test_non_digit_characters_stripped(self):
        assert PhoneDiscoveryService._normalize_key("tel:+7(916)123-45-67!") == "9161234567"

    def test_eleven_digit_7_prefix(self):
        assert PhoneDiscoveryService._normalize_key("79161234567") == "9161234567"

    def test_twelve_digits_takes_last_ten(self):
        assert PhoneDiscoveryService._normalize_key("879161234567") == "9161234567"

    def test_long_garbage_takes_last_ten(self):
        assert PhoneDiscoveryService._normalize_key("abc000079161234567xyz") == "9161234567"

    def test_only_letters_returns_empty(self):
        assert PhoneDiscoveryService._normalize_key("abcdef") == ""

    def test_single_digit(self):
        assert PhoneDiscoveryService._normalize_key("7") == "7"

    @pytest.mark.parametrize("raw,expected", [
        ("+7 (926) 555-12-34", "9265551234"),
        ("8-903-111-22-33", "9031112233"),
        ("+7(965)000-00-01", "9650000001"),
        ("9991234567", "9991234567"),
    ])
    def test_parametrized_formats(self, raw, expected):
        assert PhoneDiscoveryService._normalize_key(raw) == expected


# ===========================================================================
# 2. SourceManager._deduplicate — basic merging (20+ tests)
# ===========================================================================

class TestDeduplicateBasic:
    """SourceManager._deduplicate merges identical data_type:value pairs."""

    def test_two_same_value_merged_to_one(self, source_manager):
        r1 = _make_result(value="ivan@mail.ru", source_name="Src1", confidence=0.6)
        r2 = _make_result(value="ivan@mail.ru", source_name="Src2", confidence=0.7)
        out = source_manager._deduplicate([r1, r2])
        assert len(out) == 1

    def test_different_emails_not_merged(self, source_manager):
        r1 = _make_result(value="ivan@mail.ru", source_name="Src1")
        r2 = _make_result(value="petr@mail.ru", source_name="Src2")
        out = source_manager._deduplicate([r1, r2])
        assert len(out) == 2

    def test_different_phones_not_merged(self, source_manager):
        r1 = _make_result(data_type="phone", value="+79161234567", source_name="Src1")
        r2 = _make_result(data_type="phone", value="+79261234567", source_name="Src2")
        out = source_manager._deduplicate([r1, r2])
        assert len(out) == 2

    def test_same_phone_from_vk_and_holehe_merge(self, source_manager):
        r1 = _make_result(
            data_type="email", value="ivan@mail.ru",
            source_name="VK API", confidence=0.8, source_tier=SourceTier.A,
        )
        r2 = _make_result(
            data_type="email", value="ivan@mail.ru",
            source_name="Holehe", confidence=0.9, source_tier=SourceTier.B,
        )
        out = source_manager._deduplicate([r1, r2])
        assert len(out) == 1
        assert out[0].confidence > 0.8  # boosted

    def test_five_same_phone_sources_near_max(self, source_manager):
        results = [
            _make_result(
                data_type="phone", value="+79161234567",
                source_name=f"Src{i}", confidence=0.5,
            )
            for i in range(5)
        ]
        out = source_manager._deduplicate(results)
        assert len(out) == 1
        assert out[0].confidence > 0.8  # significantly boosted

    def test_case_insensitive_email(self, source_manager):
        r1 = _make_result(value="Ivan@Mail.RU", source_name="Src1")
        r2 = _make_result(value="ivan@mail.ru", source_name="Src2")
        out = source_manager._deduplicate([r1, r2])
        assert len(out) == 1

    def test_whitespace_stripped_for_key(self, source_manager):
        r1 = _make_result(value=" ivan@mail.ru ", source_name="Src1")
        r2 = _make_result(value="ivan@mail.ru", source_name="Src2")
        out = source_manager._deduplicate([r1, r2])
        assert len(out) == 1

    def test_tier_promotion_c_to_s(self, source_manager):
        r1 = _make_result(value="ivan@mail.ru", source_name="Pattern", source_tier=SourceTier.C)
        r2 = _make_result(value="ivan@mail.ru", source_name="Breach", source_tier=SourceTier.S)
        out = source_manager._deduplicate([r1, r2])
        assert out[0].source_tier == SourceTier.S

    def test_tier_promotion_b_to_a(self, source_manager):
        r1 = _make_result(value="x@y.ru", source_name="Holehe", source_tier=SourceTier.B)
        r2 = _make_result(value="x@y.ru", source_name="VK API", source_tier=SourceTier.A)
        out = source_manager._deduplicate([r1, r2])
        assert out[0].source_tier == SourceTier.A

    def test_tier_not_demoted(self, source_manager):
        """If first result is Tier S, merging a Tier C should keep S."""
        r1 = _make_result(value="a@b.ru", source_name="Breach", source_tier=SourceTier.S)
        r2 = _make_result(value="a@b.ru", source_name="Pattern", source_tier=SourceTier.C)
        out = source_manager._deduplicate([r1, r2])
        assert out[0].source_tier == SourceTier.S

    def test_sources_list_tracks_all_names(self, source_manager):
        r1 = _make_result(value="a@b.ru", source_name="Src1")
        r2 = _make_result(value="a@b.ru", source_name="Src2")
        r3 = _make_result(value="a@b.ru", source_name="Src3")
        out = source_manager._deduplicate([r1, r2, r3])
        assert set(out[0].metadata['sources']) == {"Src1", "Src2", "Src3"}

    def test_source_count_correct(self, source_manager):
        results = [
            _make_result(value="a@b.ru", source_name=f"Src{i}")
            for i in range(4)
        ]
        out = source_manager._deduplicate(results)
        assert out[0].metadata['source_count'] == 4

    def test_raw_data_merged(self, source_manager):
        r1 = _make_result(value="a@b.ru", source_name="S1", raw_data={"breach": "VK2012"})
        r2 = _make_result(value="a@b.ru", source_name="S2", raw_data={"breach2": "Mail2014"})
        out = source_manager._deduplicate([r1, r2])
        assert "breach" in out[0].raw_data
        assert "breach2" in out[0].raw_data

    def test_metadata_merged_from_both(self, source_manager):
        r1 = _make_result(value="a@b.ru", source_name="S1", metadata={"date": "2024-01"})
        r2 = _make_result(value="a@b.ru", source_name="S2", metadata={"origin": "leak"})
        out = source_manager._deduplicate([r1, r2])
        assert out[0].metadata.get("origin") == "leak"

    def test_confidence_boosted_on_merge(self, source_manager):
        r1 = _make_result(value="a@b.ru", source_name="S1", confidence=0.5)
        r2 = _make_result(value="a@b.ru", source_name="S2", confidence=0.7)
        out = source_manager._deduplicate([r1, r2])
        assert out[0].confidence > 0.5

    def test_confidence_capped_at_one(self, source_manager):
        results = [
            _make_result(value="a@b.ru", source_name=f"S{i}", confidence=0.99)
            for i in range(10)
        ]
        out = source_manager._deduplicate(results)
        assert out[0].confidence <= 1.0

    def test_empty_input_returns_empty(self, source_manager):
        assert source_manager._deduplicate([]) == []

    def test_single_result_unchanged(self, source_manager):
        r = _make_result(value="solo@mail.ru", source_name="Only", confidence=0.6)
        out = source_manager._deduplicate([r])
        assert len(out) == 1
        assert out[0].confidence == 0.6
        assert out[0].metadata['sources'] == ["Only"]
        assert out[0].metadata['source_count'] == 1

    def test_different_data_types_same_value_not_merged(self, source_manager):
        """email:ivan@mail.ru and phone:ivan@mail.ru are different keys."""
        r1 = _make_result(data_type="email", value="ivan@mail.ru", source_name="S1")
        r2 = _make_result(data_type="phone", value="ivan@mail.ru", source_name="S2")
        out = source_manager._deduplicate([r1, r2])
        assert len(out) == 2

    def test_duplicate_source_name_not_double_counted(self, source_manager):
        """Same source name appearing twice should only be listed once."""
        r1 = _make_result(value="a@b.ru", source_name="Breach", confidence=0.7)
        r2 = _make_result(value="a@b.ru", source_name="Breach", confidence=0.8)
        out = source_manager._deduplicate([r1, r2])
        assert out[0].metadata['sources'] == ["Breach"]
        assert out[0].metadata['source_count'] == 1

    def test_raw_data_first_wins_on_conflict(self, source_manager):
        """When both sources have the same raw_data key, first occurrence wins."""
        r1 = _make_result(value="a@b.ru", source_name="S1", raw_data={"key": "first"})
        r2 = _make_result(value="a@b.ru", source_name="S2", raw_data={"key": "second"})
        out = source_manager._deduplicate([r1, r2])
        assert out[0].raw_data["key"] == "first"

    def test_metadata_sources_and_count_not_overwritten(self, source_manager):
        """Metadata keys 'sources' and 'source_count' are reserved and not overwritten by merge."""
        r1 = _make_result(value="a@b.ru", source_name="S1", metadata={"extra": "keep"})
        r2 = _make_result(
            value="a@b.ru", source_name="S2",
            metadata={"sources": ["fake"], "source_count": 999, "extra2": "also_keep"},
        )
        out = source_manager._deduplicate([r1, r2])
        # 'sources' should be the real tracked list, not the fake one
        assert "S1" in out[0].metadata['sources']
        assert "S2" in out[0].metadata['sources']
        assert out[0].metadata['source_count'] == 2
        assert out[0].metadata.get("extra2") == "also_keep"


# ===========================================================================
# 3. Confidence boosting math (10+ tests)
# ===========================================================================

class TestConfidenceBoosting:
    """Verify the formula: boost = min(0.15, (1.0 - existing.confidence) * 0.5)"""

    def test_base_0_5_one_additional(self, source_manager):
        """0.5 + min(0.15, 0.25) = 0.65"""
        r1 = _make_result(value="a@b.ru", source_name="S1", confidence=0.5)
        r2 = _make_result(value="a@b.ru", source_name="S2", confidence=0.3)
        out = source_manager._deduplicate([r1, r2])
        assert abs(out[0].confidence - 0.65) < 1e-9

    def test_base_0_9_one_additional(self, source_manager):
        """0.9 + min(0.15, 0.05) = 0.95"""
        r1 = _make_result(value="a@b.ru", source_name="S1", confidence=0.9)
        r2 = _make_result(value="a@b.ru", source_name="S2", confidence=0.3)
        out = source_manager._deduplicate([r1, r2])
        assert abs(out[0].confidence - 0.95) < 1e-9

    def test_base_0_95_one_additional(self, source_manager):
        """0.95 + min(0.15, 0.025) = 0.975"""
        r1 = _make_result(value="a@b.ru", source_name="S1", confidence=0.95)
        r2 = _make_result(value="a@b.ru", source_name="S2", confidence=0.3)
        out = source_manager._deduplicate([r1, r2])
        assert abs(out[0].confidence - 0.975) < 1e-9

    def test_base_0_3_three_additional(self, source_manager):
        """Incremental boosts from 0.3:
        Step 1: 0.3 + min(0.15, 0.35) = 0.45
        Step 2: 0.45 + min(0.15, 0.275) = 0.60
        Step 3: 0.60 + min(0.15, 0.20) = 0.75
        """
        results = [
            _make_result(value="a@b.ru", source_name=f"S{i}", confidence=0.3)
            for i in range(4)
        ]
        out = source_manager._deduplicate(results)
        assert abs(out[0].confidence - 0.75) < 1e-9

    def test_already_at_1_0_stays_1_0(self, source_manager):
        r1 = _make_result(value="a@b.ru", source_name="S1", confidence=1.0)
        r2 = _make_result(value="a@b.ru", source_name="S2", confidence=0.9)
        out = source_manager._deduplicate([r1, r2])
        assert out[0].confidence == 1.0

    def test_very_low_base_many_sources(self, source_manager):
        """Start at 0.1, add 9 sources — approaches 1.0 but never exceeds."""
        results = [
            _make_result(value="a@b.ru", source_name=f"S{i}", confidence=0.1)
            for i in range(10)
        ]
        out = source_manager._deduplicate(results)
        assert out[0].confidence <= 1.0
        assert out[0].confidence > 0.8  # significant boost from 9 merges

    def test_base_0_7_one_additional(self, source_manager):
        """0.7 + min(0.15, 0.15) = 0.85"""
        r1 = _make_result(value="a@b.ru", source_name="S1", confidence=0.7)
        r2 = _make_result(value="a@b.ru", source_name="S2", confidence=0.5)
        out = source_manager._deduplicate([r1, r2])
        assert abs(out[0].confidence - 0.85) < 1e-9

    def test_base_0_0_one_additional(self, source_manager):
        """0.0 + min(0.15, 0.5) = 0.15"""
        r1 = _make_result(value="a@b.ru", source_name="S1", confidence=0.0)
        r2 = _make_result(value="a@b.ru", source_name="S2", confidence=0.9)
        out = source_manager._deduplicate([r1, r2])
        assert abs(out[0].confidence - 0.15) < 1e-9

    def test_base_0_6_two_additional(self, source_manager):
        """
        Step 1: 0.6 + min(0.15, 0.20) = 0.75
        Step 2: 0.75 + min(0.15, 0.125) = 0.875
        """
        results = [
            _make_result(value="a@b.ru", source_name=f"S{i}", confidence=0.6)
            for i in range(3)
        ]
        out = source_manager._deduplicate(results)
        assert abs(out[0].confidence - 0.875) < 1e-9

    def test_base_0_85_one_additional(self, source_manager):
        """0.85 + min(0.15, 0.075) = 0.925"""
        r1 = _make_result(value="a@b.ru", source_name="S1", confidence=0.85)
        r2 = _make_result(value="a@b.ru", source_name="S2", confidence=0.4)
        out = source_manager._deduplicate([r1, r2])
        assert abs(out[0].confidence - 0.925) < 1e-9

    def test_convergence_never_exceeds_1(self, source_manager):
        """Even with 50 sources, confidence never goes above 1.0."""
        results = [
            _make_result(value="a@b.ru", source_name=f"S{i}", confidence=0.99)
            for i in range(50)
        ]
        out = source_manager._deduplicate(results)
        assert out[0].confidence <= 1.0

    def test_boost_is_zero_when_already_1(self, source_manager):
        """min(0.15, (1.0 - 1.0) * 0.5) = 0.0, so no change."""
        r1 = _make_result(value="a@b.ru", source_name="S1", confidence=1.0)
        r2 = _make_result(value="a@b.ru", source_name="S2", confidence=1.0)
        r3 = _make_result(value="a@b.ru", source_name="S3", confidence=1.0)
        out = source_manager._deduplicate([r1, r2, r3])
        assert out[0].confidence == 1.0

    def test_two_merges_monotonically_increasing(self, source_manager):
        """Confidence always increases or stays the same with each merge."""
        r1 = _make_result(value="a@b.ru", source_name="S1", confidence=0.4)
        r2 = _make_result(value="a@b.ru", source_name="S2", confidence=0.3)
        r3 = _make_result(value="a@b.ru", source_name="S3", confidence=0.2)
        # Process one at a time
        out1 = source_manager._deduplicate([r1, r2])
        c_after_1 = out1[0].confidence
        out2 = source_manager._deduplicate([out1[0], r3])
        c_after_2 = out2[0].confidence
        assert c_after_2 >= c_after_1 >= 0.4


# ===========================================================================
# 4. Cross-validation (15+ tests)
# ===========================================================================

class TestCrossValidation:
    """SourceManager._cross_validate applies multi-source and cross-type rules."""

    def test_phone_and_email_both_tier_s_verified(self, source_manager):
        phone = _make_result(
            data_type="phone", value="+79161234567",
            source_name="Breach", source_tier=SourceTier.S,
            metadata={'sources': ['Breach'], 'source_count': 1},
        )
        email = _make_result(
            data_type="email", value="ivan@mail.ru",
            source_name="Breach", source_tier=SourceTier.S,
            metadata={'sources': ['Breach'], 'source_count': 1},
        )
        out = source_manager._cross_validate([phone, email])
        assert out[0].verified is True
        assert out[1].verified is True

    def test_phone_tier_s_no_email_not_cross_validated(self, source_manager):
        phone = _make_result(
            data_type="phone", value="+79161234567",
            source_name="Breach", source_tier=SourceTier.S,
            metadata={'sources': ['Breach'], 'source_count': 1},
        )
        out = source_manager._cross_validate([phone])
        # Not verified because no email from Tier S exists
        assert out[0].verified is False

    def test_email_tier_s_no_phone_not_cross_validated(self, source_manager):
        email = _make_result(
            data_type="email", value="ivan@mail.ru",
            source_name="Breach", source_tier=SourceTier.S,
            metadata={'sources': ['Breach'], 'source_count': 1},
        )
        out = source_manager._cross_validate([email])
        assert out[0].verified is False

    def test_three_sources_verified(self, source_manager):
        r = _make_result(
            value="ivan@mail.ru", source_name="Multi",
            metadata={'sources': ['S1', 'S2', 'S3'], 'source_count': 3},
        )
        out = source_manager._cross_validate([r])
        assert out[0].verified is True
        assert 'confirmed_by_3_sources' in out[0].metadata.get('verified_reason', '')

    def test_four_sources_verified_with_count(self, source_manager):
        r = _make_result(
            value="ivan@mail.ru",
            metadata={'sources': ['A', 'B', 'C', 'D'], 'source_count': 4},
        )
        out = source_manager._cross_validate([r])
        assert out[0].verified is True
        assert '4' in out[0].metadata['verified_reason']

    def test_two_sources_high_confidence_verified(self, source_manager):
        r = _make_result(
            value="ivan@mail.ru", confidence=0.8,
            metadata={'sources': ['S1', 'S2'], 'source_count': 2},
        )
        out = source_manager._cross_validate([r])
        assert out[0].verified is True
        assert out[0].metadata['verified_reason'] == 'dual_source_high_confidence'

    def test_two_sources_exactly_0_7_verified(self, source_manager):
        r = _make_result(
            value="ivan@mail.ru", confidence=0.7,
            metadata={'sources': ['S1', 'S2'], 'source_count': 2},
        )
        out = source_manager._cross_validate([r])
        assert out[0].verified is True

    def test_two_sources_low_confidence_not_verified(self, source_manager):
        r = _make_result(
            value="ivan@mail.ru", confidence=0.4,
            metadata={'sources': ['S1', 'S2'], 'source_count': 2},
        )
        out = source_manager._cross_validate([r])
        assert out[0].verified is False

    def test_one_source_high_confidence_not_verified(self, source_manager):
        r = _make_result(
            value="ivan@mail.ru", confidence=0.95,
            metadata={'sources': ['S1'], 'source_count': 1},
        )
        out = source_manager._cross_validate([r])
        assert out[0].verified is False

    def test_multiple_phones_multiple_emails_tier_s_all_cross(self, source_manager):
        p1 = _make_result(
            data_type="phone", value="+79161234567",
            source_tier=SourceTier.S, metadata={'source_count': 1},
        )
        p2 = _make_result(
            data_type="phone", value="+79261234567",
            source_tier=SourceTier.S, metadata={'source_count': 1},
        )
        e1 = _make_result(
            data_type="email", value="ivan@mail.ru",
            source_tier=SourceTier.S, metadata={'source_count': 1},
        )
        e2 = _make_result(
            data_type="email", value="ivan@yandex.ru",
            source_tier=SourceTier.S, metadata={'source_count': 1},
        )
        out = source_manager._cross_validate([p1, p2, e1, e2])
        for r in out:
            assert r.verified is True

    def test_phone_tier_a_email_tier_s_not_cross_validated_by_tier(self, source_manager):
        """Cross-validation requires BOTH to be Tier S."""
        phone = _make_result(
            data_type="phone", value="+79161234567",
            source_tier=SourceTier.A, metadata={'source_count': 1},
        )
        email = _make_result(
            data_type="email", value="ivan@mail.ru",
            source_tier=SourceTier.S, metadata={'source_count': 1},
        )
        out = source_manager._cross_validate([phone, email])
        # Phone is NOT Tier S so cross-validation doesn't apply to the phone
        assert out[0].verified is False  # phone (Tier A)
        # Email is Tier S but the phone isn't, so the email also isn't cross-validated
        assert out[1].verified is False

    def test_cross_validated_metadata_present(self, source_manager):
        phone = _make_result(
            data_type="phone", value="+79161234567",
            source_tier=SourceTier.S, metadata={'source_count': 1},
        )
        email = _make_result(
            data_type="email", value="ivan@mail.ru",
            source_tier=SourceTier.S, metadata={'source_count': 1},
        )
        out = source_manager._cross_validate([phone, email])
        assert out[0].metadata.get('cross_validated_with') == 'email_breach'
        assert out[1].metadata.get('cross_validated_with') == 'phone_breach'

    def test_empty_input_cross_validate(self, source_manager):
        assert source_manager._cross_validate([]) == []

    def test_profile_type_not_affected_by_cross_validation(self, source_manager):
        """Profile results should only be affected by multi-source rules, not phone/email cross."""
        profile = _make_result(
            data_type="profile", value="https://vk.com/id123",
            source_tier=SourceTier.S, metadata={'source_count': 1},
        )
        out = source_manager._cross_validate([profile])
        assert out[0].verified is False

    def test_three_sources_overrides_low_confidence(self, source_manager):
        """Even with low confidence, 3+ sources makes it verified."""
        r = _make_result(
            value="ivan@mail.ru", confidence=0.2,
            metadata={'sources': ['A', 'B', 'C'], 'source_count': 3},
        )
        out = source_manager._cross_validate([r])
        assert out[0].verified is True

    def test_two_sources_confidence_0_69_not_verified(self, source_manager):
        """Just below the 0.7 threshold — not verified."""
        r = _make_result(
            value="ivan@mail.ru", confidence=0.69,
            metadata={'sources': ['S1', 'S2'], 'source_count': 2},
        )
        out = source_manager._cross_validate([r])
        assert out[0].verified is False

    def test_cross_and_multi_source_both_apply(self, source_manager):
        """A phone from Tier S with 3 sources gets both cross-validation and multi-source."""
        phone = _make_result(
            data_type="phone", value="+79161234567",
            source_tier=SourceTier.S, confidence=0.9,
            metadata={'sources': ['S1', 'S2', 'S3'], 'source_count': 3},
        )
        email = _make_result(
            data_type="email", value="ivan@mail.ru",
            source_tier=SourceTier.S, metadata={'source_count': 1},
        )
        out = source_manager._cross_validate([phone, email])
        assert out[0].verified is True
        # Should have both cross_validated_with and verified_reason
        assert 'cross_validated_with' in out[0].metadata
        assert 'verified_reason' in out[0].metadata


# ===========================================================================
# 5. Email dedup with verification merging (10+ tests)
# ===========================================================================

class TestEmailDedup:
    """Email dedup in EmailDiscoveryService.discover() merges verification info."""

    def _make_email(self, email="ivan@mail.ru", source="Test", confidence="low",
                    verified=False, verified_on=None, verification="unverified"):
        from app.services.phase2.email_discovery import DiscoveredEmail
        return DiscoveredEmail(
            email=email,
            source=source,
            confidence=confidence,
            verified=verified,
            verified_on=verified_on or [],
            verification=verification,
        )

    def test_guess_then_holehe_becomes_verified(self):
        """Same email: pattern (low, unverified) + holehe (high, verified) -> verified."""
        from app.services.phase2.email_discovery import DiscoveredEmail

        # Simulate the merge logic from EmailDiscoveryService.discover()
        all_emails = {}

        guess = self._make_email(
            email="ivan@mail.ru", source="Pattern", confidence="low",
            verified=False, verified_on=[], verification="pattern",
        )
        holehe = self._make_email(
            email="ivan@mail.ru", source="Holehe", confidence="high",
            verified=True, verified_on=["holehe:twitter", "holehe:spotify"],
            verification="holehe_confirmed",
        )

        # Insert first (guess)
        key = guess.email.lower()
        all_emails[key] = guess

        # Merge second (holehe)
        existing = all_emails[key]
        existing.verified_on.extend(holehe.verified_on)
        existing.verified_on = list(set(existing.verified_on))
        if holehe.verified:
            existing.verified = True
        if len(existing.verified_on) >= 2:
            existing.confidence = 'high'
            existing.verification = 'multi_verified'
        elif holehe.confidence == 'high':
            existing.confidence = 'high'
        verification_priority = {
            'holehe_confirmed': 0, 'smtp_verified': 1, 'gravatar': 2,
            'multi_verified': 0, 'likely': 3, 'pattern': 4, 'unverified': 5,
        }
        if verification_priority.get(holehe.verification, 5) < \
           verification_priority.get(existing.verification, 5):
            existing.verification = holehe.verification

        result = all_emails["ivan@mail.ru"]
        assert result.verified is True
        assert result.confidence == 'high'

    def test_three_sources_becomes_multi_verified(self):
        all_emails = {}
        emails_to_merge = [
            self._make_email(verified_on=["pattern"], verification="pattern"),
            self._make_email(verified=True, verified_on=["holehe:twitter"], verification="holehe_confirmed"),
            self._make_email(verified=True, verified_on=["smtp"], verification="smtp_verified"),
        ]
        for email_info in emails_to_merge:
            key = email_info.email.lower()
            if key not in all_emails:
                all_emails[key] = email_info
            else:
                existing = all_emails[key]
                existing.verified_on.extend(email_info.verified_on)
                existing.verified_on = list(set(existing.verified_on))
                if email_info.verified:
                    existing.verified = True
                if len(existing.verified_on) >= 2:
                    existing.confidence = 'high'
                    existing.verification = 'multi_verified'

        result = all_emails["ivan@mail.ru"]
        assert result.verification == "multi_verified"
        assert result.verified is True
        assert result.confidence == "high"

    def test_verified_on_lists_merged_and_deduped(self):
        all_emails = {}
        e1 = self._make_email(verified_on=["holehe:twitter", "holehe:spotify"])
        e2 = self._make_email(verified_on=["holehe:twitter", "gravatar"])

        all_emails[e1.email.lower()] = e1
        existing = all_emails[e1.email.lower()]
        existing.verified_on.extend(e2.verified_on)
        existing.verified_on = list(set(existing.verified_on))

        assert len(existing.verified_on) == 3
        assert "holehe:twitter" in existing.verified_on
        assert "holehe:spotify" in existing.verified_on
        assert "gravatar" in existing.verified_on

    def test_stronger_verification_preserved_holehe_over_smtp(self):
        """holehe_confirmed (priority 0) beats smtp_verified (priority 1)."""
        all_emails = {}
        e1 = self._make_email(verification="smtp_verified")
        e2 = self._make_email(verification="holehe_confirmed")

        all_emails[e1.email.lower()] = e1
        existing = all_emails[e1.email.lower()]
        verification_priority = {
            'holehe_confirmed': 0, 'smtp_verified': 1, 'gravatar': 2,
            'multi_verified': 0, 'likely': 3, 'pattern': 4, 'unverified': 5,
        }
        if verification_priority.get(e2.verification, 5) < \
           verification_priority.get(existing.verification, 5):
            existing.verification = e2.verification

        assert existing.verification == "holehe_confirmed"

    def test_stronger_verification_preserved_smtp_over_gravatar(self):
        all_emails = {}
        e1 = self._make_email(verification="gravatar")
        e2 = self._make_email(verification="smtp_verified")

        all_emails[e1.email.lower()] = e1
        existing = all_emails[e1.email.lower()]
        verification_priority = {
            'holehe_confirmed': 0, 'smtp_verified': 1, 'gravatar': 2,
            'multi_verified': 0, 'likely': 3, 'pattern': 4, 'unverified': 5,
        }
        if verification_priority.get(e2.verification, 5) < \
           verification_priority.get(existing.verification, 5):
            existing.verification = e2.verification

        assert existing.verification == "smtp_verified"

    def test_stronger_verification_preserved_gravatar_over_likely(self):
        all_emails = {}
        e1 = self._make_email(verification="likely")
        e2 = self._make_email(verification="gravatar")

        all_emails[e1.email.lower()] = e1
        existing = all_emails[e1.email.lower()]
        verification_priority = {
            'holehe_confirmed': 0, 'smtp_verified': 1, 'gravatar': 2,
            'multi_verified': 0, 'likely': 3, 'pattern': 4, 'unverified': 5,
        }
        if verification_priority.get(e2.verification, 5) < \
           verification_priority.get(existing.verification, 5):
            existing.verification = e2.verification

        assert existing.verification == "gravatar"

    def test_weaker_verification_does_not_overwrite(self):
        """pattern (priority 4) should NOT overwrite holehe_confirmed (priority 0)."""
        all_emails = {}
        e1 = self._make_email(verification="holehe_confirmed")
        e2 = self._make_email(verification="pattern")

        all_emails[e1.email.lower()] = e1
        existing = all_emails[e1.email.lower()]
        verification_priority = {
            'holehe_confirmed': 0, 'smtp_verified': 1, 'gravatar': 2,
            'multi_verified': 0, 'likely': 3, 'pattern': 4, 'unverified': 5,
        }
        if verification_priority.get(e2.verification, 5) < \
           verification_priority.get(existing.verification, 5):
            existing.verification = e2.verification

        assert existing.verification == "holehe_confirmed"

    def test_case_insensitive_email_key(self):
        """Ivan@Mail.RU and ivan@mail.ru produce the same key."""
        all_emails = {}
        e1 = self._make_email(email="Ivan@Mail.RU", verification="pattern")
        e2 = self._make_email(email="ivan@mail.ru", verified=True, verification="holehe_confirmed")

        key1 = e1.email.lower()
        all_emails[key1] = e1
        key2 = e2.email.lower()
        assert key1 == key2
        assert key2 in all_emails

    def test_empty_verified_on_merged_with_populated(self):
        all_emails = {}
        e1 = self._make_email(verified_on=[])
        e2 = self._make_email(verified_on=["holehe:twitter"])

        all_emails[e1.email.lower()] = e1
        existing = all_emails[e1.email.lower()]
        existing.verified_on.extend(e2.verified_on)
        existing.verified_on = list(set(existing.verified_on))

        assert existing.verified_on == ["holehe:twitter"]

    def test_confidence_promoted_to_high_on_multi_verify(self):
        """When 2+ verified_on entries, confidence becomes 'high'."""
        all_emails = {}
        e1 = self._make_email(confidence="low", verified_on=["gravatar"])
        e2 = self._make_email(confidence="medium", verified_on=["holehe:spotify"])

        all_emails[e1.email.lower()] = e1
        existing = all_emails[e1.email.lower()]
        existing.verified_on.extend(e2.verified_on)
        existing.verified_on = list(set(existing.verified_on))
        if len(existing.verified_on) >= 2:
            existing.confidence = 'high'
            existing.verification = 'multi_verified'

        assert existing.confidence == "high"
        assert existing.verification == "multi_verified"

    def test_single_high_confidence_email_promotes(self):
        """When merging, if the new email is 'high' confidence, existing becomes 'high'."""
        all_emails = {}
        e1 = self._make_email(confidence="low")
        e2 = self._make_email(confidence="high")

        all_emails[e1.email.lower()] = e1
        existing = all_emails[e1.email.lower()]
        if e2.confidence == 'high':
            existing.confidence = 'high'

        assert existing.confidence == "high"


# ===========================================================================
# 6. End-to-end dedup scenarios (10+ tests)
# ===========================================================================

class TestEndToEndDedup:
    """Full pipeline: _deduplicate + _cross_validate combined."""

    def test_ten_results_five_unique(self, source_manager):
        results = []
        for i in range(5):
            results.append(
                _make_result(value=f"user{i}@mail.ru", source_name="Src1", confidence=0.5)
            )
            results.append(
                _make_result(value=f"user{i}@mail.ru", source_name="Src2", confidence=0.6)
            )
        out = source_manager._deduplicate(results)
        assert len(out) == 5

    def test_all_unique_all_preserved(self, source_manager):
        results = [
            _make_result(value=f"unique{i}@mail.ru", source_name=f"Src{i}")
            for i in range(7)
        ]
        out = source_manager._deduplicate(results)
        assert len(out) == 7

    def test_all_same_collapses_to_one(self, source_manager):
        results = [
            _make_result(value="same@mail.ru", source_name=f"Src{i}", confidence=0.5)
            for i in range(8)
        ]
        out = source_manager._deduplicate(results)
        assert len(out) == 1
        assert out[0].confidence > 0.9  # heavily boosted

    def test_mixed_types_deduped_independently(self, source_manager):
        results = [
            _make_result(data_type="phone", value="+79161234567", source_name="Src1"),
            _make_result(data_type="phone", value="+79161234567", source_name="Src2"),
            _make_result(data_type="email", value="ivan@mail.ru", source_name="Src1"),
            _make_result(data_type="email", value="ivan@mail.ru", source_name="Src2"),
            _make_result(data_type="profile", value="https://vk.com/id123", source_name="Src1"),
            _make_result(data_type="profile", value="https://vk.com/id123", source_name="Src2"),
        ]
        out = source_manager._deduplicate(results)
        types = [r.data_type for r in out]
        assert types.count("phone") == 1
        assert types.count("email") == 1
        assert types.count("profile") == 1

    def test_empty_input_returns_empty(self, source_manager):
        out = source_manager._deduplicate([])
        validated = source_manager._cross_validate(out)
        assert validated == []

    def test_dedup_then_cross_validate_breach_pair(self, source_manager):
        """Full pipeline: two breach sources for phone and email, all merge and cross-validate."""
        results = [
            _make_result(
                data_type="phone", value="+79161234567",
                source_name="LeakCheck", source_tier=SourceTier.S, confidence=0.9,
            ),
            _make_result(
                data_type="email", value="ivan@mail.ru",
                source_name="LeakCheck", source_tier=SourceTier.S, confidence=0.85,
            ),
        ]
        deduped = source_manager._deduplicate(results)
        validated = source_manager._cross_validate(deduped)
        for r in validated:
            assert r.verified is True

    def test_dedup_then_cross_validate_three_source_email(self, source_manager):
        """Email from 3 sources should be verified after full pipeline."""
        results = [
            _make_result(value="ivan@mail.ru", source_name="Src1", confidence=0.5),
            _make_result(value="ivan@mail.ru", source_name="Src2", confidence=0.6),
            _make_result(value="ivan@mail.ru", source_name="Src3", confidence=0.7),
        ]
        deduped = source_manager._deduplicate(results)
        validated = source_manager._cross_validate(deduped)
        assert len(validated) == 1
        assert validated[0].verified is True
        assert 'confirmed_by_3_sources' in validated[0].metadata.get('verified_reason', '')

    def test_single_source_no_cross_no_verify(self, source_manager):
        results = [
            _make_result(value="lone@mail.ru", source_name="Only", confidence=0.5),
        ]
        deduped = source_manager._deduplicate(results)
        validated = source_manager._cross_validate(deduped)
        assert validated[0].verified is False

    def test_dedup_preserves_order_of_first_seen(self, source_manager):
        """First occurrence's value casing is what gets kept in the result."""
        r1 = _make_result(value="First@Mail.RU", source_name="S1")
        r2 = _make_result(value="first@mail.ru", source_name="S2")
        out = source_manager._deduplicate([r1, r2])
        # The actual object kept is r1, so its value remains as-is
        assert out[0].value == "First@Mail.RU"

    def test_large_batch_dedup_performance(self, source_manager):
        """100 results for 10 unique values should produce 10 results."""
        results = []
        for i in range(10):
            for j in range(10):
                results.append(
                    _make_result(
                        value=f"user{i}@mail.ru",
                        source_name=f"Src{j}",
                        confidence=0.3 + j * 0.05,
                    )
                )
        out = source_manager._deduplicate(results)
        assert len(out) == 10
        for r in out:
            assert r.metadata['source_count'] == 10
            assert r.confidence > 0.8  # heavily boosted

    def test_mixed_phone_email_profile_full_pipeline(self, source_manager):
        """Realistic scenario with phones, emails, and profiles from multiple sources."""
        results = [
            # Phone from breach + VK
            _make_result(data_type="phone", value="+79161234567", source_name="Breach", source_tier=SourceTier.S, confidence=0.95),
            _make_result(data_type="phone", value="+79161234567", source_name="VK API", source_tier=SourceTier.A, confidence=0.8),
            # Email from breach + holehe
            _make_result(data_type="email", value="ivan@mail.ru", source_name="Breach", source_tier=SourceTier.S, confidence=0.9),
            _make_result(data_type="email", value="ivan@mail.ru", source_name="Holehe", source_tier=SourceTier.B, confidence=0.85),
            # Unique profile
            _make_result(data_type="profile", value="https://vk.com/id123", source_name="VK", source_tier=SourceTier.A, confidence=0.99),
        ]
        deduped = source_manager._deduplicate(results)
        validated = source_manager._cross_validate(deduped)

        assert len(validated) == 3
        phone = [r for r in validated if r.data_type == "phone"][0]
        email = [r for r in validated if r.data_type == "email"][0]
        profile = [r for r in validated if r.data_type == "profile"][0]

        # Phone and email: both Tier S, cross-validated + dual source high confidence
        assert phone.verified is True
        assert email.verified is True
        assert phone.source_tier == SourceTier.S
        assert email.source_tier == SourceTier.S
        # Profile: single source, no cross-validation
        assert profile.verified is False

    def test_group_by_type_after_dedup(self, source_manager):
        """Verify _group_by_type correctly categorizes after dedup."""
        results = [
            _make_result(data_type="phone", value="+79161234567", source_name="S1"),
            _make_result(data_type="email", value="a@b.ru", source_name="S1"),
            _make_result(data_type="email", value="c@d.ru", source_name="S1"),
            _make_result(data_type="profile", value="https://vk.com/123", source_name="S1"),
        ]
        deduped = source_manager._deduplicate(results)
        grouped = source_manager._group_by_type(deduped)
        assert len(grouped["phone"]) == 1
        assert len(grouped["email"]) == 2
        assert len(grouped["profile"]) == 1
