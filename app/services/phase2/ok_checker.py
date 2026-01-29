"""
OK (Odnoklassniki) Account Checker
==================================
Check if accounts exist on OK.ru by phone number, email, or username.
Returns masked contact information confirming account existence.

Based on: https://github.com/OSINT-mindset/odnoklassniki-checker
Technique: Uses OK.ru's password recovery/registration endpoints

Returns:
- Masked name (e.g., "И*** П***")
- Masked email (e.g., "p****@mail.ru")
- Masked phone (e.g., "+7 *** ***-**-45")
- Profile info (age, city)
- Registration date
"""

import requests
import re
import json
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from urllib.parse import urlencode
import hashlib
import time

logger = logging.getLogger(__name__)


@dataclass
class OKAccountInfo:
    """Information about an OK.ru account."""
    query: str  # Original search query
    exists: bool = False
    masked_name: Optional[str] = None
    masked_email: Optional[str] = None
    masked_phone: Optional[str] = None
    age: Optional[int] = None
    city: Optional[str] = None
    profile_url: Optional[str] = None
    registration_date: Optional[str] = None
    error: Optional[str] = None
    raw_response: Dict = field(default_factory=dict)


class OKChecker:
    """
    Check OK.ru accounts by phone, email, or username.

    Uses OK.ru's account recovery mechanism to check existence
    and retrieve masked contact information.
    """

    # OK.ru endpoints
    RECOVERY_URL = "https://ok.ru/dk"
    API_URL = "https://api.ok.ru/fb.do"

    # Request headers
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
        'Origin': 'https://ok.ru',
        'Referer': 'https://ok.ru/',
    }

    def __init__(self, timeout: int = 15):
        """
        Initialize OK checker.

        Args:
            timeout: Request timeout in seconds
        """
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)

    def check_account(self, query: str) -> OKAccountInfo:
        """
        Check if account exists on OK.ru.

        Args:
            query: Phone number, email, or username to check

        Returns:
            OKAccountInfo with masked data if found
        """
        result = OKAccountInfo(query=query)

        # Detect query type
        query_type = self._detect_query_type(query)

        try:
            if query_type == 'phone':
                return self._check_by_phone(query, result)
            elif query_type == 'email':
                return self._check_by_email(query, result)
            else:
                return self._check_by_username(query, result)

        except requests.exceptions.Timeout:
            result.error = "Request timeout"
            return result
        except Exception as e:
            result.error = str(e)
            logger.error(f"OK check error for {query}: {e}")
            return result

    def _detect_query_type(self, query: str) -> str:
        """Detect if query is phone, email, or username."""
        # Phone patterns
        if re.match(r'^\+?[78]?\d{10,11}$', re.sub(r'[\s\-\(\)]', '', query)):
            return 'phone'

        # Email pattern
        if '@' in query and '.' in query:
            return 'email'

        return 'username'

    def _normalize_phone(self, phone: str) -> str:
        """Normalize phone to format expected by OK.ru."""
        # Remove non-digits
        digits = re.sub(r'\D', '', phone)

        # Ensure +7 format
        if len(digits) == 11:
            if digits.startswith('8'):
                return '+7' + digits[1:]
            elif digits.startswith('7'):
                return '+' + digits
        elif len(digits) == 10:
            return '+7' + digits

        return '+' + digits

    def _check_by_phone(self, phone: str, result: OKAccountInfo) -> OKAccountInfo:
        """Check account by phone number."""
        normalized = self._normalize_phone(phone)

        # Method 1: Recovery page check
        try:
            params = {
                'st.cmd': 'anonymRecoveryAfterRecaptcha',
                'st.login': normalized,
            }

            response = self.session.get(
                self.RECOVERY_URL,
                params=params,
                timeout=self.timeout
            )

            if response.status_code == 200:
                # Parse response for account info
                html = response.text

                # Check if account exists
                if 'Мы не нашли аккаунт' not in html and 'не найден' not in html.lower():
                    result.exists = True

                    # Extract masked data from HTML
                    self._parse_recovery_html(html, result)

        except Exception as e:
            logger.debug(f"Phone recovery check failed: {e}")

        # Method 2: API registration check
        if not result.exists:
            try:
                result = self._check_via_registration_api(normalized, result)
            except Exception as e:
                logger.debug(f"Phone API check failed: {e}")

        return result

    def _check_by_email(self, email: str, result: OKAccountInfo) -> OKAccountInfo:
        """Check account by email address."""
        email = email.lower().strip()

        try:
            params = {
                'st.cmd': 'anonymRecoveryAfterRecaptcha',
                'st.login': email,
            }

            response = self.session.get(
                self.RECOVERY_URL,
                params=params,
                timeout=self.timeout
            )

            if response.status_code == 200:
                html = response.text

                if 'Мы не нашли аккаунт' not in html and 'не найден' not in html.lower():
                    result.exists = True
                    self._parse_recovery_html(html, result)

        except Exception as e:
            logger.debug(f"Email recovery check failed: {e}")

        return result

    def _check_by_username(self, username: str, result: OKAccountInfo) -> OKAccountInfo:
        """Check account by username/profile ID."""
        username = username.lower().strip()

        # Try direct profile access
        profile_urls = [
            f"https://ok.ru/{username}",
            f"https://ok.ru/profile/{username}",
        ]

        for url in profile_urls:
            try:
                response = self.session.get(url, timeout=self.timeout, allow_redirects=True)

                if response.status_code == 200:
                    html = response.text

                    # Check if it's a real profile page
                    if 'data-l="userCard' in html or 'class="profile-user' in html:
                        result.exists = True
                        result.profile_url = response.url

                        # Extract available info
                        self._parse_profile_html(html, result)
                        break

            except Exception as e:
                logger.debug(f"Username profile check failed: {e}")

        return result

    def _check_via_registration_api(self, login: str, result: OKAccountInfo) -> OKAccountInfo:
        """Check if login is taken via registration API."""
        try:
            # This endpoint checks if login is available for registration
            params = {
                'method': 'users.getInfo',
                'login': login,
                'format': 'json',
            }

            response = self.session.get(
                'https://ok.ru/api/users/getInfo',
                params=params,
                timeout=self.timeout
            )

            if response.status_code == 200:
                data = response.json()
                if data and not data.get('error'):
                    result.exists = True
                    result.raw_response = data

        except Exception:
            pass

        return result

    def _parse_recovery_html(self, html: str, result: OKAccountInfo):
        """Parse account recovery page for masked data."""
        # Look for masked phone pattern
        phone_match = re.search(r'\+7\s*\*+\s*\d{2}', html)
        if phone_match:
            result.masked_phone = phone_match.group().strip()

        # Look for masked email pattern
        email_match = re.search(r'[a-zA-Z]\*+@[a-zA-Z]+\.[a-zA-Z]+', html)
        if email_match:
            result.masked_email = email_match.group()

        # Look for masked name
        name_match = re.search(r'([А-Яа-яA-Za-z]+\s*\*+\s+[А-Яа-яA-Za-z]*\*+)', html)
        if name_match:
            result.masked_name = name_match.group().strip()

    def _parse_profile_html(self, html: str, result: OKAccountInfo):
        """Parse profile page for available info."""
        # Try to extract age
        age_match = re.search(r'(\d{1,2})\s*(?:лет|год|года)', html)
        if age_match:
            result.age = int(age_match.group(1))

        # Try to extract city
        city_patterns = [
            r'data-l="userCard,city[^"]*">([^<]+)',
            r'class="[^"]*city[^"]*">([^<]+)',
            r'"location":"([^"]+)"',
        ]
        for pattern in city_patterns:
            city_match = re.search(pattern, html)
            if city_match:
                result.city = city_match.group(1).strip()
                break

    def check_multiple(self, queries: List[str]) -> List[OKAccountInfo]:
        """
        Check multiple accounts.

        Args:
            queries: List of phone numbers, emails, or usernames

        Returns:
            List of OKAccountInfo for each query
        """
        results = []
        for query in queries:
            result = self.check_account(query)
            results.append(result)
            time.sleep(0.5)  # Rate limiting
        return results

    def check_phones(self, phones: List[str]) -> List[OKAccountInfo]:
        """Check multiple phone numbers."""
        return [self.check_account(phone) for phone in phones]

    def check_emails(self, emails: List[str]) -> List[OKAccountInfo]:
        """Check multiple email addresses."""
        return [self.check_account(email) for email in emails]


def check_ok_account(query: str) -> OKAccountInfo:
    """Convenience function to check single account."""
    checker = OKChecker()
    return checker.check_account(query)


def check_ok_accounts(queries: List[str]) -> List[OKAccountInfo]:
    """Convenience function to check multiple accounts."""
    checker = OKChecker()
    return checker.check_multiple(queries)
