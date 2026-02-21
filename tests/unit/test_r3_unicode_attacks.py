"""
Round 3 (ADVERSARIAL) -- Unicode edge cases and attacks.

Tests for Cyrillic homoglyphs, bidirectional text, combining characters,
fullwidth/halfwidth characters, surrogate/astral plane, Unicode normalization
forms, and miscellaneous edge Unicode cases.

90+ tests covering all functions that handle user-supplied text:
- EmailDiscoveryService._transliterate, _clean_username, _is_valid_email, _generate_candidates
- normalize_phone (app.utils.phone)
- RussianPhoneValidator.validate, extract_phones
- PhoneDiscoveryService._extract_from_usernames, _normalize_key
- SourceManager._deduplicate
- SourceResult construction
"""

import unicodedata
import pytest

from app.services.phase2.email_discovery import EmailDiscoveryService
from app.utils.phone import normalize_phone
from app.services.phase2.russian_phone_validator import (
    RussianPhoneValidator, validate_phone, extract_phones_from_text,
)
from app.services.phase2.phone_discovery import PhoneDiscoveryService
from app.services.phase2.base_source import SourceResult, SourceTier
from app.services.phase2.source_manager import SourceManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _email_svc():
    """Create a fresh EmailDiscoveryService for unit method tests."""
    return EmailDiscoveryService()


def _phone_svc():
    """Create a fresh PhoneDiscoveryService."""
    return PhoneDiscoveryService()


def _validator():
    return RussianPhoneValidator()


def _make_result(value, data_type="email", source="test", confidence=0.8):
    return SourceResult(
        data_type=data_type,
        value=value,
        source_name=source,
        source_tier=SourceTier.C,
        confidence=confidence,
    )


# ═══════════════════════════════════════════════════════════════════════════
# 1. Cyrillic Homoglyphs  (15 tests)
# ═══════════════════════════════════════════════════════════════════════════

class TestCyrillicHomoglyphs:
    """Cyrillic letters that visually match Latin ones."""

    def test_cyrillic_a_vs_latin_a_in_email(self):
        """Cyrillic 'а' (U+0430) must be rejected from email local part."""
        svc = _email_svc()
        # email with Cyrillic 'а' at position 0
        email = "\u0430test@mail.ru"
        assert not svc._is_valid_email(email)

    def test_cyrillic_o_vs_latin_o_in_email(self):
        """Cyrillic 'о' (U+043E) should be invalid in email."""
        svc = _email_svc()
        email = "test\u043E@mail.ru"
        assert not svc._is_valid_email(email)

    def test_cyrillic_c_vs_latin_c_in_username(self):
        """_clean_username strips non-Latin, so Cyrillic 'с' (U+0441) is removed."""
        svc = _email_svc()
        result = svc._clean_username("\u0441ool_user")
        # Cyrillic с is not [a-z0-9_.], so it's stripped
        assert "\u0441" not in result
        assert result == "ool_user"

    def test_cyrillic_r_vs_latin_p_in_username(self):
        """Cyrillic 'р' (U+0440) is stripped from usernames."""
        svc = _email_svc()
        result = svc._clean_username("\u0440avel")
        assert result == "avel"

    def test_cyrillic_kh_vs_latin_x_in_username(self):
        """Cyrillic 'х' (U+0445) is stripped from usernames."""
        svc = _email_svc()
        result = svc._clean_username("\u0445ero")
        assert result == "ero"

    def test_cyrillic_e_vs_latin_e_in_email_domain(self):
        """Cyrillic 'е' (U+0435) in domain part invalidates email."""
        svc = _email_svc()
        email = "test@m\u0435il.ru"  # Cyrillic е in 'mеil'
        assert not svc._is_valid_email(email)

    def test_full_cyrillic_lookalike_email_rejected(self):
        """An email that looks Latin but is entirely Cyrillic is rejected."""
        svc = _email_svc()
        # 'аеос' in Cyrillic that looks like 'aeos'
        email = "\u0430\u0435\u043E\u0441@mail.ru"
        assert not svc._is_valid_email(email)

    def test_transliterate_cyrillic_a(self):
        """_transliterate maps Cyrillic 'а' to Latin 'a'."""
        svc = _email_svc()
        assert svc._transliterate("\u0430") == "a"

    def test_transliterate_cyrillic_o(self):
        svc = _email_svc()
        assert svc._transliterate("\u043E") == "o"

    def test_transliterate_cyrillic_e(self):
        svc = _email_svc()
        assert svc._transliterate("\u0435") == "e"

    def test_transliterate_cyrillic_p(self):
        """Cyrillic 'р' (U+0440) maps to Latin 'r', not 'p'."""
        svc = _email_svc()
        assert svc._transliterate("\u0440") == "r"

    def test_transliterate_mixed_script_string(self):
        """Mixed Cyrillic + Latin string passes Cyrillic through translit, keeps Latin."""
        svc = _email_svc()
        # "\u041c\u0430\u0448\u0430" = "Маша"
        result = svc._transliterate("\u041c\u0430\u0448\u0430")
        assert result == "masha"

    def test_transliterate_uppercase_cyrillic(self):
        """_transliterate calls .lower() first, so uppercase Cyrillic works."""
        svc = _email_svc()
        # "АННА" uppercase
        result = svc._transliterate("\u0410\u041d\u041d\u0410")
        assert result == "anna"

    def test_dedup_latin_vs_cyrillic_email_not_merged(self):
        """Latin 'test@mail.ru' and Cyrillic 'tеst@mail.ru' have different bytes."""
        mgr = SourceManager.__new__(SourceManager)
        mgr.sources = []
        r1 = _make_result("test@mail.ru")
        # Cyrillic е in 'tеst'
        r2 = _make_result("t\u0435st@mail.ru")
        results = mgr._deduplicate([r1, r2])
        # They differ at byte level, so both survive
        values = {r.value.lower().strip() for r in results}
        assert len(values) == 2

    def test_clean_username_all_cyrillic_returns_empty(self):
        """Entirely Cyrillic username is stripped to empty string."""
        svc = _email_svc()
        result = svc._clean_username("\u0438\u0432\u0430\u043d")  # 'иван'
        assert result == ""


# ═══════════════════════════════════════════════════════════════════════════
# 2. Bidirectional Text (RTL)  (10 tests)
# ═══════════════════════════════════════════════════════════════════════════

class TestBidirectionalText:
    """RTL overrides and marks injected into phone/email/name strings."""

    def test_rtl_override_in_phone(self):
        """RTL override U+202E in phone string -- digits still extracted."""
        phone = "+7\u202E9161234567"
        result = normalize_phone(phone)
        # \D strips the RTL char; digits = 79161234567
        assert result.startswith("+7")

    def test_rtl_mark_in_email(self):
        """RTL mark U+200F in email invalidates it."""
        svc = _email_svc()
        email = "test\u200F@mail.ru"
        assert not svc._is_valid_email(email)

    def test_ltr_mark_in_email(self):
        """LTR mark U+200E in email invalidates it."""
        svc = _email_svc()
        email = "test\u200E@mail.ru"
        assert not svc._is_valid_email(email)

    def test_rtl_override_in_username(self):
        """RTL override is stripped from username by _clean_username.
        Note: _clean_username first strips ^(user|id|profile|@), so 'user'
        prefix is consumed, then RTL char is stripped leaving 'name'."""
        svc = _email_svc()
        result = svc._clean_username("user\u202Ename")
        assert "\u202E" not in result
        # 'user' prefix is stripped first, then RTL char stripped -> 'name'
        assert result == "name"

    def test_arabic_chars_in_phone_normalize(self):
        """Arabic characters mixed with digits."""
        phone = "+7\u0627916\u06281234567"
        result = normalize_phone(phone)
        # Non-digit Arabic stripped, depends on digit count
        assert isinstance(result, str)

    def test_rtl_embedding_in_phone_string(self):
        """U+202B (RTL embedding) in phone."""
        phone = "\u202B+79161234567"
        result = normalize_phone(phone)
        assert result == "+79161234567"

    def test_pop_directional_formatting_in_phone(self):
        """U+202C (PDF) in phone."""
        phone = "+7916\u202C1234567"
        result = normalize_phone(phone)
        assert result == "+79161234567"

    def test_transliterate_with_rtl_chars_passthrough(self):
        """RTL chars not in translit map pass through unchanged."""
        svc = _email_svc()
        result = svc._transliterate("\u0627\u0628")  # Arabic alef + ba
        # These are not in the Cyrillic map, so they pass through
        assert "\u0627" in result
        assert "\u0628" in result

    def test_phone_extract_ignores_rtl_markers(self):
        """extract_phones handles RTL markers in text without crashing."""
        v = _validator()
        text = "Call me \u202E+79161234567\u202C anytime"
        phones = v.extract_phones(text)
        # The RTL override reverses visual display but regex works on logical order
        # Whether it matches depends on the regex, but it must not crash
        assert isinstance(phones, list)

    def test_rtl_isolate_in_email(self):
        """U+2066 (LRI), U+2067 (RLI), U+2069 (PDI) in email are invalid."""
        svc = _email_svc()
        email = "\u2067test\u2069@mail.ru"
        assert not svc._is_valid_email(email)


# ═══════════════════════════════════════════════════════════════════════════
# 3. Combining Characters  (15 tests)
# ═══════════════════════════════════════════════════════════════════════════

class TestCombiningCharacters:
    """NFD decomposition, combining diacriticals, zero-width joiners."""

    def test_nfc_yo_transliterate(self):
        """NFC ё (U+0451) transliterates to 'e'."""
        svc = _email_svc()
        assert svc._transliterate("\u0451") == "e"

    def test_nfd_yo_transliterate(self):
        """NFD ё = е (U+0435) + combining diaeresis (U+0308).
        _transliterate maps е -> 'e', combining mark passes through."""
        svc = _email_svc()
        decomposed = "\u0435\u0308"  # е + combining diaeresis
        result = svc._transliterate(decomposed)
        # The combining diaeresis U+0308 is not in the map, passes through
        assert result.startswith("e")

    def test_nfc_short_i_transliterate(self):
        """NFC й (U+0439) transliterates to 'y'."""
        svc = _email_svc()
        assert svc._transliterate("\u0439") == "y"

    def test_nfd_short_i_transliterate(self):
        """NFD й = и (U+0438) + combining breve (U+0306).
        _transliterate maps и -> 'i', combining breve passes through."""
        svc = _email_svc()
        decomposed = "\u0438\u0306"  # и + combining breve
        result = svc._transliterate(decomposed)
        # и -> 'i', combining breve passes through
        assert result.startswith("i")

    def test_zwj_in_phone(self):
        """Zero-width joiner U+200D in phone string is stripped as \\D."""
        result = normalize_phone("+7\u200D9161234567")
        assert result == "+79161234567"

    def test_zwnj_in_phone(self):
        """Zero-width non-joiner U+200C in phone string is stripped as \\D."""
        result = normalize_phone("+7\u200C9161234567")
        assert result == "+79161234567"

    def test_zwj_in_email_invalid(self):
        """Zero-width joiner in email makes it invalid."""
        svc = _email_svc()
        email = "te\u200Dst@mail.ru"
        assert not svc._is_valid_email(email)

    def test_combining_marks_in_email(self):
        """Combining acute accent U+0301 in email makes it invalid."""
        svc = _email_svc()
        email = "te\u0301st@mail.ru"
        assert not svc._is_valid_email(email)

    def test_multiple_combining_marks(self):
        """Multiple combining marks (Zalgo-style) in phone stripped by \\D."""
        phone = "+7\u0300\u0301\u0302\u03039161234567"
        result = normalize_phone(phone)
        assert result == "+79161234567"

    def test_combining_marks_in_username(self):
        """Combining marks stripped from username by _clean_username."""
        svc = _email_svc()
        result = svc._clean_username("te\u0301st_user")
        assert result == "test_user"

    def test_nfd_full_name_transliterate(self):
        """Full Cyrillic name in NFD form through _transliterate."""
        svc = _email_svc()
        # "Алёна" in NFC
        nfc = "\u0410\u043B\u0451\u043D\u0430"
        nfd = unicodedata.normalize("NFD", nfc)
        nfc_result = svc._transliterate(nfc)
        nfd_result = svc._transliterate(nfd)
        assert nfc_result == "alena"
        # NFD result starts with "al" but the combining diaeresis may leak
        assert nfd_result.startswith("al")

    def test_phone_normalize_with_combining_enclosing_circle(self):
        """Combining enclosing circle U+20DD should be stripped."""
        phone = "+79161234567\u20DD"
        result = normalize_phone(phone)
        assert result == "+79161234567"

    def test_transliterate_empty_after_soft_hard_sign(self):
        """ъ and ь map to empty string."""
        svc = _email_svc()
        assert svc._transliterate("\u044A") == ""  # ъ
        assert svc._transliterate("\u044C") == ""  # ь

    def test_generate_candidates_nfc_nfd_name(self):
        """_generate_candidates does not crash on NFD-decomposed name."""
        svc = _email_svc()
        # "Алёна" NFD
        nfd_name = unicodedata.normalize("NFD", "\u0410\u043B\u0451\u043D\u0430")
        candidates = svc._generate_candidates(nfd_name, "Иванова", [])
        assert isinstance(candidates, list)

    def test_combining_cedilla_in_phone(self):
        """Combining cedilla U+0327 in phone stripped."""
        phone = "+7916\u03271234567"
        result = normalize_phone(phone)
        assert result == "+79161234567"


# ═══════════════════════════════════════════════════════════════════════════
# 4. Fullwidth / Halfwidth Characters  (10 tests)
# ═══════════════════════════════════════════════════════════════════════════

class TestFullwidthHalfwidth:
    """Fullwidth digits, Latin, symbols."""

    def test_fullwidth_digits_in_phone(self):
        """Fullwidth digits 0-9 (U+FF10-FF19) are non-ASCII, \\D strips them."""
        # Fullwidth +7 9161234567
        fw_phone = "\uFF0B\uFF17\uFF19\uFF11\uFF16\uFF11\uFF12\uFF13\uFF14\uFF15\uFF16\uFF17"
        result = normalize_phone(fw_phone)
        # \D strips everything (fullwidth digits are NOT \d), so digits == ""
        # normalize_phone returns original for empty/unrecognized
        assert result == fw_phone

    def test_fullwidth_at_sign_in_email(self):
        """Fullwidth @ (U+FF20) is not matched by regex, email is invalid."""
        svc = _email_svc()
        email = "test\uFF20mail.ru"
        assert not svc._is_valid_email(email)

    def test_fullwidth_latin_in_email(self):
        """Fullwidth Latin 'Ａ' (U+FF21) etc. are not [a-z], email is invalid."""
        svc = _email_svc()
        email = "\uFF41\uFF42\uFF43@mail.ru"  # fullwidth abc
        assert not svc._is_valid_email(email)

    def test_fullwidth_digits_in_username(self):
        """Fullwidth digits in username are stripped by [^a-z0-9_.].
        _clean_username first strips ^(user|id|profile|@) prefix, consuming 'user',
        then fullwidth digits are stripped as non-[a-z0-9_.], leaving empty."""
        svc = _email_svc()
        result = svc._clean_username("user\uFF11\uFF12\uFF13")
        assert result == ""

    def test_normalize_phone_fullwidth_returns_original(self):
        """normalize_phone returns original when fullwidth digits yield no match."""
        fw = "\uFF18\uFF19\uFF11\uFF16\uFF11\uFF12\uFF13\uFF14\uFF15\uFF16\uFF17"
        result = normalize_phone(fw)
        assert result == fw

    def test_halfwidth_katakana_in_name_transliterate(self):
        """Halfwidth Katakana (U+FF65-FF9F) passes through _transliterate."""
        svc = _email_svc()
        result = svc._transliterate("\uFF71\uFF72\uFF73")  # halfwidth ア イ ウ
        # Not in Cyrillic map, passes through
        assert "\uFF71" in result

    def test_fullwidth_period_in_email(self):
        """Fullwidth period (U+FF0E) is not matched by email regex."""
        svc = _email_svc()
        email = "test@mail\uFF0Eru"
        assert not svc._is_valid_email(email)

    def test_phone_normalize_key_fullwidth(self):
        """PhoneDiscoveryService._normalize_key with fullwidth digits.
        Python 3 re \\d matches Unicode decimal digits (Nd category),
        including fullwidth digits, so \\D does NOT strip them."""
        svc = _phone_svc()
        result = svc._normalize_key("\uFF17\uFF19\uFF11\uFF16\uFF11\uFF12\uFF13\uFF14\uFF15\uFF16\uFF17")
        # Fullwidth digits are Unicode \\d, so they survive \\D stripping
        # [-10:] returns the last 10 fullwidth chars
        assert len(result) == 10

    def test_fullwidth_hyphen_in_phone(self):
        """Fullwidth hyphen (U+FF0D) is stripped by \\D."""
        phone = "+7\uFF0D916\uFF0D1234567"
        result = normalize_phone(phone)
        assert result == "+79161234567"

    def test_fullwidth_plus_in_phone(self):
        """Fullwidth plus (U+FF0B) is stripped by \\D, so digit count might change."""
        phone = "\uFF0B79161234567"
        result = normalize_phone(phone)
        # \D strips fullwidth plus, digits = 79161234567 (11), starts with 7
        assert result == "+79161234567"


# ═══════════════════════════════════════════════════════════════════════════
# 5. Surrogate Pairs and Astral Plane  (10 tests)
# ═══════════════════════════════════════════════════════════════════════════

class TestAstralPlane:
    """Emoji, math symbols, and other characters outside the BMP."""

    def test_emoji_in_phone(self):
        """Emoji in phone string stripped by \\D."""
        phone = "+7\U0001F600916\U0001F6001234567"
        result = normalize_phone(phone)
        assert result == "+79161234567"

    def test_emoji_in_email_invalid(self):
        """Emoji in email is invalid."""
        svc = _email_svc()
        email = "test\U0001F600@mail.ru"
        assert not svc._is_valid_email(email)

    def test_emoji_in_username_stripped(self):
        """Emoji in username stripped by _clean_username.
        _clean_username strips ^(user|id|profile|@) first, consuming 'user',
        then emoji is stripped, leaving 'name'."""
        svc = _email_svc()
        result = svc._clean_username("user\U0001F600name")
        assert result == "name"

    def test_math_bold_capitals_in_name(self):
        """Mathematical bold A-C (U+1D400-1D402) pass through _transliterate."""
        svc = _email_svc()
        result = svc._transliterate("\U0001D400\U0001D401\U0001D402")
        # These are not in the Cyrillic map; .lower() may or may not affect them
        assert isinstance(result, str)

    def test_cjk_in_transliterate(self):
        """CJK characters pass through _transliterate unchanged."""
        svc = _email_svc()
        result = svc._transliterate("\u4e2d\u6587")  # 中文
        assert "\u4e2d" in result

    def test_emoji_in_phone_extract(self):
        """extract_phones does not crash on emoji-laden text."""
        v = _validator()
        text = "\U0001F4DE Call +79161234567 \U0001F4F1"
        phones = v.extract_phones(text)
        assert len(phones) >= 1
        assert phones[0].normalized == "+79161234567"

    def test_musical_symbols_in_email(self):
        """Musical symbol U+1D11E in email is invalid."""
        svc = _email_svc()
        email = "test\U0001D11E@mail.ru"
        assert not svc._is_valid_email(email)

    def test_playing_card_in_username(self):
        """Playing card character U+1F0A1 stripped from username."""
        svc = _email_svc()
        result = svc._clean_username("ace\U0001F0A1user")
        assert result == "aceuser"

    def test_gothic_letters_in_name(self):
        """Gothic script letters (U+10330+) in _transliterate."""
        svc = _email_svc()
        result = svc._transliterate("\U00010330\U00010331")
        # Not in map, should pass through without crash
        assert isinstance(result, str)

    def test_source_result_with_emoji_value(self):
        """SourceResult can hold emoji in value without crashing."""
        r = _make_result("\U0001F4E7 test@mail.ru")
        assert r.value == "\U0001F4E7 test@mail.ru"
        d = r.to_dict()
        assert isinstance(d, dict)


# ═══════════════════════════════════════════════════════════════════════════
# 6. Unicode Normalization Forms  (15 tests)
# ═══════════════════════════════════════════════════════════════════════════

class TestUnicodeNormalization:
    """NFC, NFD, NFKC, NFKD effects on transliteration and validation."""

    def test_nfc_nfd_same_cyrillic(self):
        """Most basic Cyrillic chars are identical in NFC and NFD."""
        svc = _email_svc()
        text = "\u0430\u043d\u043d\u0430"  # анна
        nfc = unicodedata.normalize("NFC", text)
        nfd = unicodedata.normalize("NFD", text)
        assert svc._transliterate(nfc) == svc._transliterate(nfd)

    def test_nfc_yo_equals_e(self):
        """NFC ё -> 'e'."""
        svc = _email_svc()
        assert svc._transliterate(unicodedata.normalize("NFC", "\u0451")) == "e"

    def test_nfkc_ligature_fi(self):
        """NFKC decomposes ﬁ (U+FB01) to 'fi'."""
        text = "\uFB01"
        nfkc = unicodedata.normalize("NFKC", text)
        assert nfkc == "fi"

    def test_ligature_fi_in_email_raw(self):
        """Raw ligature ﬁ in email is invalid (not [a-z])."""
        svc = _email_svc()
        email = "\uFB01rst@mail.ru"
        assert not svc._is_valid_email(email)

    def test_ligature_fi_nfkc_in_email(self):
        """After NFKC normalization, 'fi' is valid in email."""
        svc = _email_svc()
        nfkc = unicodedata.normalize("NFKC", "\uFB01rst@mail.ru")
        assert svc._is_valid_email(nfkc)  # "first@mail.ru"

    def test_superscript_digits_in_phone(self):
        """Superscript digits (U+00B2, U+00B3, U+00B9) are stripped by \\D."""
        phone = "+7916\u00B9234567"
        result = normalize_phone(phone)
        # \D strips superscript 1 (U+00B9), digits become shorter
        assert isinstance(result, str)

    def test_nfkc_superscript_to_normal(self):
        """NFKC normalizes superscript digits to normal digits."""
        text = "\u00B9\u00B2\u00B3"
        nfkc = unicodedata.normalize("NFKC", text)
        assert nfkc == "123"

    def test_subscript_digits_in_phone(self):
        """Subscript digits (U+2080-U+2089) stripped by \\D."""
        phone = "+7916\u20801234567"
        result = normalize_phone(phone)
        # subscript 0 stripped
        assert isinstance(result, str)

    def test_nfkd_decomposition_of_angstrom(self):
        """NFKD: \u212B (Angstrom) -> A + combining ring. Not relevant but must not crash."""
        svc = _email_svc()
        result = svc._transliterate("\u212B")
        assert isinstance(result, str)

    def test_nfc_precomposed_vs_decomposed_in_email(self):
        """NFC vs NFD form of accented Latin char in email."""
        svc = _email_svc()
        # e with acute: NFC U+00E9, NFD 'e' + U+0301
        nfc_email = "\u00E9test@mail.ru"
        nfd_email = "e\u0301test@mail.ru"
        # Both invalid (accented char not in [a-z0-9])
        assert not svc._is_valid_email(nfc_email)
        assert not svc._is_valid_email(nfd_email)

    def test_transliterate_nfkc_cyrillic(self):
        """NFKC normalization of Cyrillic should not change basic letters."""
        svc = _email_svc()
        text = "\u0418\u0432\u0430\u043d"  # Иван
        nfkc = unicodedata.normalize("NFKC", text)
        assert svc._transliterate(nfkc) == "ivan"

    def test_transliterate_nfkd_cyrillic(self):
        """NFKD normalization of Cyrillic should not change basic letters."""
        svc = _email_svc()
        text = "\u0418\u0432\u0430\u043d"  # Иван
        nfkd = unicodedata.normalize("NFKD", text)
        assert svc._transliterate(nfkd) == "ivan"

    def test_nfkc_fraction_in_phone(self):
        """NFKC: fraction 1/2 (U+00BD) decomposes to '1' + '/' + '2'."""
        nfkc = unicodedata.normalize("NFKC", "\u00BD")
        # NFKC maps U+00BD to "1\u20442" (1 + fraction slash + 2)
        assert "1" in nfkc
        assert "2" in nfkc

    def test_dedup_nfc_vs_nfd(self):
        """Dedup key uses .lower().strip() -- NFC vs NFD are different bytes."""
        mgr = SourceManager.__new__(SourceManager)
        mgr.sources = []
        nfc_val = unicodedata.normalize("NFC", "\u00E9mail@test.ru")
        nfd_val = unicodedata.normalize("NFD", "\u00E9mail@test.ru")
        r1 = _make_result(nfc_val)
        r2 = _make_result(nfd_val)
        results = mgr._deduplicate([r1, r2])
        # NFC and NFD have different byte representations -> not merged
        assert len(results) == 2

    def test_roman_numeral_in_name(self):
        """Roman numeral II (U+2161) through _transliterate without crash."""
        svc = _email_svc()
        result = svc._transliterate("\u2161")  # Ⅱ
        assert isinstance(result, str)


# ═══════════════════════════════════════════════════════════════════════════
# 7. Edge Unicode Cases  (15+ tests)
# ═══════════════════════════════════════════════════════════════════════════

class TestEdgeUnicodeCases:
    """Empty strings, replacement char, BOM, line/paragraph separators,
    soft hyphen, non-breaking space, null character."""

    def test_empty_string_transliterate(self):
        svc = _email_svc()
        assert svc._transliterate("") == ""

    def test_empty_string_clean_username(self):
        svc = _email_svc()
        assert svc._clean_username("") == ""

    def test_empty_string_is_valid_email(self):
        svc = _email_svc()
        assert not svc._is_valid_email("")

    def test_empty_string_normalize_phone(self):
        assert normalize_phone("") == ""

    def test_none_normalize_phone(self):
        assert normalize_phone(None) == ""

    def test_single_char_transliterate(self):
        svc = _email_svc()
        assert svc._transliterate("a") == "a"
        assert svc._transliterate("\u0430") == "a"  # Cyrillic а

    def test_single_char_email_invalid(self):
        svc = _email_svc()
        assert not svc._is_valid_email("a")

    def test_replacement_char_in_email(self):
        """Replacement character U+FFFD in email is invalid."""
        svc = _email_svc()
        email = "test\uFFFD@mail.ru"
        assert not svc._is_valid_email(email)

    def test_replacement_char_in_phone(self):
        """U+FFFD in phone is stripped by \\D."""
        phone = "+7\uFFFD9161234567"
        result = normalize_phone(phone)
        assert result == "+79161234567"

    def test_bom_at_start_of_email(self):
        """BOM U+FEFF at start of email makes it invalid."""
        svc = _email_svc()
        email = "\uFEFFtest@mail.ru"
        assert not svc._is_valid_email(email)

    def test_bom_at_start_of_phone(self):
        """BOM stripped from phone by \\D."""
        phone = "\uFEFF+79161234567"
        result = normalize_phone(phone)
        assert result == "+79161234567"

    def test_line_separator_in_phone(self):
        """Line separator U+2028 stripped by \\D."""
        phone = "+7916\u20281234567"
        result = normalize_phone(phone)
        assert result == "+79161234567"

    def test_paragraph_separator_in_phone(self):
        """Paragraph separator U+2029 stripped by \\D."""
        phone = "+7916\u20291234567"
        result = normalize_phone(phone)
        assert result == "+79161234567"

    def test_soft_hyphen_in_phone(self):
        """Soft hyphen U+00AD stripped by \\D."""
        phone = "+7916\u00AD1234567"
        result = normalize_phone(phone)
        assert result == "+79161234567"

    def test_nbsp_in_phone(self):
        """Non-breaking space U+00A0 stripped by \\D."""
        phone = "+7\u00A0916\u00A01234567"
        result = normalize_phone(phone)
        assert result == "+79161234567"

    def test_nbsp_in_email(self):
        """Non-breaking space in email is invalid."""
        svc = _email_svc()
        email = "test\u00A0user@mail.ru"
        assert not svc._is_valid_email(email)

    def test_null_char_in_phone(self):
        """Null character U+0000 in phone string -- \\D strips it."""
        phone = "+7916\x001234567"
        result = normalize_phone(phone)
        assert result == "+79161234567"

    def test_null_char_in_email(self):
        """Null character in email is invalid."""
        svc = _email_svc()
        email = "test\x00@mail.ru"
        assert not svc._is_valid_email(email)

    def test_generate_candidates_empty_names(self):
        """_generate_candidates with empty first and last name does not crash."""
        svc = _email_svc()
        result = svc._generate_candidates("", "", [])
        assert isinstance(result, list)

    def test_phone_validate_empty(self):
        """validate_phone with empty string."""
        info = validate_phone("")
        assert not info.is_valid

    def test_extract_from_usernames_unicode(self):
        """_extract_from_usernames with Unicode usernames doesn't crash."""
        svc = _phone_svc()
        result = svc._extract_from_usernames([
            "\U0001F600emoji_user",
            "\u0438\u0432\u0430\u043d",  # иван
            "normal_user123",
        ])
        assert isinstance(result, list)

    def test_normalize_key_empty(self):
        """_normalize_key with empty string."""
        svc = _phone_svc()
        result = svc._normalize_key("")
        assert result == ""

    def test_source_result_empty_value(self):
        """SourceResult with empty value string."""
        r = _make_result("")
        assert r.value == ""
        d = r.to_dict()
        assert d["value"] == ""

    def test_interrobang_in_email(self):
        """Interrobang U+203D in email is invalid."""
        svc = _email_svc()
        email = "test\u203D@mail.ru"
        assert not svc._is_valid_email(email)

    def test_ideographic_space_in_phone(self):
        """Ideographic space U+3000 in phone stripped by \\D."""
        phone = "+7\u3000916\u30001234567"
        result = normalize_phone(phone)
        assert result == "+79161234567"

    def test_object_replacement_char_in_email(self):
        """Object replacement character U+FFFC in email is invalid."""
        svc = _email_svc()
        email = "test\uFFFC@mail.ru"
        assert not svc._is_valid_email(email)
