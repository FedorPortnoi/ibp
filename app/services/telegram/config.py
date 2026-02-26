"""
Telegram Configuration
======================
Loads Telegram API credentials from environment variables.

To get credentials:
1. Go to https://my.telegram.org/apps
2. Create a new application
3. Copy API ID and API Hash
4. Set them as environment variables

Required env vars:
  TELEGRAM_API_ID      — Numeric API ID from my.telegram.org
  TELEGRAM_API_HASH    — API hash string from my.telegram.org
  TELEGRAM_PHONE       — Phone number for the Telegram account (+79001234567)

Optional env vars:
  TELEGRAM_SESSION_PATH — Where to store the .session file
                          Default: app/services/telegram/ibp_session
"""

import os
import logging

logger = logging.getLogger(__name__)

# Base directory for session files — unified to tg_session/ at project root
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
_SESSION_DIR = os.path.join(_PROJECT_ROOT, 'tg_session')

# Configuration values (loaded from environment)
API_ID = os.environ.get('TELEGRAM_API_ID', '')
API_HASH = os.environ.get('TELEGRAM_API_HASH', '')
PHONE = os.environ.get('TELEGRAM_PHONE', '')
SESSION_PATH = os.environ.get(
    'TELEGRAM_SESSION_PATH',
    os.path.join(_SESSION_DIR, 'ibp_session')
)


def is_configured() -> bool:
    """
    Check if Telegram credentials are set in environment.

    Returns True only if API_ID, API_HASH, and PHONE are all present.
    """
    configured = bool(API_ID and API_HASH and PHONE)
    if not configured:
        logger.debug(
            "Telegram not configured. Set TELEGRAM_API_ID, "
            "TELEGRAM_API_HASH, and TELEGRAM_PHONE env vars."
        )
    return configured


def get_config() -> dict:
    """Return Telegram configuration as a dict."""
    return {
        'api_id': int(API_ID) if API_ID.isdigit() else 0,
        'api_hash': API_HASH,
        'phone': PHONE,
        'session_path': SESSION_PATH,
        'configured': is_configured(),
    }
