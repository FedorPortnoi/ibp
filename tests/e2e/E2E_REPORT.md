# E2E Stress Test Report: Candidate Check Pipeline

**Date:** 2026-03-16
**Server:** https://shtirletzsled.ru
**Server version:** 6222f34 (pre-fix; pipeline fix a2046d3 committed but not yet deployed)
**Test script:** `tests/e2e/test_candidate_stress.py`

## Summary

| Metric | Value |
|--------|-------|
| Total cycles | 60 |
| PASS | 48 (80%) |
| EXPECTED_REJECT | 4 (7%) |
| FAIL | 8 (13%) |
| Avg pipeline time | 144s |
| Min pipeline time | 54s |
| Max pipeline time | 478s |

## Failure Analysis

All 8 failures are the **same root cause**: `Pipeline error: 1 (of 3) futures unfinished`

This is a **server-side bug** in `app/services/candidate/pipeline.py` where `concurrent.futures.as_completed()` with `timeout=120` raises `TimeoutError` when one of the 3 parallel gov registry futures (EGRUL, courts, FSSP) exceeds 120 seconds. The unhandled `TimeoutError` kills the entire pipeline instead of gracefully degrading.

**Fix committed:** `a2046d3` wraps `as_completed()` in `try/except TimeoutError`, processes already-completed futures, and marks timed-out ones as unavailable. Awaiting server redeployment.

### Failed Cycles

| Cycle | Category | Note |
|-------|----------|------|
| 11 | minimal | Иванов Пётр (standard name) |
| 20 | full | Ермаков Кирилл (all fields) |
| 21 | full | Захаров Тимур (all fields) |
| 32 | edge_name | СМИРНОВ АЛЕКСАНДР (all uppercase) |
| 36 | edge_name | Ан Ольга (2-letter surname) |
| 42 | edge_data | Passport without space |
| 43 | edge_data | Passport with space |
| 44 | edge_data | Phone 8-format |

No pattern by input data — failures are random, caused by upstream service latency (likely FSSP Playwright scraping exceeding 120s).

## Test Categories

| Category | PASS | FAIL | EXPECTED_REJECT |
|----------|------|------|-----------------|
| minimal (1-12) | 11 | 1 | 0 |
| full (13-24) | 10 | 2 | 0 |
| edge_name (25-36) | 10 | 2 | 0 |
| edge_data (37-48) | 6 | 3 | 3 |
| security (49-56) | 9 | 0 | 1 |
| stress (57-60) | 2 | 0 | 0 |

## Rejection Tests (4/4 correct)

| Cycle | Input | Expected | Got |
|-------|-------|----------|-----|
| 38 | Future DOB | Reject | "Дата рождения не может быть в будущем" |
| 41 | Invalid INN checksum (12-digit) | Reject | "Контрольная сумма ИНН некорректна" |
| 48 | Invalid INN checksum (10-digit) | Reject | "Контрольная сумма ИНН некорректна" |
| 56 | 255-char single word name | Reject | "Укажите полное имя (минимум имя и фамилия)" |

## Dossier Verification

All 48 passing pipelines have all 9 dossier sections verified:
- identity, business, courts, fssp, bankruptcy, sanctions, social, contacts, risk

## Bugs Found & Fixed

### Bug 1: `as_completed` TimeoutError crashes pipeline (SERVER)

- **Impact:** ~13% of pipeline runs fail when FSSP/court scraping is slow
- **Root cause:** `as_completed(futures, timeout=120)` raises `TimeoutError` which propagates unhandled, killing the pipeline
- **Fix:** `a2046d3` — wrap in try/except, process completed futures, mark timed-out as unavailable
- **Status:** Fixed in code, awaiting server redeployment

### Bug 2: Dossier verification false failures (TEST)

- **Impact:** Previous run had 10 false "404 page" failures due to gunicorn worker affinity
- **Root cause:** `_verify_dossier` used `page.goto()` which goes through gunicorn routing; ~50% of requests hit the wrong worker which redirects to progress page
- **Fix:** Replaced with `page.evaluate(fetch())` which stays in the same browser session context and gets dossier content directly via HTTP; added 5 retries with redirect detection
- **Status:** Fixed and verified — 0 false 404 failures in this run

## Security Test Results

All security/stress inputs handled correctly:
- XSS in name field: tags stripped, pipeline completes normally
- SQL injection in name: properly escaped, no error
- XSS in address field: sanitized
- Zero-width characters: handled gracefully
- RTL override character: handled gracefully
- Newlines in name: handled (treated as whitespace)
- Tabs in name: handled (treated as whitespace)
- Duplicate INN resubmission: creates separate check, no conflict
- Rapid re-submission: accepted normally

## Performance

- Pipeline completion: 54s - 478s (avg 144s)
- Fastest batches: cycles completing in ~60s (minimal input, no social media hits)
- Slowest: cycles with VK/Telegram discovery and contact chain (~5-8 min)
- Rejection tests: <1s each
- Total test run time: ~63 minutes for 60 cycles (3 parallel batches)

## Recommendations

1. **Deploy pipeline fix** (`a2046d3`) to eliminate "futures unfinished" failures
2. Consider increasing `as_completed` timeout from 120s to 180s for heavy-load scenarios
3. Consider sticky sessions or shared task storage for multi-worker deployments to improve progress polling reliability
