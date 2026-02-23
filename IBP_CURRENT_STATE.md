# IBP Current State

**Last updated**: 2026-02-23
**Branch**: `merge-buratino` (19 commits ahead of `main`)
**Latest commit**: `b0845d7` feat: integration tests for unified 8-stage candidate check

---

## Codebase Metrics

| Metric | Count |
|--------|-------|
| Python files (app/) | 104 |
| Lines of code (app/) | 48,432 |
| HTML templates | 29 |
| Template lines | 11,171 |
| Test files | 61 |
| Test functions | ~2,814 |
| Test lines | 35,408 |
| Database models | 7 |
| Route blueprints | 13 |
| Service classes | 35+ |
| Total endpoints | 60+ |
| Pipeline stages | 8 |

**Total source files**: 194 (app/ + tests/ + templates)
**Total lines**: ~95,000 (app + tests + templates)

---

## Feature Completion vs Original Spec

### Merge Plan (15 tasks): **100% complete**

All 15 tasks from `.planning/merge-buratino-into-candidate.md` are implemented and committed.

### 8-Stage Pipeline: **100% wired, ~85% data quality**

| Stage | Wired | Real Data | Demo Fallback | Notes |
|-------|-------|-----------|---------------|-------|
| 1. Gov Registries | Yes | EGRUL + sudact.ru work | Empty results | FSSP API broken, bankruptcy needs Russian IP |
| 2. Security Checks | Yes | Interpol works globally | Empty results | Russian sanctions need Russian IP |
| 3. Social Media | Yes | VK + Telegram work | 3 fake VK profiles | Yandex may timeout (CAPTCHA) |
| 4. Contact Discovery | Yes | Breach APIs + Holehe work | Empty results | Paid APIs are stubs |
| 5. Social Analysis | Yes | Search4Faces + graph work | Demo graph data | Snoop needs local tool |
| 6. Behavioral Analysis | Yes | Text/geo/timeline work | Demo data | Requires VK wall access |
| 7. Risk Scoring | Yes | 8 categories scored | Scores empty data | Always produces a level |
| 8. Report Generation | Yes | Full dossier + PDF | Works with any data | Identity card, vis.js graph, geo map |

---

## What Works End-to-End in Demo Mode

These features work without any API keys configured:

1. Start a candidate check (quick or precise mode)
2. All 8 stages execute (with demo/empty data)
3. Progress bar tracks all 8 stages in real-time
4. Precise mode pauses at Stage 3 for profile confirmation
5. Risk scoring produces a risk level (CLEAN with no data)
6. Dossier page renders with all tabs (social graph, geo, behavioral, accounts)
7. PDF export generates a downloadable file
8. JSON export includes all stage data

## What Needs Real API Keys

| API Key | What It Enables | Cost |
|---------|----------------|------|
| `VK_SERVICE_TOKEN` | Real VK profiles, social graph, wall posts | Free (create VK app) |
| `TELEGRAM_API_ID/HASH/PHONE` | Telegram profile search | Free (my.telegram.org) |
| `SNUSBASE_API_KEY` | Extended breach database | $5-16/mo |
| `DEHASHED_EMAIL/API_KEY` | Extended breach database | $5.49/mo |
| `GETCONTACT_TOKEN` + keys | Phone-to-name reverse lookup | Requires rooted Android |
| `NUMBUSTER_API_KEY` | Phone lookup | Paid |
| `HUNTER_API_KEY` | Email verification (25/mo free) | Free tier available |
| `FSSP_API_TOKEN` | Enforcement proceedings API | Free but needs Russian IP |

## What Needs Russian IP

These data sources are geo-blocked or work poorly from outside Russia:

| Source | Impact Without Russian IP |
|--------|--------------------------|
| FSSP API | SSL errors, falls back to manual URL |
| EFRSB bankruptcy | May fail, Playwright fallback |
| Rosfinmonitoring sanctions | Cannot scrape, returns unchecked |
| MVD wanted list | Cannot scrape, returns unchecked |
| Extremist list | Cannot scrape, returns unchecked |
| kad.arbitr.ru (arbitration) | HTTP 451 blocked entirely |

**Works globally**: nalog.ru EGRUL, sudact.ru courts, Interpol, VK API, Telegram API, all breach APIs, Search4Faces

## What Is Completely Unimplemented

These features are mentioned in README/CLAUDE.md but have no working code:

| Feature | Status |
|---------|--------|
| OK.ru (Odnoklassniki) search | Only password recovery check exists |
| Instagram/Facebook/Twitter/TikTok search | Not implemented |
| Maigret integration | External tool, not wired into pipeline |
| Sherlock integration | External tool, not wired into pipeline |
| Property registry (Rosreestr) | Not implemented |
| Vehicle registry (GIBDD) | Not implemented |
| Passport verification (FMS) | Not implemented |
| Bank account discovery | Not implemented |
| Real-time monitoring | One-shot only |
| Multi-user RBAC | Single-user design |
| Compliance audit logs | Basic file logging only |

---

## Priority List: What to Build Next

### P0 — Critical (before merging to main)
1. **Run full test suite and fix failures** — Ensure all 2,814 tests pass
2. **Manual QA of 8-stage flow** — Test with real VK token, verify dossier renders correctly
3. **Merge to main** — Create PR, review, merge

### P1 — High Value
4. **Wire Snoop/Maigret into Stage 5** — These external tools exist locally, just need subprocess integration
5. **Add OK.ru search to Stage 3** — Recovery check exists, expand to profile search
6. **Deploy to Render** — Verify production config works, add health checks
7. **Rate limiting** — Add Flask-Limiter to public endpoints

### P2 — Medium Value
8. **Wire paid breach APIs** — Snusbase + DeHashed stubs are ready, just need keys
9. **SourceManager integration in Stage 4** — Replace manual 9-step chain with plugin auto-discovery
10. **Russian IP proxy** — Configure SOCKS5 proxy for geo-blocked sources
11. **Improve E2E test coverage** — Full Playwright test of candidate check flow

### P3 — Nice to Have
12. **Instagram/Twitter/TikTok** — Requires new scraping services
13. **Property/Vehicle registries** — Requires Russian government API access
14. **Multi-user auth** — Flask-Login with user roles
15. **Real-time monitoring** — Periodic re-checks with change detection

---

## Known Technical Debt

| Issue | Impact | Fix Effort |
|-------|--------|-----------|
| `per_profile_search.py` (2,695 lines) | Dead code, superseded by combined_search | Delete after confirming no imports |
| OSINT knowledge routes (5,354 lines) | Massive static data in route files | Move to JSON/YAML data files |
| No CSRF on all forms | Security gap | Add Flask-WTF csrf_token to all forms |
| No rate limiting | DoS vulnerability | Add Flask-Limiter |
| Error handler returns exception details | Information disclosure | Strip details in production |
| WeasyPrint reference in dossier.py | Always fails on Windows | Remove, use Playwright only |
| Duplicate SECRET_KEY / FLASK_SECRET_KEY | Confusing | Consolidate to one var |

---

## Branch Status

```
main (stable)
  └── merge-buratino (+19 commits, all 15 merge tasks complete)
       ├── 3 new service files (social_analysis, behavioral_analysis, report_builder)
       ├── 1 new template (candidate_confirm_profiles)
       ├── 14 new model fields on CandidateCheck
       ├── 5 new route endpoints
       ├── 8-category risk scorer (was 6)
       ├── Enhanced dossier (social graph, geo map, behavioral tabs)
       ├── Enhanced PDF export
       └── New integration test suite (test_candidate_unified.py)
```
