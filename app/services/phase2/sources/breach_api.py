"""
Breach Database API Sources
============================
Queries breach/leak database APIs for real data associated with
email addresses, phone numbers, and usernames.

Implemented:
- HudsonRock Cavalier — FREE, no key needed, infostealer data
- HIBP Pwned Passwords — FREE, no key needed, password validation

Placeholder (needs API keys):
- LeakCheck.io (LEAKCHECK_API_KEY)
- Snusbase (SNUSBASE_API_KEY)
- DeHashed (DEHASHED_EMAIL, DEHASHED_API_KEY)

Tier: S (Breach Database) — highest reliability, real leaked data
"""

import hashlib
import os
import logging
import time
from typing import List, Optional

import requests

from ..base_source import BaseSource, SourceResult, SourceTier, SourceType

logger = logging.getLogger(__name__)

# Shared session for connection pooling
_session = None


def _get_session():
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update({
            'User-Agent': 'IBP-OSINT/1.0 (Research Tool)',
            'Accept': 'application/json',
        })
    return _session


class HudsonRockSource(BaseSource):
    """
    Query HudsonRock Cavalier FREE OSINT API for infostealer data.

    NO API KEY NEEDED. Returns actual cleartext passwords, URLs,
    computer metadata from infostealer malware logs.

    Free endpoints:
    - GET /api/json/v2/osint-tools/search-by-email?email={email}
    - GET /api/json/v2/osint-tools/search-by-username?username={username}
    - GET /api/json/v2/osint-tools/search-by-domain?domain={domain}

    API Docs: https://docs.hudsonrock.com/
    """

    name = "HudsonRock Cavalier"
    source_type = SourceType.IDENTITY
    source_tier = SourceTier.S
    requires_api_key = False
    rate_limit_per_minute = 30

    BASE_URL = "https://cavalier.hudsonrock.com/api/json/v2/osint-tools"
    REQUEST_TIMEOUT = 10
    DELAY_BETWEEN_REQUESTS = 1.0

    def is_available(self) -> bool:
        return True

    def query_impl(
        self,
        name: Optional[str] = None,
        phone: Optional[str] = None,
        email: Optional[str] = None,
        username: Optional[str] = None,
        vk_id: Optional[str] = None,
        photo_path: Optional[str] = None,
        **kwargs
    ) -> List[SourceResult]:
        results = []

        # Collect emails to check - from kwargs (email_candidates from pipeline)
        emails_to_check = []
        if email:
            if isinstance(email, list):
                emails_to_check.extend(email)
            else:
                emails_to_check.append(email)

        # Also check email_candidates passed from the pipeline
        email_candidates = kwargs.get('email_candidates', [])
        for candidate in email_candidates:
            if isinstance(candidate, dict):
                addr = candidate.get('email', '')
            else:
                addr = str(candidate)
            if addr and addr not in emails_to_check:
                emails_to_check.append(addr)

        # Limit to top 10 emails to avoid excessive API calls
        emails_to_check = emails_to_check[:10]

        # Search by email
        for email_addr in emails_to_check:
            try:
                email_results = self._search_by_email(email_addr)
                results.extend(email_results)
                if emails_to_check.index(email_addr) < len(emails_to_check) - 1:
                    time.sleep(self.DELAY_BETWEEN_REQUESTS)
            except Exception as e:
                self.logger.warning(f"HudsonRock email search error for {email_addr}: {e}")

        # Search by username if provided
        if username:
            usernames = [username] if isinstance(username, str) else list(username)
            for uname in usernames[:3]:
                try:
                    time.sleep(self.DELAY_BETWEEN_REQUESTS)
                    username_results = self._search_by_username(uname)
                    results.extend(username_results)
                except Exception as e:
                    self.logger.warning(f"HudsonRock username search error for {uname}: {e}")

        if results:
            self.logger.info(f"HudsonRock found {len(results)} results")
        return results

    def _search_by_email(self, email: str) -> List[SourceResult]:
        """Search HudsonRock by email address."""
        results = []
        session = _get_session()

        try:
            resp = session.get(
                f"{self.BASE_URL}/search-by-email",
                params={"email": email},
                timeout=self.REQUEST_TIMEOUT,
            )

            if resp.status_code == 404:
                return results
            if resp.status_code != 200:
                self.logger.debug(f"HudsonRock returned {resp.status_code} for {email}")
                return results

            data = resp.json()

            # Check for "no results" response
            if isinstance(data, dict) and data.get('message', '').lower().startswith('no result'):
                return results

            stealers = data.get('stealers', [])
            if not stealers:
                return results

            # Email confirmed in breach - add with high confidence
            results.append(SourceResult(
                data_type='email',
                value=email,
                source_name=self.name,
                source_tier=self.source_tier,
                confidence=0.95,
                verified=True,
                metadata={
                    'breach_source': 'infostealer',
                    'stealer_count': len(stealers),
                    'verification': 'breach_confirmed',
                },
            ))

            # Extract credentials from each stealer
            seen_creds = set()
            for stealer in stealers:
                computer_name = stealer.get('computer_name', 'Unknown')
                os_name = stealer.get('operating_system', '')
                date_compromised = stealer.get('date_compromised', '')

                for cred in stealer.get('credentials', []):
                    cred_url = cred.get('url', '')
                    cred_user = cred.get('username', '')
                    cred_pass = cred.get('password', '')

                    # Add discovered passwords
                    if cred_pass:
                        cred_key = f"{cred_user}:{cred_pass}"
                        if cred_key not in seen_creds:
                            seen_creds.add(cred_key)
                            results.append(SourceResult(
                                data_type='credential',
                                value=f"{cred_user}",
                                source_name=self.name,
                                source_tier=self.source_tier,
                                confidence=0.95,
                                verified=True,
                                raw_data={
                                    'password': cred_pass,
                                    'url': cred_url,
                                },
                                metadata={
                                    'computer_name': computer_name,
                                    'os': os_name,
                                    'date_compromised': date_compromised,
                                    'breach_source': 'infostealer',
                                },
                            ))

                    # Discover additional emails from credentials
                    if cred_user and '@' in cred_user and cred_user.lower() != email.lower():
                        results.append(SourceResult(
                            data_type='email',
                            value=cred_user.lower(),
                            source_name=self.name,
                            source_tier=self.source_tier,
                            confidence=0.90,
                            verified=True,
                            metadata={
                                'breach_source': 'infostealer',
                                'discovered_via': email,
                                'url': cred_url,
                            },
                        ))

                # Extract top logins (additional usernames)
                for login in stealer.get('top_logins', [])[:5]:
                    if login and login != email:
                        results.append(SourceResult(
                            data_type='username',
                            value=login,
                            source_name=self.name,
                            source_tier=self.source_tier,
                            confidence=0.80,
                            metadata={
                                'breach_source': 'infostealer',
                                'discovered_via': email,
                            },
                        ))

        except requests.Timeout:
            self.logger.warning(f"HudsonRock timeout for email: {email}")
        except requests.ConnectionError:
            self.logger.warning("HudsonRock connection error (offline or blocked)")
        except Exception as e:
            self.logger.warning(f"HudsonRock search error: {e}")

        return results

    def _search_by_username(self, username: str) -> List[SourceResult]:
        """Search HudsonRock by username."""
        results = []
        session = _get_session()

        try:
            resp = session.get(
                f"{self.BASE_URL}/search-by-username",
                params={"username": username},
                timeout=self.REQUEST_TIMEOUT,
            )

            if resp.status_code != 200:
                return results

            data = resp.json()
            if isinstance(data, dict) and data.get('message', '').lower().startswith('no result'):
                return results

            stealers = data.get('stealers', [])
            if not stealers:
                return results

            # Extract emails and credentials from username search
            seen_emails = set()
            for stealer in stealers:
                date_compromised = stealer.get('date_compromised', '')
                for cred in stealer.get('credentials', []):
                    cred_user = cred.get('username', '')
                    if cred_user and '@' in cred_user and cred_user.lower() not in seen_emails:
                        seen_emails.add(cred_user.lower())
                        results.append(SourceResult(
                            data_type='email',
                            value=cred_user.lower(),
                            source_name=self.name,
                            source_tier=self.source_tier,
                            confidence=0.90,
                            verified=True,
                            metadata={
                                'breach_source': 'infostealer',
                                'discovered_via_username': username,
                                'date_compromised': date_compromised,
                            },
                        ))

        except requests.Timeout:
            self.logger.warning(f"HudsonRock timeout for username: {username}")
        except requests.ConnectionError:
            self.logger.warning("HudsonRock connection error")
        except Exception as e:
            self.logger.warning(f"HudsonRock username search error: {e}")

        return results


class HIBPSource(BaseSource):
    """
    Have I Been Pwned — Pwned Passwords API (k-anonymity).

    FREE, no API key needed. Validates whether passwords found by
    other sources (e.g., HudsonRock) appear in known breaches.

    This is a VALIDATION source — it confirms data found by others,
    it doesn't discover new data on its own.

    API: GET https://api.pwnedpasswords.com/range/{first5SHA1chars}
    """

    name = "HIBP Pwned Passwords"
    source_type = SourceType.VERIFICATION
    source_tier = SourceTier.B
    requires_api_key = False
    rate_limit_per_minute = 60

    PWNED_PASSWORDS_URL = "https://api.pwnedpasswords.com/range"
    REQUEST_TIMEOUT = 10

    def is_available(self) -> bool:
        return True

    def query_impl(
        self,
        name: Optional[str] = None,
        phone: Optional[str] = None,
        email: Optional[str] = None,
        username: Optional[str] = None,
        vk_id: Optional[str] = None,
        photo_path: Optional[str] = None,
        **kwargs
    ) -> List[SourceResult]:
        results = []

        # This source validates passwords found by other sources
        # It receives passwords via kwargs from the pipeline
        passwords_to_check = kwargs.get('passwords', [])
        if not passwords_to_check:
            return results

        for password_entry in passwords_to_check[:20]:
            if isinstance(password_entry, dict):
                password = password_entry.get('password', '')
                associated_email = password_entry.get('email', '')
            else:
                password = str(password_entry)
                associated_email = ''

            if not password:
                continue

            try:
                breach_count = self._check_password(password)
                if breach_count > 0:
                    results.append(SourceResult(
                        data_type='credential_validation',
                        value=associated_email or 'unknown',
                        source_name=self.name,
                        source_tier=self.source_tier,
                        confidence=0.98,
                        verified=True,
                        metadata={
                            'breach_count': breach_count,
                            'validation': 'password_in_breaches',
                            'password_compromised': True,
                        },
                    ))

                time.sleep(0.1)  # Be polite to HIBP

            except Exception as e:
                self.logger.warning(f"HIBP password check error: {e}")

        return results

    def _check_password(self, password: str) -> int:
        """
        Check if password appears in HIBP using k-anonymity.

        Returns the number of times the password has been seen in breaches,
        or 0 if not found.
        """
        sha1_hash = hashlib.sha1(password.encode('utf-8')).hexdigest().upper()
        prefix = sha1_hash[:5]
        suffix = sha1_hash[5:]

        session = _get_session()
        resp = session.get(
            f"{self.PWNED_PASSWORDS_URL}/{prefix}",
            timeout=self.REQUEST_TIMEOUT,
            headers={'Add-Padding': 'true'},
        )

        if resp.status_code != 200:
            return 0

        # Response is lines of "HASH_SUFFIX:COUNT"
        for line in resp.text.splitlines():
            parts = line.strip().split(':')
            if len(parts) == 2 and parts[0] == suffix:
                return int(parts[1])

        return 0


class LeakCheckSource(BaseSource):
    """
    Query LeakCheck.io API for breach data.

    Free tier (public API): Returns breach names only, no key needed.
    Pro tier ($9.99/mo): Returns actual data (emails, passwords, names).

    API Docs: https://wiki.leakcheck.io/en/api
    Python SDK: pip install leakcheck
    """

    name = "LeakCheck API"
    source_type = SourceType.BOTH
    source_tier = SourceTier.S
    requires_api_key = False
    rate_limit_per_minute = 180

    def is_available(self) -> bool:
        return True

    def query_impl(
        self,
        name: Optional[str] = None,
        phone: Optional[str] = None,
        email: Optional[str] = None,
        username: Optional[str] = None,
        vk_id: Optional[str] = None,
        photo_path: Optional[str] = None,
        **kwargs
    ) -> List[SourceResult]:
        # TODO: Implement when LeakCheck API key is available
        self.logger.debug("LeakCheck source not yet implemented")
        return []


class SnusbaseSource(BaseSource):
    """
    Query Snusbase API for breach data.
    Requires paid subscription ($5-16/mo), API included.
    """

    name = "Snusbase API"
    source_type = SourceType.BOTH
    source_tier = SourceTier.S
    requires_api_key = True
    rate_limit_per_minute = 512

    def is_available(self) -> bool:
        return bool(os.environ.get('SNUSBASE_API_KEY'))

    def query_impl(self, **kwargs) -> List[SourceResult]:
        self.logger.debug("Snusbase source not yet implemented")
        return []


class DehashedSource(BaseSource):
    """
    Query DeHashed API for breach data.
    Requires subscription + credits.
    """

    name = "DeHashed API"
    source_type = SourceType.BOTH
    source_tier = SourceTier.S
    requires_api_key = True
    rate_limit_per_minute = 60

    def is_available(self) -> bool:
        return bool(
            os.environ.get('DEHASHED_EMAIL')
            and os.environ.get('DEHASHED_API_KEY')
        )

    def query_impl(self, **kwargs) -> List[SourceResult]:
        self.logger.debug("DeHashed source not yet implemented")
        return []
