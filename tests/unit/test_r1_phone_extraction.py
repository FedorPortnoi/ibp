"""
Comprehensive tests for Russian phone number extraction and validation.
=======================================================================
160+ tests covering:
  - Russian mobile format variations (40+)
  - Russian landline formats (15+)
  - Phones-from-text extraction (50+)
  - Username phone extraction (15+)
  - Email-to-phone extraction (10+)
  - Carrier detection (20+)
  - Display formatting (10+)
  - Variant generation (10+)
  - Edge cases (10+)

Targets:
  - app.services.phase2.russian_phone_validator.RussianPhoneValidator
  - app.utils.phone.normalize_phone
  - app.services.phase2.phone_discovery.PhoneDiscoveryService
"""

import sys
import os
import re

import pytest

# Ensure project root is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-unit-tests')

from app.utils.phone import normalize_phone
from app.services.phase2.russian_phone_validator import (
    RussianPhoneValidator,
    PhoneInfo,
    CARRIER_PREFIXES,
    CITY_CODES,
)
from app.services.phase2.phone_discovery import (
    PhoneDiscoveryService,
    DiscoveredPhone,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def validator():
    """Fresh RussianPhoneValidator instance."""
    return RussianPhoneValidator()


@pytest.fixture
def discovery():
    """PhoneDiscoveryService for username/email tests."""
    svc = PhoneDiscoveryService()
    yield svc
    svc.close()


# ===========================================================================
# 1. RUSSIAN MOBILE FORMAT VARIATIONS (40+ tests via parametrize)
# ===========================================================================

MOBILE_FORMAT_CASES = [
    # --- +7 prefix formats ---
    ("+7 (916) 123-45-67", "+79161234567"),
    ("+7(916)123-45-67", "+79161234567"),
    ("+7 916 123 45 67", "+79161234567"),
    ("+7-916-123-45-67", "+79161234567"),
    ("+79161234567", "+79161234567"),
    ("+7 916 1234567", "+79161234567"),
    ("+7 916 123-4567", "+79161234567"),
    ("+7 916 12-345-67", "+79161234567"),
    ("+7(916) 123-45-67", "+79161234567"),
    ("+7 (916)123-45-67", "+79161234567"),
    ("+7(916)1234567", "+79161234567"),
    ("+7-916-1234567", "+79161234567"),
    ("+7 (916) 1234567", "+79161234567"),
    ("+7916 123 45 67", "+79161234567"),
    ("+7 916-123-45-67", "+79161234567"),
    # --- 8 prefix formats ---
    ("8 (916) 123-45-67", "+79161234567"),
    ("8(916)1234567", "+79161234567"),
    ("8-916-123-45-67", "+79161234567"),
    ("8 916 123 45 67", "+79161234567"),
    ("89161234567", "+79161234567"),
    ("8 916 1234567", "+79161234567"),
    ("8(916) 123-45-67", "+79161234567"),
    ("8 (916)1234567", "+79161234567"),
    ("8(916) 1234567", "+79161234567"),
    ("8916 123 45 67", "+79161234567"),
    ("8 916-123-45-67", "+79161234567"),
    ("8-916 123-45-67", "+79161234567"),
    ("8-(916)-123-45-67", "+79161234567"),
    ("8.916.123.45.67", "+79161234567"),
    # --- 7 prefix (no plus) ---
    ("7 916 123 45 67", "+79161234567"),
    ("79161234567", "+79161234567"),
    ("7-916-123-45-67", "+79161234567"),
    ("7(916)1234567", "+79161234567"),
    ("7 (916) 123-45-67", "+79161234567"),
    # --- 10-digit (no country code) ---
    ("9161234567", "+79161234567"),
    ("916 123 45 67", "+79161234567"),
    ("916-123-45-67", "+79161234567"),
    ("(916) 123-45-67", "+79161234567"),
    ("(916)1234567", "+79161234567"),
    # --- Exotic whitespace/separator combos ---
    ("+7  916  123  45  67", "+79161234567"),
    ("8  916  123  45  67", "+79161234567"),
    ("+7\t916\t1234567", "+79161234567"),
]


class TestMobileFormatVariations:
    """1. Russian mobile format variations -- 40+ parametrized cases."""

    @pytest.mark.parametrize("raw, expected", MOBILE_FORMAT_CASES)
    def test_normalize_phone_util(self, raw, expected):
        """normalize_phone() from app.utils.phone produces canonical form."""
        assert normalize_phone(raw) == expected

    @pytest.mark.parametrize("raw, expected", MOBILE_FORMAT_CASES)
    def test_validator_normalize(self, validator, raw, expected):
        """RussianPhoneValidator.normalize() delegates and produces same result."""
        assert validator.normalize(raw) == expected


# ===========================================================================
# 2. RUSSIAN LANDLINE FORMATS (15+ tests)
# ===========================================================================

LANDLINE_FORMAT_CASES = [
    ("+7 (495) 123-45-67", "+74951234567", "Moscow"),
    ("+7 (499) 123-45-67", "+74991234567", "Moscow"),
    ("+7 (812) 123-45-67", "+78121234567", "Saint Petersburg"),
    ("8 (495) 123-45-67", "+74951234567", "Moscow"),
    ("8 (812) 123-45-67", "+78121234567", "Saint Petersburg"),
    ("+7 495 1234567", "+74951234567", "Moscow"),
    ("84951234567", "+74951234567", "Moscow"),
    ("+7(343)1234567", "+73431234567", "Yekaterinburg"),
    ("8 (383) 123-45-67", "+73831234567", "Novosibirsk"),
    ("+7 (831) 123-45-67", "+78311234567", "Nizhny Novgorod"),
    ("+7 (843) 123-45-67", "+78431234567", "Kazan"),
    ("+7 (861) 123-45-67", "+78611234567", "Krasnodar"),
    ("+7 (863) 123-45-67", "+78631234567", "Rostov-on-Don"),
    ("8-351-123-45-67", "+73511234567", "Chelyabinsk"),
    ("+7 (391) 123-45-67", "+73911234567", "Krasnoyarsk"),
    ("4951234567", "+74951234567", "Moscow"),
    ("8121234567", "+78121234567", "Saint Petersburg"),
]


class TestLandlineFormats:
    """2. Russian landline formats -- region detection."""

    @pytest.mark.parametrize("raw, expected_norm, expected_region", LANDLINE_FORMAT_CASES)
    def test_landline_normalization(self, raw, expected_norm, expected_region):
        assert normalize_phone(raw) == expected_norm

    @pytest.mark.parametrize("raw, expected_norm, expected_region", LANDLINE_FORMAT_CASES)
    def test_landline_validation(self, validator, raw, expected_norm, expected_region):
        info = validator.validate(raw)
        assert info.is_valid is True
        assert info.is_mobile is False
        assert info.format_type == "landline"
        assert info.region == expected_region


# ===========================================================================
# 3. PHONES-FROM-TEXT EXTRACTION (50+ tests)
# ===========================================================================

# Cases: (text, expected_phone_count, expected_normalized_phones)
# expected_normalized_phones is a set of normalized phone strings that must appear.
TEXT_EXTRACTION_CASES = [
    # Simple single-phone cases
    (
        "Звоните по номеру +7 916 123 45 67 в рабочее время",
        1, {"+79161234567"},
    ),
    (
        "Мой номер 89161234567, пишите в WhatsApp",
        1, {"+79161234567"},
    ),
    (
        "Связь: тел. +7(916)123-45-67, email: ivan@mail.ru",
        1, {"+79161234567"},
    ),
    (
        "Для заказов: 8 800 123 45 67",
        1, {"+78001234567"},
    ),
    (
        "WhatsApp/Telegram: +79161234567",
        1, {"+79161234567"},
    ),
    (
        "Тел.: 8 916 123-45-67 (с 9 до 18)",
        1, {"+79161234567"},
    ),
    (
        "Звонить сюда: +7-903-555-12-34",
        1, {"+79035551234"},
    ),
    (
        "Принимаю заказы по телефону 8(926)777-88-99",
        1, {"+79267778899"},
    ),
    (
        "Мой мобильный: +7 977 111 22 33",
        1, {"+79771112233"},
    ),
    (
        "Пишите по номеру 89651112233 в Viber",
        1, {"+79651112233"},
    ),
    (
        "Контакт для связи 8-916-000-11-22",
        1, {"+79160001122"},
    ),
    (
        "Телефон офиса: +7(495)777-88-99",
        1, {"+74957778899"},
    ),
    (
        "Факс: +7(812)333-44-55, моб: +7(921)666-77-88",
        2, {"+78123334455", "+79216667788"},
    ),
    (
        "Позвоните мне на 8 905 123-45-67 или +7 916 987-65-43",
        2, {"+79051234567", "+79169876543"},
    ),
    (
        "Рабочий: 8-495-123-45-67\nМобильный: +7-916-987-65-43",
        2, {"+74951234567", "+79169876543"},
    ),
    (
        "+7 916 123 45 67 / +7 916 987 65 43",
        2, {"+79161234567", "+79169876543"},
    ),
    (
        "8(916)123-45-67; 8(916)987-65-43",
        2, {"+79161234567", "+79169876543"},
    ),
    (
        "Номера для связи: +7(903)111-22-33, +7(926)444-55-66, +7(977)777-88-99",
        3, {"+79031112233", "+79264445566", "+79777778899"},
    ),
    # No phones
    (
        "Нет телефонов в этом тексте",
        0, set(),
    ),
    (
        "Привет, как дела? Погода сегодня хорошая.",
        0, set(),
    ),
    (
        "Мой id: 12345, номер заказа 67890",
        0, set(),
    ),
    (
        "",
        0, set(),
    ),
    # Deduplication
    (
        "+79161234567 and 89161234567",
        1, {"+79161234567"},
    ),
    (
        "+7 (916) 123-45-67, повторяю: 8-916-123-45-67",
        1, {"+79161234567"},
    ),
    # Phones surrounded by Russian context
    (
        "Уважаемые клиенты! Наш новый номер горячей линии: +7(495)789-01-23. Ждём ваших звонков!",
        1, {"+74957890123"},
    ),
    (
        "Запись на приём по телефону 8 916 222-33-44 с понедельника по пятницу с 9:00 до 18:00",
        1, {"+79162223344"},
    ),
    (
        "Доставка осуществляется по Москве и МО. Заказ: +7(926)555-66-77 (звонок бесплатный)",
        1, {"+79265556677"},
    ),
    (
        "Менеджер Анна: 8-916-111-22-33\nМенеджер Иван: 8-926-444-55-66\nОфис: 8(495)777-88-99",
        3, {"+79161112233", "+79264445566", "+74957778899"},
    ),
    (
        "По вопросам рекламы: +7 916 321-00-00, по вопросам сотрудничества: +7 903 654-00-00",
        2, {"+79163210000", "+79036540000"},
    ),
    # Phone buried in long text
    (
        "А" * 200 + " Телефон: +7 916 123 45 67 " + "Б" * 200,
        1, {"+79161234567"},
    ),
    # Multiple separators -- regex only supports single separator, so triple dashes won't match
    (
        "Наберите 8-916-123-45-67 прямо сейчас!",
        1, {"+79161234567"},
    ),
    # Phone after emoji-like text
    (
        "Звоните :) +7 916 999-00-11",
        1, {"+79169990011"},
    ),
    # Phone in VK-style contact info
    (
        "моб.тел: +79161234567 | раб.тел: +74951234567",
        2, {"+79161234567", "+74951234567"},
    ),
    # Only landline
    (
        "Городской: 8(495)111-22-33",
        1, {"+74951112233"},
    ),
    # Multiple mobile same prefix
    (
        "Наши менеджеры: 8-916-000-00-01, 8-916-000-00-02, 8-916-000-00-03",
        3, {"+79160000001", "+79160000002", "+79160000003"},
    ),
    # Phone with "тел." prefix
    (
        "тел. 89161234567",
        1, {"+79161234567"},
    ),
    # Phone in angle brackets
    (
        "Контакт: <+79161234567>",
        1, {"+79161234567"},
    ),
    # Mixed Latin and Cyrillic around phone
    (
        "Call me: +7 916 123 45 67 (mobile), email: test@test.com",
        1, {"+79161234567"},
    ),
    # Phone in multiline text
    (
        "Адрес: ул. Ленина, д. 1\nТелефон: +7 916 123-45-67\nЧасы работы: 9-18",
        1, {"+79161234567"},
    ),
    # Two phones on same line, comma-separated
    (
        "+79161234567, +79261234567",
        2, {"+79161234567", "+79261234567"},
    ),
    # Phone with "tel:" URI prefix
    (
        "tel:+79161234567",
        1, {"+79161234567"},
    ),
    # Phone after URL
    (
        "Сайт: https://example.com Телефон: 89161234567",
        1, {"+79161234567"},
    ),
    # Russian 8-800 toll-free
    (
        "Горячая линия: 8 800 555 00 00",
        1, {"+78005550000"},
    ),
    # Tab-separated phones
    (
        "+79161234567\t+79261234567",
        2, {"+79161234567", "+79261234567"},
    ),
    # Phone with leading/trailing whitespace
    (
        "   +79161234567   ",
        1, {"+79161234567"},
    ),
    # Single-line multiple phones, pipe separated
    (
        "+7(916)111-22-33 | +7(926)444-55-66 | +7(903)777-88-99",
        3, {"+79161112233", "+79264445566", "+79037778899"},
    ),
    # Cyrillic keywords preceding phone
    (
        "сот: 89161234567",
        1, {"+79161234567"},
    ),
    (
        "Контактный телефон: 8 926 111-22-33 (Иван Петрович)",
        1, {"+79261112233"},
    ),
]


class TestTextExtraction:
    """3. Phones-from-text extraction -- 50+ parametrized cases."""

    @pytest.mark.parametrize("text, expected_count, expected_phones", TEXT_EXTRACTION_CASES)
    def test_extract_phones(self, validator, text, expected_count, expected_phones):
        results = validator.extract_phones(text)
        assert len(results) == expected_count
        found_normalized = {r.normalized for r in results}
        assert found_normalized == expected_phones

    def test_extract_phones_returns_phone_info(self, validator):
        """Each result should be a PhoneInfo dataclass."""
        results = validator.extract_phones("+79161234567")
        assert len(results) == 1
        info = results[0]
        assert isinstance(info, PhoneInfo)
        assert info.is_valid is True

    def test_extract_long_russian_text(self, validator):
        """Phone buried among 500+ characters of Russian text."""
        filler = "Компания ООО Ромашка занимается производством и реализацией товаров. " * 8
        text = filler + "Телефон для справок: +7 903 222 33 44. " + filler
        results = validator.extract_phones(text)
        assert len(results) == 1
        assert results[0].normalized == "+79032223344"


# ===========================================================================
# 4. USERNAME PHONE EXTRACTION (15+ tests)
# ===========================================================================

USERNAME_CASES = [
    # (list of usernames, expected count, expected set of normalized +7... numbers)
    # Username IS a phone
    (["89161234567"], 1, {"+79161234567"}),
    (["79161234567"], 1, {"+79161234567"}),
    (["9161234567"], 1, {"+79161234567"}),
    # Username with prefix
    (["id79161234567"], 1, {"+79161234567"}),
    (["id89161234567"], 1, {"+79161234567"}),
    # Phone at end of username
    (["ivan_9161234567"], 1, {"+79161234567"}),
    # No digits
    (["ivan_petrov"], 0, set()),
    (["durov"], 0, set()),
    # Short digits - not a phone
    (["ivan123"], 0, set()),
    # Letters mixed (no clean phone)
    (["abc123def456"], 0, set()),
    # Multiple usernames, one with phone
    (["durov", "89161234567", "test_user"], 1, {"+79161234567"}),
    # Multiple usernames both phones
    (["89161234567", "89261234567"], 2, {"+79161234567", "+79261234567"}),
    # Pure 10-digit starting with 9
    (["9031234567"], 1, {"+79031234567"}),
    # 11 digits starting with 8
    (["89261112233"], 1, {"+79261112233"}),
    # 11 digits starting with 7
    (["79261112233"], 1, {"+79261112233"}),
    # Empty list
    ([], 0, set()),
    # Username with 10 digits not starting with 9 -- matched by USERNAME_PHONE_PATTERNS \d{10}
    (["4951234567"], 1, {"+74951234567"}),
]


class TestUsernamePhoneExtraction:
    """4. Username phone extraction via PhoneDiscoveryService._extract_from_usernames."""

    @pytest.mark.parametrize("usernames, expected_count, expected_phones", USERNAME_CASES)
    def test_extract_from_usernames(self, discovery, usernames, expected_count, expected_phones):
        results = discovery._extract_from_usernames(usernames)
        found_numbers = {r.number for r in results}
        # Check expected phones are present (there might be duplicates from multiple patterns)
        assert expected_phones.issubset(found_numbers)
        if expected_count == 0:
            assert len(results) == 0

    def test_username_result_is_discovered_phone(self, discovery):
        results = discovery._extract_from_usernames(["89161234567"])
        assert len(results) >= 1
        assert isinstance(results[0], DiscoveredPhone)
        assert results[0].source.startswith("Username pattern")

    def test_username_confidence_is_set(self, discovery):
        results = discovery._extract_from_usernames(["89161234567"])
        assert len(results) >= 1
        assert results[0].confidence in ("high", "medium", "low")


# ===========================================================================
# 5. EMAIL-TO-PHONE EXTRACTION (10+ tests)
# ===========================================================================

EMAIL_CASES = [
    # (emails, expected_count, expected_phones)
    (["9161234567@mail.ru"], 1, {"+79161234567"}),
    (["79161234567@gmail.com"], 1, {"+79161234567"}),
    (["89161234567@yandex.ru"], 1, {"+79161234567"}),
    (["ivan.petrov@mail.ru"], 0, set()),
    (["test@test.com"], 0, set()),
    ([], 0, set()),
    (["9261112233@inbox.ru"], 1, {"+79261112233"}),
    (["79031234567@rambler.ru"], 1, {"+79031234567"}),
    # Not a phone -- 8 digits
    (["12345678@mail.ru"], 0, set()),
    # No @ sign -- skip
    (["not-an-email"], 0, set()),
    # Mix of phone-email and normal email
    (["9161234567@mail.ru", "john@gmail.com"], 1, {"+79161234567"}),
    # Multiple phone-emails
    (["9161234567@mail.ru", "9261234567@yandex.ru"], 2, {"+79161234567", "+79261234567"}),
]


class TestEmailPhoneExtraction:
    """5. Email-to-phone extraction via PhoneDiscoveryService._extract_from_emails."""

    @pytest.mark.parametrize("emails, expected_count, expected_phones", EMAIL_CASES)
    def test_extract_from_emails(self, discovery, emails, expected_count, expected_phones):
        results = discovery._extract_from_emails(emails)
        assert len(results) == expected_count
        found = {r.number for r in results}
        assert found == expected_phones

    def test_email_result_is_discovered_phone(self, discovery):
        results = discovery._extract_from_emails(["9161234567@mail.ru"])
        assert len(results) == 1
        assert isinstance(results[0], DiscoveredPhone)
        assert "Email local part" in results[0].source

    def test_email_confidence(self, discovery):
        results = discovery._extract_from_emails(["9161234567@mail.ru"])
        assert results[0].confidence == "medium"


# ===========================================================================
# 6. CARRIER DETECTION (20+ tests)
# ===========================================================================

CARRIER_CASES = [
    # (prefix, expected_carrier)
    # MTS: 910-919, 980-989
    ("910", "MTS"),
    ("911", "MTS"),
    ("916", "MTS"),
    ("919", "MTS"),
    ("980", "MTS"),
    ("989", "MTS"),
    # Beeline: 900-909, 960-969
    ("900", "Beeline"),
    ("903", "Beeline"),
    ("909", "Beeline"),
    ("960", "Beeline"),
    ("965", "Beeline"),
    ("969", "Beeline"),
    # Megafon: 920-939
    ("920", "Megafon"),
    ("926", "Megafon"),
    ("929", "Megafon"),
    ("930", "Megafon"),
    ("935", "Megafon"),
    ("939", "Megafon"),
    # Tele2: 950-959, 977-978, 999
    ("950", "Tele2"),
    ("955", "Tele2"),
    ("977", "Tele2"),
    ("978", "Tele2"),
    ("999", "Tele2"),
    # Yota: 990-998
    ("990", "Yota"),
    ("991", "Yota"),
    ("995", "Yota"),
    ("998", "Yota"),
    # Rostelecom: 940-949
    ("940", "Rostelecom"),
    ("945", "Rostelecom"),
    ("949", "Rostelecom"),
]


class TestCarrierDetection:
    """6. Carrier detection -- one test per prefix."""

    @pytest.mark.parametrize("prefix, expected_carrier", CARRIER_CASES)
    def test_carrier_hint(self, validator, prefix, expected_carrier):
        phone = f"+7{prefix}1234567"
        info = validator.validate(phone)
        assert info.is_valid is True
        assert info.is_mobile is True
        assert info.carrier_hint == expected_carrier

    def test_unknown_carrier_prefix(self, validator):
        """A valid mobile prefix not assigned to any carrier returns fallback hint."""
        # 970 is not listed in CARRIER_PREFIXES
        info = validator.validate("+79701234567")
        assert info.is_valid is True
        assert info.is_mobile is True
        assert info.carrier_hint == "Unknown (possibly MNP)"

    def test_landline_no_carrier(self, validator):
        """Landline numbers should have no carrier hint."""
        info = validator.validate("+74951234567")
        assert info.carrier_hint is None


# ===========================================================================
# 7. DISPLAY FORMATTING (10+ tests)
# ===========================================================================

DISPLAY_FORMAT_CASES = [
    ("+79161234567", "+7 (916) 123-45-67"),
    ("89161234567", "+7 (916) 123-45-67"),
    ("8 (916) 123-45-67", "+7 (916) 123-45-67"),
    ("+7-916-123-45-67", "+7 (916) 123-45-67"),
    ("+7 916 123 45 67", "+7 (916) 123-45-67"),
    ("9161234567", "+7 (916) 123-45-67"),
    ("79161234567", "+7 (916) 123-45-67"),
    ("+7(916)1234567", "+7 (916) 123-45-67"),
    # Landline
    ("+74951234567", "+7 (495) 123-45-67"),
    ("84951234567", "+7 (495) 123-45-67"),
    ("8 (495) 123-45-67", "+7 (495) 123-45-67"),
    # Different mobile operators
    ("+79031234567", "+7 (903) 123-45-67"),
    ("+79261234567", "+7 (926) 123-45-67"),
    ("+79771234567", "+7 (977) 123-45-67"),
]


class TestDisplayFormatting:
    """7. Display formatting -- all must produce +7 (XXX) XXX-XX-XX."""

    @pytest.mark.parametrize("raw, expected_display", DISPLAY_FORMAT_CASES)
    def test_format_display(self, raw, expected_display):
        result = RussianPhoneValidator.format_display(raw)
        assert result == expected_display

    @pytest.mark.parametrize("raw, expected_display", DISPLAY_FORMAT_CASES)
    def test_validate_display_format(self, validator, raw, expected_display):
        """PhoneInfo.display_format matches format_display output."""
        info = validator.validate(raw)
        assert info.display_format == expected_display


# ===========================================================================
# 8. VARIANT GENERATION (10+ tests)
# ===========================================================================

class TestVariantGeneration:
    """8. generate_variants() should return multiple format variants."""

    def test_variant_count(self, validator):
        """Valid phone should generate at least 8 distinct variants."""
        variants = validator.generate_variants("+79161234567")
        assert len(variants) >= 8

    def test_variants_contain_plus7_compact(self, validator):
        variants = validator.generate_variants("+79161234567")
        assert "+79161234567" in variants

    def test_variants_contain_eight_compact(self, validator):
        variants = validator.generate_variants("+79161234567")
        assert "89161234567" in variants

    def test_variants_contain_seven_compact(self, validator):
        variants = validator.generate_variants("+79161234567")
        assert "79161234567" in variants

    def test_variants_contain_ten_digit(self, validator):
        variants = validator.generate_variants("+79161234567")
        assert "9161234567" in variants

    def test_variants_contain_display_format(self, validator):
        variants = validator.generate_variants("+79161234567")
        assert "+7 (916) 123-45-67" in variants

    def test_variants_contain_dash_format(self, validator):
        variants = validator.generate_variants("+79161234567")
        assert "+7-916-123-45-67" in variants

    def test_variants_contain_space_format(self, validator):
        variants = validator.generate_variants("+79161234567")
        assert "+7 916 123 45 67" in variants

    def test_variants_contain_eight_display(self, validator):
        variants = validator.generate_variants("+79161234567")
        assert "8 (916) 123-45-67" in variants

    def test_invalid_phone_returns_original(self, validator):
        """Invalid phone should return list with just the original."""
        variants = validator.generate_variants("12345")
        assert variants == ["12345"]

    def test_variants_all_unique(self, validator):
        """All returned variants must be unique."""
        variants = validator.generate_variants("+79161234567")
        assert len(variants) == len(set(variants))

    def test_variants_from_eight_format(self, validator):
        """Input in 8-format should produce same variants as +7 format."""
        v1 = set(validator.generate_variants("+79161234567"))
        v2 = set(validator.generate_variants("89161234567"))
        assert v1 == v2


# ===========================================================================
# 9. EDGE CASES (10+ tests)
# ===========================================================================

class TestEdgeCases:
    """9. Edge cases for normalization, validation, and extraction."""

    def test_empty_string_normalize(self):
        assert normalize_phone("") == ""

    def test_none_normalize(self):
        assert normalize_phone(None) == ""

    def test_very_short_number(self, validator):
        info = validator.validate("12")
        assert info.is_valid is False

    def test_very_long_number(self, validator):
        info = validator.validate("+7916123456700000")
        assert info.is_valid is False

    def test_all_zeros(self, validator):
        info = validator.validate("00000000000")
        assert info.is_valid is False

    def test_letters_mixed_in(self):
        """Letters mixed with digits -- can't normalize to valid phone."""
        result = normalize_phone("8abc916def1234567")
        # Stripping non-digits gives 89161234567 (11 digits starting with 8)
        assert result == "+79161234567"

    def test_non_phone_text(self):
        assert normalize_phone("hello world") == "hello world"

    def test_single_digit(self, validator):
        info = validator.validate("7")
        assert info.is_valid is False

    def test_twelve_digits(self, validator):
        """12 digits -- too long for Russian number."""
        info = validator.validate("791612345678")
        assert info.is_valid is False

    def test_nine_digits(self, validator):
        """9 digits -- too short for Russian number."""
        info = validator.validate("916123456")
        assert info.is_valid is False

    def test_extract_from_empty_text(self, validator):
        assert validator.extract_phones("") == []

    def test_normalize_key_last_ten_digits(self, discovery):
        """_normalize_key keeps only last 10 digits."""
        assert discovery._normalize_key("+79161234567") == "9161234567"
        assert discovery._normalize_key("89161234567") == "9161234567"
        assert discovery._normalize_key("9161234567") == "9161234567"

    def test_normalize_key_strips_non_digits(self, discovery):
        assert discovery._normalize_key("+7 (916) 123-45-67") == "9161234567"

    def test_is_russian_mobile_true(self):
        assert RussianPhoneValidator.is_russian_mobile("+79161234567") is True
        assert RussianPhoneValidator.is_russian_mobile("89161234567") is True
        assert RussianPhoneValidator.is_russian_mobile("9161234567") is True

    def test_is_russian_mobile_false_landline(self):
        assert RussianPhoneValidator.is_russian_mobile("+74951234567") is False

    def test_is_russian_mobile_false_short(self):
        assert RussianPhoneValidator.is_russian_mobile("12345") is False

    def test_international_non_russian_returned_as_is(self):
        """Non-Russian international number returned unchanged."""
        result = normalize_phone("+1-202-555-0123")
        assert result == "+1-202-555-0123"

    def test_validate_invalid_returns_original_as_normalized(self, validator):
        """When phone is invalid, normalized field contains the original string."""
        info = validator.validate("shortnum")
        assert info.is_valid is False
        assert info.normalized == "shortnum"
        assert info.display_format == "shortnum"


# ===========================================================================
# 10. ADDITIONAL CROSS-CUTTING TESTS
# ===========================================================================

class TestCrossCutting:
    """Additional tests ensuring consistency between modules."""

    def test_validator_normalize_matches_util(self):
        """RussianPhoneValidator.normalize delegates to app.utils.phone.normalize_phone."""
        phone = "+7 (926) 555-66-77"
        assert RussianPhoneValidator.normalize(phone) == normalize_phone(phone)

    def test_validate_returns_correct_dataclass_fields(self, validator):
        info = validator.validate("+79161234567")
        assert hasattr(info, 'original')
        assert hasattr(info, 'normalized')
        assert hasattr(info, 'is_valid')
        assert hasattr(info, 'is_mobile')
        assert hasattr(info, 'carrier_hint')
        assert hasattr(info, 'region')
        assert hasattr(info, 'format_type')
        assert hasattr(info, 'display_format')

    def test_discovered_phone_fields(self, discovery):
        results = discovery._extract_from_emails(["9161234567@mail.ru"])
        dp = results[0]
        assert hasattr(dp, 'number')
        assert hasattr(dp, 'source')
        assert hasattr(dp, 'confidence')
        assert hasattr(dp, 'verified')
        assert hasattr(dp, 'carrier')
        assert hasattr(dp, 'region')
        assert hasattr(dp, 'telegram_url')

    def test_extract_phones_all_valid(self, validator):
        """Every phone returned by extract_phones() must have is_valid=True."""
        text = "+79161234567 8(926)111-22-33 +7 903 444 55 66"
        results = validator.extract_phones(text)
        for info in results:
            assert info.is_valid is True

    def test_city_codes_dict_not_empty(self):
        """CITY_CODES should contain known entries."""
        assert '495' in CITY_CODES
        assert '812' in CITY_CODES
        assert CITY_CODES['495'] == 'Moscow'

    def test_carrier_prefixes_dict_not_empty(self):
        """CARRIER_PREFIXES should contain all major carriers."""
        assert 'MTS' in CARRIER_PREFIXES
        assert 'Beeline' in CARRIER_PREFIXES
        assert 'Megafon' in CARRIER_PREFIXES
        assert 'Tele2' in CARRIER_PREFIXES
        assert 'Yota' in CARRIER_PREFIXES
        assert 'Rostelecom' in CARRIER_PREFIXES
