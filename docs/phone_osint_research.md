# Phone Number OSINT Research Summary

This document summarizes legitimate phone number OSINT tools and methods for integration into the IBP platform.

## 1. PhoneInfoga Analysis

**Repository:** [github.com/sundowndev/phoneinfoga](https://github.com/sundowndev/phoneinfoga)

**Status:** Stable but unmaintained (as of 2025)

### Architecture
PhoneInfoga is written in Go and uses Google's [libphonenumber](https://github.com/nyaruka/phonenumbers) library for phone number parsing.

### Available Scanners

#### 1.1 Local Scanner (No API Required)
Extracts metadata from the phone number itself using offline libphonenumber data:
- **Valid**: Whether the number format is valid
- **RawLocal**: Number in raw local format (e.g., `9261234567`)
- **Local**: Formatted local number (e.g., `926 123-45-67`)
- **E164**: International format (e.g., `+79261234567`)
- **International**: Without plus (e.g., `79261234567`)
- **CountryCode**: Numeric code (e.g., `7` for Russia)
- **Country**: ISO code (e.g., `RU`)
- **Carrier**: Carrier from libphonenumber database (may be outdated due to MNP)

#### 1.2 Numverify Scanner (API Required)
Requires `NUMVERIFY_API_KEY` from [apilayer.com](https://apilayer.com/marketplace/number_verification-api):
- Valid, Number, LocalFormat, InternationalFormat
- CountryPrefix, CountryCode, CountryName
- **Location**: City/region
- **Carrier**: Mobile operator
- **LineType**: mobile, landline, voip, etc.

**Free tier:** 100 requests/month

#### 1.3 Google Search Scanner (No API)
Generates Google Dork URLs for manual investigation:
- **Social Media**: Facebook, Twitter, LinkedIn, Instagram, VK
- **Disposable Providers**: 20+ SMS reception services
- **Reputation**: Spam/fraud reporting sites
- **Individuals**: Pastebin, sync.me, numinfo.net
- **General**: Document search (PDF, DOC, XLS, etc.)

#### 1.4 OVH Scanner (No API)
Checks if number is from OVH Telecom VoIP service:
- **Supported countries only**: FR (+33), BE (+32), UK (+44), ES (+34), CH (+41)
- **NOT supported for Russia (+7)**

### Python Integration
PhoneInfoga is Go-based, so integration options:
1. **Subprocess call**: `phoneinfoga scan -n +79261234567`
2. **REST API**: Run `phoneinfoga serve` and call HTTP endpoints
3. **Replicate logic in Python** using `phonenumbers` library

---

## 2. Ignorant Analysis

**Repository:** [github.com/megadose/ignorant](https://github.com/megadose/ignorant)

### What It Does
Checks if a phone number is registered on various platforms WITHOUT alerting the target.

### Supported Platforms
| Platform  | Domain         | Method   | Rate Limit Risk |
|-----------|----------------|----------|-----------------|
| Amazon    | amazon.com     | login    | Low             |
| Instagram | instagram.com  | register | Low             |
| Snapchat  | snapchat.com   | register | Low             |

### How It Works

**Instagram Module:**
```python
# Uses Instagram's internal API
USERS_LOOKUP_URL = 'https://i.instagram.com/api/v1/users/lookup/'
# Signs request with IG_SIG_KEY
# Checks if "No users found" in response
```

**Snapchat Module:**
```python
# Uses registration validation endpoint
# POST to https://accounts.snapchat.com/accounts/validate_phone_number
# Checks if status_code == "TAKEN_NUMBER"
```

**Amazon Module:**
```python
# Uses login page form submission
# Checks for "auth-password-missing-alert" div (account exists)
```

### Python Integration Example
```python
import trio
import httpx
from ignorant.modules.social_media.instagram import instagram

async def check_phone_instagram(phone: str, country_code: str) -> dict:
    """Check if phone is registered on Instagram"""
    client = httpx.AsyncClient(timeout=10)
    out = []

    await instagram(phone, country_code, client, out)

    await client.aclose()
    return out[0] if out else None

# Usage
# result = trio.run(lambda: check_phone_instagram("9261234567", "7"))
# result['exists'] = True/False
```

### Russian Support
- Country code "7" maps to "RU" in Snapchat's lookup
- Instagram and Amazon work with Russian numbers

---

## 3. Python-Phonenumbers Library

**Repository:** [github.com/daviddrysdale/python-phonenumbers](https://github.com/daviddrysdale/python-phonenumbers)

### Installation
```bash
pip install phonenumbers
```

### Core Functionality

```python
import phonenumbers
from phonenumbers import carrier, geocoder, timezone

def analyze_phone_number(phone_string: str) -> dict:
    """
    Analyze a phone number and extract all available metadata.

    Args:
        phone_string: Phone number with country code (e.g., "+79261234567")

    Returns:
        Dictionary with all extracted information
    """
    try:
        # Parse the number
        parsed = phonenumbers.parse(phone_string)

        return {
            # Basic info
            'valid': phonenumbers.is_valid_number(parsed),
            'possible': phonenumbers.is_possible_number(parsed),
            'country_code': parsed.country_code,
            'national_number': parsed.national_number,

            # Formatted versions
            'e164': phonenumbers.format_number(
                parsed, phonenumbers.PhoneNumberFormat.E164
            ),
            'international': phonenumbers.format_number(
                parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL
            ),
            'national': phonenumbers.format_number(
                parsed, phonenumbers.PhoneNumberFormat.NATIONAL
            ),

            # Number type
            'number_type': get_number_type_name(
                phonenumbers.number_type(parsed)
            ),

            # Carrier (may be inaccurate due to MNP)
            'carrier': carrier.name_for_number(parsed, 'ru'),

            # Location
            'location': geocoder.description_for_number(parsed, 'ru'),

            # Timezone(s)
            'timezones': list(timezone.time_zones_for_number(parsed)),

            # Region code
            'region_code': phonenumbers.region_code_for_number(parsed),
        }
    except phonenumbers.NumberParseException as e:
        return {'error': str(e), 'valid': False}


def get_number_type_name(num_type: int) -> str:
    """Convert phonenumbers type constant to string"""
    types = {
        phonenumbers.PhoneNumberType.FIXED_LINE: 'fixed_line',
        phonenumbers.PhoneNumberType.MOBILE: 'mobile',
        phonenumbers.PhoneNumberType.FIXED_LINE_OR_MOBILE: 'fixed_line_or_mobile',
        phonenumbers.PhoneNumberType.TOLL_FREE: 'toll_free',
        phonenumbers.PhoneNumberType.PREMIUM_RATE: 'premium_rate',
        phonenumbers.PhoneNumberType.SHARED_COST: 'shared_cost',
        phonenumbers.PhoneNumberType.VOIP: 'voip',
        phonenumbers.PhoneNumberType.PERSONAL_NUMBER: 'personal',
        phonenumbers.PhoneNumberType.PAGER: 'pager',
        phonenumbers.PhoneNumberType.UAN: 'uan',
        phonenumbers.PhoneNumberType.VOICEMAIL: 'voicemail',
        phonenumbers.PhoneNumberType.UNKNOWN: 'unknown',
    }
    return types.get(num_type, 'unknown')


# Example usage
result = analyze_phone_number("+79261234567")
print(result)
# {
#   'valid': True,
#   'country_code': 7,
#   'national_number': 9261234567,
#   'number_type': 'mobile',
#   'carrier': 'Megafon',  # From original carrier, may have ported
#   'location': 'Russia',
#   'timezones': ['Europe/Moscow'],
#   'region_code': 'RU',
#   ...
# }
```

### Limitations
- **Carrier data is static**: Based on original number block allocation, not current carrier (due to MNP - Mobile Number Portability)
- **No real-time validation**: Cannot check if number is currently active

---

## 4. Carrier Lookup Services

### 4.1 NumVerify API
**URL:** https://apilayer.com/marketplace/number_verification-api

```python
import requests

def numverify_lookup(phone: str, api_key: str) -> dict:
    """
    Lookup phone number using NumVerify API.

    Args:
        phone: Phone number in international format (no +)
        api_key: NumVerify API key from apilayer.com

    Returns:
        API response with carrier, location, line type
    """
    url = f"https://api.apilayer.com/number_verification/validate"

    response = requests.get(
        url,
        params={'number': phone},
        headers={'apikey': api_key}
    )

    if response.status_code == 200:
        return response.json()
    return {'error': response.text}

# Example response:
# {
#   "valid": true,
#   "number": "79261234567",
#   "local_format": "9261234567",
#   "international_format": "+79261234567",
#   "country_prefix": "+7",
#   "country_code": "RU",
#   "country_name": "Russia (Russian Federation)",
#   "location": "Moscow",
#   "carrier": "MegaFon",
#   "line_type": "mobile"
# }
```

**Pricing:**
- Free: 100 requests/month
- Paid: Starting $9.99/month

### 4.2 Twilio Lookup API
**URL:** https://www.twilio.com/docs/lookup/v2-api

```python
from twilio.rest import Client

def twilio_lookup(phone: str, account_sid: str, auth_token: str) -> dict:
    """
    Lookup phone number using Twilio Lookup API v2.

    Args:
        phone: Phone number in E.164 format
        account_sid: Twilio account SID
        auth_token: Twilio auth token

    Returns:
        Phone number information including line type
    """
    client = Client(account_sid, auth_token)

    # Basic lookup (FREE)
    phone_number = client.lookups.v2.phone_numbers(phone).fetch()

    # With line type (PAID - $0.005/lookup)
    phone_number = client.lookups.v2.phone_numbers(phone).fetch(
        fields='line_type_intelligence'
    )

    return {
        'phone_number': phone_number.phone_number,
        'country_code': phone_number.country_code,
        'national_format': phone_number.national_format,
        'valid': phone_number.valid,
        'line_type': phone_number.line_type_intelligence
    }
```

**Pricing:**
- Basic validation: FREE
- Line Type Intelligence: $0.005/lookup
- Carrier lookup: $0.005/lookup

### 4.3 Abstract API
**URL:** https://www.abstractapi.com/api/phone-validation-api

**Free tier:** 250 requests/month

### 4.4 Veriphone
**Free tier:** 1,000 requests/month

---

## 5. Russian Phone Number Format Analysis

### Number Structure
Russian phone numbers follow the format: `+7 (DEF) XXX-XX-XX`
- **+7**: Country code
- **DEF**: 3-digit area/operator code
- **XXX-XX-XX**: 7-digit subscriber number

### Mobile Operators (DEF codes 9xx)

```python
# Russian mobile operator prefix database
RUSSIAN_MOBILE_PREFIXES = {
    # MTS (Mobile TeleSystems)
    'MTS': [
        '910', '911', '912', '913', '914', '915', '916', '917', '918', '919',
        '980', '981', '982', '983', '984', '985', '986', '987', '988', '989'
    ],

    # Beeline (VimpelCom)
    'Beeline': [
        '903', '905', '906', '909',
        '960', '961', '962', '963', '964', '965', '966', '967', '968', '969'
    ],

    # MegaFon
    'MegaFon': [
        '920', '921', '922', '923', '924', '925', '926', '927', '928', '929',
        '930', '931', '932', '933', '934', '936', '937', '938', '939',
        '999'
    ],

    # Tele2
    'Tele2': [
        '900', '901', '902', '904',
        '950', '951', '952', '953', '958',
        '977', '978'
    ],

    # Yota (owned by MegaFon)
    'Yota': ['995', '996', '997'],

    # Motiv
    'Motiv': ['908'],

    # Rostelecom mobile
    'Rostelecom': ['991', '992', '993', '994'],
}

# Reserved/unused codes
RESERVED_CODES = [
    '907', '935', '940', '941', '942', '943', '944', '945', '946', '947',
    '948', '949', '954', '955', '956', '957', '959',
    '970', '971', '972', '973', '974', '975', '976', '979',
    '990', '998'
]
```

### Landline Area Codes

```python
# Major Russian city codes
RUSSIAN_CITY_CODES = {
    # Moscow
    '495': 'Moscow',
    '498': 'Moscow (new)',
    '499': 'Moscow',

    # St. Petersburg
    '812': 'Saint Petersburg',

    # Major cities
    '343': 'Yekaterinburg',
    '383': 'Novosibirsk',
    '846': 'Samara',
    '831': 'Nizhny Novgorod',
    '863': 'Rostov-on-Don',
    '351': 'Chelyabinsk',
    '843': 'Kazan',
    '342': 'Perm',
    '347': 'Ufa',
    '861': 'Krasnodar',
    '391': 'Krasnoyarsk',
    '473': 'Voronezh',
    '423': 'Vladivostok',
}
```

### Carrier Identification Function

```python
def identify_russian_carrier(phone: str) -> dict:
    """
    Identify Russian mobile carrier from phone number prefix.

    WARNING: Due to Mobile Number Portability (MNP) introduced in Russia in 2013,
    the prefix may not reflect the CURRENT carrier. This shows the ORIGINAL
    carrier that was assigned this number block.

    Args:
        phone: Phone number (can include +7 or just 9xxxxxxxxx)

    Returns:
        Dictionary with carrier info and confidence
    """
    # Normalize phone number
    phone = phone.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
    if phone.startswith('+7'):
        phone = phone[2:]
    elif phone.startswith('7') and len(phone) == 11:
        phone = phone[1:]
    elif phone.startswith('8') and len(phone) == 11:
        phone = phone[1:]

    if len(phone) != 10:
        return {'error': 'Invalid phone number length', 'carrier': None}

    prefix = phone[:3]

    # Check if it's a mobile number
    if not prefix.startswith('9'):
        # Check landline codes
        for code, city in RUSSIAN_CITY_CODES.items():
            if phone.startswith(code):
                return {
                    'type': 'landline',
                    'city': city,
                    'area_code': code,
                    'carrier': None,
                    'confidence': 'high'
                }
        return {
            'type': 'landline',
            'carrier': None,
            'confidence': 'low',
            'note': 'Unknown area code'
        }

    # Check mobile carriers
    for carrier_name, prefixes in RUSSIAN_MOBILE_PREFIXES.items():
        if prefix in prefixes:
            return {
                'type': 'mobile',
                'original_carrier': carrier_name,
                'prefix': prefix,
                'confidence': 'medium',  # Due to MNP
                'note': 'May have ported to different carrier (MNP)'
            }

    if prefix in RESERVED_CODES:
        return {
            'type': 'reserved',
            'prefix': prefix,
            'carrier': None,
            'note': 'Reserved/unused mobile code'
        }

    return {
        'type': 'mobile',
        'prefix': prefix,
        'carrier': 'Unknown',
        'confidence': 'low'
    }
```

---

## 6. Complete Phone OSINT Service

Here's a complete service class that combines all methods:

```python
"""
Phone Number OSINT Service for IBP Platform
Combines multiple data sources for comprehensive phone analysis.
"""

import phonenumbers
from phonenumbers import carrier, geocoder, timezone
import httpx
from typing import Optional, Dict, Any
import asyncio


class PhoneOSINTService:
    """
    Comprehensive phone number OSINT service.

    Features:
    - Offline validation and formatting (phonenumbers)
    - Carrier/location lookup (NumVerify API if available)
    - Social media presence check (Ignorant-style)
    - Google dork generation for manual investigation
    """

    def __init__(self, numverify_api_key: Optional[str] = None):
        self.numverify_api_key = numverify_api_key

    def validate_and_parse(self, phone: str) -> Dict[str, Any]:
        """Parse and validate phone number using phonenumbers library."""
        try:
            parsed = phonenumbers.parse(phone, 'RU')  # Default to Russia

            return {
                'valid': phonenumbers.is_valid_number(parsed),
                'possible': phonenumbers.is_possible_number(parsed),
                'country_code': parsed.country_code,
                'national_number': parsed.national_number,
                'e164': phonenumbers.format_number(
                    parsed, phonenumbers.PhoneNumberFormat.E164
                ),
                'international': phonenumbers.format_number(
                    parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL
                ),
                'national': phonenumbers.format_number(
                    parsed, phonenumbers.PhoneNumberFormat.NATIONAL
                ),
                'number_type': self._get_type_name(phonenumbers.number_type(parsed)),
                'carrier': carrier.name_for_number(parsed, 'ru'),
                'location': geocoder.description_for_number(parsed, 'ru'),
                'timezones': list(timezone.time_zones_for_number(parsed)),
                'region_code': phonenumbers.region_code_for_number(parsed),
            }
        except Exception as e:
            return {'valid': False, 'error': str(e)}

    def identify_russian_carrier(self, phone: str) -> Dict[str, Any]:
        """Identify carrier from Russian mobile prefix."""
        # Implementation from section 5 above
        pass  # See full implementation above

    async def check_numverify(self, phone: str) -> Optional[Dict[str, Any]]:
        """Query NumVerify API for carrier and location data."""
        if not self.numverify_api_key:
            return None

        async with httpx.AsyncClient() as client:
            response = await client.get(
                'https://api.apilayer.com/number_verification/validate',
                params={'number': phone.replace('+', '')},
                headers={'apikey': self.numverify_api_key}
            )

            if response.status_code == 200:
                return response.json()
            return None

    async def check_instagram(self, phone: str, country_code: str) -> Dict[str, Any]:
        """Check if phone is registered on Instagram (without alerting user)."""
        # Simplified implementation
        import hmac
        import hashlib
        import urllib.parse
        import json

        IG_SIG_KEY = 'e6358aeede676184b9fe702b30f4fd35e71744605e39d2181a34cede076b3c33'

        data = json.dumps({
            'login_attempt_count': '0',
            'directly_sign_in': 'true',
            'source': 'default',
            'q': f'{country_code}{phone}',
            'ig_sig_key_version': '4'
        })

        signed = f'ig_sig_key_version=4&signed_body=' + \
                 hmac.new(IG_SIG_KEY.encode(), data.encode(), hashlib.sha256).hexdigest() + \
                 '.' + urllib.parse.quote_plus(data)

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    'https://i.instagram.com/api/v1/users/lookup/',
                    headers={
                        'User-Agent': 'Instagram 101.0.0.15.120',
                        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                    },
                    data=signed
                )
                result = response.json()
                return {
                    'platform': 'instagram',
                    'exists': 'message' not in result or result.get('message') != 'No users found',
                    'rate_limited': False
                }
            except:
                return {'platform': 'instagram', 'exists': False, 'rate_limited': True}

    def generate_google_dorks(self, phone: str) -> Dict[str, list]:
        """Generate Google dork URLs for phone number investigation."""
        parsed = self.validate_and_parse(phone)
        if not parsed.get('valid'):
            return {}

        e164 = parsed['e164']
        international = e164.replace('+', '')
        national = parsed['national'].replace(' ', '').replace('-', '')

        base = 'https://www.google.com/search?q='

        return {
            'social_media': [
                f'{base}site:vk.com+intext:"{international}"',
                f'{base}site:ok.ru+intext:"{international}"',
                f'{base}site:facebook.com+intext:"{international}"',
                f'{base}site:instagram.com+intext:"{international}"',
                f'{base}site:twitter.com+intext:"{international}"',
            ],
            'directories': [
                f'{base}site:spravker.ru+intext:"{national}"',
                f'{base}site:nomer.org+intext:"{national}"',
                f'{base}site:phonenumber.to+intext:"{international}"',
            ],
            'general': [
                f'{base}"{e164}"',
                f'{base}"{international}"',
                f'{base}"{national}"',
            ],
            'documents': [
                f'{base}(ext:pdf+OR+ext:doc+OR+ext:xls)+intext:"{international}"',
            ]
        }

    async def full_scan(self, phone: str) -> Dict[str, Any]:
        """Perform complete phone number OSINT scan."""
        results = {
            'phone': phone,
            'validation': self.validate_and_parse(phone),
        }

        if not results['validation'].get('valid'):
            return results

        # Get country code for social checks
        country_code = str(results['validation']['country_code'])
        national = str(results['validation']['national_number'])

        # Russian carrier identification
        if results['validation']['region_code'] == 'RU':
            results['russian_carrier'] = self.identify_russian_carrier(phone)

        # API-based lookups (run in parallel)
        tasks = []

        if self.numverify_api_key:
            tasks.append(self.check_numverify(phone))

        tasks.append(self.check_instagram(national, country_code))

        if tasks:
            api_results = await asyncio.gather(*tasks, return_exceptions=True)

            if self.numverify_api_key and not isinstance(api_results[0], Exception):
                results['numverify'] = api_results[0]

            ig_idx = 1 if self.numverify_api_key else 0
            if not isinstance(api_results[ig_idx], Exception):
                results['instagram'] = api_results[ig_idx]

        # Generate dorks for manual investigation
        results['google_dorks'] = self.generate_google_dorks(phone)

        return results

    @staticmethod
    def _get_type_name(num_type: int) -> str:
        """Convert phonenumbers type constant to string."""
        types = {
            phonenumbers.PhoneNumberType.FIXED_LINE: 'landline',
            phonenumbers.PhoneNumberType.MOBILE: 'mobile',
            phonenumbers.PhoneNumberType.FIXED_LINE_OR_MOBILE: 'fixed_or_mobile',
            phonenumbers.PhoneNumberType.TOLL_FREE: 'toll_free',
            phonenumbers.PhoneNumberType.PREMIUM_RATE: 'premium_rate',
            phonenumbers.PhoneNumberType.VOIP: 'voip',
            phonenumbers.PhoneNumberType.UNKNOWN: 'unknown',
        }
        return types.get(num_type, 'unknown')


# Usage example
async def main():
    service = PhoneOSINTService(
        numverify_api_key=None  # Set your API key here
    )

    result = await service.full_scan('+79261234567')
    print(result)

# asyncio.run(main())
```

---

## 7. Summary: What Data Can Be Obtained

### Free Methods (No API)
| Data Point | Source | Reliability |
|------------|--------|-------------|
| Valid format | phonenumbers | High |
| Country | phonenumbers | High |
| Number type (mobile/landline) | phonenumbers | High |
| Original carrier | phonenumbers / prefix DB | Medium (MNP) |
| Region/city | phonenumbers | Medium |
| Timezone | phonenumbers | High |
| Instagram registration | Ignorant method | Medium |
| Snapchat registration | Ignorant method | Medium |
| Amazon registration | Ignorant method | Medium |

### Paid APIs
| Data Point | Source | Cost |
|------------|--------|------|
| Current carrier | NumVerify, Twilio | $0.005-0.01/lookup |
| Line type (VoIP detection) | NumVerify, Twilio | $0.005/lookup |
| Precise location | NumVerify | Included |
| Real-time validity | NumVerify, Twilio | Included |

### Russian Numbers Specifics
- **Prefix-based carrier ID**: Works but unreliable due to MNP (since 2013)
- **OVH Scanner**: NOT supported for +7 numbers
- **Social media checks**: VK would be most valuable (not in Ignorant)

---

## 8. Recommended Implementation for IBP

1. **Phase 1**: Use `phonenumbers` library for all basic validation and metadata extraction
2. **Phase 2**: Add Russian carrier prefix database for initial identification
3. **Phase 3**: Optional NumVerify integration for real-time carrier/location data
4. **Phase 4**: Ignorant-style social media checks (Instagram, Snapchat, potentially VK)
5. **Phase 5**: Google dork generation for manual investigation

### Dependencies to Add
```
phonenumbers>=8.13.0
httpx>=0.24.0
trio>=0.22.0  # For Ignorant-style async checks
```

---

## Sources

- [PhoneInfoga GitHub](https://github.com/sundowndev/phoneinfoga)
- [Ignorant GitHub](https://github.com/megadose/ignorant)
- [python-phonenumbers](https://github.com/daviddrysdale/python-phonenumbers)
- [NumVerify API](https://numverify.com/documentation)
- [Twilio Lookup API](https://www.twilio.com/docs/lookup/v2-api)
- [Telephone numbers in Russia](https://en.wikipedia.org/wiki/Telephone_numbers_in_Russia)
- [Russian mobile operator codes](https://mdlr.ru/en/megafon/portal-operatorov-svyazi.html)
