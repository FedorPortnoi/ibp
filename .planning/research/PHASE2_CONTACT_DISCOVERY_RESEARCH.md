# Phase 2 Contact Discovery Research
## Russian OSINT Techniques for Email, Phone, and Photo-Based Discovery

**Research Date:** 2026-01-26
**Focus:** Russia-specific OSINT techniques for IBP Phase 2

---

## PART 1: EMAIL DISCOVERY TECHNIQUES FOR RUSSIA

### Technique 1: Mailcat - Username to Email Discovery
- **How it works**: Given a username, checks if `username@domain` exists across 170+ email domains using SMTP probing, API checks, and registration page testing
- **Success rate**: ~60-70% for active usernames
- **Requirements**: Username, Python 3, optional Tor/proxy
- **Russian domains supported**:
  - yandex.ru (+ ya.ru, yandex.com, yandex.by, yandex.kz, yandex.ua)
  - mail.ru (+ bk.ru, list.ru, inbox.ru, internet.ru)
  - rambler.ru (+ lenta.ru, myrambler.ru, autorambler.ru, ro.ru, r0.ru)
- **Implementation**: YES - can wrap as Python service
- **Source**: [github.com/sharsil/mailcat](https://github.com/sharsil/mailcat)

### Technique 2: Holehe - Email Registration Check
- **How it works**: Checks if a given email is registered on 120+ websites using password recovery/registration endpoints
- **Success rate**: ~80% detection rate for registered emails
- **Requirements**: Full email address, Python 3
- **Russian services supported**: mail.ru, rambler.ru, ok.ru (Odnoklassniki)
- **Implementation**: YES - already Python library, pip install holehe
- **Source**: [github.com/megadose/holehe](https://github.com/megadose/holehe)

### Technique 3: VK Profile Contact Extraction
- **How it works**: Scrape VK profile's "Contact Information" section which may contain email if user made it public
- **Success rate**: ~15-20% (many users hide email)
- **Requirements**: VK profile URL, VK API token
- **Implementation**: YES - use vk_api library
- **Source**: [VK API Documentation](https://vk.com/dev/fields)

### Technique 4: Telegram OSINT Bots - Email Search
- **How it works**: Bots like Quick_OSINT_bot and Eye of God search leaked databases and public sources by email
- **Success rate**: ~40-60% for Russian emails
- **Requirements**: Telegram account, payment for full results
- **Russian services**:
  - @Quick_OSINT_bot - Free daily queries, $0.10/report
  - @EyeGodsBot (Eye of God) - Most comprehensive, paid subscription
  - @UniversalSearchBot - Yandex email checks
- **Implementation**: PARTIAL - can integrate via Telegram Bot API for automated queries
- **Source**: [HackMag Testing](https://hackmag.com/security/telegram-bots)

### Technique 5: Cross-Platform Username Correlation
- **How it works**: If we find VK username "ivan_petrov", generate email candidates: ivan_petrov@mail.ru, ivan_petrov@yandex.ru, etc.
- **Success rate**: ~30-40% (Russians often reuse usernames)
- **Requirements**: Social media username
- **Implementation**: YES - simple pattern generation + Mailcat/Holehe verification
- **Source**: [OSINT Industries VK Guide](https://www.osint.industries/post/osint-on-vk-find-russian-emails-phone-numbers-and-more)

### Technique 6: H8mail - Breach Database Search
- **How it works**: Searches email against known breach databases (local or API services)
- **Success rate**: Varies by breach coverage
- **Requirements**: Email address, optional API keys for premium services
- **Implementation**: YES - pip install h8mail
- **Source**: [github.com/khast3x/h8mail](https://github.com/khast3x/h8mail)

### Technique 7: Reveng.ee - Russian Breach Database
- **How it works**: Free service for journalists/researchers with parsed Russian databases
- **Success rate**: Unknown, but specifically Russian-focused
- **Requirements**: Account verification as journalist/researcher
- **Implementation**: MANUAL - no known API
- **Source**: [reveng.ee](https://reveng.ee)

---

## PART 2: PHONE DISCOVERY TECHNIQUES FOR RUSSIA

### Technique 1: Sberbank/Tinkoff Money Transfer Lookup
- **How it works**: Initiate a money transfer to a phone number via Sberbank/Tinkoff online banking. System reveals partial cardholder name (e.g., "Иван П.")
- **Success rate**: ~90% (most Russians have bank accounts linked to phones)
- **Requirements**: Russian bank account, target phone number
- **Implementation**: MANUAL - requires authentication, no public API
- **Source**: [Medium - Igor Bederov](https://medium.com/@ibederov_en/check-and-locate-phone-number-in-osint-8beb8af50d5e)

### Technique 2: GetContact API Lookup
- **How it works**: Query GetContact's crowdsourced database to see how others have saved a phone number in their contacts
- **Success rate**: ~70% for Russian numbers (popular app in Russia)
- **Requirements**: Phone number, GetContact tokens from Android app
- **Russian relevance**: Very popular in Russia, high coverage
- **Implementation**: YES - Python wrapper available
- **Source**: [github.com/kovinevmv/getcontact](https://github.com/kovinevmv/getcontact)

```python
# Example GetContact usage
python3 ./src/main.py -p +79291045312
# Returns: display names, tags, country code
```

### Technique 3: vkOsint - Phone to VK Account
- **How it works**: Uses VK's private API to search for accounts linked to a phone number
- **Success rate**: ~60% (depends on VK privacy settings)
- **Requirements**: Phone number, VK account credentials
- **Implementation**: YES - pip install vkOsint
- **Source**: [github.com/DIJIRO/vkOsint](https://github.com/DIJIRO/vkOsint)

```python
from vkOsint import vkOsint
vk = vkOsint()
vk.login(username='login', password='password')
results = vk.osint(phoneNumbers=['+79001234567'])
```

### Technique 4: VK Password Recovery Phone Hints
- **How it works**: Initiate password recovery on VK with email/username, system shows masked phone (e.g., "+7 *** *** **45")
- **Success rate**: ~80% for accounts with phone linked
- **Requirements**: VK username or email
- **Implementation**: YES - can automate via requests/selenium
- **Recovery URL**: https://connect.vk.com/restore/
- **Source**: [HackYourMom VK OSINT](https://hackyourmom.com/en/osvita/vk/)

### Technique 5: Telegram Phone Number Checker
- **How it works**: Check if a phone number has a Telegram account, retrieve username and display name
- **Success rate**: ~85% (Telegram very popular in Russia)
- **Requirements**: Phone number, Telegram account (may get blocked for bulk queries)
- **Implementation**: YES - Bellingcat tool available
- **Source**: [Bellingcat Toolkit](https://bellingcat.gitbook.io/toolkit/more/all-tools/telegram-phone-number-checker)

### Technique 6: WhatsApp Registration Check
- **How it works**: Verify if phone is registered on WhatsApp, retrieve profile picture if public
- **Success rate**: ~70% for Russian numbers
- **Requirements**: Phone number
- **Implementation**: YES - RapidAPI WhatsApp OSINT API or custom tool
- **Source**: [github.com/kinghacker0/WhatsApp-OSINT](https://github.com/kinghacker0/WhatsApp-OSINT)

### Technique 7: email2phonenumber - Cross-Platform Digit Scraping
- **How it works**: Submit password reset requests to multiple services, each reveals different phone digits, combine to get full number
- **Success rate**: ~30% (many services now have captchas)
- **Requirements**: Target's email address
- **Implementation**: DEPRECATED - original services added protections
- **Source**: [github.com/martinvigo/email2phonenumber](https://github.com/martinvigo/email2phonenumber)

### Technique 8: Eye of God Telegram Bot
- **How it works**: Comprehensive Russian OSINT bot searching government DBs, leaked social networks, classifieds
- **Success rate**: ~80% ("if Eye of God doesn't have it, 70% others don't")
- **Requirements**: Telegram, subscription payment
- **Bot**: @EyeGodsBot
- **Implementation**: PARTIAL - can query via Telegram Bot API
- **Source**: [eyeofgod.bot](https://eyeofgod.bot/)

### Technique 9: Russian Phone Number Validation
- **How it works**: Validate phone format and identify carrier from prefix
- **Format**: +7 9XX XXX XX XX (mobile), +7 (area) XXX-XX-XX (landline)
- **Mobile prefixes**:
  - MTS: 910-919, 980-989
  - Beeline: 900-909, 960-969
  - Megafon: 920-929, 930-939
  - Tele2: 950-959, 970-979
- **Implementation**: YES - regex validation
- **Note**: MNP since 2013 means prefix != current carrier
- **Source**: [Wikipedia - Russian Phone Numbers](https://en.wikipedia.org/wiki/Telephone_numbers_in_Russia)

### Technique 10: Avito/Classifieds Phone Discovery
- **How it works**: Search Avito (Russia's largest classifieds) for ads by name/photo, extract phone from listings
- **Success rate**: ~20% (depends on person posting ads)
- **Requirements**: Name or photo
- **Implementation**: PARTIAL - Avito has anti-scraping measures
- **Source**: [Avito.ru](https://avito.ru)

---

## PART 3: PHOTO-BASED DISCOVERY TECHNIQUES

### Technique 1: Search4faces - VK/OK Face Search
- **How it works**: Upload photo, searches 850M+ faces from VK and OK profiles
- **Success rate**: ~60-70% for Russians with social media
- **Requirements**: Face photo, account for API access
- **Databases**:
  - 280M VK main profile pictures
  - 570M VK additional photos
  - OK (Odnoklassniki) profiles
  - TikTok, Clubhouse
- **Implementation**: YES - API available
- **Source**: [search4faces.com](https://search4faces.com), [Bellingcat Guide](https://bellingcat.gitbook.io/toolkit/more/all-tools/search4faces)

### Technique 2: Yandex Reverse Image Search
- **How it works**: Upload photo to Yandex Images, finds visually similar images with emphasis on faces
- **Success rate**: ~50-60% for Russian subjects
- **Requirements**: Photo
- **Key advantage**: Best face recognition for Eastern European/Russian faces, free
- **Implementation**: YES - can automate via requests (no official API)
- **Source**: [Yandex Images](https://yandex.com/images/)

### Technique 3: FindClone - VK Face Recognition
- **How it works**: Powerful facial recognition against VK database
- **Success rate**: ~70-80% (considered most accurate)
- **Requirements**: Photo, Russian/Belarus payment method (sanctions)
- **Status**: Difficult to access due to Western sanctions since 2022
- **Implementation**: DIFFICULT - payment/access issues
- **Source**: [findclone.ru](https://findclone.ru)

### Technique 4: AVinfoBot - Photo to VK Account
- **How it works**: Send face photo to Telegram bot, returns matching VK profiles
- **Success rate**: ~50%
- **Requirements**: Photo, Telegram account
- **Bot**: @AVinfoBot
- **Implementation**: PARTIAL - via Telegram Bot API
- **Source**: [HackMag Testing](https://hackmag.com/security/telegram-bots)

### Technique 5: Face → Profile → Contact Chain
- **How it works**:
  1. Upload photo to Search4faces/Yandex
  2. Get VK/OK profile link
  3. Scrape profile for contact info (phone, email in bio)
  4. Cross-reference with other techniques
- **Success rate**: ~30-40% end-to-end
- **Requirements**: Photo
- **Implementation**: YES - chain existing services
- **Source**: [OSINT Industries](https://www.osint.industries/post/osint-on-vk-find-russian-emails-phone-numbers-and-more)

### Technique 6: PimEyes - Web Face Search
- **How it works**: Searches web (not social media) for face matches
- **Success rate**: ~40% for Russians (less Russian web coverage)
- **Requirements**: Photo, paid subscription
- **Implementation**: NO - paid API, limited Russian coverage
- **Source**: [pimeyes.com](https://pimeyes.com)

---

## PART 2: PRIORITIZED IMPLEMENTATION PLAN

## HIGH PRIORITY (Implement First)

### 1. Mailcat Integration - Username to Email Discovery
**Reason**: We already generate usernames in Phase 1. This directly converts them to verified emails.
**Effort**: Low (pip install, wrapper function)
**Impact**: High - adds real email discovery from existing data

### 2. Holehe Integration - Email Verification
**Reason**: Verify which generated emails actually exist on Russian services
**Effort**: Low (pip install holehe)
**Impact**: High - filters noise, confirms valid emails

### 3. VK Profile Contact Scraping Enhancement
**Reason**: We already scrape VK profiles. Add email/phone extraction from contact section.
**Effort**: Low (add fields to existing scraper)
**Impact**: Medium-High - direct contact discovery

### 4. Russian Phone Validation
**Reason**: Validate any phone numbers found, identify carrier
**Effort**: Very Low (regex patterns)
**Impact**: Medium - improves data quality

### 5. Yandex Reverse Image Search Automation
**Reason**: Already using Yandex for images. Automate face-to-profile discovery.
**Effort**: Medium (web scraping)
**Impact**: High - photo leads to profile leads to contacts

## MEDIUM PRIORITY (Implement If Time)

### 6. Search4faces API Integration
**Reason**: Best Russian face search, has API
**Effort**: Medium (API integration)
**Impact**: High - but duplicates Yandex effort

### 7. Telegram Phone Checker
**Reason**: Verify phones have Telegram, get usernames
**Effort**: Medium (Telegram API, account risks)
**Impact**: Medium - additional verification

### 8. vkOsint - Phone to VK Lookup
**Reason**: Reverse lookup from phone to VK profile
**Effort**: Medium (requires VK credentials)
**Impact**: Medium - useful for phone→profile chain

### 9. WhatsApp Registration Check
**Reason**: Verify phones, get profile pictures
**Effort**: Medium (API integration)
**Impact**: Medium - additional verification

## LOW PRIORITY (Future Enhancement)

### 10. GetContact API Integration
**Reason**: See how contacts save a phone number
**Effort**: High (requires Android app token extraction)
**Impact**: Medium - interesting data but complex setup

### 11. Telegram Bot Queries (Eye of God, Quick_OSINT)
**Reason**: Comprehensive Russian data
**Effort**: Medium (Telegram Bot API)
**Impact**: High but requires payment

### 12. H8mail Breach Search
**Reason**: Find passwords/data from breaches
**Effort**: Low
**Impact**: Variable - ethical/legal concerns

## NOT FEASIBLE (Skip)

### 1. Sberbank/Tinkoff Lookup
**Reason**: Requires Russian bank account with authentication
**Skip**: No automation possible

### 2. FindClone
**Reason**: Western sanctions block payment/access
**Skip**: Cannot access service

### 3. email2phonenumber
**Reason**: Services added captchas, tool deprecated
**Skip**: No longer functional

### 4. Avito Scraping
**Reason**: Heavy anti-scraping, requires phone verification
**Skip**: Too complex for limited return

---

## PART 3: CODE ENHANCEMENTS

## Enhancement 1: Mailcat Email Discovery Service

### New file: `app/services/phase2/mailcat_email_discovery.py`

```python
"""
Mailcat Email Discovery Service
Discovers existing emails from usernames using SMTP/API probing
"""

import subprocess
import json
import os
import tempfile
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)

# Russian email domains to prioritize
RUSSIAN_DOMAINS = [
    'mail.ru', 'bk.ru', 'list.ru', 'inbox.ru', 'internet.ru',
    'yandex.ru', 'ya.ru', 'yandex.com',
    'rambler.ru', 'lenta.ru', 'myrambler.ru', 'autorambler.ru', 'ro.ru'
]

class MailcatEmailDiscovery:
    """Discover emails from usernames using mailcat"""

    def __init__(self, use_tor: bool = False, proxy: Optional[str] = None):
        self.use_tor = use_tor
        self.proxy = proxy
        self.mailcat_path = self._find_mailcat()

    def _find_mailcat(self) -> Optional[str]:
        """Find mailcat installation"""
        # Check if mailcat is installed
        try:
            result = subprocess.run(
                ['python', '-c', 'import mailcat'],
                capture_output=True,
                timeout=10
            )
            if result.returncode == 0:
                return 'mailcat'
        except Exception:
            pass
        return None

    def discover_emails(self, username: str) -> Dict:
        """
        Discover existing emails for a username

        Args:
            username: Social media username to check

        Returns:
            Dict with discovered emails and metadata
        """
        results = {
            'username': username,
            'discovered_emails': [],
            'checked_domains': [],
            'errors': []
        }

        if not self.mailcat_path:
            # Fallback: generate candidates without verification
            results['discovered_emails'] = self._generate_candidates(username)
            results['verified'] = False
            return results

        try:
            # Build command
            cmd = ['python', '-m', 'mailcat', username]
            if self.use_tor:
                cmd.append('--tor')
            if self.proxy:
                cmd.extend(['--proxy', self.proxy])

            # Run mailcat
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120
            )

            # Parse output
            if result.returncode == 0:
                results['discovered_emails'] = self._parse_mailcat_output(result.stdout)
                results['verified'] = True
            else:
                results['errors'].append(result.stderr)
                results['discovered_emails'] = self._generate_candidates(username)
                results['verified'] = False

        except subprocess.TimeoutExpired:
            results['errors'].append('Mailcat timeout')
            results['discovered_emails'] = self._generate_candidates(username)
            results['verified'] = False
        except Exception as e:
            results['errors'].append(str(e))
            results['discovered_emails'] = self._generate_candidates(username)
            results['verified'] = False

        return results

    def _generate_candidates(self, username: str) -> List[str]:
        """Generate email candidates without verification"""
        candidates = []
        for domain in RUSSIAN_DOMAINS:
            candidates.append(f"{username}@{domain}")
        return candidates

    def _parse_mailcat_output(self, output: str) -> List[str]:
        """Parse mailcat output for discovered emails"""
        emails = []
        for line in output.split('\n'):
            if '@' in line and 'Found' in line:
                # Extract email from line like "Found: username@domain.ru"
                parts = line.split(':')
                if len(parts) >= 2:
                    email = parts[1].strip()
                    if '@' in email:
                        emails.append(email)
        return emails

    def discover_from_usernames(self, usernames: List[str]) -> List[Dict]:
        """Discover emails for multiple usernames"""
        all_results = []
        for username in usernames:
            result = self.discover_emails(username)
            all_results.append(result)
        return all_results
```

### Integration in `app/services/combined_search.py`:

```python
# Add import at top
from app.services.phase2.mailcat_email_discovery import MailcatEmailDiscovery

# Add in Phase 2 discovery method
def discover_emails_from_usernames(self, usernames: List[str]) -> List[str]:
    """Convert discovered usernames to verified emails"""
    email_discovery = MailcatEmailDiscovery()
    all_emails = []

    for username in usernames[:10]:  # Limit to avoid timeouts
        result = email_discovery.discover_emails(username)
        all_emails.extend(result.get('discovered_emails', []))

    return list(set(all_emails))  # Deduplicate
```

---

## Enhancement 2: Holehe Email Verification Service

### New file: `app/services/phase2/holehe_verification.py`

```python
"""
Holehe Email Verification Service
Verifies if emails are registered on various services
"""

import subprocess
import json
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)

class HoleheVerification:
    """Verify email registration across services using Holehe"""

    # Russian services that Holehe supports
    RUSSIAN_SERVICES = ['mail.ru', 'rambler.ru', 'ok.ru']

    def __init__(self):
        self.holehe_available = self._check_holehe()

    def _check_holehe(self) -> bool:
        """Check if holehe is installed"""
        try:
            result = subprocess.run(
                ['holehe', '--help'],
                capture_output=True,
                timeout=10
            )
            return result.returncode == 0
        except Exception:
            return False

    def verify_email(self, email: str) -> Dict:
        """
        Verify which services an email is registered on

        Args:
            email: Email address to check

        Returns:
            Dict with services where email is registered
        """
        results = {
            'email': email,
            'registered_services': [],
            'checked_services': [],
            'russian_services': [],
            'exists': False,
            'errors': []
        }

        if not self.holehe_available:
            results['errors'].append('Holehe not installed')
            return results

        try:
            # Run holehe
            result = subprocess.run(
                ['holehe', email, '--only-used', '-C'],
                capture_output=True,
                text=True,
                timeout=180
            )

            if result.returncode == 0:
                parsed = self._parse_holehe_output(result.stdout)
                results['registered_services'] = parsed['registered']
                results['checked_services'] = parsed['checked']
                results['exists'] = len(parsed['registered']) > 0

                # Filter Russian services
                results['russian_services'] = [
                    s for s in parsed['registered']
                    if any(rs in s.lower() for rs in self.RUSSIAN_SERVICES)
                ]
            else:
                results['errors'].append(result.stderr)

        except subprocess.TimeoutExpired:
            results['errors'].append('Holehe timeout')
        except Exception as e:
            results['errors'].append(str(e))

        return results

    def _parse_holehe_output(self, output: str) -> Dict:
        """Parse holehe CSV output"""
        registered = []
        checked = []

        for line in output.split('\n'):
            if ',' in line:
                parts = line.split(',')
                if len(parts) >= 2:
                    service = parts[0].strip()
                    status = parts[1].strip().lower()
                    checked.append(service)
                    if 'true' in status or 'used' in status:
                        registered.append(service)

        return {'registered': registered, 'checked': checked}

    def verify_multiple_emails(self, emails: List[str]) -> List[Dict]:
        """Verify multiple emails"""
        results = []
        for email in emails:
            result = self.verify_email(email)
            results.append(result)
        return results

    def filter_valid_emails(self, emails: List[str]) -> List[str]:
        """Return only emails that are registered somewhere"""
        valid = []
        for email in emails:
            result = self.verify_email(email)
            if result['exists']:
                valid.append(email)
        return valid
```

---

## Enhancement 3: Russian Phone Validator

### New file: `app/services/phase2/russian_phone_validator.py`

```python
"""
Russian Phone Number Validator
Validates format and identifies carrier for Russian phone numbers
"""

import re
from typing import Dict, Optional, List
from dataclasses import dataclass

@dataclass
class PhoneInfo:
    """Information about a phone number"""
    original: str
    normalized: str
    is_valid: bool
    is_mobile: bool
    carrier_hint: Optional[str]
    region: Optional[str]
    format_type: str  # 'mobile', 'landline', 'unknown'

# Russian mobile operator prefixes (approximate - MNP means these aren't definitive)
CARRIER_PREFIXES = {
    'MTS': ['910', '911', '912', '913', '914', '915', '916', '917', '918', '919',
            '980', '981', '982', '983', '984', '985', '986', '987', '988', '989'],
    'Beeline': ['900', '901', '902', '903', '904', '905', '906', '907', '908', '909',
                '960', '961', '962', '963', '964', '965', '966', '967', '968', '969'],
    'Megafon': ['920', '921', '922', '923', '924', '925', '926', '927', '928', '929',
                '930', '931', '932', '933', '934', '935', '936', '937', '938', '939'],
    'Tele2': ['950', '951', '952', '953', '954', '955', '956', '957', '958', '959',
              '977', '978', '999'],
    'Yota': ['990', '991', '992', '993', '994', '995', '996', '997', '998'],
}

# Moscow and St. Petersburg area codes
MAJOR_CITY_CODES = {
    '495': 'Moscow',
    '499': 'Moscow',
    '498': 'Moscow Oblast',
    '812': 'Saint Petersburg',
}

class RussianPhoneValidator:
    """Validate and analyze Russian phone numbers"""

    # Regex patterns for Russian phones
    PATTERNS = {
        'international_mobile': re.compile(r'^\+7\s*9\d{2}\s*\d{3}\s*\d{2}\s*\d{2}$'),
        'international_landline': re.compile(r'^\+7\s*\d{3}\s*\d{3}\s*\d{2}\s*\d{2}$'),
        'domestic_mobile': re.compile(r'^8\s*9\d{2}\s*\d{3}\s*\d{2}\s*\d{2}$'),
        'domestic_landline': re.compile(r'^8\s*\d{3}\s*\d{3}\s*\d{2}\s*\d{2}$'),
    }

    @staticmethod
    def normalize(phone: str) -> str:
        """Normalize phone to +7XXXXXXXXXX format"""
        # Remove all non-digits
        digits = re.sub(r'\D', '', phone)

        # Handle different formats
        if len(digits) == 11:
            if digits.startswith('8'):
                return '+7' + digits[1:]
            elif digits.startswith('7'):
                return '+' + digits
        elif len(digits) == 10:
            return '+7' + digits

        return phone  # Return original if can't normalize

    def validate(self, phone: str) -> PhoneInfo:
        """
        Validate a Russian phone number

        Args:
            phone: Phone number in any format

        Returns:
            PhoneInfo with validation results
        """
        normalized = self.normalize(phone)
        digits_only = re.sub(r'\D', '', normalized)

        # Check if valid Russian number
        is_valid = (
            len(digits_only) == 11 and
            digits_only.startswith('7')
        )

        # Determine if mobile
        is_mobile = is_valid and digits_only[1] == '9'

        # Get carrier hint
        carrier_hint = None
        region = None
        format_type = 'unknown'

        if is_valid:
            prefix = digits_only[1:4]  # e.g., '910'

            if is_mobile:
                format_type = 'mobile'
                for carrier, prefixes in CARRIER_PREFIXES.items():
                    if prefix in prefixes:
                        carrier_hint = carrier
                        break
            else:
                format_type = 'landline'
                if prefix in MAJOR_CITY_CODES:
                    region = MAJOR_CITY_CODES[prefix]

        return PhoneInfo(
            original=phone,
            normalized=normalized,
            is_valid=is_valid,
            is_mobile=is_mobile,
            carrier_hint=carrier_hint,
            region=region,
            format_type=format_type
        )

    def extract_phones(self, text: str) -> List[PhoneInfo]:
        """Extract and validate all Russian phone numbers from text"""
        # Patterns to find phones in text
        phone_patterns = [
            r'\+7[\s\-\(]?\d{3}[\s\-\)]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}',
            r'8[\s\-\(]?\d{3}[\s\-\)]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}',
            r'\+7\d{10}',
            r'8\d{10}',
        ]

        found_phones = []
        for pattern in phone_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                info = self.validate(match)
                if info.is_valid and info.normalized not in [p.normalized for p in found_phones]:
                    found_phones.append(info)

        return found_phones

    def format_display(self, phone: str) -> str:
        """Format phone for display: +7 (XXX) XXX-XX-XX"""
        normalized = self.normalize(phone)
        digits = re.sub(r'\D', '', normalized)

        if len(digits) == 11 and digits.startswith('7'):
            return f"+7 ({digits[1:4]}) {digits[4:7]}-{digits[7:9]}-{digits[9:11]}"

        return phone
```

---

## Enhancement 4: VK Contact Extractor Enhancement

### Add to existing `app/services/vk_search.py` or create `app/services/phase2/vk_contact_extractor.py`:

```python
"""
VK Contact Extractor
Extract phone/email from VK profile contact information
"""

import re
import requests
from typing import Dict, List, Optional
from bs4 import BeautifulSoup
import logging

logger = logging.getLogger(__name__)

class VKContactExtractor:
    """Extract contact information from VK profiles"""

    def __init__(self, access_token: Optional[str] = None):
        self.access_token = access_token
        self.api_version = '5.131'
        self.api_base = 'https://api.vk.com/method/'

    def extract_from_profile_url(self, profile_url: str) -> Dict:
        """
        Extract contact info from VK profile

        Args:
            profile_url: VK profile URL

        Returns:
            Dict with extracted contacts
        """
        results = {
            'url': profile_url,
            'phones': [],
            'emails': [],
            'telegram': None,
            'instagram': None,
            'skype': None,
            'websites': [],
            'raw_contacts': None
        }

        # Extract user ID from URL
        user_id = self._extract_user_id(profile_url)
        if not user_id:
            return results

        # Try API first if token available
        if self.access_token:
            api_result = self._extract_via_api(user_id)
            if api_result:
                return {**results, **api_result}

        # Fallback to web scraping
        return self._extract_via_scraping(profile_url, results)

    def _extract_user_id(self, url: str) -> Optional[str]:
        """Extract VK user ID or screen name from URL"""
        patterns = [
            r'vk\.com/id(\d+)',
            r'vk\.com/([a-zA-Z0-9_.]+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    def _extract_via_api(self, user_id: str) -> Optional[Dict]:
        """Extract contacts via VK API"""
        try:
            # Request user info with contacts field
            params = {
                'user_ids': user_id,
                'fields': 'contacts,connections,site,mobile_phone,home_phone',
                'access_token': self.access_token,
                'v': self.api_version
            }

            response = requests.get(
                f'{self.api_base}users.get',
                params=params,
                timeout=10
            )

            data = response.json()
            if 'response' in data and data['response']:
                user = data['response'][0]
                return self._parse_api_response(user)

        except Exception as e:
            logger.error(f"VK API error: {e}")

        return None

    def _parse_api_response(self, user: Dict) -> Dict:
        """Parse VK API user response"""
        result = {
            'phones': [],
            'emails': [],
            'telegram': None,
            'instagram': None,
            'skype': None,
            'websites': []
        }

        # Extract phone numbers
        if 'mobile_phone' in user and user['mobile_phone']:
            result['phones'].append(user['mobile_phone'])
        if 'home_phone' in user and user['home_phone']:
            result['phones'].append(user['home_phone'])

        # Extract connections
        if 'connections' in user:
            conn = user['connections']
            if 'skype' in conn:
                result['skype'] = conn['skype']
            if 'instagram' in conn:
                result['instagram'] = conn['instagram']

        # Extract website
        if 'site' in user and user['site']:
            result['websites'].append(user['site'])

        return result

    def _extract_via_scraping(self, url: str, results: Dict) -> Dict:
        """Extract contacts by scraping profile page"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }

            response = requests.get(url, headers=headers, timeout=15)
            soup = BeautifulSoup(response.text, 'html.parser')

            # Look for contact information sections
            text = soup.get_text()

            # Extract phones
            phone_patterns = [
                r'\+7[\s\-\(]?\d{3}[\s\-\)]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}',
                r'8[\s\-\(]?\d{3}[\s\-\)]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}',
            ]
            for pattern in phone_patterns:
                matches = re.findall(pattern, text)
                results['phones'].extend(matches)

            # Extract emails
            email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
            emails = re.findall(email_pattern, text)
            results['emails'].extend(emails)

            # Extract Telegram usernames
            tg_pattern = r'(?:t\.me/|@)([a-zA-Z0-9_]{5,32})'
            tg_matches = re.findall(tg_pattern, text)
            if tg_matches:
                results['telegram'] = tg_matches[0]

            # Deduplicate
            results['phones'] = list(set(results['phones']))
            results['emails'] = list(set(results['emails']))

        except Exception as e:
            logger.error(f"VK scraping error: {e}")

        return results

    def extract_from_multiple_profiles(self, profile_urls: List[str]) -> List[Dict]:
        """Extract contacts from multiple VK profiles"""
        all_results = []
        for url in profile_urls:
            result = self.extract_from_profile_url(url)
            all_results.append(result)
        return all_results
```

---

## Enhancement 5: Yandex Image Face Search Automation

### New file: `app/services/phase2/yandex_face_search.py`

```python
"""
Yandex Image Face Search
Automate face search using Yandex reverse image search
"""

import requests
import re
from typing import List, Dict, Optional
from urllib.parse import urlencode, quote
import logging
import base64
import time

logger = logging.getLogger(__name__)

class YandexFaceSearch:
    """Search for faces using Yandex reverse image search"""

    UPLOAD_URL = 'https://yandex.com/images/search'

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept-Language': 'en-US,en;q=0.9,ru;q=0.8',
        })

    def search_by_image_url(self, image_url: str) -> Dict:
        """
        Search Yandex by image URL

        Args:
            image_url: URL of the image to search

        Returns:
            Dict with search results including similar faces
        """
        results = {
            'query_url': image_url,
            'similar_images': [],
            'face_matches': [],
            'related_pages': [],
            'errors': []
        }

        try:
            # Build search URL
            params = {
                'rpt': 'imageview',
                'url': image_url,
            }
            search_url = f"{self.UPLOAD_URL}?{urlencode(params)}"

            # Make request
            response = self.session.get(search_url, timeout=30)

            if response.status_code == 200:
                results = self._parse_results(response.text, results)
            else:
                results['errors'].append(f"HTTP {response.status_code}")

        except Exception as e:
            results['errors'].append(str(e))

        return results

    def search_by_image_file(self, image_path: str) -> Dict:
        """
        Search Yandex by uploading image file

        Args:
            image_path: Path to image file

        Returns:
            Dict with search results
        """
        results = {
            'query_file': image_path,
            'similar_images': [],
            'face_matches': [],
            'related_pages': [],
            'errors': []
        }

        try:
            # Read and prepare image
            with open(image_path, 'rb') as f:
                image_data = f.read()

            # Upload image
            files = {
                'upfile': ('image.jpg', image_data, 'image/jpeg')
            }

            upload_url = 'https://yandex.com/images/search?rpt=imageview&format=json&request='
            response = self.session.post(
                upload_url,
                files=files,
                timeout=60
            )

            if response.status_code == 200:
                # Parse redirect URL or results
                results = self._parse_results(response.text, results)
            else:
                results['errors'].append(f"Upload failed: HTTP {response.status_code}")

        except Exception as e:
            results['errors'].append(str(e))

        return results

    def _parse_results(self, html: str, results: Dict) -> Dict:
        """Parse Yandex image search results"""

        # Extract VK profile links
        vk_pattern = r'https?://vk\.com/[a-zA-Z0-9_.]+|https?://vk\.com/id\d+'
        vk_matches = re.findall(vk_pattern, html)
        if vk_matches:
            results['face_matches'].extend([
                {'platform': 'vk', 'url': url}
                for url in set(vk_matches)
            ])

        # Extract OK profile links
        ok_pattern = r'https?://ok\.ru/profile/\d+|https?://ok\.ru/[a-zA-Z0-9_.]+'
        ok_matches = re.findall(ok_pattern, html)
        if ok_matches:
            results['face_matches'].extend([
                {'platform': 'ok', 'url': url}
                for url in set(ok_matches)
            ])

        # Extract Instagram links
        ig_pattern = r'https?://(?:www\.)?instagram\.com/[a-zA-Z0-9_.]+/?'
        ig_matches = re.findall(ig_pattern, html)
        if ig_matches:
            results['face_matches'].extend([
                {'platform': 'instagram', 'url': url}
                for url in set(ig_matches)
            ])

        # Extract similar image URLs
        img_pattern = r'"origin":"(https?://[^"]+\.(?:jpg|jpeg|png|webp))"'
        img_matches = re.findall(img_pattern, html)
        results['similar_images'] = list(set(img_matches))[:20]

        return results

    def extract_profiles_from_results(self, results: Dict) -> List[Dict]:
        """Extract social media profiles from search results"""
        profiles = []

        for match in results.get('face_matches', []):
            profile = {
                'platform': match['platform'],
                'url': match['url'],
                'confidence': 'yandex_match'
            }
            profiles.append(profile)

        return profiles
```

---

## Summary of New Services Created

| File | Purpose | Dependencies |
|------|---------|--------------|
| `app/services/phase2/mailcat_email_discovery.py` | Username → Email discovery | mailcat (optional) |
| `app/services/phase2/holehe_verification.py` | Email registration verification | holehe |
| `app/services/phase2/russian_phone_validator.py` | Phone validation & carrier ID | None |
| `app/services/phase2/vk_contact_extractor.py` | Extract contacts from VK | requests, beautifulsoup4 |
| `app/services/phase2/yandex_face_search.py` | Photo → Profile via Yandex | requests |

## Required pip installations

```bash
pip install holehe
pip install mailcat  # Optional, has fallback
pip install beautifulsoup4
pip install vkOsint  # Optional for phone→VK lookup
```

## Integration Order

1. **Immediate**: Russian Phone Validator (no dependencies)
2. **Next**: VK Contact Extractor (enhance existing profile scraping)
3. **Then**: Holehe Verification (verify generated emails)
4. **Then**: Mailcat Discovery (generate emails from usernames)
5. **Finally**: Yandex Face Search (automate photo→profile chain)

---

## Sources

- [OSINT Industries - VK Guide](https://www.osint.industries/post/osint-on-vk-find-russian-emails-phone-numbers-and-more)
- [Bellingcat Toolkit](https://bellingcat.gitbook.io/toolkit/)
- [HackYourMom VK OSINT](https://hackyourmom.com/en/osvita/vk/)
- [GitHub - paulpogoda/OSINT-Tools-Russia](https://github.com/paulpogoda/OSINT-Tools-Russia)
- [GitHub - megadose/holehe](https://github.com/megadose/holehe)
- [GitHub - sharsil/mailcat](https://github.com/sharsil/mailcat)
- [GitHub - kovinevmv/getcontact](https://github.com/kovinevmv/getcontact)
- [GitHub - DIJIRO/vkOsint](https://github.com/DIJIRO/vkOsint)
- [Medium - Igor Bederov OSINT](https://medium.com/@ibederov_en)
- [HackMag - Telegram Bots Testing](https://hackmag.com/security/telegram-bots)
- [Wikipedia - Russian Phone Numbers](https://en.wikipedia.org/wiki/Telephone_numbers_in_Russia)
