"""
Telegram Authentication & Session Management
=============================================
Standalone script for Telethon authentication. Handles:
  1. New authentication (interactive code entry)
  2. Session validation (check if existing session is still valid)
  3. Re-authentication (if session expired)

Prerequisites:
  1. Set TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_PHONE in .env
  2. Get API credentials from https://my.telegram.org/apps

Usage:
  python scripts/auth_telegram.py           # Authenticate or validate
  python scripts/auth_telegram.py --check   # Only check session validity
"""

import os
import sys
import argparse

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, '.env'))

# Session file lives in tg_session/ at project root
SESSION_DIR = os.path.join(PROJECT_ROOT, 'tg_session')
SESSION_PATH = os.path.join(SESSION_DIR, 'ibp_session')


def get_credentials():
    """Load and validate Telegram credentials from environment."""
    api_id = os.environ.get('TELEGRAM_API_ID', '').strip()
    api_hash = os.environ.get('TELEGRAM_API_HASH', '').strip()
    phone = os.environ.get('TELEGRAM_PHONE', '').strip()

    if not all([api_id, api_hash, phone]):
        print("ERROR: Telegram credentials not configured.")
        print()
        print("Set these in your .env file:")
        print("  TELEGRAM_API_ID=<numeric_id>")
        print("  TELEGRAM_API_HASH=<hash_string>")
        print("  TELEGRAM_PHONE=+79001234567")
        print()
        print("Get credentials at: https://my.telegram.org/apps")
        return None

    if not api_id.isdigit():
        print(f"ERROR: TELEGRAM_API_ID must be numeric, got: {api_id}")
        return None

    return {'api_id': int(api_id), 'api_hash': api_hash, 'phone': phone}


def check_session(creds):
    """Check if existing session is valid. Returns True if authenticated."""
    session_file = SESSION_PATH + '.session'
    if not os.path.exists(session_file):
        print(f"No session file found at: {session_file}")
        return False

    try:
        from telethon.sync import TelegramClient
        client = TelegramClient(SESSION_PATH, creds['api_id'], creds['api_hash'])
        client.connect()

        if client.is_user_authorized():
            me = client.get_me()
            name = f"{me.first_name} {me.last_name or ''}".strip()
            username = f"@{me.username}" if me.username else "no username"
            print(f"Session VALID: {name} ({username})")
            print(f"  Phone: {me.phone}")
            print(f"  User ID: {me.id}")
            client.disconnect()
            return True
        else:
            print("Session EXPIRED: authorization no longer valid.")
            client.disconnect()
            return False

    except Exception as e:
        print(f"Session CHECK FAILED: {e}")
        return False


def authenticate(creds):
    """Run interactive authentication flow."""
    os.makedirs(SESSION_DIR, exist_ok=True)

    print(f"Connecting to Telegram API (api_id={creds['api_id']})...")
    print(f"Session file: {SESSION_PATH}.session")
    print()

    from telethon.sync import TelegramClient
    client = TelegramClient(
        SESSION_PATH,
        creds['api_id'],
        creds['api_hash'],
        connection_retries=3,
        retry_delay=2,
        timeout=30,
    )
    client.connect()

    if client.is_user_authorized():
        me = client.get_me()
        name = f"{me.first_name} {me.last_name or ''}".strip()
        print(f"Already authenticated as: {name} (@{me.username or 'no username'})")
        print("Session is valid, no action needed.")
        client.disconnect()
        return True

    # Need to authenticate
    print(f"Sending verification code to {creds['phone']}...")
    try:
        client.send_code_request(creds['phone'])
    except Exception as e:
        print(f"ERROR sending code: {e}")
        client.disconnect()
        return False

    print()
    code = input('Enter the code you received on Telegram: ').strip()
    if not code:
        print("No code entered. Aborting.")
        client.disconnect()
        return False

    try:
        client.sign_in(creds['phone'], code)
    except Exception as e:
        err_str = str(e).lower()
        if 'two-steps verification' in err_str or 'password' in err_str or '2fa' in err_str:
            print()
            password = input('Enter your 2FA password: ').strip()
            if not password:
                print("No password entered. Aborting.")
                client.disconnect()
                return False
            try:
                client.sign_in(password=password)
            except Exception as e2:
                print(f"ERROR during 2FA: {e2}")
                client.disconnect()
                return False
        else:
            print(f"ERROR during sign-in: {e}")
            client.disconnect()
            return False

    me = client.get_me()
    name = f"{me.first_name} {me.last_name or ''}".strip()
    print()
    print(f"Authenticated as: {name} (@{me.username or 'no username'})")
    print(f"Session saved to: {SESSION_PATH}.session")
    print()
    print("IBP can now use Telethon for Telegram directory search (Method C).")
    print("Restart the IBP server for the change to take effect.")

    client.disconnect()
    return True


def main():
    parser = argparse.ArgumentParser(description='Telegram authentication for IBP')
    parser.add_argument('--check', action='store_true',
                        help='Only check session validity (no interactive auth)')
    args = parser.parse_args()

    creds = get_credentials()
    if not creds:
        sys.exit(1)

    if args.check:
        valid = check_session(creds)
        sys.exit(0 if valid else 1)
    else:
        # First check existing session
        print("Checking existing session...")
        if check_session(creds):
            print()
            print("Session is still valid. No re-authentication needed.")
            sys.exit(0)

        print()
        print("Session needs (re-)authentication.")
        print()

        success = authenticate(creds)
        sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
