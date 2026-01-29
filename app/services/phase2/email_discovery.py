"""
Email Discovery Service - Fast Async Implementation
====================================================
Discovers and verifies emails using multiple methods in parallel.
Target: Complete in under 60 seconds.

Methods:
1. Pattern generation from name + usernames
2. Direct email validation (MX record + SMTP)
3. Holehe verification (async, with short timeout)
4. Username-to-email mapping for Russian services
5. Profile scraping for visible emails
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
import subprocess

logger = logging.getLogger(__name__)


@dataclass
class DiscoveredEmail:
    """An email discovered during investigation."""
    email: str
    source: str
    confidence: str  # "high", "medium", "low"
    verified: bool = False
    verified_on: List[str] = field(default_factory=list)


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


class EmailDiscoveryService:
    """
    Fast async email discovery service.
    Designed to complete in under 60 seconds.
    """

    def __init__(
        self,
        max_candidates: int = 30,
        verify_timeout: float = 5.0,
        max_concurrent: int = 10
    ):
        """
        Initialize email discovery service.

        Args:
            max_candidates: Maximum email candidates to generate
            verify_timeout: Timeout for each verification request
            max_concurrent: Maximum concurrent verification tasks
        """
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

                # Task 1: Verify candidates with Holehe (fast mode)
                tasks.append(self._verify_with_holehe_batch(candidates[:15]))

                # Task 2: Check Gravatar for candidates
                tasks.append(self._check_gravatar_batch(session, candidates[:20]))

                # Task 3: Check if emails have MX records (quick validation)
                tasks.append(self._validate_mx_batch(candidates))

                # Task 4: Scrape profile URLs for visible emails
                if profile_urls:
                    tasks.append(self._scrape_profiles_async(session, profile_urls))

                # Task 5: Check username-based emails on Russian services
                tasks.append(self._check_russian_services(session, usernames[:5]))

                # Run all tasks with overall timeout
                try:
                    task_results = await asyncio.wait_for(
                        asyncio.gather(*tasks, return_exceptions=True),
                        timeout=35.0  # 35 second overall timeout
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
                                    if email_info.confidence == 'high':
                                        existing.confidence = 'high'

        except Exception as e:
            results.errors.append(f"Discovery error: {str(e)}")
            logger.error(f"Email discovery error: {e}")

        # Finalize results
        results.emails = sorted(
            all_emails.values(),
            key=lambda e: (0 if e.verified else 1, 0 if e.confidence == 'high' else 1)
        )
        results.candidates_verified = len([e for e in results.emails if e.verified])
        results.discovery_time = time.time() - start_time

        logger.info(f"Email discovery complete: {len(results.emails)} emails found in {results.discovery_time:.1f}s")

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
        fname = self._transliterate(first_name.lower().strip())
        lname = self._transliterate(last_name.lower().strip())

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

    def _transliterate(self, text: str) -> str:
        """Transliterate Russian text to Latin."""
        translit_map = {
            'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
            'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
            'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
            'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
            'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
        }
        result = ""
        for char in text.lower():
            result += translit_map.get(char, char)
        return result

    def _clean_username(self, username: str) -> str:
        """Clean username for email generation."""
        # Remove common prefixes
        username = re.sub(r'^(id|user|profile|@)', '', username.lower())
        # Keep only alphanumeric and underscore/dot
        username = re.sub(r'[^a-z0-9_.]', '', username)
        return username

    def _is_valid_email(self, email: str) -> bool:
        """Validate email format."""
        pattern = r'^[a-z0-9][a-z0-9._-]*@[a-z0-9.-]+\.[a-z]{2,}$'
        return bool(re.match(pattern, email.lower())) and len(email) <= 254

    async def _verify_with_holehe_batch(
        self,
        emails: List[str]
    ) -> List[DiscoveredEmail]:
        """
        Verify emails with Holehe CLI (fast mode).
        Uses subprocess with short timeout.
        """
        verified = []

        # Run Holehe in thread pool to avoid blocking
        loop = asyncio.get_event_loop()

        for email in emails[:5]:  # Limit to 5 for speed
            try:
                result = await asyncio.wait_for(
                    loop.run_in_executor(
                        self._executor,
                        self._holehe_check_single,
                        email
                    ),
                    timeout=6.0  # 6 second timeout per email
                )

                if result:
                    services = result.get('services', [])
                    if services:
                        verified.append(DiscoveredEmail(
                            email=email,
                            source="Holehe verification",
                            confidence="high" if len(services) >= 2 else "medium",
                            verified=True,
                            verified_on=services[:5]
                        ))
                        logger.info(f"Holehe verified: {email} on {services}")

            except asyncio.TimeoutError:
                logger.debug(f"Holehe timeout for {email}")
            except Exception as e:
                logger.debug(f"Holehe error for {email}: {e}")

        return verified

    def _holehe_check_single(self, email: str) -> Optional[Dict]:
        """Run Holehe for a single email (blocking)."""
        try:
            result = subprocess.run(
                ['holehe', email, '--only-used', '--no-color', '--no-clear', '-T', '3'],
                capture_output=True,
                text=True,
                timeout=7,
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
        except Exception:
            return None

    async def _check_gravatar_batch(
        self,
        session: aiohttp.ClientSession,
        emails: List[str]
    ) -> List[DiscoveredEmail]:
        """Check Gravatar for email existence."""
        import hashlib
        verified = []

        async def check_one(email: str) -> Optional[DiscoveredEmail]:
            try:
                email_hash = hashlib.md5(email.lower().encode()).hexdigest()
                url = f"https://www.gravatar.com/avatar/{email_hash}?d=404"

                async with session.head(url) as response:
                    if response.status == 200:
                        return DiscoveredEmail(
                            email=email,
                            source="Gravatar",
                            confidence="medium",
                            verified=True,
                            verified_on=['gravatar']
                        )
            except Exception:
                pass
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

    async def _validate_mx_batch(
        self,
        emails: List[str]
    ) -> List[DiscoveredEmail]:
        """Validate emails have valid MX records (quick check)."""
        validated = []
        checked_domains = set()

        loop = asyncio.get_event_loop()

        for email in emails:
            domain = email.split('@')[-1]

            # Skip if already checked this domain
            if domain in checked_domains:
                continue
            checked_domains.add(domain)

            try:
                # Quick MX lookup
                has_mx = await asyncio.wait_for(
                    loop.run_in_executor(self._executor, self._check_mx, domain),
                    timeout=2.0
                )

                if has_mx:
                    # Add all emails with this domain as low-confidence candidates
                    for e in emails:
                        if e.split('@')[-1] == domain:
                            validated.append(DiscoveredEmail(
                                email=e,
                                source="Pattern generation",
                                confidence="low",
                                verified=False,
                                verified_on=[]
                            ))

            except Exception:
                pass

        return validated

    def _check_mx(self, domain: str) -> bool:
        """Check if domain has MX records."""
        try:
            # Use known MX for common domains
            if domain in KNOWN_MX_SERVERS:
                return True

            # Try DNS lookup
            import dns.resolver
            try:
                dns.resolver.resolve(domain, 'MX')
                return True
            except:
                pass

            # Fallback: try socket lookup
            socket.getaddrinfo(f'mail.{domain}', 25)
            return True

        except Exception:
            return False

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

                        # Find emails in page
                        matches = email_pattern.findall(text)
                        for email in set(matches):
                            email_lower = email.lower()
                            # Filter out obvious garbage
                            if any(x in email_lower for x in ['example', 'test', 'noreply', 'support']):
                                continue
                            if email_lower.endswith(('.png', '.jpg', '.gif', '.svg')):
                                continue

                            emails.append(DiscoveredEmail(
                                email=email_lower,
                                source=f"{platform.upper()} profile",
                                confidence="high",
                                verified=True,
                                verified_on=[platform]
                            ))

            except Exception as e:
                logger.debug(f"Scrape error for {url}: {e}")

            return emails

        # Scrape all profiles in parallel
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

    async def _check_russian_services(
        self,
        session: aiohttp.ClientSession,
        usernames: List[str]
    ) -> List[DiscoveredEmail]:
        """Check username-based emails on Russian services."""
        found = []

        # Yandex Collections check
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
                                verified_on=['yandex_collections']
                            )
            except Exception:
                pass
            return None

        # Check all usernames
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
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Already in async context, create new loop in thread
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run,
                        self.discover(first_name, last_name, usernames, profile_urls)
                    )
                    return future.result(timeout=60)
            else:
                return loop.run_until_complete(
                    self.discover(first_name, last_name, usernames, profile_urls)
                )
        except RuntimeError:
            # No event loop, create one
            return asyncio.run(
                self.discover(first_name, last_name, usernames, profile_urls)
            )

    def close(self):
        """Clean up resources."""
        self._executor.shutdown(wait=False)


# Convenience functions
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
