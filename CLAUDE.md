# CLAUDE.md

## Project Overview

IBP (Identity-Based Profiler) is a unified OSINT investigation platform for Russian-speaking targets. It runs background checks by searching government registries, social networks, breach databases, and behavioral signals. INN (Russian Tax ID) is the primary required identifier.

- **Primary flow**: Candidate Check (`/candidate/start`) — 9-stage automated pipeline (INN required)
- **Legacy flow**: People Search — multi-phase manual investigation (routes still work, deprecated)
- **Stack**: Python 3.12, Flask 3.1, SQLAlchemy 2.0, SQLite, Playwright, Telethon, Tailwind CSS
- **Branch**: `main` = production-ready

## Platform Constraints

- Runs on **Windows 11**. NEVER use WeasyPrint, GTK, or Cairo-dependent libraries.
- PDF generation: **Playwright** or **reportlab** only.
- Always verify native dependency compatibility before adding libraries.

## Commands

```bash
python run.py                                                    # Dev server at http://127.0.0.1:5000
pip install -r requirements.txt                                  # Install deps
python -m pytest tests/ -v -p no:faulthandler                   # Run tests
python scripts/auth_telegram.py                                  # Telethon session auth (interactive)
python scripts/auth_telegram.py --check                          # Validate Telegram session
python scripts/auth_vk.py                                        # VK OAuth token (interactive)
python scripts/load_leaks.py vk_2012 ./data/raw/vk_2012.csv    # Load leak data
```

## The 9-Stage Pipeline (Stage 0-8)

Pipeline orchestrator: `app/services/candidate/pipeline.py`

| Stage | Name | % | Key Service | What It Does |
|-------|------|---|-------------|-------------|
| 0 | Identity Confirmation | 0-8 | `pipeline.py` + `business_registry.py`, `bankruptcy_service.py` | INN-first: EGRUL by INN, bankruptcy, business network. Sets `confirmed_name` for all subsequent stages |
| 1 | Government Registries | 8-18 | `fssp_service.py` + phase3 services | EGRUL by name, courts (sudact.ru), checko.ru, casebook.ru, FSSP fallback |
| 2 | Security Checks | 18-27 | `sanctions_check.py` | OpenSanctions, local MVD/extremist DBs, Interpol |
| 3 | Social Media Discovery | 27-42 | `phase1/buratino_vk_search.py`, `phase1/telegram_discovery.py`, `phase1/ok_search_integration.py` | VK (4 strategies + DOB filtering), Telegram (3 methods), OK.ru. Precise mode pauses here |
| 4 | Contact Discovery | 42-57 | `contact_discovery.py` | 11-step chain: VK extraction, wall mining, Telegram, business/FSSP, email guessing, Hunter.io, LeakDB, breach APIs, forgot-password oracle (8 services), marketplace mining (6 platforms), Holehe, dedup |
| 5 | Deep Social Analysis | 57-72 | `social_analysis.py` | Search4Faces, social graph (NetworkX + Louvain), Snoop, Maigret, Sherlock, YaSeeker. Feedback loop to Stage 4 |
| 6 | Behavioral Intelligence | 72-83 | `behavioral_analysis.py` | VK wall text analysis, geo extraction (98 Russian cities + text pattern matching from VK post text), activity timeline |
| 7 | Risk Scoring | 83-93 | `risk_scorer.py` | 9-category scoring (+ identity flags) -> CLEAN/LOW/MEDIUM/HIGH/CRITICAL |
| 8 | Report Generation | 93-100 | `report_builder.py` | Dossier with identity card, social graph, geo map, PDF/JSON export |

### Quick vs Precise Mode

- **Quick** (default): All stages run without pausing.
- **Precise**: Pauses after Stage 3 for user to confirm social profiles. Resumes with confirmed profiles only.

### Demo Mode

When `VK_SERVICE_TOKEN` is unset, VK returns fake profiles. OK.ru returns demo profiles when `OK_SESSION_TOKEN` is unset. Paid services return empty lists without keys. Currently `VK_SERVICE_TOKEN` **is set** (real data).

## Project Structure (files on disk)

```
app/
  __init__.py              # App factory, 13 blueprints, extensions
  models/
    candidate_check.py     # PRIMARY — 53 fields (incl. 7 task tracking), 9-stage JSON properties
    investigation.py       # Legacy Buratino model
    social_profile.py      # VK/OK/TG profiles linked to Investigation
    friend.py              # Social graph connections
    business_record.py     # EGRUL company affiliations
    court_record.py        # Court case records
    connection.py          # Cross-investigation links
  routes/
    candidate_check.py     # PRIMARY — /candidate/* (start, progress, confirm, dossier, export)
    api_search.py          # /api/search/* (VK + Telegram parallel search API)
    main.py                # /, /health, /vk/auth, /vk/callback
    auth.py                # /login, /logout
    phase1.py              # DEPRECATED — /phase1/* (VK+OK search)
    phase2.py              # DEPRECATED — /phase2/* (contact discovery)
    phase3.py              # DEPRECATED — /phase3/* (deep investigation)
    phase4.py              # DEPRECATED — graph visualization, people search
    report.py              # /report/* (identity cards, PDF/JSON/HTML)
    dossier.py             # /dossier/* (professional dossier view/export)
    scoring.py             # /api/scoring/* (risk scoring)
    connections.py         # /connections (cross-investigation analysis)
    timeline.py            # /timeline/* (activity timeline)
  services/
    candidate/             # 9-stage pipeline services
      pipeline.py          # Orchestrator (CandidateTaskStatus, run_full_pipeline)
      contact_discovery.py # Stage 4 — 11-step chain
      social_analysis.py   # Stage 5 — face search, social graph, username search
      behavioral_analysis.py # Stage 6 — text, geo, timeline
      risk_scorer.py       # Stage 7 — 9-category scoring
      report_builder.py    # Stage 8 — dossier compilation
      sanctions_check.py   # Stage 2 — OpenSanctions + local DBs + Interpol
      opensanctions_service.py # OpenSanctions API
      local_security_db.py # Offline MVD + extremist list
      fssp_service.py      # Stage 1 — FSSP (API -> Playwright -> manual)
      bankruptcy_service.py # Stage 0 — EFRSB bankruptcy
    phase1/                # Social media discovery (used by Stage 3)
      buratino_vk_search.py # VK People Search (4 strategies)
      telegram_discovery.py # Telegram (3 methods: VK cross-ref, guessing, Telethon)
      ok_search_integration.py # OK.ru search
      yandex_search.py     # Yandex People (CAPTCHA-prone)
      transliteration.py   # Multi-system Cyrillic<->Latin transliteration
      russian_diminutives.py # 78+ names with diminutive mappings
      fuzzy_matching.py    # Surname similarity + gender variants
      vk_web_search.py     # VK web scraping fallback + name verification
      combined_search.py   # Combines VK/TG/OK results
    phase2/                # Contact extraction (used by Stages 4-5)
      search4faces_service.py # Face search (API + Playwright fallback)
      telegram_crossref.py # t.me username checking + name verification
      vk_api_extractor.py  # VK profile contact extraction
      vk_wall_extractor.py # Deep VK wall mining (posts, comments, photos)
      email_generator.py   # Email patterns + Hunter.io
      email_discovery.py   # Email orchestration
      holehe_service.py    # Email verification (120+ services)
      forgot_password_oracle.py # Password recovery hints (8 services)
      marketplace_scanner.py # 6 Russian marketplaces (Avito: Playwright)
      breach_checker.py    # HudsonRock, LeakCheck, ProxyNova, HIBP
      social_graph.py      # NetworkX + Louvain community detection
      phone_discovery.py   # Phone orchestration
      phone_sources.py     # GetContact, NumBuster
      yaseeker_service.py  # Yandex Collections/Dzen/Music
      source_manager.py    # Contact discovery source execution
      # + 10 more supporting files (base_source, ok_checker, gravatar, etc.)
    phase3/                # Business/courts (used by Stages 0-1, 6)
      business_registry.py # EGRUL: nalog.ru + Rusprofile + list-org
      court_search.py      # sudact.ru (Playwright)
      checko_service.py    # checko.ru (global FSSP alternative)
      casebook_service.py  # casebook.ru (arbitration courts)
      fssp_search.py       # FSSP enforcement
      text_analyzer.py     # VK wall text analysis
      geo_extractor.py     # Geographic extraction
      combined_search.py   # Combines business/court/FSSP
      video_analyzer.py    # Video content analysis
    ai/
      claude_integration.py # Claude API: risk narrative, behavioral/executive summaries
    telegram/
      session_manager.py   # Telethon client lifecycle (singleton)
      bot_query.py         # Telegram bot queries
      config.py            # Telegram configuration
    # Top-level services:
    activity_timeline.py   # VK wall timestamp analysis
    connection_intelligence.py # Cross-investigation analysis
    dossier_generator.py   # Legacy dossier compilation
    report_generator.py    # Identity cards + PDF (reportlab)
    risk_scoring.py        # Legacy 7-dimension scoring
    snoop_search.py        # Snoop username search (5,372 sites)
    maigret_search.py      # Maigret username search (3,000+ sites)
    sherlock_search.py     # Sherlock username search (400+ sites)
    photo_investigation.py # Photo-first investigation flow
  templates/               # On disk (13 files):
    base.html              # Main layout (Tailwind + СЛЕД design system)
    home.html              # Candidate Check form
    login.html             # Auth screen (standalone, not extending base)
    people_search.html     # Two-column VK|Telegram search
    candidate_progress.html
    candidate_confirm_profiles.html
    candidate_dossier.html
    candidate_dossier_pdf.html
    candidate_history.html
    vk_callback.html
    error.html
    errors/404.html, errors/500.html
  utils/
    inn_validator.py       # INN checksum validation (10/12-digit)
    vk_token_manager.py    # VK dual-token management + OAuth
    startup_checks.py      # Boot-time validation of services/keys
    name_similarity.py     # Russian name matching
    phone.py               # Phone number parsing
    logger.py              # Logging config + token masking
  static/
    css/                   # СЛЕД design system (variables, base, components, animations)
    icons/                 # Platform icons (VK, Telegram, etc.)
    img/                   # Images
    reports/               # Generated reports
    uploads/               # User uploads
config.py                  # DevelopmentConfig / ProductionConfig / TestingConfig + load_env_config()
run.py                     # Flask server entry point
scripts/
  auth_telegram.py         # Telethon session auth (--check flag)
  auth_vk.py               # VK OAuth token acquisition
  load_leaks.py            # Populate local LeakDB
  update_mvd_list.py       # Update MVD wanted list
  update_extremist_list.py # Update extremist list
  load_all.sh              # Batch leak loading
data/
  mvd_wanted.json          # Offline MVD wanted list
  extremist_list.json      # Offline extremist list
  demo/                    # Demo leak data
  leaks/                   # Real leak database
  raw/                     # Raw import files
tests/
  unit/                            # 127 unit tests across 13 test files
  e2e/test_candidate_stress.py    # E2E stress tests (Playwright)
  security/test_security_audit.py # Security audit tests
```

**84 service files**, **13 route files**, **7 models**, **13 templates on disk**, **6 utility modules**.

## Database Models

| Model | Table | Purpose |
|-------|-------|---------|
| `CandidateCheck` | `candidate_checks` | **Primary** — 53 fields (incl. 7 task tracking), JSON properties for all 9 stages |
| `Investigation` | `investigations` | Legacy Buratino — multi-phase investigation |
| `SocialProfile` | `social_profiles` | VK/OK/TG profiles linked to Investigation |
| `Friend` | `friends` | Social graph with centrality_score, community_id |
| `BusinessRecord` | `business_records` | EGRUL company affiliations |
| `CourtRecord` | `court_records` | Court cases with risk scoring |
| `Connection` | `connections` | Cross-investigation entity links |

## Route Blueprints (13 active)

| Blueprint | Prefix | Key Endpoints | Status |
|-----------|--------|---------------|--------|
| `candidate_bp` | `/candidate` | start, progress, confirm, dossier, export, history, delete | **PRIMARY** |
| `api_search_bp` | `/api/search` | vk, telegram, save-selection, page | Active (People Search) |
| `main_bp` | `/` | index, health, vk/auth, vk/callback | Active |
| `auth_bp` | `/` | login, logout | Active |
| `report_bp` | `/report` | view, generate, download (html/pdf/json) | Active |
| `dossier_bp` | `/dossier` | view, json, pdf | Active |
| `scoring_bp` | `/` | calculate, breakdown, risk-report | Active |
| `connections_bp` | `/` | connections, analyze, graph-data | Active |
| `timeline_bp` | `/timeline` | view, api data | Active |
| `phase1_bp` | `/phase1` | new, search, confirm, refresh, photo-search | Deprecated but functional |
| `phase2_bp` | `/phase2` | analyze, start, progress, buratino | Deprecated but functional |
| `phase3_bp` | `/phase3` | start, progress, business/court/geo/text APIs | Deprecated but functional |
| `phase4_bp` | `/` | people search, graph, connections | Deprecated but functional |

## Async Task Pattern

All long-running operations run in background threads:
- `CandidateTaskStatus` — in-memory progress objects **+ DB-backed** for cross-worker visibility
- Task progress persisted to `CandidateCheck` model (7 `task_*` columns) via `_sync_to_db()` on every `task.update()` call
- Frontend polls `GET /candidate/progress/<task_id>/status` — reads in-memory first, falls back to DB (gunicorn multi-worker safe)
- `task_id` stored on `CandidateCheck` with indexed column for fast cross-worker lookup
- Auto-migration adds task columns to existing databases on startup (`_migrate_task_columns()`)
- Cancel via status flag. Auto-cleanup after 3600s.
- Max 10 concurrent candidate checks.

## Frontend Stack

- Tailwind CSS via CDN + custom СЛЕД design system (dark theme, violet accent)
- vis.js — social graph + connections visualization
- Chart.js — risk radar charts
- Leaflet.js — geo heatmap
- Vanilla JS — AJAX polling, form handling
- Fonts: Outfit (body), IBM Plex Mono (data)

## Data Sources

### Globally Accessible (no geo-block, no paid keys)
nalog.ru EGRUL, sudact.ru courts, checko.ru (FSSP), casebook.ru (arbitration), bankrot.fedresurs.ru (bankruptcy), OpenSanctions, Interpol, local MVD/extremist DBs, VK API (with token), Telegram (with session), HudsonRock, LeakCheck Public, ProxyNova COMB, HIBP (k-anonymity), Holehe, Snoop, Maigret, Sherlock, YaSeeker

### Needs Keys or Russian IP
FSSP API (Russian IP), Rosfinmonitoring/MVD/Extremist live scrapers (Russian IP), Gosuslugi/Sberbank oracle (Russian IP), Snusbase ($5-16/mo), DeHashed ($5.49/mo), LeakCheck Pro ($2.99-24.99/mo), HIBP Paid ($3.50/mo), GetContact, NumBuster, Search4Faces API ($40+/mo), Hunter.io (25/mo free tier)

## API Keys & Environment Variables

```bash
# Required
SECRET_KEY=...                  # Flask session secret

# VK (dual-token)
VK_SERVICE_TOKEN=...            # Permanent app token for search (SET)
VK_USER_TOKEN=...               # User OAuth for private data (wall, friends, photos)
VK_APP_ID=...                   # For OAuth (SET)
VK_TOKEN=...                    # Legacy fallback

# Telegram
TELEGRAM_API_ID=...             # From my.telegram.org (SET)
TELEGRAM_API_HASH=...           # (SET)
TELEGRAM_PHONE=...              # (SET)

# Optional
ANTHROPIC_API_KEY=...           # Claude AI summaries (pipeline works without)
OK_SESSION_TOKEN=...            # OK.ru real search (demo if unset)
IBP_PASSWORD=...                # App login (no auth if unset)
SEARCH4FACES_API_KEY=...        # Paid face search (Playwright fallback if unset)
HUNTER_API_KEY=...              # Corporate emails (25/mo free)
OSINT_TOOLS_DIR=...             # Snoop/Maigret/Sherlock path
ENABLE_GEO_RESTRICTED_CHECKERS=1 # Enable Gosuslugi+Sberbank (Russian IP only)
```

## VK Dual-Token Architecture

| Token | Variable | Methods | How to Get |
|-------|----------|---------|------------|
| Service | `VK_SERVICE_TOKEN` | users.search, users.get | VK app settings |
| User | `VK_USER_TOKEN` | wall.get, friends.get, photos.getAll | `python scripts/auth_vk.py` |
| Legacy | `VK_TOKEN` | Fallback for user token | VK OAuth (24h expiry) |

Priority: `VK_USER_TOKEN` -> `VK_TOKEN` -> `VK_SERVICE_TOKEN` -> demo mode.
Helper: `from app.utils.vk_token_manager import get_vk_token` — `get_vk_token('search')` / `get_vk_token('private')`

## Telegram Search (3 Methods)

Service: `app/services/phase1/telegram_discovery.py` (TelegramDiscoveryService)

| Method | What | Source |
|--------|------|--------|
| A | VK Cross-Reference: check t.me/{vk_screen_name} | VK results |
| B | Username Guessing: transliterate name, generate patterns, check t.me | Name input |
| C | Telethon Directory Search: contacts.SearchRequest by name | Telegram API |

Rate limit: 0.35s between t.me checks. Telethon: 1s between API calls.
Auth: `python scripts/auth_telegram.py` (one-time, creates `tg_session/ibp_session.session`)

## Name Matching System

- `app/services/phase1/russian_diminutives.py` — 78+ formal names with diminutive mappings (bidirectional)
- `app/services/phase1/transliteration.py` — Multi-system Cyrillic<->Latin (GOST, BGN/PCGN, passport, informal)
- `app/services/phase1/fuzzy_matching.py` — Surname similarity with gender variant handling
- `app/services/phase1/vk_web_search.py` — `verify_profile_name_matches_query()` (last name >= 0.7, first name >= 0.65 or diminutive match)

## Web Scraping Strategy

- API/AJAX first, Playwright only as fallback.
- Assume CAPTCHA will appear. Build fallback chain: API -> AJAX -> Playwright -> Manual link.
- FSSP: 2-attempt Playwright retry with 3s delay.
- Rusprofile: graceful 403/404/429 handling.
- VK: intercept API calls, not DOM parsing.

## Security

- Global `@app.before_request` auth check with session timeout
- Session fixation protection
- CSP, X-Frame-Options, HSTS, nosniff headers via `@app.after_request`
- CSRF protection (Flask-WTF)
- Rate limiting (Flask-Limiter, 120/min default)
- All user inputs sanitized (HTML tag stripping, length limits)
- Open redirect protection in login flow
- bcrypt password hashing with caching

## Testing

**127 unit tests** across 13 test files in `tests/unit/`, plus E2E stress tests (`tests/e2e/test_candidate_stress.py`) and security audit tests (`tests/security/test_security_audit.py`). Previous test suite (69 files, 3,794+ tests) was cleaned up; unit tests rebuilt during bug-fixing sessions.

```bash
python -m pytest tests/ -v -p no:faulthandler
```

Use `-p no:faulthandler` on Windows to avoid I/O capture bugs.

## Known Issues

1. **pytest capture bug on Windows**: Use `-p no:faulthandler`. Run files individually if stdout crashes.
2. **FSSP API SSL errors**: Persistent at api-ip.fssp.gov.ru. Playwright retry + manual URL fallback.
3. **kad.arbitr.ru geo-blocked**: HTTP 451. Replaced by casebook.ru.
4. **Holehe slow**: ~25s per email. Pipeline has 120s timeout for Stage 4.
5. **pymorphy2 Python 3.12+**: Uses `inspect.getfullargspec` shim.
6. **WeasyPrint forbidden**: PDF via Playwright or reportlab only.
7. **SocialProfile.full_name**: Property, not a setter. Use first_name/last_name/display_name.
8. **Rusprofile anti-bot**: 403/429 under load. Falls through to nalog.ru EGRUL.
9. **Forgot-password oracle geo-blocking**: Gosuslugi/Sberbank skipped unless `ENABLE_GEO_RESTRICTED_CHECKERS=1`.
10. **Many legacy templates deleted**: Phase 1-3 routes render templates that no longer exist on disk. Only candidate pipeline templates are current.
11. **Interpol API intermittent 502**: Returns 502/503 under load. Handled with graceful fallback message (fixed March 2026).
12. **sudact.ru court case regex** (fixed March 2026): Case number regex missed Cyrillic letters (e.g., `2А-1853/2025` for administrative cases). Fixed from `\d{1,2}-\d+/\d{4}` to `\d{1,2}[А-Яа-я]{0,3}-\d+/\d{4}` in 5 locations. sudact.ru accessible (HTTP 200), Playwright renders results.
13. **FSSP CAPTCHA-blocked**: All automated strategies (API, AJAX, Playwright) blocked by CAPTCHA. Manual fallback works (`source='manual'`). Need `FSSP_API_TOKEN` from https://api-ip.fssp.gov.ru or Russian IP to bypass. checko.ru fixed (March 2026): URL changed from `/person` (404) to `/search` (200).
14. **Telegram Method C session file**: Telethon works but needs interactive session creation. Run `python scripts/auth_telegram.py` interactively. Session file: `tg_session/ibp_session.session` (not yet created, requires interactive auth).
15. **ё/е normalization** (fixed March 2026): Was causing valid Russian name matches to score 0.0 (e.g., "Артём" vs "Артем"). Added `_normalize_yo()` to `telegram_discovery.py` and `telegram_crossref.py`.

## Deprecated Code (still functional)

**Routes**: `phase1_bp`, `phase2_bp`, `phase3_bp`, `phase4_bp` — functional but superseded by Candidate Check pipeline.

**Services**: The underlying phase1/phase2/phase3 service files are NOT deprecated — they are actively imported by the candidate pipeline.

**Templates**: Most legacy templates (`phase1_buratino_*.html`, `phase2*.html`, `phase3*.html`, etc.) have been deleted from disk. Legacy routes that render them will 500.

## Git Workflow

- Commit and push after completing implementation work unless told otherwise.
- Conventional commit prefixes: `feat:`, `fix:`, `chore:`, `docs:`, `security:`, `test:`
- `main` = production branch. Feature branches off main.

## File Targeting

Before editing any template or file, confirm it exists with `ls`. This project had many similar files; several have been deleted. Never assume — verify first.
