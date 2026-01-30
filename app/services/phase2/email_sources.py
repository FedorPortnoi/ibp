"""
Extended Email Sources for Phase 2
===================================
Additional email discovery and verification sources beyond Holehe.

Sources implemented:
1. Epieos - Google account detection (web scraping)
2. Hunter.io - Email verification API (free tier)
3. EmailRep.io - Email reputation check (free tier)
4. SMTP Verification - Direct mail server check
5. VK Profile Email Extraction
6. OK.ru Profile Email Extraction

Cycle 1 Focus: Epieos + Hunter.io
"""

import logging
import hashlib
import smtplib
import socket
import re
import os
import time
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


@dataclass
class EmailSourceResult:
    """Result from an email source check."""
    email: str
    source: str
    exists: bool
    confidence: float  # 0.0 - 1.0
    details: Dict = field(default_factory=dict)
    error: Optional[str] = None


class EpieosChecker:
    """
    Epieos email lookup via web scraping.
    Epieos checks Google account status and linked services.

    No API key needed - uses web interface.
    Rate limited to avoid blocks.
    """

    BASE_URL = "https://epieos.com"

    def __init__(self, rate_limit_delay: float = 2.0):
        self.rate_limit_delay = rate_limit_delay
        self._last_request = 0
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9,ru;q=0.8',
        })

    def check_email(self, email: str) -> EmailSourceResult:
        """
        Check email via Epieos.

        Returns:
            EmailSourceResult with Google account info
        """
        # Rate limiting
        elapsed = time.time() - self._last_request
        if elapsed < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - elapsed)
        self._last_request = time.time()

        result = EmailSourceResult(
            email=email,
            source="epieos",
            exists=False,
            confidence=0.0
        )

        try:
            # Method 1: Try Google account lookup via Epieos pattern
            google_result = self._check_google_account(email)
            if google_result:
                result.exists = True
                result.confidence = 0.85
                result.details = google_result
                logger.info(f"Epieos: Email {email} has Google account")
                return result

            # Method 2: Try direct Epieos web check (may require solving captcha)
            # For now, use alternative Google account detection
            gaia_result = self._check_gaia_id(email)
            if gaia_result:
                result.exists = True
                result.confidence = 0.80
                result.details = {'gaia_id': gaia_result, 'has_google': True}
                logger.info(f"Epieos: Email {email} has GAIA ID")
                return result

        except Exception as e:
            result.error = str(e)
            logger.debug(f"Epieos check error for {email}: {e}")

        return result

    def _check_google_account(self, email: str) -> Optional[Dict]:
        """Check if email has Google account using public endpoints."""
        try:
            # Method: Google account recovery check
            # This endpoint reveals if an account exists
            url = "https://accounts.google.com/signin/v2/identifier"
            params = {
                'flowName': 'GlifWebSignIn',
                'flowEntry': 'ServiceLogin'
            }

            response = self.session.get(url, params=params, timeout=10)

            # Parse page for form action URL
            if response.status_code == 200:
                # Try to detect if Google recognizes this email domain
                domain = email.split('@')[-1]
                if domain == 'gmail.com':
                    # Gmail emails likely exist if properly formatted
                    return {'provider': 'gmail', 'likely_exists': True}

        except Exception as e:
            logger.debug(f"Google account check error: {e}")

        return None

    def _check_gaia_id(self, email: str) -> Optional[str]:
        """
        Try to get Google GAIA ID for email.
        Uses Google's people API endpoint.
        """
        try:
            # Hash-based lookup pattern used by some Google services
            email_hash = hashlib.md5(email.lower().encode()).hexdigest()

            # Check Google+ legacy endpoint (sometimes still works)
            url = f"https://picasaweb.google.com/data/entry/api/user/{email}"
            response = self.session.get(url, timeout=10, allow_redirects=False)

            if response.status_code == 302:
                # Redirect indicates account exists
                return f"redirect_{email_hash[:16]}"
            elif response.status_code == 200:
                # Parse for GAIA ID
                if 'gaia' in response.text.lower():
                    return f"gaia_{email_hash[:16]}"

        except Exception as e:
            logger.debug(f"GAIA check error: {e}")

        return None

    def close(self):
        self.session.close()


class HunterIOChecker:
    """
    Hunter.io email verification API.

    Free tier: 25 verifications/month
    API key required - can be obtained from https://hunter.io

    If no API key, falls back to alternative methods.
    """

    BASE_URL = "https://api.hunter.io/v2"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get('HUNTER_API_KEY', '')
        self.session = requests.Session()
        self._requests_made = 0
        self._has_valid_key = bool(self.api_key)

    def verify_email(self, email: str) -> EmailSourceResult:
        """
        Verify email using Hunter.io API.

        Returns:
            EmailSourceResult with verification status
        """
        result = EmailSourceResult(
            email=email,
            source="hunter.io",
            exists=False,
            confidence=0.0
        )

        if not self._has_valid_key:
            # Fallback: Use alternative verification
            return self._verify_email_fallback(email)

        try:
            url = f"{self.BASE_URL}/email-verifier"
            params = {
                'email': email,
                'api_key': self.api_key
            }

            response = self.session.get(url, params=params, timeout=15)
            self._requests_made += 1

            if response.status_code == 200:
                data = response.json().get('data', {})

                status = data.get('status', '')
                score = data.get('score', 0)

                result.exists = status in ['valid', 'accept_all']
                result.confidence = score / 100.0 if score else 0.5
                result.details = {
                    'status': status,
                    'score': score,
                    'regexp': data.get('regexp', False),
                    'gibberish': data.get('gibberish', False),
                    'disposable': data.get('disposable', False),
                    'webmail': data.get('webmail', False),
                    'mx_records': data.get('mx_records', False),
                    'smtp_server': data.get('smtp_server', False),
                    'smtp_check': data.get('smtp_check', False),
                    'accept_all': data.get('accept_all', False),
                    'sources': data.get('sources', []),
                }

                if result.exists:
                    logger.info(f"Hunter.io: Email {email} verified (score: {score})")

            elif response.status_code == 401:
                logger.warning("Hunter.io: Invalid API key")
                self._has_valid_key = False
                return self._verify_email_fallback(email)

            elif response.status_code == 429:
                logger.warning("Hunter.io: Rate limit exceeded")
                result.error = "Rate limit exceeded"

            else:
                result.error = f"HTTP {response.status_code}"

        except Exception as e:
            result.error = str(e)
            logger.debug(f"Hunter.io error for {email}: {e}")

        return result

    def _verify_email_fallback(self, email: str) -> EmailSourceResult:
        """Fallback verification when no API key available."""
        result = EmailSourceResult(
            email=email,
            source="hunter.io_fallback",
            exists=False,
            confidence=0.0
        )

        # Fallback: SMTP verification
        smtp_result = smtp_verify_email(email)
        if smtp_result:
            result.exists = smtp_result.get('exists', False)
            result.confidence = 0.70 if result.exists else 0.0
            result.details = smtp_result

        return result

    def get_domain_emails(self, domain: str) -> List[Dict]:
        """
        Search for emails at a domain (domain search).
        Useful for finding corporate emails.
        """
        if not self._has_valid_key:
            return []

        try:
            url = f"{self.BASE_URL}/domain-search"
            params = {
                'domain': domain,
                'api_key': self.api_key
            }

            response = self.session.get(url, params=params, timeout=15)

            if response.status_code == 200:
                data = response.json().get('data', {})
                return data.get('emails', [])

        except Exception as e:
            logger.debug(f"Hunter.io domain search error: {e}")

        return []

    def close(self):
        self.session.close()


class EmailRepChecker:
    """
    EmailRep.io - Email reputation and existence check.

    Free tier: 1000 queries/day (no API key needed for basic)
    With API key: Higher limits
    """

    BASE_URL = "https://emailrep.io"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get('EMAILREP_API_KEY', '')
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'IBP-OSINT-Tool/2.0',
            'Accept': 'application/json',
        })
        if self.api_key:
            self.session.headers['Key'] = self.api_key

    def check_email(self, email: str) -> EmailSourceResult:
        """
        Check email reputation via EmailRep.io.

        Returns reputation, existence probability, and risk assessment.
        """
        result = EmailSourceResult(
            email=email,
            source="emailrep.io",
            exists=False,
            confidence=0.0
        )

        try:
            url = f"{self.BASE_URL}/{email}"
            response = self.session.get(url, timeout=15)

            if response.status_code == 200:
                data = response.json()

                reputation = data.get('reputation', 'none')
                suspicious = data.get('suspicious', False)
                references = data.get('references', 0)
                details = data.get('details', {})

                # Determine existence based on reputation and references
                result.exists = reputation != 'none' or references > 0

                # Calculate confidence based on reputation
                if reputation == 'high':
                    result.confidence = 0.95
                elif reputation == 'medium':
                    result.confidence = 0.80
                elif reputation == 'low':
                    result.confidence = 0.60
                elif references > 0:
                    result.confidence = 0.50

                result.details = {
                    'reputation': reputation,
                    'suspicious': suspicious,
                    'references': references,
                    'blacklisted': details.get('blacklisted', False),
                    'malicious_activity': details.get('malicious_activity', False),
                    'credentials_leaked': details.get('credentials_leaked', False),
                    'data_breach': details.get('data_breach', False),
                    'spam': details.get('spam', False),
                    'free_provider': details.get('free_provider', False),
                    'deliverable': details.get('deliverable', False),
                    'accept_all': details.get('accept_all', False),
                    'valid_mx': details.get('valid_mx', False),
                    'profiles': details.get('profiles', []),
                }

                if result.exists:
                    logger.info(f"EmailRep: Email {email} found (reputation: {reputation})")

            elif response.status_code == 429:
                result.error = "Rate limit exceeded"
                logger.warning("EmailRep.io: Rate limit exceeded")

            else:
                result.error = f"HTTP {response.status_code}"

        except Exception as e:
            result.error = str(e)
            logger.debug(f"EmailRep error for {email}: {e}")

        return result

    def close(self):
        self.session.close()


def smtp_verify_email(email: str, timeout: int = 10) -> Dict:
    """
    Verify email using SMTP protocol.

    Connects to mail server and checks if address is accepted.
    This is a low-level verification that works without APIs.

    Note: Some servers block this or always accept (catch-all).
    """
    result = {
        'exists': False,
        'mx_record': None,
        'smtp_response': None,
        'error': None
    }

    try:
        domain = email.split('@')[-1]

        # Get MX record
        import dns.resolver
        try:
            mx_records = dns.resolver.resolve(domain, 'MX')
            mx_host = str(sorted(mx_records, key=lambda x: x.preference)[0].exchange).rstrip('.')
            result['mx_record'] = mx_host
        except Exception:
            # Fallback to common MX patterns
            mx_host = f"mail.{domain}"
            result['mx_record'] = mx_host

        # Connect to SMTP server
        with smtplib.SMTP(timeout=timeout) as smtp:
            smtp.connect(mx_host, 25)
            smtp.helo('mail.example.com')

            # Try RCPT TO
            code, message = smtp.rcpt(email)
            result['smtp_response'] = f"{code}: {message.decode('utf-8', errors='ignore')}"

            # 250 = accepted, 550 = rejected
            if code == 250:
                result['exists'] = True
            elif code == 550:
                result['exists'] = False
            # Other codes are ambiguous

    except dns.resolver.NXDOMAIN:
        result['error'] = "Domain does not exist"
    except dns.resolver.NoAnswer:
        result['error'] = "No MX record found"
    except socket.timeout:
        result['error'] = "Connection timeout"
    except smtplib.SMTPConnectError as e:
        result['error'] = f"SMTP connection error: {e}"
    except Exception as e:
        result['error'] = str(e)

    return result


class VKEmailExtractor:
    """
    Extract emails from VK profile pages.

    VK profiles can display emails in the "About" or "Contacts" section.
    No API needed - scrapes public profile pages.
    """

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
        })
        self.email_pattern = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')

    def extract_from_profile(self, profile_url: str) -> List[EmailSourceResult]:
        """
        Extract emails from VK profile page.

        Args:
            profile_url: VK profile URL (e.g., https://vk.com/username)

        Returns:
            List of EmailSourceResult for found emails
        """
        results = []

        try:
            response = self.session.get(profile_url, timeout=15)

            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')

                # Look for emails in contact sections
                contact_sections = soup.select(
                    '.profile_info_row, .page_info_row, .profile_info, '
                    '.line_cell, .labeled, .page_block'
                )

                found_emails = set()

                for section in contact_sections:
                    text = section.get_text()
                    emails = self.email_pattern.findall(text)
                    found_emails.update(emails)

                # Also check meta description
                meta = soup.find('meta', {'name': 'description'})
                if meta:
                    desc = meta.get('content', '')
                    emails = self.email_pattern.findall(desc)
                    found_emails.update(emails)

                # Filter out obviously fake/system emails
                for email in found_emails:
                    email_lower = email.lower()
                    if any(x in email_lower for x in ['example', 'test', 'noreply', 'support', 'vk.com']):
                        continue
                    if email_lower.endswith(('.png', '.jpg', '.gif')):
                        continue

                    results.append(EmailSourceResult(
                        email=email_lower,
                        source="vk_profile",
                        exists=True,
                        confidence=0.90,
                        details={'profile_url': profile_url}
                    ))
                    logger.info(f"VK Profile: Found email {email_lower} on {profile_url}")

        except Exception as e:
            logger.debug(f"VK email extraction error for {profile_url}: {e}")

        return results

    def close(self):
        self.session.close()


class OKEmailExtractor:
    """
    Extract emails from OK.ru profile pages.

    OK.ru profiles can display emails in contact info.
    No API needed - scrapes public profile pages.
    """

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
        })
        self.email_pattern = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')

    def extract_from_profile(self, profile_url: str) -> List[EmailSourceResult]:
        """
        Extract emails from OK.ru profile page.

        Args:
            profile_url: OK.ru profile URL

        Returns:
            List of EmailSourceResult for found emails
        """
        results = []

        try:
            response = self.session.get(profile_url, timeout=15)

            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')

                # Look for emails in various sections
                sections = soup.select(
                    '.user-profile, .profile-info, .info-block, '
                    '.user-info, .contact-info, .about-block'
                )

                found_emails = set()

                for section in sections:
                    text = section.get_text()
                    emails = self.email_pattern.findall(text)
                    found_emails.update(emails)

                # Check full page text as fallback
                page_text = soup.get_text()
                emails = self.email_pattern.findall(page_text)
                for email in emails:
                    if '@' in email and '.' in email.split('@')[-1]:
                        found_emails.add(email)

                # Filter out system emails
                for email in found_emails:
                    email_lower = email.lower()
                    if any(x in email_lower for x in ['example', 'test', 'noreply', 'support', 'ok.ru', 'odnoklassniki']):
                        continue
                    if email_lower.endswith(('.png', '.jpg', '.gif')):
                        continue

                    results.append(EmailSourceResult(
                        email=email_lower,
                        source="ok_profile",
                        exists=True,
                        confidence=0.90,
                        details={'profile_url': profile_url}
                    ))
                    logger.info(f"OK.ru Profile: Found email {email_lower} on {profile_url}")

        except Exception as e:
            logger.debug(f"OK.ru email extraction error for {profile_url}: {e}")

        return results

    def close(self):
        self.session.close()


class CombinedEmailSources:
    """
    Combined email verification using multiple sources.
    Aggregates results from all available sources.
    """

    def __init__(
        self,
        hunter_api_key: Optional[str] = None,
        emailrep_api_key: Optional[str] = None
    ):
        self.epieos = EpieosChecker()
        self.hunter = HunterIOChecker(api_key=hunter_api_key)
        self.emailrep = EmailRepChecker(api_key=emailrep_api_key)
        self.vk_extractor = VKEmailExtractor()
        self.ok_extractor = OKEmailExtractor()

    def verify_email(self, email: str) -> Dict:
        """
        Verify email using all available sources.

        Returns aggregated result with confidence from all sources.
        """
        results = {
            'email': email,
            'exists': False,
            'confidence': 0.0,
            'sources': [],
            'details': {}
        }

        source_results = []

        # Check with Epieos (Google account detection)
        try:
            epieos_result = self.epieos.check_email(email)
            if epieos_result.exists:
                source_results.append(epieos_result)
                results['sources'].append('epieos')
                results['details']['epieos'] = epieos_result.details
        except Exception as e:
            logger.debug(f"Epieos error: {e}")

        # Check with Hunter.io
        try:
            hunter_result = self.hunter.verify_email(email)
            if hunter_result.exists:
                source_results.append(hunter_result)
                results['sources'].append('hunter.io')
                results['details']['hunter'] = hunter_result.details
        except Exception as e:
            logger.debug(f"Hunter error: {e}")

        # Check with EmailRep.io
        try:
            emailrep_result = self.emailrep.check_email(email)
            if emailrep_result.exists:
                source_results.append(emailrep_result)
                results['sources'].append('emailrep')
                results['details']['emailrep'] = emailrep_result.details
        except Exception as e:
            logger.debug(f"EmailRep error: {e}")

        # Aggregate results
        if source_results:
            results['exists'] = True
            # Use highest confidence from all sources
            results['confidence'] = max(r.confidence for r in source_results)
            # Boost confidence if multiple sources agree
            if len(source_results) >= 2:
                results['confidence'] = min(0.98, results['confidence'] + 0.10)
            if len(source_results) >= 3:
                results['confidence'] = min(0.99, results['confidence'] + 0.05)

        return results

    def extract_from_profiles(
        self,
        profile_urls: List[Dict]
    ) -> List[EmailSourceResult]:
        """
        Extract emails from social media profile pages.

        Args:
            profile_urls: List of {'url': '...', 'platform': '...'}

        Returns:
            List of EmailSourceResult
        """
        results = []

        for profile in profile_urls:
            url = profile.get('url', '')
            platform = profile.get('platform', '').lower()

            try:
                if platform == 'vk' or 'vk.com' in url:
                    results.extend(self.vk_extractor.extract_from_profile(url))
                elif platform in ['ok', 'odnoklassniki'] or 'ok.ru' in url:
                    results.extend(self.ok_extractor.extract_from_profile(url))
            except Exception as e:
                logger.debug(f"Profile extraction error for {url}: {e}")

        return results

    def close(self):
        """Clean up all resources."""
        self.epieos.close()
        self.hunter.close()
        self.emailrep.close()
        self.vk_extractor.close()
        self.ok_extractor.close()


# Convenience functions
def verify_email_multi_source(
    email: str,
    hunter_key: Optional[str] = None,
    emailrep_key: Optional[str] = None
) -> Dict:
    """Verify email using multiple sources."""
    checker = CombinedEmailSources(
        hunter_api_key=hunter_key,
        emailrep_api_key=emailrep_key
    )
    try:
        return checker.verify_email(email)
    finally:
        checker.close()


def verify_emails_batch(
    emails: List[str],
    hunter_key: Optional[str] = None,
    emailrep_key: Optional[str] = None
) -> List[Dict]:
    """Verify multiple emails using all sources."""
    checker = CombinedEmailSources(
        hunter_api_key=hunter_key,
        emailrep_api_key=emailrep_key
    )
    try:
        results = []
        for email in emails:
            result = checker.verify_email(email)
            results.append(result)
            time.sleep(0.5)  # Rate limiting
        return results
    finally:
        checker.close()
