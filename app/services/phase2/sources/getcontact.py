"""
GetContact / NumBuster Phone Lookup Source
===========================================
Reverse phone lookup using crowdsourced contact databases.

GetContact: Crowdsourced caller ID (how a number is saved in others' phones)
NumBuster: Similar service with trust ratings

Three authentication modes (checked in order):
1. GETCONTACT_API_KEY — compact format "TOKEN|AES_KEY|DEVICE_ID"
2. GETCONTACT_TOKEN + AES_KEY + DEVICE_ID — rooted Android credentials
3. No credentials — demo mode with synthetic data

Tier: A (Platform API) — direct platform data, not leaked
"""

import base64
import binascii
import hashlib
import hmac
import json
import os
import logging
import re
import time
from typing import List, Optional, Dict, Any

import requests

from ..base_source import BaseSource, SourceResult, SourceTier, SourceType
from ...mock_data import _use_mock_apis, mock_getcontact, mock_numbuster

logger = logging.getLogger(__name__)

# GetContact HMAC signing key (extracted from decompiled APK, public knowledge)
_GC_HMAC_KEY = '2Wq7)qkX~cp7)H|n_tc&o+:G_USN3/-uIi~>M+c ;Oq]E{t9)RC_5|lhAA_Qq%_4'

# API endpoints
_GC_API_BASE = 'https://pbssrv-centralevents.com'
_GC_SEARCH_URL = f'{_GC_API_BASE}/v2.5/search'
_GC_DETAILS_URL = f'{_GC_API_BASE}/v2.5/number-detail'


class GetContactAPI:
    """
    Low-level GetContact API client.

    Handles AES-256-ECB encryption, HMAC-SHA256 request signing,
    and the encrypted request/response protocol.

    Requires: pycryptodome (Crypto.Cipher.AES) for encryption.
    Falls back gracefully if not installed.
    """

    def __init__(self, token: str, aes_key: str, device_id: str = '14130e29cebe9c39'):
        self.token = token
        self.aes_key = aes_key  # hex-encoded AES key
        self.device_id = device_id
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Dalvik/2.1.0 (Linux; U; Android 6.0; Google Build/MRA58K)',
            'Content-Type': 'application/json; charset=utf-8',
            'Accept-Encoding': 'deflate',
            'X-App-Version': '5.2.2',
            'X-Os': 'android 6.0',
            'X-Client-Device-Id': self.device_id,
            'X-Lang': 'en_US',
            'X-Encrypted': '1',
        })
        self._aes_available = self._check_aes()

    @staticmethod
    def _check_aes() -> bool:
        """Check if pycryptodome is available."""
        try:
            from Crypto.Cipher import AES  # noqa: F401
            return True
        except ImportError:
            logger.warning(
                "pycryptodome not installed — GetContact API encryption unavailable. "
                "Install with: pip install pycryptodome"
            )
            return False

    def _encrypt(self, plaintext: str) -> str:
        """AES-256-ECB encrypt and base64 encode."""
        from Crypto.Cipher import AES as _AES
        key_bytes = binascii.unhexlify(self.aes_key)
        # PKCS7 padding on raw bytes
        data = plaintext.encode('utf-8')
        pad_len = _AES.block_size - (len(data) % _AES.block_size)
        data += bytes([pad_len] * pad_len)
        cipher = _AES.new(key_bytes, _AES.MODE_ECB)
        encrypted = cipher.encrypt(data)
        return base64.b64encode(encrypted).decode('utf-8')

    def _decrypt(self, ciphertext: str) -> str:
        """Base64 decode and AES-256-ECB decrypt."""
        from Crypto.Cipher import AES as _AES
        key_bytes = binascii.unhexlify(self.aes_key)
        cipher = _AES.new(key_bytes, _AES.MODE_ECB)
        raw = base64.b64decode(ciphertext)
        decrypted = cipher.decrypt(raw)
        # Remove PKCS7 padding
        pad_len = decrypted[-1]
        if isinstance(pad_len, int) and 1 <= pad_len <= _AES.block_size:
            decrypted = decrypted[:-pad_len]
        return decrypted.decode('utf-8', errors='replace')

    def _sign_request(self, timestamp: str, payload_json: str) -> str:
        """Generate HMAC-SHA256 signature for the request."""
        message = f'{timestamp}-{payload_json}'
        sig = hmac.new(
            _GC_HMAC_KEY.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).digest()
        return base64.b64encode(sig).decode('utf-8')

    def _make_request(self, url: str, payload: dict) -> Optional[dict]:
        """
        Send encrypted request to GetContact API.

        Returns decrypted JSON response or None on error.
        """
        if not self._aes_available:
            logger.error("Cannot make GetContact API request: pycryptodome not installed")
            return None

        payload_json = json.dumps(payload, separators=(',', ':'))
        timestamp = str(int(time.time()))
        signature = self._sign_request(timestamp, payload_json)
        encrypted_data = self._encrypt(payload_json)

        headers = {
            'X-Token': self.token,
            'X-Req-Timestamp': timestamp,
            'X-Req-Signature': signature,
        }

        body = json.dumps({'data': encrypted_data})

        try:
            resp = self.session.post(
                url,
                data=body,
                headers=headers,
                timeout=15
            )

            if resp.status_code == 403:
                logger.warning("GetContact API rate limited (403) — CAPTCHA required")
                return None

            if resp.status_code != 200:
                logger.warning(f"GetContact API HTTP {resp.status_code}")
                return None

            resp_data = resp.json()

            # Check for meta errors
            meta = resp_data.get('meta', {})
            if meta.get('errorCode'):
                logger.warning(
                    f"GetContact API error: {meta.get('errorCode')} — "
                    f"{meta.get('errorMessage', 'unknown')}"
                )
                return None

            # Decrypt response data if encrypted
            encrypted_resp = resp_data.get('data')
            if encrypted_resp:
                decrypted = self._decrypt(encrypted_resp)
                # Clean up any trailing garbage after JSON
                decrypted = re.sub(r'}]}}.*$', '}]}}', decrypted)
                return json.loads(decrypted)

            # Some responses may not be encrypted
            return resp_data.get('result', resp_data)

        except json.JSONDecodeError as e:
            logger.error(f"GetContact API JSON decode error: {e}")
            return None
        except requests.RequestException as e:
            logger.error(f"GetContact API request error: {e}")
            return None
        except Exception as e:
            logger.error(f"GetContact API unexpected error: {e}")
            return None

    def search_phone(self, phone: str, country_code: str = 'RU') -> Optional[dict]:
        """
        Search for a phone number — returns display name and basic profile.

        Args:
            phone: Phone number in international format (e.g. +79161234567)
            country_code: ISO country code (default: RU)

        Returns:
            dict with 'profile' key containing displayName, countryCode, etc.
            or None on error.
        """
        payload = {
            'countryCode': country_code,
            'source': 'search',
            'token': self.token,
            'phoneNumber': phone,
        }
        return self._make_request(_GC_SEARCH_URL, payload)

    def get_tags(self, phone: str, country_code: str = 'RU') -> Optional[dict]:
        """
        Get contact tags for a phone number — returns how others saved this number.

        Args:
            phone: Phone number in international format
            country_code: ISO country code (default: RU)

        Returns:
            dict with 'tags' key containing list of tag objects,
            or None on error.
        """
        payload = {
            'countryCode': country_code,
            'source': 'details',
            'token': self.token,
            'phoneNumber': phone,
        }
        return self._make_request(_GC_DETAILS_URL, payload)


def _normalize_phone_for_gc(phone: str) -> str:
    """Normalize phone to +7XXXXXXXXXX format for GetContact API."""
    digits = re.sub(r'\D', '', phone)
    if len(digits) == 11 and digits.startswith('8'):
        digits = '7' + digits[1:]
    if len(digits) == 10:
        digits = '7' + digits
    if not digits.startswith('+'):
        return '+' + digits
    return phone


def _detect_country_code(phone: str) -> str:
    """Detect country code from phone prefix."""
    digits = re.sub(r'\D', '', phone)
    # Check multi-digit prefixes first (before single-digit '7')
    if digits.startswith('380'):
        return 'UA'
    if digits.startswith('375'):
        return 'BY'
    if digits.startswith('996'):
        return 'KG'
    # Kazakhstan uses +77XX (7 + 7XX area codes)
    if digits.startswith('77'):
        return 'KZ'
    if digits.startswith('7') or digits.startswith('8'):
        return 'RU'
    return 'RU'


class GetContactSource(BaseSource):
    """
    Reverse phone lookup via GetContact API.

    Returns how a phone number is saved in other people's contacts.
    Useful for confirming that a phone belongs to the target.

    Authentication modes:
    - GETCONTACT_API_KEY: Compact format "TOKEN|AES_KEY|DEVICE_ID" or "TOKEN|AES_KEY"
    - GETCONTACT_TOKEN + AES_KEY + DEVICE_ID: Rooted Android credentials (individual env vars)
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

    def _parse_api_key(self) -> Optional[tuple]:
        """
        Parse GETCONTACT_API_KEY into (token, aes_key, device_id).

        Supports formats:
        - "TOKEN|AES_KEY|DEVICE_ID"
        - "TOKEN|AES_KEY" (uses default device ID)
        """
        api_key = self._api_key
        if not api_key:
            return None

        parts = api_key.split('|')
        if len(parts) >= 2:
            token = parts[0].strip()
            aes_key = parts[1].strip()
            device_id = parts[2].strip() if len(parts) >= 3 else '14130e29cebe9c39'
            return (token, aes_key, device_id)

        return None

    def _get_credentials(self) -> Optional[tuple]:
        """Get credentials from any available source. Returns (token, aes_key, device_id) or None."""
        # Try compact API key first
        parsed = self._parse_api_key()
        if parsed:
            return parsed

        # Try individual env vars
        return self._legacy_credentials

    def _query_real_api(self, phone: str, token: str, aes_key: str, device_id: str) -> List[SourceResult]:
        """Query the real GetContact API and return results."""
        # Validate AES key is valid hex before attempting API calls
        try:
            binascii.unhexlify(aes_key)
        except (binascii.Error, ValueError):
            self.logger.error(
                f"GetContact AES key is not valid hex ({len(aes_key)} chars). "
                "Expected 64 hex characters (256-bit key). Check your credentials."
            )
            return []

        api = GetContactAPI(token=token, aes_key=aes_key, device_id=device_id)

        normalized_phone = _normalize_phone_for_gc(phone)
        country_code = _detect_country_code(phone)

        results = []

        # Step 1: Search for display name
        search_result = api.search_phone(normalized_phone, country_code)
        display_name = None
        remain_count = None

        if search_result:
            profile = search_result.get('result', {}).get('profile', {})
            if not profile:
                # Try flat structure
                profile = search_result.get('profile', {})
            display_name = profile.get('displayName')
            remain_count = search_result.get('result', {}).get('remainCount',
                           search_result.get('remainCount'))

            if remain_count is not None:
                self.logger.info(f"GetContact remaining requests: {remain_count}")

        # Step 2: Get tags (how number is saved in contacts)
        tags_result = api.get_tags(normalized_phone, country_code)
        tags = []

        if tags_result:
            tag_list = tags_result.get('result', {}).get('tags', [])
            if not tag_list:
                tag_list = tags_result.get('tags', [])
            for tag_obj in tag_list:
                tag_text = tag_obj.get('tag', '') if isinstance(tag_obj, dict) else str(tag_obj)
                if tag_text:
                    tags.append(tag_text)

        # Build results
        if display_name or tags:
            name_value = display_name or (tags[0] if tags else 'Unknown')
            results.append(SourceResult(
                data_type='name',
                value=name_value,
                source_name=self.name,
                source_tier=self.source_tier,
                confidence=0.85 if display_name else 0.75,
                metadata={
                    'phone': phone,
                    'display_name': display_name,
                    'tag_count': len(tags),
                    'tags': tags,
                    'country': country_code,
                    'remain_count': remain_count,
                },
            ))
        else:
            self.logger.info(f"GetContact: no results for {phone}")

        return results

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

        # Mode 1: API key (compact format) or Mode 2: Legacy credentials
        credentials = self._get_credentials()
        if credentials:
            token, aes_key, device_id = credentials
            source = 'API key' if self._api_key else 'legacy credentials'
            self.logger.info(
                f"GetContact REAL mode ({source}): querying phone={phone}"
            )
            return self._query_real_api(phone, token, aes_key, device_id or '14130e29cebe9c39')

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
