"""
VK OAuth Token Acquisition Script
===================================
Obtains a VK user token via OAuth Implicit Flow.

The user token grants access to private-data API methods:
  wall.get, friends.get, photos.getAll, market.get

Uses VK official Android app client_id (2685278) for OAuth implicit flow.
Scopes requested: wall, photos, offline

Flow:
  1. Opens VK OAuth URL in your browser
  2. You log in and grant permissions
  3. VK redirects to blank.html with token in URL fragment
  4. You paste the redirect URL back here
  5. Script extracts token and saves to .env as VK_USER_TOKEN

Usage:
  python scripts/auth_vk.py
  python scripts/auth_vk.py --check    # only check existing token
"""

import os
import sys
import re
import argparse

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, '.env'))


def check_token():
    """Check if VK_USER_TOKEN is set and valid."""
    token = os.environ.get('VK_USER_TOKEN', '').strip()
    if not token:
        token = os.environ.get('VK_TOKEN', '').strip()
    if not token:
        print("VK user token: NOT SET")
        print("  Run: python scripts/auth_vk.py")
        return False

    import requests
    try:
        resp = requests.get(
            'https://api.vk.com/method/users.get',
            params={'access_token': token, 'v': '5.199'},
            timeout=5
        )
        data = resp.json()
        if 'error' in data:
            error_msg = data['error'].get('error_msg', 'Unknown')
            print(f"VK user token: INVALID -- {error_msg}")
            print(f"  Token: {token[:8]}...{token[-4:]}")
            return False

        user = data['response'][0]
        name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
        print(f"VK user token: VALID")
        print(f"  Authenticated as: {name} (id{user['id']})")
        print(f"  Token: {token[:8]}...{token[-4:]}")

        # Test private methods
        print()
        print("Testing private API methods:")
        _test_method(token, 'friends.get', {'user_id': user['id'], 'count': 1})
        _test_method(token, 'wall.get', {'owner_id': user['id'], 'count': 1})
        _test_method(token, 'photos.getAll', {'owner_id': user['id'], 'count': 1})

        return True
    except Exception as e:
        print(f"VK user token: CHECK FAILED -- {e}")
        return False


def _test_method(token, method, params):
    """Test a VK API method and report success/failure."""
    import requests
    try:
        params['access_token'] = token
        params['v'] = '5.199'
        resp = requests.get(f'https://api.vk.com/method/{method}', params=params, timeout=5)
        data = resp.json()
        if 'error' in data:
            error_msg = data['error'].get('error_msg', '')
            print(f"  {method}: BLOCKED -- {error_msg}")
        else:
            count = data.get('response', {}).get('count', '?')
            print(f"  {method}: OK (count={count})")
    except Exception as e:
        print(f"  {method}: ERROR -- {e}")


def get_oauth_url():
    """Build the VK OAuth URL."""
    # Use VK official Android app client_id — supports user OAuth implicit flow
    # without app verification. Standard technique for obtaining user tokens.
    app_id = '2685278'

    return (
        f'https://oauth.vk.com/authorize'
        f'?client_id={app_id}'
        f'&redirect_uri=https://oauth.vk.com/blank.html'
        f'&scope=wall,photos,offline'
        f'&response_type=token'
        f'&v=5.199'
    )


def extract_token_from_url(url):
    """Extract access_token from VK OAuth redirect URL."""
    match = re.search(r'access_token=([a-zA-Z0-9._-]+)', url)
    if match:
        return match.group(1)
    return None


def save_token_to_env(token):
    """Save VK_USER_TOKEN to .env file."""
    env_path = os.path.join(PROJECT_ROOT, '.env')

    lines = []
    token_found = False
    if os.path.exists(env_path):
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip().startswith('VK_USER_TOKEN='):
                    lines.append(f'VK_USER_TOKEN={token}\n')
                    token_found = True
                else:
                    lines.append(line)

    if not token_found:
        lines.append(f'\nVK_USER_TOKEN={token}\n')

    with open(env_path, 'w', encoding='utf-8') as f:
        f.writelines(lines)

    os.environ['VK_USER_TOKEN'] = token
    print(f"Token saved to .env as VK_USER_TOKEN")


def authenticate():
    """Run interactive OAuth authentication."""
    url = get_oauth_url()
    if not url:
        return False

    print("VK OAuth Token Acquisition")
    print("=" * 50)
    print()
    print("Step 1: Open this URL in your browser:")
    print()
    print(f"  {url}")
    print()

    # Try to open in browser automatically
    try:
        import webbrowser
        webbrowser.open(url)
        print("  (Browser opened automatically)")
        print()
    except Exception:
        print("  (Copy-paste the URL above into your browser)")
        print()

    print("Step 2: Log in to VK and grant permissions")
    print()
    print("Step 3: After redirect, copy the FULL URL from your browser's address bar")
    print("  It will look like: https://oauth.vk.com/blank.html#access_token=vk1.a...")
    print()

    redirect_url = input("Paste the redirect URL here: ").strip()
    if not redirect_url:
        print("No URL provided. Aborting.")
        return False

    token = extract_token_from_url(redirect_url)
    if not token:
        print("ERROR: Could not extract access_token from the URL.")
        print("  Make sure you copied the complete URL including the #access_token= part.")
        return False

    # Validate token
    import requests
    try:
        resp = requests.get(
            'https://api.vk.com/method/users.get',
            params={'access_token': token, 'v': '5.199'},
            timeout=5
        )
        data = resp.json()
        if 'error' in data:
            error_msg = data['error'].get('error_msg', 'Unknown')
            print(f"ERROR: Token is invalid -- {error_msg}")
            return False

        user = data['response'][0]
        name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
        print()
        print(f"Authenticated as: {name} (id{user['id']})")
    except Exception as e:
        print(f"WARNING: Could not validate token ({e}), saving anyway...")

    save_token_to_env(token)
    print()
    print("VK user token saved. Restart the IBP server for changes to take effect.")
    print()
    print("This token grants access to:")
    print("  - wall.get (wall posts for phone/contact discovery)")
    print("  - friends.get (social graph building)")
    print("  - photos.getAll (facial recognition)")
    print("  - offline (long-lived token, no re-auth needed)")
    return True


def main():
    parser = argparse.ArgumentParser(description='VK OAuth token acquisition for IBP')
    parser.add_argument('--check', action='store_true', help='Only check existing token')
    args = parser.parse_args()

    if args.check:
        valid = check_token()
        sys.exit(0 if valid else 1)
    else:
        # First check existing token
        print("Checking existing VK user token...")
        if check_token():
            print()
            print("Token is still valid. No re-authentication needed.")
            print("To get a new token anyway, delete VK_USER_TOKEN from .env and re-run.")
            sys.exit(0)

        print()
        success = authenticate()
        sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
