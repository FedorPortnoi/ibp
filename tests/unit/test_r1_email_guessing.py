"""
Tests for email candidate generation and guessing logic.
==========================================================
Tests EmailDiscoveryService._generate_candidates(), _transliterate(),
_clean_username(), and _is_valid_email() methods.

110+ tests covering:
  1. Username-based candidate generation
  2. Name-based candidate generation (with Russian transliteration)
  3. Domain coverage
  4. Prioritization and ordering
  5. Edge cases in generation
  6. Combined name + username scenarios
  7. Parametrized transliteration mapping
  8. Email validation
"""

import pytest
from app.services.phase2.email_discovery import (
    EmailDiscoveryService,
    RUSSIAN_EMAIL_DOMAINS,
)


@pytest.fixture
def svc():
    """Create EmailDiscoveryService instance for testing."""
    service = EmailDiscoveryService()
    yield service
    service.close()


@pytest.fixture
def uncapped_svc():
    """Create EmailDiscoveryService with high cap for deterministic tests."""
    service = EmailDiscoveryService(max_candidates=500)
    yield service
    service.close()


# ── Helpers ──────────────────────────────────────────────────────────

ALL_DOMAINS = RUSSIAN_EMAIL_DOMAINS  # 9 domains


def candidates(svc, first="", last="", usernames=None):
    """Shorthand for _generate_candidates."""
    return svc._generate_candidates(first, last, usernames or [])


def emails_set(svc, first="", last="", usernames=None):
    """Return candidates as a set for membership tests."""
    return set(candidates(svc, first, last, usernames))


def locals_set(svc, first="", last="", usernames=None):
    """Return set of local parts (before @) from candidates."""
    return {e.split("@")[0] for e in candidates(svc, first, last, usernames)}


# =====================================================================
# 1. USERNAME-BASED CANDIDATE GENERATION (27 tests)
# =====================================================================
class TestUsernameCandidates:
    """Username-based candidate generation."""

    def test_username_generates_candidates_across_domains(self, svc):
        """Username 'ivanov_ivan' generates emails for all 9 domains."""
        result = emails_set(svc, usernames=["ivanov_ivan"])
        for domain in ALL_DOMAINS:
            assert f"ivanov_ivan@{domain}" in result

    def test_username_with_dots(self, svc):
        """Username 'ivan.ivanov' generates candidates."""
        result = emails_set(svc, usernames=["ivan.ivanov"])
        assert any(e.startswith("ivan.ivanov@") for e in result)

    def test_username_with_underscores(self, svc):
        """Username 'cool_ivan' generates candidates."""
        result = emails_set(svc, usernames=["cool_ivan"])
        assert any(e.startswith("cool_ivan@") for e in result)

    def test_username_with_hyphens_stripped(self, svc):
        """Hyphens are removed by _clean_username (not in [a-z0-9_.])."""
        cleaned = svc._clean_username("ivan-ivanov")
        assert "-" not in cleaned
        assert cleaned == "ivanivanov"

    def test_username_with_numbers(self, svc):
        """Username with numbers preserved."""
        result = emails_set(svc, usernames=["ivan2023"])
        assert any(e.startswith("ivan2023@") for e in result)

    def test_username_is_email_cleaned(self, svc):
        """Username that IS an email gets @ stripped by clean_username."""
        cleaned = svc._clean_username("ivan@mail.ru")
        # @ is removed by regex [^a-z0-9_.]
        assert "@" not in cleaned

    def test_short_username_skipped(self, svc):
        """Username shorter than 3 chars after cleaning is skipped."""
        result = candidates(svc, usernames=["iv"])
        # "iv" is only 2 chars, should not generate username-based candidates
        for email in result:
            local = email.split("@")[0]
            assert local != "iv"

    def test_username_exactly_3_chars(self, svc):
        """Username exactly 3 chars after cleaning is included."""
        result = emails_set(svc, usernames=["abc"])
        assert any(e.startswith("abc@") for e in result)

    def test_long_username_still_generates(self, svc):
        """Long username (50+ chars) still generates candidates."""
        long_user = "a" * 55
        result = emails_set(svc, usernames=[long_user])
        assert any(e.startswith(f"{long_user}@") for e in result)

    def test_cyrillic_username_cleaned_to_empty(self, svc):
        """Cyrillic-only username cleaned to empty (non a-z0-9_. removed)."""
        cleaned = svc._clean_username("иванов")
        assert cleaned == ""

    def test_cyrillic_username_skipped_in_generation(self, svc):
        """Cyrillic username cleaned to empty -> no candidates from it."""
        result_with = candidates(svc, usernames=["иванов"])
        result_without = candidates(svc, usernames=[])
        assert set(result_with) == set(result_without)

    def test_id_prefix_stripped(self, svc):
        """Username 'id12345' -> prefix 'id' stripped -> '12345'."""
        cleaned = svc._clean_username("id12345")
        assert cleaned == "12345"

    def test_user_prefix_stripped(self, svc):
        """Username 'user456' -> prefix 'user' stripped -> '456'."""
        cleaned = svc._clean_username("user456")
        assert cleaned == "456"

    def test_profile_prefix_stripped(self, svc):
        """Username 'profilename' -> prefix 'profile' stripped -> 'name'."""
        cleaned = svc._clean_username("profilename")
        assert cleaned == "name"

    def test_at_prefix_stripped(self, svc):
        """Username '@username' -> prefix '@' stripped -> 'username'."""
        cleaned = svc._clean_username("@username")
        assert cleaned == "username"

    def test_multiple_usernames_all_contribute(self, svc):
        """Multiple usernames all contribute patterns."""
        result = locals_set(svc, usernames=["cool_ivan", "ivan2023"])
        assert "cool_ivan" in result
        assert "ivan2023" in result

    def test_up_to_10_usernames_processed(self, svc):
        """Only first 10 usernames are processed."""
        # Use names that do NOT have known prefixes so they stay intact
        usernames = [f"handle{i:03d}" for i in range(15)]
        result = locals_set(svc, usernames=usernames)
        assert "handle000" in result
        assert "handle009" in result

    def test_11th_username_ignored(self, svc):
        """11th username beyond the limit is ignored."""
        usernames = [f"handle{i:03d}" for i in range(15)]
        result = locals_set(svc, usernames=usernames)
        # The code does usernames[:10], so indices 10-14 are NOT processed
        assert "handle010" not in result
        assert "handle014" not in result

    def test_mixed_valid_invalid_usernames(self, svc):
        """Mix of valid and invalid (short) usernames."""
        result = locals_set(svc, usernames=["ab", "valid_user", "x"])
        assert "valid_user" in result
        # "ab" and "x" too short after cleaning
        assert "ab" not in result
        assert "x" not in result

    def test_username_uppercase_lowered(self, svc):
        """Uppercase usernames are lowercased."""
        cleaned = svc._clean_username("IvanOV")
        assert cleaned == "ivanov"

    def test_username_special_chars_removed(self, svc):
        """Special characters (!#$%^&*) removed from username."""
        cleaned = svc._clean_username("ivan!#$%ov")
        assert all(c in "abcdefghijklmnopqrstuvwxyz0123456789_." for c in cleaned)

    def test_username_with_mixed_prefix_and_content(self, svc):
        """Username 'id_cool_name' -> 'id' prefix stripped -> '_cool_name'."""
        cleaned = svc._clean_username("id_cool_name")
        assert cleaned == "_cool_name"

    def test_username_only_dots(self, svc):
        """Username of only dots cleaned but may be invalid email local part."""
        cleaned = svc._clean_username("...")
        assert cleaned == "..."

    def test_username_digits_only(self, svc):
        """Username of pure digits generates candidates."""
        result = locals_set(svc, usernames=["123456"])
        assert "123456" in result

    def test_username_with_trailing_spaces(self, svc):
        """Username with spaces - spaces removed by clean."""
        cleaned = svc._clean_username("ivan ivanov")
        assert " " not in cleaned

    def test_empty_username_skipped(self, svc):
        """Empty username string produces no candidates from it."""
        result_with = candidates(svc, usernames=[""])
        result_without = candidates(svc, usernames=[])
        assert set(result_with) == set(result_without)

    def test_username_at_stripped_leaves_content(self, svc):
        """Username '@cool_handle' -> 'cool_handle' after @ prefix strip."""
        cleaned = svc._clean_username("@cool_handle")
        assert cleaned == "cool_handle"


# =====================================================================
# 2. NAME-BASED CANDIDATE GENERATION (34 tests)
# =====================================================================
class TestNameCandidates:
    """Name-based candidate generation with Russian transliteration."""

    def test_ivan_ivanov_dot_pattern(self, uncapped_svc):
        """'Ivan' 'Ivanov' -> 'ivan.ivanov@' pattern exists."""
        result = emails_set(uncapped_svc, "Иван", "Иванов")
        assert "ivan.ivanov@mail.ru" in result

    def test_ivan_ivanov_concat_pattern(self, uncapped_svc):
        """'Ivan' 'Ivanov' -> 'ivanivanov@' pattern exists."""
        result = emails_set(uncapped_svc, "Иван", "Иванов")
        assert "ivanivanov@mail.ru" in result

    def test_ivan_ivanov_reverse_dot_pattern(self, uncapped_svc):
        """'Ivan' 'Ivanov' -> 'ivanov.ivan@' pattern exists."""
        result = emails_set(uncapped_svc, "Иван", "Иванов")
        assert "ivanov.ivan@mail.ru" in result

    def test_ivan_ivanov_underscore_pattern(self, uncapped_svc):
        """'Ivan' 'Ivanov' -> 'ivan_ivanov@' pattern exists."""
        result = emails_set(uncapped_svc, "Иван", "Иванов")
        assert "ivan_ivanov@mail.ru" in result

    def test_ivan_ivanov_initial_last_pattern(self, uncapped_svc):
        """'Ivan' 'Ivanov' -> 'iivanov@' pattern (first initial + last)."""
        result = emails_set(uncapped_svc, "Иван", "Иванов")
        assert "iivanov@mail.ru" in result

    def test_ivan_ivanov_first_initial_pattern(self, uncapped_svc):
        """'Ivan' 'Ivanov' -> 'ivani@' pattern (first + last initial)."""
        result = emails_set(uncapped_svc, "Иван", "Иванов")
        assert "ivani@mail.ru" in result

    def test_ivan_ivanov_reverse_concat_pattern(self, uncapped_svc):
        """'Ivan' 'Ivanov' -> 'ivanovivan@' pattern."""
        result = emails_set(uncapped_svc, "Иван", "Иванов")
        assert "ivanovivan@mail.ru" in result

    def test_ivan_ivanov_first_only_pattern(self, uncapped_svc):
        """'Ivan' 'Ivanov' -> 'ivan@' pattern."""
        result = emails_set(uncapped_svc, "Иван", "Иванов")
        assert "ivan@mail.ru" in result

    def test_ivan_ivanov_last_only_pattern(self, uncapped_svc):
        """'Ivan' 'Ivanov' -> 'ivanov@' pattern."""
        result = emails_set(uncapped_svc, "Иван", "Иванов")
        assert "ivanov@mail.ru" in result

    def test_yo_transliteration(self, uncapped_svc):
        """'Fedor' 'Fedorov' (yo letter) -> fedor.fedorov@ pattern."""
        result = emails_set(uncapped_svc, "Фёдор", "Фёдоров")
        assert "fedor.fedorov@mail.ru" in result

    def test_complex_transliteration_shch(self, svc):
        """'Schukina' -> 'schukina' (Shch->sch)."""
        translit = svc._transliterate("Щукина")
        assert translit == "schukina"

    def test_complex_transliteration_yu(self, svc):
        """'Yuliya' -> 'yuliya' (Yu->yu, Ya->ya)."""
        translit = svc._transliterate("Юлия")
        assert translit == "yuliya"

    def test_schukina_yuliya_pattern(self, svc):
        """First='Yuliya', Last='Schukina' -> yuliya.schukina@ pattern present."""
        result = locals_set(svc, "Юлия", "Щукина")
        assert "yuliya.schukina" in result

    def test_short_surname_kim(self, svc):
        """'Aleksey' 'Kim' -> 'aleksey.kim' local part generated."""
        result = locals_set(svc, "Алексей", "Ким")
        assert "aleksey.kim" in result

    def test_hard_sign_stripped(self, svc):
        """Hard sign (Твёрдый знак) is stripped in transliteration."""
        translit = svc._transliterate("Подъёмный")
        assert "ъ" not in translit
        # П->p, о->o, д->d, ъ->'', ё->e, м->m, н->n, ы->y, й->y
        assert translit == "podemnyy"

    def test_soft_sign_stripped(self, svc):
        """Soft sign (Мягкий знак) is stripped in transliteration."""
        translit = svc._transliterate("Ольга")
        assert "ь" not in translit
        assert translit == "olga"

    def test_double_letters(self, svc):
        """'Kirillov' -> 'kirillov' (double l preserved)."""
        translit = svc._transliterate("Кириллов")
        assert translit == "kirillov"

    def test_single_name_no_surname(self, svc):
        """Single first name, empty last name -> generates 'ivan@' etc."""
        result = locals_set(svc, "Иван", "")
        assert "ivan" in result

    def test_empty_first_name(self, svc):
        """Empty first name, last name only -> generates 'ivanov@' etc."""
        result = locals_set(svc, "", "Иванов")
        assert "ivanov" in result

    def test_zh_transliteration(self, svc):
        """Zh transliteration: Ж -> zh."""
        translit = svc._transliterate("Жуков")
        assert translit == "zhukov"

    def test_kh_transliteration(self, svc):
        """Kh transliteration: Х -> kh."""
        translit = svc._transliterate("Хомяков")
        assert translit == "khomyakov"

    def test_ts_transliteration(self, svc):
        """Ts transliteration: Ц -> ts."""
        translit = svc._transliterate("Цветков")
        assert translit == "tsvetkov"

    def test_ch_transliteration(self, svc):
        """Ch transliteration: Ч -> ch."""
        translit = svc._transliterate("Чернов")
        assert translit == "chernov"

    def test_sh_transliteration(self, svc):
        """Sh transliteration: Ш -> sh."""
        translit = svc._transliterate("Шишкин")
        assert translit == "shishkin"

    def test_ya_transliteration(self, svc):
        """Ya transliteration: Я -> ya."""
        translit = svc._transliterate("Яковлев")
        assert translit == "yakovlev"

    def test_e_transliteration(self, svc):
        """E transliteration: Э -> e."""
        translit = svc._transliterate("Эдуард")
        assert translit == "eduard"

    def test_y_for_i_kratkoe(self, svc):
        """Y transliteration: Й -> y."""
        translit = svc._transliterate("Йод")
        assert translit == "yod"

    def test_y_for_yeri(self, svc):
        """Y transliteration: Ы -> y."""
        translit = svc._transliterate("Крыса")
        assert translit == "krysa"

    def test_very_long_name(self, svc):
        """Very long name still generates valid candidates."""
        long_name = "Абвгдежзиклмнопрстуфхцчш"
        result = candidates(svc, long_name, "Иванов")
        assert len(result) > 0
        for email in result:
            assert svc._is_valid_email(email)

    def test_name_with_whitespace(self, svc):
        """Names with extra whitespace are stripped."""
        result1 = emails_set(svc, "  Иван  ", "  Иванов  ")
        result2 = emails_set(svc, "Иван", "Иванов")
        assert result1 == result2

    @pytest.mark.parametrize("first,last,expected_local", [
        ("Александр", "Петров", "aleksandr.petrov"),
        ("Дмитрий", "Козлов", "dmitriy.kozlov"),
        ("Мария", "Соколова", "mariya.sokolova"),
        ("Наталья", "Новикова", "natalya.novikova"),
        ("Сергей", "Морозов", "sergey.morozov"),
    ])
    def test_common_russian_names_dot_pattern(self, svc, first, last, expected_local):
        """Common Russian names generate correct dot-separated local part."""
        result = locals_set(svc, first, last)
        assert expected_local in result

    def test_latin_name_passthrough(self, svc):
        """Latin names pass through transliteration unchanged."""
        translit = svc._transliterate("Ivan")
        assert translit == "ivan"

    def test_mixed_cyrillic_latin(self, svc):
        """Mixed Cyrillic/Latin transliterated correctly."""
        translit = svc._transliterate("Иvanов")
        assert translit == "ivanov"

    def test_single_name_generates_all_patterns(self, uncapped_svc):
        """First name only produces fname@domain for all 9 domains."""
        result = emails_set(uncapped_svc, "Иван", "")
        for domain in ALL_DOMAINS:
            assert f"ivan@{domain}" in result


# =====================================================================
# 3. DOMAIN COVERAGE (15 tests)
# =====================================================================
class TestDomainCoverage:
    """Verify all 9 domains appear in candidates."""

    @pytest.mark.parametrize("domain", ALL_DOMAINS)
    def test_domain_present_for_common_name(self, svc, domain):
        """Each domain appears in candidates for 'Ivan' 'Ivanov'."""
        result = emails_set(svc, "Иван", "Иванов")
        domain_emails = [e for e in result if e.endswith(f"@{domain}")]
        assert len(domain_emails) > 0, f"No candidates for domain {domain}"

    def test_all_9_domains_covered(self, svc):
        """All 9 configured domains appear in candidate set."""
        result = candidates(svc, "Иван", "Иванов")
        domains_found = {e.split("@")[1] for e in result}
        for domain in ALL_DOMAINS:
            assert domain in domains_found

    def test_mail_ru_present(self, svc):
        """mail.ru is in candidates."""
        result = emails_set(svc, "Иван", "Иванов")
        assert any(e.endswith("@mail.ru") for e in result)

    def test_gmail_present(self, svc):
        """gmail.com is in candidates."""
        result = emails_set(svc, "Иван", "Иванов")
        assert any(e.endswith("@gmail.com") for e in result)

    def test_yandex_present(self, svc):
        """yandex.ru is in candidates."""
        result = emails_set(svc, "Иван", "Иванов")
        assert any(e.endswith("@yandex.ru") for e in result)

    def test_candidate_count_does_not_exceed_max(self, svc):
        """Candidate count does not exceed max_candidates (30)."""
        result = candidates(svc, "Иван", "Иванов", ["cool_ivan", "ivan2023"])
        assert len(result) <= svc.max_candidates

    def test_default_max_candidates_is_30(self, svc):
        """Default max_candidates is 30."""
        assert svc.max_candidates == 30

    def test_custom_max_candidates(self):
        """Custom max_candidates is respected."""
        svc = EmailDiscoveryService(max_candidates=10)
        try:
            result = candidates(svc, "Иван", "Иванов", ["cool_ivan", "ivan2023"])
            assert len(result) <= 10
        finally:
            svc.close()

    def test_many_patterns_capped_at_max(self):
        """With many usernames, candidates capped at max_candidates."""
        svc = EmailDiscoveryService(max_candidates=15)
        try:
            usernames = [f"handle{i}" for i in range(10)]
            result = candidates(svc, "Иван", "Иванов", usernames)
            assert len(result) <= 15
        finally:
            svc.close()

    def test_each_local_paired_with_domains_uncapped(self, uncapped_svc):
        """Each valid local part is paired with all 9 domains when uncapped."""
        result = emails_set(uncapped_svc, "Иван", "")
        # 'ivan' pattern should have all 9 domains
        ivan_domains = {e.split("@")[1] for e in result if e.startswith("ivan@")}
        assert ivan_domains == set(ALL_DOMAINS)


# =====================================================================
# 4. PRIORITIZATION AND ORDERING (10 tests)
# =====================================================================
class TestPrioritizationOrdering:
    """Prioritization and ordering of candidates."""

    def test_no_duplicates(self, svc):
        """No duplicate emails in candidate list."""
        result = candidates(svc, "Иван", "Иванов", ["ivan"])
        assert len(result) == len(set(result))

    def test_all_candidates_valid_format(self, svc):
        """All generated candidates are valid email format."""
        result = candidates(svc, "Иван", "Иванов", ["cool_ivan"])
        for email in result:
            assert svc._is_valid_email(email), f"Invalid email: {email}"

    def test_all_candidates_lowercase(self, svc):
        """All candidates are lowercase."""
        result = candidates(svc, "ИВАН", "ИВАНОВ")
        for email in result:
            assert email == email.lower()

    def test_candidates_contain_at_sign(self, svc):
        """All candidates contain exactly one @."""
        result = candidates(svc, "Иван", "Иванов")
        for email in result:
            assert email.count("@") == 1

    def test_candidates_have_valid_domain(self, svc):
        """All candidate domains are from RUSSIAN_EMAIL_DOMAINS."""
        result = candidates(svc, "Иван", "Иванов")
        for email in result:
            domain = email.split("@")[1]
            assert domain in ALL_DOMAINS

    def test_username_patterns_included(self, svc):
        """Username-based patterns are included in candidates."""
        result = locals_set(svc, "Иван", "Иванов", ["unique_handle"])
        assert "unique_handle" in result

    def test_name_patterns_all_present(self, svc):
        """All expected name local parts present for full name."""
        result = locals_set(svc, "Иван", "Иванов")
        expected_locals = [
            "ivan.ivanov", "ivanivanov", "ivanov.ivan",
            "ivan_ivanov", "iivanov", "ivani",
            "ivanovivan", "ivan", "ivanov",
        ]
        for local in expected_locals:
            assert local in result, f"Pattern '{local}' not found in locals"

    def test_returns_list(self, svc):
        """_generate_candidates returns a list."""
        result = candidates(svc, "Иван", "Иванов")
        assert isinstance(result, list)

    def test_all_elements_are_strings(self, svc):
        """All elements in candidates are strings."""
        result = candidates(svc, "Иван", "Иванов")
        for email in result:
            assert isinstance(email, str)

    def test_no_empty_strings(self, svc):
        """No empty strings in candidates."""
        result = candidates(svc, "Иван", "Иванов")
        for email in result:
            assert len(email) > 0


# =====================================================================
# 5. EDGE CASES IN GENERATION (20 tests)
# =====================================================================
class TestEdgeCases:
    """Edge cases in email candidate generation."""

    def test_both_names_empty(self, svc):
        """Both names empty -> zero candidates."""
        result = candidates(svc, "", "")
        assert len(result) == 0

    def test_both_names_empty_with_username(self, svc):
        """Both names empty but username provided -> username candidates only."""
        result = locals_set(svc, "", "", ["validuser"])
        assert "validuser" in result

    def test_name_only_hard_sign(self, svc):
        """Name with only hard sign -> transliterates to empty -> handled."""
        translit = svc._transliterate("Ъ")
        assert translit == ""
        result = candidates(svc, "Ъ", "Ъ")
        assert len(result) == 0

    def test_name_only_soft_sign(self, svc):
        """Name with only soft sign -> transliterates to empty."""
        translit = svc._transliterate("Ь")
        assert translit == ""

    def test_name_with_only_silent_letters(self, svc):
        """Name of only silent letters -> transliterates to empty."""
        translit = svc._transliterate("ЪЬ")
        assert translit == ""

    def test_numbers_in_name_passthrough(self, svc):
        """Numbers in names pass through transliteration."""
        translit = svc._transliterate("Иван123")
        assert translit == "ivan123"

    def test_unicode_non_russian(self, svc):
        """Non-Russian Unicode (Chinese) passes through as-is."""
        translit = svc._transliterate("李明")
        assert translit == "李明"

    def test_unicode_non_russian_candidates(self, svc):
        """Non-Russian Unicode names -> candidates all pass validation."""
        result = candidates(svc, "李明", "王")
        for email in result:
            assert svc._is_valid_email(email)

    def test_single_char_first_name(self, svc):
        """Single char first name transliterates correctly."""
        translit = svc._transliterate("А")
        assert translit == "a"

    def test_single_char_patterns_skipped(self, svc):
        """Patterns shorter than 2 chars are skipped."""
        result = candidates(svc, "А", "Б")
        for email in result:
            local = email.split("@")[0]
            assert len(local) >= 2

    def test_email_max_length_254(self, svc):
        """Emails over 254 chars are invalid."""
        assert not svc._is_valid_email("a" * 250 + "@mail.ru")

    def test_email_valid_format(self, svc):
        """Valid email passes validation."""
        assert svc._is_valid_email("ivan.ivanov@mail.ru")

    def test_email_invalid_starts_with_dot(self, svc):
        """Email starting with dot is invalid."""
        assert not svc._is_valid_email(".ivan@mail.ru")

    def test_email_invalid_no_domain(self, svc):
        """Email without domain is invalid."""
        assert not svc._is_valid_email("ivan@")

    def test_email_invalid_no_local(self, svc):
        """Email without local part is invalid."""
        assert not svc._is_valid_email("@mail.ru")

    def test_email_invalid_special_chars(self, svc):
        """Email with invalid chars fails validation."""
        assert not svc._is_valid_email("iv an@mail.ru")

    def test_email_valid_with_numbers(self, svc):
        """Email with numbers is valid."""
        assert svc._is_valid_email("ivan123@mail.ru")

    def test_email_valid_with_dots_and_underscores(self, svc):
        """Email with dots and underscores in local part is valid."""
        assert svc._is_valid_email("ivan.cool_user@mail.ru")

    def test_transliterate_empty_string(self, svc):
        """Transliterate empty string returns empty string."""
        assert svc._transliterate("") == ""

    def test_clean_username_empty(self, svc):
        """Clean empty username returns empty."""
        assert svc._clean_username("") == ""


# =====================================================================
# 6. COMBINED NAME + USERNAME SCENARIOS (17 tests)
# =====================================================================
class TestCombinedScenarios:
    """Combined name + username scenarios."""

    def test_name_and_username_both_contribute(self, svc):
        """Name patterns AND username patterns both present."""
        result = locals_set(svc, "Иван", "Иванов", ["cool_ivan"])
        assert "ivan.ivanov" in result
        assert "cool_ivan" in result

    def test_name_and_multiple_usernames(self, svc):
        """Name + multiple usernames all contribute."""
        result = locals_set(svc, "Иван", "Иванов", ["cool_ivan", "ivan2023"])
        assert "ivan.ivanov" in result
        assert "cool_ivan" in result
        assert "ivan2023" in result

    def test_username_same_as_transliterated_name_deduped(self, svc):
        """Username same as transliterated name -> no duplicate emails."""
        result = candidates(svc, "Иван", "Иванов", ["ivan"])
        # "ivan" is both a name pattern and a username pattern
        # Since candidates uses a set, no duplicates
        ivan_mails = [e for e in result if e.split("@")[0] == "ivan"]
        # Each ivan@domain should appear at most once
        assert len(ivan_mails) == len(set(ivan_mails))

    def test_username_overlaps_name_pattern(self, svc):
        """Username 'ivan.ivanov' overlaps with name pattern -> deduped."""
        result = candidates(svc, "Иван", "Иванов", ["ivan.ivanov"])
        assert len(result) == len(set(result))

    def test_10_usernames_all_processed(self, uncapped_svc):
        """10 usernames all processed (up to the limit)."""
        usernames = [f"handle{i}" for i in range(10)]
        result = locals_set(uncapped_svc, "Иван", "Иванов", usernames)
        for i in range(10):
            assert f"handle{i}" in result

    def test_combined_still_capped_at_max(self):
        """Combined name + many usernames still capped at max_candidates."""
        svc = EmailDiscoveryService(max_candidates=20)
        try:
            usernames = [f"handle{i}" for i in range(10)]
            result = candidates(svc, "Иван", "Иванов", usernames)
            assert len(result) <= 20
        finally:
            svc.close()

    def test_duplicate_username_entries(self, svc):
        """Duplicate usernames in list -> deduplicated in output."""
        result = candidates(svc, "Иван", "Иванов", ["same_user", "same_user"])
        assert len(result) == len(set(result))

    def test_username_generates_emails_for_all_domains(self, svc):
        """A single username generates email for all 9 domains."""
        result = emails_set(svc, "", "", ["testuser"])
        for domain in ALL_DOMAINS:
            assert f"testuser@{domain}" in result

    def test_no_name_only_usernames(self, svc):
        """Empty names + usernames -> only username-based candidates."""
        result = emails_set(svc, "", "", ["myhandle"])
        assert "myhandle@mail.ru" in result
        for email in result:
            local = email.split("@")[0]
            assert local == "myhandle"

    def test_complex_scenario_full_pipeline(self, svc):
        """Full scenario: name + varied usernames."""
        result = locals_set(
            svc, "Дмитрий", "Козлов",
            ["dimka_koz", "id98765", "dk2023"]
        )
        # Name patterns
        assert "dmitriy.kozlov" in result
        # Username patterns
        assert "dimka_koz" in result
        assert "dk2023" in result
        # id prefix stripped: "id98765" -> "98765" (5 chars, valid)
        assert "98765" in result

    def test_transliteration_combined_with_username(self, svc):
        """Russian name transliterated + Latin username both work."""
        result = locals_set(svc, "Ольга", "Смирнова", ["olga_s"])
        assert "olga.smirnova" in result
        assert "olga_s" in result

    def test_fedor_scenario(self):
        """Test with Fedor name (yo letter) — use high cap to avoid set truncation."""
        svc = EmailDiscoveryService(max_candidates=100)
        result = locals_set(svc, "Фёдор", "Щукин", ["fedor_sch"])
        assert "fedor.schukin" in result
        assert "fedor_sch" in result
        svc.close()

    def test_all_candidates_have_at_and_dot(self, svc):
        """Every candidate in combined scenario has @ and domain dot."""
        result = candidates(svc, "Анна", "Кузнецова", ["anna_k"])
        for email in result:
            assert "@" in email
            domain = email.split("@")[1]
            assert "." in domain

    def test_non_empty_result_for_normal_input(self, svc):
        """Normal input always produces non-empty candidates."""
        result = candidates(svc, "Иван", "Иванов")
        assert len(result) > 0

    def test_min_candidates_for_full_name(self, svc):
        """Full name (first+last) produces at least 20 candidates."""
        result = candidates(svc, "Иван", "Иванов")
        # 9 patterns * 9 domains = 81 theoretical, capped at 30
        assert len(result) >= 20

    def test_uncapped_produces_all_combinations(self, uncapped_svc):
        """Uncapped service produces 9 patterns * 9 domains = 81 candidates."""
        result = candidates(uncapped_svc, "Иван", "Иванов")
        assert len(result) == 81

    def test_full_name_all_9_patterns_present(self, svc):
        """All 9 name patterns appear as local parts for full name input."""
        result = locals_set(svc, "Иван", "Иванов")
        expected = {
            "ivan.ivanov", "ivanivanov", "ivanov.ivan",
            "ivan_ivanov", "iivanov", "ivani",
            "ivanovivan", "ivan", "ivanov",
        }
        assert expected.issubset(result)


# =====================================================================
# 7. PARAMETRIZED TRANSLITERATION TESTS (33 tests)
# =====================================================================
class TestTransliterationParametrized:
    """Parametrized transliteration mapping tests."""

    @pytest.mark.parametrize("cyrillic,expected", [
        ("а", "a"),
        ("б", "b"),
        ("в", "v"),
        ("г", "g"),
        ("д", "d"),
        ("е", "e"),
        ("ё", "e"),
        ("ж", "zh"),
        ("з", "z"),
        ("и", "i"),
        ("й", "y"),
        ("к", "k"),
        ("л", "l"),
        ("м", "m"),
        ("н", "n"),
        ("о", "o"),
        ("п", "p"),
        ("р", "r"),
        ("с", "s"),
        ("т", "t"),
        ("у", "u"),
        ("ф", "f"),
        ("х", "kh"),
        ("ц", "ts"),
        ("ч", "ch"),
        ("ш", "sh"),
        ("щ", "sch"),
        ("ъ", ""),
        ("ы", "y"),
        ("ь", ""),
        ("э", "e"),
        ("ю", "yu"),
        ("я", "ya"),
    ])
    def test_individual_letter_transliteration(self, svc, cyrillic, expected):
        """Each Cyrillic letter maps to correct Latin equivalent."""
        assert svc._transliterate(cyrillic) == expected


# =====================================================================
# 8. ADDITIONAL _is_valid_email TESTS (14 tests)
# =====================================================================
class TestIsValidEmail:
    """Additional email validation tests."""

    @pytest.mark.parametrize("email,expected", [
        ("ivan@mail.ru", True),
        ("ivan.ivanov@gmail.com", True),
        ("i@m.ru", True),
        ("123@mail.ru", True),
        ("ivan_cool@yandex.ru", True),
        ("ivan-test@mail.ru", True),
        ("", False),
        ("@mail.ru", False),
        ("ivan@", False),
        ("ivan@.ru", False),
        ("ivan@@mail.ru", False),
        (".ivan@mail.ru", False),
        ("ivan@mail", False),
        ("ivan ivanov@mail.ru", False),
    ])
    def test_email_validation(self, svc, email, expected):
        """Email validation covers various formats."""
        assert svc._is_valid_email(email) == expected, f"Failed for {email}"
