"""
VK Wall Post Contact Extractor
==============================
Extract contact information from VK wall posts.
Searches for phone numbers, emails, and contact mentions in:
- User's own wall posts
- Comments on posts
- Bio/status updates

Based on: OSINT techniques for VK contact discovery
"""

import re
import requests
from typing import List, Dict, Optional, Set
from dataclasses import dataclass, field
import logging
from bs4 import BeautifulSoup
import time

logger = logging.getLogger(__name__)


@dataclass
class ExtractedContact:
    """A contact found in VK content."""
    value: str  # Phone number or email
    contact_type: str  # 'phone' or 'email'
    source: str  # Where it was found
    context: str  # Surrounding text
    confidence: str  # 'high', 'medium', 'low'
    post_url: Optional[str] = None
    post_date: Optional[str] = None


@dataclass
class WallExtractionResult:
    """Results from wall extraction."""
    profile_url: str
    phones: List[ExtractedContact] = field(default_factory=list)
    emails: List[ExtractedContact] = field(default_factory=list)
    telegram_usernames: List[str] = field(default_factory=list)
    instagram_usernames: List[str] = field(default_factory=list)
    other_contacts: List[Dict] = field(default_factory=list)
    posts_analyzed: int = 0
    errors: List[str] = field(default_factory=list)


class VKWallExtractor:
    """
    Extract contacts from VK wall posts.

    Searches public posts for:
    - Phone numbers in various formats
    - Email addresses
    - Telegram/WhatsApp usernames
    - Contact mentions
    """

    # Russian phone patterns (more comprehensive)
    PHONE_PATTERNS = [
        # International format with country code
        r'\+7\s*[\(\-]?\s*(\d{3})\s*[\)\-]?\s*(\d{3})\s*[\-]?\s*(\d{2})\s*[\-]?\s*(\d{2})',
        # Domestic format starting with 8
        r'8\s*[\(\-]?\s*(\d{3})\s*[\)\-]?\s*(\d{3})\s*[\-]?\s*(\d{2})\s*[\-]?\s*(\d{2})',
        # Plain digits
        r'\+7(\d{10})',
        r'8(\d{10})',
        # With "тел" prefix
        r'(?:тел\.?|телефон|phone|моб\.?)[\s:]*(\+?[78][\s\-\(\)]?\d{3}[\s\-\(\)]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2})',
    ]

    # Email patterns
    EMAIL_PATTERNS = [
        r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
        # With "почта" prefix
        r'(?:почта|email|e-mail|mail)[\s:]*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
    ]

    # Telegram patterns
    TELEGRAM_PATTERNS = [
        r't\.me/([a-zA-Z0-9_]{5,32})',
        r'telegram\.me/([a-zA-Z0-9_]{5,32})',
        r'(?:telegram|тг|tg)[\s:]*@?([a-zA-Z0-9_]{5,32})',
        r'@([a-zA-Z][a-zA-Z0-9_]{4,31})',  # Generic @username
    ]

    # WhatsApp patterns
    WHATSAPP_PATTERNS = [
        r'(?:whatsapp|wa|вотсап|вацап)[\s:]*(\+?[78][\d\s\-\(\)]{10,15})',
        r'wa\.me/(\d+)',
    ]

    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml',
        'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
    }

    def __init__(self, access_token: Optional[str] = None):
        """
        Initialize wall extractor.

        Args:
            access_token: VK API access token (optional, for API access)
        """
        self.access_token = access_token
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)

    def extract_from_profile(
        self,
        profile_url: str,
        max_posts: int = 50
    ) -> WallExtractionResult:
        """
        Extract contacts from VK profile wall.

        Args:
            profile_url: VK profile URL
            max_posts: Maximum posts to analyze

        Returns:
            WallExtractionResult with found contacts
        """
        result = WallExtractionResult(profile_url=profile_url)

        # Extract user ID from URL
        user_id = self._extract_user_id(profile_url)
        if not user_id:
            result.errors.append("Could not extract user ID from URL")
            return result

        # Try API first if token available
        if self.access_token:
            api_result = self._extract_via_api(user_id, max_posts)
            if api_result:
                return api_result

        # Fallback to web scraping
        return self._extract_via_scraping(profile_url, max_posts, result)

    def _extract_user_id(self, url: str) -> Optional[str]:
        """Extract VK user ID or screen name from URL."""
        patterns = [
            r'vk\.com/id(\d+)',
            r'vk\.com/([a-zA-Z0-9_.]+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    def _extract_via_api(
        self,
        user_id: str,
        max_posts: int
    ) -> Optional[WallExtractionResult]:
        """Extract wall posts via VK API."""
        if not self.access_token:
            return None

        result = WallExtractionResult(
            profile_url=f"https://vk.com/{user_id}"
        )

        try:
            # Get wall posts
            params = {
                'owner_id': user_id if user_id.isdigit() else None,
                'domain': user_id if not user_id.isdigit() else None,
                'count': min(max_posts, 100),
                'access_token': self.access_token,
                'v': '5.199',
            }

            response = self.session.get(
                'https://api.vk.com/method/wall.get',
                params={k: v for k, v in params.items() if v},
                timeout=15
            )

            data = response.json()
            if 'response' not in data:
                return None

            posts = data['response'].get('items', [])
            result.posts_analyzed = len(posts)

            # Analyze each post
            for post in posts:
                text = post.get('text', '')
                post_id = post.get('id')
                post_date = post.get('date')
                post_url = f"https://vk.com/wall{post.get('owner_id')}_{post_id}"

                self._extract_contacts_from_text(
                    text, result,
                    source='VK wall post',
                    post_url=post_url,
                    post_date=str(post_date) if post_date else None
                )

            return result

        except Exception as e:
            logger.error(f"VK API extraction error: {e}")
            return None

    def _extract_via_scraping(
        self,
        profile_url: str,
        max_posts: int,
        result: WallExtractionResult
    ) -> WallExtractionResult:
        """Extract wall posts by scraping (limited without login)."""
        try:
            # Try to access public wall
            response = self.session.get(profile_url, timeout=15)

            if response.status_code != 200:
                result.errors.append(f"HTTP {response.status_code}")
                return result

            soup = BeautifulSoup(response.text, 'html.parser')

            # Find wall posts
            post_elements = soup.select('.wall_post_text, .post_content, .wall_text')

            result.posts_analyzed = min(len(post_elements), max_posts)

            for i, post in enumerate(post_elements[:max_posts]):
                text = post.get_text(separator=' ')
                self._extract_contacts_from_text(
                    text, result,
                    source='VK wall post (scraped)',
                    post_url=None
                )

            # Also check profile info sections
            info_sections = soup.select(
                '.profile_info_row, .page_info_row, .pp_info, '
                '.profile_info_block, .page_block_header_extra'
            )

            for section in info_sections:
                text = section.get_text(separator=' ')
                self._extract_contacts_from_text(
                    text, result,
                    source='VK profile info'
                )

            # Check status
            status = soup.select_one('.page_status, .profile_info_status')
            if status:
                self._extract_contacts_from_text(
                    status.get_text(),
                    result,
                    source='VK status'
                )

        except Exception as e:
            result.errors.append(str(e))
            logger.error(f"VK scraping error: {e}")

        return result

    def _extract_contacts_from_text(
        self,
        text: str,
        result: WallExtractionResult,
        source: str,
        post_url: Optional[str] = None,
        post_date: Optional[str] = None
    ):
        """Extract all contact types from text."""
        if not text:
            return

        # Extract phones
        for pattern in self.PHONE_PATTERNS:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                phone = match.group()
                # Normalize phone
                phone_digits = re.sub(r'\D', '', phone)
                if len(phone_digits) >= 10:
                    # Get context (surrounding 50 chars)
                    start = max(0, match.start() - 25)
                    end = min(len(text), match.end() + 25)
                    context = text[start:end].strip()

                    contact = ExtractedContact(
                        value=self._normalize_phone(phone_digits),
                        contact_type='phone',
                        source=source,
                        context=context,
                        confidence='high' if 'тел' in text.lower() or 'phone' in text.lower() else 'medium',
                        post_url=post_url,
                        post_date=post_date
                    )

                    # Avoid duplicates
                    if not any(p.value == contact.value for p in result.phones):
                        result.phones.append(contact)

        # Extract emails
        for pattern in self.EMAIL_PATTERNS:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                email = match.group() if '@' in match.group() else match.group(1)
                email = email.lower()

                # Filter garbage
                if any(x in email for x in ['.png', '.jpg', '.gif', 'example']):
                    continue

                start = max(0, match.start() - 25)
                end = min(len(text), match.end() + 25)
                context = text[start:end].strip()

                contact = ExtractedContact(
                    value=email,
                    contact_type='email',
                    source=source,
                    context=context,
                    confidence='high' if 'почта' in text.lower() or 'email' in text.lower() else 'medium',
                    post_url=post_url,
                    post_date=post_date
                )

                if not any(e.value == contact.value for e in result.emails):
                    result.emails.append(contact)

        # Extract Telegram usernames
        for pattern in self.TELEGRAM_PATTERNS:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                username = match.group(1) if match.lastindex else match.group()
                username = username.lstrip('@').lower()

                if len(username) >= 5 and username not in result.telegram_usernames:
                    result.telegram_usernames.append(username)

        # Extract WhatsApp mentions
        for pattern in self.WHATSAPP_PATTERNS:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                wa_contact = match.group(1) if match.lastindex else match.group()
                result.other_contacts.append({
                    'type': 'whatsapp',
                    'value': wa_contact,
                    'source': source
                })

    def _normalize_phone(self, digits: str) -> str:
        """Normalize phone to +7 (XXX) XXX-XX-XX format."""
        if len(digits) == 11:
            if digits.startswith('8'):
                digits = '7' + digits[1:]
            return f"+{digits[0]} ({digits[1:4]}) {digits[4:7]}-{digits[7:9]}-{digits[9:11]}"
        elif len(digits) == 10:
            return f"+7 ({digits[0:3]}) {digits[3:6]}-{digits[6:8]}-{digits[8:10]}"
        return digits

    def extract_from_multiple_profiles(
        self,
        profile_urls: List[str],
        max_posts_each: int = 30
    ) -> List[WallExtractionResult]:
        """Extract contacts from multiple VK profiles."""
        results = []
        for url in profile_urls:
            result = self.extract_from_profile(url, max_posts_each)
            results.append(result)
            time.sleep(0.5)  # Rate limiting
        return results


def extract_vk_wall_contacts(
    profile_url: str,
    access_token: Optional[str] = None
) -> WallExtractionResult:
    """Convenience function for single profile extraction."""
    extractor = VKWallExtractor(access_token=access_token)
    return extractor.extract_from_profile(profile_url)


def extract_multiple_vk_wall_contacts(
    profile_urls: List[str],
    access_token: Optional[str] = None
) -> List[WallExtractionResult]:
    """Convenience function for multiple profile extraction."""
    extractor = VKWallExtractor(access_token=access_token)
    return extractor.extract_from_multiple_profiles(profile_urls)
