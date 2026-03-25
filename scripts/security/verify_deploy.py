"""Post-deployment security verification for shtirletzsled.ru
Run after deploying to confirm all security fixes are live.
"""
import requests
import sys

BASE_URL = "https://shtirletzsled.ru"
errors = []
warnings = []

def check(label, ok, detail=""):
    if ok:
        print(f"  PASS: {label}")
    else:
        errors.append(label)
        print(f"  FAIL: {label} {detail}")

def warn(label, ok, detail=""):
    if ok:
        print(f"  PASS: {label}")
    else:
        warnings.append(label)
        print(f"  WARN: {label} {detail}")

print("=== Security Verification ===\n")

# 1. Headers
r = requests.get(BASE_URL, timeout=10)
h = r.headers

print("[Headers]")
check("Server header hidden", "nginx" not in h.get("Server", "").lower() or "/" not in h.get("Server", ""),
      f"(got: {h.get('Server', 'hidden')})")
check("X-Frame-Options = DENY", h.get("X-Frame-Options") == "DENY",
      f"(got: {h.get('X-Frame-Options', 'missing')})")
check("X-Content-Type-Options = nosniff", h.get("X-Content-Type-Options") == "nosniff")
check("HSTS with preload", "preload" in h.get("Strict-Transport-Security", ""),
      f"(got: {h.get('Strict-Transport-Security', 'missing')})")
check("Permissions-Policy set", "Permissions-Policy" in h)
check("CSP set", "Content-Security-Policy" in h)
check("frame-ancestors none in CSP", "frame-ancestors 'none'" in h.get("Content-Security-Policy", ""),
      f"(got frame-ancestors: {[p for p in h.get('Content-Security-Policy', '').split(';') if 'frame' in p]})")
check("Referrer-Policy set", "Referrer-Policy" in h)

# 2. Cookie
print("\n[Cookies]")
cookie_header = h.get("Set-Cookie", "")
check("Session cookie HttpOnly", "HttpOnly" in cookie_header or "httponly" in cookie_header.lower())
check("Session cookie Secure", "Secure" in cookie_header,
      f"(Set-Cookie: ...{cookie_header[-80:]})")
check("Session cookie SameSite", "SameSite" in cookie_header)

# 3. Sensitive paths blocked
print("\n[Sensitive Paths]")
blocked_paths = ["/.env", "/.git/config", "/.git/HEAD", "/config.py",
                 "/requirements.txt", "/database.db", "/backup.sql"]
for path in blocked_paths:
    r2 = requests.get(f"{BASE_URL}{path}", allow_redirects=False, timeout=5)
    check(f"{path} blocked (expect 404)", r2.status_code == 404,
          f"(got: {r2.status_code})")

# 4. No stack traces
print("\n[Error Handling]")
r3 = requests.get(f"{BASE_URL}/nonexistent_xyz_test", timeout=5)
check("404 no traceback", "traceback" not in r3.text.lower())
check("404 no werkzeug", "werkzeug" not in r3.text.lower())

# 5. Summary
print(f"\n=== Results: {len(errors)} failures, {len(warnings)} warnings ===")
if errors:
    print("FAILURES:")
    for e in errors:
        print(f"  - {e}")
if warnings:
    print("WARNINGS:")
    for w in warnings:
        print(f"  - {w}")
if not errors and not warnings:
    print("All checks passed!")

sys.exit(1 if errors else 0)
