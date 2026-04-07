# E2E FIX PLAN

## Root Cause Analysis

All 5 failures stem from **2 root causes**, not 11 independent issues.

---

## BUG 1 (CRITICAL): Pipeline hangs at 82% — Telegram public message search blocks indefinitely

**Impact**: ALL pipelines stuck at Stage 6 (behavioral). Stages 7 (risk scoring) and 8 (report) never execute. This is why every candidate has risk_score=0.

**Root Cause**: `search_telegram_public_messages()` in `app/services/candidate/behavioral_analysis.py:654` creates a new `TelegramClient` per call with `asyncio.new_event_loop()`. When 8+ pipelines run concurrently, multiple Telethon clients all try to connect using the same session file (`tg_session/ibp_session.session`). The `client.connect()` call on line 715 has NO timeout — it blocks indefinitely waiting for the session lock.

The `asyncio.wait_for(..., timeout=30)` on line 733 only wraps the `SearchGlobalRequest`, not the `connect()`. So if `connect()` hangs, the 30s timeout never fires.

**File**: `app/services/candidate/behavioral_analysis.py`

**Fix**:
```python
# Line ~709-715: Wrap the entire async function in a timeout
async def _search_global():
    from telethon import TelegramClient
    from telethon.tl.functions.messages import SearchGlobalRequest
    from telethon.tl.types import InputMessagesFilterEmpty

    client = TelegramClient(session_path, int(api_id), api_hash)
    # Add timeout to connect() — this is where the hang occurs
    try:
        await asyncio.wait_for(client.connect(), timeout=10)
    except asyncio.TimeoutError:
        logger.warning("Telegram public search: connect timed out after 10s")
        return empty_result
    ...

# Line ~778-783: Add overall timeout to the entire operation
try:
    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(
            asyncio.wait_for(_search_global(), timeout=45)  # Overall 45s cap
        )
    finally:
        loop.close()
    return result
```

**Affected candidates**: ALL (01-10). This single fix would let pipelines complete to Stage 8.

**Cascading fixes**:
- risk_score failures for candidates 01, 02, 03, 08 (all would get scores once Stage 7 runs)
- geo_intelligence, geo_analysis, text_analysis, activity_timeline (all from Stage 6 after the hang point)

---

## BUG 2 (KNOWN): FSSP records not found — CAPTCHA blocking

**Impact**: Candidates 03 (Шаламов) and 08 (Волков) have known FSSP debts but FSSP returns empty.

**Root Cause**: Already documented in CLAUDE.md Known Issue #13: "FSSP CAPTCHA-blocked: All automated strategies (API, AJAX, Playwright) blocked by CAPTCHA." The checko.ru fallback works for basic searches but may not return all records.

**File**: `app/services/candidate/fssp_service.py`, `app/services/phase3/checko_service.py`

**Fix options**:
1. Obtain `FSSP_API_TOKEN` from https://api-ip.fssp.gov.ru (requires Russian IP)
2. Use Russian proxy/VPN for FSSP Playwright scraping
3. Add more FSSP data aggregators (e.g., dolgi.ru, pristavy.ru)

**Status**: Known limitation, not a new bug. Low priority unless Russian IP becomes available.

---

## BUG 3 (MEDIUM): Server concurrent check limit hit when running sequential tests

**Impact**: Candidate 07 (Фомичев) never started — "Слишком много активных проверок"

**Root Cause**: The server enforces max 10 concurrent checks (`candidate_check.py:257`). Because Bug 1 causes pipelines to hang indefinitely, they never complete and never free up slots. After 6-8 stuck pipelines, new starts are rejected.

**File**: `app/routes/candidate_check.py:255-258`

**Fix**: This is a symptom of Bug 1. Once pipelines complete properly (after Bug 1 fix), slots free up naturally. Additionally, the `cleanup_old_tasks()` function should forcibly complete tasks that have been running for >30 minutes:

```python
# In cleanup_old_tasks():
for tid, task in list(tasks.items()):
    elapsed = (datetime.now() - task.started_at).total_seconds()
    if elapsed > 1800 and not task.completed_at:  # 30 min hard limit
        task.error = "Pipeline timed out after 30 minutes"
        task.completed_at = datetime.now()
```

---

## NOT A BUG: Candidate 09 (Калмыков) — INN required rejection

INN is required by design. The API correctly returns 400 "ИНН обязателен". The test correctly classifies this as PASS.

---

## NOT A BUG: ЧВК Вагнер flag not found for Волков

The system finds 31 court records and murder evidence for Волков. The ЧВК Вагнер association is from external HR intelligence, not from any public registry that the system searches. Once risk scoring runs (after Bug 1 fix), the murder conviction alone should produce a CRITICAL risk score.

---

## PRIORITY ORDER

| # | Bug | Severity | Effort | Fixes |
|---|-----|----------|--------|-------|
| 1 | Telegram connect() timeout | CRITICAL | 15 min | ALL risk_score failures, pipeline hangs, concurrent limit |
| 2 | FSSP CAPTCHA | KNOWN | N/A | FSSP data gaps (needs Russian IP) |
| 3 | Stale task cleanup | LOW | 10 min | Prevents concurrent limit from orphaned tasks |

**Fixing Bug 1 alone resolves 9 of 11 reported failures.**
