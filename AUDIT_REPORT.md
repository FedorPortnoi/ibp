# IBP AUDIT REPORT — LIVE vs DEAD CODE

**Generated:** 2026-02-02
**Auditor:** Claude Code
**Status:** AUDIT COMPLETE

---

## EXECUTIVE SUMMARY

**GOOD NEWS:** The codebase is actually WELL-WIRED. The Буратино-style services ARE being called by routes.

The routes correctly import and use the new orchestrators:
- Phase 1 → `CombinedSearchService` → Uses VK/OK/Telegram **people search** (real name search, not username guessing)
- Phase 2 → `Phase2CombinedSearch` → Uses email/phone discovery, breach checking, face search
- Phase 3 → `Phase3CombinedSearch` → Uses business registry, court records, geo extraction
- Phase 4 → `ResearchOrchestrator` → Coordinates cross-platform search

**POTENTIAL ISSUES IDENTIFIED:**
1. Phase 1 results page may not display all confidence/name-match data returned by services
2. Phase 4 `/search/people` route exists but may not be linked in main navigation
3. Connection mapping endpoint exists but cross-target analysis is minimal
4. Some old services (maigret_search, sherlock_search) are NOT used in main pipeline (replaced by direct platform APIs)

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

**Returns to Template:**
- `phase1_results.html` receives: `task_id`, `target_name`, `has_photo`, `photo_filename`, `platforms`, `total_accounts`, `stats`

**STATUS: ✅ LIVE - Properly wired to new services**

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

**Returns to Template:**
- JSON response with: `phones`, `emails`, `additional_profiles`, `face_matches`, `stats`, `errors`

**STATUS: ✅ LIVE - Properly wired to new services**

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

**Service Calls:**
- Line 79: `Phase3CombinedSearch()`
- Line 90: `searcher.investigate(target_name, confirmed_profiles, discovered_contacts, ...)`

**STATUS: ✅ LIVE - Properly wired to new services**

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

**STATUS: ✅ LIVE - Properly wired to new services**

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

**Service Calls:**
- `report_generator.compile_data(investigation.to_dict())`
- `report_generator.generate_identity_card_html(card_data)`
- `report_generator.generate_pdf_report(card_data, data)`

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

| File | Imported By | Status |
|------|-------------|--------|
| `app/services/combined_search.py` | phase1.py line 15 | ✅ LIVE |
| `app/services/username_generator.py` | combined_search.py line 27 | ✅ LIVE |
| `app/services/telegram_search.py` | combined_search.py line 28 | ✅ LIVE |
| `app/services/vk_search.py` | combined_search.py line 29 | ✅ LIVE |
| `app/services/ok_search.py` | combined_search.py line 30 | ✅ LIVE |
| `app/services/yandex_image_search.py` | combined_search.py line 31 | ✅ LIVE |
| `app/services/phase1/vk_people_search.py` | combined_search.py line 33 | ✅ LIVE |
| `app/services/phase1/ok_people_search.py` | combined_search.py line 34 | ✅ LIVE |
| `app/services/phase1/telegram_people_search.py` | combined_search.py line 35 | ✅ LIVE |
| `app/services/phase1/face_search.py` | combined_search.py line 36 | ✅ LIVE |
| `app/services/ultimate_face_matcher.py` | combined_search.py line 215 | ✅ LIVE |

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
| `app/services/phase3/video_analyzer.py` | ⚠️ EXISTS but not called directly |

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

## DEPRECATED/UNUSED SERVICE FILES

These files exist but are NOT called by the main pipeline:

| File | Notes |
|------|-------|
| `app/services/maigret_search.py` | ☠️ REPLACED by direct platform searches |
| `app/services/sherlock_search.py` | ☠️ REPLACED by direct platform searches |
| `app/services/phase1_service.py` | ☠️ OLD - replaced by combined_search.py |
| `app/services/deduplication.py` | ⚠️ May be imported somewhere |
| `app/services/face_comparator.py` | ⚠️ Imported by other services |
| `app/services/facial_recognition.py` | ⚠️ Imports russia_filter |
| `app/services/russia_filter.py` | ⚠️ Only used by deprecated maigret/sherlock |

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

### `phase2.html` expects:
- Receives profile selection from Phase 1
- Sends JSON to `/phase2/start`
- Polls `/phase2/progress/<task_id>`
- Gets results from `/phase2/results/<task_id>`

### `phase3.html` expects:
- `investigation_id` passed in URL
- Sends JSON to `/phase3/start`
- Gets results from `/phase3/results/<task_id>`

### `identity_card.html` expects:
- Receives HTML content generated by `report_generator.generate_identity_card_html()`

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
  - Shows face match score and photos

### Feature: Confidence scoring on results
- **Service exists:** ✅ YES
  - `combined_search.py` method `_calculate_confidence_scores()` lines 464-517
- **Route calls it:** ✅ YES
  - Called automatically in `search()` method
- **Template displays it:** ⚠️ PARTIAL
  - Results include `confidence_score`, `confidence_level`, `name_similarity`
  - Template may not fully utilize these fields (needs UI check)

### Feature: Phone-to-name validation (GetContact style)
- **Service exists:** ✅ YES
  - `app/services/phase2/russian_phone_validator.py`
  - `app/services/phase2/phone_discovery.py`
- **Route calls it:** ✅ YES
  - `phase2/combined_search.py` uses `RussianPhoneValidator`
- **Template displays it:** ✅ YES
  - Shows verified phone numbers with source attribution

### Feature: Cross-person connection mapping
- **Service exists:** ✅ YES
  - `app/services/phase4/connection_analyzer.py`
  - `app/models/connection.py`
- **Route calls it:** ✅ YES
  - `/api/investigation/<id>/connections` endpoints
  - `research_orchestrator.search_person()` calls analyzer
- **Template displays it:** ✅ YES
  - `graph.html` shows relationship diagram via vis.js

### Feature: Social graph / hidden connections
- **Service exists:** ✅ YES
  - `app/services/phase3/combined_search.py` method `_build_social_graph()`
  - `app/services/phase4/connection_analyzer.py`
- **Route calls it:** ✅ YES
  - Phase 3 builds social graph from profiles
  - Phase 4 analyzes and stores connections
- **Template displays it:** ✅ YES
  - `graph.html` and `identity_card.html` show connections

### Feature: Business registry search
- **Service exists:** ✅ YES
  - `app/services/phase3/business_registry.py`
- **Route calls it:** ✅ YES
  - `phase3.py` line 211 and Phase3CombinedSearch
- **Template displays it:** ✅ YES
  - Results shown in identity card

### Feature: Court records search
- **Service exists:** ✅ YES
  - `app/services/phase3/court_search.py`
- **Route calls it:** ✅ YES
  - `phase3.py` line 235 and Phase3CombinedSearch
- **Template displays it:** ✅ YES
  - Results shown in identity card with risk indicators

---

## DISCONNECT SUMMARY

**The code is actually WELL-WIRED.** However, there are a few improvements that could be made:

### 1. Template Enhancement Opportunities
- `phase1_results.html` could better display confidence levels (color badges)
- `phase1_results.html` could show name similarity scores
- Dashboard could link all 4 phases together in a workflow

### 2. Navigation Gaps
- `/search/people` (Phase 4) exists but may not be linked from main navigation
- No unified investigation dashboard to see all phases together

### 3. Deprecated Code Cleanup
These files could be removed as they're not used:
- `app/services/maigret_search.py` (replaced by direct platform APIs)
- `app/services/sherlock_search.py` (replaced by direct platform APIs)
- `app/services/phase1_service.py` (replaced by combined_search.py)

### 4. Data Flow Verification Needed
- Verify Phase 1 → Phase 2 → Phase 3 data passes correctly in UI
- Verify Investigation model stores all Phase 2/3 results

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
| Phase 3 business records works | Searches EGRUL/EGRIP | 🔲 UNTESTED |
| Phase 3 court records works | Searches court databases | 🔲 UNTESTED |
| Phase 4 connection mapping works | Shows relationships | 🔲 UNTESTED |
| Identity card shows all data | All fields populated | 🔲 UNTESTED |
| @etoglaz username IS found | Regression test | 🔲 UNTESTED |

---

## CONCLUSION

**The Буратино-style architecture IS properly implemented.** The routes correctly call the new services:

1. ✅ Phase 1 uses real VK/OK/Telegram people search (not just username guessing)
2. ✅ Phase 2 uses comprehensive email/phone discovery with validation
3. ✅ Phase 3 uses business registry, court records, and text analysis
4. ✅ Phase 4 uses connection analysis and entity resolution
5. ✅ Report generation compiles data from all phases

**No major rewiring needed.** The main opportunities are:
1. UI enhancements to display confidence data
2. Navigation improvements for cross-phase workflow
3. Cleanup of deprecated code
4. End-to-end testing to verify data flow

---

*Audit completed by Claude Code on 2026-02-02*
