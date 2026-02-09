#!/usr/bin/env python3
"""Generate a bcrypt password hash for IBP authentication."""
import bcrypt
import sys

if len(sys.argv) > 1:
    password = sys.argv[1]
else:
    import getpass
    password = getpass.getpass("Enter IBP master password: ")

hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
print(f"\nAdd this to your .env file:")
print(f"IBP_PASSWORD_HASH={hashed}")
print(f"\nOr set a plain text password (less secure, auto-hashed on first login):")
print(f"IBP_PASSWORD={password}")
