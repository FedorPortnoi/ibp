"""
Telegram session authentication for IBP.

Run this ONCE to authenticate Telethon with your Telegram account.
After running, a session file is created at tg_session/ibp_session.session
and the app can use Telethon without interactive prompts.

Usage:
    python scripts/auth_telegram.py          # Interactive auth
    python scripts/auth_telegram.py --check  # Validate existing session
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()


def get_session_path():
    session_dir = os.path.join(os.path.dirname(__file__), '..', 'tg_session')
    os.makedirs(session_dir, exist_ok=True)
    return os.path.join(session_dir, 'ibp_session')


def check_session():
    """Validate existing Telethon session without triggering auth."""
    from telethon.sync import TelegramClient

    api_id = int(os.environ['TELEGRAM_API_ID'])
    api_hash = os.environ['TELEGRAM_API_HASH']
    session_path = get_session_path()

    session_file = session_path + '.session'
    if not os.path.exists(session_file):
        print(f"Session file not found: {session_file}")
        print("Run without --check to authenticate.")
        return False

    with TelegramClient(session_path, api_id, api_hash) as client:
        if client.is_user_authorized():
            me = client.get_me()
            print(f"Session valid: {me.first_name} {me.last_name or ''} (@{me.username or 'no username'})")
            print(f"Phone: {me.phone}")
            print(f"Session file: {session_file}")
            return True
        else:
            print("Session exists but is not authorized.")
            print("Run without --check to re-authenticate.")
            return False


def authenticate():
    """Interactive Telethon authentication."""
    from telethon.sync import TelegramClient

    api_id = int(os.environ['TELEGRAM_API_ID'])
    api_hash = os.environ['TELEGRAM_API_HASH']
    phone = os.environ['TELEGRAM_PHONE']
    session_path = get_session_path()

    print(f"Telegram API ID: {api_id}")
    print(f"Phone: {phone}")
    print(f"Session path: {session_path}")
    print()

    with TelegramClient(session_path, api_id, api_hash) as client:
        if not client.is_user_authorized():
            client.send_code_request(phone)
            code = input('Enter the code you received on Telegram: ')
            try:
                client.sign_in(phone, code)
            except Exception as e:
                if 'Two-steps verification' in str(e) or 'password' in str(e).lower():
                    password = input('Two-factor authentication enabled. Enter your password: ')
                    client.sign_in(password=password)
                else:
                    raise

        me = client.get_me()
        print()
        print(f"Authenticated as: {me.first_name} {me.last_name or ''} (@{me.username or 'no username'})")
        print(f"Session saved to: {session_path}.session")


if __name__ == '__main__':
    required = ['TELEGRAM_API_ID', 'TELEGRAM_API_HASH', 'TELEGRAM_PHONE']
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        print(f"Missing environment variables: {', '.join(missing)}")
        print("Set them in .env file and try again.")
        sys.exit(1)

    if '--check' in sys.argv:
        ok = check_session()
        sys.exit(0 if ok else 1)
    else:
        authenticate()
