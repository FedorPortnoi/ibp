# IBP AUDIT REPORT — LIVE vs DEAD CODE

**Generated:** 2026-02-05
**Auditor:** Claude Opus 4.5
**Status:** AUDIT COMPLETE - CODE IS PROPERLY WIRED

---

## EXECUTIVE SUMMARY

**THE CODEBASE IS WELL-WIRED.** All routes correctly call the new Буратино-style services. The architecture is sound.

**What's working:**
- Phase 1 → `CombinedSearchService` → Real VK/OK/Telegram people search (not just username guessing)
- Phase 2 → `Phase2CombinedSearch` → Email/phone discovery with validation, face search, breach checking
- Phase 3 → `Phase3CombinedSearch` → Business registry, court records, social graph
- Phase 4 → `ResearchOrchestrator` → Cross-platform people search, connection analysis
- Report → `report_generator` → Identity card generation

**Issues Found (Navigation only, not wiring):**
1. Phase 4 `/search/people` is NOT linked in main navigation
2. Phase 2 has no "Continue to Phase 3" button
3. Phase 3 has no "Generate Identity Card" button
4. No unified dashboard showing all investigations

**Dead/Deprecated code that can be removed:**
- `app/services/maigret_search.py` - Never imported (replaced by direct platform APIs)
- `app/services/sherlock_search.py` - Never imported (replaced by direct platform APIs)
- `app/services/phase1_service.py` - Never imported (replaced by combined_search.py)

---

## ROUTE FILES (what the browser actually hits)

### File: `app/routes/phase1.py`

| Route | Method | Function |
|-------|--------|----------|
| `/phase1/` | GET | `index()` → renders `phase1_start.html` |
| `/phase1/start` | POST | `start_search()` → creates task, starts background thread |
| `/phase1/loading/<task_id>` | GET | `loading()` → renders `phase1_loading.html` |
| `/phase1/progress/<task_id>` | GET | `get_progress()` → returns task status JSON |
| `/phase1/results/<task_id>` | GET | `results()` → renders `phase1_results.html` |
| `/phase1/uploads/<filename>` | GET | `get_upload()` → serves uploaded photos |
| `/phase1/api/task/<task_id>` | GET | `api_task_status()` → full task status |
| `/phase1/api/task/<task_id>/accounts` | GET | `api_task_accounts()` → all accounts |

**Imports:**
```python
from app.services.combined_search import CombinedSearchService
```

**Service Calls:**
- Line 174: `CombinedSearchService(max_usernames=100, ...)`
- Line 185: `service.search(target_name, target_photo_path, progress_callback)`

**What CombinedSearchService actually does (verified by reading source):**
1. Generates usernames with `SmartUsernameGenerator`
2. Calls `vk_people_search.search_people()` - REAL VK name search
3. Calls `ok_people_search.search_people()` - REAL OK name search
4. Calls `telegram_people_search.search_people()` - REAL Telegram search
5. Calls `face_search_service.search_by_photo()` - Search4faces API
6. Runs face matching with `UltimateFaceMatcher`
7. Calculates confidence scores

**STATUS: ✅ LIVE - Properly wired to Буратино-style services**

---

### File: `app/routes/phase2.py`

| Route | Method | Function |
|-------|--------|----------|
| `/phase2/` | GET | `phase2_page()` → renders `phase2.html` |
| `/phase2/start` | POST | `start_investigation()` → async task |
| `/phase2/progress/<task_id>` | GET | `get_progress()` → task status JSON |
| `/phase2/results/<task_id>` | GET | `get_results()` → full results JSON |
| `/phase2/api/investigate` | POST | `investigate_sync()` → synchronous API |
| `/phase2/status` | GET | `get_status()` → system status |

**Imports:**
```python
from app.services.phase2.combined_search import Phase2CombinedSearch, Phase2Results
```

**Service Calls:**
- Line 84: `Phase2CombinedSearch()`
- Line 89: `searcher.investigate_fast(selected_profiles, target_name, target_photo_path)`
- Line 95: `searcher.investigate(...)` (full mode)

**What Phase2CombinedSearch actually does (verified by reading source):**
1. Scrapes selected VK profiles via `VKAPIExtractor`
2. Runs face search via `search_all_databases()` and `ApiFaceSearchService`
3. Generates email candidates and verifies with Holehe
4. Validates phones with `RussianPhoneValidator`
5. Checks Mailcat for verified emails
6. Runs username intelligence analysis
7. Checks OK.ru accounts
8. Extracts contacts from VK wall posts
9. Runs YaSeeker for Yandex services
10. Checks emails for breaches via `BreachChecker`
11. Checks Gravatar profiles

**STATUS: ✅ LIVE - Properly wired to all Phase 2 services**

---

### File: `app/routes/phase3.py`

| Route | Method | Function |
|-------|--------|----------|
| `/phase3/<investigation_id>` | GET | `index()` → renders `phase3.html` |
| `/phase3/start` | POST | `start_investigation()` → async task |
| `/phase3/progress/<task_id>` | GET | `get_progress()` → task status |
| `/phase3/results/<task_id>` | GET | `get_results()` → full results JSON |
| `/phase3/results/<investigation_id>` | GET | `results_page()` → renders `phase3_results.html` |
| `/phase3/api/business-search` | POST | `api_business_search()` → direct API |
| `/phase3/api/court-search` | POST | `api_court_search()` → direct API |
| `/phase3/api/geo-extract` | POST | `api_geo_extract()` → direct API |
| `/phase3/api/text-analyze` | POST | `api_text_analyze()` → direct API |

**Imports (lazy loaded inside functions):**
```python
from app.services.phase3.combined_search import Phase3CombinedSearch
from app.services.phase3.business_registry import business_registry_search
from app.services.phase3.court_search import court_search
from app.services.phase3.geo_extractor import geo_extractor
from app.services.phase3.text_analyzer import text_analyzer
```

**What Phase3CombinedSearch actually does:**
1. Searches business registries (ЕГРЮЛ/ЕГРИП) via `BusinessRegistrySearch`
2. Searches court records via `CourtRecordSearch`
3. Builds social graph from confirmed profiles
4. Extracts locations via `GeoExtractor`
5. Analyzes text from profile bios via `TextAnalyzer`
6. Calculates risk indicators

**STATUS: ✅ LIVE - Properly wired to all Phase 3 services**

---

### File: `app/routes/phase4.py`

| Route | Method | Function |
|-------|--------|----------|
| `/search/people` | GET | `people_search()` → renders `people_search.html` |
| `/api/search/people` | POST | `api_people_search()` → orchestrated search |
| `/investigation/<id>/graph` | GET | `show_graph()` → renders `graph.html` |
| `/api/investigation/<id>/graph-data` | GET | `get_graph_data()` → vis.js format |
| `/api/investigation/<id>/connections` | GET | `get_connections()` → all connections |
| `/api/investigation/<id>/connections` | POST | `add_connection()` → add new connection |
| `/api/connections/<id>` | DELETE | `delete_connection()` → remove connection |

**Imports (lazy loaded):**
```python
from app.services.phase4.research_orchestrator import research_orchestrator
```

**Service Calls:**
- Line 41: `research_orchestrator.search_person(name, city, age_from, age_to, platforms, ...)`

**STATUS: ✅ LIVE - Properly wired to orchestrator**

---

### File: `app/routes/report.py`

| Route | Method | Function |
|-------|--------|----------|
| `/report/<investigation_id>` | GET | `view()` → renders `identity_card.html` |
| `/report/generate` | POST | `generate()` → generates from JSON data |
| `/report/generate/<investigation_id>` | POST | `generate_from_investigation()` → from DB |
| `/report/download/html` | POST | `download_html()` → HTML file |
| `/report/download/pdf` | POST | `download_pdf()` → PDF file |
| `/report/download/json` | POST | `download_json()` → JSON file |
| `/report/download/<id>/<format>` | GET | `download()` → download by ID |
| `/report/preview` | POST | `preview()` → HTML preview |

**Imports (lazy loaded):**
```python
from app.services.report_generator import report_generator, IdentityCardData
```

**STATUS: ✅ LIVE - Properly wired**

---

### File: `app/routes/main.py`

| Route | Method | Function |
|-------|--------|----------|
| `/` | GET | `index()` → redirects to `/phase1/` |
| `/dashboard` | GET | `dashboard()` → redirects to `/phase1/` |
| `/diagnostic` | GET | `diagnostic()` → system diagnostic JSON |
| `/diagnostic/search/<name>` | GET | `diagnostic_search()` → test search |

**STATUS: ✅ LIVE - Working**

---

## LIVE SERVICE FILES (actually called by routes)

### Phase 1 Services (all LIVE)

| File | Called By | Status |
|------|-----------|--------|
| `app/services/combined_search.py` | phase1.py:15 | ✅ LIVE - Main orchestrator |
| `app/services/username_generator.py` | combined_search.py:27 | ✅ LIVE |
| `app/services/telegram_search.py` | combined_search.py:28 | ✅ LIVE |
| `app/services/vk_search.py` | combined_search.py:29 | ✅ LIVE |
| `app/services/ok_search.py` | combined_search.py:30 | ✅ LIVE |
| `app/services/yandex_image_search.py` | combined_search.py:31 | ✅ LIVE |
| `app/services/phase1/vk_people_search.py` | combined_search.py:33 | ✅ LIVE |
| `app/services/phase1/ok_people_search.py` | combined_search.py:34 | ✅ LIVE |
| `app/services/phase1/telegram_people_search.py` | combined_search.py:35 | ✅ LIVE |
| `app/services/phase1/face_search.py` | combined_search.py:36 | ✅ LIVE |
| `app/services/ultimate_face_matcher.py` | combined_search.py:215 | ✅ LIVE |

### Phase 2 Services (all LIVE)

| File | Status |
|------|--------|
| `app/services/phase2/combined_search.py` | ✅ LIVE - Main orchestrator |
| `app/services/phase2/email_generator.py` | ✅ LIVE |
| `app/services/phase2/profile_scraper.py` | ✅ LIVE |
| `app/services/phase2/gravatar_lookup.py` | ✅ LIVE |
| `app/services/phase2/holehe_service.py` | ✅ LIVE |
| `app/services/phase2/search4faces_service.py` | ✅ LIVE |
| `app/services/phase2/yaseeker_service.py` | ✅ LIVE |
| `app/services/phase2/url_validator.py` | ✅ LIVE |
| `app/services/phase2/russian_phone_validator.py` | ✅ LIVE |
| `app/services/phase2/mailcat_discovery.py` | ✅ LIVE |
| `app/services/phase2/vk_api_extractor.py` | ✅ LIVE |
| `app/services/phase2/ok_checker.py` | ✅ LIVE |
| `app/services/phase2/username_intelligence.py` | ✅ LIVE |
| `app/services/phase2/breach_checker.py` | ✅ LIVE |
| `app/services/phase2/vk_wall_extractor.py` | ✅ LIVE |
| `app/services/phase2/email_discovery.py` | ✅ LIVE |
| `app/services/phase2/face_search_api.py` | ✅ LIVE |
| `app/services/phase2/phone_discovery.py` | ✅ LIVE |
| `app/services/phase2/cross_validation.py` | ✅ LIVE |
| `app/services/phase2/email_sources.py` | ✅ LIVE |
| `app/services/phase2/phone_sources.py` | ✅ LIVE |
| `app/services/phase2/per_profile_search.py` | ✅ LIVE |

### Phase 3 Services (all LIVE)

| File | Status |
|------|--------|
| `app/services/phase3/combined_search.py` | ✅ LIVE - Main orchestrator |
| `app/services/phase3/business_registry.py` | ✅ LIVE |
| `app/services/phase3/court_search.py` | ✅ LIVE |
| `app/services/phase3/geo_extractor.py` | ✅ LIVE |
| `app/services/phase3/text_analyzer.py` | ✅ LIVE |
| `app/services/phase3/video_analyzer.py` | ⚠️ EXISTS but not called (reserved for future use) |

### Phase 4 Services (all LIVE)

| File | Status |
|------|--------|
| `app/services/phase4/research_orchestrator.py` | ✅ LIVE - Main orchestrator |
| `app/services/phase4/entity_resolver.py` | ✅ LIVE |
| `app/services/phase4/connection_analyzer.py` | ✅ LIVE |
| `app/services/phase4/ok_people_search.py` | ✅ LIVE |
| `app/services/phase4/telegram_search.py` | ✅ LIVE |

### Report Services (LIVE)

| File | Status |
|------|--------|
| `app/services/report_generator.py` | ✅ LIVE |

---

## DEAD SERVICE FILES (can be removed)

These files exist but are NEVER imported anywhere:

| File | Notes |
|------|-------|
| `app/services/maigret_search.py` | ☠️ REPLACED - Direct platform APIs are used instead |
| `app/services/sherlock_search.py` | ☠️ REPLACED - Direct platform APIs are used instead |
| `app/services/phase1_service.py` | ☠️ REPLACED - combined_search.py is the new orchestrator |

These files are imported by other services but not directly by routes:
| File | Notes |
|------|-------|
| `app/services/deduplication.py` | Used internally |
| `app/services/face_comparator.py` | Used by face matching |
| `app/services/facial_recognition.py` | Used by face services |
| `app/services/russia_filter.py` | Used by filtering logic |

---

## TEMPLATE DATA EXPECTATIONS

### `phase1_results.html` expects:
```
task_id: string
target_name: string
has_photo: boolean
photo_filename: string | null
platforms: list of (platform_name, accounts_list) tuples
total_accounts: int
stats: {
    usernames_searched: int,
    raw_accounts: int,
    validated_accounts: int,
    elapsed_time: float,
    face_matches: int
}
```

Each account in platforms has:
- `url`, `username`, `platform`
- `display_name`, `photo_url` (from people search)
- `confidence_score`, `confidence_level`, `name_similarity` (from scoring)
- `face_match`, `face_similarity` (from face matching)

### `phase2.html` expects:
- Reads from sessionStorage `phase2_input` (set by Phase 1 results)
- Sends JSON to `/phase2/start`
- Polls `/phase2/progress/<task_id>`
- Gets results from `/phase2/results/<task_id>`:
  - `phones`: [{number, source, confidence, verified_on}]
  - `emails`: [{email, source, confidence, verified_on}]
  - `additional_profiles`: [{platform, url, username, source}]
  - `face_matches`: [{platform, profile_url, username, similarity}]

### `phase3.html` expects:
- `investigation_id` passed in URL
- Sends JSON to `/phase3/start`
- Gets results from `/phase3/results/<task_id>`

### `identity_card.html` expects:
- `investigation_id` passed in URL
- Calls `/report/generate/<investigation_id>` to get HTML content

---

## BURATINO FEATURES — STATUS

### Feature: Real VK/OK people search (not username guessing)
- **Service exists:** ✅ YES
  - `app/services/phase1/vk_people_search.py`
  - `app/services/phase1/ok_people_search.py`
- **Route calls it:** ✅ YES
  - `combined_search.py` lines 266-308 calls both services
- **Template displays it:** ✅ YES
  - Results include `display_name`, `photo_url`, `name_similarity`, `name_match`

### Feature: Face search (search4faces + Yandex Images)
- **Service exists:** ✅ YES
  - `app/services/phase1/face_search.py`
  - `app/services/phase2/search4faces_service.py`
  - `app/services/phase2/face_search_api.py`
- **Route calls it:** ✅ YES
  - Phase 1: `combined_search.py` line 362 calls `face_search_service.search_by_photo()`
  - Phase 2: `phase2/combined_search.py` line 395 calls `search_all_databases()`
- **Template displays it:** ✅ YES

### Feature: Confidence scoring on results
- **Service exists:** ✅ YES
  - `combined_search.py` method `_calculate_confidence_scores()` lines 464-517
- **Route calls it:** ✅ YES
- **Template displays it:** ✅ YES
  - Results include `confidence_score`, `confidence_level`, `name_similarity`

### Feature: Phone-to-name validation
- **Service exists:** ✅ YES
  - `app/services/phase2/russian_phone_validator.py`
  - `app/services/phase2/phone_discovery.py`
- **Route calls it:** ✅ YES
- **Template displays it:** ✅ YES

### Feature: Cross-person connection mapping
- **Service exists:** ✅ YES
  - `app/services/phase4/connection_analyzer.py`
  - `app/models/connection.py`
- **Route calls it:** ✅ YES
  - `/api/investigation/<id>/connections` endpoints
- **Template displays it:** ✅ YES
  - `graph.html` shows relationship diagram via vis.js

### Feature: Business registry search
- **Service exists:** ✅ YES - `app/services/phase3/business_registry.py`
- **Route calls it:** ✅ YES
- **Template displays it:** ✅ YES

### Feature: Court records search
- **Service exists:** ✅ YES - `app/services/phase3/court_search.py`
- **Route calls it:** ✅ YES
- **Template displays it:** ✅ YES

---

## NAVIGATION GAPS (UI only, not code)

### 1. Phase 4 People Search not in main navigation
- **Location:** `app/templates/base.html`
- **Problem:** Nav only links to `/` and `/phase1`, not `/search/people`
- **Fix:** Add link to People Search in nav

### 2. Phase 2 → Phase 3 flow missing
- **Location:** `app/templates/phase2.html`
- **Problem:** No "Continue to Phase 3" button after results
- **Fix:** Add button that stores phase2 results and redirects to Phase 3

### 3. Phase 3 → Report flow missing
- **Location:** `app/templates/phase3.html`
- **Problem:** No "Generate Identity Card" button
- **Fix:** Add button that redirects to `/report/<investigation_id>`

### 4. No unified dashboard
- **Problem:** Can't see all investigations in one place
- **Fix:** Create dashboard page listing all investigations with status

---

## VERIFICATION CHECKLIST

Test with target: **Daniil Glazkov** (has known username @etoglaz)

| Test | Expected Result | Status |
|------|-----------------|--------|
| Phase 1 finds real VK/OK profiles | Should find profiles by name search | 🔲 UNTESTED |
| Phase 1 shows profile photos | Photos from VK/OK visible | 🔲 UNTESTED |
| Phase 1 shows confidence scores | High/medium/low badges visible | 🔲 UNTESTED |
| Phase 2 email discovery works | Finds and verifies emails | 🔲 UNTESTED |
| Phase 2 phone discovery works | Finds and validates phones | 🔲 UNTESTED |
| Phase 3 business records works | Searches ЕГРЮЛ/ЕГРИП | 🔲 UNTESTED |
| Phase 3 court records works | Searches court databases | 🔲 UNTESTED |
| Phase 4 connection mapping works | Shows relationships | 🔲 UNTESTED |
| Identity card shows all data | All fields populated | 🔲 UNTESTED |
| @etoglaz username IS found | Regression test | 🔲 UNTESTED |

---

## CONCLUSION

**The Буратино-style architecture IS properly implemented.** All routes correctly call the new services:

1. ✅ Phase 1 uses real VK/OK/Telegram people search (not just username guessing)
2. ✅ Phase 2 uses comprehensive email/phone discovery with validation
3. ✅ Phase 3 uses business registry, court records, and text analysis
4. ✅ Phase 4 uses connection analysis and entity resolution
5. ✅ Report generation compiles data from all phases

**No rewiring needed.** The only improvements needed are:
1. Navigation UI enhancements (add Phase 4 link, add phase-to-phase buttons)
2. Cleanup of 3 deprecated service files (optional, doesn't affect functionality)
3. End-to-end testing to verify data flow works correctly

---

*Audit completed by Claude Opus 4.5 on 2026-02-05*
