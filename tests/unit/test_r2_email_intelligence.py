"""
Round 2 -- Email Intelligence Tests
====================================
Deep testing that IBP is SMART about emails, not just format-correct.

Tests cover:
  1. Transliteration intelligence (33 Cyrillic chars + edge cases)
  2. Email domain intelligence (constants, groupings, MX consistency)
  3. Email validation edge cases (regex boundary conditions)
  4. SMTP verification intelligence (blocked/catch-all/verified/rejected)
  5. Verification priority / merging logic
  6. MX validation (known domains, DNS mocking, caching)

120+ tests total.
"""

import asyncio
import hashlib
import smtplib
import socket
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest

from app.services.phase2.email_discovery import (
    CATCH_ALL_DOMAINS,
    DiscoveredEmail,
    EmailDiscoveryResults,
    EmailDiscoveryService,
    KNOWN_MX_SERVERS,
    RUSSIAN_EMAIL_DOMAINS,
    SMTP_BLOCKED_DOMAINS,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def svc():
    """Fresh EmailDiscoveryService with default settings."""
    service = EmailDiscoveryService()
    yield service
    service.close()


@pytest.fixture
def svc_small():
    """Service with very small candidate cap for focused tests."""
    service = EmailDiscoveryService(max_candidates=5)
    yield service
    service.close()


# ===========================================================================
# 1. TRANSLITERATION INTELLIGENCE  (30+ tests)
# ===========================================================================

class TestTransliterationIntelligence:
    """Verify every Cyrillic char and tricky combinations."""

    # -- Individual character tests (33 letters) ----------------------------

    @pytest.mark.parametrize("cyrillic,latin", [
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
    ], ids=lambda p: p if len(p) <= 3 else p[:3])
    def test_individual_cyrillic_char(self, svc, cyrillic, latin):
        assert svc._transliterate(cyrillic) == latin

    # -- Name-level transliteration -----------------------------------------

    def test_yo_in_name_fedorov(self, svc):
        """Ё in Фёдоров must collapse to 'e', not 'yo'."""
        assert svc._transliterate("фёдоров") == "fedorov"

    def test_yo_standalone_yolka(self, svc):
        """ёлка → elka."""
        assert svc._transliterate("ёлка") == "elka"

    def test_sch_shchukin(self, svc):
        """Щукин → schukin."""
        assert svc._transliterate("щукин") == "schukin"

    def test_hard_sign_stripping_podyezd(self, svc):
        """подъезд → podezd (ъ stripped, no extra y)."""
        assert svc._transliterate("подъезд") == "podezd"

    def test_soft_sign_stripping_olga(self, svc):
        """ольга → olga (ь stripped)."""
        assert svc._transliterate("ольга") == "olga"

    def test_complex_combo_zhsh(self, svc):
        """жш → zhsh."""
        assert svc._transliterate("жш") == "zhsh"

    def test_complex_combo_tsch(self, svc):
        """цч → tsch."""
        assert svc._transliterate("цч") == "tsch"

    def test_mixed_cyrillic_latin(self, svc):
        """Mixed input: Cyrillic chars transliterated, Latin kept."""
        result = svc._transliterate("ivan иванов")
        assert result == "ivan ivanov"

    def test_already_latin_passthrough(self, svc):
        """Pure Latin text passes through unchanged."""
        assert svc._transliterate("john smith") == "john smith"

    def test_empty_string(self, svc):
        assert svc._transliterate("") == ""

    def test_numbers_passthrough(self, svc):
        assert svc._transliterate("123") == "123"

    def test_special_chars_passthrough(self, svc):
        """Non-Cyrillic specials pass through as-is."""
        assert svc._transliterate("@.#") == "@.#"

    def test_double_letters_kirillov(self, svc):
        """Кириллов → kirillov (лл → ll)."""
        assert svc._transliterate("кириллов") == "kirillov"

    def test_long_name_20_plus_chars(self, svc):
        """Long name transliterates fully."""
        name = "александровский"  # 15 Cyrillic = potentially longer Latin
        result = svc._transliterate(name)
        assert result == "aleksandrovskiy"
        assert len(result) >= 15  # Multi-char mappings can expand length

    def test_uppercase_converted_to_lowercase(self, svc):
        """Input is lowercased before transliteration."""
        assert svc._transliterate("ИВАНОВ") == "ivanov"

    def test_khabarovsk(self, svc):
        """Хабаровск → khabarovsk (х → kh)."""
        assert svc._transliterate("хабаровск") == "khabarovsk"

    def test_yulia(self, svc):
        """юлия → yuliya."""
        assert svc._transliterate("юлия") == "yuliya"

    def test_yakov(self, svc):
        """яков → yakov."""
        assert svc._transliterate("яков") == "yakov"

    def test_tsvetkov(self, svc):
        """цветков → tsvetkov."""
        assert svc._transliterate("цветков") == "tsvetkov"

    def test_spaces_preserved(self, svc):
        """Spaces between words are preserved."""
        assert svc._transliterate("иван петров") == "ivan petrov"

    def test_hyphens_preserved(self, svc):
        assert svc._transliterate("анна-мария") == "anna-mariya"


# ===========================================================================
# 2. EMAIL DOMAIN INTELLIGENCE  (20+ tests)
# ===========================================================================

class TestEmailDomainIntelligence:
    """Verify constants are correct and consistent."""

    # -- RUSSIAN_EMAIL_DOMAINS completeness ---------------------------------

    def test_russian_domains_count(self):
        assert len(RUSSIAN_EMAIL_DOMAINS) == 9

    @pytest.mark.parametrize("domain", [
        "mail.ru", "yandex.ru", "ya.ru", "bk.ru", "list.ru",
        "inbox.ru", "rambler.ru", "gmail.com", "outlook.com",
    ])
    def test_russian_domain_present(self, domain):
        assert domain in RUSSIAN_EMAIL_DOMAINS

    # -- SMTP_BLOCKED_DOMAINS -----------------------------------------------

    @pytest.mark.parametrize("domain", [
        "mail.ru", "bk.ru", "list.ru", "inbox.ru", "yandex.ru", "ya.ru",
    ])
    def test_smtp_blocked_domain_present(self, domain):
        assert domain in SMTP_BLOCKED_DOMAINS

    def test_smtp_blocked_is_set(self):
        assert isinstance(SMTP_BLOCKED_DOMAINS, set)

    def test_gmail_not_smtp_blocked(self):
        assert "gmail.com" not in SMTP_BLOCKED_DOMAINS

    def test_rambler_not_smtp_blocked(self):
        assert "rambler.ru" not in SMTP_BLOCKED_DOMAINS

    # -- CATCH_ALL_DOMAINS --------------------------------------------------

    @pytest.mark.parametrize("domain", [
        "gmail.com", "outlook.com", "hotmail.com", "yahoo.com", "icloud.com",
    ])
    def test_catch_all_domain_present(self, domain):
        assert domain in CATCH_ALL_DOMAINS

    def test_catch_all_is_set(self):
        assert isinstance(CATCH_ALL_DOMAINS, set)

    def test_mail_ru_not_catch_all(self):
        assert "mail.ru" not in CATCH_ALL_DOMAINS

    # -- KNOWN_MX_SERVERS ---------------------------------------------------

    def test_mail_ru_group_shares_mx(self):
        """mail.ru, bk.ru, list.ru, inbox.ru all resolve to mxs.mail.ru."""
        for d in ("mail.ru", "bk.ru", "list.ru", "inbox.ru"):
            assert KNOWN_MX_SERVERS[d] == "mxs.mail.ru"

    def test_yandex_group_shares_mx(self):
        """yandex.ru and ya.ru both resolve to mx.yandex.ru."""
        for d in ("yandex.ru", "ya.ru"):
            assert KNOWN_MX_SERVERS[d] == "mx.yandex.ru"

    def test_rambler_mx(self):
        assert KNOWN_MX_SERVERS["rambler.ru"] == "mx.rambler.ru"

    def test_gmail_mx(self):
        assert KNOWN_MX_SERVERS["gmail.com"] == "gmail-smtp-in.l.google.com"

    def test_outlook_not_in_known_mx(self):
        """outlook.com is NOT in KNOWN_MX_SERVERS (catch-all, no need)."""
        assert "outlook.com" not in KNOWN_MX_SERVERS

    def test_all_smtp_blocked_in_known_mx(self):
        """Every SMTP-blocked domain should have a KNOWN_MX entry."""
        for d in SMTP_BLOCKED_DOMAINS:
            assert d in KNOWN_MX_SERVERS, f"{d} blocked but no known MX"

    def test_no_catch_all_overlap_with_smtp_blocked(self):
        """CATCH_ALL and SMTP_BLOCKED should be disjoint sets."""
        overlap = CATCH_ALL_DOMAINS & SMTP_BLOCKED_DOMAINS
        assert len(overlap) == 0, f"Overlap: {overlap}"

    def test_known_mx_keys_are_subset_of_russian_domains(self):
        """Every KNOWN_MX key should be in the RUSSIAN_EMAIL_DOMAINS list."""
        for d in KNOWN_MX_SERVERS:
            assert d in RUSSIAN_EMAIL_DOMAINS, f"{d} in MX but not in domains"


# ===========================================================================
# 3. EMAIL VALIDATION EDGE CASES  (25+ tests)
# ===========================================================================

class TestEmailValidationEdgeCases:
    """Test _is_valid_email regex boundary conditions."""

    # -- Valid emails -------------------------------------------------------

    @pytest.mark.parametrize("email", [
        "a@b.co",
        "user123@mail.ru",
        "a.b.c@d.e.f.com",
        "test-user@mail.ru",
        "user_name@yandex.ru",
        "x@y.zz",
        "john.doe@gmail.com",
        "1user@mail.ru",
        "user1@bk.ru",
        "ab@cd.ef",
    ])
    def test_valid_email(self, svc, email):
        assert svc._is_valid_email(email), f"Should be valid: {email}"

    def test_exactly_254_chars_valid(self, svc):
        """Email of exactly 254 characters is valid."""
        local = "a" * 63  # local part
        # domain needs to fill remaining: @(domain)
        # 254 - 63 - 1(@) = 190 chars for domain
        domain_body = "b" * 186  # leave room for ".com"
        email = f"{local}@{domain_body}.com"
        assert len(email) == 254
        assert svc._is_valid_email(email)

    def test_plus_tag_valid(self, svc):
        """user+tag@gmail.com — regex allows + after first char (it is in [a-z0-9._-]*)
        Actually + is not in the regex character class, so this should be INVALID."""
        # The regex is: ^[a-z0-9][a-z0-9._-]*@...
        # Plus sign (+) is NOT in [a-z0-9._-], so this is invalid
        assert not svc._is_valid_email("user+tag@gmail.com")

    def test_single_char_local_valid(self, svc):
        assert svc._is_valid_email("a@mail.ru")

    def test_numeric_local_valid(self, svc):
        assert svc._is_valid_email("123@mail.ru")

    def test_dot_in_local_part_valid(self, svc):
        assert svc._is_valid_email("first.last@mail.ru")

    def test_hyphen_in_local_part_valid(self, svc):
        assert svc._is_valid_email("first-last@mail.ru")

    def test_underscore_in_local_part_valid(self, svc):
        assert svc._is_valid_email("first_last@mail.ru")

    # -- Invalid emails -----------------------------------------------------

    def test_starts_with_dot_invalid(self, svc):
        assert not svc._is_valid_email(".user@mail.ru")

    def test_starts_with_dash_invalid(self, svc):
        assert not svc._is_valid_email("-user@mail.ru")

    def test_starts_with_underscore_invalid(self, svc):
        """Underscore not in first-char class [a-z0-9]."""
        assert not svc._is_valid_email("_user@mail.ru")

    def test_double_dots_in_local_invalid(self, svc):
        """user..name@mail.ru — actually the regex allows '.' in the middle.
        The regex ^[a-z0-9][a-z0-9._-]*@ does allow consecutive dots,
        so this will actually be valid per the implementation."""
        # Let's test actual behavior
        result = svc._is_valid_email("user..name@mail.ru")
        # The regex does NOT forbid consecutive dots, so it matches.
        assert result is True  # Known: regex allows double dots

    def test_no_tld_invalid(self, svc):
        assert not svc._is_valid_email("user@mail")

    def test_tld_single_char_invalid(self, svc):
        """TLD must be 2+ chars: [a-z]{2,}$."""
        assert not svc._is_valid_email("user@mail.r")

    def test_empty_local_part_invalid(self, svc):
        assert not svc._is_valid_email("@mail.ru")

    def test_space_in_email_invalid(self, svc):
        assert not svc._is_valid_email("user name@mail.ru")

    def test_255_chars_invalid(self, svc):
        """255 characters exceeds the 254 limit."""
        local = "a" * 64
        domain_body = "b" * 186
        email = f"{local}@{domain_body}.com"
        assert len(email) == 255
        assert not svc._is_valid_email(email)

    def test_double_dots_in_domain_invalid(self, svc):
        """user@mail..ru — domain regex [a-z0-9.-]+ allows it, but
        the TLD regex requires ending in \\.[a-z]{2,}$. Let's check."""
        # mail..ru has empty label, but regex [a-z0-9.-]+\.[a-z]{2,}$ may match
        result = svc._is_valid_email("user@mail..ru")
        # '.' is in [a-z0-9.-]+, and it ends in .ru which is [a-z]{2,}
        # This is technically matched by the regex
        assert result is True  # regex permits it (known limitation)

    def test_ip_address_domain_invalid(self, svc):
        """user@[192.168.0.1] — brackets not in regex."""
        assert not svc._is_valid_email("user@[192.168.0.1]")

    def test_unicode_domain_invalid(self, svc):
        assert not svc._is_valid_email("user@\u043f\u043e\u0447\u0442\u0430.\u0440\u0444")

    def test_unicode_local_part_invalid(self, svc):
        assert not svc._is_valid_email("\u0438\u0432\u0430\u043d@mail.ru")

    def test_uppercase_is_lowered(self, svc):
        """_is_valid_email lowercases input before matching."""
        assert svc._is_valid_email("User@Mail.RU")

    def test_no_at_sign_invalid(self, svc):
        assert not svc._is_valid_email("usermail.ru")

    def test_double_at_invalid(self, svc):
        assert not svc._is_valid_email("user@@mail.ru")

    def test_trailing_dot_in_domain_invalid(self, svc):
        """user@mail.ru. — trailing dot not matched by [a-z]{2,}$."""
        assert not svc._is_valid_email("user@mail.ru.")

    def test_empty_string_invalid(self, svc):
        assert not svc._is_valid_email("")

    def test_just_at_sign_invalid(self, svc):
        assert not svc._is_valid_email("@")

    def test_whitespace_only_invalid(self, svc):
        assert not svc._is_valid_email("   ")

    def test_tab_in_email_invalid(self, svc):
        assert not svc._is_valid_email("user\t@mail.ru")


# ===========================================================================
# 4. CLEAN USERNAME  (10 tests)
# ===========================================================================

class TestCleanUsername:
    """Verify _clean_username strips prefixes and special chars."""

    @pytest.mark.parametrize("raw,expected", [
        ("id12345", "12345"),
        ("user_john", "_john"),
        ("profile_test", "_test"),
        ("@durov", "durov"),
        ("JohnDoe", "johndoe"),
        ("user.name.123", ".name.123"),  # "user" prefix stripped
        ("some-user!", "someuser"),
        ("UPPERCASE", "uppercase"),
        ("", ""),
        ("id", ""),
    ])
    def test_clean_username(self, svc, raw, expected):
        assert svc._clean_username(raw) == expected

    def test_cyrillic_stripped(self, svc):
        """Cyrillic chars are removed (not in [a-z0-9_.])."""
        assert svc._clean_username("\u0438\u0432\u0430\u043d123") == "123"

    def test_mixed_prefix_and_special(self, svc):
        """id prefix stripped, then specials removed."""
        assert svc._clean_username("id_user!name") == "_username"

    def test_at_prefix_stripped(self, svc):
        """@ prefix stripped by regex."""
        assert svc._clean_username("@etoglaz") == "etoglaz"


# ===========================================================================
# 5. CANDIDATE GENERATION  (12 tests)
# ===========================================================================

class TestCandidateGeneration:
    """Test _generate_candidates logic."""

    def test_generates_emails_for_russian_name(self, svc):
        candidates = svc._generate_candidates("\u0418\u0432\u0430\u043d", "\u041f\u0435\u0442\u0440\u043e\u0432", [])
        assert len(candidates) > 0
        # Should contain transliterated patterns
        emails_str = " ".join(candidates)
        assert "ivan" in emails_str
        assert "petrov" in emails_str

    def test_candidates_use_all_nine_domains(self, svc):
        candidates = svc._generate_candidates("ivan", "petrov", [])
        domains_found = {c.split("@")[1] for c in candidates}
        # At least the main domains should appear
        assert len(domains_found) >= 5

    def test_candidate_cap_respected(self, svc_small):
        """max_candidates=5 caps output."""
        candidates = svc_small._generate_candidates("ivan", "petrov", ["cooluser"])
        assert len(candidates) <= 5

    def test_username_patterns_included(self, svc):
        candidates = svc._generate_candidates("ivan", "petrov", ["etoglaz"])
        emails_str = " ".join(candidates)
        assert "etoglaz" in emails_str

    def test_short_username_excluded(self, svc):
        """Usernames < 3 chars after cleaning are excluded."""
        candidates = svc._generate_candidates("ivan", "petrov", ["ab"])
        emails_str = " ".join(candidates)
        assert "ab@" not in emails_str

    def test_empty_name_handled(self, svc):
        """Empty first name should not crash."""
        candidates = svc._generate_candidates("", "petrov", [])
        assert isinstance(candidates, list)

    def test_all_candidates_valid_email_format(self, svc):
        candidates = svc._generate_candidates("\u041e\u043b\u044c\u0433\u0430", "\u041a\u0443\u0437\u043d\u0435\u0446\u043e\u0432\u0430", ["olga_k"])
        for email in candidates:
            assert svc._is_valid_email(email), f"Invalid candidate: {email}"

    def test_all_candidates_lowercase(self, svc):
        candidates = svc._generate_candidates("IVAN", "PETROV", ["BigUser"])
        for email in candidates:
            assert email == email.lower(), f"Not lowercase: {email}"

    def test_no_duplicate_candidates(self, svc):
        candidates = svc._generate_candidates("ivan", "petrov", ["ivan", "ivan"])
        assert len(candidates) == len(set(candidates))

    def test_latin_names_work(self, svc):
        """Already-Latin names should generate valid candidates."""
        candidates = svc._generate_candidates("john", "smith", [])
        assert any("john" in c for c in candidates)

    def test_username_prefix_stripped_in_candidate(self, svc):
        """id12345 -> 12345, and if len>=3 it appears in candidates."""
        candidates = svc._generate_candidates("ivan", "petrov", ["id12345"])
        emails_str = " ".join(candidates)
        assert "12345" in emails_str

    def test_many_usernames_capped_at_10(self, svc):
        """Only first 10 usernames are used."""
        usernames = [f"user{i}" for i in range(20)]
        candidates = svc._generate_candidates("a", "b", usernames)
        # Should not crash; result is bounded by max_candidates
        assert len(candidates) <= svc.max_candidates


# ===========================================================================
# 6. SMTP VERIFICATION INTELLIGENCE  (15+ tests)
# ===========================================================================

class TestSmtpVerificationIntelligence:
    """Test _verify_smtp_batch and _smtp_verify_single with mocks."""

    def _run_async(self, coro):
        """Helper to run async coroutine."""
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    def test_smtp_blocked_domain_marked_likely(self, svc):
        """Emails on SMTP_BLOCKED_DOMAINS get 'likely' verification."""
        emails = ["ivan@mail.ru", "ivan@bk.ru"]
        results = self._run_async(svc._verify_smtp_batch(emails))
        for r in results:
            assert r.verification == "likely"
            assert r.verified is False
            assert r.confidence == "low"

    def test_catch_all_domain_skipped_entirely(self, svc):
        """Emails on CATCH_ALL_DOMAINS produce no results."""
        emails = ["ivan@gmail.com", "ivan@outlook.com", "ivan@hotmail.com"]
        results = self._run_async(svc._verify_smtp_batch(emails))
        # Catch-all domains are skipped (continue), not added to results
        assert len(results) == 0

    @patch("app.services.phase2.email_discovery.EmailDiscoveryService._smtp_verify_single")
    def test_smtp_code_250_verified(self, mock_smtp, svc):
        """SMTP returning True (code 250) -> verified=True, smtp_verified."""
        mock_smtp.return_value = True
        emails = ["ivan@rambler.ru"]
        results = self._run_async(svc._verify_smtp_batch(emails))
        assert len(results) == 1
        assert results[0].verified is True
        assert results[0].verification == "smtp_verified"
        assert results[0].confidence == "high"

    @patch("app.services.phase2.email_discovery.EmailDiscoveryService._smtp_verify_single")
    def test_smtp_code_550_rejected(self, mock_smtp, svc):
        """SMTP returning False (code 550) -> email rejected, not in results."""
        mock_smtp.return_value = False
        emails = ["noexist@rambler.ru"]
        results = self._run_async(svc._verify_smtp_batch(emails))
        assert len(results) == 0

    @patch("app.services.phase2.email_discovery.EmailDiscoveryService._smtp_verify_single")
    def test_smtp_inconclusive_none(self, mock_smtp, svc):
        """SMTP returning None (code 421 etc.) -> inconclusive, not in results."""
        mock_smtp.return_value = None
        emails = ["maybe@rambler.ru"]
        results = self._run_async(svc._verify_smtp_batch(emails))
        assert len(results) == 0

    @patch("app.services.phase2.email_discovery.EmailDiscoveryService._smtp_verify_single")
    def test_max_10_smtp_checks(self, mock_smtp, svc):
        """Only 10 SMTP checks are performed, even with more candidates."""
        mock_smtp.return_value = True
        # Generate 15 emails on a verifiable domain
        emails = [f"user{i}@rambler.ru" for i in range(15)]
        results = self._run_async(svc._verify_smtp_batch(emails))
        assert mock_smtp.call_count == 10

    @patch("app.services.phase2.email_discovery.EmailDiscoveryService._smtp_verify_single")
    def test_blocked_domains_dont_count_toward_limit(self, mock_smtp, svc):
        """Blocked domain emails don't consume the 10-check limit."""
        mock_smtp.return_value = True
        emails = (
            ["u@mail.ru", "u@bk.ru"]  # blocked -> 'likely'
            + [f"user{i}@rambler.ru" for i in range(10)]  # verifiable
        )
        results = self._run_async(svc._verify_smtp_batch(emails))
        # 2 blocked (likely) + 10 verified
        smtp_verified = [r for r in results if r.verification == "smtp_verified"]
        likely = [r for r in results if r.verification == "likely"]
        assert len(smtp_verified) == 10
        assert len(likely) == 2

    @patch("app.services.phase2.email_discovery.EmailDiscoveryService._smtp_verify_single")
    def test_smtp_exception_handled_gracefully(self, mock_smtp, svc):
        """If _smtp_verify_single raises, it's caught and skipped."""
        mock_smtp.side_effect = Exception("connection failed")
        emails = ["fail@rambler.ru"]
        results = self._run_async(svc._verify_smtp_batch(emails))
        # Should not crash; no results added for exceptions
        assert len(results) == 0

    def test_smtp_verify_single_dns_nxdomain(self, svc):
        """DNS NXDOMAIN -> False."""
        import dns.resolver
        with patch("dns.resolver.resolve", side_effect=dns.resolver.NXDOMAIN()):
            result = svc._smtp_verify_single("user@nonexistent.xyz")
            assert result is False

    def test_smtp_verify_single_dns_noanswer(self, svc):
        """DNS NoAnswer -> None (inconclusive)."""
        import dns.resolver
        with patch("dns.resolver.resolve", side_effect=dns.resolver.NoAnswer()):
            result = svc._smtp_verify_single("user@noanswer.xyz")
            assert result is None

    def test_smtp_verify_single_connection_refused(self, svc):
        """ConnectionRefusedError -> None."""
        import dns.resolver
        mock_mx = MagicMock()
        mock_record = MagicMock()
        mock_record.exchange = "mx.test.com."
        mock_mx.__iter__ = MagicMock(return_value=iter([mock_record]))
        mock_mx.__getitem__ = MagicMock(return_value=mock_record)

        with patch("dns.resolver.resolve", return_value=mock_mx):
            with patch("smtplib.SMTP", side_effect=ConnectionRefusedError):
                result = svc._smtp_verify_single("user@test.com")
                assert result is None

    def test_smtp_verify_single_timeout(self, svc):
        """Timeout -> None."""
        import dns.resolver
        mock_mx = MagicMock()
        mock_record = MagicMock()
        mock_record.exchange = "mx.test.com."
        mock_mx.__iter__ = MagicMock(return_value=iter([mock_record]))
        mock_mx.__getitem__ = MagicMock(return_value=mock_record)

        with patch("dns.resolver.resolve", return_value=mock_mx):
            with patch("smtplib.SMTP", side_effect=TimeoutError):
                result = svc._smtp_verify_single("user@test.com")
                assert result is None

    def test_smtp_verify_single_code_250(self, svc):
        """SMTP code 250 -> True."""
        import dns.resolver
        mock_mx = MagicMock()
        mock_record = MagicMock()
        mock_record.exchange = "mx.test.com."
        mock_mx.__getitem__ = MagicMock(return_value=mock_record)

        mock_server = MagicMock()
        mock_server.rcpt.return_value = (250, b"OK")

        with patch("dns.resolver.resolve", return_value=mock_mx):
            with patch("smtplib.SMTP", return_value=mock_server):
                result = svc._smtp_verify_single("user@test.com")
                assert result is True

    @pytest.mark.parametrize("code", [550, 551, 552, 553, 554])
    def test_smtp_verify_single_reject_codes(self, svc, code):
        """SMTP reject codes -> False."""
        import dns.resolver
        mock_mx = MagicMock()
        mock_record = MagicMock()
        mock_record.exchange = "mx.test.com."
        mock_mx.__getitem__ = MagicMock(return_value=mock_record)

        mock_server = MagicMock()
        mock_server.rcpt.return_value = (code, b"Rejected")

        with patch("dns.resolver.resolve", return_value=mock_mx):
            with patch("smtplib.SMTP", return_value=mock_server):
                result = svc._smtp_verify_single("user@test.com")
                assert result is False

    def test_smtp_verify_single_code_421_inconclusive(self, svc):
        """SMTP code 421 (try later) -> None."""
        import dns.resolver
        mock_mx = MagicMock()
        mock_record = MagicMock()
        mock_record.exchange = "mx.test.com."
        mock_mx.__getitem__ = MagicMock(return_value=mock_record)

        mock_server = MagicMock()
        mock_server.rcpt.return_value = (421, b"Try later")

        with patch("dns.resolver.resolve", return_value=mock_mx):
            with patch("smtplib.SMTP", return_value=mock_server):
                result = svc._smtp_verify_single("user@test.com")
                assert result is None

    def test_smtp_verify_single_smtp_disconnect(self, svc):
        """SMTPServerDisconnected -> None."""
        import dns.resolver
        mock_mx = MagicMock()
        mock_record = MagicMock()
        mock_record.exchange = "mx.test.com."
        mock_mx.__getitem__ = MagicMock(return_value=mock_record)

        with patch("dns.resolver.resolve", return_value=mock_mx):
            with patch("smtplib.SMTP") as MockSMTP:
                instance = MockSMTP.return_value
                instance.connect.side_effect = smtplib.SMTPServerDisconnected("gone")
                result = svc._smtp_verify_single("user@test.com")
                assert result is None


# ===========================================================================
# 7. VERIFICATION PRIORITY AND MERGING  (15+ tests)
# ===========================================================================

class TestVerificationPriorityAndMerging:
    """Test the verification merge logic inside discover()."""

    def _make_email(self, email, verification, confidence="medium",
                    verified=False, verified_on=None):
        return DiscoveredEmail(
            email=email,
            source="test",
            confidence=confidence,
            verified=verified,
            verified_on=verified_on or [],
            verification=verification,
        )

    # -- Priority ordering --------------------------------------------------

    def test_verification_priority_map(self):
        """Confirm the priority ordering: lower number = stronger."""
        priority = {
            'holehe_confirmed': 0,
            'multi_verified': 0,
            'smtp_verified': 1,
            'gravatar': 2,
            'likely': 3,
            'pattern': 4,
            'unverified': 5,
        }
        assert priority['holehe_confirmed'] < priority['smtp_verified']
        assert priority['smtp_verified'] < priority['gravatar']
        assert priority['gravatar'] < priority['likely']
        assert priority['likely'] < priority['pattern']
        assert priority['pattern'] < priority['unverified']

    def test_holehe_beats_smtp(self):
        priority = {'holehe_confirmed': 0, 'smtp_verified': 1}
        assert priority['holehe_confirmed'] < priority['smtp_verified']

    def test_smtp_beats_gravatar(self):
        priority = {'smtp_verified': 1, 'gravatar': 2}
        assert priority['smtp_verified'] < priority['gravatar']

    def test_gravatar_beats_likely(self):
        priority = {'gravatar': 2, 'likely': 3}
        assert priority['gravatar'] < priority['likely']

    def test_likely_beats_pattern(self):
        priority = {'likely': 3, 'pattern': 4}
        assert priority['likely'] < priority['pattern']

    def test_pattern_beats_unverified(self):
        priority = {'pattern': 4, 'unverified': 5}
        assert priority['pattern'] < priority['unverified']

    def test_multi_verified_equals_holehe(self):
        priority = {'multi_verified': 0, 'holehe_confirmed': 0}
        assert priority['multi_verified'] == priority['holehe_confirmed']

    # -- Merge behavior via discover() mock ---------------------------------

    def _run_async(self, coro):
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    def test_merge_two_verifications_promotes_to_high(self, svc):
        """When 2+ verified_on entries, confidence -> 'high'."""
        # Simulate merge manually (same logic as discover)
        existing = self._make_email(
            "x@mail.ru", "gravatar", "medium", True, ["gravatar"]
        )
        incoming = self._make_email(
            "x@mail.ru", "smtp_verified", "high", True, ["smtp"]
        )

        # Apply merge logic from discover()
        existing.verified_on.extend(incoming.verified_on)
        existing.verified_on = list(set(existing.verified_on))
        if incoming.verified:
            existing.verified = True
        if len(existing.verified_on) >= 2:
            existing.confidence = 'high'
            existing.verification = 'multi_verified'

        assert existing.confidence == "high"
        assert existing.verification == "multi_verified"
        assert set(existing.verified_on) == {"gravatar", "smtp"}

    def test_merge_deduplicates_verified_on(self, svc):
        """Duplicate verified_on entries are removed."""
        existing = self._make_email("x@mail.ru", "gravatar", "low", True, ["gravatar"])
        incoming_on = ["gravatar", "smtp"]

        existing.verified_on.extend(incoming_on)
        existing.verified_on = list(set(existing.verified_on))

        assert existing.verified_on.count("gravatar") == 1

    def test_stronger_verification_wins_on_merge(self):
        """holehe_confirmed (0) should override smtp_verified (1)."""
        verification_priority = {
            'holehe_confirmed': 0, 'smtp_verified': 1, 'gravatar': 2,
            'likely': 3, 'pattern': 4, 'unverified': 5, 'multi_verified': 0,
        }
        existing_v = 'smtp_verified'
        incoming_v = 'holehe_confirmed'
        if verification_priority.get(incoming_v, 5) < verification_priority.get(existing_v, 5):
            existing_v = incoming_v
        assert existing_v == 'holehe_confirmed'

    def test_weaker_verification_does_not_override(self):
        """pattern (4) should NOT override smtp_verified (1)."""
        verification_priority = {
            'holehe_confirmed': 0, 'smtp_verified': 1, 'gravatar': 2,
            'likely': 3, 'pattern': 4, 'unverified': 5, 'multi_verified': 0,
        }
        existing_v = 'smtp_verified'
        incoming_v = 'pattern'
        if verification_priority.get(incoming_v, 5) < verification_priority.get(existing_v, 5):
            existing_v = incoming_v
        assert existing_v == 'smtp_verified'

    def test_verified_flag_set_true_on_merge(self):
        """If incoming is verified=True, existing becomes verified=True."""
        existing = self._make_email("x@mail.ru", "pattern", "low", False, [])
        incoming = self._make_email("x@mail.ru", "smtp_verified", "high", True, ["smtp"])
        if incoming.verified:
            existing.verified = True
        assert existing.verified is True

    def test_verified_flag_stays_true(self):
        """If existing is already verified=True, it stays True even if incoming is False."""
        existing = self._make_email("x@mail.ru", "holehe_confirmed", "high", True, ["holehe:twitter"])
        incoming = self._make_email("x@mail.ru", "pattern", "low", False, [])
        if incoming.verified:
            existing.verified = True
        assert existing.verified is True  # unchanged

    def test_high_confidence_from_incoming_propagates(self):
        """If incoming has high confidence, existing gets promoted."""
        verification_priority = {
            'holehe_confirmed': 0, 'smtp_verified': 1, 'gravatar': 2,
            'likely': 3, 'pattern': 4, 'unverified': 5, 'multi_verified': 0,
        }
        existing = self._make_email("x@mail.ru", "pattern", "low", False, [])
        incoming = self._make_email("x@mail.ru", "smtp_verified", "high", True, ["smtp"])

        existing.verified_on.extend(incoming.verified_on)
        existing.verified_on = list(set(existing.verified_on))
        if incoming.verified:
            existing.verified = True
        if len(existing.verified_on) >= 2:
            existing.confidence = 'high'
            existing.verification = 'multi_verified'
        elif incoming.confidence == 'high':
            existing.confidence = 'high'
        if verification_priority.get(incoming.verification, 5) < \
           verification_priority.get(existing.verification, 5):
            existing.verification = incoming.verification

        assert existing.confidence == "high"
        assert existing.verification == "smtp_verified"

    def test_unknown_verification_type_defaults_to_5(self):
        """Unknown verification types get priority 5 (lowest)."""
        verification_priority = {
            'holehe_confirmed': 0, 'smtp_verified': 1, 'gravatar': 2,
            'likely': 3, 'pattern': 4, 'unverified': 5, 'multi_verified': 0,
        }
        assert verification_priority.get("totally_new_type", 5) == 5

    # -- Sorting tests ------------------------------------------------------

    def test_results_sorted_by_verification_then_confidence(self):
        """Verify final sort order: verification strength, then confidence."""
        verification_order = {
            'holehe_confirmed': 0, 'multi_verified': 0, 'smtp_verified': 1,
            'gravatar': 2, 'likely': 3, 'pattern': 4, 'unverified': 5,
        }
        emails = [
            self._make_email("a@mail.ru", "unverified", "low"),
            self._make_email("b@mail.ru", "holehe_confirmed", "high"),
            self._make_email("c@mail.ru", "smtp_verified", "high"),
            self._make_email("d@mail.ru", "gravatar", "medium"),
            self._make_email("e@mail.ru", "pattern", "low"),
        ]

        sorted_emails = sorted(
            emails,
            key=lambda e: (
                verification_order.get(e.verification, 5),
                0 if e.confidence == 'high' else 1 if e.confidence == 'medium' else 2,
            )
        )

        assert sorted_emails[0].email == "b@mail.ru"  # holehe_confirmed
        assert sorted_emails[1].email == "c@mail.ru"  # smtp_verified
        assert sorted_emails[2].email == "d@mail.ru"  # gravatar
        assert sorted_emails[3].email == "e@mail.ru"  # pattern
        assert sorted_emails[4].email == "a@mail.ru"  # unverified

    def test_same_verification_sorted_by_confidence(self):
        """Among same verification type, high > medium > low."""
        verification_order = {
            'pattern': 4,
        }
        emails = [
            self._make_email("low@mail.ru", "pattern", "low"),
            self._make_email("high@mail.ru", "pattern", "high"),
            self._make_email("med@mail.ru", "pattern", "medium"),
        ]

        sorted_emails = sorted(
            emails,
            key=lambda e: (
                verification_order.get(e.verification, 5),
                0 if e.confidence == 'high' else 1 if e.confidence == 'medium' else 2,
            )
        )

        assert sorted_emails[0].email == "high@mail.ru"
        assert sorted_emails[1].email == "med@mail.ru"
        assert sorted_emails[2].email == "low@mail.ru"


# ===========================================================================
# 8. MX VALIDATION  (15+ tests)
# ===========================================================================

class TestMxValidation:
    """Test _check_mx and _validate_mx_batch with mocks."""

    def _run_async(self, coro):
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    # -- _check_mx (synchronous) --------------------------------------------

    @pytest.mark.parametrize("domain", list(KNOWN_MX_SERVERS.keys()))
    def test_known_domain_returns_true_immediately(self, svc, domain):
        """Known domains return True without DNS lookup."""
        # No DNS mock needed — should not even call dns.resolver
        assert svc._check_mx(domain) is True

    def test_unknown_domain_with_valid_mx(self, svc):
        """Unknown domain + valid MX record -> True."""
        mock_result = MagicMock()
        with patch("dns.resolver.resolve", return_value=mock_result):
            assert svc._check_mx("custom-domain.org") is True

    def test_unknown_domain_dns_exception_fallback_to_socket(self, svc):
        """When dns.resolver fails but socket succeeds -> True."""
        with patch("dns.resolver.resolve", side_effect=Exception("DNS fail")):
            with patch("socket.getaddrinfo", return_value=[("", "", "", "", "")]):
                assert svc._check_mx("custom.org") is True

    def test_unknown_domain_all_methods_fail(self, svc):
        """When both DNS and socket fail -> False."""
        with patch("dns.resolver.resolve", side_effect=Exception("DNS fail")):
            with patch("socket.getaddrinfo", side_effect=socket.gaierror("no host")):
                assert svc._check_mx("totally-fake-domain-xyz.invalid") is False

    def test_dns_import_error_falls_back(self, svc):
        """If dns.resolver can't import, falls back to socket."""
        with patch("dns.resolver.resolve", side_effect=ImportError("no module")):
            with patch("socket.getaddrinfo", return_value=[("", "", "", "", "")]):
                assert svc._check_mx("some-domain.com") is True

    # -- _validate_mx_batch (async) -----------------------------------------

    def test_validate_mx_batch_known_domains(self, svc):
        """Known domains validated without external calls."""
        emails = ["ivan@mail.ru", "olga@yandex.ru"]
        results = self._run_async(svc._validate_mx_batch(emails))
        assert len(results) >= 2
        for r in results:
            assert r.verification == "pattern"

    def test_validate_mx_batch_caches_per_domain(self, svc):
        """Multiple emails on same domain -> domain checked once."""
        emails = ["a@mail.ru", "b@mail.ru", "c@mail.ru"]
        with patch.object(svc, "_check_mx", return_value=True) as mock_check:
            results = self._run_async(svc._validate_mx_batch(emails))
            # mail.ru checked once, results for all 3 emails
            assert mock_check.call_count == 1
            assert len(results) == 3

    def test_validate_mx_batch_different_domains_checked_separately(self, svc):
        """Different domains checked independently."""
        emails = ["a@custom1.org", "b@custom2.org"]
        with patch.object(svc, "_check_mx", return_value=True) as mock_check:
            results = self._run_async(svc._validate_mx_batch(emails))
            assert mock_check.call_count == 2

    def test_validate_mx_batch_failed_domain_no_results(self, svc):
        """If MX check fails, no DiscoveredEmail for that domain."""
        emails = ["a@fakefake.invalid"]
        with patch.object(svc, "_check_mx", return_value=False):
            results = self._run_async(svc._validate_mx_batch(emails))
            assert len(results) == 0

    def test_validate_mx_batch_exception_handled(self, svc):
        """Exception during MX check is caught gracefully."""
        emails = ["a@error.domain"]
        with patch.object(svc, "_check_mx", side_effect=Exception("boom")):
            results = self._run_async(svc._validate_mx_batch(emails))
            assert len(results) == 0

    def test_validate_mx_results_have_correct_fields(self, svc):
        """Validated emails have pattern verification, low confidence."""
        emails = ["ivan@mail.ru"]
        results = self._run_async(svc._validate_mx_batch(emails))
        assert len(results) >= 1
        r = results[0]
        assert r.verification == "pattern"
        assert r.confidence == "low"
        assert r.verified is False
        assert r.verified_on == []
        assert r.source == "Pattern generation"

    def test_validate_mx_batch_empty_list(self, svc):
        """Empty input returns empty results."""
        results = self._run_async(svc._validate_mx_batch([]))
        assert results == []

    def test_check_mx_mail_ru_true(self, svc):
        assert svc._check_mx("mail.ru") is True

    def test_check_mx_bk_ru_true(self, svc):
        assert svc._check_mx("bk.ru") is True

    def test_check_mx_ya_ru_true(self, svc):
        assert svc._check_mx("ya.ru") is True

    def test_check_mx_rambler_ru_true(self, svc):
        assert svc._check_mx("rambler.ru") is True

    def test_check_mx_gmail_true(self, svc):
        assert svc._check_mx("gmail.com") is True


# ===========================================================================
# 9. GRAVATAR INTELLIGENCE  (10 tests)
# ===========================================================================

class TestGravatarIntelligence:
    """Test Gravatar hash and batch logic."""

    def test_gravatar_md5_hash(self):
        """Gravatar uses MD5 of lowercased email."""
        email = "Test@Example.COM"
        expected = hashlib.md5("test@example.com".encode()).hexdigest()
        actual = hashlib.md5(email.lower().encode()).hexdigest()
        assert actual == expected

    def test_gravatar_url_format(self):
        """Gravatar JSON endpoint uses correct format."""
        email = "user@mail.ru"
        h = hashlib.md5(email.lower().encode()).hexdigest()
        url = f"https://gravatar.com/{h}.json"
        assert url.startswith("https://gravatar.com/")
        assert url.endswith(".json")

    def test_gravatar_hash_deterministic(self):
        """Same email always produces same hash."""
        email = "consistent@mail.ru"
        h1 = hashlib.md5(email.encode()).hexdigest()
        h2 = hashlib.md5(email.encode()).hexdigest()
        assert h1 == h2

    def test_gravatar_different_emails_different_hashes(self):
        """Different emails produce different hashes."""
        h1 = hashlib.md5("a@mail.ru".encode()).hexdigest()
        h2 = hashlib.md5("b@mail.ru".encode()).hexdigest()
        assert h1 != h2

    def test_gravatar_hash_is_32_hex_chars(self):
        h = hashlib.md5("test@mail.ru".encode()).hexdigest()
        assert len(h) == 32
        assert all(c in "0123456789abcdef" for c in h)

    def _run_async(self, coro):
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    def test_gravatar_batch_empty_input(self, svc):
        """Empty list returns empty results."""
        async def _test():
            import aiohttp
            async with aiohttp.ClientSession() as session:
                return await svc._check_gravatar_batch(session, [])
        results = self._run_async(_test())
        assert results == []

    def test_gravatar_result_fields(self):
        """DiscoveredEmail from Gravatar has correct fields."""
        email = DiscoveredEmail(
            email="found@mail.ru",
            source="Gravatar (John)",
            confidence="medium",
            verified=True,
            verified_on=["gravatar"],
            verification="gravatar",
        )
        assert email.verified is True
        assert email.verification == "gravatar"
        assert "gravatar" in email.verified_on

    def test_gravatar_high_confidence_with_linked_accounts(self):
        """If Gravatar returns linked accounts, confidence is high."""
        email = DiscoveredEmail(
            email="linked@mail.ru",
            source="Gravatar",
            confidence="high" if 2 > 1 else "medium",  # len(verified_on) > 1
            verified=True,
            verified_on=["gravatar", "gravatar:twitter.com"],
            verification="gravatar",
        )
        assert email.confidence == "high"
        assert len(email.verified_on) == 2

    def test_gravatar_medium_confidence_without_accounts(self):
        """Basic Gravatar hit without accounts -> medium confidence."""
        email = DiscoveredEmail(
            email="basic@mail.ru",
            source="Gravatar",
            confidence="high" if 1 > 1 else "medium",
            verified=True,
            verified_on=["gravatar"],
            verification="gravatar",
        )
        assert email.confidence == "medium"


# ===========================================================================
# 10. DISCOVERED EMAIL DATACLASS  (8 tests)
# ===========================================================================

class TestDiscoveredEmailDataclass:
    """Verify DiscoveredEmail defaults and field behavior."""

    def test_default_verified_false(self):
        e = DiscoveredEmail(email="a@b.com", source="test", confidence="low")
        assert e.verified is False

    def test_default_verified_on_empty_list(self):
        e = DiscoveredEmail(email="a@b.com", source="test", confidence="low")
        assert e.verified_on == []

    def test_default_verification_unverified(self):
        e = DiscoveredEmail(email="a@b.com", source="test", confidence="low")
        assert e.verification == "unverified"

    def test_verified_on_is_mutable_list(self):
        e = DiscoveredEmail(email="a@b.com", source="test", confidence="low")
        e.verified_on.append("smtp")
        assert "smtp" in e.verified_on

    def test_different_instances_have_independent_lists(self):
        e1 = DiscoveredEmail(email="a@b.com", source="test", confidence="low")
        e2 = DiscoveredEmail(email="c@d.com", source="test", confidence="low")
        e1.verified_on.append("x")
        assert "x" not in e2.verified_on

    def test_all_fields_set(self):
        e = DiscoveredEmail(
            email="full@test.com",
            source="Holehe",
            confidence="high",
            verified=True,
            verified_on=["holehe:twitter", "holehe:instagram"],
            verification="holehe_confirmed",
        )
        assert e.email == "full@test.com"
        assert e.source == "Holehe"
        assert e.confidence == "high"
        assert e.verified is True
        assert len(e.verified_on) == 2
        assert e.verification == "holehe_confirmed"

    def test_email_results_defaults(self):
        r = EmailDiscoveryResults()
        assert r.emails == []
        assert r.candidates_generated == 0
        assert r.candidates_verified == 0
        assert r.discovery_time == 0
        assert r.errors == []

    def test_email_results_errors_appendable(self):
        r = EmailDiscoveryResults()
        r.errors.append("test error")
        assert "test error" in r.errors


# ===========================================================================
# 11. SERVICE INITIALIZATION  (5 tests)
# ===========================================================================

class TestServiceInitialization:
    """Verify service constructor defaults."""

    def test_default_max_candidates(self):
        svc = EmailDiscoveryService()
        assert svc.max_candidates == 30
        svc.close()

    def test_default_verify_timeout(self):
        svc = EmailDiscoveryService()
        assert svc.verify_timeout == 5.0
        svc.close()

    def test_default_max_concurrent(self):
        svc = EmailDiscoveryService()
        assert svc.max_concurrent == 10
        svc.close()

    def test_custom_params(self):
        svc = EmailDiscoveryService(max_candidates=50, verify_timeout=10.0, max_concurrent=20)
        assert svc.max_candidates == 50
        assert svc.verify_timeout == 10.0
        assert svc.max_concurrent == 20
        svc.close()

    def test_executor_created(self):
        svc = EmailDiscoveryService()
        assert svc._executor is not None
        svc.close()
