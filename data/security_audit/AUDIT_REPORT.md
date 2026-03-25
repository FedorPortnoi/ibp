# СЛЕД Security Audit Report — 2026-03-25

## Scope
- Static analysis: bandit + safety on Python codebase
- Live pentest: OWASP Top 10 against https://shtirletzsled.ru
- Code review: IDOR, access control, session management
- Dependency audit: CVE scan on requirements.txt

## Executive Summary

| Category | Before | After |
|----------|--------|-------|
| CRITICAL | 0 | 0 |
| HIGH (code) | 19 IDOR endpoints + rate limit bypass | 0 |
| HIGH (deps) | 12 CVEs | 0 |
| MEDIUM | 2 (headers) | 0 |
| LOW | 1 (server fingerprint) | 0 (nginx config provided) |

---

## Findings & Fixes

### 1. IDOR — 19 Unprotected Endpoints [HIGH -> FIXED]

**Finding**: 19 endpoints accessed CandidateCheck/Investigation records by ID without verifying the current user owns that record.

**Affected endpoints**:

Candidate Check (7 endpoints):
- `/candidate/progress/<task_id>` — view progress
- `/candidate/progress/<task_id>/status` — JSON progress polling
- `/candidate/confirm/<check_id>` GET — view profiles
- `/candidate/confirm/<check_id>` POST — modify confirmed profiles
- `/candidate/api/social-graph/<check_id>` — social graph data
- `/candidate/api/geo-data/<check_id>` — geo intelligence
- `/candidate/api/timeline/<check_id>` — activity timeline

Legacy routes (12 endpoints) — report, dossier, scoring (all Investigation-based):
- `/report/<id>`, `/report/api/investigation-data/<id>`
- `/dossier/<id>`, `/dossier/<id>/json`, `/dossier/<id>/pdf`
- `/api/scoring/calculate`, `/api/scoring/breakdown/<id>`, `/risk-report/<id>`
- `/report/generate`, `/report/download/html`, `/report/download/pdf`, `/report/download/json`

**Fix**:
- Candidate endpoints: Added `_check_owner_or_admin()` helper — verifies `check.user_id == current_user.id` or admin role
- Legacy endpoints: Added `@admin_required` decorator (Investigation model lacks user_id, admin-only is safest)

**Files changed**: `app/routes/candidate_check.py`, `app/routes/report.py`, `app/routes/dossier.py`, `app/routes/scoring.py`

---

### 2. Rate Limit Bypass Behind Reverse Proxy [HIGH -> FIXED]

**Finding**: Login rate limit (10/min) was not triggered during brute force test. Flask-Limiter's `get_remote_address` saw nginx proxy IP (127.0.0.1), not client IP.

**Fix**:
- Added `ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)` to trust X-Forwarded-For
- Tightened login limit from `10 per minute` to `5 per minute` (POST only)

**File changed**: `app/__init__.py`, `app/routes/auth.py`

---

### 3. Registration Race Condition [HIGH -> FIXED]

**Finding**: Between `User.query.filter_by(username=...).first()` check and `db.session.commit()`, concurrent requests could create duplicate users.

**Fix**: Added `IntegrityError` catch around `db.session.commit()` with rollback and error message.

**File changed**: `app/routes/auth.py`

---

### 4. Missing Security Headers [MEDIUM -> FIXED]

**Finding**: `Permissions-Policy` header missing. `X-Frame-Options` was SAMEORIGIN (should be DENY for this app).

**Fix**:
- Added `Permissions-Policy: geolocation=(), microphone=(), camera=(), payment=(), usb=()`
- Changed `X-Frame-Options` from SAMEORIGIN to DENY
- Changed CSP `frame-ancestors` from `'self'` to `'none'`
- Added `preload` to HSTS
- Added `Server`/`X-Powered-By` header removal in Flask

**File changed**: `app/__init__.py`

---

### 5. Server Fingerprint Exposure [LOW -> FIX PROVIDED]

**Finding**: `Server: nginx/1.24.0 (Ubuntu)` exposed in response headers.

**Fix**: Provided `scripts/security/nginx_hardening.conf` with:
- `server_tokens off;`
- Dotfile blocking (`location ~ /\.`)
- Sensitive extension blocking (`.env`, `.db`, `.py`, etc.)
- Data directory blocking

**Action required**: Apply to nginx config on server.

---

### 6. Vulnerable Dependencies [HIGH -> FIXED]

| Package | Old | New | CVEs Fixed |
|---------|-----|-----|-----------|
| Flask | 3.1.2 | 3.1.3 | CVE-2026-27205 |
| Werkzeug | 3.1.4 | 3.1.6 | CVE-2026-21860, CVE-2026-27199 |
| aiohttp | 3.13.2 | 3.13.3 | CVE-2025-69223 through CVE-2025-69230 (8 CVEs) |
| Pillow | 11.3.0 | 12.1.1 | CVE-2026-25990 |

**File changed**: `requirements.txt`

---

### 7. Bandit Static Analysis — MD5/SHA1 False Positives [HIGH -> FIXED]

**Finding**: 15 `hashlib.md5()`/`hashlib.sha1()` calls flagged as weak hash usage. All are non-security uses (Gravatar hashes, data dedup, cache keys, HIBP k-anonymity).

**Fix**: Added `usedforsecurity=False` parameter to all 12 calls across 8 files.

**Remaining bandit issues** (false positives):
- 3x B413: `pycryptodome` flagged as deprecated `pycrypto` (different library)
- 2x B108: Playwright temp dir usage (not security-sensitive)

---

## Already Secure (Passed Tests)

| Test | Result |
|------|--------|
| SQL Injection (4 payloads) | PASS — SQLAlchemy parameterized queries |
| XSS (4 payloads) | PASS — Jinja2 auto-escaping |
| CSRF | PASS — Flask-WTF CSRFProtect |
| Session fixation | PASS — `session.clear()` on successful login |
| Admin role injection | PASS — role hardcoded to 'user' in register |
| Subscription bypass | PASS — `before_request` check |
| Open redirect | PASS — `urlparse` validation |
| .env / .git exposure | PASS — nginx blocks dotfiles |
| Debug mode | PASS — no Werkzeug debugger |
| SQLite DB exposure | PASS — not accessible via HTTP |
| HSTS | PASS — max-age=31536000 |
| CSP | PASS — restrictive policy |
| bcrypt password hashing | PASS |
| Activity-based session timeout | PASS — 1h default |

---

## Server-Side Actions Required

```bash
# 1. Apply nginx hardening
sudo cp scripts/security/nginx_hardening.conf /etc/nginx/snippets/ibp-security.conf
# Add to server block: include snippets/ibp-security.conf;
sudo nginx -t && sudo systemctl reload nginx

# 2. Update dependencies on server
pip install -r requirements.txt

# 3. Cleanup pentest test accounts
python scripts/security/cleanup_pentest_users.py

# 4. Restart application
sudo systemctl restart ibp
```
