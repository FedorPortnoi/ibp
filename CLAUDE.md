# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Project Overview

IBP (Identity-Based Profiler) is a unified OSINT investigation platform for Russian-speaking targets. The core feature is a **single 9-stage (Stage 0-8) Candidate Check pipeline** that runs background checks by searching government registries, social networks, breach databases, and behavioral signals. INN (Russian Tax ID) is the primary required identifier.

- **Primary flow**: Candidate Check (`/candidate/start`) — 9-stage automated pipeline (INN required)
- **Legacy flow**: People Search (Buratino) — 3-phase manual investigation (routes still work, deprecated)
- **Stack**: Python Flask + SQLite + Playwright + VK API + Tailwind CSS
- **Deployment**: Render free tier, Frankfurt region (ibp-osint.onrender.com)
- **Branch**: `main` = production-ready

## Platform Constraints

- This project runs on **Windows**. NEVER use WeasyPrint, GTK, or Cairo-dependent libraries.
- For PDF generation: use **Playwright** (installed) or **reportlab**. Never try WeasyPrint or xhtml2pdf.
- Always verify native dependency compatibility before suggesting any new library.

## The 9-Stage Pipeline (Stage 0-8)

The pipeline lives in `app/services/candidate/pipeline.py`:

| Stage | Name | % | Key Service | What It Does |
|-------|------|---|-------------|-------------|
| 0 | Identity Confirmation | 0-8 | `pipeline.py` (inline) + `business_registry.py`, `bankruptcy_service.py` | **INN-first**: EGRUL lookup by INN, bankruptcy by INN, linked companies deep dive, business network extraction, identity confirmation report. Sets `confirmed_name` used by all subsequent stages. |
| 1 | Government Registries | 8-18 | `fssp_service.py` + phase3 services | EGRUL by name (merged with Stage 0 INN results), courts (sudact.ru), FSSP enforcement (2-attempt Playwright retry) |
| 2 | Security Checks | 18-27 | `sanctions_check.py` | Rosfinmonitoring, MVD wanted, Interpol, extremist list |
| 3 | Social Media Discovery | 27-42 | `phase1/buratino_vk_search.py`, `phase1/telegram_discovery.py`, `phase1/ok_search_integration.py` | VK People Search (4 strategies + DOB filtering), Telegram (3 methods + birth year username patterns), OK.ru search. **Precise mode**: pauses here for profile confirmation |
| 4 | Contact Discovery | 42-57 | `contact_discovery.py` | 14-step chain: VK extraction, deep VK wall mining, Telegram, business/FSSP, email guessing (with birth year patterns), Hunter.io corporate, LeakDB, breach APIs, LeakDB cross-ref, forgot-password oracle (8 services), marketplace mining (6 platforms, Avito Playwright phone extraction), Holehe, dedup with cross-source boost. Uses `confirmed_name` for name-based lookups. |
| 5 | Deep Social Analysis | 57-72 | `social_analysis.py` | Search4Faces (3 DBs), social graph (NetworkX + Louvain), Snoop (5,372 sites), YaSeeker. Feedback loop: new accounts re-enter Stage 4 |
| 6 | Behavioral Intelligence | 72-83 | `behavioral_analysis.py` | VK wall text analysis (sentiment/keywords), geo extraction (100 Russian cities), activity timeline |
| 7 | Risk Scoring | 83-93 | `risk_scorer.py` | 9-category dimensional scoring (+ identity flags) → CLEAN/LOW/MEDIUM/HIGH/CRITICAL |
| 8 | Report Generation | 93-100 | `report_builder.py` | Compiles dossier with all stage data, identity card, identity confirmation section, social graph, geo map, PDF/JSON export |

### Contact Discovery 11-Step Chain (Stage 4)

| Step | What | Confidence |
|------|------|------------|
| 1 | VK profile contacts (mobile_phone, site, about, status) | 0.95 |
| 1b | Deep VK wall mining (posts, comments, tagged posts + their comments, photo comments, mentions) | 0.85 / 0.70 |
| 2 | Telegram profile data | 0.85 |
| 3 | Business (EGRUL) / FSSP records | 0.50 / 0.45 |
| 4 | Email guessing (username + name transliteration + corporate patterns) | 0.40 |
| 4b | Hunter.io corporate email verification (if employer known from VK career) | 0.80 |
| 5 | LeakDB name lookup (local breach data) | 0.65 |
| 6 | Breach API enrichment (HudsonRock, LeakCheck, ProxyNova) | 0.60 |
| 7 | LeakDB cross-reference (snowball: phone→email, email→phone) | 0.55 |
| 8 | Forgot-password oracle (VK, Mail.ru, Yandex, OK, Gosuslugi, TG, Avito, Sberbank) | 0.78-0.90 |
| 9 | Marketplace mining (Avito, Youla, CIAN, Auto.ru, Yandex, VK Market) | 0.90 |
| 10 | Holehe email verification (120+ services) | 0.80 |
| 11 | Deduplicate + merge sources + cross-source boost (+0.15 for 3+ sources, max 0.98) | — |

### Confidence Scoring

Numeric scores 0.0-1.0 stored in `CONFIDENCE_SCORES` dict. Each contact has:
- `confidence_score`: numeric value
- `confidence`: Russian label (`высокая` >=0.75, `средняя` >=0.50, `низкая` <0.50)
- `sources`: list of all sources that independently found this contact

Helper functions: `_score_to_label()`, `_label_to_score()`, `_get_score(source_key)`

### Quick vs Precise Mode

- **Quick** (default): Runs all 8 stages without pausing. Uses all social profiles found.
- **Precise**: Pauses after Stage 3. Shows found VK/Telegram/OK profiles for user confirmation. Resumes with confirmed profiles only.

### Demo Mode

When `VK_SERVICE_TOKEN` is not set, VK search returns 3 fake profiles and social graph returns 8 fake friends. OK.ru returns 3 demo profiles when `OK_SESSION_TOKEN` is unset. All paid services return **empty lists** when their keys are not set (no fake data). Currently VK_SERVICE_TOKEN **is set**, so real data flows.

## Key Files (most important first)

| File | Purpose |
|------|---------|
| `app/services/ai/claude_integration.py` | Claude AI integration: risk narrative, behavioral summary, executive summary, court case interpretation |
| `app/services/candidate/pipeline.py` | 9-stage orchestrator (Stage 0-8), CandidateTaskStatus, progress tracking |
| `app/models/candidate_check.py` | Main model (~30 fields), JSON property getters/setters for all stages, identity confirmation fields |
| `app/routes/candidate_check.py` | All endpoints: /start (INN required + checksum validation), /progress, /confirm, /dossier, /export |
| `app/utils/inn_validator.py` | Russian INN checksum validation (10-digit legal, 12-digit individual) |
| `app/services/candidate/social_analysis.py` | Stage 5: face search + social graph + Snoop + Maigret + Sherlock + YaSeeker |
| `app/services/candidate/behavioral_analysis.py` | Stage 6: text analysis + geo extraction + timeline |
| `app/services/candidate/contact_discovery.py` | Stage 4: 14-step chain (incl. 1b deep VK wall, 4b Hunter.io) + supplementary discovery for feedback loop |
| `app/services/candidate/risk_scorer.py` | Stage 7: 8 risk categories, severity levels, composite scoring |
| `app/services/candidate/report_builder.py` | Stage 8: compiles all data into report structure |
| `app/services/candidate/bankruptcy_service.py` | Stage 1: EFRSB API + Playwright fallback |
| `app/services/candidate/sanctions_check.py` | Stage 2: OpenSanctions + local DBs + Interpol + fallback scrapers |
| `app/services/candidate/opensanctions_service.py` | Stage 2: OpenSanctions API — global sanctions database |
| `app/services/candidate/local_security_db.py` | Stage 2: Local MVD + Extremist list JSON databases |
| `app/services/candidate/fssp_service.py` | Stage 1: 4-tier fallback (API → AJAX → Playwright with 2-attempt retry → manual URL) |
| `app/services/phase3/checko_service.py` | Stage 1: checko.ru enforcement proceedings (global FSSP alternative) |
| `app/services/phase3/casebook_service.py` | Stage 1: casebook.ru arbitration courts (global kad.arbitr.ru alternative) |
| `app/services/maigret_search.py` | Stage 5: Maigret username search (3,000+ sites) |
| `app/services/sherlock_search.py` | Stage 5: Sherlock username search (400+ sites) |
| `app/services/phase2/forgot_password_oracle.py` | Stage 4 Step 8: password recovery hints from 8 Russian services (VK is account_existence_only) |
| `app/services/phase2/marketplace_scanner.py` | Stage 4 Step 9: mining 6 Russian marketplace platforms (Avito: Playwright phone extraction) |
| `app/services/phase1/buratino_vk_search.py` | VK search engine (4 strategies), used by Stage 3 |
| `app/services/phase1/telegram_discovery.py` | Telegram search (3 methods), used by Stage 3 |
| `app/services/phase1/ok_search_integration.py` | OK.ru search with demo fallback, used by Stage 3 and Phase 1 route |
| `app/services/phase2/vk_wall_extractor.py` | Deep VK wall mining: posts, comments, tagged posts + tagged post comments, photo comments, social fields. Wired into Stage 4 Step 1b |
| `app/services/phase2/email_generator.py` | Email patterns: username, transliteration, corporate, Skype-to-email + Hunter.io verify/domain search |
| `config.py` | DevelopmentConfig / ProductionConfig / TestingConfig |
| `run.py` | Flask server entry point |

## Data Sources Status

### Stage 1: Government Registries
| Source | Status | Notes |
|--------|--------|-------|
| nalog.ru EGRUL | WORKS | Free government API, 2-step token flow, ~20 results/name |
| sudact.ru courts | WORKS | Playwright scraping, 8-10 cases/name, ~5s |
| **checko.ru** | WORKS | **Primary** FSSP alternative. Globally accessible, no geo-block |
| casebook.ru | WORKS | Arbitration court aggregator. Replaces geo-blocked kad.arbitr.ru |
| FSSP enforcement | FALLBACK | Fallback behind checko.ru. API has SSL errors; Playwright retry (2 attempts). Needs Russian IP |
| EFRSB bankruptcy | WORKS | bankrot.fedresurs.ru API + Playwright fallback |
| Rusprofile.ru | WORKS | Fallback for EGRUL. Uses `type=fl` person search. Graceful 403/404/429 handling |
| kad.arbitr.ru | GEO-BLOCKED | HTTP 451, replaced by casebook.ru |

### Stage 2: Security Checks
| Source | Status | Notes |
|--------|--------|-------|
| **OpenSanctions API** | WORKS | **Primary**. Free, global, covers Rosfinmonitoring + OFAC + EU + UN + Interpol |
| Local MVD database | WORKS | Offline MVD wanted list (`data/mvd_wanted.json`). Update via `scripts/update_mvd_list.py` |
| Local Extremist list | WORKS | Offline extremist list (`data/extremist_list.json`). Update via `scripts/update_extremist_list.py` |
| Interpol | WORKS | REST API, works globally |
| Rosfinmonitoring | FALLBACK | Web scraping fallback. Needs Russian IP |
| MVD Wanted | FALLBACK | Web scraping fallback. Needs Russian IP |
| Extremist list | FALLBACK | Web scraping fallback. Needs Russian IP |

### Stage 3: Social Media
| Source | Status | Notes |
|--------|--------|-------|
| VK People Search | WORKS | 4 strategies via buratino_vk_search. Needs VK_SERVICE_TOKEN (set) |
| Telegram | WORKS | 3 methods. Needs TELEGRAM_API_ID/HASH/PHONE (set) |
| OK.ru (Odnoklassniki) | WORKS | Web scraping + demo mode. Set OK_SESSION_TOKEN for real search |
| Yandex People | DEMO | Playwright + CAPTCHA detection. Called from pipeline but may timeout |

### Stage 4: Contact Discovery
| Source | Status | Notes |
|--------|--------|-------|
| VK profile extraction | WORKS | users.get API with expanded fields (Instagram, Skype, career, etc.) |
| VK wall mining | WORKS | Posts, comments, tagged posts (filter=others) + their comments, photo comments. Wired into Stage 4 Step 1b |
| Email pattern generation | WORKS | Username + transliteration + corporate + Skype-to-email (confidence 0.40) |
| Hunter.io email verification | WIRED | Free tier: 25/month. Corporate email discovery from VK career data. Set HUNTER_API_KEY |
| Holehe verification | WORKS | 120+ services, ~25s per email. CPU-intensive |
| HudsonRock Cavalier | WORKS | Free, no API key. Infostealer logs |
| LeakCheck Public | WORKS | Free, no key. 12B+ records |
| ProxyNova COMB | WORKS | Free, no key. 3.2B email:password pairs |
| HIBP Pwned Passwords | WORKS | Free, k-anonymity |
| Forgot-password oracle | WORKS | 6 global (VK account_existence_only, Mail.ru, Yandex, OK, TG, Avito) + 2 geo-restricted (Gosuslugi, Sberbank, skip by default) |
| Marketplace scanner | WORKS | 6 platforms (Avito, Youla, CIAN, Auto.ru, Yandex, VK Market). Avito: Playwright phone extraction + city data |
| Snusbase | WIRED | Returns empty without key. Set SNUSBASE_API_KEY to activate ($5-16/mo) |
| DeHashed | WIRED | Returns empty without keys. Set DEHASHED_EMAIL + DEHASHED_API_KEY ($5.49/mo) |
| LeakCheck Pro | WIRED | Free public tier auto. Set LEAKCHECK_API_KEY for full results ($2.99-24.99/mo) |
| HIBP Paid | WIRED | Free k-anonymity auto. Set HIBP_API_KEY for email breach lookup ($3.50/mo) |
| GetContact | WIRED | Returns empty without key. Set GETCONTACT_API_KEY or legacy TOKEN+AES_KEY+DEVICE_ID |
| NumBuster | WIRED | Returns empty without key. Set NUMBUSTER_API_KEY to activate |
| Local LeakDB | WORKS | Auto-loads demo data (data/demo/) if DB empty. Real data via scripts/load_leaks.py |

### Stage 5: Social Analysis
| Source | Status | Notes |
|--------|--------|-------|
| Search4Faces | WORKS | JSON-RPC API (paid, SEARCH4FACES_API_KEY) + Playwright browser fallback (free). 3 databases (vkok, vk01, vkokn) |
| Social graph | WORKS | VK friends → NetworkX → Louvain → vis.js |
| Snoop username search | WORKS | 5,372 sites, Russian-filtered. Uses `OSINT_TOOLS_DIR` env var for path |
| Maigret username search | WIRED | 3,000+ sites. pip install or OSINT_TOOLS_DIR. Runs in parallel with Snoop |
| Sherlock username search | WIRED | 400+ sites. pip install or OSINT_TOOLS_DIR. Runs in parallel with Snoop |
| YaSeeker | WORKS | Yandex Collections, Dzen, Music |

### Stage 6: Behavioral Analysis
| Source | Status | Notes |
|--------|--------|-------|
| Text analysis | WORKS | VK wall post sentiment/keywords/topics |
| Geo extraction | WORKS | 100 hardcoded Russian cities + postal codes |
| Activity timeline | WORKS | Post timestamps + check events |

### Stage 7-8: Scoring & Reports
| Component | Status |
|-----------|--------|
| 8-category risk scorer | WORKS |
| HTML dossier | WORKS |
| PDF export (Playwright) | WORKS |
| JSON export | WORKS |

## API Keys & Environment Variables

```bash
# === REQUIRED ===
SECRET_KEY=...                  # Flask session secret (REQUIRED)

# === AI INTEGRATION (optional) ===
ANTHROPIC_API_KEY=...           # Claude API key for AI summaries. Pipeline works without it.

# === VK API (dual-token architecture) ===
VK_SERVICE_TOKEN=...            # Permanent app token for search (users.search, users.get). Demo mode if unset. Currently SET.
VK_USER_TOKEN=...               # User OAuth token for private data (wall.get, friends.get, photos.getAll). Get via: python scripts/auth_vk.py
VK_APP_ID=...                   # For OAuth. Currently SET.
VK_TOKEN=...                    # Legacy fallback (treated as user token if VK_USER_TOKEN unset)
VK_LOGIN=...                    # VK web login (fallback for web search)
VK_LOGIN_EMAIL=...              # VK email for auto-login
VK_PASSWORD=...                 # VK password for auto-login

# === TELEGRAM (enables Stage 3 Telegram search) ===
TELEGRAM_API_ID=...             # From my.telegram.org/apps. Currently SET.
TELEGRAM_API_HASH=...           # Currently SET.
TELEGRAM_PHONE=...              # Currently SET.

# === OK.RU (enables real OK.ru search in Stage 3) ===
OK_SESSION_TOKEN=...            # OK.ru session cookie. Demo mode (3 fake profiles) if unset.

# === OPTIONAL ===
FSSP_API_TOKEN=...              # FSSP enforcement API (Russian IP required). Playwright retry + manual fallback without.
IBP_PASSWORD=...                # App login password. App runs without auth if unset.
IBP_PASSWORD_HASH=...           # bcrypt hash alternative. Takes precedence.
IBP_SESSION_TIMEOUT=3600        # Session timeout seconds
IBP_SESSION_REMEMBER=2592000    # "Remember me" timeout seconds

# === PAID BREACH APIs (return empty without keys) ===
SNUSBASE_API_KEY=...            # $5-16/mo. Empty results if unset.
DEHASHED_EMAIL=...              # $5.49/mo. Both email+key needed. Empty if unset.
DEHASHED_API_KEY=...
LEAKCHECK_API_KEY=...           # $2.99-24.99/mo. Free public tier if unset.
HIBP_API_KEY=...                # $3.50/mo. Free k-anonymity if unset.

# === PHONE LOOKUP (return empty without keys) ===
GETCONTACT_API_KEY=...          # Simple API key mode. Empty if unset.
GETCONTACT_TOKEN=...            # Legacy: rooted Android credentials
GETCONTACT_AES_KEY=...
GETCONTACT_DEVICE_ID=...
NUMBUSTER_API_KEY=...           # Empty if unset.
HIMERA_API_KEY=...

# === FACE SEARCH (optional paid tier) ===
SEARCH4FACES_API_KEY=...        # $40+/mo JSON-RPC API. Playwright browser fallback if unset (free).

# === PAID EMAIL APIs (wired) ===
HUNTER_API_KEY=...              # Free tier: 25/month. SMTP fallback if unset.
EMAILREP_API_KEY=...
SNOV_CLIENT_ID=...
SNOV_CLIENT_SECRET=...

# === LOCAL LEAK DATABASE ===
LEAKDB_DATA_DIR=...             # Default: data/demo/ (ships with fake data)

# === GEO-RESTRICTED SERVICES ===
ENABLE_GEO_RESTRICTED_CHECKERS= # Set to "1" for Russian IP. Enables Gosuslugi + Sberbank oracle checkers.

# === OSINT TOOLS ===
OSINT_TOOLS_DIR=...             # Path to osint_tools dir (snoop, maigret, sherlock). Default: ~/osint_tools

# === OTHER ===
GITHUB_TOKEN=...                # GitHub profile lookups
INFOTRACKPEOPLE_API_KEY=...
DATABASE_URL=...                # Default: sqlite:///ibp.db
FLASK_ENV=development           # development / production / testing
```

## Commands

```bash
# Run development server (http://127.0.0.1:5000)
python run.py

# Install dependencies
pip install -r requirements.txt

# Run tests (use -p no:faulthandler on Windows to avoid capture bugs)
python -m pytest tests/ -v -p no:faulthandler

# Run specific test file
python -m pytest tests/test_candidate_unified.py -v -p no:faulthandler

# Load leak data into local DB
python scripts/load_leaks.py vk_2012 ./data/raw/vk_2012.csv
python scripts/load_leaks.py getcontact ./data/raw/getcontact.jsonl --dedup
python scripts/load_leaks.py telco ./data/raw/beeline.csv --carrier beeline
```

## Test Infrastructure

- **69 test files**, **~3,018 test functions** of test code
- **3,794+ tests pass**, 0 failures, 0 errors
- Located in `tests/` with subdirectories: `unit/`, `e2e/`, and root-level integration tests
- E2E tests use Playwright browser automation
- Unit tests mock external services (autouse fixtures for network-heavy steps)
- Stress tests in `test_r3_*.py` (API chaos, unicode attacks, extreme load, type attacks)
- Integration tests for the full 8-stage pipeline in `test_candidate_unified.py`
- Demo E2E tests in `test_demo_e2e.py` (20 tests, all pass)

```bash
# Run all tests
python -m pytest tests/ -v -p no:faulthandler

# Run just unit tests
python -m pytest tests/unit/ -v -p no:faulthandler

# Run demo E2E tests
python -m pytest tests/test_demo_e2e.py -v -p no:faulthandler

# Run E2E (needs dev server running)
python -m pytest tests/e2e/ -v -p no:faulthandler
```

### Known pytest issue on Windows
Use `-p no:faulthandler` flag to avoid "ValueError: I/O operation on closed file" capture bugs. When running the full suite at once, a pytest I/O error may kill output — run test files individually if needed.

## Architecture

### Database Models (SQLAlchemy + SQLite)

| Model | File | Purpose |
|-------|------|---------|
| `CandidateCheck` | `app/models/candidate_check.py` | **Primary model** — 30+ fields for 8-stage pipeline, JSON properties |
| `Investigation` | `app/models/investigation.py` | Legacy Buratino model, JSON-serialized fields |
| `SocialProfile` | `app/models/social_profile.py` | VK/OK profiles linked to Investigation |
| `Friend` | `app/models/friend.py` | Social graph connections with centrality_score |
| `BusinessRecord` | `app/models/business_record.py` | EGRUL company affiliations |
| `CourtRecord` | `app/models/court_record.py` | Court case records |
| `Connection` | `app/models/connection.py` | Cross-investigation links |

### Route Blueprints (13 active)

| Blueprint | Prefix | Status |
|-----------|--------|--------|
| `candidate_bp` | `/candidate` | **PRIMARY** — 8-stage pipeline endpoints |
| `main_bp` | `/` | Home, health check, VK auth |
| `auth_bp` | `/` | Login/logout |
| `report_bp` | `/report` | Report generation/download |
| `dossier_bp` | `/dossier` | Dossier view/export |
| `scoring_bp` | `/scoring` | Risk scoring API |
| `connections_bp` | `/connections` | Cross-investigation analysis |
| `timeline_bp` | `/timeline` | Activity timeline |
| `api_search_bp` | `/api/search` | Search API endpoints |
| `phase1_bp` | `/phase1` | **DEPRECATED** — VK/Telegram/OK search |
| `phase2_bp` | `/phase2` | **DEPRECATED** — Contact discovery |
| `phase3_bp` | `/phase3` | **DEPRECATED** — Deep investigation |
| `phase4_bp` | `/phase4` | **DEPRECATED** — Connection analysis |

### Async Task Pattern
All long-running operations (Stages 1-8) run in background threads:
- `CandidateTaskStatus` in-memory object tracks progress
- Frontend polls `GET /candidate/progress/<task_id>` for live updates
- Cancel support via status flag
- Auto-cleanup of completed tasks after 3600s

### Frontend Stack
- Tailwind CSS via CDN (violet theme)
- vis.js — social graph + connections
- Chart.js — risk radar charts
- Leaflet.js — geo heatmap
- Vanilla JS — AJAX polling, form handling

## Web Scraping Strategy

- Russian government sites (FSSP, EFRSB, Rosfinmonitoring, MVD) use aggressive anti-bot measures and geo-blocking.
- Default to API/AJAX approaches FIRST, not Playwright/browser scraping.
- If browser scraping is unavoidable, implement CAPTCHA detection with graceful manual-fallback from the start.
- VK uses SPA rendering — intercept API calls rather than parsing DOM HTML.
- Assume CAPTCHA will appear. Build the fallback chain upfront: API -> AJAX -> Playwright -> Manual link.
- FSSP: 2-attempt Playwright retry with 3s delay between attempts.
- Rusprofile: graceful handling for 403 (anti-bot), 404 (URL change), 429 (rate limit).

## Phone/Name Parsing (Russian)

- Russian phone numbers: +7 (916) 123-45-67, 8-916-123-45-67, +7 916 1234567. Always handle parenthesized area codes.
- Russian names require bidirectional diminutive matching (Aleksandr <-> Sasha <-> Shura). Check both directions.
- Test regex patterns against edge cases before committing.

## Git Workflow

- After completing implementation work, always commit and push unless explicitly told otherwise.
- Use descriptive commit messages in English with conventional prefixes: feat:, fix:, chore:, docs:.
- `main` = production-ready branch
- Feature branches off main for new work

## Deprecated Code (still functional)

These routes and templates work but are superseded by the Candidate Check pipeline:

**Routes**: `phase1_bp` (7 endpoints, now includes OK search), `phase2_bp` (12 endpoints), `phase3_bp` (10 endpoints), `phase4_bp` (3 endpoints)

**Templates**: `phase1_buratino_new.html`, `phase1_buratino_results.html`, `phase2_analyze.html`, `phase2_buratino_results.html`, `phase3_buratino.html`, `phase3_buratino_results.html`, `phase2.html`, `phase3.html`

**Services**: The underlying phase1/phase2/phase3 services are NOT deprecated — they are imported and used by the candidate pipeline.

## VK Dual-Token Architecture

VK API methods require different token types:

| Token | Variable | Methods | How to Get |
|-------|----------|---------|------------|
| **Service** | `VK_SERVICE_TOKEN` | `users.search`, `users.get`, `newsfeed.search` | VK app settings → Service token |
| **User** | `VK_USER_TOKEN` | `wall.get`, `friends.get`, `photos.getAll`, `market.get` | `python scripts/auth_vk.py` |
| **Legacy** | `VK_TOKEN` | Fallback for user token | VK OAuth (24h expiry) |

Priority chain: `VK_USER_TOKEN` → `VK_TOKEN` → `VK_SERVICE_TOKEN` → demo mode

Without a user token: wall posts, friend lists, and photos are inaccessible.
The pipeline degrades gracefully — services skip private-data steps.

Helper: `from app.utils.vk_token_manager import get_vk_token`
- `get_vk_token('search')` — returns service token
- `get_vk_token('private')` — returns user token

## Authentication Scripts

| Script | Purpose | Usage |
|--------|---------|-------|
| `scripts/auth_telegram.py` | Telethon session authentication | `python scripts/auth_telegram.py` (interactive) / `--check` (validate only) |
| `scripts/auth_vk.py` | VK OAuth user token acquisition | `python scripts/auth_vk.py` (interactive) / `--check` (validate only) |

Session files:
- Telegram: `tg_session/ibp_session.session` (unified path)
- VK user token: saved to `.env` as `VK_USER_TOKEN`

## Known Issues

1. **VK token loading**: FIXED — `load_env_config()` in config.py now reads all API keys fresh from `os.environ` at `create_app()` time, not as frozen class attributes.
2. **pytest capture bug on Windows**: Use `-p no:faulthandler` to avoid I/O errors. Full suite may crash stdout — run files individually.
3. **FSSP API SSL errors**: The API at api-ip.fssp.gov.ru has persistent SSL issues. Playwright retry (2 attempts, 3s delay) + manual URL fallback.
4. **kad.arbitr.ru geo-blocked**: HTTP 451 from outside Russia. Manual URL only.
5. **Holehe slow**: ~25s per email check. Pipeline has 120s timeout for Stage 4.
6. **pymorphy2 Python 3.12+ compat**: Uses `inspect.getfullargspec` shim (patched).
7. **WeasyPrint forbidden on Windows**: Dossier PDF falls back to print-ready HTML or Playwright.
8. **SocialProfile.full_name is a property**: Not a setter — use first_name/last_name/display_name.
9. **Rusprofile anti-bot**: Returns 403/429 under load. Handled gracefully, falls through to nalog.ru EGRUL.
10. **Forgot-password oracle geo-blocking**: Gosuslugi and Sberbank checkers skipped by default. Set `ENABLE_GEO_RESTRICTED_CHECKERS=1` for Russian IP deployments.

## External Tools

OSINT tools path: `OSINT_TOOLS_DIR` env var > `~/osint_tools/` > project root.
- **Snoop**: integrated via `app/services/snoop_search.py` (5,372 sites)
- **Maigret**: integrated via `app/services/maigret_search.py` (3,000+ sites). Also pip-installable.
- **Sherlock**: integrated via `app/services/sherlock_search.py` (400+ sites). Also pip-installable.
- In Docker: maigret/sherlock are pip-installed. Snoop is not bundled.

## File Targeting

Before editing any template or file, confirm you have the correct filename by checking the route handler or import that references it. This project has multiple similar template files. Never assume — verify first.

## Testing

- Always run the full test suite after making changes.
- If tests use a database, ensure test isolation — never corrupt the main dev database.
- After E2E/Playwright tests, verify the dev server still works.
- Contact discovery tests use an autouse fixture to mock network-heavy steps (forgot-password oracle, marketplace scanner, breach APIs, Holehe, LeakDB). Override with `TestHolehe._real_verify` pattern if testing those steps directly.
