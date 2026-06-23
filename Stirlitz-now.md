# Stirlitz — Complete Platform Reference
## Last updated: 2026-06-23

---

## 1. What It Is

**Штирлиц (Stirlitz)** — self-hosted Russian-language OSINT background check platform. User enters name + date of birth + INN → system runs a 9-stage automated pipeline across 30+ sources → returns structured dossier with risk score.

Branded as **СЛЕД** (Stirlitz). IBP = Identity-Based Profiler (internal codename).

**Target:** B2B — HR departments, corporate security services, recruitment agencies, landlord companies.

**Status:** Pre-production. Core pipeline fully functional. Subscription payment stubbed (no real processor). Self-service registration open. First real deploy: 2026-06-19.

**Two investigation types:**
- Тип 01 — Кандидат (person background check, 9-stage pipeline)
- Тип 02 — Юридическое лицо / ИП (company check, 3-wave pipeline)

---

## 2. Infrastructure & Deployment

| Item | Value |
|---|---|
| VPS | reg.ru, IP `194.67.99.107` |
| OS | Linux (reg.ru managed) |
| App path | `/opt/ibp/` |
| Process manager | Gunicorn via systemd (`ibp.service`) |
| Reverse proxy | Nginx (SSL termination, proxies to Gunicorn) |
| Workers | Gunicorn (2 workers, 120s timeout — Render config) |
| SSH | `ssh fedor@194.67.99.107` (root disabled) |
| Deploy | `git pull` → `pip install -r requirements.txt` → `alembic upgrade head` → `sudo systemctl restart ibp` |
| DB (prod) | SQLite at `/opt/ibp/ibp_investigations.db` (PostgreSQL ready via `DATABASE_URL`) |
| DB (dev) | SQLite WAL mode, 30s busy timeout, `ibp_investigations.db` |
| Repo | https://github.com/FedorPortnoi/ibp (private) |
| Landing repo | https://github.com/FedorPortnoi/shtirlitz-landing (private) |
| Telegram session | `/opt/ibp/tg_session/ibp_session.session` |

**wsgi.py:** file not found — entry point is `run.py` or gunicorn targets `app:create_app()`.
**gunicorn.conf.py:** file not found — Gunicorn launched via systemd unit directly.
**Dockerfile / docker-compose.yml:** exist (Docker setup present but not primary deploy).
**nginx.conf:** not found in root (nginx config managed on server separately).

---

## 3. Domain & SSL

- Domain: **shtirletzsled.ru**
- SSL: nginx terminates TLS (HSTS set: `max-age=31536000; includeSubDomains; preload`)
- Health check: `GET /health` (unauthenticated → `{"status":"ok"}`)
- Readiness: `GET /ready` (unauthenticated → `{"status":"ok","database":true,"local_data":{...}}`)

---

## 4. Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.12 (dev/Windows), 3.11 (Render/prod) |
| Web framework | Flask 3.1.3 |
| ORM | Flask-SQLAlchemy 3.1.1 + SQLAlchemy 2.0.45 |
| Migrations | Flask-Migrate 4.1.0 (Alembic) |
| CSRF | Flask-WTF 1.2.2 |
| Rate limiting | Flask-Limiter 4.1.1 (memory:// or Redis) |
| Database | SQLite (dev) / PostgreSQL (prod target) |
| Browser automation | Playwright 1.58.0 (Chromium headless) — courts, PDF export, Search4Faces fallback |
| Telegram | Telethon 1.42.0 |
| NLP | pymorphy2 0.9.1 + pymorphy2-dicts-ru (Russian morphology; Python 3.12 shim required) |
| Social graph | NetworkX 2.8.8 + python-louvain 0.16 |
| Auth hashing | bcrypt 4.3.0 |
| Email | Resend API (`resend` package via HTTP) |
| AI | anthropic 0.96.0 |
| HTTP clients | requests 2.33.0, httpx 0.28.1, aiohttp 3.13.4 |
| HTML parsing | BeautifulSoup4 4.12.3 + lxml 6.1.0 |
| Phone parsing | phonenumbers 9.0.21 |
| PDF export | Playwright Chromium headless print (no WeasyPrint — Windows constraint) |
| Frontend | Tailwind CSS (CDN) + vis.js (social graph) + Leaflet.js (geo map) + Chart.js |
| Process manager | Gunicorn 25.0.3 |
| Process monitoring | psutil 7.2.2 (Playwright zombie killer) |
| Data enrichment | dadata.ru (DaData API) |
| DoS protection | Custom middleware (in-memory + Redis optional) |

---

## 5. Environment Variables (names only, no values)

From `.env` and `config.py`:

**Flask core:**
- `FLASK_ENV`
- `SECRET_KEY`
- `FLASK_SECRET_KEY` (fallback for SECRET_KEY)
- `DATABASE_URL`
- `PREFERRED_URL_SCHEME`

**Auth / session:**
- `IBP_PASSWORD`
- `IBP_PASSWORD_HASH`
- `IBP_SESSION_TIMEOUT` (default: 3600s)
- `IBP_SESSION_REMEMBER` (default: 2592000s)
- `IBP_REGISTRATION_OPEN` (set to 1 to allow self-service registration)
- `IBP_STUB_PAYMENTS` (set to 1 for dev-only instant subscription activation)

**VK API:**
- `VK_SERVICE_TOKEN`
- `VK_USER_TOKEN`
- `VK_API_VERSION` (default: 5.199)
- `VK_APP_ID`
- `VK_TOKEN`
- `VK_LOGIN`
- `VK_LOGIN_EMAIL`
- `VK_PASSWORD`

**Telegram:**
- `TELEGRAM_API_ID`
- `TELEGRAM_API_HASH`
- `TELEGRAM_PHONE`

**AI:**
- `ANTHROPIC_API_KEY`

**Email:**
- `RESEND_API_KEY`

**DaData:**
- `DADATA_API_KEY`
- `DADATA_SECRET`

**Breach APIs:**
- `LEAKCHECK_API_KEY`
- `SNUSBASE_API_KEY`
- `DEHASHED_EMAIL`
- `DEHASHED_API_KEY`
- `HIBP_API_KEY`

**Face search:**
- `SEARCH4FACES_API_KEY`

**Phone lookup:**
- `GETCONTACT_API_KEY`
- `GETCONTACT_TOKEN`
- `GETCONTACT_AES_KEY`
- `GETCONTACT_DEVICE_ID`
- `NUMBUSTER_API_KEY`
- `HIMERA_API_KEY`

**Email discovery:**
- `HUNTER_API_KEY`
- `EMAILREP_API_KEY`
- `SNOV_CLIENT_ID`
- `SNOV_CLIENT_SECRET`

**Government / legal:**
- `PARSER_API_KEY` (parser-api.com — ФССП + kad.arbitr proxy)
- `FSSP_API_TOKEN` (dead — api-ip.fssp.gov.ru shut down Feb 2026)

**Other:**
- `GITHUB_TOKEN`
- `INFOTRACKPEOPLE_API_KEY`
- `LEAKDB_DATA_DIR`
- `REDIS_URL` (optional; enables shared rate-limit counters across workers)
- `APP_VERSION`
- `ENABLE_PEOPLE_SEARCH` (legacy phase1–4 routes; default off)
- `ENABLE_GEO_RESTRICTED_CHECKERS` (Gosuslugi + Sberbank oracles)

---

## 6. Database Models (every field of every model)

### Table: `users`
| Column | Type | Notes |
|---|---|---|
| `id` | Integer PK | |
| `username` | String(64) | unique, indexed |
| `password_hash` | String(128) | bcrypt |
| `role` | String(16) | `'admin'` or `'user'` |
| `email` | String(120) | nullable |
| `created_at` | DateTime | utcnow |
| `is_active` | Boolean | default True |

**Relationships:** `checks` (→ CandidateCheck, dynamic), `subscription` (→ Subscription, uselist=False)

**Methods:**
- `set_password(password)` — bcrypt hash + store
- `check_password(password)` — bcrypt verify
- `is_admin` (property) — role == 'admin'

---

### Table: `candidate_checks`
| Column | Type | Notes |
|---|---|---|
| `id` | String(36) PK | UUID hex |
| `created_at` | DateTime | |
| `completed_at` | DateTime | nullable |
| `status` | String(20) | pending/running/complete/error/awaiting_confirmation |
| `full_name` | String(255) | required |
| `date_of_birth` | Date | required |
| `inn` | String(12) | required |
| `passport_series` | String(4) | nullable |
| `passport_number` | String(6) | nullable |
| `registered_address` | Text | nullable |
| `region` | String(100) | nullable |
| `phone` | String(20) | nullable |
| `email` | String(255) | nullable |
| `photo_path` | String(500) | nullable |
| `identity_confirmation` | Text (JSON) | Stage 0 result |
| `confirmed_name` | String(255) | nullable |
| `identity_confirmed` | Boolean | default False |
| `business_records` | Text (JSON) | |
| `court_records` | Text (JSON) | |
| `court_source_statuses` | Text (JSON) | per-source: ok/empty/blocked/timeout/error |
| `fssp_records` | Text (JSON) | |
| `fssp_status` | String(20) | ok/empty/blocked/rate_limited/timeout/error |
| `bankruptcy_records` | Text (JSON) | |
| `sanctions_results` | Text (JSON) | |
| `pledge_records` | Text (JSON) | |
| `source_statuses` | Text (JSON) | general per-source status map |
| `adverse_media` | Text (JSON) | Yandex-sourced negative news hits |
| `connections` | Text (JSON) | Axis 2: web of connections |
| `social_media_profiles` | Text (JSON) | |
| `contact_discoveries` | Text (JSON) | {phones: [], emails: []} |
| `check_mode` | String(20) | 'quick' or 'precise' |
| `paused_at_stage` | String(50) | nullable; 'awaiting_confirmation' |
| `pd_consent` | Boolean | 152-FZ |
| `pd_consent_at` | DateTime | nullable |
| `user_id` | Integer FK → users.id | indexed |
| `confirmed_profiles` | Text (JSON) | Stage 3 precise mode confirmations |
| `social_graph_data` | Text (JSON) | vis.js graph data |
| `face_matches` | Text (JSON) | Search4Faces results |
| `username_accounts` | Text (JSON) | Snoop/Maigret/Sherlock results |
| `geo_intelligence` | Text (JSON) | aggregated from all stages |
| `geo_analysis` | Text (JSON) | Stage 6 VK location analysis |
| `text_analysis` | Text (JSON) | Stage 6 VK wall text analysis |
| `activity_timeline` | Text (JSON) | Stage 6 timeline events |
| `group_analysis` | Text (JSON) | Stage 6 VK groups |
| `activity_patterns` | Text (JSON) | Stage 6 patterns |
| `vk_snapshot` | Text (JSON) | Stage 6 VK profile snapshot |
| `connected_checks` | Text (JSON) | cross-check links |
| `risk_breakdown` | Text (JSON) | category → {count, score, max_severity} |
| `risk_score_numeric` | Float | 0-100 |
| `risk_score` | Integer | 0-100 |
| `risk_narrative` | Text | AI-generated (Stage 7) |
| `behavioral_summary` | Text | AI-generated (Stage 6) |
| `executive_summary` | Text | AI-generated (Stage 8) |
| `report_generated` | Boolean | default False |
| `risk_level` | String(20) | low/medium/high/critical |
| `red_flags` | Text (JSON) | |
| `red_flag_count` | Integer | |
| `task_id` | String(36) | indexed |
| `task_progress` | Integer | 0-100 |
| `task_stage` | String(50) | |
| `task_message` | String(500) | |
| `task_log` | Text (JSON) | last 40 pipeline messages |
| `task_error` | Text | nullable |
| `sources_checked` | Integer | |
| `sources_with_results` | Integer | |
| `check_duration_seconds` | Float | |

**Computed properties:** `check_level`, `check_level_display`, `risk_level_display`, `name_parts`, `task_status_dict()`, `to_dict()`

---

### Table: `company_checks`
| Column | Type | Notes |
|---|---|---|
| `id` | String(36) PK | UUID |
| `created_at` | DateTime | |
| `completed_at` | DateTime | nullable |
| `status` | String(20) | pending/running/complete/error |
| `inn` | String(12) | 10-digit company / 12-digit ИП |
| `query_name` | String(255) | optional user name hint |
| `company_name` | String(500) | from EGRUL |
| `company_short_name` | String(255) | |
| `company_type` | String(50) | ООО/АО/ИП/etc. |
| `company_status` | String(50) | active/liquidated/etc. |
| `ogrn` | String(15) | |
| `egrul_data` | Text (JSON) | full EGRUL profile |
| `court_records` | Text (JSON) | |
| `fssp_records` | Text (JSON) | |
| `sanctions_results` | Text (JSON) | |
| `bankruptcy_data` | Text (JSON) | |
| `sanctions_meta` | Text (JSON) | {no_key, unavailable} |
| `gov_contracts_data` | Text (JSON) | ЕИС Закупки |
| `financial_data` | Text (JSON) | dadata.ru financial snapshot |
| `rnp_data` | Text (JSON) | реестр недобросовестных поставщиков |
| `risk_flags` | Text (JSON) | |
| `risk_score` | Integer | 0-100 |
| `risk_level` | String(20) | |
| `task_id` | String(36) | indexed |
| `task_progress` | Integer | |
| `task_stage` | String(50) | |
| `task_message` | String(500) | |
| `task_log` | Text (JSON) | |
| `task_error` | Text | nullable |
| `task_started_at` | DateTime | nullable |
| `user_id` | Integer FK → users.id | indexed |
| `sources_checked` | Integer | |
| `check_duration_seconds` | Float | |

**Computed:** `display_name`, `risk_level_display`, `task_status_dict()`, `to_dict()`

---

### Table: `subscriptions`
| Column | Type | Notes |
|---|---|---|
| `id` | Integer PK | |
| `user_id` | Integer FK → users.id | unique |
| `status` | String(16) | 'active' / 'inactive' / 'expired' |
| `started_at` | DateTime | nullable |
| `expires_at` | DateTime | nullable |
| `auto_renew` | Boolean | default False |
| `payment_id` | String(128) | nullable (YooKassa or 'stub_N') |
| `created_at` | DateTime | |
| `updated_at` | DateTime | onupdate |

**Constants:** `FREE_CHECKS_PER_WEEK = 2`

**Methods:**
- `is_active` (property) — status=='active' and not expired
- `is_free_tier` (property) — not is_active
- `days_left` (property) — days until expiry
- `free_checks_used_this_week()` — count checks this ISO week
- `free_checks_remaining()` — max(0, 2 - used)
- `can_run_check()` — is_active or remaining > 0
- `activate(payment_id, auto_renew)` — sets status='active', expires_at=now+30d

---

### Table: `audit_log`
| Column | Type | Notes |
|---|---|---|
| `id` | Integer PK | |
| `created_at` | DateTime | indexed |
| `user_id` | Integer FK → users.id | nullable, SET NULL on delete, indexed |
| `ip_address` | String(45) | IPv6-safe |
| `action` | String(64) | indexed (auth.login, auth.login_failed, auth.register, auth.logout, check.start, check.delete, check.export_pdf, check.export_json, subscription.activate) |
| `outcome` | String(16) | success/failure/denied |
| `target_type` | String(64) | nullable |
| `target_id` | String(36) | nullable |
| `_extra` (col: metadata) | Text (JSON) | nullable |

---

### Table: `login_attempts`
| Column | Type | Notes |
|---|---|---|
| `id` | Integer PK autoincrement | |
| `username_lower` | String(64) | indexed |
| `attempted_at` | DateTime | indexed |

Used for per-username lockout: 5 failures in 5 minutes → 15-minute lockout.

---

### Table: `chat_messages`
| Column | Type | Notes |
|---|---|---|
| `id` | Integer PK | |
| `user_id` | Integer FK → users.id | indexed |
| `content` | Text | max 4000 chars |
| `is_pinned` | Boolean | default False |
| `created_at` | DateTime | indexed |

**Methods:** `to_dict()`

---

## 7. Routes & Endpoints (every route, method, auth requirement, what it does)

### Blueprint: `auth` (prefix: none)

| Route | Method | Auth | Description |
|---|---|---|---|
| `/set-lang/<lang>` | GET | public | Set session language (ru/en); redirects to /login |
| `/login` | GET, POST | public | Login form. POST rate-limited: 5/min, 20/hr. Checks per-username lockout. Sets session, logs auth.login |
| `/register` | GET, POST | public | Self-service registration. Gated by `IBP_REGISTRATION_OPEN`. Rate-limited: 5/min, 20/hr. Creates User + Subscription, signs in |
| `/logout` | POST | public | Clears session, redirects to /login |

**Helper functions:**
- `detect_language()` — geo-IP (ip-api.com) + Accept-Language → 'ru' or 'en'
- `get_current_user()` — returns User from session or None
- `login_required(f)` — decorator; redirects to /login if not authenticated
- `admin_required(f)` — decorator; 403 if not admin
- `_record_login_failure(username)` — writes LoginAttempt
- `_clear_login_failures(username)` — deletes LoginAttempt rows on success
- `_is_locked_out(username)` — checks ≥5 failures in 5min window

---

### Blueprint: `main` (prefix: none)

| Route | Method | Auth | Description |
|---|---|---|---|
| `/health` | GET | public (detail: auth) | Liveness. Unauthenticated: `{"status":"ok"}`. Authenticated+admin: full service status |
| `/ready` | GET | public | Readiness: DB connectivity + local data files |
| `/privacy` | GET | public | Privacy policy page (152-FZ compliance) |
| `/` | GET | required | Redirects to /dashboard |
| `/dashboard` | GET | required | Investigation type selection screen |
| `/investigations` | GET | required | Redirects to /candidate/history |
| `/vk/auth` | GET | admin | Redirect to VK OAuth URL |
| `/vk/callback` | GET | admin | VK OAuth callback landing page |
| `/vk/save-token` | POST | admin | Save VK token from OAuth callback |
| `/api/vk/token-status` | GET | admin | Get VK token status |

**Helper functions:**
- `_project_root()` — resolve absolute path to project root
- `_probe_database()` — SELECT 1 health check
- `_app_version()` — read VERSION file or APP_VERSION env
- `_local_data_status()` — check mvd_wanted.json + extremist_list.json exist

---

### Blueprint: `candidate` (prefix: `/candidate`)

| Route | Method | Auth | Rate limit | Description |
|---|---|---|---|---|
| `/new` | GET | required | — | Render candidate check form |
| `/start` | POST | required | 10/min, 50/hr | Validate inputs + 152-FZ consent + free tier check + create CandidateCheck + launch pipeline thread; redirect to progress |
| `/progress/<task_id>` | GET | required (owner) | — | Progress page (polls status endpoint every 2s) |
| `/progress/<task_id>/status` | GET | required (owner) | exempt | JSON status polling; in-memory first, DB fallback |
| `/confirm/<check_id>` | GET | required (owner) | — | Profile confirmation page (Precise mode only) |
| `/confirm/<check_id>` | POST | required (owner) | — | Submit confirmed profiles, resume pipeline |
| `/confirm/<check_id>/retry-expanded` | POST | required (owner) | 5/min | Re-run VK search with relaxed thresholds |
| `/confirm/<check_id>/search-name` | POST | required (owner) | 5/min | Search VK by alternative name (maiden, alias) |
| `/confirm/<check_id>/manual-vk` | POST | required (owner) | 5/min | Validate + add manually entered VK profile URL |
| `/api/social-graph/<check_id>` | GET | required (owner) | — | Return vis.js social graph JSON |
| `/api/geo-data/<check_id>` | GET | required (owner) | — | Return geo analysis JSON |
| `/api/geo-intelligence/<check_id>` | GET | required (owner) | — | Return aggregated geo intelligence JSON |
| `/api/timeline/<check_id>` | GET | required (owner) | — | Return activity timeline JSON |
| `/dossier/<check_id>` | GET | required (owner) | — | Render completed dossier |
| `/history` | GET | required | — | List user's past checks (admin → redirects to admin panel) |
| `/delete/<check_id>` | POST | required (owner) | 10/min | Delete check record + photo |
| `/export/<check_id>/json` | GET | required (owner) | 5/min | Download dossier as JSON file |
| `/export/<check_id>/pdf` | GET | required (owner) | 5/min | Generate PDF via Playwright Chromium |

**Helper functions:**
- `_is_valid_image_header(header, ext)` — magic bytes validation for uploaded photos
- `_check_owner_or_admin(check)` — IDOR guard
- `_check_owner_or_admin_by_task(task_id)` — IDOR guard by task_id
- `_safe_filename(name_slug)` — Cyrillic→Latin transliteration + sanitize for Content-Disposition
- `_format_duration(seconds)` — seconds to "Xм Yс" string
- `_export_filename(check, ext)` — build dossier_<Name>_<date>.<ext>
- `_vk_post_json(client, method, data)` — VK API call with short timeouts
- `_fetch_manual_vk_profile(screen_name)` — resolve VK screen name → profile dict
- `_lookup_manual_vk_profile(screen_name)` — run VK lookup in executor with 8s cap
- `_manual_vk_error_response(error)` — map ManualVKLookupError to JSON response

---

### Blueprint: `company` (prefix: `/company`)

| Route | Method | Auth | Rate limit | Description |
|---|---|---|---|---|
| `/new` | GET | required | — | Render company investigation form |
| `/start` | POST | required | 10/min, 50/hr | Validate INN + free tier + create CompanyCheck + launch pipeline thread; return JSON with redirect |
| `/progress/<check_id>` | GET | required (owner) | — | Progress page |
| `/status/<check_id>` | GET | required (owner) | — | JSON status polling |
| `/check/<check_id>` | GET | required (owner) | — | Company dossier |
| `/history` | GET | required | — | List company checks |

---

### Blueprint: `subscribe` (prefix: none)

| Route | Method | Auth | Description |
|---|---|---|---|
| `/subscribe` | GET | login_required | Subscription page; skips if admin or already active |
| `/subscribe/pay` | POST | login_required | Process payment. Production: blocked unless `IBP_STUB_PAYMENTS=true`. Dev: activates immediately. Sends email confirmation. |
| `/subscribe/success` | GET | login_required | Success page |
| `/subscribe/status` | GET | login_required | Subscription status page |

---

### Blueprint: `admin_users` (prefix: `/admin/users`)

| Route | Method | Auth | Description |
|---|---|---|---|
| `/` | GET | admin | List all users with check count + last check date |
| `/<int:user_id>/investigations` | GET | admin | Show all investigations for a specific user |

---

### Blueprint: `chat` (prefix: `/chat`)

| Route | Method | Auth | Rate limit | Description |
|---|---|---|---|---|
| `/` | GET | required | — | Personal scratchpad (Telegram Favorites-style) |
| `/api/messages` | GET | required | — | List user's messages (pinned first, limit 500) |
| `/api/messages` | POST | required | 60/min | Post new message (max 4000 chars) |
| `/api/messages/<int:msg_id>` | DELETE | required (owner) | — | Delete message |
| `/api/messages/<int:msg_id>/pin` | POST | required (owner) | — | Toggle pin status |

---

## 8. Pipeline — Candidate Check (all 9 stages, every function name)

**Entry point:** `POST /candidate/start` → `run_candidate_pipeline(app, task_id, check_id)` in `app/services/candidate/pipeline.py`

**Execution model:** `threading.Thread` (daemon), in-memory `CandidateTaskStatus` + DB-backed progress sync. Max 10 concurrent tasks. Cleanup after 1hr (completed) or 30min (stuck).

### Stage 0: Identity Confirmation [0–8%]
**Wave: 2-worker ThreadPoolExecutor, 30s timeout each**

- `_stage0_egrul()` — EGRUL lookup by INN via `BusinessRegistrySearch.search_by_inn()`
- `_stage0_bankruptcy()` — bankruptcy lookup via `BankruptcyService.search()`
- `_lookup_company(c_inn)` — co-founder lookup for each linked company (up to 5 companies, 5-worker pool)
- `search_by_address()` — address co-registrants (from `phase3/address_intelligence.py`)
- `extract_address_coparties()` — extract Axis 2 connection edges from address results

**Writes:** `identity_confirmation`, `confirmed_name`, `identity_confirmed`, `business_records` (Stage 0 INN set), `bankruptcy_records`, `source_statuses['address_intel']`

---

### Stage 1: Government Registries [8–18%]
**Wave 1: parallel with Stage 2 (Stage 2 background thread launched first)**

**Parallel 3-worker pool:**
- `_search_business(full_name, inn)` — EGRUL by name + INN; returns (records, coparty_edges); inner `_lookup_company` for co-owners
- `_search_fssp(full_name, date_of_birth, region)` — 3-tier: parser-api.com → checko.ru → official FSSP (CAPTCHA-blocked)
- `_search_pledges(full_name)` — pledge registry via `PledgeRegistrySearch.search_by_name()`

**Sequential (after pool, 150s timeout):**
- `_search_courts(full_name, inn)` — 4 sources: судебныерешения.рф + reputation.su + kad.arbitr.ru (via parser-api) + sudact.ru; returns (records, source_statuses, coparty_edges)

**Post-processing:**
- `_normalize_court_confidence(records, candidate_region)` — maps high/medium → VERIFIED/LIKELY/POSSIBLE/UNVERIFIED
- `filter_business_records_by_inn(biz_records, check.inn)` — INN-based false-positive filter
- `summarize_court_cases(court_records)` — AI court case summaries (Claude)
- Adverse-media screening: `ams.search_adverse_media(name, context)` via Yandex

**Writes:** `business_records`, `court_records`, `court_source_statuses`, `fssp_records`, `fssp_status`, `pledge_records`, `source_statuses`, `adverse_media`

---

### Stage 2: Security Checks [18–27%]
**Runs parallel with Stage 1 in background `ThreadPoolExecutor(1)`**

- `_run_stage2_computation(effective_name, inn, passport_series, passport_number)` — pure computation, no DB access
- `SanctionsService.check_all(effective_name, inn)` — all sanctions sources
- `check_passport_mvd(passport_series, passport_number)` — MВД passport validity (dead since July 2023)

**Writes:** `sanctions_results`

---

### Stage 3: Social Media Discovery [27–42%]
**3-worker parallel pool, 45s shared timeout**

- `_vk_search_worker()` — `buratino_vk_search.search()` with name/city/age/DOB params
- `_tg_search_worker()` — `TelegramDiscoveryService.discover()` Methods B+C
- `_phone_tg_worker()` — `TelegramDiscoveryService.search_by_phone()` if phone provided
- `_do_vk_tg_xref()` — VK→TG cross-reference Method A (screen_names → Telegram); runs after pool in separate 1-worker pool, 30s timeout

**Precise Mode:** After Stage 3, pipeline pauses at `status='awaiting_confirmation'`; waits up to 30min for user confirmation; auto-resumes after timeout.

**Writes:** `social_media_profiles`

---

### Stage 4: Contact Discovery [42–57%]
**Wave 3: parallel with Stage 5 in 2-worker pool, 60s timeout**

- `_run_contact_discovery()` → `ContactDiscoveryService.discover(check)` — phones + emails from VK profiles, breach APIs, oracle, INN breach
- `run_phone_intelligence(check.phone)` — phone intelligence (runs while waiting for Stage 5)
- `search_inn_in_breaches(check.inn)` — INN in breach databases

**Stage 5e (feedback loop, after both Stage 4+5):**
- `contact_service.discover_supplementary(new_accounts, existing_contacts)` — enrichment from newly discovered accounts

**Writes:** `contact_discoveries`

---

### Stage 5: Deep Social Analysis [44–72%]
**Wave 3: parallel with Stage 4, 90s timeout**

- `_run_social_analysis()` → `run_social_analysis(check)` — face search + username search + social graph

**Writes:** `social_graph_data`, `face_matches`, `username_accounts`, `source_statuses['search4faces']`, `source_statuses['username_search']`

---

### Stage 6: Behavioral Intelligence [72–83%]
**Wave 4: single-worker pool, 60s timeout**

- `run_behavioral_analysis(check, callback)` — VK wall extraction + text analysis + geo analysis + group analysis + activity patterns

**AI:**
- `generate_behavioral_summary(text_analysis, full_name)` — Claude behavioral profile from VK posts

**Writes:** `text_analysis`, `geo_analysis`, `activity_timeline`, `group_analysis`, `activity_patterns`, `behavioral_summary`, `source_statuses['vk_wall']`

**Post-Stage 6:**
- `collect_geo_intelligence(check, is_demo)` — aggregate geo from all stages into `geo_intelligence`

---

### Stage 7: Risk Scoring [83–93%]
**Wave 5: synchronous on pipeline thread**

- `find_connected_checks(check)` — find checks that share phone/email with this candidate
- `build_from_check(check, extra_edges)` — build Axis 2 connection graph (companies, co-owners, address co-registrants, court co-parties)
- `RiskScorer.analyze(check)` — runs 15 sub-analyzers, returns (risk_level, red_flags)
  - `_analyze_identity(check)` — name discrepancy, INN not confirmed
  - `_analyze_business(check)` — serial entrepreneur, mass director, liquidations, address match
  - `_analyze_courts(check)` — criminal cases, fraud, many cases, defendant pattern
  - `_analyze_fssp(check)` — active debts, multiple active, debt amounts, alimony, tax
  - `_analyze_bankruptcy(check)` — active bankruptcy, recent bankruptcy
  - `_analyze_pledges(check)` — many pledges, pledge found
  - `_analyze_sanctions(check)` — sanctions match, unchecked sources
  - `_analyze_adverse_media(check)` — criminal confirmed, reputational confirmed, possible
  - `_analyze_social(check)` — no social presence
  - `_analyze_social_behavior(check)` — no friends, isolated graph, fake profile indicators, established identity
  - `_analyze_behavioral_patterns(check)` — negative sentiment, risk keywords, night activity, geo discrepancy, inactive profile
  - `_analyze_groups(check)` — political, criminal, gambling, drug, security groups
  - `_analyze_activity_patterns(check)` — from activity_patterns.activity_flags
  - `_analyze_profile_anomalies(check)` — new VK account (ID>700M), closed profile, no photo
  - `_analyze_connections(check)` — connected to high-risk candidate
- `calculate_risk_score(flags)` — weighted sum capped at 100; maps to low(<30)/medium(<60)/high(<80)/critical(≥80)

**AI:**
- `generate_risk_narrative(risk_level, risk_score, red_flags, full_name)` — Claude 2-3 sentence risk summary

**Writes:** `connected_checks`, `connections`, `red_flags`, `red_flag_count`, `risk_breakdown`, `risk_score`, `risk_score_numeric`, `risk_level`, `risk_narrative`

---

### Stage 8: Report Generation [93–100%]
**Wave 6: synchronous**

- `build_report(check)` — assemble final dossier data structure, sets `report_generated=True`
- `generate_executive_summary(check_data)` — Claude 1-paragraph executive summary

**Writes:** `report_generated=True`, `executive_summary`, `status='complete'`, `completed_at`, `check_duration_seconds`, `source_statuses['ai_summary']`

---

### CandidateTaskStatus class (`pipeline.py`)
- `__init__(task_id, check_id, full_name)` — init in-memory tracker
- `bind_check(check)` — bind ORM instance for DB persistence
- `add_message(text, msg_type)` — append to messages list
- `update(stage, step, percent)` — update all fields + call `_sync_to_db()`
- `_sync_to_db()` — write progress to DB (cross-worker visibility; last 40 messages)
- `to_dict()` — serialize to JSON-safe dict for polling endpoint

**Pipeline helpers:**
- `_normalize_court_confidence(records, candidate_region)` — confidence scale normalization
- `_is_demo_mode()` — True if VK_SERVICE_TOKEN not set
- `_get_demo_gov_data(full_name)` — stub biz/courts/fssp/bankruptcy data
- `_get_demo_sanctions()` — stub sanctions results
- `_get_demo_contacts(full_name)` — stub phone + email contacts
- `_kill_playwright_zombies(max_age_seconds)` — kill orphaned headless Chrome; called at start and end of every pipeline run
- `cleanup_old_tasks(task_store, max_age_seconds)` — remove completed tasks; force-complete stuck tasks (>30min)
- `_run_stage2_computation(...)` — background computation for Stage 2
- `_make_ctx_wrapper(app_obj)` — wrap callables with Flask app context for ThreadPoolExecutor threads
- `_pause()` — `time.sleep(0.05)` minimal rate-limit delay

---

## 9. Pipeline — Company Check

**Entry point:** `POST /company/start` → `run_company_pipeline(check_id, app)` in `app/services/company/company_pipeline.py`

**Architecture: 3-wave parallel**
- Wave 0: EGRUL lookup [0–35%]
- Wave 1: Courts + Sanctions in parallel [35–75%] — also: Bankruptcy, RNP, Gov Contracts, Financial (all parallel)
- Wave 2: Risk scoring [75–100%]

**Pipeline functions:**
- `_log(check, msg)` — append log entry + commit
- `_set_progress(check, pct, stage, msg)` — update progress fields + commit
- `_run_egrul(check)` — `EGRULService.lookup(inn)` → company profile dict
- `_run_courts(inn, query_name, egrul)` — `CompanyCourtSearch.search()` → court case list
- `_run_financial(inn, query_name, egrul)` — `FinancialService.lookup(inn)` → financial snapshot
- `_run_gov_contracts(inn, query_name, egrul)` — ЕИС Закупки contract search
- `run_company_pipeline(check_id, app)` — main orchestrator

**Company services:**
- `EGRULService` — EGRUL company profile lookup
- `CompanyCourtSearch` — court cases for company; `get_manual_search_urls()` — returns kad.arbitr search URLs
- `FinancialService` — dadata.ru financial snapshot
- `GovContractsService` — ЕИС Закупки (госзакупки.gov.ru)
- `FedresursService` — bankrot.fedresurs.ru bankruptcy
- `RnpService` — реестр недобросовестных поставщиков (FAS)
- `SanctionsLocalService` — local OpenSanctions DB for companies
- `PlaywrightFinancialService` — Playwright-based financial data fallback

---

## 10. Phase 1: Identity Resolution (every function, what it does)

### `phase1/combined_search.py`
- `CombinedSearch.search(query, ...)` — orchestrate all Phase 1 search methods

### `phase1/buratino_vk_search.py`
- `BuratinoVKSearch.search(query, first_name, last_name, target_name, city, age_from, age_to, birth_day, birth_month, birth_year)` — VK people.search + name similarity scoring; returns (profiles, metadata)
- `BuratinoVKSearch.search_expanded(query, city, age_from, age_to, count)` — relaxed-threshold VK search for "retry expanded" button
- `buratino_vk_search` — module-level singleton instance

### `phase1/vk_web_search.py`
- `VKWebSearch.search(query, first_name, last_name, city, age_from, age_to)` — VK web search with explicit name params

### `phase1/yandex_search.py`
- `YandexSearch.search(query, ...)` — Yandex people search (CAPTCHA-prone, unreliable)

### `phase1/telegram_discovery.py`
- `TelegramDiscoveryService.discover(first_name, last_name, vk_screen_names, city, birth_year)` — Methods B+C Telegram discovery
- `TelegramDiscoveryService.search_by_phone(phone)` — phone → Telegram profile via Telethon
- `TelegramDiscoveryService._method_a_vk_crossref(vk_screen_names, first, last)` — VK screen name → Telegram username cross-ref
- `TelegramDiscoveryService.close()` — clean up Telethon client

### `phase1/fuzzy_matching.py`
- `fuzzy_match(name1, name2, threshold)` — fuzzy name matching with threshold
- `calculate_similarity(s1, s2)` — string similarity score

### `phase1/russian_diminutives.py`
- `get_diminutives(name)` — return list of Russian diminutive forms for a name
- `normalize_name(name)` — canonical form

### `phase1/transliteration.py`
- `transliterate(text)` — Cyrillic → Latin transliteration (multiple schemas)
- `reverse_transliterate(text)` — Latin → Cyrillic

---

## 11. Phase 2: Digital Footprint (every function, what it does)

### `phase2/combined_search.py`
- `Phase2Search.run(check)` — orchestrate all Phase 2 searches

### `phase2/phone_discovery.py`
- `PhoneDiscovery.discover(profiles, input_phone)` — extract phones from social profiles

### `phase2/phone_intelligence.py`
- `run_phone_intelligence(phone)` — aggregate phone info from all sources; returns summary dict

### `phase2/email_discovery.py`
- `EmailDiscovery.discover(profiles, input_email, full_name, inn)` — extract/guess emails

### `phase2/breach_checker.py`
- `BreachChecker.check_email(email)` — check email across all configured breach APIs
- `BreachChecker.check_phone(phone)` — check phone in breach databases

### `phase2/forgot_password_oracle.py`
- `ForgotPasswordOracle.check_all(email, phone)` — run all 8 checkers (VK, Mail.ru, Yandex, OK.ru, Gosuslugi, Telegram, Avito, Sberbank)
- `cross_correlate_hints(hints)` — merge partial phone strings across checkers by digit position
- `VKUsernameForgotChecker.check(screen_names)` — VK account existence via recovery flow (returns existence only since Feb 2026 VK patch; no masked hints)

### `phase2/search4faces_service.py`
- `Search4FacesService.search_by_photo(photo_path, max_results)` — JSON-RPC face search (requires API key)
- `Search4FacesService.search_all_databases(photo_path, max_results_per_db)` — search vkok + vk01 databases
- `Search4FacesService.search_playwright_fallback(photo_path, max_results)` — free web scrape fallback

### `phase2/social_graph.py`
- `SocialGraphBuilder.build(vk_profiles, friends_data)` — build NetworkX graph + Louvain communities → vis.js format
- `SocialGraphBuilder.to_vis_dict()` — serialize graph to vis.js nodes/edges

### `phase2/vk_api_extractor.py`
- `VKApiExtractor.get_friends(vk_id)` — friends.get API call
- `VKApiExtractor.get_photos(vk_id)` — photos.getAll API call
- `VKApiExtractor.get_groups(vk_id)` — groups.get API call
- `VKApiExtractor.get_profile(vk_id)` — users.get with extended fields

### `phase2/vk_wall_extractor.py`
- `VKWallExtractor.get_posts(vk_id, count)` — wall.get API call; returns post list
- `VKWallExtractor.extract_text_data(posts)` — extract text content for NLP

### `phase2/telegram_crossref.py`
- `TelegramCrossRef.crossref(vk_screen_names)` — look up VK usernames on Telegram

### `phase2/username_intelligence.py`
- `UsernameIntelligence.search(username)` — run Snoop/Maigret/Sherlock for username

### `phase2/marketplace_scanner.py`
- `MarketplaceScanner.scan(name, phone, email)` — Avito/Wildberries/Ozon scan (removed from pipeline 2026-06-08 — never returned results)

### `phase2/ok_checker.py`
- `OKChecker.search(name, city)` — OK.ru (Одноклассники) profile search

### `phase2/profile_scraper.py`
- `ProfileScraper.scrape(url)` — generic social profile scraper

### `phase2/gravatar_lookup.py`
- `GravatarLookup.lookup(email)` — Gravatar profile by email hash

### `phase2/inn_breach_search.py`
- `search_inn_in_breaches(inn)` — search INN in breach databases; returns {found: bool, sources: [...]}

### `phase2/mailcat_discovery.py`
- `MailcatDiscovery.search(username)` — Mailcat email discovery by username

### `phase2/yaseeker_service.py`
- `YaSeekerService.search(email)` — Yandex-specific email intelligence

### `phase2/source_manager.py`
- `SourceManager.get_sources()` — return list of active breach sources
- `SourceManager.run_all(query)` — run all sources against query

### `phase2/sources/breach_api.py`
- `BreachAPISource.search(email)` — generic breach API source base class/implementation

---

## 12. Phase 3: Legal & Government (every function, what it does)

### `phase3/combined_search.py`
- `Phase3Search.run(check)` — orchestrate Phase 3 searches

### `phase3/court_search.py`
- `CourtRecordSearch.search_by_name(full_name, inn)` — search all court sources; sets `last_source_statuses`, `last_coparty_edges`
- `CourtRecordSearch.get_manual_search_urls(company_name, inn)` — returns dict of manual search URLs including kad.arbitr.ru
- `classify_court_role(text, name)` — 100-char proximity window, returns plaintiff/defendant
- `extract_criminal_articles(text)` — regex УК РФ article citations
- `extract_verdict(text)` — parse sentence/fine from full case text

### `phase3/fssp_search.py`
- `FSSPSearch.search(name, dob, region)` — official FSSP (dead/CAPTCHA); returns records + status
- `search_fssp_via_parser_api(name, dob)` — primary: parser-api.com proxied FSSP; returns (records, status)

### `phase3/kad_arbitr_service.py`
- `KadArbitrService.search(name, inn)` — kad.arbitr.ru via parser-api.com; geo-blocked from non-RU IPs for direct access

### `phase3/business_registry.py`
- `BusinessRegistrySearch.search_by_name(full_name, egrul_cache)` — EGRUL + Rusprofile by name
- `BusinessRegistrySearch.search_by_inn(inn, candidate_name)` — EGRUL by INN (primary)
- `BusinessRegistrySearch.search_by_inn_extended(inn)` — ИП status + FNS tax debt
- `filter_business_records_by_inn(records, candidate_inn)` — INN match → confidence filtering
- `extract_egrul_coparties(raw_egrul_json, company_name, company_inn, candidate_inn, candidate_name)` — Axis 2 co-director/co-founder edge extraction
- `extract_address_coparties(connections, address, candidate_inn)` — Axis 2 address co-registrant edges

### `phase3/checko_service.py`
- `CheckoService.search_enforcement(name)` — FSSP data via checko.ru `/search?query=name`; returns (records, status)
- `CheckoService.search_business(name)` — business data via checko.ru

### `phase3/address_intelligence.py`
- `search_by_address(address, candidate_inn)` — FNS address search; returns {found, connections, mass_registration, status}
- `extract_address_coparties(connections, address, candidate_inn)` — extract Axis 2 edges

### `phase3/geo_extractor.py`
- `GeoExtractor.extract_locations(posts)` — extract location mentions from VK posts
- `GeoExtractor.extract_from_profile(profile)` — extract city from VK profile

### `phase3/geo_intelligence.py`
- `collect_geo_intelligence(check, is_demo)` — aggregate geo data from all stages: VK geo_analysis + business addresses + FSSP addresses → {locations, summary, home_location}

### `phase3/passport_check.py`
- `check_passport_mvd(series, number)` — ГУВМ МВД passport validity check. Dead since July 2023; returns MVD_UNAVAILABLE_MSG directing to Gosuslugi.

### `phase3/pledge_registry.py`
- `PledgeRegistrySearch.search_by_name(name)` — залоговый реестр (reestr-zalogov.ru); reCAPTCHA-walled; returns (records, status)

### `phase3/reputation_su_service.py`
- `ReputationSuService.search(name)` — court aggregator reputation.su; SSR Nuxt 3 scraping

### `phase3/text_analyzer.py`
- `TextAnalyzer.analyze(posts)` — NLP on VK wall posts: sentiment, keywords (pymorphy2), topics, posting_times, word_count

---

## 13. AI Integration (model, prompts structure, 4 summary types)

**Model:** `claude-haiku-4-5-20251001`
**Max tokens:** 512 (default); 256 for risk narrative; 384 for behavioral + executive; 1024 for court batch
**Client:** `anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)` with optional `HTTPS_PROXY`
**Status:** LIVE — key set, `is_available()` gating replaced hardcoded `return None` (fixed 2026-05-22)
**Failure mode:** All functions return `None` on any failure; pipeline continues without AI; `source_statuses['ai_summary']` records honest 'ok'/'unavailable'/'error'

### Functions in `app/services/ai/claude_integration.py`:

- `_get_client()` — build Anthropic client; returns None if key missing or package not installed
- `is_available()` — lightweight check: key set + anthropic importable (no network)
- `_call_claude(system_prompt, user_content, max_tokens)` — single API call; returns text or None

**4 AI summary types:**

1. **`generate_risk_narrative(risk_level, risk_score, red_flags, full_name)`**
   - Called after Stage 7. 2-3 sentence risk summary in English. Uses "the subject".
   - Input: risk_level, score/100, top 15 flags with severity + text.
   - max_tokens: 256

2. **`generate_behavioral_summary(text_analysis, full_name)`**
   - Called after Stage 6. 3-5 sentences: personality, lifestyle, political views, red flags.
   - Input: sentiment score/label, top 15 keywords, top 10 topics, word_count.
   - Returns None if no text_analysis or empty keywords/topics.
   - max_tokens: 384

3. **`generate_executive_summary(check_data)`**
   - Called after Stage 8. 1 paragraph (4-6 sentences): identity, findings, risk, hiring recommendation. Uses "the candidate".
   - Input: full check summary — identity, risk, counts (biz/courts/fssp/bankruptcy/social/phones/emails), top 5 flags, sanctions matches.
   - max_tokens: 384

4. **`summarize_court_cases(court_records)`**
   - Called after Stage 1. Batch prompt for up to 20 cases. Returns JSON array of "English / Русское" summaries. Adds `ai_summary` key to each case dict.
   - max_tokens: 1024

---

## 14. External APIs — Active (name, what it does, env var, cost, limit, status)

| Name | What it does | Env Var | Cost | Limit | Status |
|---|---|---|---|---|---|
| VK API | People search, wall extraction, friends, groups, photos | `VK_SERVICE_TOKEN`, `VK_USER_TOKEN` | Free | VK rate limits | KEY SET |
| Telegram (Telethon) | Username lookup, phone→TG, session-based discovery | `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, `TELEGRAM_PHONE` | Free | Telegram limits | KEY SET — session may expire on prod |
| Anthropic Claude (Haiku 4.5) | 4 AI summaries per check | `ANTHROPIC_API_KEY` | $1/1M input, $5/1M output | API limits | KEY SET — LIVE |
| Resend | Transactional email (subscription confirmation) | `RESEND_API_KEY` | Free tier / paid | 100/day free | KEY SET |
| DaData | Russian address/company enrichment (financial_service.py) | `DADATA_API_KEY`, `DADATA_SECRET` | Free tier | 10k/day | KEY SET |
| parser-api.com | Proxied ФССП + kad.arbitr.ru (bypasses geo-block + CAPTCHA) | `PARSER_API_KEY` | Paid till 2026-07-10 | 200 req/mo each service | KEY SET — LIVE (verified 2026-06-12) |
| ЕГРЮЛ (nalog.ru) | Company/ИП registry lookup | None (web scrape) | Free | — | Works |
| судебныерешения.рф | Court records | None (web scrape) | Free | — | Works |
| reputation.su | Court aggregator | None (web scrape) | Free | — | Works |
| OpenSanctions | Sanctions database (local DB + free API) | None | Free | — | Works |
| ip-api.com | Geo-IP for language detection in auth | None | Free | 1000/hr | Works |

---

## 15. External APIs — Planned / NOT SET (same format)

| Name | What it does | Env Var | Est. cost | Notes |
|---|---|---|---|---|
| Search4Faces | Face search across 312M–1.1B VK/OK profiles | `SEARCH4FACES_API_KEY` | $40+/mo | Playwright fallback runs without key |
| LeakCheck | Email/phone breach lookup | `LEAKCHECK_API_KEY` | ~880 ₽/mo | Returns empty without key |
| Snusbase | Breach database | `SNUSBASE_API_KEY` | ~880 ₽/mo | Returns empty without key |
| DeHashed | Breach database | `DEHASHED_EMAIL`, `DEHASHED_API_KEY` | ~1 320 ₽/mo | Returns empty without key |
| HIBP (paid) | Have I Been Pwned | `HIBP_API_KEY` | ~1 900 ₽/mo | Returns empty without key |
| Hunter.io | Email discovery | `HUNTER_API_KEY` | ~4 310 ₽/mo Starter | Returns empty without key |
| EmailRep | Email reputation | `EMAILREP_API_KEY` | Unknown | Returns empty without key |
| Snov.io | Email discovery | `SNOV_CLIENT_ID`, `SNOV_CLIENT_SECRET` | Unknown | Returns empty without key |
| GetContact | Phone → caller ID (contacts database) | `GETCONTACT_API_KEY`, `GETCONTACT_TOKEN`, `GETCONTACT_AES_KEY`, `GETCONTACT_DEVICE_ID` | Unknown | AES-256-ECB + HMAC-SHA256 signing; requires pycryptodome; 403 = CAPTCHA |
| NumBuster | Phone intelligence | `NUMBUSTER_API_KEY` | Unknown | Returns empty without key |
| Himera | 9B+ record breach DB | `HIMERA_API_KEY` | Unknown | Stub marked implemented=False |
| YooKassa | Payment processing | — | — | Requires registered ИП/ООО; stub active |
| DataNewton | Russian legal: FSSP, courts, FNS, contracts (60+ endpoints) | — | Free 200 req/mo | Alternative FSSP source; not yet wired |
| FSSP API (official) | ФССП enforcement data | `FSSP_API_TOKEN` | — | DEAD — shut down Feb 2026; all endpoints 404 |
| kad.arbitr.ru (direct) | Arbitration courts | — | Free | GEO-BLOCKED (HTTP 451 non-RU IPs); use parser-api.com instead |
| checko.ru | Business data + FSSP aggregator | None (web scrape) | Free | 403 anti-bot possible; `/search?query=name` works |

---

## 16. Middleware & Security

### DoS Protection (`app/middleware/dos_protection.py`)
- `DosProtection` class — in-memory behavioral analysis
- `_get_client_ip()` — real IP extraction (ProxyFix + X-Forwarded-For + X-Real-IP fallback)
- `DosProtection._cleanup()` — remove expired bans + old request data
- `init_dos_protection(app)` — register middleware with Flask
- Tracks: request timestamps per IP (deque maxlen=1000), 404 counts (deque maxlen=100), ban expiry, suspicious scores
- Optional Redis backend for cross-worker shared state

### Application-level security (`app/__init__.py`):
- `ProxyFix(x_for=1)` — trust one nginx hop for real IP
- `_StripServerHeader` WSGI middleware — removes Server header (fingerprinting prevention)
- `check_auth()` before_request hook — validates session user_id + DB existence + is_active + inactivity timeout (default 1hr)
- `set_security_headers()` after_request hook — X-Content-Type-Options, X-Frame-Options, X-XSS-Protection, Referrer-Policy, HSTS, Permissions-Policy, full CSP
- Session: HTTPONLY, SameSite=Lax, Secure (prod), activity-based timeout
- Per-username login lockout: 5 failures in 5-min window → 15-min lockout (DB-backed, immune to IP rotation)
- Flask-Limiter: default 200/day, 50/hr; login/register POST: 5/min + 20/hr
- CSRF: Flask-WTF, `WTF_CSRF_SSL_STRICT=False` in prod (nginx SSL termination)
- Free tier atomic enforcement: `BEGIN IMMEDIATE` serializes read-then-write to prevent TOCTOU
- SQLite WAL mode + 30s busy_timeout (prevents pipeline write conflicts)
- Max 10 concurrent pipeline tasks
- IDOR guard: `can_access_check(user, check)` — admin or owner only
- PD consent required at check start (152-FZ)

### Permissions module (`app/permissions.py`):
- `is_admin(user)` — user is not None and role=='admin'
- `can_access_check(user, check)` — admin or check.user_id==user.id
- `enforce_free_tier_limit(user)` — BEGIN IMMEDIATE atomic quota check; returns (True, None) or (False, error_response)

### Audit module (`app/audit.py`):
- `log(action, *, outcome, user_id, target_type, target_id, ip_address, metadata)` — write AuditLog entry; never raises

---

## 17. Utils

### `app/utils/inn_validator.py`
- `validate_inn(inn)` — checksum validation for 10-digit (company) and 12-digit (individual) INN; returns (bool, error_str)

### `app/utils/logger.py`
- `setup_logging(log_level)` — configure structured JSON logging for production

### `app/utils/name_similarity.py`
- `calculate_name_similarity(name1, name2)` — normalized string similarity; used for EGRUL business record filtering (threshold 0.7 for ИП names, 0.85 for different INN, 0.75 for no INN)

### `app/utils/phone.py`
- `normalize_phone(phone)` — normalize Russian phone number to E.164 (+7XXXXXXXXXX); uses `phonenumbers` library

### `app/utils/startup_checks.py`
- `run_startup_checks(app)` — verify required env vars, API key presence, data file existence at startup

### `app/utils/vk_token_manager.py`
- `get_vk_token(purpose)` — return appropriate VK token for purpose ('search' → service token, 'wall' → user token)
- `get_oauth_url()` — generate VK OAuth URL for admin token refresh
- `save_token(token)` — persist new VK token; invalidates cache so freshly-saved token is verified immediately
- `get_token_status()` — return token validity status dict; **30-second in-process cache** (thread-safe, double-checked locking). Before cache: ~900ms/call. After: ~8ms P50. `save_token()` invalidates cache. Reduced P95 from 1100ms → 150ms at 200 concurrent users.
- `_sanitize_token(raw)` — strip whitespace and validate token format

### `app/market/russia.py`
- `CIS_COUNTRY_CODES` — set of CIS country ISO codes for geo-IP language detection

### `app/services/shared/court_utils.py`
- Shared utilities for court record processing (parsing, deduplication)

### `app/services/shared/money_utils.py`
- `parse_amount(text)` — extract monetary amount from text string

### `app/services/email_service.py`
- `send_subscription_confirmation(username, email, expires_at, auto_renew)` — send Resend transactional email

### `app/services/maigret_search.py`
- `MaigretSearch.search(username)` — username search via Maigret (if installed via pip or OSINT_TOOLS_DIR)

### `app/services/sherlock_search.py`
- `SherlockSearch.search(username)` — username search via Sherlock

### `app/services/snoop_search.py`
- `SnoopSearch.search(username)` — Russian-focused username search via Snoop

### `app/services/telegram/session_manager.py`
- `TelegramSessionManager.get_client()` — return authenticated Telethon client
- `TelegramSessionManager.is_session_valid()` — check if session file exists and is not expired

### `app/services/telegram/config.py`
- Telegram API configuration constants (API ID, hash, phone, session path)

### `app/services/candidate/adverse_media_service.py`
- `is_available()` — check if Yandex search key configured
- `search_adverse_media(name, context)` — Yandex XML API search for negative news; disambiguation engine tags hits as confirmed/possible; context: {inns, companies, birth_year, city}

### `app/services/candidate/bankruptcy_service.py`
- `BankruptcyService.search(name, inn, dob)` — bankrot.fedresurs.ru ЕФРСБ search

### `app/services/candidate/opensanctions_service.py`
- `OpenSanctionsService.search(name, inn)` — local DB + free API sanctions check
- `OpenSanctionsService.is_reachable(timeout)` — connectivity check (used by /health)

### `app/services/candidate/sanctions_check.py`
- `SanctionsService.check_all(name, inn)` — run all sanctions sources: Росфинмониторинг, МВД розыск, Interpol, экстремисты list, OpenSanctions

### `app/services/candidate/connection_graph.py`
- `build_from_check(check, extra_edges)` — build Axis 2 connection graph from all edges accumulated during pipeline; entity-resolved by INN/name; returns list of Connection objects
- `Connection.to_dict()` — serialize edge to dict

### `app/services/candidate/local_security_db.py`
- `LocalSecurityDB.check_wanted(name, dob)` — check local mvd_wanted.json
- `LocalSecurityDB.check_extremist(name)` — check local extremist_list.json

### `app/services/candidate/report_builder.py`
- `build_report(check)` — assemble final structured dossier; sets report_generated=True

### `app/services/candidate/social_analysis.py`
- `run_social_analysis(check)` — orchestrate Stage 5: Search4Faces face search + username search (Snoop/Maigret/Sherlock) + social graph build
- Returns: {social_graph, face_matches, username_accounts, face_search_status, username_search_status, new_accounts_for_enrichment}

### `app/services/candidate/contact_discovery.py`
- `ContactDiscoveryService.discover(check)` — Stage 4: extract phones/emails from confirmed social profiles + breach APIs + forgot-password oracle
- `ContactDiscoveryService.discover_supplementary(new_accounts, existing_contacts)` — Stage 5e: enrich newly discovered accounts

### `app/services/candidate/behavioral_analysis.py`
- `run_behavioral_analysis(check, callback)` — Stage 6: VK wall text analysis + geo analysis + group analysis + activity patterns
- `find_connected_checks(check)` — find other CandidateChecks that share phone/email with this candidate

### `app/services/candidate/fssp_service.py`
- `FSSPService.search_with_status(name, dob, region)` — direct official FSSP (CAPTCHA/dead; last resort)
- `search_fssp_via_parser_api(name, dob)` — primary FSSP path via parser-api.com

### Risk scoring weights (all 77 codes in `risk_scorer.py`):
Facts (verified): court_criminal(25), fraud_case(20), active_debts(10), multiple_active(15), fssp_debt(15), critical_debt(20), large_debt(15), medium_debt(8), alimony_debt(10), tax_debt(15), active_bankruptcy(20), recent_bankruptcy(10), many_pledges(8), pledge_found(3), sanctions_match(30), passport_invalid(20), interpol_found(35), adverse_media_criminal(22), adverse_media_reputational(8), name_discrepancy(8), court_admin(10)

Suspicions (indirect): serial_entrepreneur(5), mass_director(8), liquidated_companies(8), recent_liquidation(6), liquidated_with_debt(10), mass_registration_address(6), address_match(5), geo_discrepancy(5), high_night_activity(5), unusual_timezone(3), political_groups(8), criminal_groups(15), gambling_groups(8), drug_groups(20), security_groups(5), name_mismatch(8), new_account(3), private_profile(2), no_photo(2), connected_high_risk(10), no_social_presence(5), no_friends(3), isolated_graph(5), fake_profile_indicators(8), negative_sentiment(3), risk_keywords(5), night_activity(5), inactive_profile(3), identity_not_confirmed(3), sanctions_unchecked(5), adverse_media_possible(2), many_cases(8), defendant_cases(10)

Score thresholds: <30=low, 30–59=medium, 60–79=high, ≥80=critical

---

## 18. Cost Model (from financial session — exact numbers)

**Per-check cost (Claude Haiku 4.5):** 1,60 руб. (4 calls × 2 000 input + 512 output tokens, $1/1M input, $5/1M output)
**Assumption:** 5 checks/day per user = 150 checks/user/month

| Users | Checks/mo | Claude | Search4Faces | Server | Fixed API stack | Total |
|---|---|---|---|---|---|---|
| 100 | 15 000 | 24 000 ₽ | 7 040 ₽ | 880 ₽ | 9 290 ₽ | 41 210 ₽ |
| 1 000 | 150 000 | 240 800 ₽ | 28 160 ₽ | 5 280 ₽ | 9 290 ₽ | 283 530 ₽ |
| 2 000 | 300 000 | 481 500 ₽ | 42 240 ₽ | 10 560 ₽ | 9 290 ₽ | 543 590 ₽ |
| 5 000 | 750 000 | 1 203 800 ₽ | 88 000 ₽ | 26 400 ₽ | 9 290 ₽ | 1 327 490 ₽ |
| 10 000 | 1 500 000 | 2 407 700 ₽ | 176 000 ₽ | 52 800 ₽ | 9 290 ₽ | 2 645 790 ₽ |

**Fixed API stack (9 290 ₽/мес):** HIBP Core 2 (1 900 ₽) + LeakCheck Monthly (880 ₽) + Snusbase (~880 ₽) + DeHashed (~1 320 ₽) + Hunter.io Starter (4 310 ₽)

**Revenue model:** ~10 000 ₽/user/month → gross margin 97.4% at scale

---

## 19. Business Context

- **Platform name:** Штирлиц (Stirlitz)
- **Domain:** shtirletzsled.ru
- **Server:** reg.ru VPS, IP 194.67.99.107
- **Production SSH:** `ssh fedor@194.67.99.107` (root disabled)
- **App path on server:** `/opt/ibp/`
- **Process manager:** Gunicorn via systemd (`ibp.service`)
- **Legal entity:** ИП (мать Федора) — Stirlitz runs under this ИП
- **152-ФЗ:** in progress (PD consent + privacy policy implemented; Roskomnadzor registration status: UNKNOWN)
- **Payment:** YooKassa stub (not live — requires ИП activation)
- **Git:** github.com/FedorPortnoi/ibp
- **Backend deploy:** git pull → pip install → alembic upgrade → restart gunicorn
- **B2B target:** HR departments, corporate security, recruitment agencies
- **Subscription:** Free tier 2 checks/week; paid 1 500 ₽/month (30 days, unlimited)
- **Admin user:** Fedor (role='admin') — can access all users' checks
- **Regular users:** self-register at /register; own checks only; free-tier gated
- **Check modes:** Quick (fully automatic) and Precise (pause after Stage 3 for manual VK profile confirmation)
- **Repo:** private on GitHub; landing page at github.com/FedorPortnoi/shtirlitz-landing
- **Last deployed:** 2026-06-19 (server live, ibp.service active); 2026-06-22+23 fixes not yet pushed
- **Startup recovery:** `_recover_orphaned_tasks()` in `app/__init__.py` — on server start, resets any `running`/`pending` CandidateCheck and CompanyCheck to `error` (catches tasks killed mid-pipeline by server restart)

---

## 20. Known Issues & Blockers

### Load Test Results (2026-06-23 — Werkzeug dev server, SQLite WAL, single-process)

| Users | Requests | Fail% | P50 | P95 | P99 | Throughput |
|---|---|---|---|---|---|---|
| 10 | 259 | 0% | 12ms | 270ms | 790ms | 4.4 req/s |
| 25 | 876 | 0% | 12ms | 770ms | 880ms | 9.8 req/s |
| 50 | 2391 | 0% | 12ms | 760ms | 970ms | 20.0 req/s |
| 100 | 4583 | 0% | 13ms | 420ms | 1000ms | 38.3 req/s |
| 200 | 8674 | 0% | 35ms | 150ms* | 520ms* | 72.4 req/s |
| 400 | 8363 | 1.72% | 2700ms | 5600ms | 8000ms | 69.7 req/s |

*After VK token cache fix. Pre-cache P95=1100ms, P99=1700ms at 200 users.
**Ceiling: ~200 concurrent users (0 failures).** At 400 users TCP accept backlog fills → `ConnectionRefused`. Bottleneck was `/api/vk/token-status` making a live VK API call (~900ms) per request — fixed with 30s cache.

### Infrastructure
- **Telethon session on prod may be expired** — `/opt/ibp/tg_session/ibp_session.session`; if Stage 3 TG returns nothing, re-auth: `python scripts/auth_telegram.py`, then `scp` session file to prod + restart. Note: Telegram intentionally removed from current pipeline (2026-06-19 rework).
- **reg.ru balance** — server balance reached 0.00 ₽ on 2026-04-16; resolved 2026-06-08; monitor at `cloud.reg.ru`.
- **parser-api.com quota** — 200 req/mo FSSP + 200 req/mo arbitr; paid till 2026-07-10. Check: `https://parser-api.com/stat/?key=`.

### Dead Integrations
- **FSSP api-ip.fssp.gov.ru** — permanently shut down Feb 2026, all endpoints 404. `FSSP_API_TOKEN` is irrelevant. Current path: parser-api.com → checko.ru → empty fallback.
- **ГУВМ МВД passport validity** — registry stopped updating 2023-06-21; code returns `MVD_UNAVAILABLE_MSG` directing to Gosuslugi manual check.
- **kad.arbitr.ru direct** — HTTP 451 from non-Russian IPs (DDoS Guard geo-block). Use parser-api.com proxy. Manual search URL provided in dossier.
- **VK forgot-password oracle** — VK patched Feb 2026; now returns only account existence, no masked phone/email hints. Class exists but `check_vk_usernames()` removed from pipeline.

### Missing API Keys (empty results)
- Search4Faces, LeakCheck, Snusbase, DeHashed, HIBP, Hunter.io, EmailRep, Snov.io, GetContact, NumBuster, Himera, InformTrackPeople

### Code / Architecture
- **pymorphy2** — needs `inspect.getfullargspec` shim on Python 3.12+; shim already in codebase.
- **pytest on Windows** — needs `-p no:faulthandler` to avoid Playwright/ctypes crash.
- **E2E baseline stale** — last run 2026-04-02; pipeline changed significantly (Playwright removed from 5 services 2026-06-08); re-run needed.
- **Legacy phase routes** — phase1–4 blueprints only registered with `ENABLE_PEOPLE_SEARCH=true`; default off in production.
- **casebook.ru dropped 2026-06-11** — `/search` 404s, API returns 401 (login wall). Removed from court_search. Coverage unchanged (kad covers arbitration).
- **Geo/behavioral fields** — Telethon asyncio hang fixed 2026-04-04 (`asyncio.wait_for` + 45s cap); behavioral fields should now populate. Verification pending.

### Legal / Compliance
- **152-FZ Roskomnadzor registration** — status UNKNOWN; must be filed before processing real personal data in production.
- **YooKassa** — stub only; requires registered ИП/ООО before activation. ИП registration in progress (2026-06-22).

### Planned / Future
- Telethon / social media stages intentionally removed from current pipeline (2026-06-19); separate rework in progress.
- Yandex People Search — CAPTCHA-prone, unreliable in production.
- Holehe — slow (~25s/email); Stage 4 timeout set to 120s to compensate.

---

## 21. Open Decisions

| Decision | Status | Blocking |
|---|---|---|
| Final pricing model (per-check vs flat monthly vs tiered) | OPEN | YooKassa integration, pricing page |
| MVP scope for first paying customer | OPEN | Sales timing; min viable: Stage 0+1+2+3+7 work |
| YooKassa activation | OPEN — needs ИП registration | Real payment processing |
| Roskomnadzor 152-FZ operator registration | UNKNOWN | Legal compliance for real user data |
| Which paid breach APIs to add first | OPEN | Stage 4 contact discovery quality |
| DataNewton as FSSP fallback | OPEN | FSSP data quality; 200 req/mo free |
| OSINT tools bundling (Snoop/Maigret/Sherlock) | OPEN | Stage 5 username search coverage |
| Social media rework (Telethon stages) | IN PROGRESS (separate branch) | Stage 3 Telegram quality |
| Telethon session on prod validity | NOT RELEVANT until social rework ships | Stage 3 |
| Redis deployment for cross-worker rate limiting | OPEN | Multi-worker rate-limit accuracy |
| kad.arbitr.ru from Russian VPS | OPEN | Arbitration court coverage (HTTP 451 on current VPS) |
| B2C pricing/onboarding (future) | DEFERRED | Not launch target |
| Role-based access within org (teams) | NOT BUILT | B2B enterprise tier |
