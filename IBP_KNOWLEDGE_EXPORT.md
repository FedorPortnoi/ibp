# IBP — Complete Project Knowledge Base

## 1. What IBP Is

IBP (Identity-Based Profiler) is a self-hosted OSINT investigation platform for Russian-speaking targets. It runs automated background checks by aggregating data from Russian government registries (EGRUL, courts, FSSP, bankruptcy), social networks (VK, Telegram), breach databases, and behavioral signals into a single 9-stage pipeline. INN (Russian Tax ID) is the primary required identifier.

The project is built for Windows (Python 3.12, Flask), uses SQLite for storage, Playwright for browser automation, and Telethon for Telegram integration. It is a single-developer project, not yet multi-user.

## 2. Tech Stack & Dependencies

- **Python 3.12** on Windows 11
- **Flask 3.1.2** + Flask-SQLAlchemy 3.1.1 + Flask-Migrate 4.1.0 + Flask-WTF + Flask-Limiter
- **SQLAlchemy 2.0.45** + SQLite
- **Playwright** (Chromium) — browser automation for scraping
- **Telethon 1.42.0** — Telegram API client
- **requests 2.32.5** + **httpx 0.28.1** + **aiohttp 3.13.2** — HTTP clients
- **BeautifulSoup4 4.12.3** + **lxml 5.4.0** — HTML parsing
- **NetworkX 2.8.8** + **python-louvain 0.16** — social graph analysis
- **pymorphy2 0.9.1** — Russian morphology (with Python 3.12 compat shim)
- **Pillow 11.3.0** — image processing
- **bcrypt 4.3.0** — password hashing
- **phonenumbers 9.0.21** — phone number parsing
- **holehe 1.61** — email service verification
- **anthropic** — Claude AI integration (optional)
- **Tailwind CSS** (CDN) + **vis.js** + **Chart.js** + **Leaflet.js** — frontend
- **gunicorn 25.0.3** — production server
- **No WeasyPrint** — Windows constraint. PDF via Playwright or reportlab.

## 3. Project Structure

```
app/
  __init__.py              # App factory, 13 blueprints, extensions, security middleware
  models/                  # 7 SQLAlchemy models (candidate_check, investigation, social_profile, friend, business_record, court_record, connection)
  routes/                  # 13 blueprint route files
  services/                # 84 service files across 7 subdirectories
    candidate/             # 11 files — 9-stage pipeline core
    phase1/                # 9 files — VK/Telegram/OK/Yandex search + name matching
    phase2/                # 23 files — contact discovery, face search, social graph, breach APIs
    phase3/                # 9 files — business registries, courts, FSSP, text/geo analysis
    ai/                    # 1 file — Claude API integration
    telegram/              # 3 files — session management, bot queries, config
    (top-level)            # 9 files — Snoop/Maigret/Sherlock, timeline, dossier, reporting
  templates/               # 13 HTML files on disk (many legacy templates deleted)
  utils/                   # 6 utility modules (INN validation, VK tokens, phone parsing, etc.)
  static/                  # CSS (СЛЕД design system), icons, images, reports, uploads
config.py                  # Dev/Prod/Test configs + load_env_config()
run.py                     # Flask dev server entry point
scripts/                   # auth_telegram.py, auth_vk.py, load_leaks.py, update scripts
data/                      # mvd_wanted.json, extremist_list.json, demo/, leaks/, raw/
tests/                     # 127 unit tests in tests/unit/ + e2e stress + security audit
```

## 4. Architecture

### App Factory (`app/__init__.py`)
Creates Flask app, loads config class, calls `load_env_config()` to read 45+ API keys from `os.environ` at creation time. Initializes SQLAlchemy, Flask-Migrate, CSRF (Flask-WTF), rate limiter (Flask-Limiter, 120/min default). Registers 13 blueprints. Adds global `@app.before_request` auth check with session timeout and `@app.after_request` security headers (CSP, HSTS, X-Frame-Options).

### 13 Blueprints
| Blueprint | Prefix | Purpose |
|-----------|--------|---------|
| `candidate_bp` | `/candidate` | **PRIMARY** — 9-stage pipeline (start, progress, confirm, dossier, export, history) |
| `api_search_bp` | `/api/search` | People Search API (VK, Telegram, save-selection) |
| `main_bp` | `/` | Home, health check, VK OAuth flow |
| `auth_bp` | `/` | Login/logout (password-only, bcrypt) |
| `report_bp` | `/report` | Report generation, PDF/JSON/HTML download |
| `dossier_bp` | `/dossier` | Professional dossier view/export |
| `scoring_bp` | `/` | Risk scoring API |
| `connections_bp` | `/` | Cross-investigation graph analysis |
| `timeline_bp` | `/timeline` | Activity timeline |
| `phase1_bp` | `/phase1` | DEPRECATED — VK+OK search |
| `phase2_bp` | `/phase2` | DEPRECATED — Contact discovery |
| `phase3_bp` | `/phase3` | DEPRECATED — Deep investigation |
| `phase4_bp` | `/` | DEPRECATED — Graph visualization, people search |

### Database (SQLAlchemy + SQLite)
7 models, all in `app/models/`:

**CandidateCheck** (`candidate_checks`) — PRIMARY. 33+ fields including input data (full_name, DOB, INN, passport, address, phone, email), identity confirmation (confirmed_name, identity_confirmed), 15+ JSON columns for stage results, risk scoring, AI summaries, report metadata.

**Investigation** (`investigations`) — Legacy Buratino model. 25+ JSON fields for multi-phase flow.

**SocialProfile** (`social_profiles`) — VK/OK/TG profiles. Confidence scoring, face/name match flags, education/career JSON. Unique constraint on (investigation_id, platform, platform_id).

**Friend** (`friends`) — Social graph. centrality_score, community_id, interaction_score.

**BusinessRecord** (`business_records`) — EGRUL data. INN, OGRN, company info, person's role, share data, OKVED codes.

**CourtRecord** (`court_records`) — Court cases. Category, participants JSON, risk scoring, decision data.

**Connection** (`connections`) — Cross-investigation links. Source/target entities, connection type, strength, evidence JSON.

### Background Tasks
No Celery. Uses Python `threading.Thread` with in-memory status objects (`CandidateTaskStatus`). Frontend polls JSON status endpoint. Auto-cleanup after 3600s. Max 10 concurrent candidate checks.

### Config (`config.py`)
`DevelopmentConfig` (DEBUG=True), `ProductionConfig` (secure cookies), `TestingConfig` (in-memory SQLite). `load_env_config()` reads 45+ env vars at app creation time to avoid module-attribute caching.

## 5. The 9-Stage Pipeline

### Stage 0: Identity Confirmation (0-8%)
- `pipeline.py` (inline) + `phase3/business_registry.py` + `candidate/bankruptcy_service.py`
- EGRUL lookup by INN via nalog.ru API, bankruptcy check via bankrot.fedresurs.ru
- Extracts business network, sets `confirmed_name` for all subsequent stages

### Stage 1: Government Registries (8-18%)
- `candidate/fssp_service.py` + `phase3/court_search.py` + `phase3/checko_service.py` + `phase3/casebook_service.py`
- EGRUL by name (merged with Stage 0), courts (sudact.ru Playwright), checko.ru (FSSP alternative), casebook.ru (arbitration), FSSP (4-tier fallback: API -> AJAX -> Playwright 2-attempt -> manual URL)

### Stage 2: Security Checks (18-27%)
- `candidate/sanctions_check.py` + `candidate/opensanctions_service.py` + `candidate/local_security_db.py`
- OpenSanctions API (primary, global), local MVD wanted list, local extremist list, Interpol REST API

### Stage 3: Social Media Discovery (27-42%)
- `phase1/buratino_vk_search.py` + `phase1/telegram_discovery.py`
- VK: 4 search strategies (name, name+city, name+age, screen_name) with DOB filtering
- Telegram: 3 methods (A: VK cross-reference, B: username guessing, C: Telethon directory search)
- **Precise mode pauses here** for user to confirm profiles

### Stage 4: Contact Discovery (42-57%)
- `candidate/contact_discovery.py` — `ContactDiscoveryService.discover()`
- 11-step chain: VK extraction, deep wall mining, Telegram, business/FSSP records, email guessing (transliteration + corporate patterns), Hunter.io, LeakDB, breach APIs (HudsonRock, LeakCheck, ProxyNova), LeakDB cross-reference, forgot-password oracle (8 services), marketplace mining (6 platforms), Holehe (120+ services), dedup with cross-source confidence boost (+0.15 for 3+ sources, max 0.98)

### Stage 5: Deep Social Analysis (57-72%)
- `candidate/social_analysis.py`
- Search4Faces (paid JSON-RPC API + Playwright free fallback, 3 VK/OK databases)
- Social graph (VK friends -> NetworkX -> Louvain community detection -> vis.js)
- Snoop (5,372 sites), Maigret (3,000+ sites), Sherlock (400+ sites) — parallel username search
- YaSeeker (Yandex Collections/Dzen/Music)
- Feedback loop: new accounts discovered re-enter Stage 4

### Stage 6: Behavioral Intelligence (72-83%)
- `candidate/behavioral_analysis.py`
- VK wall text analysis (sentiment, keywords, topics via pymorphy2)
- Geo extraction (98 hardcoded Russian cities + text pattern matching from VK post text)
- Activity timeline from post timestamps

### Stage 7: Risk Scoring (83-93%)
- `candidate/risk_scorer.py` — `RiskScorer.analyze()`
- 9 categories: identity, business, courts, FSSP, bankruptcy, sanctions, social, behavioral, identity_flags
- Composite score -> CLEAN/LOW/MEDIUM/HIGH/CRITICAL

### Stage 8: Report Generation (93-100%)
- `candidate/report_builder.py`
- Compiles dossier with identity card, identity confirmation section, all stage data, social graph, geo map
- Export: PDF (Playwright), JSON

## 6. People Search (Legacy)

### Flow
1. User opens `/api/search/page` -> `people_search.html` (two-column VK | Telegram)
2. User enters name, optional city/age, clicks search
3. JS fires VK search first: `POST /api/search/vk` -> `buratino_vk_search.py`
4. VK results render in left column. Screen names extracted.
5. JS fires Telegram search: `POST /api/search/telegram` with `vk_screen_names`
6. `telegram_discovery.py` runs 3 methods sequentially, renders in right column
7. User selects a profile -> "Proceed to Phase 2" saves selection to Investigation

### VK Search Internals
- `BuratinoVKSearch.search()` — 4 strategies using VK API `users.search`
- Dual-token: `VK_SERVICE_TOKEN` (search), `VK_USER_TOKEN` (private data)
- Name verification: `verify_profile_name_matches_query()` — surname >= 0.7 similarity + first name >= 0.65 or diminutive match
- Diminutive matching: `russian_diminutives.py` — 78+ formal names with bidirectional lookup (Александр <-> Саша <-> Шура)
- Transliteration: `transliteration.py` — GOST, BGN/PCGN, passport, informal systems
- Demo mode: returns 3 fake profiles when VK_SERVICE_TOKEN unset

### Telegram Search Internals
- `TelegramDiscoveryService.discover()` — 3 sequential methods
- Method A: Check `t.me/{vk_screen_name}` for each VK result (rate: 0.35s delay)
- Method B: Generate username candidates from name (transliteration + diminutives), check `t.me/`
- Method C: Telethon `contacts.SearchRequest` by Cyrillic name, diminutives, Latin transliteration
- Name verification: `_score_name_match()` — 4-pass cross-script comparison (original, Latin, cross-script diminutive, first-name-only cap at 0.55)
- Auth: `python scripts/auth_telegram.py` creates `tg_session/ibp_session.session`

## 7. External APIs & Services

| Service | Config Key | Required | Cost | Fallback |
|---------|-----------|----------|------|----------|
| VK API | `VK_SERVICE_TOKEN` | Yes | Free | Demo mode (3 fake profiles) |
| VK Private Data | `VK_USER_TOKEN` | No | Free | Skip wall/friends/photos |
| Telegram | `TELEGRAM_API_ID/HASH/PHONE` | No | Free | Skip Telethon (Methods A/B still work) |
| nalog.ru EGRUL | (none) | No | Free | Rusprofile fallback |
| sudact.ru | (none) | No | Free | Manual URL |
| checko.ru | (none) | No | Free | FSSP fallback |
| casebook.ru | (none) | No | Free | Manual URL |
| EFRSB | (none) | No | Free | Playwright fallback |
| OpenSanctions | (none) | No | Free | None |
| Interpol | (none) | No | Free | None |
| Claude AI | `ANTHROPIC_API_KEY` | No | Paid | Returns None (pipeline continues) |
| Search4Faces API | `SEARCH4FACES_API_KEY` | No | $40+/mo | Playwright free fallback |
| Hunter.io | `HUNTER_API_KEY` | No | 25/mo free | SMTP fallback |
| HudsonRock | (none) | No | Free | None |
| LeakCheck Public | (none) | No | Free | None |
| ProxyNova COMB | (none) | No | Free | None |
| HIBP | (none/`HIBP_API_KEY`) | No | Free k-anonymity / $3.50/mo | k-anonymity |
| Holehe | (none) | No | Free | None |
| Snusbase | `SNUSBASE_API_KEY` | No | $5-16/mo | Empty results |
| DeHashed | `DEHASHED_EMAIL/API_KEY` | No | $5.49/mo | Empty results |
| LeakCheck Pro | `LEAKCHECK_API_KEY` | No | $2.99-24.99/mo | Free public tier |
| GetContact | `GETCONTACT_API_KEY` | No | Paid | Empty results |
| NumBuster | `NUMBUSTER_API_KEY` | No | Paid | Empty results |
| FSSP API | `FSSP_API_TOKEN` | No | Free (Russian IP) | checko.ru + Playwright |
| Snoop | `OSINT_TOOLS_DIR` | No | Free | Skip |
| Maigret | pip install | No | Free | Skip |
| Sherlock | pip install | No | Free | Skip |

## 8. VK Dual-Token Architecture

| Token | Variable | Methods | How to Get |
|-------|----------|---------|------------|
| Service | `VK_SERVICE_TOKEN` | users.search, users.get, newsfeed.search | VK app settings |
| User | `VK_USER_TOKEN` | wall.get, friends.get, photos.getAll, market.get | `python scripts/auth_vk.py` |
| Legacy | `VK_TOKEN` | Fallback for user token | VK OAuth (24h expiry) |

Priority chain: `VK_USER_TOKEN` -> `VK_TOKEN` -> `VK_SERVICE_TOKEN` -> demo mode.
Helper: `from app.utils.vk_token_manager import get_vk_token` — `get_vk_token('search')` / `get_vk_token('private')`

## 9. Authentication & Security

- **Password auth**: Optional. Enabled when `IBP_PASSWORD` or `IBP_PASSWORD_HASH` set.
- **bcrypt** hashing with cached hash computation
- **Session timeout**: `IBP_SESSION_TIMEOUT` (default 3600s), `IBP_SESSION_REMEMBER` (30 days)
- **Session fixation protection** via session regeneration on login
- **Open redirect protection** in login flow
- **Global auth check**: `@app.before_request` — allows health check, login, static files
- **Security headers**: CSP, X-Frame-Options DENY, HSTS, X-Content-Type-Options nosniff
- **CSRF**: Flask-WTF globally, disabled in testing
- **Rate limiting**: Flask-Limiter. Login: 10/min, searches: 10-30/min, exports: 5/min
- **Input sanitization**: HTML tag stripping, length limits, format validation on all user inputs

## 10. Demo Mode

Triggered when `VK_SERVICE_TOKEN` is unset (sets `DEMO_MODE=True` in config).
- VK search returns 3 fake profiles with demo data
- Social graph returns 8 fake friends
- All paid services return empty lists (no fake data)
- Local LeakDB auto-loads demo data from `data/demo/`

## 11. Testing

**127 unit tests** across 13 test files in `tests/unit/`, plus:
- `tests/e2e/test_candidate_stress.py` — E2E stress tests with Playwright
- `tests/security/test_security_audit.py` — Security vulnerability checks

Previous suite (69 files, 3,794+ tests) was cleaned up during production prep. Unit tests rebuilt during bug-fixing sessions (March 2026).
Run with: `python -m pytest tests/ -v -p no:faulthandler` (Windows requires `-p no:faulthandler`)

## 12. Key Code Patterns

### Bidirectional Diminutive Matching
`app/services/phase1/russian_diminutives.py` — 78+ formal Russian names with all diminutive forms. `get_all_name_variants(name)` returns all forms regardless of direction. Used in VK/Telegram name verification.

### Multi-System Transliteration
`app/services/phase1/transliteration.py` — `transliterate_russian(name, max_variants=12)` generates all transliteration variants (GOST, BGN/PCGN, passport, informal). Handles ambiguities: Х->{Kh,H,X}, special surname endings: ой->{oi,oy}.

### 4-Pass Cross-Script Name Matching
`telegram_discovery.py:_score_name_match()`:
1. Original comparison (Cyrillic vs Cyrillic)
2. Latin transliteration (both sides)
3. Cross-script diminutive check
4. First-name-only cap (single-word displays max 0.55)

### Background Thread + Progress Polling
`CandidateTaskStatus` in-memory dict. Pipeline updates `status.percent`, `status.messages[]`, `status.stage`. Frontend polls every 2s. Auto-cleanup after 1h.

### Graceful Service Degradation
Every external service is wrapped in try/except. Missing API keys -> empty results. Service errors -> logged warning, pipeline continues. No single failure crashes the pipeline.

### Confidence Scoring
Numeric 0.0-1.0 per source. Russian labels: высокая (>=0.75), средняя (>=0.50), низкая (<0.50). Cross-source boost: +0.15 for 3+ independent sources, max 0.98.

## 13. Known Issues

1. Legacy phase routes render deleted templates (will 500 if accessed)
2. FSSP API has persistent SSL errors (uses checko.ru as primary)
3. Holehe is slow (~25s/email, 120s pipeline timeout)
4. Yandex People search is CAPTCHA-prone and unreliable
5. pymorphy2 needs `inspect.getfullargspec` shim on Python 3.12+
6. Rusprofile returns 403/429 under load (falls through to nalog.ru)
7. SocialProfile.full_name is a property, not a setter
8. pytest on Windows needs `-p no:faulthandler`
9. **FSSP CAPTCHA-blocked**: All automated strategies (API, AJAX, Playwright) blocked by CAPTCHA. Manual fallback works (`source='manual'`). Need `FSSP_API_TOKEN` from https://api-ip.fssp.gov.ru or Russian IP. checko.ru `/person` endpoint returns 404.
10. **Telegram Method C session**: Telethon works but session file needs interactive creation via `python scripts/auth_telegram.py`. Session path: `tg_session/ibp_session.session`.
11. **Court case regex** (fixed March 2026): Was missing Cyrillic letters in case numbers (e.g., `2А-1853/2025`). Fixed regex in 5 locations in `court_search.py`.
12. **ё/е normalization** (fixed March 2026): Caused valid name matches to score 0.0. Added `_normalize_yo()` to `telegram_discovery.py` and `telegram_crossref.py`.

## 14. Commands

```bash
python run.py                                       # Dev server at http://127.0.0.1:5000
pip install -r requirements.txt                     # Install dependencies
python -m pytest tests/ -v -p no:faulthandler      # Run tests
python scripts/auth_telegram.py                     # Telethon session auth
python scripts/auth_telegram.py --check             # Validate Telegram session
python scripts/auth_vk.py                           # VK OAuth token
python scripts/load_leaks.py <name> <file>          # Load leak data
python scripts/update_mvd_list.py                   # Update MVD wanted list
python scripts/update_extremist_list.py             # Update extremist list
```

## 15. Bugs Fixed (March 2026 Sessions)

### Session 1 (Previous)
- **VK contact extraction**: Expanded API fields, added social link/personal section/Telegram handle extraction
- **Geo NER**: Expanded RUSSIAN_CITIES from 25 to 98 entries, added text pattern matching from VK post text
- **Maigret**: Added standalone CLI detection, improved fallback logging
- **Snoop**: Improved fallback warning with install instructions

### Session 2 (Current)
- **ё/е normalization bug**: "Артём" vs "Артем" caused 0.0 match scores in Telegram name matching. Added `_normalize_yo()` to `telegram_discovery.py` and `telegram_crossref.py`.
- **Court case number regex**: Missed Cyrillic letters (e.g., `2А-1853/2025` for administrative cases). Fixed from `\d{1,2}-\d+/\d{4}` to `\d{1,2}[А-Яа-я]{0,3}-\d+/\d{4}` in 5 locations in `court_search.py`. Was dropping ~10% of results.
- **FSSP investigation**: Confirmed all automated strategies (API, AJAX, Playwright) are CAPTCHA-blocked. Manual fallback verified working. No code bug — needs `FSSP_API_TOKEN` or Russian IP.
- **Export endpoints**: Verified all three (JSON/PDF/HTML) working with correct headers, `@csrf.exempt` on all download routes, valid PDF output via reportlab.
