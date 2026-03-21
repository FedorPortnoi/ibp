"""
Telegram Bot Automation Service
================================
Manages Telethon client sessions for programmatically querying
Telegram OSINT bots (Himera Search, Leak OSINT, etc.).

Setup:
1. Get API credentials from https://my.telegram.org/apps
2. Set environment variables:
   TELEGRAM_API_ID=12345
   TELEGRAM_API_HASH=abcdef1234567890
   TELEGRAM_PHONE=+79001234567
3. On first run, authenticate interactively (enter code from Telegram)
4. Session is persisted to disk for future use

Components:
- config.py — Loads credentials from environment
- session_manager.py — Manages Telethon client lifecycle (singleton)
- bot_query.py — Send messages to bots, parse responses
"""
