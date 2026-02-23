# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

IBP (Identity-Based Profiler) is a multi-phase OSINT investigation platform built with Flask, optimized for Russian social networks. It follows a "Buratino-style" person-first workflow with 16 route blueprints, 60+ endpoints, 35+ service classes, and 27 templates.

## Platform Constraints
- This project runs on Windows. NEVER use WeasyPrint, GTK, or Cairo-dependent libraries.
- For PDF generation: use Playwright (already installed) or reportlab. Never try WeasyPrint or xhtml2pdf.
- Always verify native dependency compatibility before suggesting any new library.
- PowerShell escaping differs from bash — test commands before running.

## Web Scraping Strategy
- Russian government sites (ФССП, ЕФРСБ, Росфинмониторинг, МВД) use aggressive anti-bot measures and geo-blocking.
- Default to API/AJAX approaches FIRST, not Playwright/browser scraping.
- If browser scraping is unavoidable, implement CAPTCHA detection with graceful manual-fallback from the start.
- VK uses SPA rendering — intercept API calls rather than parsing DOM HTML.
- Assume CAPTCHA will appear. Build the fallback chain upfront: API → AJAX → Playwright → Manual link.

## Git Workflow
- After completing implementation work, always commit and push unless explicitly told otherwise.
- Use descriptive commit messages in English with conventional prefixes: feat:, fix:, chore:, docs:.

## Testing
- Always run the full test suite after making changes.
- If tests use a database, ensure test isolation — never corrupt the main dev database.
- After E2E/Playwright tests, verify the dev server still works.

## File Targeting
- Before editing any template or file, confirm you have the correct filename by checking the route handler or import that references it.
- This project has multiple similar template files. Never assume — verify first.

## Phone/Name Parsing (Russian)
- Russian phone numbers come in many formats: +7 (916) 123-45-67, 8-916-123-45-67, +7 916 1234567. Always handle parenthesized area codes.
- Russian names require bidirectional diminutive matching (Александр ↔ Саша ↔ Шура). Check both directions.
- Test regex patterns against these edge cases before committing.

## Commands

```bash
# Run development server (http://127.0.0.1:5000)
python run.py

# Install dependencies
pip install -r requirements.txt

# Run tests
python -m pytest tests/ -v

# Load leak data
python scripts/load_leaks.py vk_2012 ./data/raw/vk_2012.csv
python scripts/load_leaks.py getcontact ./data/raw/getcontact.jsonl --dedup
python scripts/load_leaks.py telco ./data/raw/beeline.csv --carrier beeline
```

---

## Complete Feature Inventory

### Phase 1: People Search

**VK People Search** (`app/services/phase1/buratino_vk_search.py`)
- VK API `users.search` with city/age/education filters
- Demo mode (3 fake profiles) when `VK_SERVICE_TOKEN` not set; real VK profiles when set
- Fake-profile filtering via set intersection of formal name roots

**Fuzzy Name Matching** (`app/services/phase1/fuzzy_matching.py`)
- `verify_profile_name_matches_query()` — set intersection of formal roots
- Confidence scoring based on similarity ratio

**Russian Diminutives** (`app/services/phase1/russian_diminutives.py`)
- 60+ bidirectional Russian name mappings (Александр ↔ Саша ↔ Шура)
- Patronymic variation handling

**Transliteration** (`app/services/phase1/transliteration.py`)
- Multi-system Cyrillic/Latin: GOST 7.79-2000, GOST R 52290-2004, BGN/PCGN
- Canonical single output used throughout Phase 1/2
- Handles Ukrainian, Belarusian, Kazakh characters

**Telegram Discovery** (`app/services/phase1/telegram_discovery.py`)
- 3 methods: Direct Telegram API search, Bot web scraping, Telethon library
- Returns TelegramProfile (username, display_name, bio, photo_url)
- Requires TELEGRAM_API_ID/HASH/PHONE in `.env`

**Yandex Search** (`app/services/phase1/yandex_search.py`)
- Yandex People service search
- CAPTCHA detection + graceful fallback to manual URL

**Photo Investigation** (`app/services/photo_investigation.py`)
- Face-first workflow: upload photo → facial recognition search → create investigation
- Validates photo, runs Search4Faces, presents matches

### Phase 2: Contact Discovery & Intelligence

**Email Discovery** (`app/services/phase2/email_discovery.py`)
- Holehe verification (120+ online services)
- SMTP RCPT TO probing (blocks Russian domains that reject: mail.ru, yandex.ru, bk.ru)
- Gravatar JSON profile lookup
- MX record validation
- Profile scraping for visible emails
- Russian service checks (Yandex Collections)

**Email Generation** (`app/services/phase2/email_generator.py`)
- Smart candidate generation from name + usernames + diminutives
- Yandex/Mail.ru domain prioritization for Russian targets
- `generate_smart_email_candidates()` + `verify_email_candidates()`

**Phone Discovery** (`app/services/phase2/phone_discovery.py`)
- VK API extraction (`users.get` contacts field) — requires VK token
- VK wall post regex scanning (last 100 posts)
- Username/email pattern extraction (digits → phone candidates)
- Telegram cross-reference (phone → Telegram username)
- Russian phone validation (mobile prefix 9XX)

**Phone Lookup Services** (`app/services/phase2/phone_sources.py`)
- GetContactChecker — reverse phone lookup (requires rooted Android credentials)
- NumBusterChecker — phone → name resolution
- TrueCallerChecker — TrueCaller API
- EyeconChecker — Ukrainian phone lookup
- CallAppChecker — CallApp integration

**Facial Recognition**:
- **Search4Faces** (`app/services/phase2/search4faces_service.py`) — FREE unlimited face search across 3 databases: vkok (VK+OK avatars), vk01 (1.1B VK photos), vkokn (newest). Returns FaceMatch with profile_url, username, similarity_score.
- **YaSeeker** (`app/services/phase2/yaseeker_service.py`) — Yandex service discovery. Checks Yandex Collections, Dzen, Yandex Music. Verification-based (confirms real profiles, no guessing).
- **FaceCheck.ID** (`app/services/phase2/face_search_api.py`) — Stub class exists, no real implementation.

**Social Graph** (`app/services/phase2/social_graph.py`)
- Friends extraction from VK API (thousands possible)
- NetworkX graph + Louvain community detection
- Centrality score calculation
- vis.js export (nodes + edges JSON)
- Demo mode: 8 fake friends when no VK token

**Username Intelligence** (`app/services/phase2/username_intelligence.py`)
- Username pattern analysis, variations, diminutives
- Cross-platform username matching

**Telegram Cross-Reference** (`app/services/phase2/telegram_crossref.py`)
- Phone → Telegram username resolution
- Name matching validation

### Phase 2: Source Plugin Architecture

**Source Manager** (`app/services/phase2/source_manager.py`)
- Auto-discovers all `BaseSource` subclasses in `sources/` directory
- Runs all available sources in parallel (ThreadPoolExecutor, 8 workers)
- Deduplication: same data from 2+ sources → merge + confidence boost
- Cross-validation: breach + platform confirmation → verified flag
- Groups results by data_type for consumption

**Base Source** (`app/services/phase2/base_source.py`)
- SourceResult dataclass: data_type, value, source_name, source_tier, confidence, verified, raw_data, metadata
- SourceTier: S (Breach DB), A (Platform API), B (Verification), C (Pattern Generation)
- SourceType: EMAIL, PHONE, BOTH, IDENTITY, PROFILE, VERIFICATION

**Breach Database Sources** (`app/services/phase2/sources/breach_api.py`):

| Source | Status | API Key | What it returns |
|--------|--------|---------|----------------|
| HudsonRock Cavalier | WORKING | None (free) | Cleartext passwords, URLs, usernames from infostealer logs |
| LeakCheck Public | WORKING | None (free) | Breach source names from 12B+ records |
| ProxyNova COMB | WORKING | None (free) | email:password pairs from 3.2B combo list |
| HIBP Pwned Passwords | WORKING | None (free) | Password breach validation (k-anonymity) |
| Snusbase | STUB | SNUSBASE_API_KEY | Not implemented |
| DeHashed | STUB | DEHASHED_EMAIL + DEHASHED_API_KEY | Not implemented |

**Local Leak Database Sources** (`app/services/phase2/sources/leak_sources.py`):

| Source | Status | Backend |
|--------|--------|---------|
| VK 2012 Leak (100M records) | READY, needs CSV import | SQLite LeakDB (`data/leaks/all_leaks.db`) |
| GetContact Leak (55M records) | READY, needs CSV import | Same SQLite DB |
| Telco Leak (Beeline/MTS/Megafon) | READY, needs CSV import | Same SQLite DB |

LeakDB: WAL mode, indexed by phone+email+name, in-memory LRU cache (50k queries), batch insert via `scripts/load_leaks.py` with auto encoding detection (CP1251/UTF-8) and delimiter sniffing.

**Other Source Plugins** (`app/services/phase2/sources/`):

| Plugin File | Source | Status |
|-------------|--------|--------|
| `vk_extract.py` | VK Profile API extraction | Working (needs VK token) |
| `verification.py` / `smtp_verify.py` | SMTP verification | Working (blocks Russian domains) |
| `holehe_check.py` | Holehe 120+ service check | Working (needs holehe library) |
| `email_pattern.py` / `pattern_gen.py` | Email pattern generation | Working (low confidence 0.30-0.40) |
| `telegram_bot.py` | Telegram OSINT bots (Himera, LeakOSINT) | STUB — returns [] |
| `getcontact.py` | GetContact API lookup | STUB — needs Android credentials |
| `platform_api.py` | NumBuster, GetContact, InfoTrackPeople | STUBS — need API keys |

### Phase 3: Deep Investigation

**Business Registry** (`app/services/phase3/business_registry.py`)
- **PRIMARY**: nalog.ru EGRUL — official FNS 2-step token API. FREE, WORKING. Returns company_name, INN, OGRN, role, status, registration_date, address. ~20 results per name, 2-3s.
- **FALLBACK**: Rusprofile.ru — scraping with `type=fl` person search → person profile page → company affiliations. WORKING (fixed Feb 2026, was returning 404).

**Court Records** (`app/services/phase3/court_search.py`)
- **PRIMARY**: sudact.ru — Playwright browser automation (JS-rendered). Selectors: `ul.results > li` + `a[href*="/doc/"]`. 8-10 cases per name, ~5s. WORKING.
- **SECONDARY**: kad.arbitr.ru — BLOCKED (HTTP 451 geo-restriction, DDoS Guard). Manual URL fallback only.

**FSSP Enforcement Proceedings** (`app/services/phase3/fssp_search.py`)
- API: `api-ip.fssp.gov.ru` — SSL errors, unreliable. Requires FSSP_API_TOKEN.
- Fallback: manual search URL generation (`fssp.gov.ru/iss/ip`). Always works.

**Geo Extraction** (`app/services/phase3/geo_extractor.py`)
- `extract_from_text()` — parses city/region/country from profile text
- Generates map data for visualization

**Text Analyzer** (`app/services/phase3/text_analyzer.py`)
- `analyze()` — wall post analysis for personality traits, keywords, sentiment

**Video Analyzer** (`app/services/phase3/video_analyzer.py`)
- Video metadata extraction from VK wall (timestamps, captions, descriptions)

**Combined Search Orchestrator** (`app/services/phase3/combined_search.py`)
- 6-step pipeline: business_registry + court_search + fssp + geo_extractor + text_analyzer + risk assessment
- Progress callbacks for UI updates
- Returns Phase3Results with all records + manual_search_links

### Candidate Background Check Pipeline

**Pipeline** (`app/services/candidate/pipeline.py`)
- 5-stage async orchestrator with progress tracking:

| Stage | Service File | What it checks | Status |
|-------|-------------|---------------|--------|
| 1. Bankruptcy | `candidate/bankruptcy_service.py` | ЕФРСБ (bankrot.fedresurs.ru) | Working (API + Playwright fallback) |
| 2. Sanctions | `candidate/sanctions_check.py` | Росфинмониторинг, МВД, Интерпол, Перечень экстремистов | Working (manual URL fallback for Interpol) |
| 3. FSSP | `candidate/fssp_service.py` | Enforcement proceedings | Partial (API unreliable, manual URL) |
| 4. Contacts | `candidate/contact_discovery.py` | Email/phone discovery + verification | Working |
| 5. Risk Score | `candidate/risk_scorer.py` | Composite risk assessment | Working |

### Risk Scoring & Intelligence

**Risk Scoring** (`app/services/risk_scoring.py`)
- `calculate_risk_score()` — composite 0-100 score
- Dimensional breakdown: business risk, legal risk, social risk, financial risk
- Radar chart data generation for UI

**Connection Intelligence** (`app/services/connection_intelligence.py`)
- Cross-investigation link analysis
- Identifies shared contacts, profiles, emails, phones across investigations
- vis.js graph visualization of connections

**Snoop Search** (`app/services/snoop_search.py`)
- Wrapper for Snoop tool (5,372 sites, 2,600+ Russian)
- Executes `snoop.py` from `C:\Users\fedor\osint_tools\snoop`
- Parses CSV results, filters to Russian/CIS platforms

### Report & Export

**Report Generator** (`app/services/report_generator.py`)
- HTML identity card generation (Tailwind CSS)
- PDF export via reportlab (Playwright fallback)
- JSON data export
- Confidence scoring (0-100)

**Dossier Generator** (`app/services/dossier_generator.py`)
- Professional investigation dossier
- Includes all investigation phases + risk assessment
- PDF/JSON export

---

## Architecture

### Entry Points
- `run.py` — Flask server with startup validation checks
- `config.py` — Environment configs (DevelopmentConfig, ProductionConfig, TestingConfig)
- `app/__init__.py` — Application factory (`create_app()`) with error handlers and logging

### Route Blueprints (16 total)

| Blueprint | File | Endpoints |
|-----------|------|-----------|
| `main_bp` | `app/routes/main.py` | `/`, `/health`, `/investigations`, `/vk/auth`, `/vk/callback`, `/api/vk/token-status`, `/api/investigations/<id>` DELETE |
| `phase1_bp` | `app/routes/phase1.py` | `/new`, `/search/<id>`, `/confirm/<id>/<pid>`, `/reject/<id>/<pid>`, `/photo-search`, `/photo-select` |
| `phase2_bp` | `app/routes/phase2.py` | `/start`, `/progress/<task_id>`, `/cancel/<task_id>`, `/analyze/<id>`, `/buratino/results/<id>`, `/api/graph/<id>`, `/api/sources/status` |
| `phase3_bp` | `app/routes/phase3.py` | `/<id>`, `/start`, `/progress/<task_id>`, `/api/business-search`, `/api/court-search`, `/buratino/<id>`, `/buratino/results/<id>` |
| `report_bp` | `app/routes/report.py` | `/<id>`, `/generate`, `/download/html`, `/download/pdf`, `/download/json` |
| `candidate_bp` | `app/routes/candidate_check.py` | `/start`, `/progress/<check_id>`, `/results/<check_id>`, `/check/<check_id>` |
| `connections_bp` | `app/routes/connections.py` | `/connections`, `/api/connections/analyze`, `/api/connections/graph-data` |
| `scoring_bp` | `app/routes/scoring.py` | `/api/scoring/calculate`, `/api/scoring/breakdown/<id>`, `/risk-report/<id>` |
| `dossier_bp` | `app/routes/dossier.py` | `/<id>`, `/<id>/json`, `/<id>/pdf` |
| `api_search_bp` | `app/routes/api_search.py` | `/page`, `/vk`, `/telegram`, `/yandex` |
| `auth_bp` | `app/routes/auth.py` | `/login`, `/logout`, `/set-password` |
| `timeline_bp` | `app/routes/timeline.py` | `/timeline/<id>` |
| `osint_knowledge_bp` | `app/routes/osint_knowledge.py` | `/api/osint/tools`, `/api/osint/techniques` |
| `osint_knowledge_gaps_bp` | `app/routes/osint_knowledge_gaps.py` | `/api/gaps` |

### Database Models (8 total)

SQLAlchemy with SQLite (`instance/ibp.db`):

| Model | File | Key Fields |
|-------|------|-----------|
| `Investigation` | `app/models/investigation.py` | input_name, status, confirmed_profile, discovered_emails/phones/usernames, business_records, court_records, property_records, risk_indicators, social_graph, connections. JSON-serialized with property helpers. |
| `SocialProfile` | `app/models/social_profile.py` | platform, platform_id, username, profile_url, first_name, last_name, city, confidence_score, face_match, face_similarity, is_confirmed, phone, email |
| `Friend` | `app/models/friend.py` | platform_id, first_name, last_name, photo_url, city, centrality_score |
| `BusinessRecord` | `app/models/business_record.py` | company_name, inn, ogrn, role, status, legal_address, registration_date, okved, source |
| `CourtRecord` | `app/models/court_record.py` | case_number, court_name, case_type, date, role, category, decision_summary, result, source |
| `Connection` | `app/models/connection.py` | Cross-investigation links, relationship type, confidence |
| `CandidateCheck` | `app/models/candidate_check.py` | full_name, date_of_birth, inn, passport, phone, email, bankruptcy/sanctions/fssp_results, risk_score, status |

### Async Task Pattern
Phase 1, 2, 3 and candidate checks run in background threads:
- `Phase2TaskStatus` / `CandidateTaskStatus` track progress with partial results
- Frontend polls `/progress/<task_id>` for live updates
- Cancel support via `/cancel/<task_id>`
- Auto-cleanup of completed tasks (3600s retention)

### Templates (27 HTML files)
- `base.html` — Tailwind CSS + navbar layout
- `people_search.html` — Phase 1 three-column search UI
- `phase1_buratino_results.html`, `phase2_buratino_results.html`, `phase3_buratino_results.html` — Phase result pages
- `identity_card.html`, `dossier.html`, `candidate_dossier.html` — Report views
- `connections.html`, `graph.html`, `risk_report.html`, `timeline.html` — Intelligence views
- `login.html`, `vk_callback.html` — Auth pages
- `errors/404.html`, `errors/500.html` — Error pages

### Frontend Stack
- Tailwind CSS via CDN (custom violet theme)
- vis.js — social graph + connections visualization
- Chart.js — risk report radar charts
- Vanilla JS — AJAX polling for progress updates

---

## Key Technical Details

- **VK Token**: Expires every 24h. Refresh via `/vk/auth` OAuth flow or manual URL. Status indicator in navbar polls `/api/vk/token-status`. `VK_SERVICE_TOKEN` is currently set.
- **Demo Mode**: Phase 1 VK search + social graph produce fake data when no VK token. All other services degrade gracefully (return empty, not fake).
- **Phase 2 Source Architecture**: `base_source.py` → `source_manager.py` auto-discovers → `sources/*.py` plugins run in parallel
- **Holehe Verification**: CPU/time-intensive (~25s per email). Uses tiered priority (Russian mail domains first) with 3 concurrent checks.
- **Logging**: Structured logging to `logs/ibp_YYYYMMDD.log`. Sensitive data masked (tokens, phones, emails).
- **Leak Data Loader**: `scripts/load_leaks.py` — auto-detects CP1251/UTF-8 encoding + CSV delimiter (comma/semicolon/pipe/tab). CLI flags: `--encoding`, `--delimiter`, `--dedup`, `--carrier`.

## Environment Variables (`.env`)

```
VK_SERVICE_TOKEN=...   # VK API service token (primary, currently set)
VK_TOKEN=...           # VK API user token (expires 24h)
VK_APP_ID=...          # VK app ID for OAuth refresh flow
TELEGRAM_API_ID=...    # Telegram API credentials
TELEGRAM_API_HASH=...
TELEGRAM_PHONE=...
FSSP_API_TOKEN=...     # FSSP bailiff service API token
SNUSBASE_API_KEY=...   # Snusbase breach DB (paid, $5-16/mo)
DEHASHED_EMAIL=...     # DeHashed breach DB (paid, $5.49/mo)
DEHASHED_API_KEY=...
GETCONTACT_TOKEN=...   # GetContact (requires rooted Android)
GETCONTACT_AES_KEY=...
GETCONTACT_DEVICE_ID=...
SECRET_KEY=...         # Flask secret key
```

## What Returns Real Data vs Stubs

### Real data (working now, no extra keys):
- HudsonRock, LeakCheck Public, ProxyNova COMB, HIBP (free breach APIs)
- VK People Search + Social Graph + Phone Extraction (VK_SERVICE_TOKEN is set)
- nalog.ru EGRUL business registry (free government API)
- sudact.ru court records (Playwright)
- Gravatar email lookup
- SMTP email verification (non-Russian domains)
- Search4Faces facial recognition (free, unlimited)
- YaSeeker Yandex service discovery
- Email/phone pattern generation (low confidence guesses)

### Stubs / not working:
- Snusbase, DeHashed (need paid API keys)
- Telegram OSINT bots — Himera, LeakOSINT (stub, returns [])
- GetContact API lookup (stub, needs Android credentials)
- NumBuster, InfoTrackPeople (stubs, need API keys)
- FaceCheck.ID (stub class, no implementation)
- FSSP API (SSL errors, manual URL fallback works)
- kad.arbitr.ru (HTTP 451 geo-blocked, manual URL fallback)
- LeakDB local sources (infrastructure ready, needs CSV data import)

## Test Suite

57 test files, 15+ categories:
- **E2E**: `test_e2e_smoke.py` (18+ smoke tests), `test_full_workflow.py`, `test_phase3_e2e.py` (3 targets)
- **Unit** (49 files in `tests/unit/`): name matching, phone normalization, transliteration, email/phone intelligence, pipeline resilience, risk scoring, leak sources, connections, dossier
- **Stress**: `test_r3_extreme_load.py`, `test_r3_api_chaos.py`, `test_r3_unicode_attacks.py`, `test_r3_type_attacks.py`

## Test Targets

Known test subjects: Тихон Портной, Ольга Ахтинас, Влада Кладко, Даниил Глазков (@etoglaz)

## External Tools

OSINT tools at `C:\Users\fedor\osint_tools\` (snoop, maigret, sherlock, etc.). Snoop integrated via `app/services/snoop_search.py`.

## Research Workflow

When investigating a new data source or API:
1. **brave-search** → find current documentation and status
2. **fetch** → test if the API/site responds from this location
3. **playwright** → if fetch fails, try with full browser (handles JS, CAPTCHA detection)
4. Write the integration code based on real responses, not guesses
