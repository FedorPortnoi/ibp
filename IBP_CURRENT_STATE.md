# IBP Current State

**Last updated**: 2026-02-27
**Branch**: `main`
**Latest commit**: `2cce0ca` docs: INN-first pipeline architecture

---

## Codebase Metrics

| Metric | Count |
|--------|-------|
| Python files (app/) | 111 |
| Lines of code (app/) | 46,762 |
| HTML templates | 29 |
| Template lines | 11,171 |
| Test files | 66 |
| Test functions | ~3,014 |
| Test lines | 38,401 |
| Database models | 7 |
| Route blueprints | 13 |
| Service classes | ~91 |
| Total endpoints | 87 |
| Pipeline stages | 9 (Stage 0-8) |
| Contact discovery steps | 11 |

**Total source files**: 206 (app/ + tests/ + templates)
**Total lines**: ~96,334 (app + tests + templates)

---

## Feature Completion vs Original Spec

### 9-Stage Pipeline (Stage 0-8): **100% wired, ~90% data quality**

INN (Russian Tax ID) is the required primary identifier. Stage 0 uses INN for direct EGRUL/bankruptcy lookups before name-based searches.

| Stage | Wired | Real Data | Demo Fallback | Notes |
|-------|-------|-----------|---------------|-------|
| 0. Identity Confirmation | Yes | EGRUL by INN + EFRSB bankruptcy by INN + business network | Skips if no INN | Sets `confirmed_name` for all subsequent stages |
| 1. Gov Registries | Yes | EGRUL by name + sudact.ru + **checko.ru** + casebook.ru | Empty results | checko.ru is primary FSSP alt (global), casebook.ru replaces kad.arbitr.ru |
| 2. Security Checks | Yes | **OpenSanctions** + Interpol + local DBs work globally | Empty results | Local MVD/extremist JSON + OpenSanctions = no geo-block needed |
| 3. Social Media | Yes | VK (with DOB filtering) + Telegram (with birth year usernames) + OK | 3 fake VK + 3 fake OK profiles | VK `users.search` now uses `birth_day/month/year` params |
| 4. Contact Discovery | Yes | 11-step chain + birth year email/username patterns | Empty results | Uses `confirmed_name`, birth year in email guessing + Telegram usernames |
| 5. Social Analysis | Yes | Search4Faces + graph + Snoop + **Maigret** + **Sherlock** | Demo graph data | Maigret/Sherlock pip-installable, run in parallel with Snoop via ThreadPoolExecutor |
| 6. Behavioral Analysis | Yes | Text/geo/timeline work | Demo data | Requires VK wall access |
| 7. Risk Scoring | Yes | 9 categories scored (incl. identity) | Scores empty data | Identity discrepancy flag, critical debt (>1M) flag |
| 8. Report Generation | Yes | Full dossier + PDF + identity section | Works with any data | Identity card, INN tab, vis.js graph, geo map |

### Contact Discovery 11-Step Chain (Stage 4)

| Step | What | Source Key | Confidence |
|------|------|-----------|------------|
| 1 | VK profile contacts | `vk_profile_contacts` | 0.95 |
| 1b | Deep VK wall mining (posts, comments, tagged posts, photos, mentions) | `vk_wall_by_subject` / `vk_wall_by_others` | 0.85 / 0.70 |
| 2 | Telegram profile data | `telegram` | 0.85 |
| 3 | Business/FSSP records | `egrul` / `fssp` | 0.50 / 0.45 |
| 4 | Email guessing (username + transliteration) | `email_guess` | 0.40 |
| 4b | Hunter.io corporate email verification (if employer known) | `hunter_verified` | 0.80 |
| 5 | LeakDB name lookup | `leak_db` | 0.65 |
| 6 | Breach API enrichment (HudsonRock, LeakCheck, ProxyNova) | `breach_api` | 0.60 |
| 7 | LeakDB cross-reference (phone->email, email->phone) | `leak_db_xref` | 0.55 |
| 8 | Forgot-password oracle (6 global + 2 geo-restricted) | `forgot_password_*` | 0.78-0.90 |
| 8a | VK username oracle (account existence only, Feb 2026) | `vk_forgot_password` | 0.80-0.90 |
| 9 | Marketplace mining (6 platforms, Avito Playwright phone extraction) | `marketplace` | 0.90 |
| 10 | Holehe email verification | `holehe_verified` | 0.80 |
| 11 | Deduplicate + merge sources + cross-source boost | -- | +0.15 boost |

### Confidence Scoring System

- Numeric scores 0.0-1.0 per source type (`CONFIDENCE_SCORES` dict in `contact_discovery.py`)
- Russian labels preserved: `высокая` (>=0.75), `средняя` (>=0.50), `низкая` (<0.50)
- Cross-source boost: +0.15 when 3+ independent sources confirm same phone/email
- Max cap: 0.98
- Each contact tracks full `sources` list for auditability

---

## What Works End-to-End in Demo Mode

These features work without any API keys configured:

1. Start a candidate check (quick or precise mode, INN required)
2. All 9 stages execute (Stage 0 identity confirmation + Stages 1-8)
3. Progress bar tracks all 9 stages in real-time
4. Precise mode pauses at Stage 3 for profile confirmation
5. Risk scoring produces a risk level (CLEAN with no data)
6. Dossier page renders with all tabs (social graph, geo, behavioral, accounts)
7. PDF export generates a downloadable file
8. JSON export includes all stage data
9. OK.ru demo profiles appear in Phase 1 search results

**20 E2E demo tests pass** (`tests/test_demo_e2e.py`)

## What Needs Real API Keys

| API Key | What It Enables | Cost |
|---------|----------------|------|
| `VK_SERVICE_TOKEN` | Real VK profiles, social graph, wall posts | Free (create VK app) |
| `TELEGRAM_API_ID/HASH/PHONE` | Telegram profile search | Free (my.telegram.org) |
| `OK_SESSION_TOKEN` | Real OK.ru profile search (demo fallback if unset) | Free (login to OK.ru) |
| `SNUSBASE_API_KEY` | Extended breach database | $5-16/mo |
| `DEHASHED_EMAIL/API_KEY` | Extended breach database | $5.49/mo |
| `LEAKCHECK_API_KEY` | Pro breach database (free public tier if unset) | $2.99-24.99/mo |
| `HIBP_API_KEY` | Email breach lookup (free k-anonymity if unset) | $3.50/mo |
| `GETCONTACT_API_KEY` | Phone-to-name reverse lookup | Paid |
| `NUMBUSTER_API_KEY` | Phone lookup | Paid |
| `HUNTER_API_KEY` | Email verification (25/mo free) | Free tier available |
| `FSSP_API_TOKEN` | Enforcement proceedings API | Free but needs Russian IP |

**Important**: Without paid keys, services return **empty lists** (not fake data). Mock data was removed entirely.

## What Needs Russian IP

| Source | Impact Without Russian IP |
|--------|--------------------------|
| FSSP API | SSL errors, Playwright retry with 3s delay, falls back to manual URL |
| EFRSB bankruptcy | May fail, Playwright fallback |
| Rosfinmonitoring sanctions | Cannot scrape, returns unchecked |
| MVD wanted list | Cannot scrape, returns unchecked |
| Extremist list | Cannot scrape, returns unchecked |
| kad.arbitr.ru (arbitration) | HTTP 451 blocked entirely |
| Forgot-password oracle (Gosuslugi, Sberbank) | Geo-blocked, returns empty |

**Works globally**: nalog.ru EGRUL, sudact.ru courts, Interpol, VK API, Telegram API, all breach APIs, Search4Faces, OK.ru demo, Holehe, marketplace scanners, OpenSanctions, checko.ru, casebook.ru

---

## Security Hardening (Added 2026-02-26)

### Rate Limiting (Flask-Limiter)
- Global default: 120 requests/minute
- `/candidate/start`: 10/minute
- Candidate export endpoints: 5/minute
- `/api/search`: 30/minute
- Auth login: 10/minute
- Dossier/report exports: 5/minute
- 429 handler returns Russian error message for JSON/AJAX requests
- Disabled in testing config

### CSRF Protection (Flask-WTF)
- `CSRFProtect()` initialized in app factory
- `csrf_token()` in all forms: login, candidate confirm, candidate history, people search
- CSRF meta tag + JS fetch interceptor in `base.html` for AJAX requests
- Disabled in testing config

### Security Headers
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: SAMEORIGIN`
- `X-XSS-Protection: 1; mode=block`
- Full `Content-Security-Policy`

---

## Services Added Since Initial Release

### Global Source Replacements (Stage 1-2)
- **checko.ru** (`app/services/phase3/checko_service.py`) — Primary FSSP alternative, globally accessible
- **casebook.ru** (`app/services/phase3/casebook_service.py`) — Arbitration courts, replaces geo-blocked kad.arbitr.ru
- **OpenSanctions** (`app/services/candidate/opensanctions_service.py`) — Global sanctions (Rosfinmonitoring + OFAC + EU + UN + Interpol)
- **Local security DBs** (`app/services/candidate/local_security_db.py`) — Offline MVD wanted + extremist JSON databases

### Username Search Tools (Stage 5)
- **Maigret** (`app/services/maigret_search.py`) — 3,000+ sites, pip-installable, wired into social_analysis.py
- **Sherlock** (`app/services/sherlock_search.py`) — 400+ sites, pip-installable, wired into social_analysis.py
- Both run in parallel with Snoop via `ThreadPoolExecutor` in Stage 5

### Contact Discovery Enhancements (Stage 4)
- **Forgot-Password Oracle** (`app/services/phase2/forgot_password_oracle.py`) — 8 Russian service checkers (VK, Mail.ru, Yandex, OK, Gosuslugi, Telegram, Avito, Sberbank). VK username oracle is account-existence-only as of Feb 2026 (VK patched id.vk.com — no masked hints shown). Other 7 services still extract masked hints, cross-correlate across services.
- **Marketplace Scanner** (`app/services/phase2/marketplace_scanner.py`) — 6 platforms (Avito, Youla, CIAN, Auto.ru, Yandex Search, VK Market). Searches by name and phone. Avito: Playwright-based phone extraction (clicking "Показать номер"), city data for geo intelligence.
- **OK.ru Search** (`app/services/phase1/ok_search_integration.py`) — Odnoklassniki people search with demo mode (3 fake profiles when `OK_SESSION_TOKEN` unset)
- **Enhanced VK Wall Extractor** — Tagged posts + tagged post comments, photo comments, expanded profile fields (Instagram, Skype, career, Facebook, Twitter, LiveJournal). Wired into Stage 4 Step 1b for deep mining with Telegram/Instagram enrichment hints.
- **Enhanced Email Generator** — Corporate patterns from VK career data, Skype-to-email, expanded domain list. Hunter.io email verification + domain search integration.
- **Hunter.io Integration** (`app/services/phase2/email_generator.py: hunter_verify_email, hunter_domain_search`) — Free tier: 25 verifications + 25 domain searches/month. Wired into Stage 4 Step 4b for corporate email discovery.

### INN-First Pipeline (Stage 0)
- **INN Validator** (`app/utils/inn_validator.py`) — Checksum validation for 10/12-digit Russian tax IDs
- **Stage 0 Identity Confirmation** — EGRUL by INN + bankruptcy by INN + business network extraction
- **DOB filtering** — VK `birth_day/month/year` params, Telegram/email year variants

### Utilities
- **Name Similarity** (`app/utils/name_similarity.py`) — Extracted from deleted per_profile_search.py

---

## What Is Completely Unimplemented

| Feature | Status |
|---------|--------|
| Instagram/Facebook/Twitter/TikTok search | Not implemented |
| Property registry (Rosreestr) | Not implemented |
| Vehicle registry (GIBDD) | Not implemented |
| Passport verification (FMS) | Not implemented |
| Bank account discovery | Not implemented |
| Real-time monitoring | One-shot only |
| Multi-user RBAC | Single-user design |
| Compliance audit logs | Basic file logging only |

---

## Deployment Infrastructure

| File | Purpose |
|------|---------|
| `Dockerfile` | python:3.12-slim + Playwright + Chromium + maigret + sherlock (pip) + gunicorn, non-root `ibp` user |
| `docker-compose.yml` | Port 80:5000, SQLite/leaks volume mounts, `.env` file, health check |
| `deploy.sh` | git pull -> docker compose build -> restart -> health check (5 retries) |
| `render.yaml` | Render free tier, gunicorn, auto-generated SECRET_KEY, Python 3.11.11 |
| `.env.example` | Full documented environment variable template |
| `.dockerignore` | Build context exclusions |

---

## Test Results (2026-02-27)

| Category | Tests | Status |
|----------|-------|--------|
| Unit tests (tests/unit/) | ~3,114 | All pass |
| Integration tests (root-level test_*.py) | ~580 | All pass |
| Demo E2E tests (test_demo_e2e.py) | 20 | All pass |
| Candidate pipeline tests (test_candidate_unified.py) | 93 | All pass |
| INN validation tests (test_inn_validation.py) | 20 | All pass |
| INN pipeline tests (test_inn_pipeline.py) | 18 | All pass |
| New service tests (oracle + marketplace + deep VK) | 172 | All pass |
| **Total** | **~3,794+** | **0 failures, 0 errors** |

Excluded from count:
- `tests/test_phase1.py`, `tests/test_phase3_e2e.py` — Playwright E2E requiring running server
- `tests/test_suite1-8_*.py` — Standalone scripts (not pytest)
- `tests/test_full_workflow.py` — Full network integration (requires live APIs)

---

## Priority List: What to Build Next

### P0 — Deploy to Production
1. **Get a Russian VPS/proxy** — Many data sources are geo-blocked
2. **Paste paid API keys** — Snusbase, DeHashed, GetContact, etc.
3. **Deploy via Docker** — Dockerfile + docker-compose ready, verify health checks

### P1 — High Value
4. **Russian IP proxy config** — SOCKS5 proxy for geo-blocked sources
5. **Instagram/Twitter/TikTok** — Requires new scraping services
6. **SourceManager plugin auto-discovery in Stage 4** — Replace manual chain with plugin system

### P2 — Medium Value
7. **Improve E2E test coverage** — Full Playwright test of candidate check flow with real data
8. **Property/Vehicle registries** — Requires Russian government API access
9. **Multi-user auth** — Flask-Login with user roles

### P3 — Nice to Have
10. **Real-time monitoring** — Periodic re-checks with change detection
11. **Compliance audit logs** — Structured logging for investigations

---

## Known Technical Debt

| Issue | Impact | Fix Effort |
|-------|--------|-----------|
| Error handler returns exception details | Information disclosure in production | Strip details in production mode |
| pytest I/O error running full suite at once | Windows stderr issue | Run test files individually, use `-p no:faulthandler` |

### Resolved Technical Debt
| Issue | Resolution |
|-------|-----------|
| `per_profile_search.py` (2,695 lines dead code) | Deleted in `0a80c02`. `calculate_name_similarity()` extracted to `app/utils/name_similarity.py` |
| OSINT knowledge routes (~5,354 lines dead code) | Deleted in `0a80c02` (`osint_knowledge.py` + `osint_knowledge_gaps.py`) |
| WeasyPrint references in dossier.py | Removed in `0a80c02`. PDF uses Playwright only |
| Duplicate SECRET_KEY / FLASK_SECRET_KEY | Consolidated in config.py — uses SECRET_KEY with FLASK_SECRET_KEY as fallback |
| No CSRF on forms | Flask-WTF `CSRFProtect` wired, all forms have `csrf_token()` |
| No rate limiting | Flask-Limiter wired with per-endpoint limits |

---

## Recent Commit History

```
2cce0ca docs: INN-first pipeline architecture
0aceb92 test: INN validation + Stage 0 pipeline tests + regression fixes
0e70299 feat: risk scoring identity flags + dossier identity section + report builder
35a1ac9 feat: contact discovery — birth year email patterns, confirmed_name, Telegram year variants
bb7175d feat: VK search with DOB filtering — birth_day/month/year params + confidence boost
5d61bd8 docs: update CLAUDE.md — dual-token architecture, auth scripts, Search4Faces API
1828e42 feat: VK dual-token architecture — VK_USER_TOKEN for private API methods
```

---

## INN-First Architecture (Added 2026-02-27)

### Stage 0: Identity Confirmation via INN
- **INN is required** — form validation + checksum verification (10/12-digit Russian tax IDs)
- **EGRUL by INN** — direct lookup via `BusinessRegistrySearch.search_by_inn()`
- **Bankruptcy by INN** — EFRSB lookup (moved from Stage 1 for early signal)
- **Business network** — extracts linked companies and co-founders from EGRUL
- Sets `confirmed_name` (EGRUL name) used by all subsequent stages
- Sets `identity_confirmed` flag and `identity_confirmation` JSON
- New utility: `app/utils/inn_validator.py` — checksum validation for 10/12-digit INNs

### DOB Filtering (Stage 3-4)
- VK `users.search` now uses `birth_day`, `birth_month`, `birth_year` API params
- Telegram username guessing adds year suffix variants (e.g., `ivanov90`, `ivanov1990`)
- Email guessing adds year-based patterns (e.g., `ivanov90@mail.ru`)
- DOB-matched VK profiles get 0.95+ confidence

### Risk Scoring Enhancements (Stage 7)
- New `_analyze_identity()` — name discrepancy flag (SEVERITY_MEDIUM), identity not confirmed flag (SEVERITY_LOW)
- New `critical_debt` flag — >1M RUB active FSSP debt (SEVERITY_HIGH)

### Dossier Updates (Stage 8)
- New "ИНН" nav pill and "Идентификация по ИНН" section in dossier
- Shows EGRUL status, confirmed name, business network, name discrepancy alert
- Report builder includes `identity_confirmation` section, `_count_stages()` returns 9

---

## Branch Status

```
main (production-ready)
  ├── 9-stage pipeline (Stage 0-8) — INN-first architecture
  ├── Stage 0: Identity confirmation (EGRUL by INN + bankruptcy + business network)
  ├── INN required with checksum validation (10/12-digit)
  ├── DOB filtering in VK search + birth year patterns in Telegram/email
  ├── 14-step contact discovery chain (incl. 1b deep VK wall, 4b Hunter.io, 8a VK oracle)
  ├── Maigret + Sherlock + Snoop username search (parallel, Stage 5)
  ├── OpenSanctions + local MVD/extremist DBs (no geo-block)
  ├── checko.ru + casebook.ru (global FSSP/court alternatives)
  ├── Forgot-password oracle (8 services, VK account_existence_only)
  ├── Marketplace scanner (6 platforms, Avito Playwright phone extraction)
  ├── Deep VK wall mining (tagged post comments, Telegram/Instagram hints)
  ├── Hunter.io email verification + domain search
  ├── OK.ru search integration
  ├── Numeric confidence scoring (0.0-1.0) with cross-source boost
  ├── Security hardening (rate limiting + CSRF + security headers)
  ├── Docker deployment ready (Dockerfile + compose + deploy.sh + render.yaml)
  ├── ~8,050 lines dead code removed
  ├── All mock data removed — services return empty without keys
  └── 3,794+ tests passing, 0 failures
```
