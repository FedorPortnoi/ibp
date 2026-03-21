"""
Telegram Username Cross-Reference Service
==========================================
VK → Telegram username correlation for phone/profile discovery.

Tier 1: Web scraping of t.me preview pages (no API keys needed)
Tier 2: Telethon API for richer data (optional, needs credentials)

Technique: Russians commonly reuse the same username across VK and Telegram.
Even when phone isn't directly visible, people often put their phone number
in their Telegram bio for business/contact purposes.
"""

import logging
import os
import re
import time
from dataclasses import dataclass, field
from typing import List, Dict, Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Russian phone patterns for bio extraction
BIO_PHONE_PATTERNS = [
    r'\+7[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}',
    r'8[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}',
    r'(?<!\d)9\d{9}(?!\d)',
]


@dataclass
class TelegramProfile:
    """Result from checking a Telegram username."""
    exists: bool = False
    is_personal: bool = False  # True if personal account (not channel/bot/group)
    username: str = ''
    display_name: str = ''
    bio: str = ''
    photo_url: Optional[str] = None
    phones_in_bio: List[str] = field(default_factory=list)
    name_match: bool = False
    name_match_score: float = 0.0
    confidence: str = 'low'  # high/medium/low
    source: str = ''  # How we found this username
    error: Optional[str] = None


class TelegramCrossRef:
    """
    Cross-reference VK usernames against Telegram via t.me preview pages.

    Usage:
        checker = TelegramCrossRef()
        result = checker.check_username_web('kozlov_dmitry')
        if result.exists and result.is_personal:
            print(f'Found: {result.display_name}, bio: {result.bio}')
    """

    def __init__(self, request_delay: float = 1.5):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.request_delay = request_delay
        self._last_request_time = 0.0

    def _rate_limit(self):
        """Enforce delay between requests to t.me."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.request_delay:
            time.sleep(self.request_delay - elapsed)
        self._last_request_time = time.time()

    def check_username_web(self, username: str) -> TelegramProfile:
        """
        Tier 1: Check if a Telegram username exists via t.me preview page.

        t.me page structure:
        - tgme_page_title: display name (ABSENT if user doesn't exist)
        - tgme_page_description: bio text
        - tgme_page_extra: "@username" for users/bots, "N subscribers" for channels
        - tgme_page_action: "Send Message" for users, "Start Bot" for bots,
                            "View in Telegram" for channels/groups
        - tgme_page_photo > img: profile photo
        """
        username = username.lstrip('@').strip()
        if not username or len(username) < 2:
            return TelegramProfile(error='Username too short')

        # Skip obviously non-Telegram usernames
        if username.startswith('id') and username[2:].isdigit():
            return TelegramProfile(error='Numeric VK ID, not a username')

        self._rate_limit()

        try:
            url = f'https://t.me/{username}'
            resp = self.session.get(url, timeout=10)

            if resp.status_code != 200:
                return TelegramProfile(error=f'HTTP {resp.status_code}')

            soup = BeautifulSoup(resp.text, 'html.parser')

            # Key detection: tgme_page_title presence = entity exists
            title_div = soup.find('div', class_='tgme_page_title')
            if not title_div:
                return TelegramProfile(exists=False, username=username)

            # Entity exists — extract data
            profile = TelegramProfile(exists=True, username=username)
            profile.display_name = title_div.get_text(strip=True).rstrip('\u2714').strip()

            # Bio / description
            desc_div = soup.find('div', class_='tgme_page_description')
            if desc_div:
                profile.bio = desc_div.get_text(strip=True)

            # Extra info (subscribers/members count or @username)
            extra_div = soup.find('div', class_='tgme_page_extra')
            extra_text = extra_div.get_text(strip=True) if extra_div else ''

            # Action button text
            action_div = soup.find('div', class_='tgme_page_action')
            action_text = action_div.get_text(strip=True) if action_div else ''

            # Determine entity type
            is_channel = 'subscriber' in extra_text.lower()
            is_group = 'member' in extra_text.lower()
            is_bot = 'Start Bot' in action_text or 'bot' in action_text.lower()

            profile.is_personal = not is_channel and not is_group and not is_bot

            # Profile photo
            photo_div = soup.find('div', class_='tgme_page_photo')
            if photo_div:
                img = photo_div.find('img')
                if img and img.get('src'):
                    profile.photo_url = img['src']

            # Extract phone numbers from bio
            if profile.bio:
                profile.phones_in_bio = self._extract_phones_from_text(profile.bio)

            return profile

        except requests.Timeout:
            return TelegramProfile(error='Timeout', username=username)
        except Exception as e:
            logger.warning(f"Telegram web check error for @{username}: {e}")
            return TelegramProfile(error=str(e), username=username)

    def check_username_telethon(self, username: str) -> TelegramProfile:
        """
        Tier 2: Check username via Telethon API (richer data, needs credentials).
        Gracefully degrades if Telethon isn't configured.
        """
        api_id = os.environ.get('TELEGRAM_API_ID', '')
        api_hash = os.environ.get('TELEGRAM_API_HASH', '')

        if not api_id or not api_hash:
            return TelegramProfile(error='Telethon not configured')

        try:
            import asyncio
            from telethon import TelegramClient
            from telethon.tl.functions.contacts import ResolveUsernameRequest
            from telethon.tl.functions.users import GetFullUserRequest
            from telethon.errors import UsernameNotOccupiedError, FloodWaitError

            async def _resolve():
                session_name = os.path.join(
                    os.path.dirname(os.path.abspath(__file__)),
                    '..', '..', '..', 'ibp_telegram_session'
                )
                client = TelegramClient(session_name, int(api_id), api_hash)
                await client.connect()

                if not await client.is_user_authorized():
                    await client.disconnect()
                    return TelegramProfile(error='Telethon session not authorized')

                try:
                    result = await client(ResolveUsernameRequest(username))
                    if not result.users:
                        return TelegramProfile(exists=False, username=username)

                    user = result.users[0]
                    profile = TelegramProfile(
                        exists=True,
                        username=username,
                        display_name=f"{user.first_name or ''} {user.last_name or ''}".strip(),
                        is_personal=not getattr(user, 'bot', False),
                    )

                    # Get full profile for bio
                    try:
                        full = await client(GetFullUserRequest(user))
                        full_user = full.full_user if hasattr(full, 'full_user') else full
                        if hasattr(full_user, 'about') and full_user.about:
                            profile.bio = full_user.about
                            profile.phones_in_bio = self._extract_phones_from_text(profile.bio)
                    except Exception as e:
                        logger.debug(f"[TelegramCrossRef] Full user profile fetch failed: {e}")

                    # Phone from user object (only visible if in contacts)
                    if getattr(user, 'phone', None):
                        normalized = self._normalize_phone(user.phone)
                        if normalized:
                            profile.phones_in_bio.append(normalized)

                    return profile

                except UsernameNotOccupiedError:
                    return TelegramProfile(exists=False, username=username)
                except FloodWaitError as e:
                    return TelegramProfile(error=f'Rate limited: {e.seconds}s', username=username)
                finally:
                    await client.disconnect()

            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(_resolve())
            finally:
                loop.close()

        except ImportError:
            return TelegramProfile(error='Telethon not installed')
        except Exception as e:
            logger.warning(f"Telethon lookup error for @{username}: {e}")
            return TelegramProfile(error=str(e), username=username)

    def cross_reference_vk_profiles(
        self,
        vk_profiles: List[Dict],
        first_name: str,
        last_name: str,
        vk_connections_telegram: Optional[str] = None,
    ) -> List[TelegramProfile]:
        """
        Main entry point: check Telegram for usernames from VK profiles.

        Args:
            vk_profiles: List of VK profile dicts with 'url', 'username', 'screen_name'
            first_name: Target's first name (for name verification)
            last_name: Target's last name (for name verification)
            vk_connections_telegram: Telegram username from VK connections field (highest priority)

        Returns:
            List of TelegramProfile results
        """
        results = []
        checked_usernames = set()

        # Priority 1: VK connections field (confirmed link)
        if vk_connections_telegram:
            username = vk_connections_telegram.lstrip('@').strip()
            if username and username not in checked_usernames:
                checked_usernames.add(username)
                logger.info(f"Telegram cross-ref: checking VK connections username @{username}")

                profile = self._check_with_fallback(username)
                if profile.exists:
                    profile.source = 'VK connections (confirmed link)'
                    profile.confidence = 'high'
                    profile.name_match = True  # VK confirmed it
                    results.append(profile)

        # Priority 2: VK screen_names
        for vk_profile in vk_profiles[:5]:
            screen_name = vk_profile.get('screen_name') or vk_profile.get('username') or ''
            if not screen_name:
                # Try extracting from URL
                url = vk_profile.get('url', '')
                m = re.search(r'vk\.com/([a-zA-Z][a-zA-Z0-9_.]+)', url)
                if m:
                    screen_name = m.group(1)

            if not screen_name or screen_name in checked_usernames:
                continue

            # Skip numeric VK IDs
            if screen_name.startswith('id') and screen_name[2:].isdigit():
                continue

            checked_usernames.add(screen_name)
            logger.info(f"Telegram cross-ref: checking VK screen_name @{screen_name}")

            profile = self._check_with_fallback(screen_name)
            if profile.exists and profile.is_personal:
                profile.source = f'VK screen_name cross-reference'

                # Verify name match
                match_result = self._verify_names(
                    first_name, last_name,
                    profile.display_name
                )
                profile.name_match = match_result['match']
                profile.name_match_score = match_result['score']

                if profile.name_match:
                    profile.confidence = 'high' if match_result['score'] > 0.8 else 'medium'
                else:
                    profile.confidence = 'low'

                results.append(profile)

            if len(results) >= 3:
                break

        return results

    def _check_with_fallback(self, username: str) -> TelegramProfile:
        """Check username via web scraping, fall back to Telethon if available."""
        profile = self.check_username_web(username)

        # If web check found the user but Telethon is available, try to enrich
        if profile.exists and profile.is_personal and not profile.phones_in_bio:
            telethon_profile = self.check_username_telethon(username)
            if telethon_profile.exists and not telethon_profile.error:
                # Merge richer Telethon data
                if telethon_profile.bio and not profile.bio:
                    profile.bio = telethon_profile.bio
                if telethon_profile.phones_in_bio:
                    profile.phones_in_bio = telethon_profile.phones_in_bio

        return profile

    def _extract_phones_from_text(self, text: str) -> List[str]:
        """Extract Russian phone numbers from text (bio, description)."""
        phones = []
        for pattern in BIO_PHONE_PATTERNS:
            matches = re.finditer(pattern, text)
            for match in matches:
                raw = match.group(0)
                normalized = self._normalize_phone(raw)
                if normalized and normalized not in phones:
                    phones.append(normalized)
        return phones

    @staticmethod
    def _normalize_phone(raw: str) -> Optional[str]:
        """Normalize a raw phone string to +7XXXXXXXXXX format."""
        digits = re.sub(r'\D', '', raw)
        if len(digits) == 10 and digits.startswith('9'):
            return '+7' + digits
        if len(digits) == 11 and digits.startswith(('7', '8')):
            return '+7' + digits[1:]
        return None

    @staticmethod
    def _normalize_yo(text: str) -> str:
        """Normalize Russian ё→е (commonly interchanged in everyday typing)."""
        return text.replace('ё', 'е').replace('Ё', 'Е')

    def _verify_names(self, vk_first: str, vk_last: str, tg_display_name: str) -> Dict:
        """
        Verify if VK and Telegram names plausibly match.
        Uses existing diminutive and transliteration logic.
        """
        if not tg_display_name or not (vk_first or vk_last):
            return {'match': False, 'score': 0.0, 'method': 'no_data'}

        # Normalize ё→е: Russians commonly type "е" instead of "ё"
        # so "Артём" and "Артем" must be treated as identical
        vk_first = self._normalize_yo(vk_first)
        vk_last = self._normalize_yo(vk_last)
        tg_display_name = self._normalize_yo(tg_display_name)

        tg_parts = tg_display_name.strip().split()
        tg_first = tg_parts[0] if tg_parts else ''
        tg_last = tg_parts[-1] if len(tg_parts) > 1 else ''

        best_score = 0.0
        match_method = 'none'

        # Method 1: Direct comparison (case-insensitive)
        first_exact = vk_first and tg_first and vk_first.lower() == tg_first.lower()
        last_exact = vk_last and tg_last and vk_last.lower() == tg_last.lower()

        if first_exact and last_exact:
            best_score = 1.0
            match_method = 'full_name_exact'
        elif last_exact:
            best_score = max(best_score, 0.75)
            match_method = 'last_name_exact'
        elif first_exact:
            best_score = max(best_score, 0.5)
            match_method = 'first_name_exact'

        # Method 2: Last name similarity (most important for Russian names)
        if vk_last and tg_last:
            try:
                from .fuzzy_matching import surname_similarity
                sim = surname_similarity(vk_last, tg_last)
                if sim > best_score:
                    best_score = sim
                    match_method = f'surname_fuzzy({sim:.2f})'
            except ImportError:
                from difflib import SequenceMatcher
                sim = SequenceMatcher(None, vk_last.lower(), tg_last.lower()).ratio()
                if sim > best_score:
                    best_score = sim
                    match_method = f'surname_seq({sim:.2f})'

        # Method 3: Diminutive matching (Александр ↔ Саша)
        if vk_first and tg_first and best_score < 0.7:
            try:
                from .russian_diminutives import get_all_name_variants
                vk_variants = {v.lower() for v in get_all_name_variants(vk_first)}
                tg_variants = {v.lower() for v in get_all_name_variants(tg_first)}
                # Add the names themselves
                vk_variants.add(vk_first.lower())
                tg_variants.add(tg_first.lower())
                if vk_variants & tg_variants:
                    score = 0.85 if vk_last and tg_last and vk_last.lower() == tg_last.lower() else 0.6
                    if score > best_score:
                        best_score = score
                        match_method = 'diminutive'
            except ImportError:
                pass

        # Method 4: Transliteration matching (Dmitry ↔ Дмитрий)
        if best_score < 0.5 and vk_first and tg_first:
            try:
                from .transliteration import transliterate_russian
                vk_variants = {v.lower() for v in transliterate_russian(vk_first)}
                vk_variants.add(vk_first.lower())
                if tg_first.lower() in vk_variants:
                    best_score = max(best_score, 0.7)
                    match_method = 'transliteration'
            except ImportError:
                pass

        is_match = best_score >= 0.5
        return {'match': is_match, 'score': best_score, 'method': match_method}

    def close(self):
        """Clean up resources."""
        self.session.close()
