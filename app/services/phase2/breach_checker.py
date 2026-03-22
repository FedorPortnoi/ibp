"""
Breach Checker Service
======================
Check if emails/usernames appear in known data breaches.
Uses multiple breach search services and local tools.

Supported services:
- Have I Been Pwned (HIBP) - free API for breach checking
- h8mail (local tool) - if installed
- LeakCheck API - if API key provided

IMPORTANT: This service only checks for EXISTENCE in breaches.
It does NOT retrieve or display passwords (even hashed).
"""

import subprocess
import requests
import hashlib
import logging
import re
import time
import json
from typing import List, Dict, Optional, Set
from urllib.parse import urlparse
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class BreachInfo:
    """Information about a single breach."""
    name: str
    date: Optional[str] = None
    breach_date: Optional[str] = None
    data_types: List[str] = field(default_factory=list)  # email, password, phone, etc.
    description: Optional[str] = None
    is_verified: bool = False
    is_sensitive: bool = False


@dataclass
class BreachCheckResult:
    """Results of breach check for a single target."""
    target: str  # email or username
    target_type: str  # 'email' or 'username'
    found_in_breaches: bool = False
    breaches: List[BreachInfo] = field(default_factory=list)
    breach_count: int = 0
    related_emails: List[str] = field(default_factory=list)
    data_exposed: List[str] = field(default_factory=list)  # Types of data exposed
    checked_services: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


class BreachChecker:
    """
    Check emails and usernames against breach databases.

    Uses ethical, publicly available breach notification services.
    Does NOT retrieve or expose passwords.
    """

    # Have I Been Pwned API
    HIBP_API_URL = "https://haveibeenpwned.com/api/v3"
    HIBP_BREACH_URL = f"{HIBP_API_URL}/breachedaccount"

    # Request headers
    HEADERS = {
        'User-Agent': 'IBP-OSINT-Tool/2.0',
        'Accept': 'application/json',
    }

    def __init__(
        self,
        hibp_api_key: Optional[str] = None,
        leakcheck_api_key: Optional[str] = None,
        use_h8mail: bool = True
    ):
        """
        Initialize breach checker.

        Args:
            hibp_api_key: Have I Been Pwned API key (optional, for full results)
            leakcheck_api_key: LeakCheck.io API key (optional)
            use_h8mail: Whether to try using h8mail if installed
        """
        self.hibp_api_key = hibp_api_key
        self.leakcheck_api_key = leakcheck_api_key
        self.use_h8mail = use_h8mail
        self._h8mail_available = None

    def _check_h8mail_available(self) -> bool:
        """Check if h8mail is installed."""
        if self._h8mail_available is not None:
            return self._h8mail_available

        try:
            result = subprocess.run(
                ['h8mail', '--help'],
                capture_output=True,
                timeout=5
            )
            self._h8mail_available = result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            self._h8mail_available = False

        return self._h8mail_available

    def check_email(self, email: str) -> BreachCheckResult:
        """
        Check if email appears in known breaches.

        Args:
            email: Email address to check

        Returns:
            BreachCheckResult with breach information
        """
        result = BreachCheckResult(
            target=email.lower(),
            target_type='email'
        )

        # Method 1: HIBP (free tier shows breach count)
        hibp_result = self._check_hibp(email)
        if hibp_result:
            result.breaches.extend(hibp_result)
            result.checked_services.append('haveibeenpwned.com')

        # Method 2: h8mail (if available)
        if self.use_h8mail and self._check_h8mail_available():
            h8mail_result = self._check_h8mail(email)
            if h8mail_result:
                # Merge results, avoiding duplicates
                existing_names = {b.name.lower() for b in result.breaches}
                for breach in h8mail_result:
                    if breach.name.lower() not in existing_names:
                        result.breaches.append(breach)
                result.checked_services.append('h8mail')

        # Method 3: LeakCheck (if API key provided)
        if self.leakcheck_api_key:
            leakcheck_result = self._check_leakcheck(email)
            if leakcheck_result:
                existing_names = {b.name.lower() for b in result.breaches}
                for breach in leakcheck_result:
                    if breach.name.lower() not in existing_names:
                        result.breaches.append(breach)
                result.checked_services.append('leakcheck.io')

        # Aggregate results
        result.found_in_breaches = len(result.breaches) > 0
        result.breach_count = len(result.breaches)

        # Collect data types exposed
        data_types = set()
        for breach in result.breaches:
            data_types.update(breach.data_types)
        result.data_exposed = sorted(data_types)

        return result

    def _check_hibp(self, email: str) -> List[BreachInfo]:
        """Check email against Have I Been Pwned."""
        breaches = []

        # HIBP v3 API requires an API key - skip if not available
        if not self.hibp_api_key:
            logger.warning("HIBP API key required for this request")
            return breaches

        try:
            headers = {**self.HEADERS}
            headers['hibp-api-key'] = self.hibp_api_key

            # Rate limit: HIBP requires 1500ms between requests
            time.sleep(1.6)

            response = requests.get(
                f"{self.HIBP_BREACH_URL}/{email}",
                headers=headers,
                params={'truncateResponse': 'false'},
                timeout=15
            )

            if response.status_code == 200:
                data = response.json()
                for breach_data in data:
                    breach = BreachInfo(
                        name=breach_data.get('Name', 'Unknown'),
                        date=breach_data.get('AddedDate'),
                        breach_date=breach_data.get('BreachDate'),
                        data_types=breach_data.get('DataClasses', []),
                        description=breach_data.get('Description'),
                        is_verified=breach_data.get('IsVerified', False),
                        is_sensitive=breach_data.get('IsSensitive', False)
                    )
                    breaches.append(breach)

            elif response.status_code == 404:
                # Not found in any breaches (good!)
                pass
            elif response.status_code == 401:
                logger.warning("HIBP API key required for this request")
            elif response.status_code == 429:
                logger.warning("HIBP rate limit exceeded")

        except requests.exceptions.Timeout:
            logger.warning("HIBP request timeout")
        except Exception as e:
            logger.error(f"HIBP check error: {e}")

        return breaches

    def _check_h8mail(self, email: str) -> List[BreachInfo]:
        """Check email using h8mail tool."""
        breaches = []

        try:
            # Run h8mail with email
            cmd = ['h8mail', '-t', email, '--hide']

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
                encoding='utf-8',
                errors='replace'
            )

            # Parse h8mail output
            output = result.stdout

            # Look for breach indicators in output
            # h8mail output format varies, look for common patterns
            if 'pwned' in output.lower() or 'breach' in output.lower():
                # Extract breach names from output
                for line in output.split('\n'):
                    if 'breach' in line.lower() or ':' in line:
                        # Try to extract breach name
                        parts = line.split(':')
                        if len(parts) >= 2:
                            name = parts[0].strip()
                            if name and len(name) > 2:
                                breaches.append(BreachInfo(name=name))

        except subprocess.TimeoutExpired:
            logger.warning("h8mail timeout")
        except Exception as e:
            logger.debug(f"h8mail check error: {e}")

        return breaches

    def _check_leakcheck(self, email: str) -> List[BreachInfo]:
        """Check email using LeakCheck.io API."""
        breaches = []

        if not self.leakcheck_api_key:
            return breaches

        try:
            response = requests.get(
                f"https://leakcheck.io/api/public",
                params={'check': email, 'key': self.leakcheck_api_key},
                timeout=15
            )

            if response.status_code == 200:
                data = response.json()
                if data.get('success') and data.get('found'):
                    for source in data.get('sources', []):
                        breach = BreachInfo(
                            name=source.get('name', 'Unknown'),
                            date=source.get('date'),
                            data_types=['email']  # LeakCheck confirms email exposure
                        )
                        breaches.append(breach)

        except Exception as e:
            logger.debug(f"LeakCheck error: {e}")

        return breaches

    def check_multiple_emails(self, emails: List[str]) -> List[BreachCheckResult]:
        """
        Check multiple emails for breaches.

        Args:
            emails: List of email addresses

        Returns:
            List of BreachCheckResult for each email
        """
        results = []
        for email in emails:
            result = self.check_email(email)
            results.append(result)
        return results

    def get_breach_summary(self, results: List[BreachCheckResult]) -> Dict:
        """
        Generate summary of breach check results.

        Args:
            results: List of BreachCheckResult

        Returns:
            Summary dict with statistics
        """
        total_checked = len(results)
        breached = [r for r in results if r.found_in_breaches]
        clean = [r for r in results if not r.found_in_breaches]

        all_breaches = set()
        all_data_types = set()
        for r in breached:
            for b in r.breaches:
                all_breaches.add(b.name)
                all_data_types.update(b.data_types)

        return {
            'total_checked': total_checked,
            'breached_count': len(breached),
            'clean_count': len(clean),
            'breached_emails': [r.target for r in breached],
            'unique_breaches': sorted(all_breaches),
            'data_types_exposed': sorted(all_data_types),
        }


def check_email_breaches(email: str, hibp_key: Optional[str] = None) -> BreachCheckResult:
    """Convenience function to check single email."""
    checker = BreachChecker(hibp_api_key=hibp_key)
    return checker.check_email(email)


def check_emails_breaches(emails: List[str], hibp_key: Optional[str] = None) -> List[BreachCheckResult]:
    """Convenience function to check multiple emails."""
    checker = BreachChecker(hibp_api_key=hibp_key)
    return checker.check_multiple_emails(emails)


# ── Breach Intelligence Analysis ─────────────────────────────────────────

FINANCIAL_DOMAINS = {
    'sberbank.ru', 'tinkoff.ru', 'vtb.ru', 'alfabank.ru', 'binance.com',
    'coinbase.com', 'bybit.com', 'blockchain.com', 'qiwi.com', 'paypal.com',
    'raiffeisen.ru', 'gazprombank.ru', 'rosbank.ru', 'otkritie.ru',
    'sovcombank.ru', 'rocketbank.ru', 'homecredit.ru', 'pochta-bank.ru',
    'kraken.com', 'okx.com', 'gate.io', 'kucoin.com', 'huobi.com',
    'webmoney.ru', 'yoomoney.ru', 'robokassa.ru', 'stripe.com',
}

# Email domains to exclude from old_emails (these are the search targets, not discoveries)
_COMMON_PROVIDER_DOMAINS = {
    'gmail.com', 'mail.ru', 'yandex.ru', 'yahoo.com', 'outlook.com',
    'hotmail.com', 'inbox.ru', 'bk.ru', 'list.ru', 'rambler.ru',
    'icloud.com', 'protonmail.com', 'internet.ru',
}

# Phone regex for extracting phones from breach data
_PHONE_RE = re.compile(r'(?:\+7|8)\d{10}')


def _extract_domain(url: str) -> Optional[str]:
    """Extract clean domain from a URL. Returns None for invalid/empty URLs."""
    if not url:
        return None
    try:
        # Ensure scheme for urlparse
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        parsed = urlparse(url)
        domain = parsed.hostname
        if not domain:
            return None
        # Strip www. prefix
        if domain.startswith('www.'):
            domain = domain[4:]
        # Basic sanity: must have at least one dot
        if '.' not in domain:
            return None
        return domain.lower()
    except Exception:
        return None


def analyze_breach_intelligence(emails: list = None, phones: list = None) -> dict:
    """
    Analyze breach data for intelligence: services used, old emails/phones,
    financial exposure. Uses HudsonRock, LeakCheck, and ProxyNova COMB APIs.

    CRITICAL: Never includes passwords in the return value. Only extracts
    service domains and contact metadata from breach records.

    Args:
        emails: List of email addresses to check
        phones: List of phone numbers to check (for future phone-based lookups)

    Returns:
        {
            'services_used': ['vk.com', 'mail.ru', ...],
            'old_emails': ['old@mail.ru', ...],
            'old_phones': ['+7...', ...],
            'breach_count': int,
            'breach_sources': ['HudsonRock', 'LeakCheck', ...],
            'has_financial_services': bool,
        }
    """
    emails = [e.lower().strip() for e in (emails or []) if e and '@' in e]
    phones = [p.strip() for p in (phones or []) if p]

    if not emails and not phones:
        return {
            'services_used': [],
            'old_emails': [],
            'old_phones': [],
            'breach_count': 0,
            'breach_sources': [],
            'has_financial_services': False,
        }

    services_used: Set[str] = set()
    old_emails: Set[str] = set()
    old_phones: Set[str] = set()
    breach_count = 0
    breach_sources: Set[str] = set()
    search_email_set = set(emails)  # to distinguish old vs. searched emails

    # Limit to top 10 emails to avoid excessive API calls
    emails_to_check = emails[:10]

    # ── HudsonRock Cavalier (free, no key) ─────────────────────────
    try:
        from app.services.phase2.sources.breach_api import HudsonRockSource
        hr = HudsonRockSource()
        for email in emails_to_check:
            try:
                results = hr.query(email=email)
                if not results:
                    continue
                breach_sources.add('HudsonRock')
                for r in results:
                    # Count breaches (email-type results with breach_confirmed)
                    if (r.data_type == 'email' and
                            r.metadata.get('verification') == 'breach_confirmed'):
                        breach_count += r.metadata.get('stealer_count', 1)

                    # Extract service domains from credential URLs
                    if r.data_type == 'credential' and r.metadata:
                        url = r.metadata.get('url') or r.raw_data.get('url', '')
                        domain = _extract_domain(url)
                        if domain:
                            services_used.add(domain)

                    # Extract old emails (emails different from what we searched)
                    if r.data_type == 'email' and r.value:
                        val = r.value.lower().strip()
                        if val not in search_email_set:
                            old_emails.add(val)

                    # Extract old phones from metadata/raw_data
                    if r.data_type == 'phone' and r.value:
                        old_phones.add(r.value.strip())

            except Exception as e:
                logger.warning(f"HudsonRock breach intelligence error for {email}: {e}")
    except ImportError:
        logger.debug("HudsonRock source not available for breach intelligence")

    # ── LeakCheck Public (free, no key) ────────────────────────────
    try:
        from app.services.phase2.sources.breach_api import LeakCheckSource
        lc = LeakCheckSource()
        for email in emails_to_check:
            try:
                results = lc.query(email=email)
                if not results:
                    continue
                breach_sources.add('LeakCheck')
                for r in results:
                    if r.metadata.get('breach_names'):
                        breach_count += len(r.metadata['breach_names'])
                        # Breach names often correspond to service domains
                        for bname in r.metadata['breach_names']:
                            # Try to interpret breach name as domain
                            bname_lower = bname.lower().strip()
                            if '.' in bname_lower and len(bname_lower) <= 60:
                                domain = _extract_domain(bname_lower)
                                if domain:
                                    services_used.add(domain)
                            # Common breach name → domain mappings
                            elif bname_lower in _BREACH_NAME_TO_DOMAIN:
                                services_used.add(_BREACH_NAME_TO_DOMAIN[bname_lower])
            except Exception as e:
                logger.warning(f"LeakCheck breach intelligence error for {email}: {e}")
    except ImportError:
        logger.debug("LeakCheck source not available for breach intelligence")

    # ── ProxyNova COMB (free, no key) ──────────────────────────────
    try:
        from app.services.phase2.sources.breach_api import ProxyNovaCOMBSource
        pn = ProxyNovaCOMBSource()
        for email in emails_to_check:
            try:
                results = pn.query(email=email)
                if not results:
                    continue
                breach_sources.add('ProxyNova COMB')
                for r in results:
                    if (r.data_type == 'email' and
                            r.metadata.get('verification') == 'breach_confirmed'):
                        breach_count += r.metadata.get('total_records', 1)

                    # Discover old emails from COMB results
                    if r.data_type == 'email' and r.value:
                        val = r.value.lower().strip()
                        if val not in search_email_set:
                            old_emails.add(val)
            except Exception as e:
                logger.warning(f"ProxyNova breach intelligence error for {email}: {e}")
    except ImportError:
        logger.debug("ProxyNova COMB source not available for breach intelligence")

    # ── HIBP (BreachChecker from this module — if HIBP key available) ──
    try:
        import os
        hibp_key = os.environ.get('HIBP_API_KEY')
        if hibp_key:
            checker = BreachChecker(hibp_api_key=hibp_key)
            for email in emails_to_check[:3]:  # HIBP has strict rate limits
                try:
                    result = checker.check_email(email)
                    if result.found_in_breaches:
                        breach_sources.add('HIBP')
                        breach_count += result.breach_count
                        # Extract breach names as potential service domains
                        for b in result.breaches:
                            bname_lower = b.name.lower().strip()
                            if '.' in bname_lower:
                                domain = _extract_domain(bname_lower)
                                if domain:
                                    services_used.add(domain)
                            elif bname_lower in _BREACH_NAME_TO_DOMAIN:
                                services_used.add(_BREACH_NAME_TO_DOMAIN[bname_lower])
                except Exception as e:
                    logger.warning(f"HIBP breach intelligence error for {email}: {e}")
    except Exception as e:
        logger.debug(f"HIBP check skipped: {e}")

    # ── Post-processing ────────────────────────────────────────────

    # Check for financial services
    has_financial = bool(services_used & FINANCIAL_DOMAINS)

    # Clean up old_emails: remove search targets and masked/invalid entries
    old_emails_clean = []
    for oe in old_emails:
        if oe in search_email_set:
            continue
        if '*' in oe or not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', oe):
            continue
        old_emails_clean.append(oe)

    # Clean up old_phones: normalize
    old_phones_clean = []
    for op in old_phones:
        digits = re.sub(r'\D', '', op)
        if len(digits) >= 10:
            if digits.startswith('8') and len(digits) == 11:
                digits = '7' + digits[1:]
            old_phones_clean.append('+' + digits)

    return {
        'services_used': sorted(services_used)[:30],
        'old_emails': old_emails_clean[:10],
        'old_phones': old_phones_clean[:10],
        'breach_count': breach_count,
        'breach_sources': sorted(breach_sources),
        'has_financial_services': has_financial,
    }


# Common breach name → domain mappings (breach names that don't look like domains)
_BREACH_NAME_TO_DOMAIN = {
    'vk': 'vk.com',
    'vkontakte': 'vk.com',
    'mail.ru': 'mail.ru',
    'mailru': 'mail.ru',
    'yandex': 'yandex.ru',
    'linkedin': 'linkedin.com',
    'facebook': 'facebook.com',
    'adobe': 'adobe.com',
    'dropbox': 'dropbox.com',
    'myspace': 'myspace.com',
    'twitter': 'twitter.com',
    'tumblr': 'tumblr.com',
    'spotify': 'spotify.com',
    'badoo': 'badoo.com',
    'canva': 'canva.com',
    'wattpad': 'wattpad.com',
    'zynga': 'zynga.com',
    'dubsmash': 'dubsmash.com',
    'sberbank': 'sberbank.ru',
    'tinkoff': 'tinkoff.ru',
    'qiwi': 'qiwi.com',
    'avito': 'avito.ru',
    'wildberries': 'wildberries.ru',
    'ozon': 'ozon.ru',
    'pikabu': 'pikabu.ru',
    'habr': 'habr.com',
    'steam': 'store.steampowered.com',
    'rambler': 'rambler.ru',
    'ok': 'ok.ru',
    'odnoklassniki': 'ok.ru',
    'telegram': 'telegram.org',
    'whatsapp': 'whatsapp.com',
    'instagram': 'instagram.com',
    'snapchat': 'snapchat.com',
    'tiktok': 'tiktok.com',
    'netflix': 'netflix.com',
    'amazon': 'amazon.com',
    'ebay': 'ebay.com',
    'coinbase': 'coinbase.com',
    'binance': 'binance.com',
    'paypal': 'paypal.com',
}
