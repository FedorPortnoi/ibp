# Real Candidate Pipeline Test Report

**Date:** 2026-03-18
**Server:** https://shtirletzsled.ru (194.67.99.107, Moscow)
**Pipeline version:** commit f36d187 (main)

## Summary

| # | Candidate | INN | Status | Duration | Risk | Sources |
|---|-----------|-----|--------|----------|------|---------|
| 1 | Судин Артем Алексеевич | 232308435186 | COMPLETE | 527s (8.8m) | LOW | 16 |
| 2 | Стасюк Сергей Анатольевич | 233500829075 | COMPLETE | 535s (8.9m) | LOW | 16 |
| 3 | Таячкова Марина Вячеславовна | 233501519037 | COMPLETE | 502s (8.4m) | LOW | 16 |
| 4 | Калмыков Александр Николаевич | (none) | REJECTED | 2s | N/A | 0 |
| 5 | Левченко Надежда Александровна | 233506450100 | COMPLETE | 566s (9.4m) | LOW | 16 |

- **4/5 completed**, 1 rejected (no INN — expected behavior)
- **Average pipeline time: ~533s (8.9 minutes)**
- All returned **LOW RISK** with 0 red flags

---

## Stage-by-Stage Analysis

### Stage 0: Identity Confirmation (INN lookup) — WORKING

| Candidate | INN Status | Confirmed Name |
|-----------|-----------|----------------|
| Судин А.А. | Confirmed via EGRUL | Судин Артем Алексеевич |
| Стасюк С.А. | Confirmed via EGRUL | (extracted from EGRUL) |
| Таячкова М.В. | Confirmed via EGRUL | (extracted from EGRUL) |
| Левченко Н.А. | Confirmed via EGRUL | (extracted from EGRUL) |

**Verdict: REAL DATA.** INN→EGRUL lookup works on the Moscow server (nalog.ru is accessible).

### Stage 1: Government Registries — PARTIALLY WORKING

#### EGRUL Business Records — WORKING (with noise)
| Candidate | Records | Data Quality |
|-----------|---------|-------------|
| Судин А.А. | 20 | Found actual candidate (ИП СУДИН АРТЁМ АЛЕКСЕЕВИЧ, ИНН 232308435186) + 19 surname matches |
| Стасюк С.А. | 19 | Found surname matches (Стасюк Александр, Игорь, Станислав — not Сергей himself) |
| Таячкова М.В. | 20 | Found surname matches (Таячкова Галина, Маврина Марина) |
| Левченко Н.А. | 19 | Found exact match (ИП Левченко Надежда Александровна) + surname matches |

**Verdict: REAL DATA** from nalog.ru/Rusprofile. The Stage 1 name-based EGRUL search returns up to 20 surname matches — this is expected behavior (broader net). 2/4 candidates had exact EGRUL matches.

#### Court Records (sudact.ru) — NOT WORKING
All 4 candidates returned **0 court records**. Судин was known to have a 2015 admin violation — this was NOT found.

**Likely cause:** sudact.ru Playwright scraping may be failing on the server (no browser headless display, timeouts, or CAPTCHA).

#### FSSP (checko.ru) — NOT WORKING
All 4 returned **0 enforcement records**.

**Likely cause:** checko.ru may be blocking the server IP or the search parameters aren't matching.

#### Bankruptcy (EFRSB) — NOT WORKING
The dossier shows "Автоматическая проверка недоступна" with a manual verification link. The EFRSB scraper needs Russian IP and may be timing out.

### Stage 2: Security Checks — PARTIALLY WORKING

| Source | Status | Notes |
|--------|--------|-------|
| OpenSanctions | **WORKING** | All candidates: "Not found" (correct) |
| Interpol | **WORKING** | All candidates: "Not found" (correct) |
| MVD Wanted | **NOT WORKING** | "Локальная база МВД не загружена" |
| Extremist List | **NOT WORKING** | "Локальная база экстремистов не загружена" |
| Rosfinmonitoring | **NOT WORKING** | "Сайт недоступен (возможна геоблокировка)" |
| MVD Розыск | **WORKING** | "Not found" (likely scraper, not local DB) |

**Action needed:**
- Load local security databases on server: `python scripts/update_mvd_list.py` and `python scripts/update_extremist_list.py`
- Rosfinmonitoring requires Russian IP (server is in Moscow, so this may be a firewall/network issue)

### Stage 3: Social Media Discovery — NOT WORKING

All 4 candidates returned **0 social profiles**. This is the most significant failure.

**VK Search:** Despite `VK_SERVICE_TOKEN` being set, no VK profiles were found. Possible causes:
- VK API rate limiting or token expiry
- VK search returning profiles but DOB/name filtering rejecting all
- Server-side error in VK API calls (timeout, network)

**Telegram:** No profiles found. The Telethon session may not be authenticated on the server.

**OK.ru:** No profiles found (likely no `OK_SESSION_TOKEN` set on server → demo mode → empty).

### Stage 4: Contact Discovery — NOT WORKING

All 4 returned **0 phones, 0 emails**. The 11-step contact chain depends heavily on Stage 3 results (VK profiles → extract contacts). With no social profiles discovered, most contact extraction steps have nothing to work with.

### Stage 5: Deep Social Analysis — NOT WORKING

No face matches, username accounts, or social graph data. Depends on Stage 3 results.

### Stage 6: Behavioral Intelligence — MINIMAL

The stage completed ("Поведенческий анализ завершён") but with no social media data to analyze, it produced no meaningful output.

### Stage 7: Risk Scoring — WORKING (but understated)

All candidates scored **LOW RISK** with 0 red flags. This is because:
- No court records found (would have flagged Судин's violation)
- No FSSP records found
- No sanctions hits
- No social media data to analyze

The risk scorer works correctly given its inputs — but the inputs are incomplete.

### Stage 8: Report Generation — PARTIALLY WORKING

- HTML dossier pages render correctly (200 OK, ~61-63KB each)
- **JSON export returns 502 Bad Gateway** for all candidates
- PDF export not tested

---

## Critical Bugs Found

### 1. JSON Export 502 (BLOCKING)
**Route:** `GET /candidate/export/<check_id>/json`
**Symptom:** nginx returns 502 Bad Gateway for all completed checks
**Impact:** Cannot programmatically access dossier data; limits automation and API usage
**Likely cause:** Gunicorn worker crashes during JSON serialization — possibly due to large response, Cyrillic filename in Content-Disposition, or unhandled exception in model property access

### 2. Social Media Discovery Returns 0 Profiles (MAJOR)
**Impact:** Stages 3-6 produce no data. This cascades to empty contacts, no behavioral analysis.
**Investigation needed:**
- Check VK_SERVICE_TOKEN validity on server
- Check Telethon session status on server
- Review VK API response logs for errors/rate limits
- Test VK search manually: `https://api.vk.com/method/users.search?q=Судин+Артем&v=5.199&access_token=...`

### 3. Court Search Returns 0 Records (MAJOR)
**Impact:** Known violations not detected (Судин's 2015 case)
**Investigation needed:**
- sudact.ru Playwright scraper may be failing silently
- Check if Playwright/Chromium is installed on server
- Review server logs for sudact.ru scraping errors

### 4. Local Security Databases Not Loaded (MODERATE)
**Impact:** MVD wanted list and extremist list checks skipped
**Fix:** Run on server:
```bash
python scripts/update_mvd_list.py
python scripts/update_extremist_list.py
```

### 5. FSSP/Bankruptcy Not Working (MODERATE)
**Impact:** Enforcement proceedings and bankruptcy not checked
**Cause:** checko.ru may be blocking, EFRSB needs Russian IP access

---

## What's REAL vs DEMO vs EMPTY

| Stage | Data Source | Status | Data Type |
|-------|-----------|--------|-----------|
| 0 | INN → EGRUL | **WORKING** | REAL |
| 1 | EGRUL by name | **WORKING** | REAL (noisy) |
| 1 | sudact.ru courts | **BROKEN** | EMPTY |
| 1 | checko.ru FSSP | **BROKEN** | EMPTY |
| 1 | EFRSB bankruptcy | **BROKEN** | EMPTY |
| 2 | OpenSanctions | **WORKING** | REAL |
| 2 | Interpol | **WORKING** | REAL |
| 2 | MVD/Extremist local | **NOT LOADED** | EMPTY |
| 2 | Rosfinmonitoring | **GEO-BLOCKED** | EMPTY |
| 3 | VK Search | **BROKEN** | EMPTY |
| 3 | Telegram | **BROKEN** | EMPTY |
| 3 | OK.ru | **NOT CONFIGURED** | EMPTY |
| 4 | Contact chain | **NO INPUT** | EMPTY |
| 5 | Face/Username/Graph | **NO INPUT** | EMPTY |
| 6 | Text/Geo/Timeline | **NO INPUT** | EMPTY |
| 7 | Risk scoring | **WORKING** | REAL (underreported) |
| 8 | HTML report | **WORKING** | REAL |
| 8 | JSON export | **502 BUG** | BROKEN |

**Working stages: 0, 1 (EGRUL only), 2 (OpenSanctions + Interpol), 7, 8 (HTML only)**
**Broken/empty: 1 (courts, FSSP, bankruptcy), 2 (local DBs), 3-6 (all), 8 (JSON)**

---

## Known Red Flags vs Found Red Flags

| Candidate | Known Issue | Found by Pipeline? |
|-----------|-----------|-------------------|
| Судин А.А. | 2015 admin arrest (fleeing car accident, ч.2 ст.12.27 КоАП) | **NO** — court search broken |
| Таячкова М.В. | Admin responsibility for refusing medical exam | **NO** — court search broken |
| Стасюк С.А. | HR says clean | Consistent (LOW, 0 flags) |
| Левченко Н.А. | HR says clean | Consistent (LOW, 0 flags) |

---

## Performance

| Metric | Value |
|--------|-------|
| Average pipeline time | 533s (8.9 min) |
| Fastest | 502s (Таячкова) |
| Slowest | 566s (Левченко) |
| Sources checked | 16 per candidate |
| Bottleneck stage | Stage 3 Social (~5 min each) |
| Server response | Stable, no crashes during pipeline |

---

## Priority Fixes

1. **P0 — Fix JSON export 502**: Add error handling/try-catch in export_json route, check gunicorn worker logs
2. **P0 — Fix VK search**: Verify VK_SERVICE_TOKEN works, check API responses, review DOB filtering
3. **P1 — Fix court search**: Check Playwright installation on server, debug sudact.ru scraper
4. **P1 — Load security DBs**: Run update scripts for MVD and extremist lists
5. **P2 — Fix FSSP/bankruptcy**: Debug checko.ru scraper, EFRSB access
6. **P2 — Configure Telegram**: Verify Telethon session on server
7. **P3 — Configure OK.ru**: Set OK_SESSION_TOKEN if available

---

## Check IDs for Manual Verification

| Candidate | check_id |
|-----------|----------|
| Судин А.А. | 5ae05b82077d420d8b757c3593b4df8a |
| Стасюк С.А. | 238e66092c3e431db358225856028411 |
| Таячкова М.В. | 6876e32c043e487881b70d7178a4710a |
| Левченко Н.А. | 55cbe38ce78d4266a9242a8158bd2a6f |

Dossier URLs: `https://shtirletzsled.ru/candidate/dossier/<check_id>`
