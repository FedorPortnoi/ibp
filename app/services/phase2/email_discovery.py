"""
Email Discovery Service - Holehe + SMTP + Gravatar Verification
================================================================
Discovers and verifies emails using multiple methods in parallel.
Target: Complete in under 60 seconds.

Verification methods (ordered by reliability):
1. Holehe library - checks registration on 120+ services (BEST)
2. SMTP RCPT TO - verifies mailbox exists at mail server
3. Gravatar JSON profile - checks if avatar/profile exists
4. MX record validation - confirms domain accepts email
5. Profile scraping - extracts visible emails from pages
"""

import asyncio
import aiohttp
import logging
import re
import socket
import time
from typing import List, Dict, Optional, Set, Tuple
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor

from app.services.phase1.transliteration import transliterate

logger = logging.getLogger(__name__)


@dataclass
class DiscoveredEmail:
    """An email discovered during investigation."""
    email: str
    source: str
    confidence: str  # "high", "medium", "low"
    verified: bool = False
    verified_on: List[str] = field(default_factory=list)
    verification: str = 'unverified'  # holehe_confirmed, smtp_verified, gravatar, likely, pattern


@dataclass
class EmailDiscoveryResults:
    """Complete results from email discovery."""
    emails: List[DiscoveredEmail] = field(default_factory=list)
    candidates_generated: int = 0
    candidates_verified: int = 0
    discovery_time: float = 0
    errors: List[str] = field(default_factory=list)


# Russian email domains - most popular
RUSSIAN_EMAIL_DOMAINS = [
    'mail.ru', 'yandex.ru', 'ya.ru', 'bk.ru', 'list.ru',
    'inbox.ru', 'rambler.ru', 'gmail.com', 'outlook.com'
]

# MX servers for quick validation
KNOWN_MX_SERVERS = {
    'mail.ru': 'mxs.mail.ru',
    'bk.ru': 'mxs.mail.ru',
    'list.ru': 'mxs.mail.ru',
    'inbox.ru': 'mxs.mail.ru',
    'yandex.ru': 'mx.yandex.ru',
    'ya.ru': 'mx.yandex.ru',
    'rambler.ru': 'mx.rambler.ru',
    'gmail.com': 'gmail-smtp-in.l.google.com',
}

# Domains that block SMTP verification
SMTP_BLOCKED_DOMAINS = {'mail.ru', 'bk.ru', 'list.ru', 'inbox.ru', 'yandex.ru', 'ya.ru'}

# Catch-all domains (always accept, can't verify individual addresses)
CATCH_ALL_DOMAINS = {'gmail.com', 'outlook.com', 'hotmail.com', 'yahoo.com', 'icloud.com'}


class EmailDiscoveryService:
    """
    Email discovery + verification service.
    Uses Holehe (library), SMTP, and Gravatar for verification.
    Designed to complete in under 60 seconds.
    """

    def __init__(
        self,
        max_candidates: int = 30,
        verify_timeout: float = 5.0,
        max_concurrent: int = 10
    ):
        self.max_candidates = max_candidates
        self.verify_timeout = verify_timeout
        self.max_concurrent = max_concurrent
        self._executor = ThreadPoolExecutor(max_workers=5)

    async def discover(
        self,
        first_name: str,
        last_name: str,
        usernames: List[str],
        profile_urls: List[Dict] = None
    ) -> EmailDiscoveryResults:
        """
        Discover emails using multiple methods in parallel.

        Args:
            first_name: Target's first name
            last_name: Target's last name
            usernames: Known usernames from Phase 1
            profile_urls: Profile URLs with platform info

        Returns:
            EmailDiscoveryResults with discovered emails
        """
        start_time = time.time()
        results = EmailDiscoveryResults()
        all_emails: Dict[str, DiscoveredEmail] = {}

        logger.info(f"Starting email discovery: {first_name} {last_name}, {len(usernames)} usernames")

        try:
            # Step 1: Generate email candidates (fast, synchronous)
            candidates = self._generate_candidates(first_name, last_name, usernames)
            results.candidates_generated = len(candidates)
            logger.info(f"Generated {len(candidates)} email candidates")

            # Step 2: Run verification methods in parallel
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.verify_timeout)
            ) as session:

                # Create all verification tasks
                tasks = []

                # Task 1: Verify candidates with Holehe library (highest priority)
                tasks.append(self._verify_with_holehe_batch(candidates[:10]))

                # Task 2: SMTP verification for top candidates
                tasks.append(self._verify_smtp_batch(candidates[:15]))

                # Task 3: Check Gravatar JSON profiles
                tasks.append(self._check_gravatar_batch(session, candidates[:20]))

                # Task 4: Check if emails have MX records (quick validation)
                tasks.append(self._validate_mx_batch(candidates))

                # Task 5: Scrape profile URLs for visible emails
                if profile_urls:
                    tasks.append(self._scrape_profiles_async(session, profile_urls))

                # Task 6: Check username-based emails on Russian services
                tasks.append(self._check_russian_services(session, usernames[:5]))

                # Run all tasks with overall timeout
                try:
                    task_results = await asyncio.wait_for(
                        asyncio.gather(*tasks, return_exceptions=True),
                        timeout=15.0  # 15 second overall timeout
                    )
                except asyncio.TimeoutError:
                    logger.warning("Overall timeout reached, using partial results")
                    task_results = []

                # Merge results from all tasks
                for i, task_result in enumerate(task_results):
                    if isinstance(task_result, Exception):
                        results.errors.append(f"Task {i} error: {str(task_result)}")
                        continue
                    if isinstance(task_result, list):
                        for email_info in task_result:
                            if isinstance(email_info, DiscoveredEmail):
                                key = email_info.email.lower()
                                if key not in all_emails:
                                    all_emails[key] = email_info
                                else:
                                    # Merge verification info
                                    existing = all_emails[key]
                                    existing.verified_on.extend(email_info.verified_on)
                                    existing.verified_on = list(set(existing.verified_on))
                                    if email_info.verified:
                                        existing.verified = True
                                    # Promote confidence based on multiple verifications
                                    if len(existing.verified_on) >= 2:
                                        existing.confidence = 'high'
                                        existing.verification = 'multi_verified'
                                    elif email_info.confidence == 'high':
                                        existing.confidence = 'high'
                                    # Prefer stronger verification type
                                    verification_priority = {
                                        'holehe_confirmed': 0,
                                        'smtp_verified': 1,
                                        'gravatar': 2,
                                        'multi_verified': 0,
                                        'likely': 3,
                                        'pattern': 4,
                                        'unverified': 5,
                                    }
                                    if verification_priority.get(email_info.verification, 5) < \
                                       verification_priority.get(existing.verification, 5):
                                        existing.verification = email_info.verification

        except Exception as e:
            results.errors.append(f"Discovery error: {str(e)}")
            logger.error(f"Email discovery error: {e}")

        # Finalize results - sort by verification strength then confidence
        verification_order = {
            'holehe_confirmed': 0, 'multi_verified': 0, 'smtp_verified': 1,
            'gravatar': 2, 'likely': 3, 'pattern': 4, 'unverified': 5,
        }
        results.emails = sorted(
            all_emails.values(),
            key=lambda e: (
                verification_order.get(e.verification, 5),
                0 if e.confidence == 'high' else 1 if e.confidence == 'medium' else 2,
            )
        )
        results.candidates_verified = len([e for e in results.emails if e.verified])
        results.discovery_time = time.time() - start_time

        logger.info(
            f"Email discovery complete: {len(results.emails)} emails found, "
            f"{results.candidates_verified} verified in {results.discovery_time:.1f}s"
        )

        return results

    def _generate_candidates(
        self,
        first_name: str,
        last_name: str,
        usernames: List[str]
    ) -> List[str]:
        """Generate email candidates from name and usernames."""
        candidates = set()

        # Transliterate Russian names to Latin
        fname = transliterate(first_name.lower().strip())
        lname = transliterate(last_name.lower().strip())

        # Name-based patterns
        patterns = [
            f"{fname}.{lname}",
            f"{fname}{lname}",
            f"{lname}.{fname}",
            f"{fname}_{lname}",
            f"{fname[0]}{lname}" if fname else "",
            f"{fname}{lname[0]}" if lname else "",
            f"{lname}{fname}",
            fname,
            lname,
        ]

        # Add username-based patterns
        for username in usernames[:10]:
            clean_user = self._clean_username(username)
            if clean_user and len(clean_user) >= 3:
                patterns.append(clean_user)

        # Generate emails for each pattern and domain
        for pattern in patterns:
            if not pattern or len(pattern) < 2:
                continue
            for domain in RUSSIAN_EMAIL_DOMAINS:
                email = f"{pattern}@{domain}"
                if self._is_valid_email(email):
                    candidates.add(email.lower())

        return list(candidates)[:self.max_candidates]

    def _clean_username(self, username: str) -> str:
        """Clean username for email generation."""
        username = re.sub(r'^(id|user|profile|@)', '', username.lower())
        username = re.sub(r'[^a-z0-9_.]', '', username)
        return username

    def _is_valid_email(self, email: str) -> bool:
        """Validate email format."""
        pattern = r'^[a-z0-9][a-z0-9._-]*@[a-z0-9.-]+\.[a-z]{2,}$'
        return bool(re.match(pattern, email.lower())) and len(email) <= 254

    # ── Holehe Verification (Library API) ────────────────────────────

    async def _verify_with_holehe_batch(
        self,
        emails: List[str]
    ) -> List[DiscoveredEmail]:
        """
        Verify emails using holehe library directly (not CLI).
        Runs checks concurrently (up to 3 at a time) with per-email timeout.
        """
        verified = []
        loop = asyncio.get_running_loop()

        # Tier the emails: Russian domains first, then international
        tier1_domains = {'mail.ru', 'yandex.ru', 'bk.ru', 'gmail.com'}
        tier1 = [e for e in emails if e.split('@')[-1] in tier1_domains][:4]
        tier2 = [e for e in emails if e not in tier1][:4]

        async def check_one(email: str) -> Optional[DiscoveredEmail]:
            try:
                result = await asyncio.wait_for(
                    loop.run_in_executor(
                        self._executor,
                        self._holehe_check_single,
                        email
                    ),
                    timeout=5.0  # 5s per email
                )
                if result:
                    services = result.get('services', [])
                    if services:
                        confidence = 'high' if len(services) >= 2 else 'medium'
                        logger.info(f"Holehe verified: {email} on {len(services)} services: {services[:5]}")
                        return DiscoveredEmail(
                            email=email,
                            source="Holehe verification",
                            confidence=confidence,
                            verified=True,
                            verified_on=[f'holehe:{s}' for s in services[:5]],
                            verification='holehe_confirmed'
                        )
            except asyncio.TimeoutError:
                logger.debug(f"Holehe timeout for {email}")
            except Exception as e:
                logger.debug(f"Holehe error for {email}: {e}")
            return None

        # Check Tier 1 concurrently (up to 3 at once)
        semaphore = asyncio.Semaphore(3)

        async def check_with_limit(email: str):
            async with semaphore:
                return await check_one(email)

        tier1_results = await asyncio.gather(
            *[check_with_limit(e) for e in tier1],
            return_exceptions=True
        )
        for r in tier1_results:
            if isinstance(r, DiscoveredEmail):
                verified.append(r)

        # Only check Tier 2 if Tier 1 found nothing
        if not verified and tier2:
            tier2_results = await asyncio.gather(
                *[check_with_limit(e) for e in tier2],
                return_exceptions=True
            )
            for r in tier2_results:
                if isinstance(r, DiscoveredEmail):
                    verified.append(r)

        return verified

    def _holehe_check_single(self, email: str) -> Optional[Dict]:
        """
        Run Holehe check for a single email using library API.
        Falls back to CLI if library import fails.
        """
        # Method 1: Use holehe library directly via asyncio + httpx
        try:
            import asyncio
            import httpx

            services = []

            async def _check(email_addr):
                from holehe.core import get_functions, import_submodules
                import holehe.modules

                modules = import_submodules(holehe.modules)
                websites = get_functions(modules)

                out = []
                async with httpx.AsyncClient(timeout=5.0) as client:
                    # Run ALL modules simultaneously for maximum speed
                    tasks = [_safe_call(func, email_addr, client, out)
                             for func in websites]
                    await asyncio.gather(*tasks)
                return out

            async def _safe_call(func, email_addr, client, out):
                try:
                    await asyncio.wait_for(func(email_addr, client, out), timeout=8.0)
                except (asyncio.TimeoutError, Exception):
                    pass

            # Run in a fresh event loop (safe from ThreadPoolExecutor)
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                results = loop.run_until_complete(
                    asyncio.wait_for(_check(email), timeout=25.0)
                )
            except RuntimeError as e:
                logger.warning(f"Holehe event loop error: {e}")
                results = []
            except asyncio.TimeoutError:
                logger.warning(f"Holehe verification timed out for {email}")
                results = []
            finally:
                loop.close()

            for r in results:
                if isinstance(r, dict) and r.get('exists') is True:
                    name = r.get('name', 'unknown')
                    if name and name != 'unknown':
                        services.append(name)

            return {'services': services} if services else None

        except ImportError:
            logger.debug("httpx/holehe not available, trying CLI fallback")
        except Exception as e:
            logger.debug(f"Holehe library error for {email}: {e}")

        # Method 2: CLI fallback
        return self._holehe_check_cli(email)

    def _holehe_check_cli(self, email: str) -> Optional[Dict]:
        """Run holehe via CLI as fallback."""
        import subprocess
        try:
            result = subprocess.run(
                ['holehe', email, '--only-used', '--no-color', '--no-clear', '-T', '3'],
                capture_output=True,
                text=True,
                timeout=5,
                encoding='utf-8',
                errors='replace'
            )

            services = []
            for line in result.stdout.split('\n'):
                if '[+]' in line:
                    parts = line.split('[+]')
                    if len(parts) > 1:
                        service = parts[1].strip().split(':')[0].split()[0]
                        if service and len(service) > 1:
                            services.append(service)

            return {'services': services} if services else None

        except (subprocess.TimeoutExpired, FileNotFoundError):
            return None
        except Exception as e:
            logger.debug(f"[EmailDiscovery] Holehe check failed: {e}")
            return None

    # ── SMTP Verification ────────────────────────────────────────────

    async def _verify_smtp_batch(
        self,
        emails: List[str]
    ) -> List[DiscoveredEmail]:
        """
        Verify emails via SMTP RCPT TO command.
        Runs blocking SMTP checks in thread pool.
        """
        verified = []
        loop = asyncio.get_running_loop()
        checked_count = 0

        for email in emails:
            domain = email.split('@')[-1] if '@' in email else ''

            # Skip domains that block SMTP verification
            if domain in SMTP_BLOCKED_DOMAINS or domain in CATCH_ALL_DOMAINS:
                # Mark as 'likely' for popular Russian domains
                if domain in SMTP_BLOCKED_DOMAINS:
                    verified.append(DiscoveredEmail(
                        email=email,
                        source="Pattern generation",
                        confidence="low",
                        verified=False,
                        verified_on=[],
                        verification='likely'
                    ))
                continue

            if checked_count >= 10:  # Limit SMTP checks
                break

            try:
                result = await asyncio.wait_for(
                    loop.run_in_executor(
                        self._executor,
                        self._smtp_verify_single,
                        email
                    ),
                    timeout=5.0
                )

                checked_count += 1

                if result is True:
                    verified.append(DiscoveredEmail(
                        email=email,
                        source="SMTP verification",
                        confidence="high",
                        verified=True,
                        verified_on=['smtp'],
                        verification='smtp_verified'
                    ))
                    logger.info(f"SMTP verified: {email}")
                elif result is False:
                    # Email rejected by server - doesn't exist, skip it
                    logger.debug(f"SMTP rejected: {email}")
                # None = inconclusive, don't add

            except asyncio.TimeoutError:
                logger.debug(f"SMTP timeout for {email}")
            except Exception as e:
                logger.debug(f"SMTP error for {email}: {e}")

        return verified

    def _smtp_verify_single(self, email: str) -> Optional[bool]:
        """
        Verify a single email via SMTP RCPT TO.
        Returns True (exists), False (rejected), None (inconclusive).
        """
        import smtplib
        try:
            import dns.resolver
        except ImportError:
            return None

        domain = email.split('@')[1]

        try:
            mx_records = dns.resolver.resolve(domain, 'MX')
            mx_host = str(mx_records[0].exchange).rstrip('.')

            server = smtplib.SMTP(timeout=8)
            server.connect(mx_host)
            server.helo('verify.example.com')
            server.mail('verify@example.com')
            code, message = server.rcpt(email)
            server.quit()

            if code == 250:
                return True
            elif code in (550, 551, 552, 553, 554):
                return False
            else:
                return None

        except dns.resolver.NXDOMAIN:
            return False
        except (dns.resolver.NoAnswer, dns.resolver.NoNameservers):
            return None
        except (smtplib.SMTPConnectError, smtplib.SMTPServerDisconnected,
                ConnectionRefusedError, TimeoutError, OSError):
            return None
        except Exception as e:
            logger.debug(f"SMTP error for {email}: {e}")
            return None

    # ── Gravatar Verification ────────────────────────────────────────

    async def _check_gravatar_batch(
        self,
        session: aiohttp.ClientSession,
        emails: List[str]
    ) -> List[DiscoveredEmail]:
        """Check Gravatar JSON profile for email existence (more reliable than HEAD)."""
        import hashlib
        verified = []

        async def check_one(email: str) -> Optional[DiscoveredEmail]:
            try:
                email_hash = hashlib.md5(email.lower().encode(), usedforsecurity=False).hexdigest()
                # Use JSON profile endpoint (more data than just avatar HEAD)
                url = f"https://gravatar.com/{email_hash}.json"

                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        entry = data.get('entry', [{}])[0]
                        display_name = entry.get('displayName', '')
                        profile_url = entry.get('profileUrl', '')

                        verified_on_list = ['gravatar']
                        # Extract linked accounts as extra verification
                        for account in entry.get('accounts', []):
                            domain = account.get('domain', '')
                            if domain:
                                verified_on_list.append(f'gravatar:{domain}')

                        return DiscoveredEmail(
                            email=email,
                            source=f"Gravatar ({display_name})" if display_name else "Gravatar",
                            confidence="high" if len(verified_on_list) > 1 else "medium",
                            verified=True,
                            verified_on=verified_on_list[:5],
                            verification='gravatar'
                        )
            except Exception as e:
                logger.debug(f"[EmailDiscovery] Gravatar check failed for '{email}': {e}")
            return None

        # Check all in parallel with semaphore
        semaphore = asyncio.Semaphore(self.max_concurrent)

        async def check_with_semaphore(email: str):
            async with semaphore:
                return await check_one(email)

        results = await asyncio.gather(
            *[check_with_semaphore(e) for e in emails],
            return_exceptions=True
        )

        for result in results:
            if isinstance(result, DiscoveredEmail):
                verified.append(result)

        return verified

    # ── MX Validation ────────────────────────────────────────────────

    async def _validate_mx_batch(
        self,
        emails: List[str]
    ) -> List[DiscoveredEmail]:
        """Validate emails have valid MX records (quick check)."""
        validated = []
        checked_domains = set()

        loop = asyncio.get_running_loop()

        for email in emails:
            domain = email.split('@')[-1]

            if domain in checked_domains:
                continue
            checked_domains.add(domain)

            try:
                has_mx = await asyncio.wait_for(
                    loop.run_in_executor(self._executor, self._check_mx, domain),
                    timeout=2.0
                )

                if has_mx:
                    for e in emails:
                        if e.split('@')[-1] == domain:
                            validated.append(DiscoveredEmail(
                                email=e,
                                source="Pattern generation",
                                confidence="low",
                                verified=False,
                                verified_on=[],
                                verification='pattern'
                            ))

            except Exception as e:
                logger.debug(f"[EmailDiscovery] MX validation failed for batch: {e}")

        return validated

    def _check_mx(self, domain: str) -> bool:
        """Check if domain has MX records."""
        try:
            if domain in KNOWN_MX_SERVERS:
                return True

            import dns.resolver
            try:
                dns.resolver.resolve(domain, 'MX')
                return True
            except Exception as e:
                logger.debug(f"[EmailDiscovery] MX resolve failed for {domain}: {e}")

            socket.getaddrinfo(f'mail.{domain}', 25)
            return True

        except Exception as e:
            logger.debug(f"[EmailDiscovery] MX check failed for {domain}: {e}")
            return False

    # ── Profile Scraping ─────────────────────────────────────────────

    async def _scrape_profiles_async(
        self,
        session: aiohttp.ClientSession,
        profiles: List[Dict]
    ) -> List[DiscoveredEmail]:
        """Scrape profile pages for visible emails."""
        found = []
        email_pattern = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')

        async def scrape_one(profile: Dict) -> List[DiscoveredEmail]:
            emails = []
            url = profile.get('url', '')
            platform = profile.get('platform', '')

            if not url:
                return emails

            try:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        text = await response.text()

                        matches = email_pattern.findall(text)
                        for email in set(matches):
                            email_lower = email.lower()
                            if any(x in email_lower for x in ['example', 'test', 'noreply', 'support']):
                                continue
                            if email_lower.endswith(('.png', '.jpg', '.gif', '.svg')):
                                continue

                            emails.append(DiscoveredEmail(
                                email=email_lower,
                                source=f"{platform.upper()} profile",
                                confidence="high",
                                verified=True,
                                verified_on=[platform],
                                verification='profile_scraped'
                            ))

            except Exception as e:
                logger.debug(f"Scrape error for {url}: {e}")

            return emails

        semaphore = asyncio.Semaphore(5)

        async def scrape_with_semaphore(profile: Dict):
            async with semaphore:
                return await scrape_one(profile)

        results = await asyncio.gather(
            *[scrape_with_semaphore(p) for p in profiles[:10]],
            return_exceptions=True
        )

        for result in results:
            if isinstance(result, list):
                found.extend(result)

        return found

    # ── Russian Service Checks ───────────────────────────────────────

    async def _check_russian_services(
        self,
        session: aiohttp.ClientSession,
        usernames: List[str]
    ) -> List[DiscoveredEmail]:
        """Check username-based emails on Russian services."""
        found = []

        async def check_yandex(username: str) -> Optional[DiscoveredEmail]:
            url = f"https://yandex.ru/collections/user/{username}/"
            try:
                async with session.get(url) as response:
                    if response.status == 200:
                        text = await response.text()
                        if 'collections-user' in text.lower() or 'subscriber' in text.lower():
                            return DiscoveredEmail(
                                email=f"{username}@yandex.ru",
                                source="Yandex Collections profile",
                                confidence="medium",
                                verified=True,
                                verified_on=['yandex_collections'],
                                verification='likely'
                            )
            except Exception as e:
                logger.debug(f"[EmailDiscovery] Yandex Collections check failed: {e}")
            return None

        for username in usernames:
            clean_user = self._clean_username(username)
            if len(clean_user) < 3:
                continue

            try:
                result = await asyncio.wait_for(
                    check_yandex(clean_user),
                    timeout=5.0
                )
                if result:
                    found.append(result)
            except asyncio.TimeoutError:
                pass

        return found

    # ── Synchronous Wrappers ─────────────────────────────────────────

    def discover_sync(
        self,
        first_name: str,
        last_name: str,
        usernames: List[str],
        profile_urls: List[Dict] = None
    ) -> EmailDiscoveryResults:
        """
        Synchronous wrapper for discover().
        Creates new event loop if needed.
        """
        try:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run,
                        self.discover(first_name, last_name, usernames, profile_urls)
                    )
                    return future.result(timeout=15)
            else:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    return loop.run_until_complete(
                        self.discover(first_name, last_name, usernames, profile_urls)
                    )
                finally:
                    loop.close()
        except RuntimeError as e:
            logger.warning(f"Email discovery sync event loop error: {e}")
            return asyncio.run(
                self.discover(first_name, last_name, usernames, profile_urls)
            )

    def close(self):
        """Clean up resources."""
        self._executor.shutdown(wait=False)


# ── Standalone Verification Functions ────────────────────────────────

def verify_emails_with_holehe(emails: List[str], max_emails: int = 5) -> List[Dict]:
    """
    Verify a list of emails with Holehe (synchronous).
    Returns list of dicts with email, services, verification status.

    Uses tiered priority: Russian mail domains first, then international.
    Runs up to 3 checks concurrently via ThreadPoolExecutor.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    service = EmailDiscoveryService()
    results = []

    # Tier emails: Russian mail providers first (most likely for Russian targets)
    tier1_domains = {'mail.ru', 'yandex.ru', 'bk.ru', 'gmail.com', 'list.ru', 'inbox.ru'}
    tier1 = [e for e in emails[:max_emails] if e.split('@')[-1] in tier1_domains]
    tier2 = [e for e in emails[:max_emails] if e not in tier1]
    ordered_emails = tier1 + tier2

    def check_single(email):
        try:
            holehe_result = service._holehe_check_single(email)
            if holehe_result and holehe_result.get('services'):
                services = holehe_result['services']
                logger.info(f"Holehe verified: {email} -> {services[:5]}")
                return {
                    'email': email,
                    'services': services,
                    'verified': True,
                    'confidence': 'high' if len(services) >= 2 else 'medium',
                    'verification': 'holehe_confirmed',
                    'verified_on': [f'holehe:{s}' for s in services[:5]],
                }
            else:
                return {
                    'email': email,
                    'services': [],
                    'verified': False,
                    'confidence': None,
                    'verification': 'holehe_not_found',
                    'verified_on': [],
                }
        except Exception as e:
            logger.debug(f"Holehe check error for {email}: {e}")
            return {
                'email': email,
                'services': [],
                'verified': False,
                'confidence': None,
                'verification': 'holehe_error',
                'verified_on': [],
            }

    # Run concurrently (8 at a time) with per-email timeout
    executor = ThreadPoolExecutor(max_workers=8)
    try:
        future_to_email = {
            executor.submit(check_single, email): email
            for email in ordered_emails
        }
        for future in as_completed(future_to_email, timeout=45):
            try:
                result = future.result(timeout=5)
                results.append(result)
            except Exception as e:
                email = future_to_email[future]
                logger.debug(f"Holehe future error for {email}: {e}")
                results.append({
                    'email': email,
                    'services': [],
                    'verified': False,
                    'confidence': None,
                    'verification': 'holehe_error',
                    'verified_on': [],
                })
    except (TimeoutError, Exception) as e:
        logger.debug(f"Holehe batch timeout: {e}")
    finally:
        executor.shutdown(wait=False, cancel_futures=True)

    service.close()
    return results


# ── Convenience Functions ────────────────────────────────────────────

def discover_emails(
    first_name: str,
    last_name: str,
    usernames: List[str],
    profile_urls: List[Dict] = None
) -> EmailDiscoveryResults:
    """Convenience function for email discovery."""
    service = EmailDiscoveryService()
    try:
        return service.discover_sync(first_name, last_name, usernames, profile_urls)
    finally:
        service.close()


def discover_emails_async(
    first_name: str,
    last_name: str,
    usernames: List[str],
    profile_urls: List[Dict] = None
) -> EmailDiscoveryResults:
    """Async convenience function for email discovery."""
    service = EmailDiscoveryService()
    return asyncio.run(
        service.discover(first_name, last_name, usernames, profile_urls)
    )
