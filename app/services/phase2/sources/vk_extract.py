"""
VK Profile Extraction Source
=============================
Wraps existing VKAPIExtractor to conform to the BaseSource interface.
Extracts phones, emails, and linked accounts from VK profiles via API.

Tier: A (Platform API)
"""

import os
from typing import List, Optional

from ..base_source import BaseSource, SourceResult, SourceTier, SourceType


class VKExtractSource(BaseSource):
    """Extract contact data from VK profiles using the VK API."""

    name = "VK Profile API"
    source_type = SourceType.BOTH
    source_tier = SourceTier.A
    requires_api_key = False  # Works without token (limited), better with token
    rate_limit_per_minute = 30

    def __init__(self):
        super().__init__()
        self._extractor = None

    def _get_extractor(self):
        """Lazy-init the VK extractor."""
        if self._extractor is None:
            from ..vk_api_extractor import VKAPIExtractor
            token = os.environ.get('VK_SERVICE_TOKEN')
            self._extractor = VKAPIExtractor(access_token=token)
        return self._extractor

    def is_available(self) -> bool:
        """VK extraction works even without token (via scraping fallback)."""
        return True

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
        results = []

        # Need a VK profile to extract from
        profile_url = None
        if vk_id:
            profile_url = f"https://vk.com/id{vk_id}"
        elif username:
            profile_url = f"https://vk.com/{username}"

        if not profile_url:
            return results

        extractor = self._get_extractor()
        vk_contact = extractor.extract_from_url(profile_url)

        if vk_contact.error:
            self.logger.debug(f"VK extraction error: {vk_contact.error}")
            return results

        # Add phones
        for phone_num in vk_contact.phones:
            results.append(SourceResult(
                data_type='phone',
                value=phone_num,
                source_name=self.name,
                source_tier=self.source_tier,
                confidence=0.85,
                metadata={'vk_id': vk_contact.user_id, 'field': 'contacts'},
            ))

        # Add emails
        for email_addr in vk_contact.emails:
            results.append(SourceResult(
                data_type='email',
                value=email_addr,
                source_name=self.name,
                source_tier=self.source_tier,
                confidence=0.85,
                metadata={'vk_id': vk_contact.user_id, 'field': 'contacts'},
            ))

        # Add linked accounts as profiles
        linked = [
            ('telegram', vk_contact.telegram, 'https://t.me/{}'),
            ('instagram', vk_contact.instagram, 'https://instagram.com/{}'),
            ('twitter', vk_contact.twitter, 'https://twitter.com/{}'),
            ('facebook', vk_contact.facebook, 'https://facebook.com/{}'),
            ('skype', vk_contact.skype, 'skype:{}'),
        ]
        for platform, handle, url_fmt in linked:
            if handle:
                results.append(SourceResult(
                    data_type='profile',
                    value=url_fmt.format(handle),
                    source_name=self.name,
                    source_tier=self.source_tier,
                    confidence=0.9,
                    metadata={
                        'platform': platform,
                        'username': handle,
                        'vk_id': vk_contact.user_id,
                    },
                ))

        # Add websites
        for website in vk_contact.websites:
            results.append(SourceResult(
                data_type='profile',
                value=website if website.startswith('http') else f'https://{website}',
                source_name=self.name,
                source_tier=self.source_tier,
                confidence=0.8,
                metadata={'platform': 'website', 'vk_id': vk_contact.user_id},
            ))

        self.logger.info(
            f"VK extract: {len(vk_contact.phones)} phones, "
            f"{len(vk_contact.emails)} emails, "
            f"{sum(1 for _, h, _ in linked if h)} linked accounts"
        )

        return results
