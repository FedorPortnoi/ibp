"""
Russian Phone Number Validator
==============================
Validates format and identifies carrier for Russian phone numbers.
Provides normalization, validation, and carrier hints.

Based on: https://en.wikipedia.org/wiki/Telephone_numbers_in_Russia
Note: MNP (Mobile Number Portability) since 2013 means prefix != current carrier
"""

import re
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass


@dataclass
class PhoneInfo:
    """Information about a validated phone number."""
    original: str
    normalized: str  # +7XXXXXXXXXX format
    is_valid: bool
    is_mobile: bool
    carrier_hint: Optional[str]  # Original carrier (may have changed via MNP)
    region: Optional[str]  # For landlines
    format_type: str  # 'mobile', 'landline', 'unknown'
    display_format: str  # +7 (XXX) XXX-XX-XX


# Russian mobile operator prefixes (approximate - MNP means these aren't definitive)
# Source: https://www.itu.int/dms_pub/itu-t/oth/02/02/T02020000AD0004PDFE.pdf
CARRIER_PREFIXES = {
    'MTS': [
        '910', '911', '912', '913', '914', '915', '916', '917', '918', '919',
        '980', '981', '982', '983', '984', '985', '986', '987', '988', '989'
    ],
    'Beeline': [
        '900', '901', '902', '903', '904', '905', '906', '907', '908', '909',
        '960', '961', '962', '963', '964', '965', '966', '967', '968', '969'
    ],
    'Megafon': [
        '920', '921', '922', '923', '924', '925', '926', '927', '928', '929',
        '930', '931', '932', '933', '934', '935', '936', '937', '938', '939'
    ],
    'Tele2': [
        '950', '951', '952', '953', '955', '956', '957', '958', '959',
        '977', '978', '999'
    ],
    'Yota': [
        '990', '991', '992', '993', '994', '995', '996', '997', '998'
    ],
    'Rostelecom': [
        '940', '941', '942', '943', '944', '945', '946', '947', '948', '949'
    ],
    'Satellite': [
        '954'  # Reserved for satellite operators
    ],
}

# Major Russian city area codes
CITY_CODES = {
    '495': 'Moscow',
    '499': 'Moscow',
    '498': 'Moscow Oblast',
    '812': 'Saint Petersburg',
    '813': 'Leningrad Oblast',
    '831': 'Nizhny Novgorod',
    '843': 'Kazan',
    '846': 'Samara',
    '861': 'Krasnodar',
    '863': 'Rostov-on-Don',
    '342': 'Perm',
    '343': 'Yekaterinburg',
    '351': 'Chelyabinsk',
    '381': 'Omsk',
    '383': 'Novosibirsk',
    '384': 'Kemerovo',
    '385': 'Barnaul',
    '391': 'Krasnoyarsk',
    '395': 'Irkutsk',
    '401': 'Kaliningrad',
    '411': 'Sakha Republic (Yakutia)',
    '421': 'Khabarovsk',
    '423': 'Vladivostok',
    '473': 'Voronezh',
    '482': 'Pskov',
    '484': 'Kaluga',
    '485': 'Yaroslavl',
    '486': 'Orel',
    '487': 'Tula',
    '491': 'Ryazan',
    '492': 'Vladimir',
    '493': 'Ivanovo',
    '494': 'Kostroma',
    '496': 'Moscow Oblast',
    '831': 'Nizhny Novgorod',
    '833': 'Chuvash Republic',
    '834': 'Penza',
    '835': 'Saransk (Mordovia)',
    '836': 'Yoshkar-Ola (Mari El)',
    '841': 'Saratov',
    '842': 'Ulyanovsk',
    '844': 'Volgograd',
    '845': 'Saratov Oblast',
    '847': 'Kalmykia',
    '848': 'Astrakhan',
    '851': 'Orenburg',
    '855': 'Naberezhnye Chelny',
    '862': 'Sochi',
    '865': 'Stavropol',
    '866': 'Nalchik (Kabardino-Balkaria)',
    '867': 'Vladikavkaz (North Ossetia)',
    '871': 'Chechnya',
    '872': 'Dagestan',
    '873': 'Ingushetia',
    '877': 'Adygea',
    '878': 'Karachay-Cherkessia',
    '879': 'Mineralnye Vody',
}


class RussianPhoneValidator:
    """Validate and analyze Russian phone numbers."""

    # Regex patterns for finding phones in text
    EXTRACTION_PATTERNS = [
        r'\+7[\s\-\(]?(\d{3})[\s\-\)]?(\d{3})[\s\-]?(\d{2})[\s\-]?(\d{2})',
        r'8[\s\-\(]?(\d{3})[\s\-\)]?(\d{3})[\s\-]?(\d{2})[\s\-]?(\d{2})',
        r'\+7(\d{10})',
        r'8(\d{10})',
    ]

    # Compiled pattern for validation
    VALID_PATTERN = re.compile(r'^\+?[78]?\d{10,11}$')

    @staticmethod
    def normalize(phone: str) -> str:
        """
        Normalize phone to +7XXXXXXXXXX format.

        Args:
            phone: Phone number in any format

        Returns:
            Normalized phone or original if can't normalize
        """
        if not phone:
            return ''

        # Remove all non-digits
        digits = re.sub(r'\D', '', phone)

        # Handle different formats
        if len(digits) == 11:
            if digits.startswith('8'):
                return '+7' + digits[1:]
            elif digits.startswith('7'):
                return '+' + digits
        elif len(digits) == 10:
            # Assume Russian mobile starting with 9
            if digits.startswith('9'):
                return '+7' + digits
            else:
                return '+7' + digits

        return phone  # Return original if can't normalize

    @staticmethod
    def format_display(phone: str) -> str:
        """
        Format phone for display: +7 (XXX) XXX-XX-XX

        Args:
            phone: Phone number (will be normalized first)

        Returns:
            Formatted phone string
        """
        normalized = RussianPhoneValidator.normalize(phone)
        digits = re.sub(r'\D', '', normalized)

        if len(digits) == 11 and digits.startswith('7'):
            return f"+7 ({digits[1:4]}) {digits[4:7]}-{digits[7:9]}-{digits[9:11]}"
        elif len(digits) == 11:
            return f"+{digits[0]} ({digits[1:4]}) {digits[4:7]}-{digits[7:9]}-{digits[9:11]}"

        return phone

    def validate(self, phone: str) -> PhoneInfo:
        """
        Validate a Russian phone number and extract metadata.

        Args:
            phone: Phone number in any format

        Returns:
            PhoneInfo with validation results and metadata
        """
        normalized = self.normalize(phone)
        digits_only = re.sub(r'\D', '', normalized)

        # Check if valid Russian number (11 digits starting with 7)
        is_valid = (
            len(digits_only) == 11 and
            digits_only.startswith('7')
        )

        # Determine if mobile (9XX prefix after country code)
        is_mobile = is_valid and digits_only[1] == '9'

        # Get carrier hint for mobile numbers
        carrier_hint = None
        region = None
        format_type = 'unknown'

        if is_valid:
            prefix = digits_only[1:4]  # e.g., '910' for mobile, '495' for landline

            if is_mobile:
                format_type = 'mobile'
                for carrier, prefixes in CARRIER_PREFIXES.items():
                    if prefix in prefixes:
                        carrier_hint = carrier
                        break
                if not carrier_hint:
                    carrier_hint = 'Unknown (possibly MNP)'
            else:
                format_type = 'landline'
                if prefix in CITY_CODES:
                    region = CITY_CODES[prefix]

        return PhoneInfo(
            original=phone,
            normalized=normalized if is_valid else phone,
            is_valid=is_valid,
            is_mobile=is_mobile,
            carrier_hint=carrier_hint,
            region=region,
            format_type=format_type,
            display_format=self.format_display(phone) if is_valid else phone
        )

    def extract_phones(self, text: str) -> List[PhoneInfo]:
        """
        Extract and validate all Russian phone numbers from text.

        Args:
            text: Text to search for phone numbers

        Returns:
            List of PhoneInfo for each found phone
        """
        # Patterns to find phones in text (capture groups optional)
        patterns = [
            r'\+7[\s\-\(]?\d{3}[\s\-\)]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}',
            r'8[\s\-\(]?\d{3}[\s\-\)]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}',
            r'\+7\d{10}',
            r'8\d{10}',
        ]

        found_phones = []
        seen_normalized = set()

        for pattern in patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                info = self.validate(match)
                if info.is_valid and info.normalized not in seen_normalized:
                    seen_normalized.add(info.normalized)
                    found_phones.append(info)

        return found_phones

    def generate_variants(self, phone: str) -> List[str]:
        """
        Generate different format variants of a phone number.
        Useful for searching databases that may store in different formats.

        Args:
            phone: Phone number to generate variants for

        Returns:
            List of format variants
        """
        info = self.validate(phone)
        if not info.is_valid:
            return [phone]

        digits = re.sub(r'\D', '', info.normalized)

        variants = [
            info.normalized,  # +79991234567
            f"+7 {digits[1:4]} {digits[4:7]} {digits[7:9]} {digits[9:]}",  # +7 999 123 45 67
            f"+7 ({digits[1:4]}) {digits[4:7]}-{digits[7:9]}-{digits[9:]}",  # +7 (999) 123-45-67
            f"+7-{digits[1:4]}-{digits[4:7]}-{digits[7:9]}-{digits[9:]}",  # +7-999-123-45-67
            f"8{digits[1:]}",  # 89991234567
            f"8 {digits[1:4]} {digits[4:7]} {digits[7:9]} {digits[9:]}",  # 8 999 123 45 67
            f"8 ({digits[1:4]}) {digits[4:7]}-{digits[7:9]}-{digits[9:]}",  # 8 (999) 123-45-67
            f"8-{digits[1:4]}-{digits[4:7]}-{digits[7:9]}-{digits[9:]}",  # 8-999-123-45-67
            f"7{digits[1:]}",  # 79991234567
            digits[1:],  # 9991234567 (without country code)
        ]

        return list(set(variants))

    @staticmethod
    def is_russian_mobile(phone: str) -> bool:
        """Quick check if phone appears to be Russian mobile."""
        digits = re.sub(r'\D', '', phone)
        return (
            len(digits) in (10, 11) and
            (digits.startswith('79') or digits.startswith('89') or digits.startswith('9'))
        )


def validate_phone(phone: str) -> PhoneInfo:
    """Convenience function to validate a single phone."""
    validator = RussianPhoneValidator()
    return validator.validate(phone)


def extract_phones_from_text(text: str) -> List[PhoneInfo]:
    """Convenience function to extract phones from text."""
    validator = RussianPhoneValidator()
    return validator.extract_phones(text)


def normalize_phone(phone: str) -> str:
    """Convenience function to normalize a phone."""
    return RussianPhoneValidator.normalize(phone)
