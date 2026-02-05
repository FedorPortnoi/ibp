"""
Telegram Phone Lookup - IBP Prototype B.6
Resolve phone numbers to Telegram users using Telethon

Features:
- Phone number to Telegram user resolution
- Profile data extraction (bio, photo, etc.)
- Username lookup
- Contact import method
- Rate limiting and error handling
- Async operation support

Requirements:
    pip install telethon

Usage:
    lookup = TelegramPhoneLookup(api_id, api_hash)
    await lookup.connect()
    result = await lookup.lookup_phone("+79161234567")
    print(f"Username: {result.username}")
"""

import os
import sys
import asyncio
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Union
from datetime import datetime
import json
import re
import hashlib
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Optional imports
HAS_TELETHON = False

try:
    from telethon import TelegramClient
    from telethon.tl.functions.contacts import (
        ImportContactsRequest,
        DeleteContactsRequest,
        GetContactsRequest,
        ResolveUsernameRequest
    )
    from telethon.tl.functions.users import GetFullUserRequest
    from telethon.tl.functions.photos import GetUserPhotosRequest
    from telethon.tl.types import (
        InputPhoneContact,
        User,
        UserFull,
        InputUser,
        Photo
    )
    from telethon.errors import (
        FloodWaitError,
        PhoneNumberInvalidError,
        UserPrivacyRestrictedError,
        UsernameNotOccupiedError,
        ApiIdInvalidError
    )
    HAS_TELETHON = True
except ImportError:
    logger.warning("telethon not installed - using DEMO mode")


@dataclass
class TelegramUser:
    """Telegram user profile data"""
    user_id: int
    phone: Optional[str] = None
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    bio: Optional[str] = None

    # Status flags
    is_verified: bool = False
    is_premium: bool = False
    is_bot: bool = False
    is_scam: bool = False
    is_fake: bool = False

    # Privacy settings (what we could access)
    phone_visible: bool = False
    photo_visible: bool = True
    bio_visible: bool = True

    # Photo info
    photo_id: Optional[int] = None
    photo_dc_id: Optional[int] = None
    has_photo: bool = False

    # Activity
    last_seen: Optional[datetime] = None
    status: Optional[str] = None  # online, offline, recently, within_week, etc.

    # Common contacts
    common_chats_count: int = 0

    # Raw data
    raw_data: Dict[str, Any] = field(default_factory=dict)

    @property
    def full_name(self) -> str:
        """Get full name"""
        parts = []
        if self.first_name:
            parts.append(self.first_name)
        if self.last_name:
            parts.append(self.last_name)
        return " ".join(parts) or "Unknown"

    @property
    def profile_url(self) -> Optional[str]:
        """Get profile URL if username exists"""
        if self.username:
            return f"https://t.me/{self.username}"
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "phone": self.phone,
            "username": self.username,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "full_name": self.full_name,
            "bio": self.bio,
            "profile_url": self.profile_url,
            "is_verified": self.is_verified,
            "is_premium": self.is_premium,
            "is_bot": self.is_bot,
            "is_scam": self.is_scam,
            "is_fake": self.is_fake,
            "phone_visible": self.phone_visible,
            "photo_visible": self.photo_visible,
            "has_photo": self.has_photo,
            "status": self.status,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
            "common_chats_count": self.common_chats_count
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)


@dataclass
class LookupResult:
    """Result of a phone/username lookup"""
    success: bool
    user: Optional[TelegramUser] = None
    error: Optional[str] = None
    error_code: Optional[str] = None
    lookup_method: str = "unknown"
    lookup_time_ms: float = 0.0

    # Rate limit info
    flood_wait_seconds: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "user": self.user.to_dict() if self.user else None,
            "error": self.error,
            "error_code": self.error_code,
            "lookup_method": self.lookup_method,
            "lookup_time_ms": round(self.lookup_time_ms, 2),
            "flood_wait_seconds": self.flood_wait_seconds
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)


@dataclass
class BatchLookupResult:
    """Results from batch phone lookup"""
    total: int
    successful: int
    failed: int
    results: List[LookupResult] = field(default_factory=list)
    processing_time_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total": self.total,
            "successful": self.successful,
            "failed": self.failed,
            "success_rate": round(self.successful / self.total * 100, 2) if self.total > 0 else 0,
            "processing_time_ms": round(self.processing_time_ms, 2),
            "results": [r.to_dict() for r in self.results]
        }


class TelegramPhoneLookup:
    """
    Telegram phone number to user lookup service

    Uses Telethon library for Telegram API access.
    Requires API credentials from https://my.telegram.org
    """

    # Rate limiting
    MIN_REQUEST_INTERVAL = 1.0  # Minimum seconds between requests
    MAX_CONTACTS_PER_IMPORT = 100  # Telegram limit

    def __init__(
        self,
        api_id: Optional[int] = None,
        api_hash: Optional[str] = None,
        session_name: str = "ibp_telegram_lookup",
        demo_mode: bool = False
    ):
        """
        Initialize Telegram lookup client

        Args:
            api_id: Telegram API ID from my.telegram.org
            api_hash: Telegram API hash from my.telegram.org
            session_name: Name for session file
            demo_mode: Force demo mode (simulated responses)
        """
        self.api_id = api_id or int(os.getenv("TELEGRAM_API_ID", "0"))
        self.api_hash = api_hash or os.getenv("TELEGRAM_API_HASH", "")
        self.session_name = session_name

        self.demo_mode = demo_mode or not HAS_TELETHON or self.api_id == 0
        self.client: Optional['TelegramClient'] = None
        self._connected = False
        self._last_request_time = 0.0

        if self.demo_mode:
            logger.info("Running in DEMO mode - responses will be simulated")
        else:
            logger.info(f"Initialized with API ID: {self.api_id}")

    async def connect(self) -> bool:
        """
        Connect to Telegram and authenticate

        Returns:
            True if connected successfully
        """
        if self.demo_mode:
            self._connected = True
            logger.info("Demo mode: Simulated connection")
            return True

        if not HAS_TELETHON:
            logger.error("Telethon not installed")
            return False

        try:
            self.client = TelegramClient(
                self.session_name,
                self.api_id,
                self.api_hash
            )

            await self.client.start()
            self._connected = True

            me = await self.client.get_me()
            logger.info(f"Connected as: {me.first_name} (@{me.username})")

            return True

        except ApiIdInvalidError:
            logger.error("Invalid API ID or hash")
            return False
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            return False

    async def disconnect(self):
        """Disconnect from Telegram"""
        if self.client and self._connected:
            await self.client.disconnect()
            self._connected = False
            logger.info("Disconnected")

    async def _rate_limit(self):
        """Apply rate limiting between requests"""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.MIN_REQUEST_INTERVAL:
            await asyncio.sleep(self.MIN_REQUEST_INTERVAL - elapsed)
        self._last_request_time = time.time()

    def _normalize_phone(self, phone: str) -> str:
        """Normalize phone number to international format"""
        # Remove all non-digit characters except leading +
        if phone.startswith("+"):
            return "+" + re.sub(r'\D', '', phone[1:])
        return "+" + re.sub(r'\D', '', phone)

    async def lookup_phone(self, phone: str) -> LookupResult:
        """
        Lookup a Telegram user by phone number

        Args:
            phone: Phone number in international format (+79161234567)

        Returns:
            LookupResult with user data if found
        """
        start_time = time.time()
        phone = self._normalize_phone(phone)

        if self.demo_mode:
            return await self._demo_lookup_phone(phone)

        if not self._connected:
            return LookupResult(
                success=False,
                error="Not connected to Telegram",
                error_code="NOT_CONNECTED",
                lookup_method="phone",
                lookup_time_ms=(time.time() - start_time) * 1000
            )

        await self._rate_limit()

        try:
            # Method: Import as contact, get user, delete contact
            contact = InputPhoneContact(
                client_id=0,
                phone=phone,
                first_name="IBP",
                last_name="Lookup"
            )

            # Import contact
            result = await self.client(ImportContactsRequest([contact]))

            if not result.users:
                # No user found for this phone
                return LookupResult(
                    success=False,
                    error="No Telegram user found for this phone number",
                    error_code="USER_NOT_FOUND",
                    lookup_method="phone_import",
                    lookup_time_ms=(time.time() - start_time) * 1000
                )

            user = result.users[0]

            # Get full profile
            try:
                full = await self.client(GetFullUserRequest(user))
                user_data = self._parse_user(user, full.full_user if hasattr(full, 'full_user') else full)
            except UserPrivacyRestrictedError:
                user_data = self._parse_user(user, None)
                user_data.bio_visible = False

            user_data.phone = phone
            user_data.phone_visible = True

            # Clean up: delete the imported contact
            try:
                await self.client(DeleteContactsRequest([InputUser(user.id, user.access_hash)]))
            except Exception:
                pass  # Ignore cleanup errors

            return LookupResult(
                success=True,
                user=user_data,
                lookup_method="phone_import",
                lookup_time_ms=(time.time() - start_time) * 1000
            )

        except FloodWaitError as e:
            return LookupResult(
                success=False,
                error=f"Rate limited, wait {e.seconds} seconds",
                error_code="FLOOD_WAIT",
                flood_wait_seconds=e.seconds,
                lookup_method="phone_import",
                lookup_time_ms=(time.time() - start_time) * 1000
            )

        except PhoneNumberInvalidError:
            return LookupResult(
                success=False,
                error="Invalid phone number format",
                error_code="PHONE_INVALID",
                lookup_method="phone_import",
                lookup_time_ms=(time.time() - start_time) * 1000
            )

        except Exception as e:
            logger.error(f"Lookup error: {e}")
            return LookupResult(
                success=False,
                error=str(e),
                error_code="UNKNOWN_ERROR",
                lookup_method="phone_import",
                lookup_time_ms=(time.time() - start_time) * 1000
            )

    async def lookup_username(self, username: str) -> LookupResult:
        """
        Lookup a Telegram user by username

        Args:
            username: Telegram username (with or without @)

        Returns:
            LookupResult with user data if found
        """
        start_time = time.time()

        # Normalize username
        username = username.lstrip("@")

        if self.demo_mode:
            return await self._demo_lookup_username(username)

        if not self._connected:
            return LookupResult(
                success=False,
                error="Not connected to Telegram",
                error_code="NOT_CONNECTED",
                lookup_method="username",
                lookup_time_ms=(time.time() - start_time) * 1000
            )

        await self._rate_limit()

        try:
            result = await self.client(ResolveUsernameRequest(username))

            if not result.users:
                return LookupResult(
                    success=False,
                    error=f"Username @{username} not found",
                    error_code="USERNAME_NOT_FOUND",
                    lookup_method="username",
                    lookup_time_ms=(time.time() - start_time) * 1000
                )

            user = result.users[0]

            # Get full profile
            try:
                full = await self.client(GetFullUserRequest(user))
                user_data = self._parse_user(user, full.full_user if hasattr(full, 'full_user') else full)
            except UserPrivacyRestrictedError:
                user_data = self._parse_user(user, None)

            return LookupResult(
                success=True,
                user=user_data,
                lookup_method="username",
                lookup_time_ms=(time.time() - start_time) * 1000
            )

        except UsernameNotOccupiedError:
            return LookupResult(
                success=False,
                error=f"Username @{username} not found",
                error_code="USERNAME_NOT_FOUND",
                lookup_method="username",
                lookup_time_ms=(time.time() - start_time) * 1000
            )

        except FloodWaitError as e:
            return LookupResult(
                success=False,
                error=f"Rate limited, wait {e.seconds} seconds",
                error_code="FLOOD_WAIT",
                flood_wait_seconds=e.seconds,
                lookup_method="username",
                lookup_time_ms=(time.time() - start_time) * 1000
            )

        except Exception as e:
            logger.error(f"Username lookup error: {e}")
            return LookupResult(
                success=False,
                error=str(e),
                error_code="UNKNOWN_ERROR",
                lookup_method="username",
                lookup_time_ms=(time.time() - start_time) * 1000
            )

    def _parse_user(self, user: 'User', full_user: Optional['UserFull'] = None) -> TelegramUser:
        """Parse Telethon User object to TelegramUser"""
        tg_user = TelegramUser(
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            is_verified=getattr(user, 'verified', False),
            is_premium=getattr(user, 'premium', False),
            is_bot=getattr(user, 'bot', False),
            is_scam=getattr(user, 'scam', False),
            is_fake=getattr(user, 'fake', False)
        )

        # Parse status
        if hasattr(user, 'status') and user.status:
            status_type = type(user.status).__name__
            status_map = {
                'UserStatusOnline': 'online',
                'UserStatusOffline': 'offline',
                'UserStatusRecently': 'recently',
                'UserStatusLastWeek': 'within_week',
                'UserStatusLastMonth': 'within_month',
                'UserStatusEmpty': 'unknown'
            }
            tg_user.status = status_map.get(status_type, 'unknown')

            # Get last seen time for offline status
            if status_type == 'UserStatusOffline' and hasattr(user.status, 'was_online'):
                tg_user.last_seen = user.status.was_online

        # Parse photo
        if hasattr(user, 'photo') and user.photo:
            tg_user.has_photo = True
            if hasattr(user.photo, 'photo_id'):
                tg_user.photo_id = user.photo.photo_id
            if hasattr(user.photo, 'dc_id'):
                tg_user.photo_dc_id = user.photo.dc_id

        # Parse full user info
        if full_user:
            if hasattr(full_user, 'about') and full_user.about:
                tg_user.bio = full_user.about

            if hasattr(full_user, 'common_chats_count'):
                tg_user.common_chats_count = full_user.common_chats_count

        return tg_user

    async def lookup_phones_batch(self, phones: List[str]) -> BatchLookupResult:
        """
        Lookup multiple phone numbers

        Args:
            phones: List of phone numbers

        Returns:
            BatchLookupResult with all results
        """
        start_time = time.time()
        results = []
        successful = 0
        failed = 0

        for phone in phones:
            result = await self.lookup_phone(phone)
            results.append(result)

            if result.success:
                successful += 1
            else:
                failed += 1

            # Handle rate limiting
            if result.flood_wait_seconds:
                logger.warning(f"Rate limited, waiting {result.flood_wait_seconds}s")
                await asyncio.sleep(result.flood_wait_seconds)

        return BatchLookupResult(
            total=len(phones),
            successful=successful,
            failed=failed,
            results=results,
            processing_time_ms=(time.time() - start_time) * 1000
        )

    async def get_user_photos(self, user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get user's profile photos

        Args:
            user_id: Telegram user ID
            limit: Maximum number of photos

        Returns:
            List of photo metadata
        """
        if self.demo_mode:
            return [{"photo_id": i, "date": "2024-01-01"} for i in range(min(3, limit))]

        if not self._connected:
            return []

        try:
            await self._rate_limit()

            photos = await self.client(GetUserPhotosRequest(
                user_id=user_id,
                offset=0,
                max_id=0,
                limit=limit
            ))

            result = []
            for photo in photos.photos:
                if isinstance(photo, Photo):
                    result.append({
                        "photo_id": photo.id,
                        "date": photo.date.isoformat() if photo.date else None,
                        "has_video": getattr(photo, 'has_video', False)
                    })

            return result

        except Exception as e:
            logger.error(f"Error getting photos: {e}")
            return []

    # Demo mode implementations
    async def _demo_lookup_phone(self, phone: str) -> LookupResult:
        """Simulated phone lookup for demo mode"""
        await asyncio.sleep(0.1)  # Simulate network delay

        # Generate deterministic "result" based on phone number
        phone_hash = hashlib.md5(phone.encode()).hexdigest()
        found = int(phone_hash[0], 16) > 4  # ~70% chance of finding

        if not found:
            return LookupResult(
                success=False,
                error="No Telegram user found for this phone number (demo)",
                error_code="USER_NOT_FOUND",
                lookup_method="phone_import_demo",
                lookup_time_ms=100.0
            )

        # Generate demo user
        user_id = int(phone_hash[:8], 16)
        demo_names = [
            ("Александр", "Иванов"),
            ("Мария", "Петрова"),
            ("Дмитрий", "Сидоров"),
            ("Елена", "Козлова"),
            ("Сергей", "Новиков"),
            ("Анна", "Морозова"),
            ("Андрей", "Волков"),
            ("Ольга", "Соколова")
        ]
        name_idx = user_id % len(demo_names)
        first_name, last_name = demo_names[name_idx]

        username = f"user_{phone_hash[:6]}" if int(phone_hash[1], 16) > 6 else None

        user = TelegramUser(
            user_id=user_id,
            phone=phone,
            username=username,
            first_name=first_name,
            last_name=last_name,
            bio="Демо профиль Telegram" if int(phone_hash[2], 16) > 8 else None,
            is_verified=int(phone_hash[3], 16) > 14,
            is_premium=int(phone_hash[4], 16) > 12,
            has_photo=int(phone_hash[5], 16) > 3,
            status="recently" if int(phone_hash[6], 16) > 8 else "within_week",
            phone_visible=True
        )

        return LookupResult(
            success=True,
            user=user,
            lookup_method="phone_import_demo",
            lookup_time_ms=100.0
        )

    async def _demo_lookup_username(self, username: str) -> LookupResult:
        """Simulated username lookup for demo mode"""
        await asyncio.sleep(0.1)

        username_hash = hashlib.md5(username.encode()).hexdigest()
        found = int(username_hash[0], 16) > 3  # ~75% chance

        if not found:
            return LookupResult(
                success=False,
                error=f"Username @{username} not found (demo)",
                error_code="USERNAME_NOT_FOUND",
                lookup_method="username_demo",
                lookup_time_ms=100.0
            )

        user_id = int(username_hash[:8], 16)

        user = TelegramUser(
            user_id=user_id,
            username=username,
            first_name="Demo",
            last_name="User",
            bio=f"Profile for @{username}",
            is_verified=int(username_hash[1], 16) > 14,
            has_photo=True,
            status="online" if int(username_hash[2], 16) > 12 else "recently"
        )

        return LookupResult(
            success=True,
            user=user,
            lookup_method="username_demo",
            lookup_time_ms=100.0
        )


async def demo():
    """Demonstrate Telegram lookup capabilities"""
    print("=" * 60)
    print("Telegram Phone Lookup - IBP Prototype B.6")
    print("=" * 60)
    print()

    # Initialize in demo mode
    lookup = TelegramPhoneLookup(demo_mode=True)
    await lookup.connect()

    print("Demo Mode - Simulated Telegram Lookups")
    print("-" * 40)

    # Test phone lookups
    test_phones = [
        "+79161234567",
        "+79031112233",
        "+79269876543"
    ]

    print("\nPhone Number Lookups:")
    for phone in test_phones:
        result = await lookup.lookup_phone(phone)
        print(f"\n  {phone}:")
        if result.success:
            print(f"    User ID: {result.user.user_id}")
            print(f"    Name: {result.user.full_name}")
            print(f"    Username: @{result.user.username}" if result.user.username else "    Username: (not set)")
            print(f"    Bio: {result.user.bio or '(empty)'}")
            print(f"    Premium: {result.user.is_premium}")
            print(f"    Status: {result.user.status}")
        else:
            print(f"    Not found: {result.error}")

    # Test username lookups
    test_usernames = [
        "durov",
        "telegram",
        "testuser123"
    ]

    print("\n\nUsername Lookups:")
    for username in test_usernames:
        result = await lookup.lookup_username(username)
        print(f"\n  @{username}:")
        if result.success:
            print(f"    User ID: {result.user.user_id}")
            print(f"    Name: {result.user.full_name}")
            print(f"    Verified: {result.user.is_verified}")
        else:
            print(f"    Not found: {result.error}")

    await lookup.disconnect()

    print("\n" + "=" * 60)
    print("Usage Example:")
    print("-" * 40)
    print("""
import asyncio
from telegram_phone_lookup import TelegramPhoneLookup

async def main():
    # Get API credentials from https://my.telegram.org
    lookup = TelegramPhoneLookup(
        api_id=YOUR_API_ID,
        api_hash="YOUR_API_HASH"
    )

    # Connect (will prompt for phone/code on first run)
    await lookup.connect()

    # Lookup by phone number
    result = await lookup.lookup_phone("+79161234567")
    if result.success:
        print(f"Found: {result.user.full_name}")
        print(f"Username: @{result.user.username}")
        print(f"Bio: {result.user.bio}")

    # Lookup by username
    result = await lookup.lookup_username("durov")
    if result.success:
        print(f"User ID: {result.user.user_id}")

    # Batch lookup
    phones = ["+79161234567", "+79031112233"]
    batch_result = await lookup.lookup_phones_batch(phones)
    print(f"Found {batch_result.successful} of {batch_result.total}")

    await lookup.disconnect()

asyncio.run(main())
""")

    print("\n" + "=" * 60)
    print("\nJSON Output Example:")
    print("-" * 40)

    # Create sample result
    sample_result = await lookup.lookup_phone("+79161234567")
    print(sample_result.to_json())


def main():
    """Entry point"""
    asyncio.run(demo())


if __name__ == "__main__":
    main()
