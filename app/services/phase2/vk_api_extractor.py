"""
VK API Contact Extractor
========================
Extract contact information from VK profiles using the VK API.
More reliable than web scraping when API access is available.

Features:
- Extract phone/email from profile contacts field
- Extract linked social accounts (Telegram, Instagram, etc.)
- Extract website links
- Works with VK user IDs and screen names

Based on: https://vk.com/dev/users.get
"""

import re
import requests
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class VKContact:
    """Contact information extracted from VK profile."""
    user_id: int = 0
    screen_name: str = ''
    profile_url: str = ''

    # Direct contacts
    phones: List[str] = field(default_factory=list)
    emails: List[str] = field(default_factory=list)

    # Linked accounts
    telegram: Optional[str] = None
    instagram: Optional[str] = None
    twitter: Optional[str] = None
    facebook: Optional[str] = None
    skype: Optional[str] = None

    # Other
    websites: List[str] = field(default_factory=list)
    bio: str = ''

    # Metadata
    is_private: bool = False
    error: Optional[str] = None


class VKAPIExtractor:
    """
    Extract contacts from VK profiles using VK API.

    Usage:
        extractor = VKAPIExtractor(access_token='your_token')
        contact = extractor.extract_from_url('https://vk.com/durov')
    """

    API_VERSION = '5.199'
    API_BASE = 'https://api.vk.com/method/'

    # Fields to request from VK API
    USER_FIELDS = [
        'contacts',          # Phone numbers
        'connections',       # Linked services (Skype, etc.)
        'site',              # Personal website
        'status',            # Status (may contain contacts)
        'about',             # About section
        'activities',        # Activities
        'interests',         # Interests
        'mobile_phone',      # Mobile phone
        'home_phone',        # Home phone
        'screen_name',       # Screen name
        'domain',            # Domain
    ]

    def __init__(self, access_token: Optional[str] = None):
        """
        Initialize VK API extractor.

        Args:
            access_token: VK API access token (optional for public data)
        """
        self.access_token = access_token
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'IBP-OSINT/1.0',
            'Accept': 'application/json',
        })

    def extract_from_url(self, profile_url: str) -> VKContact:
        """
        Extract contact info from VK profile URL.

        Args:
            profile_url: VK profile URL (e.g., https://vk.com/durov or https://vk.com/id1)

        Returns:
            VKContact with extracted information
        """
        result = VKContact(profile_url=profile_url)

        # Extract user identifier from URL
        user_id = self._extract_user_id(profile_url)
        if not user_id:
            result.error = 'Could not extract user ID from URL'
            return result

        # Try API first
        api_result = self._fetch_via_api(user_id)
        if api_result:
            return api_result

        # Fallback to web scraping
        return self._fetch_via_scraping(profile_url, result)

    def extract_from_id(self, user_id: str) -> VKContact:
        """
        Extract contact info using VK user ID or screen name.

        Args:
            user_id: Numeric ID (e.g., '1') or screen name (e.g., 'durov')

        Returns:
            VKContact with extracted information
        """
        return self._fetch_via_api(user_id) or VKContact(error='Failed to fetch user data')

    def extract_from_multiple(self, profile_urls: List[str]) -> List[VKContact]:
        """
        Extract contacts from multiple VK profiles.

        Args:
            profile_urls: List of VK profile URLs

        Returns:
            List of VKContact for each URL
        """
        results = []
        for url in profile_urls:
            result = self.extract_from_url(url)
            results.append(result)
        return results

    def _extract_user_id(self, url: str) -> Optional[str]:
        """Extract VK user ID or screen name from URL."""
        patterns = [
            r'vk\.com/id(\d+)',           # Numeric ID: vk.com/id1
            r'vk\.com/([a-zA-Z0-9_.]+)',  # Screen name: vk.com/durov
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)

        return None

    def _fetch_via_api(self, user_id: str) -> Optional[VKContact]:
        """Fetch user data via VK API."""
        try:
            params = {
                'user_ids': user_id,
                'fields': ','.join(self.USER_FIELDS),
                'v': self.API_VERSION,
            }

            if self.access_token:
                params['access_token'] = self.access_token

            response = self.session.get(
                f'{self.API_BASE}users.get',
                params=params,
                timeout=10
            )
            response.raise_for_status()

            data = response.json()

            if 'error' in data:
                error = data['error']
                logger.warning(f"VK API error: {error.get('error_msg', 'Unknown error')}")
                return None

            if 'response' not in data or not data['response']:
                return None

            user = data['response'][0]
            return self._parse_user_data(user)

        except requests.exceptions.Timeout:
            logger.warning("VK API timeout")
            return None
        except Exception as e:
            logger.error(f"VK API error: {e}")
            return None

    def _parse_user_data(self, user: Dict[str, Any]) -> VKContact:
        """Parse VK API user response into VKContact."""
        result = VKContact()

        # Basic info
        result.user_id = user.get('id', 0)
        result.screen_name = user.get('screen_name') or user.get('domain', '')
        result.profile_url = f"https://vk.com/id{result.user_id}"

        if result.screen_name:
            result.profile_url = f"https://vk.com/{result.screen_name}"

        # Check if profile is deactivated/private
        if user.get('deactivated'):
            result.is_private = True
            return result

        # Extract phones
        phones = []
        if user.get('mobile_phone'):
            phones.append(user['mobile_phone'])
        if user.get('home_phone'):
            phones.append(user['home_phone'])

        # Also check contacts field
        if 'contacts' in user:
            contacts = user['contacts']
            if contacts.get('mobile_phone'):
                phones.append(contacts['mobile_phone'])
            if contacts.get('home_phone'):
                phones.append(contacts['home_phone'])

        result.phones = list(set(p for p in phones if p and len(p) > 5))

        # Extract connections (linked services)
        if 'connections' in user:
            conn = user['connections']
            result.skype = conn.get('skype')
            result.facebook = conn.get('facebook')
            result.twitter = conn.get('twitter')
            result.instagram = conn.get('instagram')

            # Livejournal, etc. less useful but could be added

        # Extract website
        if user.get('site'):
            sites = user['site'].split(',')
            result.websites = [s.strip() for s in sites if s.strip()]

        # Extract bio/about for text analysis
        bio_parts = []
        if user.get('about'):
            bio_parts.append(user['about'])
        if user.get('status'):
            bio_parts.append(user['status'])
        if user.get('activities'):
            bio_parts.append(user['activities'])
        if user.get('interests'):
            bio_parts.append(user['interests'])

        result.bio = ' '.join(bio_parts)

        # Extract contacts from bio text
        self._extract_contacts_from_bio(result)

        return result

    def _extract_contacts_from_bio(self, contact: VKContact):
        """Extract additional contacts from bio text."""
        if not contact.bio:
            return

        text = contact.bio

        # Extract phones from bio
        phone_patterns = [
            r'\+7[\s\-\(]?\d{3}[\s\-\)]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}',
            r'8[\s\-\(]?\d{3}[\s\-\)]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}',
        ]
        for pattern in phone_patterns:
            matches = re.findall(pattern, text)
            for phone in matches:
                if phone not in contact.phones:
                    contact.phones.append(phone)

        # Extract emails from bio
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        emails = re.findall(email_pattern, text, re.IGNORECASE)
        for email in emails:
            email_lower = email.lower()
            # Filter garbage
            if not any(ext in email_lower for ext in ['.png', '.jpg', '.gif']):
                if email_lower not in contact.emails:
                    contact.emails.append(email_lower)

        # Extract Telegram from bio
        if not contact.telegram:
            tg_patterns = [
                r't\.me/([a-zA-Z0-9_]{5,32})',
                r'telegram\.me/([a-zA-Z0-9_]{5,32})',
                r'@([a-zA-Z][a-zA-Z0-9_]{4,31})',  # @username format
            ]
            for pattern in tg_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    contact.telegram = match.group(1)
                    break

        # Extract Instagram from bio
        if not contact.instagram:
            ig_patterns = [
                r'instagram\.com/([a-zA-Z0-9_.]+)',
                r'inst?a?:?\s*@?([a-zA-Z0-9_.]{3,30})',
            ]
            for pattern in ig_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    contact.instagram = match.group(1)
                    break

    def _fetch_via_scraping(self, url: str, result: VKContact) -> VKContact:
        """Fallback: scrape VK profile page."""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
            }

            response = self.session.get(url, headers=headers, timeout=15)

            if response.status_code != 200:
                result.error = f'HTTP {response.status_code}'
                return result

            html = response.text

            # Extract basic info from HTML
            # ID from URL or meta
            id_match = re.search(r'"member_id":\s*(\d+)', html)
            if id_match:
                result.user_id = int(id_match.group(1))

            # Screen name
            screen_match = re.search(r'"screen_name":\s*"([^"]+)"', html)
            if screen_match:
                result.screen_name = screen_match.group(1)

            # Check if private
            if 'page_private' in html or 'profile_closed' in html:
                result.is_private = True
                return result

            # Extract text content for contact extraction
            # Look for profile info sections
            import re

            # Get text between common profile sections
            bio_text = ''

            # Look for profile info block
            info_match = re.search(r'<div class="profile_info"[^>]*>(.*?)</div>', html, re.DOTALL)
            if info_match:
                bio_text += info_match.group(1)

            # Look for page info rows
            info_rows = re.findall(r'<div class="page_info_row"[^>]*>(.*?)</div>', html, re.DOTALL)
            bio_text += ' '.join(info_rows)

            # Clean HTML tags
            bio_text = re.sub(r'<[^>]+>', ' ', bio_text)
            bio_text = re.sub(r'\s+', ' ', bio_text)

            result.bio = bio_text

            # Extract contacts from scraped bio
            self._extract_contacts_from_bio(result)

            return result

        except Exception as e:
            result.error = str(e)
            return result


def extract_vk_contacts(profile_url: str, access_token: Optional[str] = None) -> VKContact:
    """Convenience function to extract contacts from single VK profile."""
    extractor = VKAPIExtractor(access_token=access_token)
    return extractor.extract_from_url(profile_url)


def extract_vk_contacts_batch(profile_urls: List[str], access_token: Optional[str] = None) -> List[VKContact]:
    """Convenience function to extract contacts from multiple VK profiles."""
    extractor = VKAPIExtractor(access_token=access_token)
    return extractor.extract_from_multiple(profile_urls)
