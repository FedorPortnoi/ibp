# IBP Current State

## Last Updated
2026-03-16

## What Works

### Candidate Check Pipeline (Primary)
- 9-stage pipeline (Stage 0-8) fully implemented and functional
- INN-first architecture with checksum validation
- Quick mode (all stages automatic) and Precise mode (pauses for profile confirmation)
- Background thread execution with progress polling
- PDF export via Playwright, JSON export
- Professional dossier view with identity card, social graph, geo map
- History page with past checks
- Demo mode fallbacks for all stages

### People Search (Legacy)
- Two-column VK | Telegram search via `/api/search/page`
- VK: 4 search strategies (name, name+city, name+age, screen_name) via API
- Telegram: 3 methods (VK cross-ref, username guessing, Telethon directory search)
- Sequential flow: VK first, then Telegram with VK screen_names
- Profile selection and investigation creation

### Government Registries
- nalog.ru EGRUL (free API, works globally)
- sudact.ru court cases (Playwright scraping)
- checko.ru enforcement proceedings (globally accessible)
- casebook.ru arbitration courts (globally accessible)
- EFRSB bankruptcy (API + Playwright fallback)
- FSSP: 4-tier fallback (API -> AJAX -> Playwright 2-attempt -> manual URL)

### Security Checks
- OpenSanctions API (primary, global)
- Local MVD wanted list (data/mvd_wanted.json)
- Local extremist list (data/extremist_list.json)
- Interpol REST API

### Contact Discovery (11-step chain)
- VK profile extraction + deep wall mining
- Telegram profile data
- Email guessing (transliteration + corporate patterns)
- Breach APIs (HudsonRock, LeakCheck, ProxyNova)
- Forgot-password oracle (6 global services + 2 geo-restricted)
- Marketplace mining (6 platforms, Avito Playwright extraction)
- Holehe email verification (120+ services)
- Cross-source deduplication with confidence boost

### Social Analysis
- Search4Faces (paid API + free Playwright fallback)
- Social graph (NetworkX + Louvain community detection + vis.js)
- Snoop username search (5,372 sites)
- YaSeeker (Yandex services)

### Authentication & Security
- Password-only auth with bcrypt
- Session management with timeout and fixation protection
- Security headers (CSP, HSTS, X-Frame-Options)
- Rate limiting on all sensitive endpoints
- CSRF protection
- Input sanitization (HTML tag stripping)

### Infrastructure
- Health check endpoint (/health) with service status
- VK OAuth flow for token management
- Telethon session management
- Startup validation checks

## What's Partially Built

- **Maigret/Sherlock integration**: Code exists, runs if installed via pip or OSINT_TOOLS_DIR. Not bundled.
- **Yandex People Search**: File exists (`yandex_search.py`), called from pipeline, but CAPTCHA-prone and may timeout.
- **OK.ru search**: Works in demo mode. Real search needs `OK_SESSION_TOKEN` cookie.
- **Claude AI summaries**: Wired into pipeline stages 1, 6, 7, 8. Returns None without `ANTHROPIC_API_KEY`.
- **Paid breach APIs**: Snusbase, DeHashed, LeakCheck Pro, HIBP Paid — code wired, returns empty without keys.
- **Phone lookup services**: GetContact, NumBuster — code wired, returns empty without keys.
- **Legacy Phase 1-3 routes**: Functional code but most templates deleted from disk. Will 500 on template render.
- **Video analyzer**: File exists (`phase3/video_analyzer.py`), status unclear.

## What's Not Built / Planned

- Mobile/responsive optimization beyond basic Tailwind
- Multi-user accounts / role-based access
- Automated report scheduling
- WhatsApp / Max (VK Messenger) search
- API-only mode for external integrations

## Recent Commits (last 20)

```
2847092 docs: add security hardening report
67f30d8 security: comprehensive hardening — XSS, injection, rate limits, session management
1c4750b security: audit findings — fix HIGH/MEDIUM vulnerabilities, add security headers
536073f fix: handle as_completed TimeoutError in contact discovery, sanctions, source manager
4b9caa4 test: E2E stress test results — 60 cycles, 48 PASS
a2046d3 fix: handle as_completed timeout in gov registries + improve E2E test reliability
f7c51d3 feat: multi-page site structure with scroll-triggered page transitions
6ab5f77 feat: СЛЕД design system — lusion.co-inspired UI redesign
6222f34 chore: clean root directory — remove junk, dev artifacts, stale docs
b2a4433 chore: production deployment prep — remove dev scripts, fix headless, Dockerfile
605b2ca session checkpoint: INN-first pipeline complete, all tests passing
be4cbf3 fix: complete plan gaps — risk scoring enhancements, docs update, live E2E test
2cce0ca docs: update CLAUDE.md — 9-stage pipeline with Stage 0 identity confirmation
0aceb92 test: INN validation + Stage 0 pipeline tests + regression fixes
0e70299 feat: risk scoring identity flags + dossier identity section
35a1ac9 feat: contact discovery — birth year email/TG patterns, confirmed_name propagation
bb7175d feat: VK search with DOB filtering — birth_day/month/year params + confidence boost
95efd47 feat: Stage 0 — identity confirmation via INN (EGRUL + bankruptcy + business network)
1f2ed75 feat: INN required — model, validation, form update
5d61bd8 docs: update CLAUDE.md — dual-token architecture, auth scripts, Search4Faces API
```

## Active Issues

1. Legacy phase routes (phase1_bp, phase2_bp, phase3_bp) render deleted templates — will 500 if accessed
2. Only 2 test files remain on disk (stress + security). Unit/integration tests were cleaned up.
3. FSSP API has persistent SSL errors — relies on checko.ru as primary source
4. Holehe is slow (~25s/email) — pipeline has 120s timeout for Stage 4
5. Yandex People search is unreliable (CAPTCHA)

## Test Status

- 2 test files on disk: `tests/e2e/test_candidate_stress.py`, `tests/security/test_security_audit.py`
- Previous full suite (69 files, 3,794+ tests) was cleaned up during production prep
- Use `-p no:faulthandler` on Windows

## TODO Comments in Code

The following files contain TODO markers for unimplemented paid API integrations:
- `app/services/phase2/sources/breach_api.py` — Snusbase, DeHashed, HIBP paid API calls (lines 356, 535, 678, 741)
- `app/services/phase2/sources/getcontact.py` — NumBuster API call (line 470)
- `app/services/phase2/sources/telegram_bot.py` — Telegram bot queries, Himera API, InfoTrackPeople API (lines 59, 111, 147)

These are all stub implementations that log the intended API call and return empty results. They work correctly in "no key" mode.

## Dead Imports (Handled Gracefully)

- `app/routes/phase4.py:44` — imports `app.services.phase4.research_orchestrator` which doesn't exist. Wrapped in `try/except ImportError`, so it falls through to VK/OK/Telegram search fallback. Not a crash risk.

## API Keys Status (Current Environment)

| Key | Status |
|-----|--------|
| SECRET_KEY | SET |
| VK_SERVICE_TOKEN | SET (real mode) |
| VK_APP_ID | SET |
| TELEGRAM_API_ID/HASH/PHONE | SET |
| IBP_PASSWORD | SET |
| VK_USER_TOKEN | Not set (private VK data inaccessible) |
| OK_SESSION_TOKEN | Not set (demo mode) |
| ANTHROPIC_API_KEY | Not set (no AI summaries) |
| SEARCH4FACES_API_KEY | Not set (Playwright fallback) |
| All paid breach APIs | Not set (empty results) |
