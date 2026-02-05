"""
Contact Discovery - IBP Prototype B.8
Extract contact information from social media profiles

Features:
- Multi-platform contact extraction (VK, OK, Telegram, etc.)
- Phone number detection and normalization
- Email address extraction
- Messenger links (Telegram, WhatsApp, Viber)
- Website URLs
- Cross-platform profile linking
- Pattern-based contact detection

Requirements:
    pip install requests beautifulsoup4

Usage:
    discovery = ContactDiscovery()
    contacts = discovery.discover_from_vk(vk_id=12345678)
    print(f"Found {len(contacts.phones)} phone numbers")
"""

import os
import re
import json
import time
import logging
import hashlib
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Set, Tuple
from datetime import datetime
from urllib.parse import urlparse, parse_qs
from enum import Enum

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Optional imports
HAS_REQUESTS = False
HAS_BS4 = False

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    logger.warning("requests not installed")

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    logger.warning("beautifulsoup4 not installed")


class Platform(Enum):
    """Social media platforms"""
    VK = "vk"
    OK = "ok"
    TELEGRAM = "telegram"
    WHATSAPP = "whatsapp"
    VIBER = "viber"
    INSTAGRAM = "instagram"
    FACEBOOK = "facebook"
    TWITTER = "twitter"
    YOUTUBE = "youtube"
    TIKTOK = "tiktok"
    LINKEDIN = "linkedin"
    GITHUB = "github"
    UNKNOWN = "unknown"


class ContactType(Enum):
    """Types of contact information"""
    PHONE = "phone"
    EMAIL = "email"
    MESSENGER = "messenger"
    WEBSITE = "website"
    SOCIAL_PROFILE = "social_profile"


@dataclass
class PhoneNumber:
    """Extracted phone number"""
    raw: str
    normalized: str  # E.164 format
    country_code: Optional[str] = None
    is_mobile: bool = True
    source: str = "unknown"
    confidence: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "raw": self.raw,
            "normalized": self.normalized,
            "country_code": self.country_code,
            "is_mobile": self.is_mobile,
            "source": self.source,
            "confidence": self.confidence
        }


@dataclass
class EmailAddress:
    """Extracted email address"""
    email: str
    domain: str
    source: str = "unknown"
    is_personal: bool = True
    confidence: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "email": self.email,
            "domain": self.domain,
            "source": self.source,
            "is_personal": self.is_personal,
            "confidence": self.confidence
        }


@dataclass
class MessengerContact:
    """Messenger/IM contact"""
    platform: Platform
    identifier: str  # username or phone
    url: Optional[str] = None
    source: str = "unknown"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "platform": self.platform.value,
            "identifier": self.identifier,
            "url": self.url,
            "source": self.source
        }


@dataclass
class SocialProfile:
    """Linked social media profile"""
    platform: Platform
    url: str
    username: Optional[str] = None
    user_id: Optional[str] = None
    display_name: Optional[str] = None
    source: str = "unknown"
    confidence: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "platform": self.platform.value,
            "url": self.url,
            "username": self.username,
            "user_id": self.user_id,
            "display_name": self.display_name,
            "source": self.source,
            "confidence": self.confidence
        }


@dataclass
class Website:
    """Website/URL"""
    url: str
    domain: str
    title: Optional[str] = None
    source: str = "unknown"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "url": self.url,
            "domain": self.domain,
            "title": self.title,
            "source": self.source
        }


@dataclass
class ContactInfo:
    """Aggregated contact information"""
    phones: List[PhoneNumber] = field(default_factory=list)
    emails: List[EmailAddress] = field(default_factory=list)
    messengers: List[MessengerContact] = field(default_factory=list)
    social_profiles: List[SocialProfile] = field(default_factory=list)
    websites: List[Website] = field(default_factory=list)

    # Metadata
    source_platform: Optional[Platform] = None
    source_id: Optional[str] = None
    source_url: Optional[str] = None
    extraction_time: datetime = field(default_factory=datetime.now)
    error: Optional[str] = None

    @property
    def total_contacts(self) -> int:
        return (len(self.phones) + len(self.emails) +
                len(self.messengers) + len(self.social_profiles) +
                len(self.websites))

    @property
    def has_contacts(self) -> bool:
        return self.total_contacts > 0

    def merge(self, other: 'ContactInfo'):
        """Merge another ContactInfo into this one"""
        # Merge phones (deduplicate by normalized)
        existing_phones = {p.normalized for p in self.phones}
        for phone in other.phones:
            if phone.normalized not in existing_phones:
                self.phones.append(phone)
                existing_phones.add(phone.normalized)

        # Merge emails (deduplicate)
        existing_emails = {e.email.lower() for e in self.emails}
        for email in other.emails:
            if email.email.lower() not in existing_emails:
                self.emails.append(email)
                existing_emails.add(email.email.lower())

        # Merge messengers
        existing_messengers = {(m.platform, m.identifier) for m in self.messengers}
        for messenger in other.messengers:
            key = (messenger.platform, messenger.identifier)
            if key not in existing_messengers:
                self.messengers.append(messenger)
                existing_messengers.add(key)

        # Merge social profiles (by URL)
        existing_profiles = {p.url for p in self.social_profiles}
        for profile in other.social_profiles:
            if profile.url not in existing_profiles:
                self.social_profiles.append(profile)
                existing_profiles.add(profile.url)

        # Merge websites
        existing_websites = {w.url for w in self.websites}
        for website in other.websites:
            if website.url not in existing_websites:
                self.websites.append(website)
                existing_websites.add(website.url)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "phones": [p.to_dict() for p in self.phones],
            "emails": [e.to_dict() for e in self.emails],
            "messengers": [m.to_dict() for m in self.messengers],
            "social_profiles": [s.to_dict() for s in self.social_profiles],
            "websites": [w.to_dict() for w in self.websites],
            "total_contacts": self.total_contacts,
            "source_platform": self.source_platform.value if self.source_platform else None,
            "source_id": self.source_id,
            "source_url": self.source_url,
            "extraction_time": self.extraction_time.isoformat(),
            "error": self.error
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)


class ContactDiscovery:
    """
    Multi-platform contact information discovery service

    Extracts phone numbers, emails, messenger links, and
    social profile links from various platforms.
    """

    # Phone number patterns
    PHONE_PATTERNS = [
        # Russian numbers
        r'(?:\+7|8)[\s\-\.]?(?:\(?\d{3}\)?[\s\-\.]?){2}\d{2}[\s\-\.]?\d{2}',
        r'(?:\+7|8)[\s\-\.]?\d{10}',
        # International format
        r'\+\d{1,3}[\s\-\.]?\(?\d{2,4}\)?[\s\-\.]?\d{3}[\s\-\.]?\d{2}[\s\-\.]?\d{2}',
        # Generic
        r'\d{3}[\s\-\.]?\d{3}[\s\-\.]?\d{2}[\s\-\.]?\d{2}'
    ]

    # Email pattern
    EMAIL_PATTERN = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'

    # Social platform URL patterns
    SOCIAL_PATTERNS = {
        Platform.VK: [
            r'(?:https?://)?(?:www\.)?vk\.com/([a-zA-Z0-9._]+)',
            r'(?:https?://)?(?:www\.)?vkontakte\.ru/([a-zA-Z0-9._]+)'
        ],
        Platform.OK: [
            r'(?:https?://)?(?:www\.)?ok\.ru/profile/(\d+)',
            r'(?:https?://)?(?:www\.)?odnoklassniki\.ru/profile/(\d+)'
        ],
        Platform.TELEGRAM: [
            r'(?:https?://)?(?:www\.)?t\.me/([a-zA-Z0-9_]+)',
            r'(?:https?://)?(?:www\.)?telegram\.me/([a-zA-Z0-9_]+)',
            r'@([a-zA-Z][a-zA-Z0-9_]{4,})'
        ],
        Platform.WHATSAPP: [
            r'(?:https?://)?(?:www\.)?wa\.me/(\d+)',
            r'(?:https?://)?(?:api\.)?whatsapp\.com/send\?phone=(\d+)'
        ],
        Platform.VIBER: [
            r'(?:https?://)?(?:www\.)?viber\.com/([a-zA-Z0-9_]+)',
        ],
        Platform.INSTAGRAM: [
            r'(?:https?://)?(?:www\.)?instagram\.com/([a-zA-Z0-9._]+)',
            r'(?:https?://)?(?:www\.)?instagr\.am/([a-zA-Z0-9._]+)'
        ],
        Platform.FACEBOOK: [
            r'(?:https?://)?(?:www\.)?facebook\.com/([a-zA-Z0-9.]+)',
            r'(?:https?://)?(?:www\.)?fb\.com/([a-zA-Z0-9.]+)'
        ],
        Platform.TWITTER: [
            r'(?:https?://)?(?:www\.)?twitter\.com/([a-zA-Z0-9_]+)',
            r'(?:https?://)?(?:www\.)?x\.com/([a-zA-Z0-9_]+)'
        ],
        Platform.YOUTUBE: [
            r'(?:https?://)?(?:www\.)?youtube\.com/(?:user|channel|c)/([a-zA-Z0-9_-]+)',
            r'(?:https?://)?(?:www\.)?youtube\.com/@([a-zA-Z0-9_-]+)'
        ],
        Platform.TIKTOK: [
            r'(?:https?://)?(?:www\.)?tiktok\.com/@([a-zA-Z0-9._]+)'
        ],
        Platform.LINKEDIN: [
            r'(?:https?://)?(?:www\.)?linkedin\.com/in/([a-zA-Z0-9_-]+)'
        ],
        Platform.GITHUB: [
            r'(?:https?://)?(?:www\.)?github\.com/([a-zA-Z0-9_-]+)'
        ]
    }

    # Messenger platforms
    MESSENGER_PLATFORMS = {Platform.TELEGRAM, Platform.WHATSAPP, Platform.VIBER}

    def __init__(
        self,
        vk_token: Optional[str] = None,
        demo_mode: bool = False
    ):
        """
        Initialize contact discovery service

        Args:
            vk_token: VK API access token for deeper extraction
            demo_mode: Force demo mode
        """
        self.vk_token = vk_token or os.getenv("VK_API_TOKEN")
        self.demo_mode = demo_mode or not HAS_REQUESTS
        self.session: Optional['requests.Session'] = None

        if not self.demo_mode and HAS_REQUESTS:
            self.session = requests.Session()
            self.session.headers.update({
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })

        if self.demo_mode:
            logger.info("Running in DEMO mode")

    def normalize_phone(self, phone: str) -> str:
        """Normalize phone number to E.164 format"""
        # Remove all non-digit characters except leading +
        digits = re.sub(r'[^\d]', '', phone)

        # Handle Russian numbers
        if digits.startswith('8') and len(digits) == 11:
            digits = '7' + digits[1:]
        elif len(digits) == 10 and not phone.startswith('+'):
            # Assume Russian number
            digits = '7' + digits

        return '+' + digits

    def extract_phones(self, text: str, source: str = "text") -> List[PhoneNumber]:
        """Extract phone numbers from text"""
        phones = []
        seen = set()

        for pattern in self.PHONE_PATTERNS:
            matches = re.findall(pattern, text)
            for match in matches:
                raw = match if isinstance(match, str) else match[0]
                normalized = self.normalize_phone(raw)

                if normalized not in seen and len(normalized) >= 10:
                    seen.add(normalized)

                    # Determine country code
                    country_code = None
                    if normalized.startswith('+7'):
                        country_code = "RU"
                    elif normalized.startswith('+1'):
                        country_code = "US"
                    elif normalized.startswith('+44'):
                        country_code = "GB"

                    phones.append(PhoneNumber(
                        raw=raw,
                        normalized=normalized,
                        country_code=country_code,
                        source=source
                    ))

        return phones

    def extract_emails(self, text: str, source: str = "text") -> List[EmailAddress]:
        """Extract email addresses from text"""
        emails = []
        seen = set()

        matches = re.findall(self.EMAIL_PATTERN, text, re.IGNORECASE)
        for email in matches:
            email_lower = email.lower()
            if email_lower not in seen:
                seen.add(email_lower)

                domain = email.split('@')[1].lower()
                is_personal = domain in [
                    'gmail.com', 'yandex.ru', 'mail.ru', 'yahoo.com',
                    'outlook.com', 'hotmail.com', 'icloud.com', 'rambler.ru'
                ]

                emails.append(EmailAddress(
                    email=email,
                    domain=domain,
                    source=source,
                    is_personal=is_personal
                ))

        return emails

    def extract_social_links(
        self,
        text: str,
        source: str = "text"
    ) -> Tuple[List[SocialProfile], List[MessengerContact]]:
        """Extract social media and messenger links from text"""
        profiles = []
        messengers = []
        seen_urls = set()

        for platform, patterns in self.SOCIAL_PATTERNS.items():
            for pattern in patterns:
                matches = re.finditer(pattern, text, re.IGNORECASE)
                for match in matches:
                    identifier = match.group(1)
                    full_match = match.group(0)

                    # Build URL if not complete
                    if full_match.startswith('http'):
                        url = full_match
                    elif full_match.startswith('@'):
                        if platform == Platform.TELEGRAM:
                            url = f"https://t.me/{identifier}"
                        else:
                            continue
                    else:
                        url = f"https://{full_match}"

                    if url in seen_urls:
                        continue
                    seen_urls.add(url)

                    # Categorize as messenger or social profile
                    if platform in self.MESSENGER_PLATFORMS:
                        messengers.append(MessengerContact(
                            platform=platform,
                            identifier=identifier,
                            url=url,
                            source=source
                        ))
                    else:
                        profiles.append(SocialProfile(
                            platform=platform,
                            url=url,
                            username=identifier,
                            source=source
                        ))

        return profiles, messengers

    def extract_websites(self, text: str, source: str = "text") -> List[Website]:
        """Extract website URLs from text"""
        websites = []
        seen = set()

        # URL pattern (exclude social media)
        url_pattern = r'https?://(?:www\.)?([a-zA-Z0-9][-a-zA-Z0-9]*(?:\.[a-zA-Z0-9][-a-zA-Z0-9]*)+)(?:/[^\s]*)?'

        # Social domains to exclude
        social_domains = {
            'vk.com', 'vkontakte.ru', 'ok.ru', 'odnoklassniki.ru',
            't.me', 'telegram.me', 'wa.me', 'whatsapp.com',
            'instagram.com', 'facebook.com', 'fb.com',
            'twitter.com', 'x.com', 'youtube.com', 'tiktok.com',
            'linkedin.com', 'github.com', 'viber.com'
        }

        matches = re.finditer(url_pattern, text, re.IGNORECASE)
        for match in matches:
            url = match.group(0)
            domain = match.group(1).lower()

            if domain in seen or domain in social_domains:
                continue
            seen.add(domain)

            websites.append(Website(
                url=url,
                domain=domain,
                source=source
            ))

        return websites

    def discover_from_text(self, text: str, source: str = "text") -> ContactInfo:
        """
        Extract all contact information from text

        Args:
            text: Text to analyze
            source: Source identifier

        Returns:
            ContactInfo with all extracted contacts
        """
        contacts = ContactInfo()

        contacts.phones = self.extract_phones(text, source)
        contacts.emails = self.extract_emails(text, source)

        profiles, messengers = self.extract_social_links(text, source)
        contacts.social_profiles = profiles
        contacts.messengers = messengers

        contacts.websites = self.extract_websites(text, source)

        return contacts

    def discover_from_vk(
        self,
        vk_id: Optional[int] = None,
        vk_url: Optional[str] = None
    ) -> ContactInfo:
        """
        Discover contacts from VK profile

        Args:
            vk_id: VK user ID
            vk_url: VK profile URL

        Returns:
            ContactInfo with extracted contacts
        """
        if self.demo_mode:
            return self._demo_discover_vk(vk_id or 12345678)

        contacts = ContactInfo(
            source_platform=Platform.VK,
            source_id=str(vk_id) if vk_id else None,
            source_url=vk_url
        )

        # Extract ID from URL if needed
        if not vk_id and vk_url:
            match = re.search(r'vk\.com/(?:id)?(\d+)', vk_url)
            if match:
                vk_id = int(match.group(1))

        if not vk_id:
            contacts.error = "VK ID or URL required"
            return contacts

        try:
            # Use VK API if token available
            if self.vk_token:
                return self._discover_vk_api(vk_id, contacts)
            else:
                return self._discover_vk_scrape(vk_id, contacts)

        except Exception as e:
            contacts.error = str(e)
            logger.error(f"VK discovery error: {e}")
            return contacts

    def _discover_vk_api(self, vk_id: int, contacts: ContactInfo) -> ContactInfo:
        """Discover using VK API"""
        api_url = "https://api.vk.com/method/users.get"

        params = {
            "user_ids": vk_id,
            "fields": "contacts,connections,site,about,status",
            "access_token": self.vk_token,
            "v": "5.131"
        }

        response = self.session.get(api_url, params=params, timeout=30)
        data = response.json()

        if "error" in data:
            contacts.error = data["error"].get("error_msg", "API error")
            return contacts

        if not data.get("response"):
            return contacts

        user = data["response"][0]
        contacts.source_id = str(user.get("id", vk_id))

        # Extract phone
        mobile = user.get("mobile_phone", "")
        home = user.get("home_phone", "")

        for phone_text in [mobile, home]:
            if phone_text:
                phones = self.extract_phones(phone_text, "vk_profile")
                contacts.phones.extend(phones)

        # Extract site
        site = user.get("site", "")
        if site:
            websites = self.extract_websites(site, "vk_profile")
            contacts.websites.extend(websites)

            # Also check for social links in site field
            profiles, messengers = self.extract_social_links(site, "vk_profile")
            contacts.social_profiles.extend(profiles)
            contacts.messengers.extend(messengers)

        # Extract from status
        status = user.get("status", "")
        if status:
            status_contacts = self.discover_from_text(status, "vk_status")
            contacts.merge(status_contacts)

        # Extract connections (Telegram, etc.)
        if "twitter" in user:
            contacts.social_profiles.append(SocialProfile(
                platform=Platform.TWITTER,
                url=f"https://twitter.com/{user['twitter']}",
                username=user["twitter"],
                source="vk_connections"
            ))

        if "instagram" in user:
            contacts.social_profiles.append(SocialProfile(
                platform=Platform.INSTAGRAM,
                url=f"https://instagram.com/{user['instagram']}",
                username=user["instagram"],
                source="vk_connections"
            ))

        if "skype" in user:
            contacts.messengers.append(MessengerContact(
                platform=Platform.UNKNOWN,
                identifier=user["skype"],
                source="vk_connections"
            ))

        return contacts

    def _discover_vk_scrape(self, vk_id: int, contacts: ContactInfo) -> ContactInfo:
        """Discover by scraping VK profile page"""
        url = f"https://vk.com/id{vk_id}"
        contacts.source_url = url

        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()

            if HAS_BS4:
                soup = BeautifulSoup(response.text, "html.parser")

                # Look for contact sections
                contact_sections = soup.select(".profile_info_row, .labeled")
                for section in contact_sections:
                    text = section.get_text()
                    section_contacts = self.discover_from_text(text, "vk_profile")
                    contacts.merge(section_contacts)

        except Exception as e:
            contacts.error = str(e)

        return contacts

    def discover_from_ok(
        self,
        ok_id: Optional[str] = None,
        ok_url: Optional[str] = None
    ) -> ContactInfo:
        """
        Discover contacts from OK.ru profile

        Args:
            ok_id: OK.ru profile ID
            ok_url: OK.ru profile URL

        Returns:
            ContactInfo with extracted contacts
        """
        if self.demo_mode:
            return self._demo_discover_ok(ok_id or "123456789")

        contacts = ContactInfo(
            source_platform=Platform.OK,
            source_id=ok_id,
            source_url=ok_url
        )

        if not ok_id and ok_url:
            match = re.search(r'ok\.ru/profile/(\d+)', ok_url)
            if match:
                ok_id = match.group(1)

        if not ok_id:
            contacts.error = "OK.ru ID or URL required"
            return contacts

        try:
            url = ok_url or f"https://ok.ru/profile/{ok_id}"
            response = self.session.get(url, timeout=30)

            if HAS_BS4:
                soup = BeautifulSoup(response.text, "html.parser")

                # Extract from various profile sections
                for section in soup.select(".profile-info, .user-info, .contacts"):
                    text = section.get_text()
                    section_contacts = self.discover_from_text(text, "ok_profile")
                    contacts.merge(section_contacts)

        except Exception as e:
            contacts.error = str(e)

        return contacts

    # Demo mode implementations
    def _demo_discover_vk(self, vk_id: int) -> ContactInfo:
        """Simulated VK discovery"""
        id_hash = hashlib.md5(str(vk_id).encode()).hexdigest()

        contacts = ContactInfo(
            source_platform=Platform.VK,
            source_id=str(vk_id),
            source_url=f"https://vk.com/id{vk_id}"
        )

        # Generate demo phone
        if int(id_hash[0], 16) > 6:
            phone = f"+7916{id_hash[:7]}"[:12]
            contacts.phones.append(PhoneNumber(
                raw=phone,
                normalized=phone,
                country_code="RU",
                source="vk_profile"
            ))

        # Generate demo email
        if int(id_hash[1], 16) > 5:
            email = f"user{vk_id}@mail.ru"
            contacts.emails.append(EmailAddress(
                email=email,
                domain="mail.ru",
                source="vk_profile"
            ))

        # Generate Telegram link
        if int(id_hash[2], 16) > 7:
            tg_user = f"user_{id_hash[:6]}"
            contacts.messengers.append(MessengerContact(
                platform=Platform.TELEGRAM,
                identifier=tg_user,
                url=f"https://t.me/{tg_user}",
                source="vk_profile"
            ))

        # Generate Instagram link
        if int(id_hash[3], 16) > 8:
            ig_user = f"user.{id_hash[:8]}"
            contacts.social_profiles.append(SocialProfile(
                platform=Platform.INSTAGRAM,
                url=f"https://instagram.com/{ig_user}",
                username=ig_user,
                source="vk_connections"
            ))

        return contacts

    def _demo_discover_ok(self, ok_id: str) -> ContactInfo:
        """Simulated OK discovery"""
        id_hash = hashlib.md5(ok_id.encode()).hexdigest()

        contacts = ContactInfo(
            source_platform=Platform.OK,
            source_id=ok_id,
            source_url=f"https://ok.ru/profile/{ok_id}"
        )

        if int(id_hash[0], 16) > 5:
            phone = f"+7903{id_hash[:7]}"[:12]
            contacts.phones.append(PhoneNumber(
                raw=phone,
                normalized=phone,
                country_code="RU",
                source="ok_profile"
            ))

        if int(id_hash[1], 16) > 6:
            email = f"ok_{ok_id}@yandex.ru"
            contacts.emails.append(EmailAddress(
                email=email,
                domain="yandex.ru",
                source="ok_profile"
            ))

        return contacts


def demo():
    """Demonstrate contact discovery capabilities"""
    print("=" * 60)
    print("Contact Discovery - IBP Prototype B.8")
    print("=" * 60)
    print()

    # Initialize in demo mode
    discovery = ContactDiscovery(demo_mode=True)

    print("Demo Mode - Simulated Contact Discovery")
    print("-" * 40)

    # Test text extraction
    test_text = """
    Связаться со мной:
    Телефон: +7 (916) 123-45-67
    Email: ivan.petrov@gmail.com
    Telegram: @ivan_petrov_123
    Instagram: https://instagram.com/ivan.petrov
    Мой сайт: https://ivan-petrov.ru
    WhatsApp: https://wa.me/79161234567
    """

    print("\nText Extraction:")
    print("-" * 40)

    contacts = discovery.discover_from_text(test_text, "test")

    print(f"Phones found: {len(contacts.phones)}")
    for phone in contacts.phones:
        print(f"  - {phone.normalized}")

    print(f"\nEmails found: {len(contacts.emails)}")
    for email in contacts.emails:
        print(f"  - {email.email}")

    print(f"\nMessengers found: {len(contacts.messengers)}")
    for msg in contacts.messengers:
        print(f"  - {msg.platform.value}: {msg.identifier}")

    print(f"\nSocial profiles found: {len(contacts.social_profiles)}")
    for profile in contacts.social_profiles:
        print(f"  - {profile.platform.value}: {profile.url}")

    print(f"\nWebsites found: {len(contacts.websites)}")
    for site in contacts.websites:
        print(f"  - {site.url}")

    # Test VK discovery
    print("\n\nVK Profile Discovery:")
    print("-" * 40)

    vk_contacts = discovery.discover_from_vk(vk_id=12345678)
    print(f"Source: {vk_contacts.source_url}")
    print(f"Total contacts: {vk_contacts.total_contacts}")

    for phone in vk_contacts.phones:
        print(f"  Phone: {phone.normalized}")
    for email in vk_contacts.emails:
        print(f"  Email: {email.email}")
    for msg in vk_contacts.messengers:
        print(f"  Messenger: {msg.platform.value}: {msg.identifier}")

    print("\n" + "=" * 60)
    print("Usage Example:")
    print("-" * 40)
    print("""
from contact_discovery import ContactDiscovery

# Initialize
discovery = ContactDiscovery(vk_token="your_vk_token")

# Discover from VK profile
contacts = discovery.discover_from_vk(vk_id=12345678)

print(f"Found {len(contacts.phones)} phone(s)")
for phone in contacts.phones:
    print(f"  {phone.normalized}")

print(f"Found {len(contacts.emails)} email(s)")
for email in contacts.emails:
    print(f"  {email.email}")

# Discover from OK.ru profile
contacts = discovery.discover_from_ok(ok_id="123456789")

# Extract from arbitrary text
text = "Contact me: +7-916-123-4567 or email@example.com"
contacts = discovery.discover_from_text(text)

# Merge results from multiple sources
all_contacts = ContactInfo()
all_contacts.merge(discovery.discover_from_vk(vk_id=123))
all_contacts.merge(discovery.discover_from_ok(ok_id="456"))

print(f"Total unique contacts: {all_contacts.total_contacts}")
""")

    print("\n" + "=" * 60)
    print("\nJSON Output Example:")
    print("-" * 40)
    print(vk_contacts.to_json())


if __name__ == "__main__":
    demo()
