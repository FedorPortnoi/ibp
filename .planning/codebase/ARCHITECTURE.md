# IBP Architecture

## Request Flow

```
Browser (Tailwind + vanilla JS)
  │
  ├─ GET /                          → home.html (Candidate form)
  ├─ POST /candidate/start          → pipeline.py (background thread)
  ├─ GET /candidate/progress/X/status → CandidateTaskStatus (in-memory)
  ├─ GET /candidate/dossier/X       → candidate_dossier.html
  │
  ├─ GET /api/search/page           → people_search.html (Two-column search)
  ├─ POST /api/search/vk            → buratino_vk_search.py → VK API
  ├─ POST /api/search/telegram      → telegram_discovery.py → t.me + Telethon
  │
  └─ GET /health                    → JSON status (DB, tokens, services)

Pipeline Background Thread:
  Stage 0: pipeline.py → business_registry.py → nalog.ru EGRUL API
                        → bankruptcy_service.py → bankrot.fedresurs.ru
  Stage 1: pipeline.py → phase3/court_search.py → sudact.ru (Playwright)
                        → phase3/checko_service.py → checko.ru
                        → phase3/casebook_service.py → casebook.ru
                        → candidate/fssp_service.py → FSSP (4-tier fallback)
  Stage 2: pipeline.py → sanctions_check.py → OpenSanctions API
                        → local_security_db.py → data/mvd_wanted.json
                        → Interpol REST API
  Stage 3: pipeline.py → buratino_vk_search.py → VK API
                        → telegram_discovery.py → t.me + Telethon
                        → ok_search_integration.py → OK.ru
  Stage 4: pipeline.py → contact_discovery.py → (11 sources)
  Stage 5: pipeline.py → social_analysis.py → Search4Faces, Snoop, etc.
  Stage 6: pipeline.py → behavioral_analysis.py → VK wall analysis
  Stage 7: pipeline.py → risk_scorer.py → 9-category scoring
  Stage 8: pipeline.py → report_builder.py → dossier compilation
```

## Application Factory (`app/__init__.py`)

```python
def create_app(config_name='development'):
    app = Flask(__name__)
    app.config.from_object(config_class)
    load_env_config(app)        # Loads 45+ API keys fresh from os.environ

    db.init_app(app)            # SQLAlchemy
    migrate.init_app(app, db)   # Flask-Migrate
    csrf.init_app(app)          # CSRF protection
    limiter.init_app(app)       # Rate limiting (120/min default)

    # Register 13 blueprints
    # Global @app.before_request auth check
    # Global @app.after_request security headers
    # Error handlers (404, 500, 429)
    # db.create_all()
```

## Blueprint Registration

| Blueprint | Prefix | Route File | Endpoints |
|-----------|--------|------------|-----------|
| `candidate_bp` | `/candidate` | `candidate_check.py` | 12 (start, progress, confirm, dossier, history, export, delete) |
| `api_search_bp` | `/api/search` | `api_search.py` | 4 (page, vk, telegram, save-selection) |
| `main_bp` | `/` | `main.py` | 8 (index, health, vk auth/callback, save-token, redirects) |
| `auth_bp` | `/` | `auth.py` | 2 (login, logout) |
| `report_bp` | `/report` | `report.py` | 7 (view, data, generate, download html/pdf/json) |
| `dossier_bp` | `/dossier` | `dossier.py` | 3 (view, json, pdf) |
| `scoring_bp` | `/` | `scoring.py` | 3 (calculate, breakdown, risk-report) |
| `connections_bp` | `/` | `connections.py` | 3 (page, analyze, graph-data) |
| `timeline_bp` | `/timeline` | `timeline.py` | 2 (view, api) |
| `phase1_bp` | `/phase1` | `phase1.py` | 8 (new, search, confirm, reject, refresh, photo) |
| `phase2_bp` | `/phase2` | `phase2.py` | 8+ (analyze, start, progress, results, buratino) |
| `phase3_bp` | `/phase3` | `phase3.py` | 12 (start, progress, results, business/court/geo/text APIs) |
| `phase4_bp` | `/` | `phase4.py` | 8 (people search, graph, connections CRUD) |

## Service Layer (84 files)

### Candidate Pipeline (`app/services/candidate/` — 11 files)
- `pipeline.py` — Orchestrator: `CandidateTaskStatus`, `run_full_pipeline(check, mode)`
- `contact_discovery.py` — `ContactDiscoveryService.discover()` — 11-step chain
- `social_analysis.py` — Face search, social graph, Snoop/Maigret/Sherlock, YaSeeker
- `behavioral_analysis.py` — VK wall text analysis, geo extraction, activity timeline
- `risk_scorer.py` — `RiskScorer.analyze()` — 9 categories
- `report_builder.py` — Compiles all stage data into report structure
- `sanctions_check.py` — `SanctionsService.check_all()` — OpenSanctions + local DBs + Interpol
- `opensanctions_service.py` — `OpenSanctionsService.check_person()`
- `local_security_db.py` — `LocalSecurityDB.check_mvd()`, `check_extremist()`
- `fssp_service.py` — 4-tier FSSP fallback
- `bankruptcy_service.py` — EFRSB API + Playwright fallback

### Phase 1 Discovery (`app/services/phase1/` — 9 files)
- `buratino_vk_search.py` — `BuratinoVKSearch.search()` — 4 VK strategies
- `telegram_discovery.py` — `TelegramDiscoveryService.discover()` — 3 methods (A/B/C)
- `ok_search_integration.py` — OK.ru search with demo fallback
- `yandex_search.py` — Yandex People (Playwright, CAPTCHA-prone)
- `transliteration.py` — Multi-system Cyrillic<->Latin
- `russian_diminutives.py` — 78+ names, bidirectional lookup
- `fuzzy_matching.py` — Surname similarity + gender variants
- `vk_web_search.py` — VK web scraping + `verify_profile_name_matches_query()`
- `combined_search.py` — Combines multi-platform results

### Phase 2 Contact/Social (`app/services/phase2/` — 23 files)
Key files:
- `search4faces_service.py` — `Search4FacesService.search_by_photo()` — API + Playwright
- `telegram_crossref.py` — `TelegramCrossRef.check_username_web()` + name verification
- `vk_api_extractor.py` — VK profile contact extraction
- `vk_wall_extractor.py` — Deep VK wall mining
- `email_generator.py` — Email patterns + Hunter.io
- `email_discovery.py`, `phone_discovery.py` — Orchestrators
- `holehe_service.py` — Email verification (120+ services)
- `forgot_password_oracle.py` — Password recovery hints (8 services)
- `marketplace_scanner.py` — 6 Russian marketplaces
- `breach_checker.py` — HudsonRock, LeakCheck, ProxyNova, HIBP
- `social_graph.py` — NetworkX + Louvain
- `yaseeker_service.py` — Yandex services discovery
- `sources/` subdir with 8 additional source files

### Phase 3 Business/Courts (`app/services/phase3/` — 9 files)
- `business_registry.py` — `BusinessRegistrySearch.search_by_name()` — nalog.ru + Rusprofile
- `court_search.py` — sudact.ru (Playwright)
- `checko_service.py` — checko.ru (globally accessible FSSP alternative)
- `casebook_service.py` — casebook.ru (arbitration courts)
- `fssp_search.py` — FSSP enforcement
- `text_analyzer.py` — VK wall sentiment/keywords
- `geo_extractor.py` — Geographic extraction
- `video_analyzer.py` — Video content analysis
- `combined_search.py` — Combines results

### Top-level Services (9 files)
- `snoop_search.py`, `maigret_search.py`, `sherlock_search.py` — Username search tools
- `activity_timeline.py` — VK wall timestamp analysis
- `connection_intelligence.py` — Cross-investigation analysis
- `dossier_generator.py` — Legacy dossier compilation
- `report_generator.py` — Identity cards + PDF (reportlab)
- `risk_scoring.py` — Legacy 7-dimension scoring
- `photo_investigation.py` — Photo-first investigation flow

### AI & Telegram (4 files)
- `ai/claude_integration.py` — Claude API for risk/behavioral/executive summaries
- `telegram/session_manager.py` — Telethon singleton lifecycle
- `telegram/bot_query.py` — Telegram bot queries
- `telegram/config.py` — Telegram configuration

## Database Schema

### candidate_checks
Primary model. 33+ columns including:
- Input: `full_name`, `date_of_birth`, `inn`, `passport_series`, `passport_number`, `registered_address`, `region`, `phone`, `email`
- Identity: `confirmed_name`, `identity_confirmed`, `_identity_confirmation` (JSON)
- Stage results: `_business_records`, `_court_records`, `_fssp_records`, `_bankruptcy_records`, `_sanctions_results`, `_social_media_profiles`, `_contact_discoveries`, `_confirmed_profiles`, `_social_graph_data`, `_face_matches`, `_username_accounts`, `_geo_analysis`, `_text_analysis`, `_activity_timeline`, `_risk_breakdown`, `_red_flags` (all JSON)
- Meta: `status`, `check_mode`, `paused_at_stage`, `risk_level`, `risk_score_numeric`, `risk_narrative`, `behavioral_summary`, `executive_summary`, `report_generated`, `sources_checked`, `check_duration_seconds`

### investigations
Legacy model. 25+ JSON fields for multi-phase Buratino flow.

### social_profiles
VK/OK/TG profiles linked to investigations. Includes confidence scoring, face/name match flags, education/career JSON, raw API data.

### friends
Social graph connections with centrality_score, community_id, interaction_score.

### business_records
EGRUL company affiliations with INN, OGRN, role, share data, OKVED codes.

### court_records
Court cases with category, participants, risk scoring, decision data.

### connections
Cross-investigation entity links (person-person, person-company) with evidence JSON.

## Background Task System

No Celery/Redis. Uses Python `threading.Thread`:

```python
# In candidate_check.py route:
task_id = str(uuid.uuid4())
candidate_tasks[task_id] = CandidateTaskStatus(task_id, check.id)
thread = threading.Thread(target=run_candidate_pipeline, args=(app._get_current_object(), task_id, check.id))
thread.daemon = True
thread.start()

# Frontend polls:
GET /candidate/progress/{task_id}/status → JSON {stage, percent, messages[], status}

# Cleanup:
Tasks auto-removed after 3600s. Max 10 concurrent checks.
```

Same pattern for Phase 2 (`Phase2TaskStatus`) and Phase 3 (`Phase3TaskStatus`).

## Authentication Flow

1. If `IBP_PASSWORD` or `IBP_PASSWORD_HASH` is set, auth is enabled
2. Login: POST `/login` with password → bcrypt verify → `session['authenticated'] = True`
3. Global `@app.before_request` checks session on every request
4. Session timeout: `IBP_SESSION_TIMEOUT` (default 3600s), `IBP_SESSION_REMEMBER` (default 30 days)
5. Session fixation protection via `session.regenerate()` on login

## VK Token Flow

1. User visits `/vk/auth` → redirected to VK OAuth with `VK_APP_ID`
2. VK redirects to `/vk/callback` with token in URL fragment
3. `vk_callback.html` JS extracts token, POSTs to `/vk/save-token`
4. Token saved to app config as `VK_USER_TOKEN`
5. Alternative: `python scripts/auth_vk.py` (interactive CLI)

## Telethon Session

1. Run `python scripts/auth_telegram.py` (one-time)
2. Creates `tg_session/ibp_session.session`
3. `TelegramSessionManager` (singleton) manages client lifecycle
4. Used by: `telegram_discovery.py` (Method C), `telegram_crossref.py`, `bot_query.py`
