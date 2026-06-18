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
import logging
import requests
from app.utils.logger import mask_token

logger = logging.getLogger('ibp.vk_token')


def get_token_status():
    """Get current VK token status.

    Returns dict with:
        valid: bool
        expires_in_seconds: int or None
        error: str or None
        token_set: bool
    """
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
            timeout=5
        )
        data = resp.json()
        if 'error' in data:
            error_code = data['error'].get('error_code', 0)
            error_msg = data['error'].get('error_msg', 'Unknown')
            return {
                'valid': False,
                'expires_in_seconds': 0,
                'error': f'{error_msg} (code {error_code})',
                'token_set': True,
            }
        return {
            'valid': True,
            'expires_in_seconds': None,  # User tokens don't report expiry
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
