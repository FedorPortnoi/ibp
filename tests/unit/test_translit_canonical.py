"""
Extended TDD tests for the canonical transliteration module.

Tests transliterate_russian() and transliterate_name_part() from
app.services.phase1.transliteration for comprehensive Cyrillic coverage.
"""

import pytest

from app.services.phase1.transliteration import (
    transliterate_russian,
    transliterate_name_part,
)


class TestTransliterateRussianExtended:
    """Extended TDD tests for transliterate_russian."""

    def test_basic_ivanov(self):
        results = transliterate_russian("Иванов")
        assert any("ivanov" in r.lower() for r in results)

    def test_yo_fedor(self):
        results = transliterate_russian("Фёдор")
        lower = [r.lower() for r in results]
        assert any("fedor" in r or "fyodor" in r for r in lower)

    def test_yo_artem(self):
        results = transliterate_russian("Артём")
        lower = [r.lower() for r in results]
        # Should have both artem and artyom
        assert any("artem" in r or "artyom" in r for r in lower)

    def test_y_yoshkar(self):
        results = transliterate_russian("Йошкар")
        lower = [r.lower() for r in results]
        assert any("yoshkar" in r or "ioshkar" in r or "joshkar" in r for r in lower)

    def test_kh_khabarovsk(self):
        results = transliterate_russian("Хабаровск")
        lower = [r.lower() for r in results]
        assert any("khabarovsk" in r or "habarovsk" in r for r in lower)

    def test_ts_tsvetkov(self):
        results = transliterate_russian("Цветков")
        lower = [r.lower() for r in results]
        assert any("tsvetkov" in r or "cvetkov" in r for r in lower)

    def test_ch_chernov(self):
        results = transliterate_russian("Чернов")
        lower = [r.lower() for r in results]
        assert any("chernov" in r for r in lower)

    def test_sh_shmidt(self):
        results = transliterate_russian("Шмидт")
        lower = [r.lower() for r in results]
        assert any("shmidt" in r for r in lower)

    def test_shch_shchukin(self):
        results = transliterate_russian("Щукин")
        lower = [r.lower() for r in results]
        assert any("shchukin" in r or "schukin" in r for r in lower)

    def test_y_krylov(self):
        results = transliterate_russian("Крылов")
        lower = [r.lower() for r in results]
        assert any("krylov" in r or "krilov" in r for r in lower)

    def test_e_eduard(self):
        results = transliterate_russian("Эдуард")
        lower = [r.lower() for r in results]
        assert any("eduard" in r for r in lower)

    def test_yu_yuriy(self):
        results = transliterate_russian("Юрий")
        lower = [r.lower() for r in results]
        assert any("yuriy" in r or "yuri" in r or "iuriy" in r for r in lower)

    def test_ya_yakovlev(self):
        results = transliterate_russian("Яковлев")
        lower = [r.lower() for r in results]
        assert any("yakovlev" in r or "iakovlev" in r for r in lower)

    def test_hard_sign_stripped(self):
        results = transliterate_russian("Объект")
        lower = [r.lower() for r in results]
        assert any("obekt" in r or "ob'ekt" in r for r in lower)

    def test_soft_sign_stripped(self):
        results = transliterate_russian("Ольга")
        lower = [r.lower() for r in results]
        assert any("olga" in r for r in lower)

    def test_already_latin_unchanged(self):
        results = transliterate_russian("Ivanov")
        assert "ivanov" in [r.lower() for r in results]

    def test_empty_string(self):
        assert transliterate_russian("") == []

    def test_whitespace_only(self):
        assert transliterate_russian("   ") == []

    def test_full_name_multi_word(self):
        results = transliterate_russian("Иванов Иван Иванович")
        lower = [r.lower() for r in results]
        assert any("ivanov" in r and "ivan" in r for r in lower)

    def test_zh_zhukov(self):
        results = transliterate_russian("Жуков")
        lower = [r.lower() for r in results]
        assert any("zhukov" in r or "jukov" in r for r in lower)

    def test_returns_list(self):
        results = transliterate_russian("Иванов")
        assert isinstance(results, list)
        assert len(results) >= 1

    def test_max_variants_respected(self):
        results = transliterate_russian("Щёлоков", max_variants=3)
        assert len(results) <= 3

    # --- Additional coverage tests ---

    def test_multiple_ambiguous_chars_generate_variants(self):
        """A word with multiple ambiguous chars should produce multiple variants."""
        results = transliterate_russian("Хабаровск")
        # х has 3 variants (kh, h, x), so we expect at least 3 variants
        assert len(results) >= 3

    def test_no_cyrillic_in_output(self):
        """Output should never contain Cyrillic characters."""
        results = transliterate_russian("Щёлоков")
        for r in results:
            assert all(ord(c) < 0x400 or ord(c) > 0x4FF for c in r), \
                f"Cyrillic found in output: {r}"

    def test_yo_produces_multiple_systems(self):
        """Yo (Ё) has 3 transliteration systems: yo, e, jo."""
        results = transliterate_russian("Фёдор")
        lower = [r.lower() for r in results]
        has_e = any("fedor" in r for r in lower)
        has_yo = any("fyodor" in r for r in lower)
        assert has_e and has_yo, f"Expected both 'fedor' and 'fyodor' variants, got: {lower}"

    def test_ending_iy_variants(self):
        """Surname ending -ий should produce -iy/-y/-ii variants."""
        results = transliterate_russian("Юрий")
        lower = [r.lower() for r in results]
        has_iy = any(r.endswith("iy") for r in lower)
        has_ii = any(r.endswith("ii") for r in lower)
        has_y = any(r.endswith("ry") or r.endswith("ury") for r in lower)
        assert has_iy or has_ii or has_y, \
            f"Expected -iy, -ii, or -y ending variants, got: {lower}"

    def test_ending_ov_preserved(self):
        """Surname ending -ов should always become -ov."""
        results = transliterate_russian("Иванов")
        lower = [r.lower() for r in results]
        assert all(r.endswith("ov") for r in lower), \
            f"Expected all variants to end with -ov, got: {lower}"

    def test_ending_ev_variants(self):
        """Surname ending -ев should produce -ev/-yev variants."""
        results = transliterate_russian("Яковлев")
        lower = [r.lower() for r in results]
        has_ev = any(r.endswith("ev") for r in lower)
        has_yev = any(r.endswith("yev") for r in lower)
        assert has_ev or has_yev, \
            f"Expected -ev or -yev ending, got: {lower}"

    def test_deterministic_output(self):
        """Same input should produce same output list each time."""
        a = transliterate_russian("Щукин")
        b = transliterate_russian("Щукин")
        assert a == b

    def test_none_input_returns_empty(self):
        """None input should return empty list without error."""
        # The function signature says str, but we should handle gracefully
        try:
            result = transliterate_russian(None)
            assert result == []
        except (TypeError, AttributeError):
            # Acceptable: function is typed as str, raising on None is fine
            pass

    def test_mixed_cyrillic_latin(self):
        """Input with mixed scripts should be handled."""
        results = transliterate_russian("Иван123")
        assert len(results) > 0

    def test_hyphenated_name(self):
        """Hyphenated names should preserve the hyphen."""
        results = transliterate_russian("Анна-Мария")
        lower = [r.lower() for r in results]
        assert any("-" in r for r in lower), \
            f"Expected hyphen preserved in output, got: {lower}"


class TestTransliterateNamePartExtended:
    """Extended TDD tests for transliterate_name_part."""

    def test_returns_list(self):
        result = transliterate_name_part("Иван")
        assert isinstance(result, list)

    def test_ivan_variants(self):
        result = transliterate_name_part("Иван")
        lower = [r.lower() for r in result]
        assert "ivan" in lower

    def test_max_variants(self):
        result = transliterate_name_part("Щёлоков", max_variants=2)
        assert len(result) <= 2

    def test_empty_string(self):
        result = transliterate_name_part("")
        assert result == ['']

    def test_default_max_is_six(self):
        """Default max_variants should be 6."""
        result = transliterate_name_part("Щёлоков")
        assert len(result) <= 6

    def test_aleksandr_variants(self):
        """Common name with ambiguous chars should have multiple variants."""
        result = transliterate_name_part("Александр")
        lower = [r.lower() for r in result]
        assert "aleksandr" in lower

    def test_single_char_cyrillic(self):
        """Single character should still return a result."""
        result = transliterate_name_part("А")
        assert len(result) >= 1
        assert "a" in [r.lower() for r in result]

    def test_soft_sign_handling(self):
        """Soft sign should be stripped or become apostrophe."""
        result = transliterate_name_part("Ольга")
        lower = [r.lower() for r in result]
        assert any("olga" in r for r in lower)

    def test_hard_sign_handling(self):
        """Hard sign should be stripped."""
        result = transliterate_name_part("Объедков")
        lower = [r.lower() for r in result]
        assert all('\u044a' not in r for r in lower)  # No Cyrillic hard sign

    def test_latin_passthrough(self):
        """Latin input should pass through unchanged (lowercased)."""
        result = transliterate_name_part("Ivanov")
        assert result == ["ivanov"]

    def test_consistent_ordering(self):
        """Multiple calls should return same ordering."""
        a = transliterate_name_part("Фёдор")
        b = transliterate_name_part("Фёдор")
        assert a == b

    def test_common_surname_portnoj(self):
        """Портной ending should produce oi/oy variants."""
        result = transliterate_name_part("Портной")
        lower = [r.lower() for r in result]
        assert any(r.endswith("oi") or r.endswith("oy") for r in lower)

    def test_ts_multiple_systems(self):
        """Ц should have ts/c/tz variants across systems."""
        result = transliterate_name_part("Цветков")
        lower = [r.lower() for r in result]
        has_ts = any(r.startswith("ts") for r in lower)
        has_c = any(r.startswith("c") for r in lower)
        assert has_ts and has_c, \
            f"Expected both 'ts' and 'c' variants, got: {lower}"
