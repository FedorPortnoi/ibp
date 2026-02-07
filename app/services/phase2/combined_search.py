"""
Phase 2 Combined Search Orchestrator - FIXED
=============================================
Coordinates all Phase 2 services to discover contact information.
Now includes URL validation, exclusion tracking, and filtering.
"""

import logging
from typing import List, Dict, Optional, Callable
from dataclasses import dataclass, field
import time
import os

# Import Phase 2 services
from .email_generator import generate_email_candidates, generate_from_username
from .profile_scraper import scrape_profile, ExtractedContacts
from .gravatar_lookup import check_gravatar, GravatarProfile
from .holehe_service import check_email_sync, HoleheResults
from .search4faces_service import search_all_databases, FaceMatch
from .yaseeker_service import check_yandex_username, YandexAccount, YaSeekerService, get_verified_yandex_accounts
from .url_validator import (
    is_valid_profile_url,
    is_reserved_username,
    validate_and_clean_profiles,
    detect_platform_from_url,
    RESERVED_USERNAMES
)

# NEW: Enhanced services from Phase 2 research
from .russian_phone_validator import RussianPhoneValidator, PhoneInfo
from .mailcat_discovery import MailcatEmailDiscovery, EmailDiscoveryResult
from .vk_api_extractor import VKAPIExtractor, VKContact

# NEW: Deep dive research services (Part 2)
from .ok_checker import OKChecker, OKAccountInfo
from .username_intelligence import UsernameIntelligence, UsernameAnalysis
from .breach_checker import BreachChecker, BreachCheckResult
from .vk_wall_extractor import VKWallExtractor, WallExtractionResult

# NEW: Fast async email discovery
from .email_discovery import EmailDiscoveryService, EmailDiscoveryResults

# NEW: API-based face search (discovers NEW profiles from photo)
from .face_search_api import ApiFaceSearchService, FaceMatch as ApiFaceMatch

# NEW: Phone discovery service
from .phone_discovery import PhoneDiscoveryService, PhoneDiscoveryResults

# NEW: Snoop username enumeration (5,372+ sites, 2,600+ Russian)
try:
    from ..snoop_search import SnoopSearchService
    SNOOP_AVAILABLE = True
except ImportError:
    SNOOP_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class DiscoveredPhone:
    """A phone number discovered during investigation."""
    number: str
    source: str  # e.g., "VK profile bio", "OK profile"
    confidence: str  # "high", "medium", "low"
    verified_on: List[str] = field(default_factory=list)  # e.g., ["telegram"]


@dataclass
class DiscoveredEmail:
    """An email address discovered during investigation."""
    email: str
    source: str
    confidence: str
    verified_on: List[str] = field(default_factory=list)  # Services where registered


@dataclass
class AdditionalProfile:
    """An additional social profile discovered during investigation."""
    platform: str
    url: str
    username: str
    source: str  # How we found it


@dataclass
class Phase2Results:
    """Complete results from Phase 2 investigation."""
    phones: List[DiscoveredPhone] = field(default_factory=list)
    emails: List[DiscoveredEmail] = field(default_factory=list)
    additional_profiles: List[AdditionalProfile] = field(default_factory=list)
    face_matches: List[FaceMatch] = field(default_factory=list)
    stats: Dict = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)


class Phase2CombinedSearch:
    """
    Orchestrates all Phase 2 discovery services.
    """

    def __init__(self, vk_service_token: Optional[str] = None):
        self.logger = logging.getLogger(__name__)
        self.progress_callback: Optional[Callable] = None

        # ===== NEW: Exclusion tracking for Phase 1 profiles =====
        self.excluded_urls: set = set()
        self.excluded_usernames: dict = {}  # {platform: set(usernames)}

        # ===== NEW: Initialize enhanced services =====
        self.phone_validator = RussianPhoneValidator()
        self.mailcat_discovery = MailcatEmailDiscovery()
        self.vk_extractor = VKAPIExtractor(access_token=vk_service_token)

        # ===== NEW: Deep dive services (Part 2) =====
        self.ok_checker = OKChecker()
        self.username_intel = UsernameIntelligence()
        self.breach_checker = BreachChecker()
        self.vk_wall_extractor = VKWallExtractor(access_token=vk_service_token)

        # ===== NEW: Fast async email discovery =====
        self.email_discovery = EmailDiscoveryService(
            max_candidates=30,
            verify_timeout=5.0,
            max_concurrent=10
        )

        # ===== NEW: API-based face search (discovers NEW profiles) =====
        self.api_face_search = ApiFaceSearchService()

        # ===== NEW: Snoop username search (5,372+ sites, 2,600+ Russian) =====
        self.snoop_service = None
        if SNOOP_AVAILABLE:
            try:
                self.snoop_service = SnoopSearchService()
                if self.snoop_service.available:
                    self.logger.info("Snoop service initialized (5,372+ sites)")
                else:
                    self.snoop_service = None
                    self.logger.info("Snoop not available (dependencies missing)")
            except Exception as e:
                self.logger.debug(f"Snoop initialization failed: {e}")

    def set_progress_callback(self, callback: Callable[[str, int], None]):
        """
        Set callback function for progress updates.

        Args:
            callback: Function that accepts (step_name: str, percent: int)
        """
        self.progress_callback = callback

    def _update_progress(self, step: str, percent: int):
        """Update progress if callback is set."""
        if self.progress_callback:
            try:
                self.progress_callback(step, percent)
            except Exception as e:
                self.logger.warning(f"Progress callback error: {e}")

    def _build_exclusion_set(self, selected_profiles: List[Dict]):
        """Build set of Phase 1 profiles to exclude from results."""
        self.excluded_urls = set()
        self.excluded_usernames = {}

        for profile in selected_profiles:
            # Add URL
            url = profile.get('url', '').lower().rstrip('/')
            if url:
                self.excluded_urls.add(url)

            # Add platform + username combo
            platform = profile.get('platform', '').lower()
            username = profile.get('username', '').lower()

            if platform and username:
                if platform not in self.excluded_usernames:
                    self.excluded_usernames[platform] = set()
                self.excluded_usernames[platform].add(username)

        self.logger.info(f"Built exclusion set: {len(self.excluded_urls)} URLs, "
                        f"{sum(len(v) for v in self.excluded_usernames.values())} usernames")

    def _is_excluded(self, url: str, platform: str, username: str) -> bool:
        """Check if a profile should be excluded (already in Phase 1 or invalid)."""
        # Check URL
        url_normalized = url.lower().rstrip('/') if url else ''
        if url_normalized in self.excluded_urls:
            return True

        # Check platform + username
        if platform and username:
            platform_lower = platform.lower()
            username_lower = username.lower()

            if platform_lower in self.excluded_usernames:
                if username_lower in self.excluded_usernames[platform_lower]:
                    return True

        # Check reserved usernames
        if username and is_reserved_username(username):
            return True

        # Check URL validity
        if url and not is_valid_profile_url(url, platform):
            return True

        return False

    def _add_profile_if_valid(self, profile: Dict, additional_profiles: List) -> bool:
        """Add profile to results only if valid and not excluded."""
        url = profile.get('url', '')
        platform = profile.get('platform', '')
        username = profile.get('username', '')

        if self._is_excluded(url, platform, username):
            self.logger.debug(f"Excluded profile: {url}")
            return False

        # Check for duplicates in current results
        url_normalized = url.lower().rstrip('/')
        for existing in additional_profiles:
            existing_url = existing.get('url', '') if isinstance(existing, dict) else existing.url
            if existing_url.lower().rstrip('/') == url_normalized:
                return False

        # Add to results
        additional_profiles.append(profile)

        # Add to exclusion set to prevent future duplicates
        self.excluded_urls.add(url_normalized)
        if platform and username:
            if platform.lower() not in self.excluded_usernames:
                self.excluded_usernames[platform.lower()] = set()
            self.excluded_usernames[platform.lower()].add(username.lower())

        return True

    def investigate(
        self,
        selected_profiles: List[Dict],
        target_name: str,
        target_photo_path: Optional[str] = None
    ) -> Phase2Results:
        """
        Run full Phase 2 investigation - FIXED VERSION.

        Args:
            selected_profiles: List of profiles from Phase 1
                [{"platform": "vk", "username": "pasha", "url": "https://vk.com/pasha"}, ...]
            target_name: Full name of target (e.g., "Pavel Durov")
            target_photo_path: Optional path to target's photo

        Returns:
            Phase2Results with all discovered information
        """
        start_time = time.time()

        # ===== DIAGNOSTIC LOGGING =====
        self.logger.info("=" * 60)
        self.logger.info(f"PHASE 2 START: Target={target_name}")
        self.logger.info(f"Selected profiles: {len(selected_profiles)}")
        for p in selected_profiles:
            self.logger.info(f"  - {p.get('platform')}: {p.get('username')} -> {p.get('url')}")
        self.logger.info(f"Photo path: {target_photo_path}")
        self.logger.info("=" * 60)

        phones: List[DiscoveredPhone] = []
        emails: List[DiscoveredEmail] = []
        additional_profiles: List[Dict] = []  # Use dicts first, convert later
        face_matches: List[FaceMatch] = []
        errors: List[str] = []

        # ===== BUILD EXCLUSION SET FROM PHASE 1 =====
        self._build_exclusion_set(selected_profiles)

        # Parse name
        name_parts = target_name.strip().split()
        first_name = name_parts[0] if name_parts else ""
        last_name = name_parts[-1] if len(name_parts) > 1 else ""
        self.logger.info(f"Parsed name: first='{first_name}', last='{last_name}'")

        # Get usernames from selected profiles - WITH VALIDATION
        username_hints = []
        for p in selected_profiles:
            u = p.get('username', '')
            if u and not is_reserved_username(u):
                username_hints.append(u)
        username_hints = list(set(username_hints))
        self.logger.info(f"Username hints: {username_hints}")

        # ===== STEP 1: Scrape Selected Profiles =====
        self._update_progress("Scraping selected profiles...", 5)
        self.logger.info(f"Step 1: Scraping {len(selected_profiles)} profiles")

        for i, profile in enumerate(selected_profiles):
            try:
                url = profile.get('url', '')
                platform = profile.get('platform', '').lower()

                if not url:
                    continue

                self._update_progress(f"Scraping {platform.upper()} profile...", 5 + (i * 3))

                # Use VK API extractor for VK profiles (more reliable)
                if platform == 'vk':
                    try:
                        vk_contact = self.vk_extractor.extract_from_url(url)
                        if not vk_contact.error:
                            # Add VK-extracted phones
                            for phone in vk_contact.phones:
                                phone_info = self.phone_validator.validate(phone)
                                if phone_info.is_valid:
                                    phones.append(DiscoveredPhone(
                                        number=phone_info.display_format,
                                        source="VK API contacts",
                                        confidence="high"
                                    ))

                            # Add VK-extracted emails
                            for email in vk_contact.emails:
                                emails.append(DiscoveredEmail(
                                    email=email,
                                    source="VK API contacts",
                                    confidence="high",
                                    verified_on=[]
                                ))

                            # Add linked accounts as additional profiles
                            if vk_contact.telegram:
                                self._add_profile_if_valid({
                                    'platform': 'telegram',
                                    'url': f'https://t.me/{vk_contact.telegram}',
                                    'username': vk_contact.telegram,
                                    'source': 'VK profile connections'
                                }, additional_profiles)

                            if vk_contact.instagram:
                                self._add_profile_if_valid({
                                    'platform': 'instagram',
                                    'url': f'https://instagram.com/{vk_contact.instagram}',
                                    'username': vk_contact.instagram,
                                    'source': 'VK profile connections'
                                }, additional_profiles)

                            self.logger.info(f"VK API extracted: {len(vk_contact.phones)} phones, {len(vk_contact.emails)} emails")
                    except Exception as e:
                        self.logger.debug(f"VK API extraction failed, falling back to scraping: {e}")

                # Always also scrape the profile (captures bio text)
                extracted = scrape_profile(url, platform)

                # Add found phones (with validation)
                for phone in extracted.phones:
                    if phone and len(phone) >= 10:
                        phone_info = self.phone_validator.validate(phone)
                        if phone_info.is_valid:
                            phones.append(DiscoveredPhone(
                                number=phone_info.display_format,
                                source=f"{platform.upper()} profile bio",
                                confidence="high"
                            ))
                        else:
                            # Add even if not a valid Russian format
                            phones.append(DiscoveredPhone(
                                number=phone,
                                source=f"{platform.upper()} profile bio",
                                confidence="medium"
                            ))

                # Add found emails
                for email in extracted.emails:
                    if email and '@' in email:
                        emails.append(DiscoveredEmail(
                            email=email,
                            source=f"{platform.upper()} profile bio",
                            confidence="high",
                            verified_on=[]
                        ))

                # Add other social profiles - WITH VALIDATION
                for social in extracted.other_socials:
                    social_url = social.get('url', '')
                    social_platform = social.get('platform', '')
                    social_username = social.get('username', '')

                    self._add_profile_if_valid({
                        'platform': social_platform,
                        'url': social_url,
                        'username': social_username,
                        'source': f'Found in {platform.upper()} bio'
                    }, additional_profiles)

                time.sleep(0.5)  # Rate limiting

            except Exception as e:
                error_msg = f"Error scraping {profile.get('url', 'unknown')}: {str(e)}"
                errors.append(error_msg)
                self.logger.warning(error_msg)

        # DIAGNOSTIC: Step 1 complete
        self.logger.info(f"STEP 1 COMPLETE: Scraped {len(selected_profiles)} profiles")
        self.logger.info(f"  Phones so far: {len(phones)} - {[p.number for p in phones]}")
        self.logger.info(f"  Emails so far: {len(emails)} - {[e.email for e in emails]}")
        self.logger.info(f"  Additional profiles so far: {len(additional_profiles)}")
        self.logger.info(f"  Errors: {len(errors)}")

        # ===== STEP 2: Facial Recognition (if photo provided) =====
        if target_photo_path and os.path.exists(target_photo_path):
            self._update_progress("Running facial recognition...", 20)
            self.logger.info("Step 2: Running Search4faces facial recognition")

            try:
                face_results = search_all_databases(
                    image_path=target_photo_path,
                    max_results_per_db=25
                )

                # Validate and filter face matches
                for match in face_results:
                    match_url = match.profile_url if hasattr(match, 'profile_url') else match.get('profile_url', '')
                    match_platform = match.platform if hasattr(match, 'platform') else match.get('platform', '')

                    if match_url and is_valid_profile_url(match_url, match_platform):
                        # Check it's not excluded
                        if not self._is_excluded(match_url, match_platform, ''):
                            face_matches.append(match)

                            # Also add as additional profile
                            self._add_profile_if_valid({
                                'platform': match_platform,
                                'url': match_url,
                                'username': match.username if hasattr(match, 'username') else '',
                                'source': f"Face match ({match.similarity_score:.1f}%)" if hasattr(match, 'similarity_score') and match.similarity_score else "Face match"
                            }, additional_profiles)

                self.logger.info(f"Found {len(face_matches)} valid face matches")

            except Exception as e:
                error_msg = f"Face search error: {str(e)}"
                errors.append(error_msg)
                self.logger.warning(error_msg)
        else:
            self._update_progress("Skipping facial recognition (no photo)", 20)

        # ===== STEP 3: Generate Email Candidates =====
        self._update_progress("Generating email candidates...", 35)
        self.logger.info("Step 3: Generating email candidates")

        email_candidates = generate_email_candidates(
            first_name=first_name,
            last_name=last_name,
            username_hints=username_hints
        )

        # Also generate from usernames
        for username in username_hints[:5]:
            email_candidates.extend(generate_from_username(username))

        # Remove duplicates
        email_candidates = list(set(email_candidates))[:50]  # Cap at 50

        self.logger.info(f"Generated {len(email_candidates)} email candidates")
        self.logger.info(f"  First 10 candidates: {email_candidates[:10]}")

        # ===== STEP 3.5: Enhanced Email Discovery with Mailcat =====
        self._update_progress("Discovering emails via Mailcat...", 40)
        self.logger.info("Step 3.5: Mailcat email discovery")

        verified_emails_from_mailcat = []
        try:
            # Try to verify emails for top usernames using Mailcat
            for username in username_hints[:5]:
                result = self.mailcat_discovery.discover_emails(username, verify=True)
                if result.verified_emails:
                    verified_emails_from_mailcat.extend(result.verified_emails)
                    for email in result.verified_emails:
                        emails.append(DiscoveredEmail(
                            email=email,
                            source="Mailcat verification",
                            confidence="high",
                            verified_on=["mailcat"]
                        ))
                    self.logger.info(f"Mailcat found {len(result.verified_emails)} verified emails for {username}")
        except Exception as e:
            error_msg = f"Mailcat error: {str(e)}"
            errors.append(error_msg)
            self.logger.debug(error_msg)

        # ===== STEP 3.6: Username Intelligence =====
        self._update_progress("Analyzing username patterns...", 42)
        self.logger.info("Step 3.6: Username intelligence analysis")

        try:
            # Analyze usernames for pattern-based email candidates
            correlation = self.username_intel.correlate_usernames(username_hints)

            # Add pattern-derived emails to candidates
            pattern_emails = correlation.get('suggested_emails', [])
            for email in pattern_emails[:20]:
                if email not in email_candidates:
                    email_candidates.append(email)

            self.logger.info(f"Username intelligence added {len(pattern_emails)} email candidates")

        except Exception as e:
            error_msg = f"Username intelligence error: {str(e)}"
            errors.append(error_msg)
            self.logger.debug(error_msg)

        # ===== STEP 3.7: OK (Odnoklassniki) Checker =====
        self._update_progress("Checking OK.ru accounts...", 43)
        self.logger.info("Step 3.7: OK.ru account check")

        ok_checked = 0
        try:
            # Check discovered phones/emails against OK.ru
            ok_queries = []

            # Add phones we've found
            for phone in phones[:5]:
                ok_queries.append(phone.number)

            # Add top email candidates
            for email in email_candidates[:5]:
                ok_queries.append(email)

            for query in ok_queries[:10]:  # Limit to 10 checks
                ok_result = self.ok_checker.check_account(query)
                ok_checked += 1

                if ok_result.exists:
                    self.logger.info(f"OK.ru account found for: {query}")

                    # Add masked data as hints
                    if ok_result.masked_phone and ok_result.masked_phone not in [p.number for p in phones]:
                        phones.append(DiscoveredPhone(
                            number=ok_result.masked_phone,
                            source="OK.ru recovery (masked)",
                            confidence="medium"
                        ))

                    if ok_result.masked_email and ok_result.masked_email not in [e.email for e in emails]:
                        emails.append(DiscoveredEmail(
                            email=ok_result.masked_email,
                            source="OK.ru recovery (masked)",
                            confidence="medium",
                            verified_on=["ok.ru"]
                        ))

                    if ok_result.profile_url:
                        self._add_profile_if_valid({
                            'platform': 'ok',
                            'url': ok_result.profile_url,
                            'username': query,
                            'source': 'OK.ru account check'
                        }, additional_profiles)

                time.sleep(0.3)  # Rate limiting

        except Exception as e:
            error_msg = f"OK checker error: {str(e)}"
            errors.append(error_msg)
            self.logger.debug(error_msg)

        # ===== STEP 3.8: VK Wall Post Extraction =====
        self._update_progress("Extracting contacts from VK wall posts...", 44)
        self.logger.info("Step 3.8: VK wall post contact extraction")

        try:
            # Extract contacts from VK profiles we've found
            vk_profiles = [
                p for p in selected_profiles
                if p.get('platform', '').lower() == 'vk'
            ]

            for vk_profile in vk_profiles[:3]:  # Limit to 3 VK profiles
                vk_url = vk_profile.get('url', '')
                if not vk_url:
                    continue

                wall_result = self.vk_wall_extractor.extract_from_profile(vk_url, max_posts=30)

                # Add discovered phones
                for phone_contact in wall_result.phones:
                    phone_info = self.phone_validator.validate(phone_contact.value)
                    if phone_info.is_valid:
                        phones.append(DiscoveredPhone(
                            number=phone_info.display_format,
                            source=f"VK wall post ({phone_contact.source})",
                            confidence=phone_contact.confidence
                        ))

                # Add discovered emails
                for email_contact in wall_result.emails:
                    emails.append(DiscoveredEmail(
                        email=email_contact.value,
                        source=f"VK wall post ({email_contact.source})",
                        confidence=email_contact.confidence,
                        verified_on=[]
                    ))

                # Add Telegram usernames as profiles
                for tg_username in wall_result.telegram_usernames:
                    self._add_profile_if_valid({
                        'platform': 'telegram',
                        'url': f'https://t.me/{tg_username}',
                        'username': tg_username,
                        'source': 'Found in VK wall post'
                    }, additional_profiles)

                self.logger.info(
                    f"VK wall extraction: {len(wall_result.phones)} phones, "
                    f"{len(wall_result.emails)} emails from {wall_result.posts_analyzed} posts"
                )

        except Exception as e:
            error_msg = f"VK wall extraction error: {str(e)}"
            errors.append(error_msg)
            self.logger.debug(error_msg)

        # ===== STEP 4: YaSeeker - VERIFIED Accounts Only =====
        self._update_progress("Checking Yandex services (verified)...", 45)
        self.logger.info("Step 4: Checking Yandex accounts")

        yaseeker = YaSeekerService()
        yandex_checked = 0

        for username in username_hints[:5]:
            try:
                self._update_progress(f"Checking Yandex: {username}...", 50)

                yandex_accounts = yaseeker.check_all_services(username)
                yandex_checked += 1

                for acc in yandex_accounts:
                    # Add as additional profile - only if verified
                    self._add_profile_if_valid({
                        'platform': acc.platform,
                        'platform_display': acc.platform_display,
                        'url': acc.url,
                        'username': acc.username,
                        'source': acc.source
                    }, additional_profiles)

                    # Also add email if found
                    if hasattr(acc, 'email') and acc.email:
                        emails.append(DiscoveredEmail(
                            email=acc.email,
                            source="YaSeeker (Yandex)",
                            confidence="medium",
                            verified_on=acc.services_used if hasattr(acc, 'services_used') else []
                        ))

            except Exception as e:
                error_msg = f"YaSeeker error for {username}: {str(e)}"
                errors.append(error_msg)
                self.logger.debug(error_msg)

        # ===== STEP 4.5: Snoop Username Search (5,372+ sites, 2,600+ Russian) =====
        if self.snoop_service and username_hints:
            self._update_progress("Searching profiles via Snoop (5,372 sites)...", 52)
            self.logger.info("Step 4.5: Snoop username enumeration (5,372+ sites)")

            snoop_found = 0
            try:
                # Search top 3 usernames with Snoop
                for username in username_hints[:3]:
                    self._update_progress(f"Snoop: searching {username}...", 52)

                    # Full search (not Russian-only) for comprehensive results
                    snoop_results = self.snoop_service.search_username(
                        username,
                        timeout=180,  # 3 minutes per username
                        russian_only=False
                    )

                    # Filter to found profiles
                    found_profiles = self.snoop_service.get_found_profiles(snoop_results)

                    # Sort with Russian platforms first
                    found_profiles = self.snoop_service.sort_results(found_profiles, russian_first=True)

                    for result in found_profiles:
                        added = self._add_profile_if_valid({
                            'platform': result.get('platform', 'unknown'),
                            'url': result.get('url', ''),
                            'username': username,
                            'source': f"Snoop ({result.get('country', 'unknown')})"
                        }, additional_profiles)
                        if added:
                            snoop_found += 1

                self.logger.info(f"Snoop found {snoop_found} additional profiles across {len(username_hints[:3])} usernames")

            except Exception as e:
                error_msg = f"Snoop error: {str(e)}"
                errors.append(error_msg)
                self.logger.debug(error_msg)

        # ===== STEP 5: Verify Top Email Candidates with Holehe =====
        self._update_progress("Verifying emails with Holehe...", 55)
        self.logger.info("Step 5: Verifying emails with Holehe")

        # Only check top 5 most likely email candidates (reduced from 15 for speed)
        top_candidates = email_candidates[:5]
        holehe_verified = 0

        for i, email in enumerate(top_candidates):
            try:
                self._update_progress(f"Checking email {i+1}/{len(top_candidates)}...", 55 + (i * 5))
                start_time_holehe = time.time()

                holehe_result = check_email_sync(email)
                elapsed_holehe = time.time() - start_time_holehe
                self.logger.info(f"Holehe check for {email}: {holehe_result.total_registered} services found in {elapsed_holehe:.1f}s")

                if holehe_result.total_registered > 0:
                    services = [r.service for r in holehe_result.registered_services]
                    emails.append(DiscoveredEmail(
                        email=email,
                        source="Holehe verification",
                        confidence="high" if len(services) >= 3 else "medium",
                        verified_on=services[:10]
                    ))
                    holehe_verified += 1
                    self.logger.info(f"VERIFIED email: {email} on {len(services)} services")

                time.sleep(0.5)  # Reduced rate limiting

            except Exception as e:
                error_msg = f"Holehe error for {email}: {str(e)}"
                errors.append(error_msg)
                self.logger.debug(error_msg)

        self.logger.info(f"Holehe verified {holehe_verified} emails")
        self.logger.info(f"CHECKPOINT after Step 5: phones={len(phones)}, emails={len(emails)}, profiles={len(additional_profiles)}")

        # ===== STEP 5.5: Check Verified Emails for Breaches =====
        self._update_progress("Checking emails against breach databases...", 80)
        self.logger.info("Step 5.5: Checking emails for breaches")

        breach_checked = 0
        try:
            # Deduplicate and get verified emails (high confidence)
            verified_emails_for_breach = [
                e.email for e in emails
                if e.confidence == 'high' and '@' in e.email
            ][:10]  # Limit to 10 due to rate limiting

            for email in verified_emails_for_breach:
                try:
                    breach_result = self.breach_checker.check_email(email)
                    breach_checked += 1

                    if breach_result.found_in_breaches:
                        self.logger.info(
                            f"Email {email} found in {breach_result.breach_count} breaches: "
                            f"{[b.name for b in breach_result.breaches[:5]]}"
                        )

                        # Update the discovered email with breach info
                        for discovered_email in emails:
                            if discovered_email.email.lower() == email.lower():
                                discovered_email.verified_on.append(
                                    f"breached ({breach_result.breach_count} times)"
                                )
                                break

                except Exception as e:
                    self.logger.debug(f"Breach check error for {email}: {e}")

        except Exception as e:
            error_msg = f"Breach checker error: {str(e)}"
            errors.append(error_msg)
            self.logger.debug(error_msg)

        self.logger.info(f"Checked {breach_checked} emails for breaches")

        # ===== STEP 5.7: Phone Discovery =====
        self._update_progress("Discovering phone numbers...", 82)
        self.logger.info("Step 5.7: Phone number discovery")

        try:
            phone_service = PhoneDiscoveryService(max_candidates=50, verify_timeout=10.0)
            email_strings = [e.email for e in emails if '@' in e.email]
            profile_url_dicts = [
                {'url': p.get('url', ''), 'platform': p.get('platform', '')}
                for p in selected_profiles
            ]

            phone_results = phone_service.discover_sync(
                first_name=first_name,
                last_name=last_name,
                usernames=username_hints,
                profile_urls=profile_url_dicts,
                emails=email_strings
            )

            for dp in phone_results.phones:
                # Deduplicate against existing phones
                if not any(p.number == dp.number for p in phones):
                    phones.append(DiscoveredPhone(
                        number=dp.number,
                        source=dp.source,
                        confidence=dp.confidence,
                    ))

            self.logger.info(
                f"Phone discovery: found {len(phone_results.phones)} phones "
                f"({phone_results.candidates_generated} candidates, "
                f"{phone_results.candidates_verified} verified) in {phone_results.discovery_time:.1f}s"
            )
            phone_service.close()

        except Exception as e:
            error_msg = f"Phone discovery error: {str(e)}"
            errors.append(error_msg)
            self.logger.warning(error_msg)

        self.logger.info(f"CHECKPOINT after Step 5.7: phones={len(phones)}")

        # ===== STEP 5.8: VK API Phone Extraction =====
        # If we have a confirmed VK profile, try VK API fields for phone
        if self.vk_extractor and self.vk_extractor.access_token:
            self._update_progress("Extracting VK contacts via API...", 83)
            self.logger.info("Step 5.8: VK API phone extraction")

            for profile in selected_profiles:
                if profile.get('platform', '').lower() == 'vk':
                    vk_id = profile.get('platform_id') or profile.get('username', '')
                    if vk_id:
                        try:
                            # Try users.get with contacts fields
                            import requests as _requests
                            resp = _requests.post(
                                'https://api.vk.com/method/users.get',
                                data={
                                    'user_ids': vk_id,
                                    'fields': 'contacts,mobile_phone,home_phone,connections',
                                    'access_token': self.vk_extractor.access_token,
                                    'v': '5.199',
                                },
                                timeout=10,
                            )
                            data = resp.json()
                            users = data.get('response', [])
                            for user in users:
                                mobile = user.get('mobile_phone', '').strip()
                                home = user.get('home_phone', '').strip()
                                for phone_val, label in [(mobile, 'VK mobile_phone'), (home, 'VK home_phone')]:
                                    if phone_val and len(phone_val) >= 7:
                                        phone_info = self.phone_validator.validate(phone_val)
                                        if phone_info.is_valid:
                                            number = phone_info.display_format
                                            if not any(p.number == number for p in phones):
                                                phones.append(DiscoveredPhone(
                                                    number=number,
                                                    source=label,
                                                    confidence='high',
                                                ))
                                                self.logger.info(f"VK API phone: {number} from {label}")
                        except Exception as e:
                            self.logger.debug(f"VK API phone extraction error: {e}")

        # ===== STEP 6: Check Gravatar for Found Emails =====
        self._update_progress("Checking Gravatar profiles...", 85)
        self.logger.info("Step 6: Checking Gravatar profiles")

        # Deduplicate emails first
        unique_emails_dict = {e.email.lower(): e for e in emails}
        unique_emails = list(unique_emails_dict.values())

        for i, discovered_email in enumerate(unique_emails[:5]):  # Top 5 emails only
            try:
                gravatar = check_gravatar(discovered_email.email)

                if gravatar.exists:
                    discovered_email.verified_on.append('gravatar')

                    # Add any linked accounts from Gravatar
                    if gravatar.accounts:
                        for account in gravatar.accounts:
                            if account.get('url'):
                                grav_url = account['url']
                                if is_valid_profile_url(grav_url):
                                    platform = detect_platform_from_url(grav_url) or account.get('domain', 'unknown')
                                    self._add_profile_if_valid({
                                        'platform': platform,
                                        'url': grav_url,
                                        'username': account.get('username', ''),
                                        'source': f"Gravatar for {discovered_email.email}"
                                    }, additional_profiles)

                time.sleep(0.3)  # Rate limiting

            except Exception as e:
                error_msg = f"Gravatar error for {discovered_email.email}: {str(e)}"
                errors.append(error_msg)
                self.logger.debug(error_msg)

        # ===== STEP 7: Deduplicate Results =====
        self._update_progress("Finalizing results...", 95)
        self.logger.info("Step 7: Deduplicating results")

        phones = deduplicate_phones(phones)
        emails = deduplicate_emails(emails)

        # Convert additional_profiles dicts to AdditionalProfile objects
        final_profiles = []
        for p in additional_profiles:
            if isinstance(p, dict):
                final_profiles.append(AdditionalProfile(
                    platform=p.get('platform', ''),
                    url=p.get('url', ''),
                    username=p.get('username', ''),
                    source=p.get('source', 'Unknown')
                ))
            else:
                final_profiles.append(p)

        final_profiles = deduplicate_profiles(final_profiles)

        # ===== Calculate Stats =====
        elapsed_time = time.time() - start_time
        stats = {
            'profiles_analyzed': len(selected_profiles),
            'phones_found': len(phones),
            'emails_found': len(emails),
            'email_candidates_checked': len(top_candidates),
            'new_profiles_found': len(final_profiles),
            'face_matches': len(face_matches),
            'yandex_accounts_checked': yandex_checked,
            'ok_accounts_checked': ok_checked,
            'emails_breach_checked': breach_checked,
            'search_time': f"{elapsed_time:.1f}s",
            'errors_count': len(errors)
        }

        self._update_progress("Complete!", 100)

        # ===== FINAL DIAGNOSTIC LOGGING =====
        self.logger.info("=" * 60)
        self.logger.info("PHASE 2 FINAL RESULTS:")
        self.logger.info(f"  Phones: {len(phones)}")
        for p in phones[:10]:
            self.logger.info(f"    - {p.number} ({p.source}, {p.confidence})")
        self.logger.info(f"  Emails: {len(emails)}")
        for e in emails[:10]:
            self.logger.info(f"    - {e.email} ({e.source}, {e.confidence})")
        self.logger.info(f"  Additional profiles: {len(final_profiles)}")
        for ap in final_profiles[:10]:
            self.logger.info(f"    - {ap.platform}: {ap.url} ({ap.source})")
        self.logger.info(f"  Face matches: {len(face_matches)}")
        self.logger.info(f"  Errors: {len(errors)}")
        if errors:
            for err in errors[:5]:
                self.logger.info(f"    - {err}")
        self.logger.info(f"  Time: {elapsed_time:.1f}s")
        self.logger.info("=" * 60)

        return Phase2Results(
            phones=phones,
            emails=emails,
            additional_profiles=final_profiles,
            face_matches=face_matches,
            stats=stats,
            errors=errors
        )

    def investigate_fast(
        self,
        selected_profiles: List[Dict],
        target_name: str,
        target_photo_path: Optional[str] = None
    ) -> Phase2Results:
        """
        FAST Phase 2 investigation using async email discovery.
        Target: Complete in under 60 seconds.

        Args:
            selected_profiles: List of profiles from Phase 1
            target_name: Full name of target
            target_photo_path: Optional path to target's photo

        Returns:
            Phase2Results with discovered information
        """
        start_time = time.time()

        self.logger.info("=" * 60)
        self.logger.info(f"PHASE 2 FAST MODE: Target={target_name}")
        self.logger.info(f"Selected profiles: {len(selected_profiles)}")
        self.logger.info("=" * 60)

        phones: List[DiscoveredPhone] = []
        emails: List[DiscoveredEmail] = []
        additional_profiles: List[Dict] = []
        face_matches: List[FaceMatch] = []
        errors: List[str] = []

        # Build exclusion set
        self._build_exclusion_set(selected_profiles)

        # Parse name
        name_parts = target_name.strip().split()
        first_name = name_parts[0] if name_parts else ""
        last_name = name_parts[-1] if len(name_parts) > 1 else ""

        # Get usernames - WITH VALIDATION
        username_hints = []
        for p in selected_profiles:
            u = p.get('username', '')
            if u and not is_reserved_username(u):
                username_hints.append(u)
        username_hints = list(set(username_hints))

        self.logger.info(f"Parsed: first='{first_name}', last='{last_name}', usernames={username_hints}")

        # ===== STEP 1: Quick Profile Scraping (limited) =====
        self._update_progress("Quick profile scan...", 5)

        for profile in selected_profiles[:3]:  # Only first 3 profiles
            try:
                url = profile.get('url', '')
                platform = profile.get('platform', '').lower()

                if not url:
                    continue

                # Quick scrape with short timeout
                extracted = scrape_profile(url, platform)

                # Add phones
                for phone in extracted.phones[:3]:
                    if phone:
                        phone_info = self.phone_validator.validate(phone)
                        phones.append(DiscoveredPhone(
                            number=phone_info.display_format if phone_info.is_valid else phone,
                            source=f"{platform.upper()} profile",
                            confidence="high" if phone_info.is_valid else "medium"
                        ))

                # Add emails
                for email in extracted.emails[:3]:
                    if email and '@' in email:
                        emails.append(DiscoveredEmail(
                            email=email,
                            source=f"{platform.upper()} profile",
                            confidence="high",
                            verified_on=[platform]
                        ))

                # Add social links
                for social in extracted.other_socials[:5]:
                    self._add_profile_if_valid(social, additional_profiles)

            except Exception as e:
                errors.append(f"Scrape error: {str(e)}")

        self.logger.info(f"Quick scrape: {len(phones)} phones, {len(emails)} emails, {len(additional_profiles)} profiles")

        # ===== STEP 1.5: API-Based Face Search (if photo provided) =====
        if target_photo_path and os.path.exists(target_photo_path):
            self._update_progress("Searching faces via API (VK, OK databases)...", 15)
            self.logger.info("Step 1.5: API-based face search")

            try:
                import asyncio

                # Run async face search
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    api_face_matches = loop.run_until_complete(
                        self.api_face_search.search_and_merge(
                            target_photo_path,
                            services=['search4faces', 'yandex'],
                            databases=['vk', 'ok']
                        )
                    )
                finally:
                    loop.close()

                # Add discovered profiles
                for match in api_face_matches:
                    self._add_profile_if_valid({
                        'platform': match.platform,
                        'url': match.profile_url,
                        'username': match.profile_username or '',
                        'source': f"Face match ({match.source_service}, {match.similarity_score:.0%})"
                    }, additional_profiles)

                    # Convert to FaceMatch for results
                    face_matches.append(match)

                self.logger.info(f"API face search: Found {len(api_face_matches)} profiles")

            except Exception as e:
                errors.append(f"API face search error: {str(e)}")
                self.logger.error(f"API face search error: {e}")
        else:
            self._update_progress("Skipping face search (no photo)", 15)

        # ===== STEP 2: Fast Async Email Discovery =====
        self._update_progress("Discovering emails (fast mode)...", 20)

        try:
            email_results = self.email_discovery.discover_sync(
                first_name=first_name,
                last_name=last_name,
                usernames=username_hints,
                profile_urls=selected_profiles
            )

            # Add discovered emails
            for discovered in email_results.emails:
                emails.append(DiscoveredEmail(
                    email=discovered.email,
                    source=discovered.source,
                    confidence=discovered.confidence,
                    verified_on=discovered.verified_on
                ))

            errors.extend(email_results.errors)

            self.logger.info(
                f"Email discovery: {len(email_results.emails)} emails found, "
                f"{email_results.candidates_generated} candidates, "
                f"{email_results.discovery_time:.1f}s"
            )

        except Exception as e:
            errors.append(f"Email discovery error: {str(e)}")
            self.logger.error(f"Email discovery error: {e}")

        # ===== STEP 2.5: Phone Discovery =====
        self._update_progress("Discovering phones...", 40)

        try:
            phone_service = PhoneDiscoveryService()

            # Get emails for phone extraction (some emails use phone as local part)
            found_email_strings = [e.email for e in emails] if emails else []

            phone_results = phone_service.discover_sync(
                first_name=first_name,
                last_name=last_name,
                usernames=username_hints,
                profile_urls=selected_profiles,
                emails=found_email_strings
            )

            # Add discovered phones
            for discovered in phone_results.phones:
                phones.append(DiscoveredPhone(
                    number=discovered.number,
                    source=discovered.source,
                    confidence=discovered.confidence
                ))

            errors.extend(phone_results.errors)

            self.logger.info(
                f"Phone discovery: {len(phone_results.phones)} phones found, "
                f"{phone_results.candidates_generated} candidates, "
                f"{phone_results.discovery_time:.1f}s"
            )

            phone_service.close()

        except Exception as e:
            errors.append(f"Phone discovery error: {str(e)}")
            self.logger.error(f"Phone discovery error: {e}")

        # ===== STEP 3: Quick Yandex Check (limited for speed) =====
        self._update_progress("Checking Yandex services...", 60)

        # Only check first username with reduced timeout
        if username_hints:
            try:
                yaseeker = YaSeekerService()
                yaseeker.rate_limit_delay = 0.2  # Faster rate limiting

                # Only check first username
                username = username_hints[0]
                accounts = yaseeker.check_all_services(username)

                for acc in accounts:
                    self._add_profile_if_valid({
                        'platform': acc.platform,
                        'url': acc.url,
                        'username': acc.username,
                        'source': 'YaSeeker'
                    }, additional_profiles)

                    if hasattr(acc, 'email') and acc.email:
                        emails.append(DiscoveredEmail(
                            email=acc.email,
                            source="YaSeeker",
                            confidence="medium",
                            verified_on=['yandex']
                        ))
            except Exception as e:
                self.logger.debug(f"YaSeeker error: {e}")

        # ===== STEP 3.5: Snoop Username Search (5,372+ sites, 2,600+ Russian) =====
        if self.snoop_service and username_hints:
            self._update_progress("Searching profiles via Snoop (5,372 sites)...", 75)
            self.logger.info("Step 3.5: Snoop username enumeration")

            try:
                # Search first 2 usernames (limit for speed in fast mode)
                snoop_found = 0
                for username in username_hints[:2]:
                    self._update_progress(f"Snoop: searching {username}...", 75)

                    # Use Russian-focused search for speed
                    snoop_results = self.snoop_service.search_username(
                        username,
                        timeout=120,  # 2 minutes per username
                        russian_only=True  # Focus on Russian sites for speed
                    )

                    # Filter to found profiles
                    found_profiles = self.snoop_service.get_found_profiles(snoop_results)

                    for result in found_profiles:
                        self._add_profile_if_valid({
                            'platform': result.get('platform', 'unknown'),
                            'url': result.get('url', ''),
                            'username': username,
                            'source': f"Snoop ({result.get('country', 'RU')})"
                        }, additional_profiles)
                        snoop_found += 1

                self.logger.info(f"Snoop found {snoop_found} additional profiles")

            except Exception as e:
                errors.append(f"Snoop error: {str(e)}")
                self.logger.debug(f"Snoop error: {e}")

        # ===== STEP 4: Deduplicate =====
        self._update_progress("Finalizing...", 90)

        phones = deduplicate_phones(phones)
        emails = deduplicate_emails(emails)

        # Convert to AdditionalProfile objects
        final_profiles = []
        for p in additional_profiles:
            if isinstance(p, dict):
                final_profiles.append(AdditionalProfile(
                    platform=p.get('platform', ''),
                    url=p.get('url', ''),
                    username=p.get('username', ''),
                    source=p.get('source', 'Unknown')
                ))
            else:
                final_profiles.append(p)

        final_profiles = deduplicate_profiles(final_profiles)

        # Stats
        elapsed_time = time.time() - start_time
        stats = {
            'profiles_analyzed': len(selected_profiles),
            'phones_found': len(phones),
            'emails_found': len(emails),
            'new_profiles_found': len(final_profiles),
            'face_matches': len(face_matches),
            'search_time': f"{elapsed_time:.1f}s",
            'mode': 'fast',
            'errors_count': len(errors)
        }

        self._update_progress("Complete!", 100)

        self.logger.info("=" * 60)
        self.logger.info("PHASE 2 FAST MODE COMPLETE:")
        self.logger.info(f"  Phones: {len(phones)}")
        self.logger.info(f"  Emails: {len(emails)}")
        self.logger.info(f"  Profiles: {len(final_profiles)}")
        self.logger.info(f"  Time: {elapsed_time:.1f}s")
        self.logger.info("=" * 60)

        return Phase2Results(
            phones=phones,
            emails=emails,
            additional_profiles=final_profiles,
            face_matches=face_matches,
            stats=stats,
            errors=errors
        )


def deduplicate_phones(phones: List[DiscoveredPhone]) -> List[DiscoveredPhone]:
    """Remove duplicate phones, keeping highest confidence. Uses RussianPhoneValidator for normalization."""
    validator = RussianPhoneValidator()
    seen = {}

    for phone in phones:
        # Use proper Russian phone normalization
        phone_info = validator.validate(phone.number)

        if phone_info.is_valid:
            normalized = phone_info.normalized
            # Update phone number to display format
            phone.number = phone_info.display_format
        else:
            # Fallback normalization
            normalized = phone.number.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')

        if normalized not in seen:
            seen[normalized] = phone
        elif phone.confidence == 'high' and seen[normalized].confidence != 'high':
            seen[normalized] = phone

    return list(seen.values())


def deduplicate_emails(emails: List[DiscoveredEmail]) -> List[DiscoveredEmail]:
    """Remove duplicate emails, merging verified_on lists."""
    seen = {}
    for email in emails:
        key = email.email.lower()
        if key not in seen:
            seen[key] = email
        else:
            # Merge verified_on lists
            seen[key].verified_on.extend(email.verified_on)
            seen[key].verified_on = list(set(seen[key].verified_on))
            # Keep higher confidence
            if email.confidence == 'high':
                seen[key].confidence = 'high'
    return list(seen.values())


def deduplicate_profiles(profiles: List[AdditionalProfile]) -> List[AdditionalProfile]:
    """Remove duplicate profiles."""
    seen = set()
    unique = []
    for profile in profiles:
        # Use URL as unique key
        key = profile.url.lower().rstrip('/')
        if key not in seen:
            seen.add(key)
            unique.append(profile)
    return unique
