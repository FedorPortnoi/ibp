"""
DEPRECATED: Use auth_telegram.py instead.

  python scripts/auth_telegram.py           # Authenticate or validate
  python scripts/auth_telegram.py --check   # Only check session validity
"""
import os
import sys
import subprocess

script_dir = os.path.dirname(os.path.abspath(__file__))
new_script = os.path.join(script_dir, 'auth_telegram.py')

print("NOTE: telethon_auth.py is deprecated. Redirecting to auth_telegram.py...")
print()

sys.exit(subprocess.call([sys.executable, new_script] + sys.argv[1:]))
