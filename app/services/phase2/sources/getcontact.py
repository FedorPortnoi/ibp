"""
GetContact / NumBuster Phone Lookup Source
===========================================
Reverse phone lookup using crowdsourced contact databases.

GetContact: Crowdsourced caller ID (how a number is saved in others' phones)
NumBuster: Similar service with trust ratings

GetContact has a reverse-engineered Python API:
  https://github.com/kovinevmv/getcontact
  Requires AES_KEY, TOKEN, DEVICE_ID from a rooted Android device.

Tier: A (Platform API) — direct platform data, not leaked

PLACEHOLDER: Requires GetContact credentials from Android device.
"""

import os
from typing import List, Optional

from ..base_source import BaseSource, SourceResult, SourceTier, SourceType


class GetContactSource(BaseSource):
    """
    Reverse phone lookup via GetContact API.

    Returns how a phone number is saved in other people's contacts.
    Useful for confirming that a phone belongs to the target.

    Setup: Extract credentials from rooted Android with GetContact installed.
    Set env vars: GETCONTACT_AES_KEY, GETCONTACT_TOKEN, GETCONTACT_DEVICE_ID
    """

    name = "GetContact Lookup"
    source_type = SourceType.PHONE
    source_tier = SourceTier.A
    requires_api_key = True
    rate_limit_per_minute = 5  # Very limited queries per token/month

    def is_available(self) -> bool:
        return bool(
            os.environ.get('GETCONTACT_TOKEN')
            and os.environ.get('GETCONTACT_AES_KEY')
        )

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

        # TODO: Implement using getcontact Python library
        #
        # from getcontact import GetContact
        # gc = GetContact(
        #     token=os.environ["GETCONTACT_TOKEN"],
        #     aes_key=os.environ["GETCONTACT_AES_KEY"],
        #     device_id=os.environ["GETCONTACT_DEVICE_ID"]
        # )
        # result = gc.search(phone)
        # for tag in result.get("tags", []):
        #     # tag = {"displayName": "Иванов Иван", ...}
        #     results.append(SourceResult(
        #         data_type='name',
        #         value=tag["displayName"],
        #         source_name=self.name,
        #         source_tier=self.source_tier,
        #         confidence=0.75,
        #         metadata={'phone': phone, 'tag_count': len(result.get("tags", []))},
        #     ))
        #
        self.logger.debug("GetContact source not yet implemented")
        return []


class NumBusterSource(BaseSource):
    """
    Reverse phone lookup via NumBuster.

    NumBuster is a mobile app with caller ID and trust ratings.
    No documented API — would need to reverse-engineer the app
    or use the mobile API endpoints.
    """

    name = "NumBuster Lookup"
    source_type = SourceType.PHONE
    source_tier = SourceTier.A
    requires_api_key = True
    rate_limit_per_minute = 5

    def is_available(self) -> bool:
        return bool(os.environ.get('NUMBUSTER_API_KEY'))

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
        # TODO: Implement if NumBuster API access is obtained
        self.logger.debug("NumBuster source not yet implemented")
        return []
