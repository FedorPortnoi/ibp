"""
Breach Database API Sources
============================
Queries breach/leak database APIs for real data associated with
email addresses, phone numbers, and usernames.

FREE (no API key):
- HudsonRock Cavalier — infostealer data (credentials, URLs)
- HIBP Pwned Passwords — password validation (k-anonymity)
- LeakCheck Public — breach source names per email/username
- ProxyNova COMB — 3.2B email:password combos

Placeholder (needs API keys):
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
    REQUEST_TIMEOUT = 5
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
    Have I Been Pwned (HIBP) — breach data API.

    Free (no key): Pwned Passwords k-anonymity validation only.
    Paid (HIBP_API_KEY, $3.50/mo): Full email breach lookup + no rate limits.

    Free API: GET https://api.pwnedpasswords.com/range/{first5SHA1chars}
    Paid API: GET https://haveibeenpwned.com/api/v3/breachedaccount/{email}
              Header: hibp-api-key: {key}
    """

    name = "HIBP Pwned Passwords"
    source_type = SourceType.VERIFICATION
    source_tier = SourceTier.B
    requires_api_key = False
    rate_limit_per_minute = 60

    PWNED_PASSWORDS_URL = "https://api.pwnedpasswords.com/range"
    BREACHED_ACCOUNT_URL = "https://haveibeenpwned.com/api/v3/breachedaccount"
    REQUEST_TIMEOUT = 5

    def is_available(self) -> bool:
        return True

    @property
    def _api_key(self) -> Optional[str]:
        return os.environ.get('HIBP_API_KEY')

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

        # If we have a paid key and an email, do email breach lookup
        api_key = self._api_key
        if api_key and email:
            email_to_check = email if isinstance(email, str) else email[0] if email else None
            if email_to_check:
                self.logger.info(
                    f"HIBP PAID mode: would call breachedaccount API "
                    f"with key={api_key[:8]}... email={email_to_check}"
                )
                # TODO: Implement real paid API call
                # GET /api/v3/breachedaccount/{email}?truncateResponse=false
                # Headers: {"hibp-api-key": api_key, "user-agent": "IBP-OSINT"}
        elif email and not api_key:
            self.logger.info("HIBP: no API key configured for email breach lookup, using free password validation only")

        # Free password validation (always available)
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
        sha1_hash = hashlib.sha1(password.encode('utf-8'), usedforsecurity=False).hexdigest().upper()
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

    Free public endpoint — NO API key needed (names only, no passwords).
    Pro API — LEAKCHECK_API_KEY enables full results with passwords.

    Free: GET https://leakcheck.io/api/public?check={query}
    Pro:  GET https://leakcheck.io/api/v2/query/{query}
          Header: X-API-Key: {key}

    Rate limit: ~3 req/s (429 on exceed)
    """

    name = "LeakCheck API"
    source_type = SourceType.BOTH
    source_tier = SourceTier.S
    requires_api_key = False
    rate_limit_per_minute = 180

    PUBLIC_URL = "https://leakcheck.io/api/public"
    PRO_URL = "https://leakcheck.io/api/v2/query"
    REQUEST_TIMEOUT = 5
    DELAY_BETWEEN_REQUESTS = 0.5
    MAX_RETRIES = 2
    RETRY_DELAY = 2.0

    def is_available(self) -> bool:
        return True

    @property
    def _pro_key(self) -> Optional[str]:
        return os.environ.get('LEAKCHECK_API_KEY')

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

        # Collect emails to check
        emails_to_check = []
        if email:
            if isinstance(email, list):
                emails_to_check.extend(email)
            else:
                emails_to_check.append(email)

        email_candidates = kwargs.get('email_candidates', [])
        for candidate in email_candidates:
            if isinstance(candidate, dict):
                addr = candidate.get('email', '')
            else:
                addr = str(candidate)
            if addr and addr not in emails_to_check:
                emails_to_check.append(addr)

        emails_to_check = emails_to_check[:5]

        # Search by email (primary)
        for email_addr in emails_to_check:
            try:
                email_results = self._search(email_addr, 'email')
                results.extend(email_results)
                if emails_to_check.index(email_addr) < len(emails_to_check) - 1:
                    time.sleep(self.DELAY_BETWEEN_REQUESTS)
            except Exception as e:
                self.logger.warning(f"LeakCheck email search error for {email_addr}: {e}")

        # Search by username (secondary)
        if username:
            usernames = [username] if isinstance(username, str) else list(username)
            for uname in usernames[:2]:
                try:
                    time.sleep(self.DELAY_BETWEEN_REQUESTS)
                    username_results = self._search(uname, 'username')
                    results.extend(username_results)
                except Exception as e:
                    self.logger.warning(f"LeakCheck username search error for {uname}: {e}")

        if results:
            self.logger.info(f"LeakCheck found {len(results)} results")
        return results

    def _search(self, query: str, query_type: str) -> List[SourceResult]:
        """Query LeakCheck API. Pro if key set, else public (free)."""
        pro_key = self._pro_key
        if pro_key:
            return self._search_pro(query, query_type, pro_key)
        return self._search_public(query, query_type)

    def _search_pro(self, query: str, query_type: str, api_key: str) -> List[SourceResult]:
        """Query LeakCheck Pro API (full results with passwords)."""
        self.logger.info(
            f"LeakCheck PRO mode: would call API with key={api_key[:8]}... "
            f"query={query}"
        )
        # TODO: Implement real Pro API call
        # GET /api/v2/query/{query}
        # Header: X-API-Key: {api_key}
        return []

    def _search_public(self, query: str, query_type: str) -> List[SourceResult]:
        """Query LeakCheck free public API with retry on 429."""
        results = []
        session = _get_session()

        for attempt in range(self.MAX_RETRIES + 1):
            try:
                resp = session.get(
                    self.PUBLIC_URL,
                    params={"check": query},
                    timeout=self.REQUEST_TIMEOUT,
                )

                if resp.status_code == 429:
                    if attempt < self.MAX_RETRIES:
                        self.logger.debug(f"LeakCheck rate limited, retrying in {self.RETRY_DELAY}s")
                        time.sleep(self.RETRY_DELAY * (attempt + 1))
                        continue
                    self.logger.warning("LeakCheck rate limit exceeded, skipping")
                    return results

                if resp.status_code == 404:
                    return results
                if resp.status_code != 200:
                    self.logger.debug(f"LeakCheck returned {resp.status_code} for {query}")
                    return results

                data = resp.json()

                # Handle different response formats
                if isinstance(data, dict):
                    if data.get('success') is False or data.get('error'):
                        return results
                    # Public API may return {"found": N, "sources": [...]}
                    found = data.get('found', 0)
                    sources = data.get('sources', [])
                    if not found and not sources:
                        # Try treating response as a list of results
                        if isinstance(data.get('result'), list):
                            sources = data['result']
                        else:
                            return results
                elif isinstance(data, list):
                    sources = data
                else:
                    return results

                if not sources:
                    return results

                # Extract breach source names
                breach_names = []
                for src in sources:
                    if isinstance(src, str):
                        breach_names.append(src)
                    elif isinstance(src, dict):
                        name = src.get('name') or src.get('source') or str(src)
                        breach_names.append(name)

                if breach_names:
                    # Query confirmed in breaches
                    results.append(SourceResult(
                        data_type=query_type,
                        value=query,
                        source_name=self.name,
                        source_tier=self.source_tier,
                        confidence=0.90,
                        verified=True,
                        metadata={
                            'breach_source': 'leakcheck_public',
                            'breach_names': breach_names,
                            'breach_count': len(breach_names),
                            'verification': 'breach_confirmed',
                        },
                    ))

                break  # Success, no retry needed

            except requests.Timeout:
                self.logger.warning(f"LeakCheck timeout for: {query}")
                break
            except requests.ConnectionError:
                self.logger.warning("LeakCheck connection error (offline or blocked)")
                break
            except Exception as e:
                self.logger.warning(f"LeakCheck search error: {e}")
                break

        return results


class SnusbaseSource(BaseSource):
    """
    Query Snusbase API for breach data.
    Requires paid subscription ($5-16/mo), API included.

    API: POST https://api.snusbase.com/data/search
    Auth: header "Auth: {API_KEY}"

    Without SNUSBASE_API_KEY: returns demo breach data.
    With key: logs intended API call (real implementation TODO).
    """

    name = "Snusbase API"
    source_type = SourceType.BOTH
    source_tier = SourceTier.S
    requires_api_key = True
    rate_limit_per_minute = 512

    BASE_URL = "https://api.snusbase.com"

    def is_available(self) -> bool:
        return True  # Always available — demo mode when no key

    @property
    def _api_key(self) -> Optional[str]:
        return os.environ.get('SNUSBASE_API_KEY')

    def query_impl(
        self,
        name: Optional[str] = None,
        phone: Optional[str] = None,
        email: Optional[str] = None,
        username: Optional[str] = None,
        vk_id: Optional[str] = None,
        photo_path: Optional[str] = None,
        **kwargs,
    ) -> List[SourceResult]:
        query = email or username
        if not query:
            return []

        key = self._api_key
        if key:
            self.logger.info(
                f"Snusbase REAL mode: would call API with key={key[:8]}... "
                f"query={query}"
            )
            # TODO: Implement real API call
            # POST /data/search with {"type": "email", "term": query}
            # Headers: {"Auth": key, "Content-Type": "application/json"}
            return []

        # No API key configured
        self.logger.info("Snusbase: no API key configured, returning empty")
        return []


class DehashedSource(BaseSource):
    """
    Query DeHashed API for breach data.
    Requires subscription + credits ($5.49/mo).

    API: GET https://api.dehashed.com/search?query=email:{email}
    Auth: Basic (email:api_key)

    Without keys: returns demo breach data.
    With keys: logs intended API call (real implementation TODO).
    """

    name = "DeHashed API"
    source_type = SourceType.BOTH
    source_tier = SourceTier.S
    requires_api_key = True
    rate_limit_per_minute = 60

    BASE_URL = "https://api.dehashed.com"

    def is_available(self) -> bool:
        return True  # Always available — demo mode when no keys

    @property
    def _credentials(self) -> Optional[tuple]:
        email = os.environ.get('DEHASHED_EMAIL')
        key = os.environ.get('DEHASHED_API_KEY')
        if email and key:
            return (email, key)
        return None

    def query_impl(
        self,
        name: Optional[str] = None,
        phone: Optional[str] = None,
        email: Optional[str] = None,
        username: Optional[str] = None,
        vk_id: Optional[str] = None,
        photo_path: Optional[str] = None,
        **kwargs,
    ) -> List[SourceResult]:
        query = email or name or phone or username
        if not query:
            return []

        query_type = 'email' if email else 'name' if name else 'phone' if phone else 'username'

        creds = self._credentials
        if creds:
            self.logger.info(
                f"DeHashed REAL mode: would call API with email={creds[0]}, "
                f"key={creds[1][:8]}... query={query}"
            )
            # TODO: Implement real API call
            # GET /search?query=email:{query}
            # Auth: Basic (email, api_key)
            return []

        # No API key configured
        self.logger.info("DeHashed: no API key configured, returning empty")
        return []


class ProxyNovaCOMBSource(BaseSource):
    """
    Query ProxyNova COMB (Combination of Many Breaches) API.

    FREE, no auth needed. 3.2 billion email:password records.
    Endpoint: GET https://api.proxynova.com/comb?query={email}&start=0&limit=100
    Returns: {"count": N, "lines": ["email:password", ...]}
    Rate limit: ~100 req/min, max 100 results per query
    """

    name = "ProxyNova COMB"
    source_type = SourceType.IDENTITY
    source_tier = SourceTier.S
    requires_api_key = False
    rate_limit_per_minute = 100

    BASE_URL = "https://api.proxynova.com/comb"
    REQUEST_TIMEOUT = 5
    MAX_RESULTS = 100

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

        # Collect emails to search
        emails_to_check = []
        if email:
            if isinstance(email, list):
                emails_to_check.extend(email)
            else:
                emails_to_check.append(email)

        email_candidates = kwargs.get('email_candidates', [])
        for candidate in email_candidates:
            if isinstance(candidate, dict):
                addr = candidate.get('email', '')
            else:
                addr = str(candidate)
            if addr and addr not in emails_to_check:
                emails_to_check.append(addr)

        emails_to_check = emails_to_check[:5]

        for email_addr in emails_to_check:
            try:
                email_results = self._search_email(email_addr)
                results.extend(email_results)
            except Exception as e:
                self.logger.warning(f"ProxyNova COMB search error for {email_addr}: {e}")

        if results:
            self.logger.info(f"ProxyNova COMB found {len(results)} results")
        return results

    def _search_email(self, email: str) -> List[SourceResult]:
        """Search COMB database by email."""
        results = []
        session = _get_session()

        try:
            resp = session.get(
                self.BASE_URL,
                params={
                    "query": email,
                    "start": 0,
                    "limit": self.MAX_RESULTS,
                },
                timeout=self.REQUEST_TIMEOUT,
            )

            if resp.status_code == 429:
                self.logger.warning("ProxyNova COMB rate limited")
                return results
            if resp.status_code != 200:
                self.logger.debug(f"ProxyNova COMB returned {resp.status_code} for {email}")
                return results

            data = resp.json()
            count = data.get('count', 0)
            lines = data.get('lines', [])

            if not lines:
                return results

            # Email confirmed in COMB — high confidence
            results.append(SourceResult(
                data_type='email',
                value=email,
                source_name=self.name,
                source_tier=self.source_tier,
                confidence=0.92,
                verified=True,
                metadata={
                    'breach_source': 'comb',
                    'total_records': count,
                    'verification': 'breach_confirmed',
                },
            ))

            # Parse email:password lines
            seen_passwords = set()
            for line in lines:
                if not isinstance(line, str):
                    continue
                # Format: "email:password" or "email;password"
                sep_idx = line.find(':')
                if sep_idx == -1:
                    sep_idx = line.find(';')
                if sep_idx == -1:
                    continue

                line_email = line[:sep_idx].strip()
                line_password = line[sep_idx + 1:].strip()

                if not line_password or line_password in seen_passwords:
                    continue
                seen_passwords.add(line_password)

                results.append(SourceResult(
                    data_type='credential',
                    value=line_email,
                    source_name=self.name,
                    source_tier=self.source_tier,
                    confidence=0.90,
                    verified=True,
                    raw_data={
                        'password': line_password,
                    },
                    metadata={
                        'breach_source': 'comb',
                    },
                ))

                # Discover additional emails
                if '@' in line_email and line_email.lower() != email.lower():
                    results.append(SourceResult(
                        data_type='email',
                        value=line_email.lower(),
                        source_name=self.name,
                        source_tier=self.source_tier,
                        confidence=0.85,
                        verified=True,
                        metadata={
                            'breach_source': 'comb',
                            'discovered_via': email,
                        },
                    ))

        except requests.Timeout:
            self.logger.warning(f"ProxyNova COMB timeout for: {email}")
        except requests.ConnectionError:
            self.logger.warning("ProxyNova COMB connection error")
        except Exception as e:
            self.logger.warning(f"ProxyNova COMB search error: {e}")

        return results
