"""
Mailcat Email Discovery Service
===============================
Discovers existing emails from usernames by checking if username@domain
exists across 170+ email domains using SMTP probing and API checks.

Based on: https://github.com/sharsil/mailcat
Unlike simple email generation, this VERIFIES which emails actually exist.

Russian domains supported:
- yandex.ru (+ ya.ru, yandex.com, yandex.by, yandex.kz, yandex.ua)
- mail.ru (+ bk.ru, list.ru, inbox.ru, internet.ru)
- rambler.ru (+ lenta.ru, myrambler.ru, autorambler.ru, ro.ru, r0.ru)
"""

import subprocess
import asyncio
import logging
from typing import List, Dict, Optional, Set
from dataclasses import dataclass, field
import re
import smtplib
import socket
from email.utils import parseaddr

logger = logging.getLogger(__name__)


# Russian email domains with their verification methods
RUSSIAN_EMAIL_DOMAINS = {
    # Mail.ru group (largest in Russia)
    'mail.ru': {'method': 'smtp', 'mx': 'mxs.mail.ru'},
    'bk.ru': {'method': 'smtp', 'mx': 'mxs.mail.ru'},
    'list.ru': {'method': 'smtp', 'mx': 'mxs.mail.ru'},
    'inbox.ru': {'method': 'smtp', 'mx': 'mxs.mail.ru'},
    'internet.ru': {'method': 'smtp', 'mx': 'mxs.mail.ru'},

    # Yandex group
    'yandex.ru': {'method': 'smtp', 'mx': 'mx.yandex.ru'},
    'ya.ru': {'method': 'smtp', 'mx': 'mx.yandex.ru'},
    'yandex.com': {'method': 'smtp', 'mx': 'mx.yandex.ru'},
    'yandex.by': {'method': 'smtp', 'mx': 'mx.yandex.ru'},
    'yandex.kz': {'method': 'smtp', 'mx': 'mx.yandex.ru'},
    'yandex.ua': {'method': 'smtp', 'mx': 'mx.yandex.ru'},

    # Rambler group
    'rambler.ru': {'method': 'smtp', 'mx': 'mx.rambler.ru'},
    'lenta.ru': {'method': 'smtp', 'mx': 'mx.rambler.ru'},
    'myrambler.ru': {'method': 'smtp', 'mx': 'mx.rambler.ru'},
    'autorambler.ru': {'method': 'smtp', 'mx': 'mx.rambler.ru'},
    'ro.ru': {'method': 'smtp', 'mx': 'mx.rambler.ru'},
    'r0.ru': {'method': 'smtp', 'mx': 'mx.rambler.ru'},
}


@dataclass
class EmailDiscoveryResult:
    """Result of email discovery for a username."""
    username: str
    verified_emails: List[str] = field(default_factory=list)  # Actually exist
    candidate_emails: List[str] = field(default_factory=list)  # Generated but not verified
    checked_domains: List[str] = field(default_factory=list)
    verification_method: str = 'none'  # 'mailcat', 'smtp', 'generated'
    errors: List[str] = field(default_factory=list)


class MailcatEmailDiscovery:
    """
    Discover existing emails from usernames.

    Priority order:
    1. Mailcat CLI (if installed) - most comprehensive
    2. SMTP verification - good for Russian domains
    3. Generation only - fallback without verification
    """

    def __init__(self, use_tor: bool = False, proxy: Optional[str] = None, timeout: int = 10):
        """
        Initialize email discovery service.

        Args:
            use_tor: Use Tor for mailcat queries
            proxy: HTTP proxy URL
            timeout: Timeout for SMTP connections
        """
        self.use_tor = use_tor
        self.proxy = proxy
        self.timeout = timeout
        self._mailcat_available = None

    def _check_mailcat_available(self) -> bool:
        """Check if mailcat CLI is available."""
        if self._mailcat_available is not None:
            return self._mailcat_available

        try:
            result = subprocess.run(
                ['mailcat', '--help'],
                capture_output=True,
                timeout=5
            )
            self._mailcat_available = result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            self._mailcat_available = False

        return self._mailcat_available

    def discover_emails(self, username: str, verify: bool = True) -> EmailDiscoveryResult:
        """
        Discover existing emails for a username.

        Args:
            username: Social media username to check
            verify: Whether to verify emails exist (slower but accurate)

        Returns:
            EmailDiscoveryResult with discovered/verified emails
        """
        result = EmailDiscoveryResult(username=username)

        # Clean username
        username = self._clean_username(username)
        if not username or len(username) < 2:
            result.errors.append('Username too short')
            return result

        # Try verification methods in order
        if verify:
            # Method 1: Try mailcat first (comprehensive)
            if self._check_mailcat_available():
                return self._discover_via_mailcat(username, result)

            # Method 2: SMTP verification for Russian domains
            return self._discover_via_smtp(username, result)

        # No verification - just generate candidates
        result.candidate_emails = self._generate_candidates(username)
        result.verification_method = 'generated'
        return result

    def _clean_username(self, username: str) -> str:
        """Clean and normalize username."""
        # Lowercase
        username = username.lower().strip()

        # Remove common social media prefixes
        username = re.sub(r'^(id|user|profile|@)', '', username)

        # Remove trailing numbers/underscores
        # username = re.sub(r'[_\d]+$', '', username)  # Commented - might be intentional

        # Remove special characters except underscore/dot
        username = re.sub(r'[^a-z0-9_.]', '', username)

        return username

    def _discover_via_mailcat(self, username: str, result: EmailDiscoveryResult) -> EmailDiscoveryResult:
        """Discover emails using mailcat CLI."""
        try:
            cmd = ['mailcat', username]
            if self.use_tor:
                cmd.append('--tor')
            if self.proxy:
                cmd.extend(['--proxy', self.proxy])

            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
                encoding='utf-8',
                errors='replace'
            )

            # Parse mailcat output
            verified = []
            for line in process.stdout.split('\n'):
                line = line.strip()
                # Mailcat outputs found emails in various formats
                if '@' in line:
                    # Extract email from line
                    email_match = re.search(r'[\w.+-]+@[\w.-]+\.\w+', line)
                    if email_match:
                        email = email_match.group().lower()
                        if self._is_valid_email(email):
                            verified.append(email)

            result.verified_emails = list(set(verified))
            result.verification_method = 'mailcat'

            # Also generate candidates for domains mailcat might have missed
            all_candidates = self._generate_candidates(username)
            result.candidate_emails = [
                e for e in all_candidates
                if e not in result.verified_emails
            ]

        except subprocess.TimeoutExpired:
            result.errors.append('Mailcat timeout')
            result.candidate_emails = self._generate_candidates(username)
            result.verification_method = 'generated'
        except Exception as e:
            result.errors.append(f'Mailcat error: {str(e)}')
            result.candidate_emails = self._generate_candidates(username)
            result.verification_method = 'generated'

        return result

    def _discover_via_smtp(self, username: str, result: EmailDiscoveryResult) -> EmailDiscoveryResult:
        """Discover emails using SMTP verification for Russian domains."""
        verified = []
        checked = []

        for domain, config in RUSSIAN_EMAIL_DOMAINS.items():
            email = f"{username}@{domain}"
            checked.append(domain)

            try:
                if self._verify_email_smtp(email, config.get('mx')):
                    verified.append(email)
            except Exception as e:
                logger.debug(f"SMTP check failed for {email}: {e}")

        result.verified_emails = verified
        result.checked_domains = checked
        result.verification_method = 'smtp'

        # Add unchecked domains as candidates
        all_candidates = self._generate_candidates(username)
        result.candidate_emails = [
            e for e in all_candidates
            if e not in verified
        ]

        return result

    def _verify_email_smtp(self, email: str, mx_server: Optional[str] = None) -> bool:
        """
        Verify email exists using SMTP.

        Warning: Many servers don't allow VRFY/RCPT checking.
        This is best-effort and may produce false negatives.
        """
        if not mx_server:
            # Try to get MX record
            domain = email.split('@')[1]
            try:
                import dns.resolver
                mx_records = dns.resolver.resolve(domain, 'MX')
                mx_server = str(mx_records[0].exchange).rstrip('.')
            except Exception:
                mx_server = f'mx.{domain}'

        try:
            # Connect to SMTP server
            smtp = smtplib.SMTP(timeout=self.timeout)
            smtp.connect(mx_server, 25)
            smtp.helo('verify.local')

            # Try RCPT TO
            code, _ = smtp.rcpt(email)
            smtp.quit()

            # 250 = OK, 251 = User not local but will forward
            return code in (250, 251)

        except smtplib.SMTPServerDisconnected:
            return False
        except smtplib.SMTPConnectError:
            return False
        except socket.timeout:
            return False
        except Exception as e:
            logger.debug(f"SMTP verification error: {e}")
            return False

    def _generate_candidates(self, username: str) -> List[str]:
        """Generate email candidates without verification."""
        candidates = []

        # All Russian domains
        all_domains = list(RUSSIAN_EMAIL_DOMAINS.keys())

        # Add some international domains
        all_domains.extend(['gmail.com', 'outlook.com', 'icloud.com'])

        for domain in all_domains:
            email = f"{username}@{domain}"
            if self._is_valid_email(email):
                candidates.append(email)

        return candidates

    def _is_valid_email(self, email: str) -> bool:
        """Basic email validation."""
        pattern = r'^[a-zA-Z0-9][a-zA-Z0-9._-]*@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email)) and len(email) <= 254

    def discover_from_usernames(self, usernames: List[str], verify: bool = True) -> List[EmailDiscoveryResult]:
        """
        Discover emails for multiple usernames.

        Args:
            usernames: List of usernames to check
            verify: Whether to verify emails exist

        Returns:
            List of EmailDiscoveryResult for each username
        """
        results = []
        for username in usernames:
            result = self.discover_emails(username, verify=verify)
            results.append(result)
        return results

    def get_all_verified_emails(self, usernames: List[str]) -> List[str]:
        """
        Get all verified emails from a list of usernames.
        Convenience method that returns flat list.
        """
        all_emails = set()
        results = self.discover_from_usernames(usernames, verify=True)
        for result in results:
            all_emails.update(result.verified_emails)
        return list(all_emails)


def discover_emails_for_username(username: str, verify: bool = True) -> EmailDiscoveryResult:
    """Convenience function for single username lookup."""
    service = MailcatEmailDiscovery()
    return service.discover_emails(username, verify=verify)


def discover_emails_for_usernames(usernames: List[str], verify: bool = True) -> List[str]:
    """Convenience function that returns flat list of verified emails."""
    service = MailcatEmailDiscovery()
    return service.get_all_verified_emails(usernames)
