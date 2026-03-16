# IBP Security Audit Report

## Date: 2026-03-16
## Auditor: Claude Code (automated)
## Scope: Code-level analysis of `app/` directory, configuration files, templates

---

### Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 2 |
| MEDIUM | 5 |
| LOW | 3 |

---

### Findings (sorted by severity)

---

#### HIGH

##### H1. Open Redirect via `next_url` Session Value

**File:** `app/routes/auth.py:90-91`, `app/__init__.py:125`

**Description:** After successful login, the user is redirected to `session['next_url']` without any validation that it points to the same origin. The value is set from `request.url`, which Flask constructs using the `Host` header. An attacker who can manipulate the Host header (e.g., via a misconfigured reverse proxy) could cause `request.url` to contain an external domain, leading to an open redirect after login.

Additionally, even without Host header injection, any code path that sets `session['next_url']` to an attacker-controlled value creates an open redirect.

```python
# auth.py:90-91
next_url = session.pop('next_url', None)
return redirect(next_url or url_for('main.dashboard'))  # No validation!
```

**Impact:** Phishing — user logs in on the real site but gets redirected to an attacker-controlled page that mimics the application.

**Fix:** Validate that `next_url` is a relative path (starts with `/` and not `//`):
```python
from urllib.parse import urlparse
next_url = session.pop('next_url', None)
if next_url:
    parsed = urlparse(next_url)
    if parsed.netloc:  # Has a domain — reject
        next_url = None
return redirect(next_url or url_for('main.dashboard'))
```

**Status:** FIXED

---

##### H2. Health Check Endpoint Exposes Internal Service Status Without Authentication

**File:** `app/__init__.py:111`, `app/routes/main.py:14-73`

**Description:** The `/health` endpoint is in the `allowed_endpoints` whitelist (`main.health_check`) and returns detailed internal status without requiring authentication:
- Git commit hash (version fingerprinting)
- Database connectivity status
- Whether VK, Telegram, OK tokens are configured
- Whether OpenSanctions API is reachable
- Whether local data files (MVD wanted, extremist list) exist

**Impact:** Information disclosure — helps attackers fingerprint the deployment, identify which services are active, and determine the exact version deployed.

**Fix:** Either require authentication for `/health`, or reduce the response to a simple `{"status": "ok"}` for unauthenticated requests and only show details when authenticated.

**Status:** FIXED

---

#### MEDIUM

##### M1. Session Cookie Missing `Secure` Flag in Production

**File:** `config.py:160`

**Description:** `ProductionConfig` explicitly sets `SESSION_COOKIE_SECURE = False` with comment "Render handles HTTPS at edge". While Render terminates TLS, the cookie should still have the Secure flag to prevent transmission over any HTTP connection. The server is now deployed to a custom domain with its own TLS.

```python
class ProductionConfig(Config):
    SESSION_COOKIE_SECURE = False  # Should be True
```

**Impact:** Session cookie could be sent over plain HTTP if a user accesses the site without HTTPS (e.g., before redirect).

**Fix:** Set `SESSION_COOKIE_SECURE = True`

**Status:** FIXED

---

##### M2. Session Cookie Missing `SameSite` Attribute

**File:** `config.py` (all config classes)

**Description:** No `SESSION_COOKIE_SAMESITE` is configured. Flask defaults to `None` for older versions and `Lax` for newer versions, but it should be explicitly set.

**Impact:** Without explicit `SameSite=Lax`, the cookie may be sent on cross-site requests in some browsers, enabling CSRF attacks (though Flask-WTF CSRF protection mitigates this).

**Fix:** Add `SESSION_COOKIE_SAMESITE = 'Lax'` to base Config class.

**Status:** FIXED

---

##### M3. Missing `Referrer-Policy` and `Strict-Transport-Security` Headers

**File:** `app/__init__.py:128-143`

**Description:** The `set_security_headers` after_request handler sets X-Frame-Options, X-Content-Type-Options, X-XSS-Protection, and CSP, but is missing:
- `Strict-Transport-Security` (HSTS) — forces HTTPS for future visits
- `Referrer-Policy` — controls what referrer info is sent to external sites

**Impact:** Without HSTS, users can be downgraded to HTTP on first visit. Without Referrer-Policy, full URLs (potentially containing sensitive check IDs) may leak via the Referer header to external CDNs.

**Fix:** Add both headers to the after_request handler.

**Status:** FIXED

---

##### M4. Content Security Policy Allows `unsafe-inline` and `unsafe-eval`

**File:** `app/__init__.py:134-142`

**Description:** The CSP includes `'unsafe-inline'` and `'unsafe-eval'` in the `script-src` directive. This is currently necessary because:
- Tailwind CSS CDN uses inline styles
- Various templates use inline `<script>` blocks
- vis.js/Chart.js may use eval

**Impact:** Weakens XSS protection — if an attacker finds an injection point, inline scripts would execute despite CSP.

**Fix:** Long-term: migrate inline scripts to external files and use nonce-based CSP. Short-term: document as accepted risk.

**Status:** DOCUMENTED (accepted risk — would require significant refactoring)

---

##### M5. Command Injection via Unsanitized Usernames in OSINT Tool Subprocess Calls

**File:** `app/services/snoop_search.py:300-302`, `app/services/maigret_search.py:128-131`, `app/services/sherlock_search.py:136-145`

**Description:** Usernames from VK/Telegram profiles are passed as arguments to subprocess calls for Snoop, Maigret, and Sherlock. While the commands use list form (not `shell=True`), which prevents shell injection, a malicious username containing path traversal characters (e.g., `../../etc/passwd`) could cause:
- Output files written to unexpected locations
- Reading/processing of unintended files

```python
cmd = ['python', str(self.snoop_script), username, '-f', '-n']
subprocess.run(cmd, ...)
```

**Impact:** Low probability — usernames come from VK/Telegram APIs, not directly from user input. But a compromised social profile could inject path traversal strings.

**Fix:** Sanitize usernames before passing to OSINT tools — strip `/`, `\`, `..`, null bytes.

**Status:** FIXED

---

#### LOW

##### L1. No Account Lockout After Failed Login Attempts

**File:** `app/routes/auth.py:62`

**Description:** Login is rate-limited to 10 attempts per minute via Flask-Limiter, but there is no progressive lockout (e.g., exponential backoff, temporary account lock after N failures). Rate limiting is per-IP, which can be bypassed via distributed attacks.

**Impact:** Brute-force attacks are slowed but not stopped. With a simple password, 10 attempts/minute = 14,400/day.

**Fix:** Consider adding exponential backoff or temporary lockout after 5 consecutive failures.

**Status:** DOCUMENTED

---

##### L2. `DEBUG=True` in DevelopmentConfig

**File:** `config.py:152`

**Description:** Development config has `DEBUG = True`, which is expected for local development. Production config correctly has `DEBUG = False`. However, if the app is accidentally run with `FLASK_ENV=development` in production, Flask's debugger would be enabled with a PIN (the Werkzeug debugger allows code execution).

**Impact:** Only if misconfigured in production. Correct production config mitigates this.

**Fix:** No code change needed — already correct. Verify FLASK_ENV=production on server.

**Status:** OK (no fix needed)

---

##### L3. Inline `innerHTML` Assignments in Templates

**File:** `app/templates/candidate_dossier.html`, `app/templates/home.html`, `app/templates/base.html`, `app/templates/candidate_history.html`

**Description:** Several templates use `innerHTML` to set content. Most set hardcoded HTML strings (no user data), but `candidate_history.html:648` builds pagination HTML from page numbers (safe integers). No user-supplied strings flow into `innerHTML`.

**Impact:** Currently safe — no user data reaches innerHTML. But fragile if future code adds user data to these paths.

**Fix:** No immediate fix needed. Use `textContent` where possible in future changes.

**Status:** OK (no fix needed)

---

### What Was Tested

- SQL injection patterns (parameterized queries throughout - SAFE)
- XSS via `| safe`, `Markup()`, `autoescape false` (none found)
- XSS via `innerHTML` / `document.write` (hardcoded values only)
- CSRF protection (Flask-WTF + global fetch interceptor - GOOD)
- Authentication enforcement (global `before_request` - GOOD)
- Session management and cookie security
- Rate limiting coverage
- File upload handling (`secure_filename` + extension whitelist - GOOD)
- Path traversal in `send_from_directory` (safe by design)
- Subprocess command injection
- Error page information leakage (clean error pages - GOOD)
- Sensitive data in `.gitignore` (.env, .db, sessions all excluded - GOOD)
- Hardcoded secrets in code (none found - all from env vars)
- Open redirect vectors

### What Was NOT Tested

- Actual exploitation (this was read-only/non-destructive)
- DDoS resilience / load testing
- Social engineering vectors
- Third-party API security (VK, Telegram token transmission)
- Server-side configuration (nginx, gunicorn, firewall, SSL)
- Dependency vulnerability scanning (requires pip audit on server)
- Network-level attacks (MITM, DNS hijacking)

### Positive Security Findings

1. **SQL Injection: SAFE** — All database queries use parameterized queries (`?` placeholders in SQLite, SQLAlchemy ORM)
2. **CSRF: WELL IMPLEMENTED** — Flask-WTF CSRFProtect globally enabled, all forms include `csrf_token()`, global fetch interceptor adds X-CSRFToken header
3. **XSS: SAFE** — Jinja2 auto-escaping active, no `| safe` or `Markup()` usage, no `autoescape false`
4. **Authentication: GOOD** — Global `before_request` hook protects all routes, bcrypt password hashing
5. **Rate Limiting: GOOD** — Flask-Limiter on login (10/min), candidate start (10/min), exports (5/min), API routes (30/min)
6. **File Upload: SAFE** — `secure_filename()` + extension whitelist + `send_from_directory()`
7. **Error Pages: CLEAN** — Custom 404/500 templates, no stack traces or internal paths
8. **Secrets: CLEAN** — All API keys loaded from environment, `.env` in `.gitignore`
9. **Input Validation: GOOD** — HTML tag stripping, length limits, INN checksum validation, date/age range validation
