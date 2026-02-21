"""
Round 3 (ADVERSARIAL) — Type Confusion & Wrong-Type Attacks
============================================================
Tests how the system handles WRONG TYPES of input:
None, int, list, dict where str expected, bool, NaN, Inf, empty collections,
mixed-type collections, etc.

90+ tests across 6 categories:
1. None Input Attacks
2. Integer/Float Input Attacks
3. List/Dict/Object Input Attacks
4. Bool Input Attacks
5. Empty Collection Attacks
6. Mixed Type in Collections

Goal: Document expected behavior (raise, return empty, handle gracefully).
No source code modifications — tests only.
"""

import math
import re
import pytest
from dataclasses import FrozenInstanceError
from unittest.mock import patch, MagicMock

from app.utils.phone import normalize_phone
from app.services.phase2.russian_phone_validator import (
    RussianPhoneValidator, PhoneInfo, validate_phone, extract_phones_from_text,
)
from app.services.phase2.email_discovery import EmailDiscoveryService, DiscoveredEmail
from app.services.phase2.phone_discovery import PhoneDiscoveryService, DiscoveredPhone
from app.services.phase2.base_source import SourceResult, SourceTier, SourceType
from app.services.phase2.source_manager import SourceManager


# ---------------------------------------------------------------------------
# Helpers / Fixtures
# ---------------------------------------------------------------------------

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


def _make_source_result(**overrides):
    """Helper to create a valid SourceResult with sensible defaults."""
    defaults = dict(
        data_type="email",
        value="test@mail.ru",
        source_name="TestSource",
        source_tier=SourceTier.C,
        confidence=0.5,
    )
    defaults.update(overrides)
    return SourceResult(**defaults)


# ===================================================================
# 1.  NONE INPUT ATTACKS  (20+ tests)
# ===================================================================

class TestNoneInputAttacks:
    """Feed None where str / list / number expected."""

    # -- normalize_phone --
    def test_normalize_phone_none_returns_empty(self):
        """normalize_phone(None) -> '' because `not phone` is True for None."""
        assert normalize_phone(None) == ''

    # -- RussianPhoneValidator.validate --
    def test_validator_validate_none(self, validator):
        """validate(None) propagates to normalize_phone which returns '',
        then re.sub on '' works but produces invalid phone."""
        info = validator.validate(None)
        assert isinstance(info, PhoneInfo)
        assert info.is_valid is False

    # -- RussianPhoneValidator.extract_phones --
    def test_extract_phones_none(self, validator):
        """extract_phones(None) — re.findall on None raises TypeError."""
        with pytest.raises(TypeError):
            validator.extract_phones(None)

    # -- RussianPhoneValidator.normalize static --
    def test_validator_normalize_none(self):
        """Static normalize(None) delegates to canonical, returns ''."""
        assert RussianPhoneValidator.normalize(None) == ''

    # -- RussianPhoneValidator.format_display --
    def test_format_display_none(self):
        """format_display(None) — normalizes to '' then returns None (original)."""
        result = RussianPhoneValidator.format_display(None)
        assert result is None

    # -- RussianPhoneValidator.is_russian_mobile --
    def test_is_russian_mobile_none(self):
        """is_russian_mobile(None) — re.sub on None raises TypeError."""
        with pytest.raises(TypeError):
            RussianPhoneValidator.is_russian_mobile(None)

    # -- RussianPhoneValidator.generate_variants --
    def test_generate_variants_none(self, validator):
        """generate_variants(None) — validate returns invalid, returns [None]."""
        result = validator.generate_variants(None)
        assert result == [None]

    # -- EmailDiscoveryService._generate_candidates --
    def test_generate_candidates_none_none_none(self, email_svc):
        """_generate_candidates(None, None, None) — crashes on None.lower()."""
        with pytest.raises((TypeError, AttributeError)):
            email_svc._generate_candidates(None, None, None)

    def test_generate_candidates_none_name_valid_usernames(self, email_svc):
        """None first_name, valid last_name."""
        with pytest.raises((TypeError, AttributeError)):
            email_svc._generate_candidates(None, 'Ivanov', ['user1'])

    def test_generate_candidates_valid_name_none_usernames(self, email_svc):
        """Valid names, None usernames — iteration on None raises TypeError."""
        with pytest.raises((TypeError, AttributeError)):
            email_svc._generate_candidates('Ivan', 'Ivanov', None)

    # -- EmailDiscoveryService._transliterate --
    def test_transliterate_none(self, email_svc):
        """_transliterate(None) — None.lower() raises AttributeError."""
        with pytest.raises((TypeError, AttributeError)):
            email_svc._transliterate(None)

    # -- EmailDiscoveryService._is_valid_email --
    def test_is_valid_email_none(self, email_svc):
        """_is_valid_email(None) — None.lower() raises AttributeError."""
        with pytest.raises((TypeError, AttributeError)):
            email_svc._is_valid_email(None)

    # -- EmailDiscoveryService._clean_username --
    def test_clean_username_none(self, email_svc):
        """_clean_username(None) — None.lower() raises AttributeError."""
        with pytest.raises((TypeError, AttributeError)):
            email_svc._clean_username(None)

    # -- PhoneDiscoveryService._extract_from_usernames --
    def test_extract_from_usernames_none(self, phone_svc):
        """_extract_from_usernames(None) — iterating None raises TypeError."""
        with pytest.raises(TypeError):
            phone_svc._extract_from_usernames(None)

    # -- PhoneDiscoveryService._extract_from_emails --
    def test_extract_from_emails_none(self, phone_svc):
        """_extract_from_emails(None) — iterating None raises TypeError."""
        with pytest.raises(TypeError):
            phone_svc._extract_from_emails(None)

    # -- PhoneDiscoveryService._normalize_key --
    def test_normalize_key_none(self):
        """_normalize_key(None) — re.sub on None raises TypeError."""
        with pytest.raises(TypeError):
            PhoneDiscoveryService._normalize_key(None)

    # -- SourceResult with None fields --
    def test_source_result_none_value(self):
        """SourceResult(value=None) — confidence_label still works on float."""
        sr = _make_source_result(value=None)
        assert sr.value is None

    def test_source_result_none_value_to_dict(self):
        """to_dict() with None value — key present, value None."""
        sr = _make_source_result(value=None)
        d = sr.to_dict()
        assert d['value'] is None

    def test_source_result_none_confidence(self):
        """SourceResult(confidence=None) — confidence_label comparison raises TypeError."""
        sr = _make_source_result(confidence=None)
        with pytest.raises(TypeError):
            _ = sr.confidence_label

    def test_source_result_none_data_type_deduplicate(self):
        """Deduplicate with None data_type — f-string works but key is weird."""
        sr = _make_source_result(data_type=None, value="x@mail.ru")
        mgr = SourceManager.__new__(SourceManager)
        mgr.sources = []
        result = mgr._deduplicate([sr])
        assert len(result) == 1


# ===================================================================
# 2.  INTEGER / FLOAT INPUT ATTACKS  (15+ tests)
# ===================================================================

class TestIntegerFloatAttacks:
    """Feed int, float, inf, nan where str or bounded float expected."""

    # -- normalize_phone --
    def test_normalize_phone_int(self):
        """normalize_phone(12345) — int is truthy, but re.sub expects str."""
        with pytest.raises(TypeError):
            normalize_phone(12345)

    def test_normalize_phone_zero(self):
        """normalize_phone(0) — falsy int, so returns ''."""
        assert normalize_phone(0) == ''

    def test_normalize_phone_float(self):
        """normalize_phone(7.916) — re.sub on float raises TypeError."""
        with pytest.raises(TypeError):
            normalize_phone(7.916)

    # -- RussianPhoneValidator.validate --
    def test_validate_int(self, validator):
        """validate(12345) — delegated to normalize_phone, crashes on re.sub."""
        with pytest.raises(TypeError):
            validator.validate(12345)

    # -- RussianPhoneValidator.extract_phones --
    def test_extract_phones_int(self, validator):
        """extract_phones(42) — re.findall on int raises TypeError."""
        with pytest.raises(TypeError):
            validator.extract_phones(42)

    # -- EmailDiscoveryService._transliterate --
    def test_transliterate_int(self, email_svc):
        """_transliterate(42) — int.lower() raises AttributeError."""
        with pytest.raises((TypeError, AttributeError)):
            email_svc._transliterate(42)

    # -- EmailDiscoveryService._is_valid_email --
    def test_is_valid_email_int(self, email_svc):
        """_is_valid_email(42) — 42.lower() raises AttributeError."""
        with pytest.raises((TypeError, AttributeError)):
            email_svc._is_valid_email(42)

    # -- EmailDiscoveryService._generate_candidates with ints --
    def test_generate_candidates_int_names(self, email_svc):
        """_generate_candidates(42, 42, [42]) — int.lower() raises."""
        with pytest.raises((TypeError, AttributeError)):
            email_svc._generate_candidates(42, 42, [42])

    # -- PhoneDiscoveryService._normalize_key --
    def test_normalize_key_int(self):
        """_normalize_key(12345) — re.sub on int raises TypeError."""
        with pytest.raises(TypeError):
            PhoneDiscoveryService._normalize_key(12345)

    # -- SourceResult confidence edge cases --
    def test_source_result_confidence_inf(self):
        """SourceResult(confidence=float('inf')) — inf >= 0.9 is True -> 'very_high'."""
        sr = _make_source_result(confidence=float('inf'))
        assert sr.confidence_label == "very_high"

    def test_source_result_confidence_neg_inf(self):
        """SourceResult(confidence=float('-inf')) — all comparisons fail -> 'low'."""
        sr = _make_source_result(confidence=float('-inf'))
        assert sr.confidence_label == "low"

    def test_source_result_confidence_nan(self):
        """SourceResult(confidence=float('nan')) — NaN comparisons always False -> 'low'."""
        sr = _make_source_result(confidence=float('nan'))
        assert sr.confidence_label == "low"

    def test_source_result_confidence_negative(self):
        """SourceResult(confidence=-1.0) — negative -> 'low'."""
        sr = _make_source_result(confidence=-1.0)
        assert sr.confidence_label == "low"

    def test_source_result_confidence_over_one(self):
        """SourceResult(confidence=5.0) — over 1 -> 'very_high'."""
        sr = _make_source_result(confidence=5.0)
        assert sr.confidence_label == "very_high"

    def test_source_result_to_dict_inf_confidence(self):
        """to_dict() with inf confidence — serialises infinity float."""
        sr = _make_source_result(confidence=float('inf'))
        d = sr.to_dict()
        assert d['confidence'] == float('inf')
        assert d['confidence_label'] == 'very_high'

    def test_source_result_to_dict_nan_confidence(self):
        """to_dict() with NaN confidence — serialises NaN."""
        sr = _make_source_result(confidence=float('nan'))
        d = sr.to_dict()
        assert math.isnan(d['confidence'])
        assert d['confidence_label'] == 'low'

    # -- PhoneDiscoveryService._extract_from_usernames with int items --
    def test_extract_from_usernames_int_item(self, phone_svc):
        """_extract_from_usernames([42]) — re.sub on int raises TypeError."""
        with pytest.raises(TypeError):
            phone_svc._extract_from_usernames([42])


# ===================================================================
# 3.  LIST / DICT / OBJECT INPUT ATTACKS  (15+ tests)
# ===================================================================

class TestListDictObjectAttacks:
    """Feed list, dict, custom objects where str or specific type expected."""

    # -- normalize_phone --
    def test_normalize_phone_list(self):
        """normalize_phone(['123']) — list is truthy, re.sub on list raises."""
        with pytest.raises(TypeError):
            normalize_phone(['123'])

    def test_normalize_phone_dict(self):
        """normalize_phone({'phone': '123'}) — re.sub on dict raises."""
        with pytest.raises(TypeError):
            normalize_phone({'phone': '123'})

    def test_normalize_phone_bytes(self):
        """normalize_phone(b'+79161234567') — re.sub on bytes works differently."""
        with pytest.raises(TypeError):
            normalize_phone(b'+79161234567')

    # -- RussianPhoneValidator.validate --
    def test_validate_list(self, validator):
        """validate(['phone']) — normalize delegates to re.sub, raises."""
        with pytest.raises(TypeError):
            validator.validate(['phone'])

    def test_validate_dict(self, validator):
        """validate({}) — empty dict is falsy, normalize returns '', result is invalid."""
        info = validator.validate({})
        assert info.is_valid is False
        assert info.format_type == 'unknown'

    # -- EmailDiscoveryService._generate_candidates usernames as str --
    def test_generate_candidates_usernames_str(self, email_svc):
        """Passing str instead of List[str] for usernames — iterates chars."""
        result = email_svc._generate_candidates('Ivan', 'Ivanov', 'not_a_list')
        # str is iterable so it iterates over individual characters
        # Each single char is len < 3 so gets filtered out by _clean_username check
        assert isinstance(result, list)

    def test_generate_candidates_usernames_dict(self, email_svc):
        """Passing dict for usernames — dict[:10] raises KeyError (not sliceable)."""
        with pytest.raises((TypeError, KeyError)):
            email_svc._generate_candidates('Ivan', 'Ivanov', {'key': 'val'})

    # -- PhoneDiscoveryService._extract_from_usernames --
    def test_extract_from_usernames_dict(self, phone_svc):
        """_extract_from_usernames({'key': 'val'}) — iterates keys as usernames."""
        result = phone_svc._extract_from_usernames({'key': 'val'})
        assert isinstance(result, list)

    def test_extract_from_usernames_set(self, phone_svc):
        """_extract_from_usernames({'+79161234567'}) — sets are iterable."""
        result = phone_svc._extract_from_usernames({'+79161234567'})
        assert isinstance(result, list)

    # -- PhoneDiscoveryService._extract_from_emails --
    def test_extract_from_emails_dict(self, phone_svc):
        """_extract_from_emails({'a@b.ru': True}) — iterates keys."""
        result = phone_svc._extract_from_emails({'9161234567@mail.ru': True})
        assert isinstance(result, list)
        # Dict iterates keys, so '9161234567@mail.ru' is processed
        assert any(p.number for p in result) or len(result) == 0

    def test_extract_from_emails_str_instead_of_list(self, phone_svc):
        """_extract_from_emails('test@mail.ru') — iterates chars, each has no '@'."""
        result = phone_svc._extract_from_emails('test@mail.ru')
        assert isinstance(result, list)
        # Each char is iterated; only '@' char contains '@' but split gives ['', '']
        assert len(result) == 0

    # -- SourceManager._deduplicate with wrong objects --
    def test_deduplicate_non_source_result_objects(self):
        """_deduplicate with plain dicts instead of SourceResult — crashes on attribute access."""
        mgr = SourceManager.__new__(SourceManager)
        mgr.sources = []
        with pytest.raises(AttributeError):
            mgr._deduplicate([{'data_type': 'email', 'value': 'x'}])

    def test_deduplicate_mixed_types(self):
        """_deduplicate with mixed SourceResult and None."""
        mgr = SourceManager.__new__(SourceManager)
        mgr.sources = []
        sr = _make_source_result()
        with pytest.raises(AttributeError):
            mgr._deduplicate([sr, None])

    # -- SourceResult with wrong metadata types --
    def test_source_result_raw_data_list(self):
        """SourceResult(raw_data=[1,2,3]) — to_dict won't include raw_data."""
        sr = _make_source_result(raw_data=[1, 2, 3])
        d = sr.to_dict()
        # to_dict does not include raw_data, so it still works
        assert 'data_type' in d

    def test_source_result_metadata_list(self):
        """SourceResult(metadata=[1,2,3]) — to_dict includes metadata."""
        sr = _make_source_result(metadata=[1, 2, 3])
        d = sr.to_dict()
        assert d['metadata'] == [1, 2, 3]


# ===================================================================
# 4.  BOOL INPUT ATTACKS  (10+ tests)
# ===================================================================

class TestBoolInputAttacks:
    """Bool is a subtype of int in Python — test the subtle consequences."""

    # -- normalize_phone --
    def test_normalize_phone_true(self):
        """normalize_phone(True) — True is truthy, but re.sub(r'\\D', '', True) raises."""
        with pytest.raises(TypeError):
            normalize_phone(True)

    def test_normalize_phone_false(self):
        """normalize_phone(False) — False is falsy, returns ''."""
        assert normalize_phone(False) == ''

    # -- RussianPhoneValidator --
    def test_validate_true(self, validator):
        """validate(True) — bool -> normalize -> re.sub raises TypeError."""
        with pytest.raises(TypeError):
            validator.validate(True)

    def test_is_russian_mobile_true(self):
        """is_russian_mobile(True) — re.sub on bool raises TypeError."""
        with pytest.raises(TypeError):
            RussianPhoneValidator.is_russian_mobile(True)

    # -- EmailDiscoveryService --
    def test_transliterate_true(self, email_svc):
        """_transliterate(True) — bool.lower() raises AttributeError."""
        with pytest.raises((TypeError, AttributeError)):
            email_svc._transliterate(True)

    def test_transliterate_false(self, email_svc):
        """_transliterate(False) — bool.lower() raises AttributeError."""
        with pytest.raises((TypeError, AttributeError)):
            email_svc._transliterate(False)

    def test_is_valid_email_true(self, email_svc):
        """_is_valid_email(True) — True.lower() raises AttributeError."""
        with pytest.raises((TypeError, AttributeError)):
            email_svc._is_valid_email(True)

    def test_is_valid_email_false(self, email_svc):
        """_is_valid_email(False) — False.lower() raises AttributeError."""
        with pytest.raises((TypeError, AttributeError)):
            email_svc._is_valid_email(False)

    # -- SourceResult --
    def test_source_result_verified_str(self):
        """SourceResult(verified='yes') — stored as str, but still works in to_dict."""
        sr = _make_source_result(verified='yes')
        d = sr.to_dict()
        assert d['verified'] == 'yes'

    def test_source_result_confidence_true(self):
        """SourceResult(confidence=True) — True == 1 (int), 1 >= 0.9 -> 'very_high'."""
        sr = _make_source_result(confidence=True)
        assert sr.confidence_label == "very_high"

    def test_source_result_confidence_false(self):
        """SourceResult(confidence=False) — False == 0, 0 < 0.5 -> 'low'."""
        sr = _make_source_result(confidence=False)
        assert sr.confidence_label == "low"

    def test_clean_username_true(self, email_svc):
        """_clean_username(True) — True.lower() raises AttributeError."""
        with pytest.raises((TypeError, AttributeError)):
            email_svc._clean_username(True)


# ===================================================================
# 5.  EMPTY COLLECTION ATTACKS  (15+ tests)
# ===================================================================

class TestEmptyCollectionAttacks:
    """Empty strings, empty lists, empty dicts — boundary of valid input."""

    # -- normalize_phone --
    def test_normalize_phone_empty_str(self):
        """normalize_phone('') — falsy, returns ''."""
        assert normalize_phone('') == ''

    # -- RussianPhoneValidator --
    def test_validate_empty_str(self, validator):
        """validate('') — normalizes to '', is_valid = False."""
        info = validator.validate('')
        assert info.is_valid is False
        assert info.format_type == 'unknown'

    def test_extract_phones_empty_str(self, validator):
        """extract_phones('') — no matches, returns []."""
        result = validator.extract_phones('')
        assert result == []

    def test_generate_variants_empty_str(self, validator):
        """generate_variants('') — invalid phone, returns ['']."""
        result = validator.generate_variants('')
        assert result == ['']

    def test_is_russian_mobile_empty_str(self):
        """is_russian_mobile('') — digits='', len=0, returns False."""
        assert RussianPhoneValidator.is_russian_mobile('') is False

    # -- EmailDiscoveryService --
    def test_generate_candidates_all_empty(self, email_svc):
        """_generate_candidates('', '', []) — empty names, no usernames."""
        result = email_svc._generate_candidates('', '', [])
        assert isinstance(result, list)
        # Empty names produce empty translit, patterns < 2 chars get filtered
        assert len(result) == 0

    def test_generate_candidates_empty_names_with_usernames(self, email_svc):
        """Empty names but valid usernames generate candidates."""
        result = email_svc._generate_candidates('', '', ['testuser'])
        assert isinstance(result, list)
        assert len(result) > 0

    def test_transliterate_empty(self, email_svc):
        """_transliterate('') — returns ''."""
        assert email_svc._transliterate('') == ''

    def test_is_valid_email_empty(self, email_svc):
        """_is_valid_email('') — empty string doesn't match pattern."""
        assert email_svc._is_valid_email('') is False

    def test_clean_username_empty(self, email_svc):
        """_clean_username('') — returns ''."""
        assert email_svc._clean_username('') == ''

    # -- PhoneDiscoveryService --
    def test_extract_from_usernames_empty_list(self, phone_svc):
        """_extract_from_usernames([]) — returns []."""
        assert phone_svc._extract_from_usernames([]) == []

    def test_extract_from_emails_empty_list(self, phone_svc):
        """_extract_from_emails([]) — returns []."""
        assert phone_svc._extract_from_emails([]) == []

    def test_normalize_key_empty_str(self):
        """_normalize_key('') — re.sub returns '', [-10:] = ''."""
        assert PhoneDiscoveryService._normalize_key('') == ''

    @patch.dict('os.environ', {}, clear=False)
    def test_discover_sync_all_empty(self, phone_svc):
        """discover_sync('', '', []) — should run without crash, return empty."""
        result = phone_svc.discover_sync('', '', [])
        assert isinstance(result.phones, list)
        assert isinstance(result.errors, list)

    # -- SourceManager --
    def test_deduplicate_empty_list(self):
        """_deduplicate([]) — returns []."""
        mgr = SourceManager.__new__(SourceManager)
        mgr.sources = []
        assert mgr._deduplicate([]) == []

    def test_cross_validate_empty_list(self):
        """_cross_validate([]) — returns []."""
        mgr = SourceManager.__new__(SourceManager)
        mgr.sources = []
        assert mgr._cross_validate([]) == []

    def test_group_by_type_empty_list(self):
        """_group_by_type([]) — returns {}."""
        mgr = SourceManager.__new__(SourceManager)
        mgr.sources = []
        assert mgr._group_by_type([]) == {}


# ===================================================================
# 6.  MIXED TYPE IN COLLECTIONS  (15+ tests)
# ===================================================================

class TestMixedTypeCollections:
    """Collections containing a mix of valid and invalid types."""

    # -- EmailDiscoveryService._generate_candidates --
    def test_generate_candidates_mixed_usernames_none(self, email_svc):
        """Usernames list with None item — _clean_username(None) raises."""
        with pytest.raises((TypeError, AttributeError)):
            email_svc._generate_candidates('Ivan', 'Ivanov', [None])

    def test_generate_candidates_mixed_usernames_int(self, email_svc):
        """Usernames list with int item — _clean_username(42) raises."""
        with pytest.raises((TypeError, AttributeError)):
            email_svc._generate_candidates('Ivan', 'Ivanov', [42])

    def test_generate_candidates_mixed_usernames_empty_str(self, email_svc):
        """Usernames with empty string — filtered out by len < 3 check."""
        result = email_svc._generate_candidates('Ivan', 'Ivanov', ['', 'validuser'])
        assert isinstance(result, list)

    def test_generate_candidates_mixed_usernames_bool(self, email_svc):
        """Usernames with bool — _clean_username(True) raises."""
        with pytest.raises((TypeError, AttributeError)):
            email_svc._generate_candidates('Ivan', 'Ivanov', [True])

    # -- PhoneDiscoveryService._extract_from_usernames --
    def test_extract_from_usernames_mixed_with_none(self, phone_svc):
        """[None, '79161234567'] — re.sub on None raises TypeError."""
        with pytest.raises(TypeError):
            phone_svc._extract_from_usernames([None, '79161234567'])

    def test_extract_from_usernames_valid_then_int(self, phone_svc):
        """['valid', 42] — re.sub on int raises TypeError."""
        with pytest.raises(TypeError):
            phone_svc._extract_from_usernames(['valid', 42])

    def test_extract_from_usernames_all_empty_strings(self, phone_svc):
        """['', '', ''] — each produces digits='', len < 10, no matches."""
        result = phone_svc._extract_from_usernames(['', '', ''])
        assert result == []

    # -- PhoneDiscoveryService._extract_from_emails --
    def test_extract_from_emails_mixed_none_first(self, phone_svc):
        """[None, 'test@mail.ru'] — iterating: 'in' on None works in `if '@' not in email`
        but None doesn't contain '@'."""
        # 'in' operator on None: `'@' not in None` raises TypeError
        with pytest.raises(TypeError):
            phone_svc._extract_from_emails([None, 'test@mail.ru'])

    def test_extract_from_emails_mixed_int(self, phone_svc):
        """[42, 'test@mail.ru'] — '@' in 42 raises TypeError."""
        with pytest.raises(TypeError):
            phone_svc._extract_from_emails([42, 'test@mail.ru'])

    def test_extract_from_emails_mixed_valid_no_phone(self, phone_svc):
        """['nophone@mail.ru', '9161234567@mail.ru'] — second has phone in local part."""
        result = phone_svc._extract_from_emails(['nophone@mail.ru', '9161234567@mail.ru'])
        assert isinstance(result, list)
        assert any(p.number.endswith('9161234567') for p in result)

    def test_extract_from_emails_with_empty_str(self, phone_svc):
        """[''] — no '@' -> continue, returns []."""
        result = phone_svc._extract_from_emails([''])
        assert result == []

    def test_extract_from_emails_with_only_at_sign(self, phone_svc):
        """['@'] — split('@')[0] = '', digits = '', len < 10 -> skip."""
        result = phone_svc._extract_from_emails(['@'])
        assert result == []

    # -- SourceManager._deduplicate mixed --
    def test_deduplicate_with_int_in_list(self):
        """_deduplicate with int mixed in — AttributeError on int.data_type."""
        mgr = SourceManager.__new__(SourceManager)
        mgr.sources = []
        sr = _make_source_result()
        with pytest.raises(AttributeError):
            mgr._deduplicate([sr, 42])

    def test_deduplicate_with_str_in_list(self):
        """_deduplicate with str mixed in — AttributeError on str.data_type."""
        mgr = SourceManager.__new__(SourceManager)
        mgr.sources = []
        sr = _make_source_result()
        with pytest.raises(AttributeError):
            mgr._deduplicate([sr, "not_a_result"])

    def test_deduplicate_duplicate_values_different_sources(self):
        """Two valid SourceResults with same value — merges and boosts confidence."""
        mgr = SourceManager.__new__(SourceManager)
        mgr.sources = []
        sr1 = _make_source_result(source_name="Source1", confidence=0.5)
        sr2 = _make_source_result(source_name="Source2", confidence=0.6)
        result = mgr._deduplicate([sr1, sr2])
        assert len(result) == 1
        assert result[0].confidence > 0.5
        assert result[0].metadata['source_count'] == 2

    # -- SourceManager._cross_validate mixed --
    def test_cross_validate_with_wrong_source_tier_type(self):
        """SourceResult where source_tier is string instead of SourceTier enum."""
        mgr = SourceManager.__new__(SourceManager)
        mgr.sources = []
        sr = _make_source_result(source_tier="S")
        # _cross_validate checks source_tier == SourceTier.S -> "S" != SourceTier.S
        result = mgr._cross_validate([sr])
        assert len(result) == 1
        assert result[0].verified is False  # String "S" != SourceTier.S enum

    # -- SourceManager._group_by_type mixed --
    def test_group_by_type_multiple_types(self):
        """Group results with different data_types."""
        mgr = SourceManager.__new__(SourceManager)
        mgr.sources = []
        sr_email = _make_source_result(data_type="email")
        sr_phone = _make_source_result(data_type="phone", value="+79161234567")
        result = mgr._group_by_type([sr_email, sr_phone])
        assert 'email' in result
        assert 'phone' in result
        assert len(result['email']) == 1
        assert len(result['phone']) == 1


# ===================================================================
# 7.  ADDITIONAL TYPE CONFUSION ATTACKS  (bonus tests for 90+ count)
# ===================================================================

class TestAdditionalTypeConfusion:
    """Extra edge cases crossing type boundaries."""

    # -- normalize_phone with special string types --
    def test_normalize_phone_whitespace_only(self):
        """normalize_phone('   ') — whitespace-only is truthy. re.sub strips to '' -> len 0."""
        result = normalize_phone('   ')
        assert result == '   '  # Can't normalize, returns original

    def test_normalize_phone_unicode_digits(self):
        """normalize_phone with full-width digits (common in Japanese/CJK contexts)."""
        result = normalize_phone('\uff17\uff19\uff11\uff16\uff11\uff12\uff13\uff14\uff15\uff16\uff17')
        # re.sub(r'\D', '', ...) strips non-ASCII digits too
        assert isinstance(result, str)

    # -- SourceResult edge cases --
    def test_source_result_source_tier_none(self):
        """SourceResult with source_tier=None — to_dict calls .value on None."""
        sr = _make_source_result(source_tier=None)
        with pytest.raises(AttributeError):
            sr.to_dict()

    def test_source_result_confidence_string(self):
        """SourceResult(confidence='high') — comparison 'high' >= 0.9 raises TypeError."""
        sr = _make_source_result(confidence='high')
        with pytest.raises(TypeError):
            _ = sr.confidence_label

    def test_source_result_confidence_exactly_thresholds(self):
        """Test confidence at exact threshold boundaries."""
        assert _make_source_result(confidence=0.9).confidence_label == "very_high"
        assert _make_source_result(confidence=0.7).confidence_label == "high"
        assert _make_source_result(confidence=0.5).confidence_label == "medium"
        assert _make_source_result(confidence=0.49).confidence_label == "low"
        assert _make_source_result(confidence=0.0).confidence_label == "low"

    # -- PhoneDiscoveryService constructor types --
    def test_phone_svc_max_candidates_str(self):
        """PhoneDiscoveryService(max_candidates='50') — stored as str, may cause issues later."""
        svc = PhoneDiscoveryService(max_candidates='50')
        assert svc.max_candidates == '50'
        svc.close()

    def test_phone_svc_verify_timeout_none(self):
        """PhoneDiscoveryService(verify_timeout=None) — stored as None."""
        svc = PhoneDiscoveryService(verify_timeout=None)
        assert svc.verify_timeout is None
        svc.close()

    # -- EmailDiscoveryService constructor types --
    def test_email_svc_max_candidates_negative(self):
        """EmailDiscoveryService(max_candidates=-1) — slicing with negative limit."""
        svc = EmailDiscoveryService(max_candidates=-1)
        result = svc._generate_candidates('Ivan', 'Ivanov', ['user1'])
        # list[:-1] drops last element
        assert isinstance(result, list)
        svc.close()

    def test_email_svc_max_candidates_zero(self):
        """EmailDiscoveryService(max_candidates=0) — list[:0] returns []."""
        svc = EmailDiscoveryService(max_candidates=0)
        result = svc._generate_candidates('Ivan', 'Ivanov', ['user1'])
        assert result == []
        svc.close()

    # -- validate_phone convenience function --
    def test_validate_phone_convenience_none(self):
        """validate_phone(None) — delegates to validator.validate(None)."""
        info = validate_phone(None)
        assert info.is_valid is False

    def test_validate_phone_convenience_int(self):
        """validate_phone(42) — raises TypeError."""
        with pytest.raises(TypeError):
            validate_phone(42)

    # -- extract_phones_from_text convenience --
    def test_extract_phones_from_text_none(self):
        """extract_phones_from_text(None) — re.findall on None raises."""
        with pytest.raises(TypeError):
            extract_phones_from_text(None)

    def test_extract_phones_from_text_int(self):
        """extract_phones_from_text(42) — raises TypeError."""
        with pytest.raises(TypeError):
            extract_phones_from_text(42)

    def test_extract_phones_from_text_empty(self):
        """extract_phones_from_text('') — returns []."""
        assert extract_phones_from_text('') == []

    # -- SourceResult.to_dict with various broken states --
    def test_source_result_to_dict_all_none_fields(self):
        """SourceResult with everything None except required confidence."""
        sr = SourceResult(
            data_type=None,
            value=None,
            source_name=None,
            source_tier=None,
            confidence=0.5,
        )
        with pytest.raises(AttributeError):
            sr.to_dict()

    def test_source_result_to_dict_valid(self):
        """Baseline: valid SourceResult.to_dict() works."""
        sr = _make_source_result()
        d = sr.to_dict()
        assert d['data_type'] == 'email'
        assert d['value'] == 'test@mail.ru'
        assert d['source_tier'] == 'Pattern Generation'
        assert d['confidence'] == 0.5
        assert d['confidence_label'] == 'medium'

    # -- RussianPhoneValidator.format_display edge --
    def test_format_display_int(self):
        """format_display(42) — normalize raises TypeError."""
        with pytest.raises(TypeError):
            RussianPhoneValidator.format_display(42)

    def test_format_display_empty_str(self):
        """format_display('') — normalize returns '', no digits, returns ''."""
        result = RussianPhoneValidator.format_display('')
        assert result == ''
