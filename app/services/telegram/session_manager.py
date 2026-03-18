"""
Telegram Session Manager
=========================
Manages Telethon client lifecycle as a singleton.

The client authenticates once (interactive code entry on first run),
then persists the session to disk. Subsequent runs reuse the session
without re-authentication.

Usage:
    from app.services.telegram.session_manager import TelegramSessionManager

    # Check if configured
    if TelegramSessionManager.is_configured():
        client = await TelegramSessionManager.get_client()
        # Use client to query bots...
        # Client stays alive for the app lifecycle

    # On app shutdown:
    await TelegramSessionManager.disconnect()
"""

import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class TelegramSessionManager:
    """
    Manages Telethon client for querying Telegram bots.

    Singleton pattern — only one client instance exists.
    Thread-safe through asyncio locks.
    """

    _client = None
    _lock = asyncio.Lock() if hasattr(asyncio, 'Lock') else None
    _connected = False

    @classmethod
    def is_configured(cls) -> bool:
        """Check if Telegram credentials are in environment."""
        try:
            from . import config
            return config.is_configured()
        except Exception as e:
            logger.debug(f"[TelegramSession] Config check failed: {e}")
            return False

    @classmethod
    async def get_client(cls):
        """
        Get or create Telethon client.

        On first call, creates the client and connects.
        If not yet authorized, will need interactive auth (code from Telegram).
        Subsequent calls return the existing connected client.

        Returns:
            TelegramClient instance (connected and authorized)

        Raises:
            ImportError: If telethon is not installed
            RuntimeError: If not configured or auth fails
        """
        if cls._client is not None and cls._connected:
            return cls._client

        # Lazy lock creation for async context
        if cls._lock is None:
            cls._lock = asyncio.Lock()

        async with cls._lock:
            # Double-check after acquiring lock
            if cls._client is not None and cls._connected:
                return cls._client

            if not cls.is_configured():
                raise RuntimeError(
                    "Telegram not configured. Set TELEGRAM_API_ID, "
                    "TELEGRAM_API_HASH, and TELEGRAM_PHONE environment variables."
                )

            try:
                from telethon import TelegramClient
                from . import config

                cfg = config.get_config()

                cls._client = TelegramClient(
                    cfg['session_path'],
                    cfg['api_id'],
                    cfg['api_hash'],
                    # Connection settings for reliability
                    connection_retries=3,
                    retry_delay=1,
                    timeout=30,
                    request_retries=3,
                )

                await cls._client.connect()

                # Check if already authorized
                if not await cls._client.is_user_authorized():
                    # Send code request
                    await cls._client.send_code_request(cfg['phone'])
                    logger.warning(
                        "Telegram authorization required. "
                        "Use the /api/telegram/auth endpoint to complete."
                    )
                    # Don't mark as connected — needs auth completion
                    return cls._client

                cls._connected = True
                me = await cls._client.get_me()
                logger.info(
                    f"Telegram connected as: {me.first_name} "
                    f"(@{me.username or 'no username'})"
                )
                return cls._client

            except ImportError:
                logger.error(
                    "Telethon not installed. Run: pip install telethon"
                )
                raise
            except Exception as e:
                logger.error(f"Telegram connection error: {e}")
                cls._client = None
                cls._connected = False
                raise

    @classmethod
    async def complete_auth(cls, code: str, password: Optional[str] = None):
        """
        Complete Telegram authentication with the code sent to the phone.

        Args:
            code: The verification code received via Telegram
            password: 2FA password if enabled (optional)

        Returns:
            True if authentication was successful
        """
        if cls._client is None:
            raise RuntimeError("Call get_client() first to initiate auth")

        try:
            from . import config
            cfg = config.get_config()

            await cls._client.sign_in(cfg['phone'], code)

            if password:
                await cls._client.sign_in(password=password)

            cls._connected = True
            me = await cls._client.get_me()
            logger.info(f"Telegram authenticated as: {me.first_name}")
            return True

        except Exception as e:
            logger.error(f"Telegram auth error: {e}")
            return False

    @classmethod
    async def ensure_connected(cls) -> bool:
        """Check if client is connected and authorized."""
        if cls._client is None:
            return False

        try:
            if not cls._client.is_connected():
                return False
            return await cls._client.is_user_authorized()
        except Exception as e:
            logger.debug(f"[TelegramSession] Auth check failed: {e}")
            return False

    @classmethod
    async def disconnect(cls):
        """Clean disconnect. Call on app shutdown."""
        if cls._client is not None:
            try:
                await cls._client.disconnect()
                logger.info("Telegram client disconnected")
            except Exception as e:
                logger.warning(f"Telegram disconnect error: {e}")
            finally:
                cls._client = None
                cls._connected = False

    @classmethod
    def get_status(cls) -> dict:
        """
        Get current connection status.
        Safe to call synchronously (doesn't use await).
        """
        return {
            'configured': cls.is_configured(),
            'client_exists': cls._client is not None,
            'connected': cls._connected,
        }

    @classmethod
    def check_session_health(cls) -> dict:
        """
        Check if the Telegram session file exists and is valid.
        Safe to call synchronously at startup. Does NOT create a client.

        Returns:
            {'valid': bool, 'message': str, 'session_path': str}
        """
        if not cls.is_configured():
            return {
                'valid': False,
                'message': 'Telegram not configured (TELEGRAM_API_ID/HASH/PHONE not set)',
                'session_path': None,
            }

        try:
            from . import config
            cfg = config.get_config()
            session_path = cfg['session_path']
            session_file = session_path + '.session'

            import os
            if not os.path.exists(session_file):
                return {
                    'valid': False,
                    'message': (
                        f'Telegram session file not found: {session_file}\n'
                        'Run: python scripts/auth_telegram.py'
                    ),
                    'session_path': session_file,
                }

            # Check file size — empty or corrupt files are < 100 bytes
            file_size = os.path.getsize(session_file)
            if file_size < 100:
                return {
                    'valid': False,
                    'message': (
                        f'Telegram session file appears corrupt ({file_size} bytes)\n'
                        'Run: python scripts/auth_telegram.py'
                    ),
                    'session_path': session_file,
                }

            return {
                'valid': True,
                'message': f'Session file exists ({file_size} bytes)',
                'session_path': session_file,
            }
        except Exception as e:
            return {
                'valid': False,
                'message': f'Session check error: {e}',
                'session_path': None,
            }
