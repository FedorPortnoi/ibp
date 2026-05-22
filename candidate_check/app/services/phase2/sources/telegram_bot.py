"""
Telegram Bot Query Source
==========================
Queries Russian OSINT Telegram bots programmatically via Telethon.

Supported bots (when Telegram session is configured):
- Himera Search (@HimeraSearchBot) — has official API, 9B+ records
- Leak OSINT (@LeakOSINTBot) — API available, 7-day free trial
- InfoTrackPeople (@treckbotpeople_bot) — documented REST API

Tier: S (Breach Database) — bots query real leaked/government databases

PLACEHOLDER: Requires Telethon session manager to be configured.
See app/services/telegram/ for session management.
"""

import os
from typing import List, Optional

from ..base_source import BaseSource, SourceResult, SourceTier, SourceType


class TelegramBotSource(BaseSource):
    """
    Query Telegram OSINT bots for person data.

    Uses the Telethon session manager (app/services/telegram/)
    to send queries to bots and parse their responses.

    Legal note: Using breach-data bots on Russian citizens
    may violate Article 272.1 of the Russian Criminal Code
    (effective Dec 2024). Use at your own risk.
    """

    name = "Telegram OSINT Bots"
    source_type = SourceType.IDENTITY
    source_tier = SourceTier.S
    enabled = False
    implemented = False
    requires_api_key = True  # Needs Telegram session
    rate_limit_per_minute = 5  # Very conservative to avoid bans

    def is_available(self) -> bool:
        """Check if Telegram session is configured."""
        try:
            from ...telegram.config import is_configured
            return is_configured()
        except ImportError:
            return False

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
        raise NotImplementedError("Telegram bot source is not implemented and is not registered")


class HimeraAPISource(BaseSource):
    """
    Query Himera Search via their official API.

    Himera offers a direct API for automated access (not via Telegram).
    Contact their support for API documentation and pricing.

    9,000+ databases, 9B+ records.
    Per-query: 35-139 RUB depending on query type.
    """

    name = "Himera Search API"
    source_type = SourceType.IDENTITY
    source_tier = SourceTier.S
    enabled = False
    implemented = False
    requires_api_key = True
    rate_limit_per_minute = 30

    def is_available(self) -> bool:
        return bool(os.environ.get('HIMERA_API_KEY'))

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
        raise NotImplementedError("Himera API source is not implemented and is not registered")


class InfoTrackPeopleSource(BaseSource):
    """
    Query InfoTrackPeople REST API.

    Documented API at docs.infotrackpeople.org (v2).
    Supports: FIO, phone, email, INN, passport, SNILS, Telegram,
              username, address, vehicle number, VIN, password, photo.

    API key obtained via support contact.
    """

    name = "InfoTrackPeople API"
    source_type = SourceType.IDENTITY
    source_tier = SourceTier.S
    enabled = False
    implemented = False
    requires_api_key = True
    rate_limit_per_minute = 30

    def is_available(self) -> bool:
        return bool(os.environ.get('INFOTRACKPEOPLE_API_KEY'))

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
        raise NotImplementedError("InfoTrackPeople source is not implemented and is not registered")
