# IBP Security Hardening Report

## Summary
- **Total iterations:** 40
- **Vulnerabilities discovered:** 8
- **Vulnerabilities fixed:** 8
- **Accepted risks:** 2
- **Final iterations (31-40):** all SECURE (no new findings)

## Attack Surface Map

### Route Endpoints (92 total)

| Endpoint | Method | Rate Limit | Auth | Status |
|----------|--------|-----------|------|--------|
| `/login` | GET/POST | 10/min | No | SECURE |
| `/logout` | GET | - | No | SECURE |
| `/health` | GET | 120/min (default) | Partial | SECURE (minimal for unauthed) |
| `/` | GET | 120/min | Yes | SECURE |
| `/candidate/start` | POST | 10/min | Yes | SECURE |
| `/candidate/progress/<id>` | GET | 120/min | Yes | SECURE |
| `/candidate/progress/<id>/status` | GET | 120/min | Yes | SECURE |
| `/candidate/confirm/<id>` | GET/POST | 120/min | Yes | SECURE |
| `/candidate/dossier/<id>` | GET | 120/min | Yes | SECURE |
| `/candidate/history` | GET | 120/min | Yes | SECURE |
| `/candidate/delete/<id>` | POST | 10/min | Yes | SECURE |
| `/candidate/export/<id>/json` | GET | 5/min | Yes | SECURE |
| `/candidate/export/<id>/pdf` | GET | 5/min | Yes | SECURE |
| `/candidate/api/social-graph/<id>` | GET | 120/min | Yes | SECURE |
| `/candidate/api/geo-data/<id>` | GET | 120/min | Yes | SECURE |
| `/candidate/api/timeline/<id>` | GET | 120/min | Yes | SECURE |
| `/vk/auth` | GET | 120/min | Yes | SECURE |
| `/vk/callback` | GET | 120/min | Yes | SECURE |
| `/vk/save-token` | POST | 120/min | Yes | SECURE (regex validation) |
| `/api/vk/token-status` | GET | 120/min | Yes | SECURE |
| `/api/investigations/<id>` | DELETE | 10/min | Yes | SECURE |
| `/phase1/new` | GET/POST | 10/min POST | Yes | SECURE |
| `/phase1/search/<id>` | GET | 120/min | Yes | SECURE |
| `/phase1/confirm/<id>/<pid>` | POST | 120/min | Yes | SECURE |
| `/phase1/uploads/<filename>` | GET | 120/min | Yes | SECURE (send_from_directory) |
| `/phase1/photo-search` | POST | 5/min | Yes | SECURE |
| `/phase1/api/search/<id>/refresh` | POST | 10/min | Yes | SECURE |
| `/phase2/start` | POST | 5/min | Yes | SECURE |
| `/phase2/analyze/<id>` | GET | 120/min | Yes | SECURE |
| `/phase3/start` | POST | 5/min | Yes | SECURE |
| `/phase3/api/business-search` | POST | 10/min | Yes | SECURE |
| `/phase3/api/court-search` | POST | 10/min | Yes | SECURE |
| `/phase3/api/buratino/start/<id>` | POST | 5/min | Yes | SECURE |
| `/phase4/api/search/people` | POST | 10/min | Yes | SECURE |
| `/investigation/<id>/graph` | GET | 120/min | Yes | SECURE (was XSS) |
| `/api/search/vk` | POST | 30/min | Yes | SECURE |
| `/api/search/telegram` | POST | 30/min | Yes | SECURE |
| `/api/search/save-selection` | POST | 120/min | Yes | SECURE |
| `/scoring/api/scoring/calculate` | POST | 10/min | Yes | SECURE |
| `/connections/api/connections/analyze` | POST | 10/min | Yes | SECURE |
| `/report/generate` | POST | 10/min | Yes | SECURE |
| `/report/download/html` | POST | 5/min | Yes | SECURE |
| `/report/download/pdf` | POST | 5/min | Yes | SECURE |
| `/report/download/json` | POST | 5/min | Yes | SECURE |
| `/dossier/<id>/json` | GET | 5/min | Yes | SECURE |
| `/dossier/<id>/pdf` | GET | 5/min | Yes | SECURE |

### Security Controls In Place

| Control | Status |
|---------|--------|
| Authentication (bcrypt) | ACTIVE |
| CSRF Protection (Flask-WTF) | ACTIVE |
| Rate Limiting (Flask-Limiter) | ACTIVE (all routes) |
| Session Timeout (activity-based) | ACTIVE |
| Session Fixation Prevention | ACTIVE |
| XSS (Jinja2 auto-escape) | ACTIVE |
| SQL Injection (SQLAlchemy ORM) | ACTIVE |
| CSP Headers | ACTIVE |
| HSTS | ACTIVE |
| X-Frame-Options | ACTIVE |
| X-Content-Type-Options | ACTIVE |
| Referrer-Policy | ACTIVE |
| Input Length Limits | ACTIVE |
| File Upload Validation | ACTIVE |
| Subprocess Safety (list args) | ACTIVE |
| Open Redirect Prevention | ACTIVE |

## Vulnerability Timeline

| # | Severity | Finding | Fix | File |
|---|----------|---------|-----|------|
| 1 | **HIGH** | XSS via `.format(investigation_id)` in inline HTML response | Replaced with `render_template('errors/404.html')` | `app/routes/phase4.py:82-98` |
| 2 | **HIGH** | Newline injection in VK token save — could inject arbitrary `.env` vars | Strict regex validation `^[a-zA-Z0-9._\-]+$` on both route and save function | `app/utils/vk_token_manager.py:81`, `app/routes/main.py:139` |
| 3 | **HIGH** | Path traversal in phase2 photo path — `os.path.exists(user_input)` accepted any path | Restricted to uploads dir with `secure_filename` + `realpath` validation | `app/routes/phase2.py:196-205` |
| 4 | **MEDIUM** | Content-Disposition header injection — user name in filenames | Added `_safe_filename()` sanitizer with `re.sub(r'[^\w\-.]', '_', ...)` | `app/routes/candidate_check.py:25-30` |
| 5 | **MEDIUM** | Session fixation — no session regeneration on login | Added `session.clear()` before setting auth | `app/routes/auth.py:89-92` |
| 6 | **MEDIUM** | No activity-based session timeout | Added `last_active` tracking + timeout enforcement in `before_request` | `app/__init__.py:128-142` |
| 7 | **MEDIUM** | Missing rate limits on 15+ endpoints | Added `@limiter.limit()` to all data-mutation and search endpoints | Multiple route files |
| 8 | **LOW** | Information disclosure — error details leaked to clients | Replaced `str(e)` in client messages with generic errors | `app/routes/phase2.py:929`, `app/routes/phase4.py:60` |

### Additional Hardening

| Change | Description |
|--------|-------------|
| Password hash caching | `get_password_hash()` now caches bcrypt output to avoid redundant `gensalt()` per login |
| Concurrent task limit | Max 10 active candidate pipeline tasks to prevent resource exhaustion |
| Stale task cleanup | Tasks stuck in running state cleaned up after 4x max_age (was: never cleaned) |

## Regression Test Results

All 9 automated security tests pass:

```
1 auth block: PASS
2 pages: PASS
3 valid start: PASS
4 invalid INN: PASS
5 XSS graph: PASS
6 token injection: PASS
7 valid token: PASS
8 HTML strip: PASS
9 session timeout: PASS
9/9 PASSED
```

## What Could NOT Be Tested

- **nginx configuration:** Server-side configs not accessible from local dev
- **Network-level attacks:** DDoS, SSL stripping — require infrastructure access
- **Social engineering:** Phishing, credential stuffing
- **External API SSRF:** Would require sending requests to live APIs
- **Production deployment specifics:** Docker container security, host hardening

## Accepted Risks

1. **CSP `unsafe-inline` / `unsafe-eval`:** Required by Tailwind CDN and inline scripts. Mitigated by Jinja2 auto-escaping preventing XSS at the template level.

2. **UUID-based resource IDs without ownership checks:** Single-user app behind auth — UUIDv4 hex values are not guessable. Would need per-user ownership model for multi-user deployment.

## Remaining Recommendations

1. **Move to nonce-based CSP:** Replace `unsafe-inline` with per-request nonces for scripts. Requires refactoring all inline `<script>` blocks.

2. **Add Content-Security-Policy-Report-Only:** Monitor CSP violations before enforcing stricter policies.

3. **Consider WAF:** For production, add a Web Application Firewall (Cloudflare, nginx ModSecurity) for additional defense-in-depth.

4. **Dependency audit:** Run `pip audit` or `safety check` regularly to detect known vulnerabilities in Python dependencies.

5. **Log monitoring:** Set up alerting on repeated 401/429 responses to detect brute-force attempts.
