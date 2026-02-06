"""
Telegram Bot Query Handler
===========================
Generic functions for querying Telegram bots and parsing their responses.

Supports:
- Sending text messages to bots
- Handling inline keyboard buttons
- Parsing structured bot responses (key: value, emoji-prefixed, tables)
- Timeout handling for slow bots
- Rate limiting to avoid bans

Usage:
    from app.services.telegram.bot_query import TelegramBotQuery

    query = TelegramBotQuery()
    response = await query.query_bot("@HimeraSearchBot", "+79001234567")
    parsed = query.parse_structured_response(response)
    # parsed = {"ФИО": "Иванов Иван Иванович", "Адрес": "г. Москва, ..."}
"""

import asyncio
import logging
import re
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)


class TelegramBotQuery:
    """
    Generic Telegram bot query handler.

    Sends messages to OSINT bots via Telethon client and
    parses their structured text responses.
    """

    # Default delay between queries (seconds) to avoid rate limits
    DEFAULT_DELAY = 2.0

    # Max response wait time (seconds)
    DEFAULT_TIMEOUT = 30

    async def query_bot(
        self,
        bot_username: str,
        message: str,
        timeout: int = DEFAULT_TIMEOUT
    ) -> Optional[str]:
        """
        Send a message to a bot and wait for its text response.

        Args:
            bot_username: Bot's Telegram username (e.g., "@HimeraSearchBot")
            message: The query to send (phone number, name, etc.)
            timeout: Max seconds to wait for response

        Returns:
            The bot's text response, or None on timeout/error.
        """
        try:
            from .session_manager import TelegramSessionManager

            client = await TelegramSessionManager.get_client()
            if not client:
                logger.error("No Telegram client available")
                return None

            # Normalize bot username
            bot_username = bot_username.lstrip('@')

            # Send the query
            await client.send_message(bot_username, message)
            logger.debug(f"Sent to @{bot_username}: {message[:50]}...")

            # Wait for response with timeout
            response_text = await asyncio.wait_for(
                self._wait_for_response(client, bot_username),
                timeout=timeout
            )

            if response_text:
                logger.debug(
                    f"Response from @{bot_username}: "
                    f"{response_text[:100]}..."
                )

            return response_text

        except asyncio.TimeoutError:
            logger.warning(f"Timeout waiting for @{bot_username} response")
            return None
        except ImportError:
            logger.error("Telethon not installed")
            return None
        except Exception as e:
            logger.error(f"Bot query error for @{bot_username}: {e}")
            return None

    async def _wait_for_response(self, client, bot_username: str) -> Optional[str]:
        """
        Wait for the next message from a specific bot.

        Polls for new messages every 0.5 seconds.
        """
        from telethon import events

        response = None
        event_received = asyncio.Event()

        @client.on(events.NewMessage(from_users=bot_username))
        async def handler(event):
            nonlocal response
            response = event.message.text
            event_received.set()

        try:
            await event_received.wait()
        finally:
            client.remove_event_handler(handler)

        return response

    async def query_bot_with_buttons(
        self,
        bot_username: str,
        message: str,
        button_text: Optional[str] = None,
        button_index: Optional[int] = None,
        timeout: int = DEFAULT_TIMEOUT
    ) -> Optional[str]:
        """
        Send message to bot, optionally click an inline button, get response.

        Some bots reply with inline keyboards (e.g., "Select search type").
        This method handles clicking the appropriate button.

        Args:
            bot_username: Bot username
            message: Initial query
            button_text: Text of the button to click (if any)
            button_index: Index of button to click (alternative to text)
            timeout: Max wait time

        Returns:
            Final bot response after button interaction, or None.
        """
        try:
            from .session_manager import TelegramSessionManager

            client = await TelegramSessionManager.get_client()
            if not client:
                return None

            bot_username = bot_username.lstrip('@')

            # Send initial message
            await client.send_message(bot_username, message)

            # Wait for response with buttons
            response_msg = None
            event_received = asyncio.Event()

            from telethon import events

            @client.on(events.NewMessage(from_users=bot_username))
            async def handler(event):
                nonlocal response_msg
                response_msg = event.message
                event_received.set()

            try:
                await asyncio.wait_for(event_received.wait(), timeout=timeout)
            finally:
                client.remove_event_handler(handler)

            if not response_msg:
                return None

            # Check if response has inline buttons
            if response_msg.buttons and (button_text or button_index is not None):
                target_button = None

                if button_text:
                    # Find button by text
                    for row in response_msg.buttons:
                        for btn in row:
                            if button_text.lower() in btn.text.lower():
                                target_button = btn
                                break
                        if target_button:
                            break

                elif button_index is not None:
                    # Find button by flat index
                    flat_buttons = [
                        btn for row in response_msg.buttons for btn in row
                    ]
                    if 0 <= button_index < len(flat_buttons):
                        target_button = flat_buttons[button_index]

                if target_button:
                    # Click the button
                    await target_button.click()

                    # Wait for updated response
                    event_received.clear()
                    response_msg = None

                    @client.on(events.NewMessage(from_users=bot_username))
                    async def handler2(event):
                        nonlocal response_msg
                        response_msg = event.message
                        event_received.set()

                    try:
                        await asyncio.wait_for(
                            event_received.wait(), timeout=timeout
                        )
                    finally:
                        client.remove_event_handler(handler2)

                    if response_msg:
                        return response_msg.text

            return response_msg.text if response_msg else None

        except asyncio.TimeoutError:
            return None
        except Exception as e:
            logger.error(f"Bot button query error: {e}")
            return None

    def parse_structured_response(self, text: str) -> Dict[str, Any]:
        """
        Parse common bot response formats into a structured dict.

        Handles multiple common formats:
        1. Key: Value lines (most common)
        2. Emoji-prefixed data (📱 +7...)
        3. Bracket-prefixed ([ФИО] Иванов Иван)

        Args:
            text: Raw bot response text

        Returns:
            Dict mapping field names to values.
            Common keys: "fio", "phone", "email", "address",
                        "passport", "inn", "snils", "car_plate"
        """
        if not text:
            return {}

        result = {}
        lines = text.strip().split('\n')

        # Emoji-to-field mapping
        emoji_map = {
            '👤': 'fio',
            '📱': 'phone',
            '📞': 'phone',
            '📧': 'email',
            '✉': 'email',
            '🏠': 'address',
            '📍': 'address',
            '🏢': 'address',
            '📄': 'passport',
            '🪪': 'passport',
            '💳': 'inn',
            '🚗': 'car_plate',
            '🚘': 'car_plate',
            '👨‍👩‍👧': 'relatives',
            '👪': 'relatives',
            '🎂': 'dob',
            '📅': 'dob',
            '💼': 'employer',
            '🏦': 'bank',
        }

        # Russian field name mapping
        field_map = {
            'фио': 'fio',
            'имя': 'fio',
            'полное имя': 'fio',
            'телефон': 'phone',
            'номер': 'phone',
            'мобильный': 'phone',
            'email': 'email',
            'почта': 'email',
            'e-mail': 'email',
            'адрес': 'address',
            'адрес регистрации': 'registration_address',
            'адрес проживания': 'address',
            'паспорт': 'passport',
            'серия и номер': 'passport',
            'инн': 'inn',
            'снилс': 'snils',
            'авто': 'car_plate',
            'госномер': 'car_plate',
            'vin': 'vin',
            'дата рождения': 'dob',
            'год рождения': 'dob',
            'место работы': 'employer',
            'работа': 'employer',
            'родственники': 'relatives',
            'вк': 'vk_url',
            'vk': 'vk_url',
            'telegram': 'telegram',
            'ok': 'ok_url',
            'одноклассники': 'ok_url',
        }

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Method 1: Emoji prefix
            for emoji, field_name in emoji_map.items():
                if line.startswith(emoji):
                    value = line[len(emoji):].strip().lstrip(':').strip()
                    if value:
                        if field_name in result and isinstance(result[field_name], list):
                            result[field_name].append(value)
                        elif field_name in result:
                            result[field_name] = [result[field_name], value]
                        else:
                            result[field_name] = value
                    break
            else:
                # Method 2: Key: Value format
                colon_match = re.match(r'^([^:]{2,30}):\s*(.+)$', line)
                if colon_match:
                    key_raw = colon_match.group(1).strip().lower()
                    value = colon_match.group(2).strip()

                    field_name = field_map.get(key_raw, key_raw.replace(' ', '_'))
                    if value:
                        result[field_name] = value
                    continue

                # Method 3: Bracket prefix [Field] Value
                bracket_match = re.match(r'^\[([^\]]+)\]\s*(.+)$', line)
                if bracket_match:
                    key_raw = bracket_match.group(1).strip().lower()
                    value = bracket_match.group(2).strip()
                    field_name = field_map.get(key_raw, key_raw.replace(' ', '_'))
                    if value:
                        result[field_name] = value

        return result

    def extract_phones_from_response(self, text: str) -> List[str]:
        """Extract all phone numbers from a bot response."""
        if not text:
            return []
        pattern = r'\+?[78][\s\-\(]?\d{3}[\s\-\)]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}'
        return re.findall(pattern, text)

    def extract_emails_from_response(self, text: str) -> List[str]:
        """Extract all email addresses from a bot response."""
        if not text:
            return []
        pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        return re.findall(pattern, text, re.IGNORECASE)
