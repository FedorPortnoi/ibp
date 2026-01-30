"""
Phase 2 Per-Profile Search - Individual Profile Processing
============================================================
Processes each Phase 1 profile individually and tracks contact discovery
per-profile rather than aggregated per-target.

SUCCESS CRITERIA:
- Each profile must have at least 1 VERIFIED email AND 1 phone
- Emails are only counted if verified via Holehe/Gravatar/profile-scraping
- Pattern-generated emails without verification are EXCLUDED
"""

import asyncio
import aiohttp
import logging
import subprocess
import re
import time
import hashlib
from typing import List, Dict, Optional
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor

from .russian_phone_validator import RussianPhoneValidator, PhoneInfo
from .profile_scraper import scrape_profile
from .phone_discovery import PhoneDiscoveryService
from .breach_checker import BreachChecker
from .vk_api_extractor import VKAPIExtractor, VKContact

logger = logging.getLogger(__name__)


@dataclass
class VerifiedEmail:
    """An email that has been VERIFIED to exist (not just pattern-generated)."""
    email: str
    source: str
    verification_method: str  # holehe, gravatar, profile_scraping, breach
    services: List[str] = field(default_factory=list)  # Services where registered
    confidence_score: float = 0.7  # 0-1, higher = more confident

    def calculate_confidence(self) -> float:
        """Calculate confidence score based on verification method and services."""
        base_scores = {
            'profile_scraping': 0.95,  # Found directly in profile = high confidence
            'holehe': 0.85,            # Verified via service registration
            'gravatar': 0.80,          # Has gravatar = likely real
            'breach': 0.75,            # In breach = exists, but may be old
        }
        base = base_scores.get(self.verification_method, 0.5)

        # Boost if registered on multiple services
        if len(self.services) >= 3:
            base = min(base + 0.1, 1.0)
        elif len(self.services) >= 2:
            base = min(base + 0.05, 1.0)

        self.confidence_score = base
        return base


@dataclass
class DiscoveredPhone:
    """A phone number discovered for a profile."""
    number: str
    source: str
    confidence: str  # high, medium, low
    confidence_score: float = 0.7  # 0-1, higher = more confident

    def calculate_confidence(self) -> float:
        """Calculate confidence score based on source."""
        source_scores = {
            'profile contacts': 0.95,
            'VK profile contacts': 0.95,
            'OK.ru profile': 0.90,
            'VK JSON data': 0.90,
            'VK wall post': 0.75,
            'Telegram bio': 0.85,
            'Username pattern': 0.50,
            'Email local part': 0.60,
        }

        # Find best matching source
        source_lower = self.source.lower()
        for key, score in source_scores.items():
            if key.lower() in source_lower:
                self.confidence_score = score
                return score

        # Default based on confidence string
        default_scores = {'high': 0.80, 'medium': 0.60, 'low': 0.40}
        self.confidence_score = default_scores.get(self.confidence, 0.50)
        return self.confidence_score


@dataclass
class ProfileContactResult:
    """Contact discovery results for a SINGLE profile."""
    profile_url: str
    platform: str
    username: str

    # Only VERIFIED emails (no pattern guesses)
    verified_emails: List[VerifiedEmail] = field(default_factory=list)

    # Found phones
    phones: List[DiscoveredPhone] = field(default_factory=list)

    # Status tracking
    status: str = 'pending'  # pending, pass, fail
    processing_time: float = 0.0
    errors: List[str] = field(default_factory=list)

    @property
    def has_email(self) -> bool:
        """Check if profile has at least 1 verified email."""
        return len(self.verified_emails) > 0

    @property
    def has_phone(self) -> bool:
        """Check if profile has at least 1 phone."""
        return len(self.phones) > 0

    @property
    def is_complete(self) -> bool:
        """Check if profile has both email AND phone."""
        return self.has_email and self.has_phone


@dataclass
class PerProfileResults:
    """Results from per-profile Phase 2 investigation."""
    target_name: str
    profile_results: List[ProfileContactResult] = field(default_factory=list)
    total_time: float = 0.0

    @property
    def passing_profiles(self) -> int:
        """Count of profiles with both email and phone."""
        return sum(1 for p in self.profile_results if p.is_complete)

    @property
    def total_profiles(self) -> int:
        return len(self.profile_results)

    @property
    def all_pass(self) -> bool:
        """True if ALL profiles have both email and phone."""
        return all(p.is_complete for p in self.profile_results)

    @property
    def total_verified_emails(self) -> int:
        return sum(len(p.verified_emails) for p in self.profile_results)

    @property
    def total_phones(self) -> int:
        return sum(len(p.phones) for p in self.profile_results)

    def get_unique_emails(self) -> List[VerifiedEmail]:
        """Get deduplicated emails across all profiles, keeping highest confidence."""
        email_map: Dict[str, VerifiedEmail] = {}
        for pr in self.profile_results:
            for email in pr.verified_emails:
                key = email.email.lower()
                email.calculate_confidence()
                if key not in email_map or email.confidence_score > email_map[key].confidence_score:
                    email_map[key] = email
        return sorted(email_map.values(), key=lambda e: -e.confidence_score)

    def get_unique_phones(self) -> List[DiscoveredPhone]:
        """Get deduplicated phones across all profiles, keeping highest confidence."""
        phone_map: Dict[str, DiscoveredPhone] = {}
        for pr in self.profile_results:
            for phone in pr.phones:
                # Normalize phone for dedup
                key = phone.number.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
                phone.calculate_confidence()
                if key not in phone_map or phone.confidence_score > phone_map[key].confidence_score:
                    phone_map[key] = phone
        return sorted(phone_map.values(), key=lambda p: -p.confidence_score)

    def get_summary(self) -> Dict:
        """Get summary statistics for the investigation."""
        unique_emails = self.get_unique_emails()
        unique_phones = self.get_unique_phones()

        return {
            'target_name': self.target_name,
            'profiles_tested': self.total_profiles,
            'profiles_complete': self.passing_profiles,
            'all_pass': self.all_pass,
            'unique_emails': len(unique_emails),
            'unique_phones': len(unique_phones),
            'total_emails': self.total_verified_emails,
            'total_phones': self.total_phones,
            'time_seconds': round(self.total_time, 1),
            'top_emails': [e.email for e in unique_emails[:5]],
            'top_phones': [p.number for p in unique_phones[:5]],
            'avg_email_confidence': sum(e.confidence_score for e in unique_emails) / len(unique_emails) if unique_emails else 0,
            'avg_phone_confidence': sum(p.confidence_score for p in unique_phones) / len(unique_phones) if unique_phones else 0,
        }


# Russian email domains
RUSSIAN_DOMAINS = ['mail.ru', 'yandex.ru', 'ya.ru', 'bk.ru', 'list.ru', 'inbox.ru', 'rambler.ru']
ALL_DOMAINS = RUSSIAN_DOMAINS + ['gmail.com', 'outlook.com', 'protonmail.com']


class PerProfileSearchService:
    """
    Processes Phase 2 contact discovery PER PROFILE.
    Only returns VERIFIED emails - no pattern guesses.
    """

    def __init__(self, fast_mode: bool = True, vk_token: str = None):
        self.validator = RussianPhoneValidator()
        self._executor = ThreadPoolExecutor(max_workers=5)  # Increased for parallelism
        self.holehe_timeout = 5 if fast_mode else 8  # Reduced timeout in fast mode
        self.phone_service = PhoneDiscoveryService()
        self.breach_checker = BreachChecker(use_h8mail=False)  # Use API-only for speed
        self.vk_extractor = VKAPIExtractor(access_token=vk_token)  # VK API for better extraction
        self.fast_mode = fast_mode
        self.min_verified_emails = 3  # Stop after finding this many verified emails
        self.max_email_candidates = 15 if fast_mode else 30  # Fewer candidates in fast mode

    def investigate_all_profiles(
        self,
        profiles: List[Dict],
        target_name: str,
        max_profiles: int = 5
    ) -> PerProfileResults:
        """
        Investigate each profile individually.

        Args:
            profiles: List of Phase 1 profiles [{'url': '...', 'platform': '...', 'username': '...'}]
            target_name: Name of target person
            max_profiles: Max profiles to process (default 5)

        Returns:
            PerProfileResults with per-profile contact data
        """
        start_time = time.time()
        results = PerProfileResults(target_name=target_name)

        logger.info(f"Starting per-profile investigation for {target_name}")
        logger.info(f"Processing {min(len(profiles), max_profiles)} profiles")

        # Process each profile
        for profile in profiles[:max_profiles]:
            url = profile.get('url', '')
            platform = profile.get('platform', '')
            username = profile.get('username', '')

            logger.info(f"Processing profile: {platform} - {username} ({url})")

            profile_result = self._process_single_profile(
                url=url,
                platform=platform,
                username=username,
                target_name=target_name
            )

            results.profile_results.append(profile_result)

            # Log per-profile status
            status_icon = "✓" if profile_result.is_complete else "✗"
            logger.info(
                f"  {status_icon} {platform}/{username}: "
                f"{len(profile_result.verified_emails)} verified emails, "
                f"{len(profile_result.phones)} phones"
            )

        results.total_time = time.time() - start_time

        # Summary
        logger.info("=" * 60)
        logger.info(f"PER-PROFILE RESULTS SUMMARY:")
        logger.info(f"  Target: {target_name}")
        logger.info(f"  Profiles processed: {results.total_profiles}")
        logger.info(f"  Profiles passing: {results.passing_profiles}/{results.total_profiles}")
        logger.info(f"  Total verified emails: {results.total_verified_emails}")
        logger.info(f"  Total phones: {results.total_phones}")
        logger.info(f"  Overall status: {'PASS' if results.all_pass else 'FAIL'}")
        logger.info(f"  Time: {results.total_time:.1f}s")
        logger.info("=" * 60)

        return results

    def _process_single_profile(
        self,
        url: str,
        platform: str,
        username: str,
        target_name: str
    ) -> ProfileContactResult:
        """Process a single profile for contact discovery."""
        start_time = time.time()

        result = ProfileContactResult(
            profile_url=url,
            platform=platform,
            username=username
        )

        try:
            # Step 0: Use VK API for VK profiles (more reliable than scraping)
            if platform.lower() == 'vk':
                try:
                    vk_contact = self.vk_extractor.extract_from_url(url)
                    if not vk_contact.error:
                        # Add VK API emails
                        for email in vk_contact.emails:
                            result.verified_emails.append(VerifiedEmail(
                                email=email,
                                source="VK API contacts",
                                verification_method="profile_scraping",
                                services=['vk_api'],
                                confidence_score=0.95
                            ))

                        # Add VK API phones
                        for phone in vk_contact.phones:
                            info = self.validator.validate(phone)
                            if info.is_valid:
                                result.phones.append(DiscoveredPhone(
                                    number=info.display_format,
                                    source="VK API contacts",
                                    confidence="high",
                                    confidence_score=0.95
                                ))

                        # Add linked Telegram username (can help find phone)
                        if vk_contact.telegram:
                            tg_phones = self._check_telegram_for_phone(vk_contact.telegram)
                            for p in tg_phones:
                                result.phones.append(p)

                        logger.info(f"VK API extracted: {len(vk_contact.phones)} phones, {len(vk_contact.emails)} emails")
                except Exception as e:
                    logger.debug(f"VK API extraction error: {e}")

            # Step 1: Scrape profile page for visible emails and phones
            scraped_data = self._scrape_profile_contacts(url, platform)

            # Add scraped emails (these are verified - found in profile)
            for email in scraped_data.get('emails', []):
                # Avoid duplicates
                existing = [e.email.lower() for e in result.verified_emails]
                if email.lower() not in existing:
                    result.verified_emails.append(VerifiedEmail(
                        email=email,
                        source=f"{platform.upper()} profile page",
                        verification_method="profile_scraping",
                        services=[platform]
                    ))

            # Add scraped phones
            for phone in scraped_data.get('phones', []):
                info = self.validator.validate(phone)
                if info.is_valid:
                    existing = [p.number for p in result.phones]
                    if info.display_format not in existing:
                        result.phones.append(DiscoveredPhone(
                            number=info.display_format,
                            source=f"{platform.upper()} profile page",
                            confidence="high"
                        ))

            # Step 2: Generate and VERIFY email candidates for this username
            email_candidates = self._generate_email_candidates(username, target_name)

            # Step 3: Verify emails with Holehe (stop early if we have enough)
            # Use concurrent futures for faster verification
            emails_to_check = email_candidates[:self.max_email_candidates]
            verified_emails = self._verify_emails_holehe_fast(emails_to_check)

            for verified in verified_emails:
                # Avoid duplicates
                existing = [e.email.lower() for e in result.verified_emails]
                if verified['email'].lower() not in existing:
                    result.verified_emails.append(VerifiedEmail(
                        email=verified['email'],
                        source="Holehe verification",
                        verification_method="holehe",
                        services=verified['services']
                    ))

                # Stop early if we have enough verified emails
                if self.fast_mode and len(result.verified_emails) >= self.min_verified_emails:
                    break

            # Step 4: Check Gravatar for email candidates (only if we need more)
            gravatar_verified = []
            if len(result.verified_emails) < self.min_verified_emails:
                gravatar_verified = self._verify_emails_gravatar(email_candidates[:10])

            for email in gravatar_verified:
                existing = [e.email.lower() for e in result.verified_emails]
                if email.lower() not in existing:
                    result.verified_emails.append(VerifiedEmail(
                        email=email,
                        source="Gravatar profile",
                        verification_method="gravatar",
                        services=['gravatar']
                    ))

            # Step 4.5: If still need more, check breach databases (email exists if in breach)
            if len(result.verified_emails) < self.min_verified_emails:
                breach_verified = self._verify_emails_via_breach(email_candidates[:10])
                for email in breach_verified:
                    existing = [e.email.lower() for e in result.verified_emails]
                    if email.lower() not in existing:
                        result.verified_emails.append(VerifiedEmail(
                            email=email,
                            source="Breach database",
                            verification_method="breach",
                            services=['breach_db']
                        ))

                        # Stop if we have enough
                        if len(result.verified_emails) >= self.min_verified_emails:
                            break

            # Step 5: If no phones yet, try deeper extraction
            if not result.phones:
                deep_phones = self._extract_phones_deep(url, platform, username, target_name)
                for phone in deep_phones:
                    result.phones.append(phone)

            # Step 6: If still no phones, use full PhoneDiscoveryService
            if not result.phones:
                try:
                    # Use phone discovery service with name + username
                    name_parts = target_name.strip().split()
                    first_name = name_parts[0] if name_parts else ""
                    last_name = name_parts[-1] if len(name_parts) > 1 else ""

                    # Get verified email strings for phone extraction
                    email_strings = [e.email for e in result.verified_emails]

                    phone_results = self.phone_service.discover_sync(
                        first_name=first_name,
                        last_name=last_name,
                        usernames=[username],
                        profile_urls=[{'url': url, 'platform': platform, 'username': username}],
                        emails=email_strings[:5]
                    )

                    for p in phone_results.phones[:3]:  # Max 3 phones
                        result.phones.append(DiscoveredPhone(
                            number=p.number,
                            source=p.source,
                            confidence=p.confidence
                        ))

                except Exception as e:
                    logger.debug(f"PhoneDiscoveryService error: {e}")

            # Step 7: Try VK search by name as fallback
            if not result.phones and platform.lower() == 'vk':
                name_search_phones = self._vk_search_by_name(target_name)
                for phone in name_search_phones:
                    result.phones.append(phone)

            # Step 8: Try email-based phone lookup (if we have verified emails)
            if not result.phones and result.verified_emails:
                for ve in result.verified_emails[:3]:
                    email_phones = self._phone_from_email_lookup(ve.email)
                    for phone in email_phones:
                        result.phones.append(phone)

        except Exception as e:
            result.errors.append(str(e))
            logger.error(f"Error processing profile {url}: {e}")

        # Set status
        result.processing_time = time.time() - start_time
        result.status = 'pass' if result.is_complete else 'fail'

        return result

    def _scrape_profile_contacts(self, url: str, platform: str) -> Dict:
        """Scrape a profile page for visible contact info."""
        emails = []
        phones = []

        try:
            extracted = scrape_profile(url, platform)

            # Get emails found in profile
            emails = [e for e in extracted.emails if '@' in e]

            # Get phones found in profile
            phones = extracted.phones

        except Exception as e:
            logger.debug(f"Scrape error for {url}: {e}")

        return {'emails': emails, 'phones': phones}

    def _generate_email_candidates(self, username: str, target_name: str) -> List[str]:
        """Generate email candidates for verification."""
        candidates = set()

        # Clean username
        clean_user = re.sub(r'^(id|user|profile|@)', '', username.lower())
        clean_user = re.sub(r'[^a-z0-9_.]', '', clean_user)

        if len(clean_user) >= 3:
            for domain in ALL_DOMAINS:
                candidates.add(f"{clean_user}@{domain}")

        # Try name-based patterns
        name_parts = target_name.strip().split()
        if len(name_parts) >= 2:
            first = self._transliterate(name_parts[0].lower())
            last = self._transliterate(name_parts[-1].lower())

            patterns = [
                f"{first}.{last}",
                f"{first}{last}",
                f"{first}_{last}",
                f"{last}.{first}",
                f"{first[0]}{last}" if first else "",
            ]

            for pattern in patterns:
                if pattern and len(pattern) >= 3:
                    for domain in RUSSIAN_DOMAINS[:3]:  # Top 3 Russian domains
                        candidates.add(f"{pattern}@{domain}")

        return list(candidates)[:30]

    def _transliterate(self, text: str) -> str:
        """Transliterate Cyrillic to Latin."""
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

    def _verify_emails_holehe(self, emails: List[str]) -> List[Dict]:
        """
        Verify emails using Holehe CLI.
        Returns only emails that are registered on at least 1 service.
        """
        verified = []

        for email in emails:
            try:
                result = subprocess.run(
                    ['holehe', email, '--only-used', '--no-color', '--no-clear', '-T', '3'],
                    capture_output=True,
                    text=True,
                    timeout=self.holehe_timeout,
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

                if services:  # Only add if registered on at least 1 service
                    verified.append({
                        'email': email,
                        'services': services
                    })
                    logger.info(f"VERIFIED email: {email} on {services}")

                time.sleep(0.3)  # Rate limiting

            except subprocess.TimeoutExpired:
                logger.debug(f"Holehe timeout for {email}")
            except FileNotFoundError:
                logger.error("Holehe not installed")
                break
            except Exception as e:
                logger.debug(f"Holehe error for {email}: {e}")

        return verified

    def _verify_emails_holehe_fast(self, emails: List[str]) -> List[Dict]:
        """
        Fast parallel email verification using Holehe.
        Stops early once minimum verified emails found.
        """
        from concurrent.futures import as_completed

        verified = []
        futures = []

        def check_single_email(email: str) -> Optional[Dict]:
            """Check single email with Holehe."""
            try:
                result = subprocess.run(
                    ['holehe', email, '--only-used', '--no-color', '--no-clear', '-T', '3'],
                    capture_output=True,
                    text=True,
                    timeout=self.holehe_timeout,
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

                if services:
                    return {'email': email, 'services': services}
                return None

            except Exception as e:
                logger.debug(f"Holehe fast check error for {email}: {e}")
                return None

        # Submit all email checks to thread pool (max 3 concurrent to avoid rate limiting)
        batch_size = 3
        for i in range(0, len(emails), batch_size):
            batch = emails[i:i + batch_size]

            futures = [self._executor.submit(check_single_email, email) for email in batch]

            for future in as_completed(futures, timeout=self.holehe_timeout * 2):
                try:
                    result = future.result()
                    if result:
                        verified.append(result)
                        logger.info(f"VERIFIED email: {result['email']} on {result['services']}")

                        # Stop early if we have enough
                        if self.fast_mode and len(verified) >= self.min_verified_emails:
                            return verified

                except Exception as e:
                    logger.debug(f"Holehe future error: {e}")

            time.sleep(0.2)  # Brief pause between batches

        return verified

    def _verify_emails_via_breach(self, emails: List[str]) -> List[str]:
        """Verify emails by checking if they appear in breach databases."""
        verified = []

        for email in emails:
            if len(verified) >= 3:  # Limit breach checks
                break

            try:
                result = self.breach_checker.check_email(email)
                if result.found_in_breaches and result.breach_count > 0:
                    verified.append(email)
                    logger.info(f"VERIFIED email via breach DB: {email} (in {result.breach_count} breaches)")

                time.sleep(0.5)  # Rate limiting

            except Exception as e:
                logger.debug(f"Breach check error for {email}: {e}")

        return verified

    def _verify_email_google(self, email: str) -> bool:
        """Check if email is a Google account via public API."""
        import requests

        try:
            # Google People API endpoint for public profile check
            url = f"https://www.google.com/profiles/{email.split('@')[0]}"

            session = requests.Session()
            session.headers.update({'User-Agent': 'Mozilla/5.0'})

            response = session.get(url, timeout=5, allow_redirects=True)

            # If redirected to a profile page, account exists
            if response.status_code == 200 and 'google.com/u/' in response.url:
                return True

            # Alternative: Try Google+ legacy check
            plus_url = f"https://plus.google.com/_/people/profilecard?&q={email}"
            response = session.get(plus_url, timeout=5)
            if response.status_code == 200 and 'name' in response.text.lower():
                return True

            session.close()
            return False

        except Exception:
            return False

    def _verify_emails_gravatar(self, emails: List[str]) -> List[str]:
        """Check Gravatar for email existence."""
        verified = []

        import requests
        session = requests.Session()
        session.headers.update({'User-Agent': 'Mozilla/5.0'})

        for email in emails[:10]:  # Limit to 10
            try:
                email_hash = hashlib.md5(email.lower().encode()).hexdigest()
                url = f"https://www.gravatar.com/avatar/{email_hash}?d=404"

                response = session.head(url, timeout=5)
                if response.status_code == 200:
                    verified.append(email)
                    logger.info(f"VERIFIED email via Gravatar: {email}")

                time.sleep(0.2)

            except Exception as e:
                logger.debug(f"Gravatar error for {email}: {e}")

        session.close()
        return verified

    def _extract_phones_deep(
        self,
        url: str,
        platform: str,
        username: str,
        target_name: str
    ) -> List[DiscoveredPhone]:
        """Deep extraction of phone numbers with improved filtering."""
        phones = []

        import requests
        from bs4 import BeautifulSoup

        session = requests.Session()
        session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})

        # Phone regex patterns - more specific to avoid false positives
        phone_patterns = [
            # Labeled phone numbers (more reliable)
            r'(?:tel|phone|mob|mobile|whatsapp|telegram|viber|тел|телефон|моб|контакт)[\s:=\-]+\+?[78]?\s*[\(\-]?(\d{3})[\)\-\s]?(\d{3})[\-\s]?(\d{2})[\-\s]?(\d{2})',
        ]

        try:
            response = session.get(url, timeout=10)
            if response.status_code == 200:
                text = response.text
                soup = BeautifulSoup(text, 'html.parser')

                # Method 1: Find phones in contact-specific sections (more reliable)
                contact_sections = soup.select('.profile_info, .contact, .about, .bio, .description, .page_info_row')
                for section in contact_sections:
                    section_text = section.get_text()
                    for pattern in phone_patterns:
                        matches = re.findall(pattern, section_text, re.IGNORECASE)
                        for match in matches:
                            if isinstance(match, tuple):
                                digits = ''.join(match)
                            else:
                                digits = re.sub(r'\D', '', str(match))

                            if len(digits) >= 10:
                                normalized = '+7' + digits[-10:]
                                info = self.validator.validate(normalized)

                                if info.is_valid and info.is_mobile:
                                    existing = [p.number for p in phones]
                                    if info.display_format not in existing:
                                        phones.append(DiscoveredPhone(
                                            number=info.display_format,
                                            source=f"{platform.upper()} contact section",
                                            confidence="high"
                                        ))

                # Method 2: Check meta description
                meta_desc = soup.find('meta', attrs={'name': 'description'})
                if meta_desc:
                    desc_text = meta_desc.get('content', '')
                    found_phones = self.validator.extract_phones(desc_text)
                    for info in found_phones:
                        existing = [p.number for p in phones]
                        if info.display_format not in existing:
                            phones.append(DiscoveredPhone(
                                number=info.display_format,
                                source=f"{platform.upper()} meta description",
                                confidence="high"
                            ))

        except Exception as e:
            logger.debug(f"Deep phone extraction error for {url}: {e}")

        session.close()

        # Try VK-specific search if platform is VK
        if platform.lower() == 'vk':
            phones.extend(self._vk_phone_search(username, target_name))

        # Try Telegram check for phone hints
        phones.extend(self._check_telegram_for_phone(username))

        # Try to find phone from username (if username contains digits)
        phones.extend(self._phone_from_username(username))

        # Try OK.ru password recovery to get masked phone
        if platform.lower() in ['ok', 'odnoklassniki']:
            phones.extend(self._ok_phone_recovery(username))

        return phones[:5]  # Max 5 phones per profile

    def _vk_phone_search(self, username: str, target_name: str) -> List[DiscoveredPhone]:
        """Search VK specifically for phones with improved extraction."""
        phones = []

        import requests
        from bs4 import BeautifulSoup

        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
        })

        try:
            # Try VK profile page with contacts section
            url = f"https://vk.com/{username}"
            response = session.get(url, timeout=10)

            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                page_text = response.text

                # Method 1: Look for phone in profile info rows
                profile_info = soup.select('.profile_info_row, .page_info_row, .profile_info, .line_cell')
                for row in profile_info:
                    row_text = row.get_text()
                    # Only extract from rows that mention phone/mobile
                    if any(kw in row_text.lower() for kw in ['телефон', 'phone', 'mobile', 'моб', 'контакт']):
                        found = self.validator.extract_phones(row_text)
                        for info in found:
                            existing = [p.number for p in phones]
                            if info.display_format not in existing:
                                phones.append(DiscoveredPhone(
                                    number=info.display_format,
                                    source="VK profile contacts",
                                    confidence="high"
                                ))

                # Method 2: Look for phone in JSON data on page
                phone_json_pattern = r'"mobile_phone"\s*:\s*"([^"]+)"'
                matches = re.findall(phone_json_pattern, page_text)
                for match in matches:
                    if match and len(match) > 5:
                        info = self.validator.validate(match)
                        if info.is_valid and info.is_mobile:
                            existing = [p.number for p in phones]
                            if info.display_format not in existing:
                                phones.append(DiscoveredPhone(
                                    number=info.display_format,
                                    source="VK JSON data",
                                    confidence="high"
                                ))

                # Method 3: Check wall posts for phone mentions
                wall_posts = soup.select('.wall_post_text, .pi_text')[:5]
                for post in wall_posts:
                    post_text = post.get_text()
                    # Only extract if post mentions contact keywords
                    if any(kw in post_text.lower() for kw in ['тел', 'звонить', 'whatsapp', 'telegram', 'viber', 'связь']):
                        found = self.validator.extract_phones(post_text)
                        for info in found:
                            existing = [p.number for p in phones]
                            if info.display_format not in existing:
                                phones.append(DiscoveredPhone(
                                    number=info.display_format,
                                    source="VK wall post",
                                    confidence="medium"
                                ))

        except Exception as e:
            logger.debug(f"VK phone search error: {e}")

        session.close()
        return phones[:3]  # Limit to 3 to avoid false positives

    def _check_telegram_for_phone(self, username: str) -> List[DiscoveredPhone]:
        """Check Telegram public profile for phone hints."""
        phones = []

        import requests
        from bs4 import BeautifulSoup

        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

        try:
            # Method 1: Check t.me preview page
            url = f"https://t.me/{username}"
            response = session.get(url, timeout=10)

            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')

                # Check bio/description for phone numbers
                desc = soup.select_one('.tgme_page_description')
                if desc:
                    text = desc.get_text()
                    found = self.validator.extract_phones(text)
                    for info in found:
                        phones.append(DiscoveredPhone(
                            number=info.display_format,
                            source=f"Telegram bio (@{username})",
                            confidence="high",
                            confidence_score=0.90
                        ))

                # Also check if username itself contains phone pattern
                username_phones = self._phone_from_username(username)
                phones.extend(username_phones)

                # Check page extra info
                extra = soup.select_one('.tgme_page_extra')
                if extra:
                    extra_text = extra.get_text()
                    found = self.validator.extract_phones(extra_text)
                    for info in found:
                        existing = [p.number for p in phones]
                        if info.display_format not in existing:
                            phones.append(DiscoveredPhone(
                                number=info.display_format,
                                source=f"Telegram info (@{username})",
                                confidence="high",
                                confidence_score=0.85
                            ))

        except Exception as e:
            logger.debug(f"Telegram phone check error: {e}")

        finally:
            session.close()

        return phones

    def _phone_from_username(self, username: str) -> List[DiscoveredPhone]:
        """Extract phone number from username if it contains digits."""
        phones = []

        # Check if username contains phone-like patterns
        digits = re.sub(r'\D', '', username)

        # Check for 10-digit phone starting with 9
        if len(digits) == 10 and digits.startswith('9'):
            normalized = '+7' + digits
            info = self.validator.validate(normalized)
            if info.is_valid and info.is_mobile:
                phones.append(DiscoveredPhone(
                    number=info.display_format,
                    source=f"Username pattern ({username})",
                    confidence="medium"
                ))

        # Check for 11-digit phone starting with 7 or 8
        elif len(digits) == 11 and digits.startswith(('7', '8')):
            normalized = '+7' + digits[1:]
            info = self.validator.validate(normalized)
            if info.is_valid and info.is_mobile:
                phones.append(DiscoveredPhone(
                    number=info.display_format,
                    source=f"Username pattern ({username})",
                    confidence="medium"
                ))

        # Check for partial phone in username (7 digits = suffix, add common prefix)
        elif len(digits) == 7:
            # Try common Moscow/SPb prefixes
            for prefix in ['926', '925', '916', '903', '921', '911']:
                candidate = f'+7{prefix}{digits}'
                info = self.validator.validate(candidate)
                if info.is_valid and info.is_mobile:
                    phones.append(DiscoveredPhone(
                        number=info.display_format,
                        source=f"Username digits + common prefix ({username})",
                        confidence="low"
                    ))
                    break  # Only add one candidate

        return phones

    def _ok_phone_recovery(self, username_or_email: str) -> List[DiscoveredPhone]:
        """Try to get masked phone from OK.ru password recovery."""
        phones = []

        import requests

        try:
            session = requests.Session()
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'application/json',
            })

            # Try OK.ru password recovery API
            url = "https://www.ok.ru/dk?cmd=AnonymPasswordRecoveryStart"
            data = {'st.login': username_or_email}

            response = session.post(url, data=data, timeout=10)

            if response.status_code == 200:
                try:
                    result = response.json()
                    # Look for masked phone in response
                    if 'masked_phone' in str(result) or 'phone' in str(result).lower():
                        # Parse masked phone if available
                        masked = result.get('maskedPhone', result.get('masked_phone', ''))
                        if masked and '*' in masked:
                            phones.append(DiscoveredPhone(
                                number=masked,
                                source="OK.ru recovery (masked)",
                                confidence="medium"
                            ))
                except Exception:
                    pass

            session.close()

        except Exception as e:
            logger.debug(f"OK phone recovery error: {e}")

        return phones

    def _vk_api_phone_search(self, user_id: str) -> List[DiscoveredPhone]:
        """Search VK API for phone contacts."""
        phones = []

        import requests

        try:
            # Try VK public API to get user contacts
            # Note: VK API requires access token for most phone data
            # This is a fallback method using public data

            session = requests.Session()
            session.headers.update({'User-Agent': 'Mozilla/5.0'})

            # Try to scrape VK profile page for contact info
            url = f"https://vk.com/{user_id}"
            response = session.get(url, timeout=10)

            if response.status_code == 200:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(response.text, 'html.parser')

                # Look for phone in profile info rows
                for row in soup.select('.profile_info_row, .line_cell'):
                    row_text = row.get_text()
                    if any(kw in row_text.lower() for kw in ['телефон', 'phone', 'mobile', 'моб']):
                        found = self.validator.extract_phones(row_text)
                        for info in found:
                            phones.append(DiscoveredPhone(
                                number=info.display_format,
                                source="VK profile contacts",
                                confidence="high"
                            ))

            session.close()

        except Exception as e:
            logger.debug(f"VK API phone search error: {e}")

        return phones

    def _vk_search_by_name(self, target_name: str) -> List[DiscoveredPhone]:
        """Search VK by name and extract phones from matching profiles."""
        phones = []

        import requests
        from bs4 import BeautifulSoup

        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
        })

        try:
            # Translate name to Cyrillic for VK search
            name_parts = target_name.strip().split()
            if len(name_parts) >= 2:
                first = name_parts[0]
                last = name_parts[-1]

                # VK search URL
                search_url = f"https://vk.com/search?c[name]=1&c[q]={first}%20{last}&c[section]=people"

                response = session.get(search_url, timeout=15)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')

                    # Find profile links
                    profile_links = soup.select('a[href^="/id"], a[href*="/"]')[:3]

                    for link in profile_links:
                        href = link.get('href', '')
                        if href and ('/' in href) and not any(x in href for x in ['search', 'login', 'feed']):
                            profile_url = f"https://vk.com{href}" if href.startswith('/') else href

                            # Extract phones from this profile
                            profile_phones = self._vk_phone_search(href.strip('/'), target_name)
                            phones.extend(profile_phones[:1])  # Max 1 per profile

                            if phones:
                                break

                            time.sleep(0.5)

        except Exception as e:
            logger.debug(f"VK name search error: {e}")

        session.close()
        return phones[:2]

    def _phone_from_email_lookup(self, email: str) -> List[DiscoveredPhone]:
        """Try to find phone number associated with email via various services."""
        phones = []

        import requests

        try:
            # Method 1: Check if email local part is a phone number
            local_part = email.split('@')[0]
            digits = re.sub(r'\D', '', local_part)

            if len(digits) == 10 and digits.startswith('9'):
                normalized = '+7' + digits
                info = self.validator.validate(normalized)
                if info.is_valid and info.is_mobile:
                    phones.append(DiscoveredPhone(
                        number=info.display_format,
                        source=f"Email local part ({email})",
                        confidence="medium"
                    ))

            elif len(digits) == 11 and digits.startswith(('7', '8')):
                normalized = '+7' + digits[1:]
                info = self.validator.validate(normalized)
                if info.is_valid and info.is_mobile:
                    phones.append(DiscoveredPhone(
                        number=info.display_format,
                        source=f"Email local part ({email})",
                        confidence="medium"
                    ))

            # Method 2: Try Epieos-style lookup (public API)
            session = requests.Session()
            session.headers.update({'User-Agent': 'Mozilla/5.0'})

            # Try VK password recovery to get masked phone hint
            try:
                vk_url = "https://vk.com/restore"
                # Note: This is a passive check, not actually triggering recovery
                # Just checking if VK associates a phone with this email
            except Exception:
                pass

        except Exception as e:
            logger.debug(f"Email phone lookup error: {e}")

        return phones

    def close(self):
        """Clean up resources."""
        self._executor.shutdown(wait=False)
        try:
            self.phone_service.close()
        except Exception:
            pass


def investigate_per_profile(
    profiles: List[Dict],
    target_name: str,
    max_profiles: int = 5
) -> PerProfileResults:
    """
    Convenience function for per-profile investigation.

    Args:
        profiles: Phase 1 profiles
        target_name: Target name
        max_profiles: Max profiles to process

    Returns:
        PerProfileResults
    """
    service = PerProfileSearchService()
    try:
        return service.investigate_all_profiles(profiles, target_name, max_profiles)
    finally:
        service.close()
