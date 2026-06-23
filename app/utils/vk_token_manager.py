"""
VK Token Manager
================
Manages VK OAuth token lifecycle: validation, save, refresh URL generation.

Dual-token architecture:
  VK_SERVICE_TOKEN — permanent app token for search (users.search, users.get)
  VK_USER_TOKEN    — user OAuth token for private data (wall.get, friends.get,
                     photos.getAll, market.get). Requires explicit scopes:
                     friends, photos, wall, groups, offline.
  VK_TOKEN         — legacy fallback (treated as user token if VK_USER_TOKEN unset)

Helper: get_vk_token(method_type) returns the right token for each use case.
"""

import os
import re
import time
import threading
import logging
import requests
from app.utils.logger import mask_token

logger = logging.getLogger('ibp.vk_token')

# Cache for get_token_status().  The /api/vk/token-status endpoint is polled
# by every open admin browser tab on page load and then every 5 minutes.
# Without the cache each call makes a live round-trip to api.vk.com (~800ms).
# TTL is short enough that a newly-invalidated token is detected within 30s.
_CACHE_TTL = 30  # seconds
_cache_lock = threading.Lock()
_cached_status: dict | None = None
_cache_expires: float = 0.0


def _fetch_token_status() -> dict:
    """Make the live VK API call and return a status dict.  No caching here."""
    token = os.environ.get('VK_SERVICE_TOKEN') or os.environ.get('VK_TOKEN')
    if not token:
        return {
            'valid': False,
            'expires_in_seconds': None,
            'error': 'No VK token configured',
            'token_set': False,
        }
    try:
        resp = requests.get(
            'https://api.vk.com/method/users.get',
            params={'user_ids': '1', 'access_token': token, 'v': '5.199'},
            timeout=5,
        )
        data = resp.json()
        if 'error' in data:
            error_code = data['error'].get('error_code', 0)
            error_msg  = data['error'].get('error_msg', 'Unknown')
            return {
                'valid': False,
                'expires_in_seconds': 0,
                'error': f'{error_msg} (code {error_code})',
                'token_set': True,
            }
        return {
            'valid': True,
            'expires_in_seconds': None,  # user tokens don't report expiry
            'error': None,
            'token_set': True,
        }
    except requests.Timeout:
        return {
            'valid': None,
            'expires_in_seconds': None,
            'error': 'VK API timeout',
            'token_set': True,
        }
    except Exception as e:
        return {
            'valid': None,
            'expires_in_seconds': None,
            'error': str(e),
            'token_set': True,
        }


def get_token_status() -> dict:
    """Get current VK token status, served from a short-lived cache.

    Returns dict with:
        valid: bool | None  (None = timeout / unknown)
        expires_in_seconds: int | None
        error: str | None
        token_set: bool

    Cache is invalidated by save_token() so a freshly-saved token is always
    verified against VK before being reported as valid.
    """
    global _cached_status, _cache_expires

    # Fast path: check under lock so we never read a half-written pair.
    with _cache_lock:
        if _cached_status is not None and time.time() < _cache_expires:
            return _cached_status

    # Cache miss — call VK API WITHOUT holding the lock so we don't block
    # other threads for ~800ms.  In the worst case a handful of concurrent
    # callers all reach here simultaneously (thundering herd), but this
    # endpoint is admin-only so at most a few tabs ever call it at once.
    result = _fetch_token_status()

    with _cache_lock:
        _cached_status = result
        _cache_expires = time.time() + _CACHE_TTL

    return result


def _sanitize_token(raw: str) -> str:
    """Sanitize and validate a raw VK token string.

    Strips whitespace and injection characters, then validates the character set.
    Returns the cleaned token if valid, or an empty string if it fails validation.
    """
    token = raw.replace('\n', '').replace('\r', '').replace('\0', '').strip()
    if not re.match(r'^[a-zA-Z0-9._\-]+$', token):
        return ''
    return token


def save_token(token):
    """Save token to .env file (update VK_TOKEN line, keep other lines)."""
    global _cached_status, _cache_expires

    token = _sanitize_token(token)
    if not token:
        logger.warning("Rejected VK token with unexpected characters")
        return

    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '..', '.env')

    lines = []
    token_found = False
    if os.path.exists(env_path):
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip().startswith('VK_TOKEN=') or line.strip().startswith('VK_SERVICE_TOKEN='):
                    if not token_found:
                        lines.append(f'VK_TOKEN={token}\n')
                        token_found = True
                    # Skip duplicate token lines
                else:
                    lines.append(line)

    if not token_found:
        lines.append(f'VK_TOKEN={token}\n')

    with open(env_path, 'w', encoding='utf-8') as f:
        f.writelines(lines)

    # Update environment variable in current process
    os.environ['VK_TOKEN'] = token
    os.environ['VK_SERVICE_TOKEN'] = token

    # Invalidate the status cache.  The caller (vk_save_token route) calls
    # get_token_status() immediately after this to verify the new token, so
    # the next call must hit VK API with the updated token, not the old cache.
    with _cache_lock:
        _cached_status = None
        _cache_expires = 0.0

    logger.info(f"VK token saved: {mask_token(token)}")


def get_oauth_url():
    """Get the VK OAuth URL for token acquisition."""
    app_id = os.environ.get('VK_APP_ID', '')
    if not app_id:
        return None, 'VK_APP_ID not set in .env. Create an app at https://vk.com/apps?act=manage'
    return (
        f'https://oauth.vk.com/authorize'
        f'?client_id={app_id}'
        f'&redirect_uri=https://oauth.vk.com/blank.html'
        f'&scope=friends,photos,wall,groups,offline'
        f'&response_type=token'
        f'&v=5.199'
    ), None


def get_vk_user_token() -> str:
    """Get VK user token for private-data API methods.

    Priority: VK_USER_TOKEN → VK_TOKEN → None
    These methods require user OAuth token with explicit scopes:
      wall.get, friends.get, photos.getAll, photos.getComments,
      wall.getComments, newsfeed.getMentions, market.get
    """
    return (
        os.environ.get('VK_USER_TOKEN', '').strip()
        or os.environ.get('VK_TOKEN', '').strip()
        or None
    )


def get_vk_service_token() -> str:
    """Get VK service token for public API methods.

    Priority: VK_SERVICE_TOKEN → VK_USER_TOKEN → VK_TOKEN → None
    These methods work with service tokens:
      users.search, users.get, newsfeed.search, utils.resolveScreenName
    """
    return (
        os.environ.get('VK_SERVICE_TOKEN', '').strip()
        or os.environ.get('VK_USER_TOKEN', '').strip()
        or os.environ.get('VK_TOKEN', '').strip()
        or None
    )


def get_vk_token(method_type: str = 'search') -> str:
    """Get the right VK token for a given method type.

    Args:
        method_type: 'search' for public methods, 'private' for user-data methods

    Returns:
        Token string or None if unavailable
    """
    if method_type == 'private':
        return get_vk_user_token()
    return get_vk_service_token()
