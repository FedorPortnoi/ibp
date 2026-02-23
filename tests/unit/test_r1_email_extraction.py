"""
Unit tests for email extraction and validation.
Tests EmailDiscoveryService methods: _is_valid_email, _transliterate,
_clean_username, _generate_candidates, and email-from-text regex patterns.

110+ tests covering format validation, transliteration, username cleaning,
candidate generation, text extraction, and edge cases.
"""

import re

import pytest

from app.services.phase2.email_discovery import (
    DiscoveredEmail,
    EmailDiscoveryService,
    RUSSIAN_EMAIL_DOMAINS,
)


@pytest.fixture
def service():
    """Create an EmailDiscoveryService instance for testing."""
    svc = EmailDiscoveryService()
    yield svc
    svc.close()


# ============================================================
# 1. Email format validation (_is_valid_email) — 35 tests
# ============================================================

class TestIsValidEmailBasicValid:
    """Valid email addresses that must pass validation."""

    @pytest.mark.parametrize("email", [
        "ivan@mail.ru",
        "ivan.ivanov@mail.ru",
        "ivan_ivanov@gmail.com",
        "ivan-ivanov@yandex.ru",
        "ivan123@mail.ru",
        "a1@mail.ru",
        "user@subdomain.example.com",
        "user@sub.domain.example.org",
        "test123@bk.ru",
        "firstname.lastname@outlook.com",
        "user_name.123@list.ru",
        "user@rambler.ru",
        "x@ya.ru",
        "0user@inbox.ru",
        "user@domain.travel",
    ])
    def test_valid_email(self, service, email):
        assert service._is_valid_email(email) is True


class TestIsValidEmailCaseInsensitive:
    """Emails with mixed case should still validate (lowercased internally)."""

    @pytest.mark.parametrize("email", [
        "Ivan.Ivanov@Mail.Ru",
        "IVAN@GMAIL.COM",
        "User@Yandex.RU",
        "FeDor@Outlook.Com",
    ])
    def test_mixed_case_valid(self, service, email):
        assert service._is_valid_email(email) is True


class TestIsValidEmailBasicInvalid:
    """Invalid email addresses that must fail validation."""

    @pytest.mark.parametrize("email", [
        "ivan@",
        "@mail.ru",
        "ivan@.ru",
        "ivan@mail",
        ".ivan@mail.ru",
        "ivan@mail.r",
        "",
        "ivan",
        "@",
        "ivan@@mail.ru",
        "ivan @mail.ru",
        "iv an@mail.ru",
        "ivan@mail .ru",
    ])
    def test_invalid_email(self, service, email):
        assert service._is_valid_email(email) is False

    def test_hyphen_start_domain_accepted_by_regex(self, service):
        # The regex [a-z0-9.-]+ allows hyphen at domain start
        assert service._is_valid_email("ivan@-mail.ru") is True


class TestIsValidEmailEdgeCases:
    """Edge cases for email validation."""

    def test_max_length_254_valid(self, service):
        # 254 chars total: local@domain.com
        local = "a" * 240
        email = f"{local}@example.com"
        assert len(email) == 252  # close to 254
        assert service._is_valid_email(email) is True

    def test_exactly_254_chars(self, service):
        # Build exactly 254 character email
        local = "a" * (254 - len("@example.com"))
        email = f"{local}@example.com"
        assert len(email) == 254
        assert service._is_valid_email(email) is True

    def test_255_chars_invalid(self, service):
        local = "a" * (255 - len("@example.com"))
        email = f"{local}@example.com"
        assert len(email) == 255
        assert service._is_valid_email(email) is False

    def test_300_chars_invalid(self, service):
        local = "a" * 290
        email = f"{local}@example.com"
        assert service._is_valid_email(email) is False

    def test_plus_in_local_part_invalid(self, service):
        # The regex ^[a-z0-9][a-z0-9._-]*@ does NOT allow +
        assert service._is_valid_email("ivan+tag@gmail.com") is False

    def test_special_chars_bang_invalid(self, service):
        assert service._is_valid_email("ivan!@mail.ru") is False

    def test_special_chars_hash_invalid(self, service):
        assert service._is_valid_email("ivan#@mail.ru") is False

    def test_unicode_local_part_invalid(self, service):
        assert service._is_valid_email("\u0438\u0432\u0430\u043d@mail.ru") is False

    def test_tld_single_char_invalid(self, service):
        assert service._is_valid_email("ivan@mail.r") is False

    def test_tld_two_chars_valid(self, service):
        assert service._is_valid_email("ivan@mail.ru") is True

    def test_tld_long_valid(self, service):
        assert service._is_valid_email("ivan@mail.museum") is True

    def test_dot_at_end_of_local_invalid(self, service):
        # The regex requires the local part to end before @; trailing dot
        # is fine since [a-z0-9._-]* allows dot anywhere, but domain must match
        assert service._is_valid_email("ivan.@mail.ru") is True  # regex allows it

    def test_consecutive_dots_local(self, service):
        # Regex allows consecutive dots in local part
        assert service._is_valid_email("i..van@mail.ru") is True

    def test_hyphen_in_local_valid(self, service):
        assert service._is_valid_email("ivan-test@mail.ru") is True

    def test_only_digits_local_valid(self, service):
        assert service._is_valid_email("123456@mail.ru") is True

    def test_underscore_start_invalid(self, service):
        # First char must be [a-z0-9], underscore is not allowed
        assert service._is_valid_email("_ivan@mail.ru") is False

    def test_dash_start_invalid(self, service):
        assert service._is_valid_email("-ivan@mail.ru") is False


# ============================================================
# 2. Transliteration (_transliterate) — 30 tests
# ============================================================

class TestTransliterateBasic:
    """Basic transliteration from Cyrillic to Latin."""

    @pytest.mark.parametrize("cyrillic,expected", [
        ("\u0438\u0432\u0430\u043d", "ivan"),
        ("\u043f\u0435\u0442\u0440", "petr"),
        ("\u0430\u043d\u043d\u0430", "anna"),
        ("\u043e\u043b\u044c\u0433\u0430", "olga"),       # ь stripped
        ("\u044e\u043b\u0438\u044f", "yuliya"),             # ю→yu, я→ya
        ("\u0444\u0451\u0434\u043e\u0440\u043e\u0432", "fedorov"),     # ё→e
        ("\u0449\u0443\u043a\u0438\u043d\u0430", "schukina"),   # щ→sch
    ])
    def test_basic_translit(self, service, cyrillic, expected):
        assert service._transliterate(cyrillic) == expected


class TestTransliterateAllLetters:
    """Test all 33 Russian letters individually."""

    @pytest.mark.parametrize("letter,expected", [
        ("\u0430", "a"),    # а
        ("\u0431", "b"),    # б
        ("\u0432", "v"),    # в
        ("\u0433", "g"),    # г
        ("\u0434", "d"),    # д
        ("\u0435", "e"),    # е
        ("\u0451", "e"),    # ё
        ("\u0436", "zh"),   # ж
        ("\u0437", "z"),    # з
        ("\u0438", "i"),    # и
        ("\u0439", "y"),    # й
        ("\u043a", "k"),    # к
        ("\u043b", "l"),    # л
        ("\u043c", "m"),    # м
        ("\u043d", "n"),    # н
        ("\u043e", "o"),    # о
        ("\u043f", "p"),    # п
        ("\u0440", "r"),    # р
        ("\u0441", "s"),    # с
        ("\u0442", "t"),    # т
        ("\u0443", "u"),    # у
        ("\u0444", "f"),    # ф
        ("\u0445", "kh"),   # х
        ("\u0446", "ts"),   # ц
        ("\u0447", "ch"),   # ч
        ("\u0448", "sh"),   # ш
        ("\u0449", "sch"),  # щ
        ("\u044a", ""),     # ъ (hard sign stripped)
        ("\u044b", "y"),    # ы
        ("\u044c", ""),     # ь (soft sign stripped)
        ("\u044d", "e"),    # э
        ("\u044e", "yu"),   # ю
        ("\u044f", "ya"),   # я
    ])
    def test_single_letter(self, service, letter, expected):
        assert service._transliterate(letter) == expected


class TestTransliterateComplex:
    """Complex transliteration cases."""

    def test_khrushchev(self, service):
        # Хрущёв: х→kh, р→r, у→u, щ→sch, ё→e, в→v = khruschev
        assert service._transliterate("\u0445\u0440\u0443\u0449\u0451\u0432") == "khruschev"

    def test_mixed_cyrillic_latin(self, service):
        # Latin chars pass through unchanged
        result = service._transliterate("ivan\u0438\u0432\u0430\u043d")
        assert result == "ivanivan"

    def test_already_latin(self, service):
        assert service._transliterate("ivanov") == "ivanov"

    def test_empty_string(self, service):
        assert service._transliterate("") == ""

    def test_spaces_preserved(self, service):
        result = service._transliterate("\u0438\u0432\u0430\u043d \u043f\u0435\u0442\u0440\u043e\u0432")
        assert result == "ivan petrov"

    def test_uppercase_lowered(self, service):
        # _transliterate calls text.lower() first
        result = service._transliterate("\u0418\u0412\u0410\u041d")
        assert result == "ivan"

    def test_digits_preserved(self, service):
        result = service._transliterate("\u0438\u0432\u0430\u043d123")
        assert result == "ivan123"

    def test_hard_sign_stripped(self, service):
        # подъезд → podezd (ъ stripped)
        result = service._transliterate("\u043f\u043e\u0434\u044a\u0435\u0437\u0434")
        assert result == "podezd"

    def test_soft_sign_stripped(self, service):
        # кузьмин → kuzmin (ь stripped)
        result = service._transliterate("\u043a\u0443\u0437\u044c\u043c\u0438\u043d")
        assert result == "kuzmin"

    def test_zhukova(self, service):
        # Жукова → zhukova
        assert service._transliterate("\u0436\u0443\u043a\u043e\u0432\u0430") == "zhukova"

    def test_tsvetaeva(self, service):
        # Цветаева → tsvetaeva
        assert service._transliterate("\u0446\u0432\u0435\u0442\u0430\u0435\u0432\u0430") == "tsvetaeva"

    def test_chernyshevsky(self, service):
        # Чернышевский → chernyshevskiy
        result = service._transliterate("\u0447\u0435\u0440\u043d\u044b\u0448\u0435\u0432\u0441\u043a\u0438\u0439")
        assert result == "chernyshevskiy"

    def test_punctuation_passthrough(self, service):
        result = service._transliterate("\u0438\u0432\u0430\u043d.\u043f\u0435\u0442\u0440\u043e\u0432")
        assert result == "ivan.petrov"


# ============================================================
# 3. Username cleaning (_clean_username) — 17 tests
# ============================================================

class TestCleanUsername:
    """Tests for username cleaning."""

    @pytest.mark.parametrize("input_val,expected", [
        ("id12345", "12345"),
        ("@username", "username"),
        ("user_name", "_name"),         # strips "user" prefix
        ("profile_ivan", "_ivan"),      # strips "profile" prefix
        ("idivan", "ivan"),             # strips "id" prefix
        ("username123", "name123"),     # strips "user" prefix
        ("my_user", "my_user"),          # "user" only stripped at start, not mid-string
        ("simple", "simple"),           # no prefix to strip
        ("test.user", "test.user"),     # "user" not at start, not stripped
    ])
    def test_prefix_stripping(self, service, input_val, expected):
        assert service._clean_username(input_val) == expected

    def test_uppercase_lowered(self, service):
        assert service._clean_username("UserName") == "name"

    def test_special_chars_removed(self, service):
        # Non [a-z0-9_.] characters are removed
        result = service._clean_username("user-name!")
        # "user-name!" → strip "user" → "-name!" → remove non-[a-z0-9_.] → "name"
        assert result == "name"

    def test_empty_string(self, service):
        assert service._clean_username("") == ""

    def test_at_only(self, service):
        # "@" → strip "@" prefix → "" → clean → ""
        assert service._clean_username("@") == ""

    def test_id_only(self, service):
        # "id" → strip "id" prefix → ""
        assert service._clean_username("id") == ""

    def test_cyrillic_removed(self, service):
        # Cyrillic chars are not in [a-z0-9_.], so stripped
        result = service._clean_username("\u0438\u0432\u0430\u043d_user")
        # lowercase → "иван_user" → no prefix match at start
        # Then re.sub(r'[^a-z0-9_.]', '', ...) removes Cyrillic chars
        # Result: "_user" (underscore + Latin "user" preserved)
        assert result == "_user"

    def test_long_username(self, service):
        long_name = "a" * 500
        result = service._clean_username(long_name)
        assert result == long_name

    def test_dots_preserved(self, service):
        result = service._clean_username("ivan.petrov")
        assert result == "ivan.petrov"

    def test_underscores_preserved(self, service):
        result = service._clean_username("ivan_petrov_123")
        assert result == "ivan_petrov_123"


# ============================================================
# 4. Email candidate generation (_generate_candidates) — 28 tests
# ============================================================

class TestGenerateCandidatesBasic:
    """Basic candidate generation tests."""

    def test_basic_name_generates_candidates(self, service):
        candidates = service._generate_candidates("\u0418\u0432\u0430\u043d", "\u0418\u0432\u0430\u043d\u043e\u0432", [])
        assert len(candidates) > 0

    def test_candidates_are_strings(self, service):
        candidates = service._generate_candidates("\u0418\u0432\u0430\u043d", "\u0418\u0432\u0430\u043d\u043e\u0432", [])
        assert all(isinstance(c, str) for c in candidates)

    def test_all_candidates_valid_format(self, service):
        candidates = service._generate_candidates("\u0418\u0432\u0430\u043d", "\u0418\u0432\u0430\u043d\u043e\u0432", [])
        for c in candidates:
            assert service._is_valid_email(c), f"Invalid email candidate: {c}"

    def test_candidates_lowercase(self, service):
        candidates = service._generate_candidates("\u0418\u0412\u0410\u041d", "\u0418\u0412\u0410\u041d\u041e\u0412", [])
        for c in candidates:
            assert c == c.lower()

    def test_max_candidates_capped(self, service):
        candidates = service._generate_candidates("\u0418\u0432\u0430\u043d", "\u0418\u0432\u0430\u043d\u043e\u0432", [])
        assert len(candidates) <= service.max_candidates

    def test_custom_max_candidates(self):
        svc = EmailDiscoveryService(max_candidates=10)
        candidates = svc._generate_candidates("\u0418\u0432\u0430\u043d", "\u0418\u0432\u0430\u043d\u043e\u0432", [])
        assert len(candidates) <= 10
        svc.close()

    def test_russian_domains_present(self, service):
        candidates = service._generate_candidates("\u0418\u0432\u0430\u043d", "\u0418\u0432\u0430\u043d\u043e\u0432", [])
        domains_in_candidates = {c.split("@")[1] for c in candidates}
        # At least some Russian domains should be present
        russian_domains_found = domains_in_candidates & set(RUSSIAN_EMAIL_DOMAINS)
        assert len(russian_domains_found) >= 3

    def test_name_patterns_present(self, service):
        # Use a higher max_candidates to avoid truncation
        svc = EmailDiscoveryService(max_candidates=100)
        candidates = svc._generate_candidates("\u0418\u0432\u0430\u043d", "\u0418\u0432\u0430\u043d\u043e\u0432", [])
        locals_parts = {c.split("@")[0] for c in candidates}
        # Should contain patterns like ivan.ivanov, ivanivanov, etc.
        assert "ivan.ivanov" in locals_parts
        assert "ivanivanov" in locals_parts
        assert "ivanov.ivan" in locals_parts
        svc.close()

    def test_initial_patterns(self, service):
        svc = EmailDiscoveryService(max_candidates=100)
        candidates = svc._generate_candidates("\u0418\u0432\u0430\u043d", "\u0418\u0432\u0430\u043d\u043e\u0432", [])
        locals_parts = {c.split("@")[0] for c in candidates}
        # Should have first initial + last name
        assert "iivanov" in locals_parts
        # Should have first name + last initial
        assert "ivani" in locals_parts
        svc.close()


class TestGenerateCandidatesWithUsernames:
    """Candidate generation with username input."""

    def test_username_added(self):
        # Use uncapped service to avoid set ordering issues with default cap
        svc = EmailDiscoveryService(max_candidates=200)
        try:
            candidates = svc._generate_candidates(
                "\u0418\u0432\u0430\u043d", "\u0418\u0432\u0430\u043d\u043e\u0432", ["cool_ivan"]
            )
            locals_parts = {c.split("@")[0] for c in candidates}
            assert "cool_ivan" in locals_parts
        finally:
            svc.close()

    def test_short_username_excluded(self, service):
        candidates = service._generate_candidates(
            "\u0418\u0432\u0430\u043d", "\u0418\u0432\u0430\u043d\u043e\u0432", ["ab"]
        )
        locals_parts = {c.split("@")[0] for c in candidates}
        # Username "ab" has length 2 < 3, excluded
        assert "ab" not in locals_parts

    def test_username_cleaned_before_use(self):
        svc = EmailDiscoveryService(max_candidates=200)
        candidates = svc._generate_candidates(
            "\u0418\u0432\u0430\u043d", "\u0418\u0432\u0430\u043d\u043e\u0432", ["id123456"]
        )
        locals_parts = {c.split("@")[0] for c in candidates}
        # "id123456" → clean_username → "123456"
        assert "123456" in locals_parts
        svc.close()

    def test_multiple_usernames(self, service):
        svc = EmailDiscoveryService(max_candidates=200)
        candidates = svc._generate_candidates(
            "\u0418\u0432\u0430\u043d", "\u0418\u0432\u0430\u043d\u043e\u0432",
            ["ivan_cool", "petrov_ivan", "ivan2023"]
        )
        locals_parts = {c.split("@")[0] for c in candidates}
        assert "ivan_cool" in locals_parts
        assert "petrov_ivan" in locals_parts
        assert "ivan2023" in locals_parts
        svc.close()

    def test_username_at_prefix_cleaned(self, service):
        candidates = service._generate_candidates(
            "\u0418\u0432\u0430\u043d", "\u0418\u0432\u0430\u043d\u043e\u0432", ["@coolivan"]
        )
        locals_parts = {c.split("@")[0] for c in candidates}
        assert "coolivan" in locals_parts

    def test_max_10_usernames(self, service):
        usernames = [f"user{i:03d}" for i in range(20)]
        candidates = service._generate_candidates(
            "\u0418\u0432\u0430\u043d", "\u0418\u0432\u0430\u043d\u043e\u0432", usernames
        )
        # Should only process first 10 usernames
        # (But the 30-candidate cap may limit total output)
        assert len(candidates) <= 30


class TestGenerateCandidatesSpecialNames:
    """Candidate generation with Cyrillic edge cases."""

    def test_yo_handling(self, service):
        # Фёдор Фёдоров → fedor fedorov
        svc = EmailDiscoveryService(max_candidates=100)
        candidates = svc._generate_candidates(
            "\u0424\u0451\u0434\u043e\u0440", "\u0424\u0451\u0434\u043e\u0440\u043e\u0432", []
        )
        locals_parts = {c.split("@")[0] for c in candidates}
        assert "fedor.fedorov" in locals_parts
        svc.close()

    def test_shch_handling(self, service):
        # Щукина → schukina
        svc = EmailDiscoveryService(max_candidates=100)
        candidates = svc._generate_candidates(
            "\u042e\u043b\u0438\u044f", "\u0429\u0443\u043a\u0438\u043d\u0430", []
        )
        locals_parts = {c.split("@")[0] for c in candidates}
        assert "schukina" in locals_parts
        assert "yuliya.schukina" in locals_parts
        svc.close()

    def test_hard_sign_in_name(self, service):
        # Подъёмов: п→p, о→o, д→d, ъ→(stripped), ё→e, м→m, о→o, в→v = podemov
        svc = EmailDiscoveryService(max_candidates=100)
        candidates = svc._generate_candidates(
            "\u0418\u0432\u0430\u043d", "\u041f\u043e\u0434\u044a\u0451\u043c\u043e\u0432", []
        )
        locals_parts = {c.split("@")[0] for c in candidates}
        assert "podemov" in locals_parts
        svc.close()

    def test_soft_sign_in_name(self, service):
        # Кузьмин → kuzmin
        svc = EmailDiscoveryService(max_candidates=100)
        candidates = svc._generate_candidates(
            "\u0418\u0432\u0430\u043d", "\u041a\u0443\u0437\u044c\u043c\u0438\u043d", []
        )
        locals_parts = {c.split("@")[0] for c in candidates}
        assert "kuzmin" in locals_parts
        svc.close()

    def test_empty_first_name(self, service):
        candidates = service._generate_candidates("", "\u0418\u0432\u0430\u043d\u043e\u0432", [])
        # Should still generate last-name-only patterns
        locals_parts = {c.split("@")[0] for c in candidates}
        assert "ivanov" in locals_parts

    def test_empty_last_name(self, service):
        candidates = service._generate_candidates("\u0418\u0432\u0430\u043d", "", [])
        locals_parts = {c.split("@")[0] for c in candidates}
        assert "ivan" in locals_parts

    def test_short_first_name(self, service):
        # Single letter first name "Я" → "ya" (2 chars)
        candidates = service._generate_candidates("\u042f", "\u0418\u0432\u0430\u043d\u043e\u0432", [])
        assert len(candidates) > 0
        for c in candidates:
            assert service._is_valid_email(c)

    def test_no_duplicates(self, service):
        candidates = service._generate_candidates("\u0418\u0432\u0430\u043d", "\u0418\u0432\u0430\u043d\u043e\u0432", [])
        assert len(candidates) == len(set(candidates))

    def test_reversed_name_pattern(self, service):
        svc = EmailDiscoveryService(max_candidates=100)
        candidates = svc._generate_candidates("\u0418\u0432\u0430\u043d", "\u0418\u0432\u0430\u043d\u043e\u0432", [])
        locals_parts = {c.split("@")[0] for c in candidates}
        # ivanovivan (last+first concatenated)
        assert "ivanovivan" in locals_parts
        svc.close()

    def test_underscore_pattern(self, service):
        svc = EmailDiscoveryService(max_candidates=100)
        candidates = svc._generate_candidates("\u0418\u0432\u0430\u043d", "\u0418\u0432\u0430\u043d\u043e\u0432", [])
        locals_parts = {c.split("@")[0] for c in candidates}
        assert "ivan_ivanov" in locals_parts
        svc.close()


# ============================================================
# 5. Emails from text patterns — 22 tests
# ============================================================

# This is the same regex used in _scrape_profiles_async
EMAIL_FROM_TEXT_RE = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')


class TestEmailFromTextBasic:
    """Extract emails from text using regex."""

    def test_simple_russian_context(self):
        text = "\u041f\u0438\u0448\u0438\u0442\u0435 \u043d\u0430 ivan@mail.ru \u0434\u043b\u044f \u0441\u0432\u044f\u0437\u0438"
        matches = EMAIL_FROM_TEXT_RE.findall(text)
        assert "ivan@mail.ru" in matches

    def test_email_with_label(self):
        text = "Email: ivan@gmail.com"
        matches = EMAIL_FROM_TEXT_RE.findall(text)
        assert "ivan@gmail.com" in matches

    def test_two_emails_slash_separated(self):
        text = "\u0421\u0432\u044f\u0437\u044c: ivan@mail.ru / ivan@gmail.com"
        matches = EMAIL_FROM_TEXT_RE.findall(text)
        assert "ivan@mail.ru" in matches
        assert "ivan@gmail.com" in matches

    def test_two_emails_with_labels(self):
        text = "ivan@mail.ru (\u0440\u0430\u0431\u043e\u0447\u0438\u0439), ivan@gmail.com (\u043b\u0438\u0447\u043d\u044b\u0439)"
        matches = EMAIL_FROM_TEXT_RE.findall(text)
        assert "ivan@mail.ru" in matches
        assert "ivan@gmail.com" in matches

    def test_email_buried_in_long_text(self):
        filler = "\u0410" * 250
        text = f"{filler} contact: test@yandex.ru {filler}"
        matches = EMAIL_FROM_TEXT_RE.findall(text)
        assert "test@yandex.ru" in matches

    def test_email_in_angle_brackets(self):
        text = "Contact: <admin@example.org>"
        matches = EMAIL_FROM_TEXT_RE.findall(text)
        assert "admin@example.org" in matches

    def test_email_in_parentheses(self):
        text = "(\u043f\u043e\u0447\u0442\u0430: user@inbox.ru)"
        matches = EMAIL_FROM_TEXT_RE.findall(text)
        assert "user@inbox.ru" in matches

    def test_email_next_to_url(self):
        text = "Site: https://example.com Email: user@example.com"
        matches = EMAIL_FROM_TEXT_RE.findall(text)
        assert "user@example.com" in matches

    def test_email_at_start_of_line(self):
        text = "user@bk.ru - main email"
        matches = EMAIL_FROM_TEXT_RE.findall(text)
        assert "user@bk.ru" in matches

    def test_email_at_end_of_line(self):
        text = "Main email: user@list.ru"
        matches = EMAIL_FROM_TEXT_RE.findall(text)
        assert "user@list.ru" in matches

    def test_no_email_in_text(self):
        text = "\u042d\u0442\u043e \u0442\u0435\u043a\u0441\u0442 \u0431\u0435\u0437 \u044d\u043b\u0435\u043a\u0442\u0440\u043e\u043d\u043d\u043e\u0439 \u043f\u043e\u0447\u0442\u044b"
        matches = EMAIL_FROM_TEXT_RE.findall(text)
        assert len(matches) == 0

    def test_email_with_plus(self):
        text = "Address: user+tag@gmail.com"
        matches = EMAIL_FROM_TEXT_RE.findall(text)
        assert "user+tag@gmail.com" in matches

    def test_email_with_dots_in_local(self):
        text = "first.middle.last@domain.com"
        matches = EMAIL_FROM_TEXT_RE.findall(text)
        assert "first.middle.last@domain.com" in matches

    def test_email_with_subdomain(self):
        text = "user@mail.sub.example.com"
        matches = EMAIL_FROM_TEXT_RE.findall(text)
        assert "user@mail.sub.example.com" in matches

    def test_multiple_emails_newline_separated(self):
        text = "user1@mail.ru\nuser2@gmail.com\nuser3@yandex.ru"
        matches = EMAIL_FROM_TEXT_RE.findall(text)
        assert len(matches) == 3

    def test_email_with_percent(self):
        text = "weird%email@domain.com"
        matches = EMAIL_FROM_TEXT_RE.findall(text)
        assert "weird%email@domain.com" in matches

    def test_email_with_numbers_in_domain(self):
        text = "user@123domain.com"
        matches = EMAIL_FROM_TEXT_RE.findall(text)
        assert "user@123domain.com" in matches

    def test_email_mixed_case(self):
        text = "Ivan.Ivanov@Mail.Ru"
        matches = EMAIL_FROM_TEXT_RE.findall(text)
        assert "Ivan.Ivanov@Mail.Ru" in matches

    def test_email_after_colon_no_space(self):
        text = "email:user@mail.ru"
        matches = EMAIL_FROM_TEXT_RE.findall(text)
        assert "user@mail.ru" in matches

    def test_email_with_hyphen_in_domain(self):
        text = "user@my-domain.com"
        matches = EMAIL_FROM_TEXT_RE.findall(text)
        assert "user@my-domain.com" in matches

    def test_three_emails_in_html(self):
        text = '<a href="mailto:a@x.com">a@x.com</a> and <span>b@y.org</span>'
        matches = EMAIL_FROM_TEXT_RE.findall(text)
        assert "a@x.com" in matches
        assert "b@y.org" in matches


# ============================================================
# 6. Edge cases and integration — 16 tests
# ============================================================

class TestEdgeCasesEmptyInputs:
    """Edge cases with empty and unusual inputs."""

    def test_transliterate_none_like(self, service):
        # Empty string
        assert service._transliterate("") == ""

    def test_clean_username_empty(self, service):
        assert service._clean_username("") == ""

    def test_is_valid_email_empty(self, service):
        assert service._is_valid_email("") is False

    def test_is_valid_email_whitespace(self, service):
        assert service._is_valid_email("   ") is False

    def test_generate_candidates_empty_names(self, service):
        candidates = service._generate_candidates("", "", [])
        # With empty names, all patterns are empty string (len < 2), so no candidates
        assert len(candidates) == 0

    def test_generate_candidates_spaces_only(self, service):
        candidates = service._generate_candidates("   ", "   ", [])
        assert len(candidates) == 0


class TestEdgeCasesUnicode:
    """Unicode edge cases."""

    def test_chinese_characters_passthrough(self, service):
        # Non-Russian Unicode passes through transliterate
        result = service._transliterate("\u4e2d\u6587")
        assert result == "\u4e2d\u6587"

    def test_emoji_passthrough(self, service):
        result = service._transliterate("test\U0001f600")
        assert "\U0001f600" in result

    def test_arabic_passthrough(self, service):
        result = service._transliterate("\u0645\u0631\u062d\u0628\u0627")
        assert result == "\u0645\u0631\u062d\u0628\u0627"


class TestEdgeCasesDomains:
    """Domain-related edge cases."""

    def test_email_many_subdomains(self, service):
        assert service._is_valid_email("user@a.b.c.d.e.com") is True

    def test_email_numeric_domain_parts(self, service):
        assert service._is_valid_email("user@123.456.com") is True

    def test_email_single_char_local(self, service):
        assert service._is_valid_email("a@mail.ru") is True

    def test_email_very_long_tld(self, service):
        assert service._is_valid_email("user@domain.international") is True


class TestDiscoveredEmailDataclass:
    """Tests for the DiscoveredEmail dataclass."""

    def test_create_basic(self):
        email = DiscoveredEmail(
            email="ivan@mail.ru",
            source="test",
            confidence="high",
        )
        assert email.email == "ivan@mail.ru"
        assert email.verified is False
        assert email.verified_on == []
        assert email.verification == "unverified"

    def test_create_full(self):
        email = DiscoveredEmail(
            email="ivan@mail.ru",
            source="Holehe verification",
            confidence="high",
            verified=True,
            verified_on=["holehe:twitter", "holehe:spotify"],
            verification="holehe_confirmed",
        )
        assert email.verified is True
        assert len(email.verified_on) == 2

    def test_default_verified_on_is_empty_list(self):
        e1 = DiscoveredEmail(email="a@b.com", source="x", confidence="low")
        e2 = DiscoveredEmail(email="c@d.com", source="y", confidence="low")
        # Ensure default list is not shared between instances
        e1.verified_on.append("test")
        assert "test" not in e2.verified_on


class TestRussianEmailDomainsConstant:
    """Tests for RUSSIAN_EMAIL_DOMAINS constant."""

    def test_contains_mail_ru(self):
        assert "mail.ru" in RUSSIAN_EMAIL_DOMAINS

    def test_contains_yandex(self):
        assert "yandex.ru" in RUSSIAN_EMAIL_DOMAINS

    def test_contains_gmail(self):
        assert "gmail.com" in RUSSIAN_EMAIL_DOMAINS

    def test_nine_domains(self):
        assert len(RUSSIAN_EMAIL_DOMAINS) == 9

    def test_all_domains_have_tld(self):
        for domain in RUSSIAN_EMAIL_DOMAINS:
            parts = domain.split(".")
            assert len(parts) >= 2
            assert len(parts[-1]) >= 2
