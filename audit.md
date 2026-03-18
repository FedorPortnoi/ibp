# IBP Full Codebase Audit Report

**Date**: 2026-03-18
**Commits**: `04e26c2`, `44850a3`
**Scope**: 44 files changed, +1143 / -592 lines

---

## P0 Bug Fixes

### Bug 1: "Задача не найдена" — Multi-Worker Task Storage (CRITICAL)

**Problem**: Task progress stored in-memory (`candidate_tasks = {}` dict). Gunicorn with 2+ workers means task created in worker A is invisible to worker B. Frontend polls hit the wrong worker → 404 "Задача не найдена".

**Root cause**: `CandidateTaskStatus` objects lived only in process memory. No shared state between workers.

**Fix**:
- Added 7 task tracking columns to `CandidateCheck` model: `task_id`, `task_progress`, `task_stage`, `task_message`, `task_log` (JSON), `task_error`, `task_started_at`
- `CandidateTaskStatus._sync_to_db()` persists progress to DB on every `task.update()` call
- Progress endpoint reads from DB when in-memory task not found (cross-worker fallback)
- `task_id` stored on `CandidateCheck` at creation time with indexed column
- Auto-migration adds columns to existing SQLite databases on startup

**Files changed**:
- `app/models/candidate_check.py` — 7 new columns + `task_log` JSON property + `task_status_dict()` method
- `app/services/candidate/pipeline.py` — `bind_check()`, `_sync_to_db()` on CandidateTaskStatus
- `app/routes/candidate_check.py` — DB fallback in `progress_page`, `progress_status`, `dossier_page`, `confirm_profiles`
- `app/__init__.py` — `_migrate_task_columns()` startup migration + index creation

**Verification**: Integration test confirms cross-worker DB reads return correct progress, stage, messages. Progress page returns 200 (not 404) when in-memory task missing.

---

### Bug 2: Stage 3 — VK Returns 0 Profiles

**Problem**: VK search returned 0 profiles for valid names.

**Root cause**: Fixed in prior commits (`78a4eae`, `8d5f86d`) — patronymic in query caused VK API to return 0, and DOB filtering was too aggressive.

**Status**: Verified. Call chain `pipeline.py → buratino_vk_search.search()` correctly strips patronymic and uses `VK_USER_TOKEN` fallback. No further changes needed.

---

### Bug 3: JSON Export 502 Bad Gateway

**Problem**: `POST /report/download/json` returned 502. Legacy `identity_card.html` template calls this endpoint via `fetch()` without CSRF token.

**Root cause**: Flask-WTF CSRF protection rejects the POST. The error propagated as a server error.

**Fix**:
- Added `@csrf.exempt` to `/report/download/{json,pdf,html}` and `/report/generate` POST endpoints (they receive JSON and return downloads — no state mutation)
- Changed `request.get_json()` → `request.get_json(silent=True)` to return 400 instead of 500 on malformed input

**Files changed**: `app/routes/report.py`

**Verification**: POST /report/download/json now returns 200 with valid JSON body. Returns 400 (not 500) without body.

---

### Bug 4: sudact.ru Court Scraper Returns 0

**Problem**: Playwright scraper for sudact.ru found no results.

**Fix**:
- Fixed search URL to include all required parameters (`regular-txt`, `regular-case_doc`, `regular-lawchunkinfo`, `regular-date_from`, etc.)
- Added retry logic (up to 2 attempts with 3-second delay)
- Added 6 alternative CSS selectors for result parsing (`ul.results > li`, `.bsr-item`, `#resultTable tr`, `.result-item`, `a[href*="/doc/"]`, `.search-results`)
- Wrapped browser in `try/finally` for guaranteed cleanup
- Basic requests fallback now uses same correct parameters
- Comprehensive logging at every step

**Files changed**: `app/services/phase3/court_search.py`

---

### Bug 5: ФССП Scraper Returns 0

**Problem**: FSSP enforcement search returned empty results.

**Fix**:
- Added strategy-level logging (Strategy 1/4: API, 2/4: AJAX, 3/4: Playwright, 4/4: Manual)
- Logged all search parameters, strategy outcomes, and result counts
- Wrapped Playwright browser in `try/finally` for guaranteed `browser.close()`
- Improved CAPTCHA detection (additional markers: `captchaVisualImage`, text-based)
- Manual fallback correctly returns `source='manual'`

**Files changed**: `app/services/candidate/fssp_service.py`

---

### Bug 6: Interpol Check — 502 Error

**Problem**: Interpol API sometimes returns HTTP 502/503/504. Previously fell through to generic exception handler showing raw error text.

**Fix**: Added explicit handling for HTTP 502/503/504 with user-friendly "Сервис временно недоступен" message.

**Files changed**: `app/services/candidate/sanctions_check.py`

---

## Audit Results

### Audit 1: Silent Exception Handlers

**Scope**: All `except:` and `except Exception:` blocks across 28+ files.

**Finding**: 60+ bare except blocks were silently swallowing errors with no logging.

**Fix**: Added `logger.error/warning/debug(f"[ServiceName] ...: {e}")` to every silent handler. No `except` blocks were removed — only logging added.

**Files fixed** (20 files in second commit):
- `candidate/`: bankruptcy_service, fssp_service
- `phase1/`: vk_web_search (18 handlers), buratino_vk_search, yandex_search
- `phase2/`: email_discovery, email_sources, face_search_api, forgot_password_oracle, gravatar_lookup, mailcat_discovery, marketplace_scanner, ok_checker, phone_sources (7 bare `except:`), search4faces_service, telegram_crossref, url_validator
- `phase2/sources/`: email_pattern, holehe_check, leak_sources (5 handlers)
- `phase3/`: court_search, fssp_search, text_analyzer, video_analyzer
- `telegram/`: session_manager
- Top-level: dossier_generator, maigret_search, report_generator (9 handlers), sherlock_search

### Audit 2: Playwright Cleanup

**Finding**: Several `browser.launch()` calls lacked `try/finally` for `browser.close()`.

**Fix**:
- `bankruptcy_service.py` — Wrapped in try/finally
- `vk_web_search.py` — Wrapped web token extraction + manual login in try/finally
- `search4faces_service.py` — Wrapped Playwright session in try/finally
- `court_search.py` — Wrapped in try/finally with retry

**Missing `page.goto()` timeouts fixed**:
- `vk_web_search.py:1090` — Added `timeout=30000`
- `forgot_password_oracle.py:740` — Added `timeout=30000`
- `marketplace_scanner.py:297,340` — Added `timeout=30000`

### Audit 3: Background Thread App Context

**Finding**: No issues. `db.session` is only used in `pipeline.py`, always inside `with app.app_context():`. All other services receive data via the `check` object and return plain dicts/lists.

### Audit 4: API Calls Without Timeout

**Finding**: All `requests.get()` and `requests.post()` calls already had `timeout=` parameters. No changes needed.

### Audit 5: VK Token Usage

**Finding**: Correct. Pipeline logs which token type is being used. `buratino_vk_search` uses web token → VK_USER_TOKEN fallback → demo mode. Service token is not used for `users.search` (would fail with Error 28).

### Audit 6: Demo Mode Leaking

**Finding**: No leakage. `_is_demo_mode()` returns `not os.environ.get('VK_SERVICE_TOKEN')` — False when token is set. All 3 demo fallback points (Stages 1, 2, 4) require BOTH `_is_demo_mode() == True` AND absence of real data.

### Audit 7: Missing Null Checks

**Finding**: No issues. All services use proper guards:
- `risk_scorer.py` — `getattr(check, ..., None) or {}` pattern
- `report_builder.py` — `_safe_json()` helper for all JSON fields
- `contact_discovery.py` — Ternary guards for `check.date_of_birth`, `check.email`, `check.phone`
- `behavioral_analysis.py` — `or []` fallback pattern

### Audit 8: DB Session Across Threads

**Finding**: No issues. `db.session` only used in `pipeline.py` within `with app.app_context():`. ThreadPoolExecutor child threads call external APIs, not the DB.

---

## Architecture Change: Task Storage

### Before (in-memory only)
```
Worker A: candidate_tasks[task_id] = CandidateTaskStatus(...)
Worker B: candidate_tasks.get(task_id) → None → 404
```

### After (DB-backed with in-memory fast path)
```
Worker A: check.task_id = task_id (DB) + candidate_tasks[task_id] (memory)
Pipeline: task.update() → sets check.task_* fields → db.session.commit()
Worker A poll: reads from candidate_tasks (fast, up-to-date)
Worker B poll: reads from CandidateCheck.query.filter_by(task_id=...) (DB fallback)
```

### New CandidateCheck columns
| Column | Type | Purpose |
|--------|------|---------|
| `task_id` | VARCHAR(36), indexed | Maps task to check for cross-worker lookup |
| `task_progress` | INTEGER | 0-100 percent complete |
| `task_stage` | VARCHAR(50) | Current pipeline stage name |
| `task_message` | VARCHAR(500) | Current step description |
| `task_log` | TEXT (JSON) | Last 40 progress messages |
| `task_error` | TEXT | Error message if pipeline failed |
| `task_started_at` | DATETIME | When the task was created |

---

## Files Changed Summary

| Category | Files | Lines Changed |
|----------|-------|---------------|
| Core bug fixes (Bug 1-3, 6) | 6 | +308 / -118 |
| Scraper fixes (Bug 4-5) | 2 | +474 / -253 |
| Silent exception audit | 20 | +247 / -221 |
| Business registry logging | 1 | +120 / -8 |
| Other service logging | 15 | +100 / -50 |
| **Total** | **44** | **+1143 / -592** |
