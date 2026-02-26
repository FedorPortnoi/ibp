"""
GetContact / NumBuster Phone Lookup Source
===========================================
Reverse phone lookup using crowdsourced contact databases.

GetContact: Crowdsourced caller ID (how a number is saved in others' phones)
NumBuster: Similar service with trust ratings

Three authentication modes (checked in order):
1. GETCONTACT_API_KEY — simple API key (paid service)
2. GETCONTACT_TOKEN + AES_KEY + DEVICE_ID — rooted Android credentials
3. No credentials — demo mode with synthetic data

Tier: A (Platform API) — direct platform data, not leaked
"""

import os
import logging
from typing import List, Optional

from ..base_source import BaseSource, SourceResult, SourceTier, SourceType
from ...mock_data import _use_mock_apis, mock_getcontact, mock_numbuster

logger = logging.getLogger(__name__)


class GetContactSource(BaseSource):
    """
    Reverse phone lookup via GetContact API.

    Returns how a phone number is saved in other people's contacts.
    Useful for confirming that a phone belongs to the target.

    Authentication modes:
    - GETCONTACT_API_KEY: Simple API key (paid service)
    - GETCONTACT_TOKEN + AES_KEY + DEVICE_ID: Rooted Android credentials
    - No credentials: Demo mode returns synthetic data
    """

    name = "GetContact Lookup"
    source_type = SourceType.PHONE
    source_tier = SourceTier.A
    requires_api_key = True
    rate_limit_per_minute = 5  # Very limited queries per token/month

    def is_available(self) -> bool:
        return True  # Always available — demo mode when no credentials

    @property
    def _api_key(self) -> Optional[str]:
        return os.environ.get('GETCONTACT_API_KEY')

    @property
    def _legacy_credentials(self) -> Optional[tuple]:
        token = os.environ.get('GETCONTACT_TOKEN')
        aes_key = os.environ.get('GETCONTACT_AES_KEY')
        device_id = os.environ.get('GETCONTACT_DEVICE_ID')
        if token and aes_key:
            return (token, aes_key, device_id)
        return None

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
        if not phone:
            return []

        # Mock mode — return realistic Russian contact tags
        if _use_mock_apis():
            self.logger.debug(f"GetContact MOCK mode for: {phone}")
            mock_results = mock_getcontact(phone)
            results = []
            for record in mock_results:
                results.append(SourceResult(
                    data_type='name',
                    value=record['name'],
                    source_name=self.name,
                    source_tier=self.source_tier,
                    confidence=0.85,
                    metadata={
                        'phone': phone,
                        'tag_count': record['tag_count'],
                        'tags': record['tags'],
                        'country': record.get('country', 'RU'),
                        'mock': True,
                    },
                ))
            return results

        # Mode 1: Simple API key
        api_key = self._api_key
        if api_key:
            self.logger.info(
                f"GetContact REAL mode (API key): would call API "
                f"with key={api_key[:8]}... phone={phone}"
            )
            # TODO: Implement real API call when service is purchased
            return []

        # Mode 2: Legacy rooted Android credentials
        legacy = self._legacy_credentials
        if legacy:
            token, aes_key, device_id = legacy
            self.logger.info(
                f"GetContact REAL mode (legacy): would call API "
                f"with token={token[:8]}... phone={phone}"
            )
            # TODO: Implement using getcontact Python library
            return []

        # Mode 3: Demo mode
        self.logger.debug(f"GetContact DEMO mode for: {phone}")
        return [
            SourceResult(
                data_type='name',
                value='Демо Контакт',
                source_name=self.name,
                source_tier=self.source_tier,
                confidence=0.50,
                metadata={
                    'phone': phone,
                    'tag_count': 2,
                    'tags': ['Демо запись 1', 'Демо запись 2'],
                    'demo': True,
                },
            ),
        ]


class NumBusterSource(BaseSource):
    """
    Reverse phone lookup via NumBuster.

    NumBuster is a mobile app with caller ID and trust ratings.
    No documented API — would need to reverse-engineer the app
    or use the mobile API endpoints.

    Without NUMBUSTER_API_KEY: returns demo data.
    With key: logs intended API call (real implementation TODO).
    """

    name = "NumBuster Lookup"
    source_type = SourceType.PHONE
    source_tier = SourceTier.A
    requires_api_key = True
    rate_limit_per_minute = 5

    def is_available(self) -> bool:
        return True  # Always available — demo mode when no key

    @property
    def _api_key(self) -> Optional[str]:
        return os.environ.get('NUMBUSTER_API_KEY')

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
        if not phone:
            return []

        # Mock mode — return realistic Russian phone lookup
        if _use_mock_apis():
            self.logger.debug(f"NumBuster MOCK mode for: {phone}")
            mock_results = mock_numbuster(phone)
            results = []
            for record in mock_results:
                results.append(SourceResult(
                    data_type='name',
                    value=record['name'],
                    source_name=self.name,
                    source_tier=self.source_tier,
                    confidence=0.80,
                    metadata={
                        'phone': phone,
                        'trust_rating': record['trust_rating'],
                        'spam_reports': record.get('spam_reports', 0),
                        'views': record.get('views', 0),
                        'mock': True,
                    },
                ))
            return results

        key = self._api_key
        if key:
            self.logger.info(
                f"NumBuster REAL mode: would call API "
                f"with key={key[:8]}... phone={phone}"
            )
            # TODO: Implement if NumBuster API access is obtained
            return []

        # Demo mode
        self.logger.debug(f"NumBuster DEMO mode for: {phone}")
        return [
            SourceResult(
                data_type='name',
                value='Демо Абонент',
                source_name=self.name,
                source_tier=self.source_tier,
                confidence=0.45,
                metadata={
                    'phone': phone,
                    'trust_rating': 0.6,
                    'demo': True,
                },
            ),
        ]
