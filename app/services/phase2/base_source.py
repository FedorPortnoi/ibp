"""
Phase 2 Source Plugin Base Class
================================
Abstract base class that all Phase 2 data sources must inherit from.
Provides a uniform interface for querying diverse data sources:
- Breach database APIs (LeakCheck, Dehashed, Snusbase)
- Telegram OSINT bots (Himera Search, Leak OSINT, etc.)
- Platform APIs (VK, GetContact, NumBuster)
- Verification services (Holehe, SMTP, Gravatar)
- Pattern generation (email patterns, username analysis)

Each source returns SourceResult objects with confidence scores
that the SourceManager merges, deduplicates, and cross-validates.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class SourceType(Enum):
    """What kind of data this source returns."""
    EMAIL = "email"
    PHONE = "phone"
    BOTH = "both"
    IDENTITY = "identity"       # Returns name, address, passport, etc.
    PROFILE = "profile"         # Returns social media profiles/URLs
    VERIFICATION = "verification"  # Verifies existing data (doesn't discover new)


class SourceTier(Enum):
    """
    Source reliability tier. Higher tiers produce more trustworthy data.
    Used for confidence scoring and result prioritization.
    """
    S = "Breach Database"       # LeakCheck, Telegram bots — real data from leaks
    A = "Platform API"          # VK API, Telegram API — direct platform queries
    B = "Verification"          # Holehe, SMTP, Epieos — confirms if data exists
    C = "Pattern Generation"    # Email pattern generation — guessing


@dataclass
class SourceResult:
    """
    Single result from a data source.

    This is the universal data unit that flows through the entire
    Phase 2 pipeline. Every source produces these, and the SourceManager
    merges/deduplicates them.
    """
    data_type: str              # "email", "phone", "name", "address", "profile", etc.
    value: str                  # The actual data (email address, phone number, URL, etc.)
    source_name: str            # Which source found this (e.g., "LeakCheck API")
    source_tier: SourceTier     # How reliable is this source type
    confidence: float           # 0.0 to 1.0 (0.9+ = very high, 0.7+ = good, 0.5+ = medium, <0.5 = low)
    verified: bool = False      # Has this been cross-validated by another source?
    raw_data: Dict = field(default_factory=dict)    # Full raw response from source
    metadata: Dict = field(default_factory=dict)     # Extra info (breach name, date, platform, etc.)

    @property
    def confidence_label(self) -> str:
        """Human-readable confidence label."""
        if self.confidence >= 0.9:
            return "very_high"
        elif self.confidence >= 0.7:
            return "high"
        elif self.confidence >= 0.5:
            return "medium"
        else:
            return "low"

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for JSON response."""
        return {
            'data_type': self.data_type,
            'value': self.value,
            'source_name': self.source_name,
            'source_tier': self.source_tier.value,
            'confidence': self.confidence,
            'confidence_label': self.confidence_label,
            'verified': self.verified,
            'metadata': self.metadata,
        }


class BaseSource(ABC):
    """
    Abstract base class for all Phase 2 data sources.

    To create a new source, inherit from this class and implement:
    - query() — perform the actual data lookup
    - is_available() — check if this source is configured

    The SourceManager will auto-discover all BaseSource subclasses
    in the sources/ directory and orchestrate them.
    """

    name: str = "Unknown Source"
    source_type: SourceType = SourceType.BOTH
    source_tier: SourceTier = SourceTier.C
    enabled: bool = True
    requires_api_key: bool = False
    rate_limit_per_minute: int = 10

    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def query(
        self,
        name: Optional[str] = None,
        phone: Optional[str] = None,
        email: Optional[str] = None,
        username: Optional[str] = None,
        vk_id: Optional[str] = None,
        photo_path: Optional[str] = None,
        **kwargs
    ) -> List[SourceResult]:
        """
        Query this source with available input data.

        This is a sync wrapper around query_impl(). It handles error
        catching so individual sources never crash the pipeline.

        Returns list of SourceResult objects.
        """
        try:
            return self.query_impl(
                name=name,
                phone=phone,
                email=email,
                username=username,
                vk_id=vk_id,
                photo_path=photo_path,
                **kwargs
            )
        except Exception as e:
            self.logger.error(f"Source {self.name} query error: {e}", exc_info=True)
            return []

    @abstractmethod
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
        """
        Actual query implementation. Subclasses MUST implement this.

        Should return empty list on failure, never raise exceptions.
        The wrapper query() catches exceptions as a safety net.
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if this source is configured and available.

        For API-based sources, check if API key is set.
        For Telegram bots, check if session is configured.
        For pattern generators, always return True.
        """
        pass

    def get_info(self) -> Dict[str, Any]:
        """Return source metadata for UI display and status dashboard."""
        return {
            "name": self.name,
            "type": self.source_type.value,
            "tier": self.source_tier.value,
            "tier_label": self.source_tier.name,
            "enabled": self.enabled,
            "requires_api_key": self.requires_api_key,
            "available": self.is_available(),
            "rate_limit": self.rate_limit_per_minute,
        }
