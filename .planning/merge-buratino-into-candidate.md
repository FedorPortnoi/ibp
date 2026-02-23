# Plan: Merge People Search (Буратино) into Candidate Check

## EXECUTION STATUS

All 15 tasks from the merge plan have been completed across 19 commits on the `merge-buratino` branch.

| Task | Description | Status | Commit |
|------|-------------|--------|--------|
| 1 | Model changes (CandidateCheck new fields) | ✅ DONE | `2e7d93b` feat: add 14 new fields to CandidateCheck |
| 2 | Stage 5 orchestrator — social_analysis.py | ✅ DONE | `a77d445` feat: Stage 5 social analysis orchestrator with demo mode |
| 3 | Stage 6 orchestrator — behavioral_analysis.py | ✅ DONE | `bf4b89d` feat: Stage 6 behavioral analysis orchestrator with demo mode |
| 4 | Stage 4 enhancement — wire SourceManager + supplementary | ✅ DONE | `fbf15a7` feat: supplementary contact discovery for Stage 5 feedback loop |
| 5 | Pipeline.py — integrate Stages 5-8 + mode toggle | ✅ DONE | `eae2252` refactor: update pipeline to 8-stage progress layout + `d101adc` + `fa358b7` + `ee8a2b6` + `2ddcb6e` |
| 6 | Risk scorer enhancement — 8 categories | ✅ DONE | `4872461` feat: add social behavior and behavioral pattern risk dimensions |
| 7 | Route changes — candidate_check.py | ✅ DONE | `692260d` feat: candidate check routes — mode toggle, confirmation, API endpoints |
| 8 | Profile confirmation template | ✅ DONE | `c1af53e` feat: profile confirmation template for Precise Mode |
| 9 | Progress template update — 8 stages | ✅ DONE | `7faa447` feat: 8-stage progress bar with confirmation pause UI |
| 10 | Dossier template enhancement | ✅ DONE | `9e84e51` feat: enhanced dossier with social graph, geo map, behavioral analysis tabs |
| 11 | People search form — mode selector | ✅ DONE | `39e8c53` feat: mode selector on candidate check form |
| 12 | PDF export template update | ✅ DONE | `5d380cb` feat: enhanced PDF export with social/behavioral/geo data |
| 13 | Report builder — Stage 8 | ✅ DONE | `9d0ff22` feat: Stage 8 unified report builder with demo mode |
| 14 | Update existing tests | ✅ DONE | `93f437a` fix: resolve set ordering bugs in email guessing tests |
| 15 | New integration tests | ✅ DONE | `b0845d7` feat: integration tests for unified 8-stage candidate check |

### Notes
- No tasks were skipped. All 15 completed successfully.
- The `1f5b3e4` commit (wire breach APIs + LeakDB into candidate check Stage 4) was done before the formal task numbering but corresponds to Task 4 scope.
- Pipeline integration (Task 5) was spread across 5 commits as stages were wired in incrementally.

---

## Executive Summary

Merge the 3-phase People Search flow (Phase 1 → Phase 2 → Phase 3) into Candidate Check,
creating a unified 8-stage pipeline. After the merge, all Buratino routes/templates become
legacy (kept but deprecated, not deleted — to avoid breaking bookmarks and allow gradual migration).

---

## A) FILE INVENTORY

### Files that move into candidate pipeline UNCHANGED (import-only)
These services are already self-contained — the pipeline will simply import and call them:

| File | Used in Stage | Currently called from |
|------|---------------|----------------------|
| `app/services/phase1/buratino_vk_search.py` | Stage 3 (already used) | pipeline.py line 344 |
| `app/services/phase1/telegram_discovery.py` | Stage 3 (already used) | pipeline.py line 420 |
| `app/services/phase1/yandex_search.py` | Stage 3 (NEW call) | phase1.py only |
| `app/services/phase1/fuzzy_matching.py` | Stage 3 (indirect) | buratino_vk_search |
| `app/services/phase1/russian_diminutives.py` | Stage 3 (indirect) | multiple services |
| `app/services/phase1/transliteration.py` | Stage 3+4 (indirect) | multiple services |
| `app/services/phase1/vk_web_search.py` | Stage 3 (indirect) | buratino_vk_search |
| `app/services/phase2/search4faces_service.py` | Stage 5 | phase2 routes only |
| `app/services/phase2/yaseeker_service.py` | Stage 5 | phase2 routes only |
| `app/services/phase2/face_search_api.py` | Stage 5 | phase2 routes only |
| `app/services/phase2/social_graph.py` | Stage 5 | phase2 routes only |
| `app/services/phase2/username_intelligence.py` | Stage 5 | phase2 routes only |
| `app/services/phase2/source_manager.py` | Stage 4 (enhance) | phase2 routes only |
| `app/services/phase2/phone_sources.py` | Stage 4 (enhance) | phase2 routes only |
| `app/services/phase3/geo_extractor.py` | Stage 6 | phase3 routes only |
| `app/services/phase3/text_analyzer.py` | Stage 6 | phase3 routes only |
| `app/services/phase3/video_analyzer.py` | Stage 6 (optional) | phase3 routes only |
| `app/services/snoop_search.py` | Stage 5 | manual only |
| `app/services/report_generator.py` | Stage 8 | report routes |
| `app/services/risk_scoring.py` | Stage 7 (enhance) | scoring routes |

### Files that need MODIFICATIONS

| File | What changes | Complexity |
|------|-------------|-----------|
| `app/services/candidate/pipeline.py` | Add stages 5-8, add mode toggle, add pause/resume logic | **XL** |
| `app/services/candidate/risk_scorer.py` | Add social/behavioral dimensions from Stage 5+6 data | **M** |
| `app/services/candidate/contact_discovery.py` | Wire in full SourceManager (18 plugins) instead of 9-step chain | **L** |
| `app/models/candidate_check.py` | New fields for social graph, geo, timeline, mode, investigation link | **M** |
| `app/routes/candidate_check.py` | New endpoints (confirm profiles, resume), mode selector, enhanced dossier | **L** |
| `app/__init__.py` | No change needed (blueprints stay registered, both old and new work) | **—** |
| `app/templates/people_search.html` | Add mode selector to candidate form tab (already has candidate tab) | **S** |
| `app/templates/candidate_progress.html` | New stages in progress bar, pause/confirmation UI | **M** |
| `app/templates/candidate_dossier.html` | Add social graph, geo heatmap, timeline, identity card sections | **L** |
| `app/templates/candidate_dossier_pdf.html` | Mirror dossier changes for PDF export | **M** |

### Files that become DEAD CODE after merge (deprecate, don't delete)
These routes/templates will still work but are superseded by candidate check:

| File | Reason |
|------|--------|
| `app/routes/phase1.py` | VK search now embedded in candidate Stage 3 |
| `app/routes/phase2.py` | Contact/graph discovery now in candidate Stages 4-5 |
| `app/routes/phase3.py` | Business/courts/FSSP now in candidate Stages 1+6 |
| `app/templates/phase1_buratino_new.html` | Replaced by candidate form |
| `app/templates/phase1_buratino_results.html` | Replaced by candidate confirmation page |
| `app/templates/phase2_analyze.html` | No longer needed |
| `app/templates/phase2_buratino_results.html` | Merged into candidate dossier |
| `app/templates/phase3_buratino.html` | No longer needed |
| `app/templates/phase3_buratino_results.html` | Merged into candidate dossier |
| `app/templates/phase2.html` | Stub page, unused |
| `app/templates/phase3.html` | Stub page, unused |

### NEW files needed

| File | Purpose |
|------|--------|
| `app/templates/candidate_confirm_profiles.html` | Profile confirmation page (Precise Mode pause point) |
| `app/services/candidate/social_analysis.py` | Stage 5 orchestrator (facial recognition + social graph + snoop + yaseeker) |
| `app/services/candidate/behavioral_analysis.py` | Stage 6 orchestrator (text analysis + geo extraction + timeline) |
| `app/services/candidate/report_builder.py` | Stage 8 orchestrator (identity card + dossier + graph + geo + timeline export) |

---

## B) MODEL CHANGES

### CandidateCheck — New fields

```python
# --- Mode & Flow Control ---
check_mode = db.Column(db.String(20), default='quick')  # 'quick' or 'precise'
paused_at_stage = db.Column(db.String(50), nullable=True)  # 'awaiting_confirmation' or None

# --- Investigation Link (optional, for identity card/report reuse) ---
investigation_id = db.Column(db.String(36), db.ForeignKey('investigations.id'), nullable=True)

# --- Stage 3 Enhanced: Profile Confirmation ---
_confirmed_profiles = db.Column('confirmed_profiles', db.Text, default='[]')  # JSON
# List of user-confirmed social profiles (VK/Telegram/Yandex) with platform, id, url, name

# --- Stage 5: Deep Social Analysis ---
_social_graph_data = db.Column('social_graph_data', db.Text, default='{}')  # JSON (vis.js format)
_face_matches = db.Column('face_matches', db.Text, default='[]')  # JSON (Search4Faces results)
_username_accounts = db.Column('username_accounts', db.Text, default='[]')  # JSON (Snoop + YaSeeker)

# --- Stage 6: Behavioral Intelligence ---
_geo_analysis = db.Column('geo_analysis', db.Text, default='{}')  # JSON (LocationAnalysis)
_text_analysis = db.Column('text_analysis', db.Text, default='{}')  # JSON (TextAnalysisResult)
_activity_timeline = db.Column('activity_timeline', db.Text, default='[]')  # JSON

# --- Stage 7 Enhanced: Dimensional Risk ---
_risk_breakdown = db.Column('risk_breakdown', db.Text, default='{}')  # JSON (7-dimension scoring)
risk_score_numeric = db.Column(db.Float, nullable=True)  # 0-100 composite score

# --- Stage 8: Report ---
report_generated = db.Column(db.Boolean, default=False)
report_path = db.Column(db.String(500), nullable=True)
```

### New status values
Current: `pending → running → complete | error`
New: `pending → running → awaiting_confirmation → running → complete | error`

The `awaiting_confirmation` status is set when `check_mode='precise'` and Stage 3 finishes.
Pipeline pauses, frontend shows confirmation page. Resume sets status back to `running`.

### Migration plan
- Use Flask-Migrate: `flask db migrate -m "add social/behavioral/mode fields to candidate_check"`
- All new columns are nullable or have defaults → no data loss on existing records
- No need to backfill existing records

---

## C) PIPELINE CHANGES

### Current pipeline.py structure (5 stages)

```
run_candidate_pipeline(app, task_id, check_id)
  Stage 1: Government Registries (business + courts + FSSP + bankruptcy)  [0-25%]
  Stage 2: Security Checks (sanctions)                                     [25-35%]
  Stage 3: Social Media (VK + Telegram search)                             [35-55%]
  Stage 4: Contact Enrichment (9-step chain + Holehe)                      [55-80%]
  Stage 5: Risk Analysis (6-category red flags)                            [80-100%]
```

### New pipeline structure (8 stages)

```
run_candidate_pipeline(app, task_id, check_id)
  Stage 1: Government Registries (UNCHANGED)                               [0-15%]
  Stage 2: Security/Sanctions (UNCHANGED)                                  [15-25%]
  Stage 3: Social Media Discovery (ENHANCED — add Yandex, add pause)       [25-40%]
    → If precise mode: pause pipeline, set status='awaiting_confirmation'
    → Frontend shows candidate_confirm_profiles.html
    → User confirms → POST /candidate/resume/<task_id> → pipeline resumes
  Stage 4: Contact Discovery (ENHANCED — wire SourceManager 18 plugins)    [40-55%]
  Stage 5: Deep Social Analysis (NEW)                                      [55-70%]
    5a. Facial recognition (Search4Faces 3 databases + FaceCheck.ID)
    5b. Social graph (fetch friends → NetworkX → Louvain → vis.js export)
    5c. Snoop username search (5,372 sites, filtered to Russian)
    5d. YaSeeker (Yandex Collections, Dzen, Music)
    5e. FEEDBACK: new accounts found → feed into Stage 4 contact discovery (re-enrich)
  Stage 6: Behavioral Intelligence (NEW)                                   [70-82%]
    6a. VK wall text analysis (sentiment, keywords, topics)
    6b. Geo extraction + location patterns (100 Russian cities)
    6c. Activity timeline + posting patterns
  Stage 7: Risk Scoring (ENHANCED — add social/behavioral dimensions)      [82-92%]
  Stage 8: Report Generation (ENHANCED)                                    [92-100%]
    8a. Risk dossier (existing)
    8b. Identity card (from report_generator)
    8c. Social graph embed (vis.js data stored in model)
    8d. Geo heatmap data (stored in model)
    8e. Activity timeline data (stored in model)
```

### Key implementation details

#### Stage 3 pause/resume mechanism
```python
# In pipeline.py, after Stage 3 social media discovery:
if check.check_mode == 'precise' and social_profiles_found:
    check.social_media_profiles = profiles_list
    check.status = 'awaiting_confirmation'
    check.paused_at_stage = 'awaiting_confirmation'
    db.session.commit()
    task.update('social', 'Ожидание подтверждения профиля', 40)

    # Wait loop: poll every 2s until status changes or cancelled
    while check.status == 'awaiting_confirmation' and not task.cancelled:
        time.sleep(2)
        db.session.refresh(check)  # Re-read from DB

    if task.cancelled:
        return

    # User confirmed — check.confirmed_profiles now populated
    # Continue with Stage 4 using confirmed profile data
```

#### Stage 5 feedback loop (→ Stage 4 re-enrichment)
```python
# After Stage 5 discovers new accounts:
new_accounts = []  # From Snoop, YaSeeker, facial recognition
if new_accounts:
    task.update('social_analysis', 'Дообогащение новых аккаунтов', 68)
    # Run mini Stage 4 for just the new accounts
    supplementary_contacts = contact_service.discover_supplementary(
        new_accounts=new_accounts,
        existing_contacts=check.contact_discoveries
    )
    # Merge into existing contacts (deduplicate)
    merged = _merge_contacts(check.contact_discoveries, supplementary_contacts)
    check.contact_discoveries = merged
    db.session.commit()
```

#### Stage 4 SourceManager integration
Currently, `contact_discovery.py` has a hand-built 9-step chain. Enhancement:
- Keep steps 1-5 (input contacts, VK profiles, Telegram, business records, FSSP) as-is
- Replace steps 6-9 with `SourceManager.run_all()` which auto-discovers all 18 plugins
- Add step 6b: SourceManager breach enrichment (replaces manual HudsonRock/LeakCheck/ProxyNova calls)
- Keep Holehe verification as final step (most expensive, runs last)

### Stage 5 orchestrator (`social_analysis.py`)
```python
def run_social_analysis(check: CandidateCheck, task: CandidateTaskStatus) -> dict:
    """
    Stage 5: Deep Social Analysis
    Returns: {face_matches, social_graph, username_accounts, new_accounts_for_enrichment}
    """
    results = {}
    confirmed = check.confirmed_profiles or check.social_media_profiles

    # 5a. Facial recognition (if photo available)
    if any(p.get('photo_url') for p in confirmed):
        face_matches = search_faces_sync(photo_path_or_url)
        results['face_matches'] = [m.to_dict() for m in face_matches]

    # 5b. Social graph (if VK profile confirmed)
    vk_profiles = [p for p in confirmed if p.get('platform') == 'vk']
    if vk_profiles:
        graph_builder = SocialGraphBuilder()
        graph_data = graph_builder.build_from_friends(vk_id, center_data, friends)
        results['social_graph'] = graph_builder.export_visjs(graph_data)

    # 5c. Snoop username search
    usernames = extract_usernames(confirmed)
    if usernames:
        snoop = SnoopSearchService()
        for username in usernames[:3]:  # Max 3 to limit time
            snoop_results = snoop.search_username(username, russian_only=True)
            results.setdefault('username_accounts', []).extend(snoop_results)

    # 5d. YaSeeker
    yaseeker = YaSeekerService()
    for username in usernames[:5]:
        yandex_accounts = yaseeker.check_all_services(username)
        results.setdefault('username_accounts', []).extend(
            [a.to_dict() for a in yandex_accounts if a.found]
        )

    # 5e. Collect new accounts for feedback into Stage 4
    results['new_accounts'] = _collect_new_accounts(results, check.contact_discoveries)

    return results
```

### Stage 6 orchestrator (`behavioral_analysis.py`)
```python
def run_behavioral_analysis(check: CandidateCheck, task: CandidateTaskStatus) -> dict:
    """
    Stage 6: Behavioral Intelligence
    Returns: {text_analysis, geo_analysis, activity_timeline}
    """
    confirmed = check.confirmed_profiles or check.social_media_profiles

    # 6a. Text analysis (VK wall posts)
    text_analyzer = TextAnalyzer()
    # Fetch wall posts via VK API for confirmed profiles
    wall_texts = _fetch_vk_wall_texts(confirmed)
    if wall_texts:
        text_result = text_analyzer.analyze_posts(wall_texts)
        results['text_analysis'] = text_result.__dict__

    # 6b. Geo extraction
    geo_extractor = GeoExtractor()
    geo_analysis = geo_extractor.extract_from_profiles(confirmed)
    results['geo_analysis'] = {
        'locations': [l.__dict__ for l in geo_analysis.locations],
        'home_location': geo_analysis.home_location,
        'frequent_places': geo_analysis.frequent_places,
        'map_data': geo_extractor.generate_map_data(geo_analysis.locations),
    }

    # 6c. Activity timeline
    results['activity_timeline'] = _build_activity_timeline(check)

    return results
```

---

## D) ROUTE CHANGES

### New endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `POST /candidate/resume/<task_id>` | POST | Resume pipeline after profile confirmation (Precise Mode) |
| `GET /candidate/confirm/<check_id>` | GET | Show profile confirmation page (Precise Mode) |
| `POST /candidate/confirm/<check_id>` | POST | Submit confirmed profiles, resume pipeline |
| `GET /candidate/api/social-graph/<check_id>` | GET | Get vis.js social graph data for dossier |
| `GET /candidate/api/geo-data/<check_id>` | GET | Get geo heatmap data for dossier |

### Modified endpoints

| Endpoint | What changes |
|----------|-------------|
| `POST /candidate/start` | Accept new `check_mode` field ('quick'/'precise'), default 'quick' |
| `GET /candidate/progress/<task_id>/status` | Return new stages (5-8) in progress data, handle 'awaiting_confirmation' status |
| `GET /candidate/dossier/<check_id>` | Pass social_graph, geo_analysis, text_analysis, face_matches, timeline to template |
| `GET /candidate/export/<check_id>/json` | Include new Stage 5+6+8 data in export |
| `GET /candidate/export/<check_id>/pdf` | Use enhanced PDF template with all sections |

### Deprecated endpoints (still work, but superseded)
All endpoints in these blueprints:
- `phase1_bp` (7 endpoints): `/phase1/new`, `/phase1/search/<id>`, `/phase1/confirm/...`, etc.
- `phase2_bp` (12 endpoints): `/phase2/start`, `/phase2/analyze/<id>`, `/phase2/buratino/results/<id>`, etc.
- `phase3_bp` (10 endpoints): `/phase3/buratino/<id>`, `/phase3/api/buratino/start/<id>`, etc.

**Total: 29 endpoints deprecated** — but NOT removed. They remain registered and functional.

---

## E) TEMPLATE CHANGES

### New templates

**`candidate_confirm_profiles.html`** — Profile confirmation page (Precise Mode)
- Shows: list of VK/Telegram profiles found in Stage 3
- Each profile card: photo, name, city, age, platform, confidence score, link
- Actions: "Подтвердить" (confirm) checkbox per profile, "Ни один не подходит" (none match) button
- Submit → POST `/candidate/confirm/<check_id>` → resumes pipeline
- Layout: similar to `phase1_buratino_results.html` but simpler (no 4-tier grouping)

### Modified templates

**`people_search.html`** — Add mode selector to candidate form tab
- The template already has a "Candidate Check" tab (second tab)
- Add radio buttons: "Быстрый режим" / "Точный режим" with description tooltips
- Add hidden input `check_mode` to the candidate form
- Complexity: **S** (just HTML/CSS, no logic changes)

**`candidate_progress.html`** — Enhanced progress bar
- Change from 5 stages to 8 stages in progress visualization
- Add "awaiting_confirmation" state: pause progress bar, show "Waiting for your input" message with link to confirmation page
- Update stage labels: add "Глубокий анализ", "Поведенческий анализ", "Генерация отчёта"
- Complexity: **M** (JS polling logic needs stage mapping update)

**`candidate_dossier.html`** — Major enhancement
- Add new tab sections:
  - "Социальный граф" — vis.js network visualization (copy from `phase2_buratino_results.html`)
  - "География" — Leaflet map with location points (from geo_analysis)
  - "Поведение" — Sentiment chart, keyword cloud, posting patterns (from text_analysis)
  - "Таймлайн" — Activity timeline visualization (from activity_timeline)
  - "Найденные аккаунты" — Snoop + YaSeeker results grid
  - "Распознавание лиц" — Face match results with similarity scores
- Add identity card section (embed from report_generator)
- Complexity: **L** (significant new HTML + JS, but mostly copying from existing templates)

**`candidate_dossier_pdf.html`** — Mirror dossier changes for PDF
- Add sections for social graph (static image or table), geo data, behavioral summary
- Complexity: **M**

### Deprecated templates (NOT deleted)
- `phase1_buratino_new.html`, `phase1_buratino_results.html`
- `phase2_analyze.html`, `phase2_buratino_results.html`
- `phase3_buratino.html`, `phase3_buratino_results.html`
- `phase2.html`, `phase3.html`

---

## F) RISK SCORING CHANGES

### Current RiskScorer dimensions (6 categories)
1. Business red flags (mass_director, liquidated_companies, etc.)
2. Court red flags (criminal_case, fraud_case, many_cases, defendant_cases)
3. FSSP red flags (active_debts, large_debt, tax_debt, alimony_debt)
4. Bankruptcy red flags (active_bankruptcy, recent_bankruptcy)
5. Sanctions red flags (sanctions_match, sanctions_unchecked)
6. Social media red flags (no_social_presence only)

### New dimensions to add from Stage 5+6

**Category 7: Social Behavior** (from Stage 5)
- `no_friends` (severity=LOW): VK profile with 0 friends (suspicious for background check)
- `isolated_graph` (severity=MEDIUM): Social graph has 0 connections (no mutual friends)
- `fake_profile_indicators` (severity=MEDIUM): Profile created recently + no photos + no posts
- `multiple_platforms_same_name` (severity=LOW, positive): Found on 5+ platforms (established identity)

**Category 8: Behavioral Patterns** (from Stage 6)
- `negative_sentiment` (severity=LOW): Predominantly negative posting pattern
- `risk_keywords_in_posts` (severity=MEDIUM): Posts contain: долг, суд, банкрот, розыск, кредит
- `night_owl_pattern` (severity=LOW): Consistent late-night posting (2-5 AM)
- `geo_discrepancy` (severity=MEDIUM): Claimed city differs from posting geo-location
- `inactive_profile` (severity=LOW): No posts in 12+ months

### How Stage 6 feeds into Stage 7
```python
# In risk_scorer.py, add new methods:
def _analyze_social_behavior(self, check) -> List[dict]:
    """Category 7: Social behavior analysis from Stage 5 data."""
    flags = []
    graph = check.social_graph_data
    if graph and graph.get('stats', {}).get('node_count', 0) == 0:
        flags.append({'severity': 'medium', 'category': 'social', 'code': 'isolated_graph', ...})
    # ... more checks
    return flags

def _analyze_behavioral_patterns(self, check) -> List[dict]:
    """Category 8: Behavioral analysis from Stage 6 data."""
    flags = []
    text = check.text_analysis
    if text and text.get('sentiment', {}).get('score', 0) < -0.3:
        flags.append({'severity': 'low', 'category': 'behavioral', 'code': 'negative_sentiment', ...})
    # ... more checks
    return flags
```

### Risk level calculation update
Current: 6 categories → score based on flag severity counts
New: Same algorithm, but with 8 categories contributing flags. No threshold changes needed —
more data simply provides more accurate risk assessment.

---

## G) EXECUTION ORDER

### Task 1: Model changes (CandidateCheck new fields) — **S**
- Add new columns to `CandidateCheck` model
- Run migration
- Add property getters/setters for JSON fields
- **Test:** Verify migration succeeds, existing records still load
- **Risk:** None — all new fields are nullable/defaulted

### Task 2: Stage 5 orchestrator — `social_analysis.py` — **L**
- Create `app/services/candidate/social_analysis.py`
- Import and orchestrate: Search4Faces, SocialGraphBuilder, SnoopSearchService, YaSeekerService
- Function: `run_social_analysis(check, task) → dict`
- Handle: photo download for face search, VK friend fetching, username extraction
- **Test:** Unit test with mocked services, verify return structure
- **Risk:** Snoop subprocess may timeout on Windows — add 120s timeout

### Task 3: Stage 6 orchestrator — `behavioral_analysis.py` — **M**
- Create `app/services/candidate/behavioral_analysis.py`
- Import and orchestrate: TextAnalyzer, GeoExtractor, VK wall fetch
- Function: `run_behavioral_analysis(check, task) → dict`
- Handle: VK API wall.get for confirmed profiles
- **Test:** Unit test with mocked VK API responses
- **Risk:** Text analyzer is CPU-light; geo extractor is hardcoded to 100 cities

### Task 4: Stage 4 enhancement — wire SourceManager — **M**
- Modify `contact_discovery.py` to optionally use SourceManager
- Add method: `discover_with_source_manager(check)` that runs all 18 plugins
- Keep existing `discover()` as fallback
- Add: `discover_supplementary(new_accounts, existing_contacts)` for Stage 5 feedback
- **Test:** Verify SourceManager auto-discovers all plugins, dedup works
- **Risk:** May need to handle SourceManager import errors gracefully (optional deps)

### Task 5: Pipeline.py — integrate Stages 5-8 + mode toggle — **XL**
- Add `check_mode` handling at Stage 3 (pause/resume loop)
- Add Stage 5 call: `run_social_analysis()`
- Add Stage 5e feedback: call `discover_supplementary()` if new accounts found
- Add Stage 6 call: `run_behavioral_analysis()`
- Update Stage 7: call enhanced `RiskScorer.analyze()`
- Add Stage 8: call report generation (store results in model)
- Update progress percentages for 8-stage layout
- Update `CandidateTaskStatus` stage names
- **Test:** E2E pipeline test with mocked services
- **Risk:** This is the critical integration task — pause/resume needs careful testing
- **Breaks existing tests:** `test_pipeline_resilience.py` (stage names change)

### Task 6: Risk scorer enhancement — **M**
- Add `_analyze_social_behavior()` method
- Add `_analyze_behavioral_patterns()` method
- Call both in `analyze()` method
- Add new red flag codes to documentation
- **Test:** Unit test for new categories (mock graph/text data)
- **Risk:** None — additive changes only
- **Breaks existing tests:** `test_risk_scorer.py`, `test_risk_scorer_edges.py` (new flag categories in output)

### Task 7: Route changes — candidate_check.py — **L**
- Add `check_mode` field parsing in `start_check()`
- Add `GET /candidate/confirm/<check_id>` route
- Add `POST /candidate/confirm/<check_id>` route (sets confirmed_profiles, resumes pipeline)
- Add `GET /candidate/api/social-graph/<check_id>` route
- Add `GET /candidate/api/geo-data/<check_id>` route
- Update `dossier()` to pass new data to template
- Update `export_json()` to include new fields
- Update `export_pdf()` to use enhanced PDF template
- Update `progress_status()` to handle `awaiting_confirmation`
- **Test:** Route-level tests for new endpoints
- **Risk:** None — all new endpoints, existing ones get minor additions

### Task 8: Profile confirmation template — **M**
- Create `candidate_confirm_profiles.html`
- Profile cards with photo, name, confidence, platform links
- Checkboxes for confirmation, "none match" button
- AJAX form submission to `/candidate/confirm/<check_id>`
- Auto-redirect back to progress page after submission
- **Test:** Visual verification + Playwright test
- **Risk:** None — new template

### Task 9: Progress template update — **S**
- Update `candidate_progress.html` from 5 to 8 stages
- Add `awaiting_confirmation` state handling (show link to confirmation page)
- Update stage label mapping in JavaScript
- **Test:** Visual verification
- **Risk:** None — JS changes only

### Task 10: Dossier template enhancement — **L**
- Add vis.js social graph tab (copy JS from `phase2_buratino_results.html`)
- Add geo map section (Leaflet.js integration)
- Add behavioral analysis section (sentiment, keywords, posting pattern)
- Add timeline section
- Add face match results section
- Add Snoop/YaSeeker accounts section
- Add identity card section
- **Test:** Visual verification + data population check
- **Risk:** Large template — ensure tab switching works with many sections

### Task 11: People search form — mode selector — **S**
- Add radio buttons to the candidate tab in `people_search.html`
- Hidden `check_mode` field in form
- Tooltip descriptions for each mode
- **Test:** Visual verification
- **Risk:** None

### Task 12: PDF export template update — **M**
- Update `candidate_dossier_pdf.html` with new sections
- Social graph as static table (no vis.js in PDF)
- Geo data as location list (no map in PDF)
- Behavioral summary as text
- **Test:** Generate PDF, verify all sections render
- **Risk:** PDF rendering with Playwright needs testing for large dossiers

### Task 13: Report builder — Stage 8 — **M**
- Create `app/services/candidate/report_builder.py`
- Orchestrate: report_generator identity card + all data compilation
- Store report path in model
- **Test:** Unit test for report data aggregation
- **Risk:** Identity card generator may need adaptation for CandidateCheck (vs Investigation)

### Task 14: Update existing tests — **M**
- Fix `test_pipeline_resilience.py` — update stage expectations
- Fix `test_risk_scorer.py` — add assertions for new categories
- Fix `test_risk_scorer_edges.py` — update expected flag counts
- Update `test_contact_discovery.py` — verify SourceManager integration
- **Test:** All existing tests pass
- **Risk:** Need to understand each test's exact assertions

### Task 15: New integration tests — **M**
- Test: Full 8-stage pipeline with mocked services (quick mode)
- Test: Precise mode pause/resume flow
- Test: Stage 5 feedback loop (new accounts → re-enrichment)
- Test: Dossier with all 8 stages of data
- Test: JSON/PDF export with full data
- **Test:** New test file: `tests/test_candidate_unified.py`

---

## H) TEST IMPACT

### Tests that will BREAK (need fixes)

| Test file | Why it breaks | Fix needed |
|-----------|-------------|-----------|
| `tests/unit/test_pipeline_resilience.py` | Stage names change (5→8) | Update stage name assertions |
| `tests/unit/test_risk_scorer.py` | New analyze() returns more categories | Update expected flag list |
| `tests/unit/test_risk_scorer_edges.py` | New categories in output | Update threshold expectations |
| `tests/unit/test_contact_discovery.py` | If discover() signature changes | Update to new method signature |

### Tests that become OBSOLETE (but still pass)
None — the old routes/services aren't removed, so all phase1/2/3 tests still work.
They just test "legacy" code paths.

### Tests that are UNAFFECTED (~50 files)
All unit tests for phase1 services (transliteration, diminutives, name matching, phone normalization) —
these services don't change, they just get called from a new location.

All E2E smoke tests (`test_e2e_smoke.py`) — existing routes still return 200.

All stress/security tests (`test_r3_*.py`) — test phase2 services which don't change.

### NEW tests needed

| Test file | What it covers | Priority |
|-----------|---------------|----------|
| `tests/test_candidate_unified.py` | Full 8-stage pipeline (quick + precise modes) | HIGH |
| `tests/unit/test_social_analysis.py` | Stage 5 orchestrator unit tests | HIGH |
| `tests/unit/test_behavioral_analysis.py` | Stage 6 orchestrator unit tests | MEDIUM |
| `tests/unit/test_report_builder.py` | Stage 8 report generation | MEDIUM |
| `tests/unit/test_candidate_model_new_fields.py` | New model fields serialization | LOW |

---

## Dependency Graph (Task ordering)

```
Task 1 (Model) ─────────────────────────┐
                                         │
Task 2 (Stage 5 service) ───┐           │
                             │           │
Task 3 (Stage 6 service) ───┤           │
                             │           │
Task 4 (Stage 4 enhance) ───┤           │
                             ├──→ Task 5 (Pipeline integration) ──→ Task 14 (Fix tests)
Task 6 (Risk scorer) ───────┤                                       │
                             │                                       │
Task 13 (Report builder) ───┘                                       │
                                                                     │
Task 7 (Routes) ──→ Task 8 (Confirm template) ──┐                  │
                 ──→ Task 9 (Progress template) ──┤                  │
                 ──→ Task 10 (Dossier template) ──┤──→ Task 15 (New tests)
                 ──→ Task 11 (Form mode selector)─┤
                 ──→ Task 12 (PDF template) ──────┘
```

**Parallelizable:** Tasks 1, 2, 3, 4, 6, 13 can all start in parallel.
**Blocking:** Task 5 depends on Tasks 1-4, 6, 13. Tasks 7-12 depend on Task 5.
**Final:** Tasks 14, 15 run after everything else.

---

## Summary

| Metric | Count |
|--------|-------|
| New service files | 3 |
| New template files | 1 |
| Modified service files | 4 |
| Modified route files | 1 |
| Modified template files | 4 |
| New model columns | ~12 |
| New route endpoints | 5 |
| Deprecated routes (kept) | 29 |
| Deprecated templates (kept) | 8 |
| Tests that break | 4 |
| New tests needed | 5 |
| Total tasks | 15 |
| Estimated complexity | XL (multi-day effort) |
