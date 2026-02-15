"""
Telethon One-Time Authentication Script
========================================
Run this ONCE to authenticate Telethon with your Telegram account.
After running, a session file is created in tg_session/ and the IBP app
can use Telethon for directory search without interactive prompts.

Prerequisites:
  1. Set TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_PHONE in .env
  2. Get API credentials from https://my.telegram.org/apps

Usage:
  python scripts/telethon_auth.py
"""

import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

api_id = os.environ.get('TELEGRAM_API_ID')
api_hash = os.environ.get('TELEGRAM_API_HASH')
phone = os.environ.get('TELEGRAM_PHONE')

if not all([api_id, api_hash, phone]):
    print("ERROR: Set TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_PHONE in .env")
    print()
    print("Get your API credentials at https://my.telegram.org/apps")
    sys.exit(1)

from telethon.sync import TelegramClient

session_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tg_session')
os.makedirs(session_dir, exist_ok=True)
session_path = os.path.join(session_dir, 'ibp_session')

print(f"Connecting to Telegram API (api_id={api_id})...")
print(f"Session will be saved to: {session_path}")
print()

with TelegramClient(session_path, int(api_id), api_hash) as client:
    if not client.is_user_authorized():
        client.send_code_request(phone)
        code = input('Enter the code you received on Telegram: ')
        try:
            client.sign_in(phone, code)
        except Exception as e:
            if 'Two-steps verification' in str(e) or 'password' in str(e).lower():
                password = input('Enter your 2FA password: ')
                client.sign_in(password=password)
            else:
                raise

    me = client.get_me()
    print()
    print(f"Authenticated as: {me.first_name} {me.last_name or ''} (@{me.username or 'no username'})")
    print(f"Session saved to: {session_path}")
    print()
    print("You can now use Telethon directory search in IBP (Method C).")
    print("Restart the IBP server for the change to take effect.")
