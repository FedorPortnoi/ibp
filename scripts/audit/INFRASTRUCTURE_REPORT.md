# INFRASTRUCTURE AUDIT REPORT
**Generated:** 2026-04-05 05:33 UTC
**Project:** IBP (shtirletzsled.ru)

---

## HEALTH SCORE: 89/100 -- GOOD
> Minor issues found

| Severity | Count | Points Deducted (capped) |
|----------|-------|--------------------------|
| CRITICAL | 0 | 0 |
| HIGH | 0 | 0 |
| MEDIUM | 53 | 10 |
| LOW | 13 | 1 |
| **TOTAL** | **66** | **11** |

---

## CRITICAL ISSUES (0)
*These MUST be fixed immediately -- they cause crashes or data loss*

## HIGH PRIORITY (0)
*Fix these soon -- they cause freezes, errors, or data quality issues*

## MEDIUM PRIORITY (53)
*Address in next development cycle*

- **\app\routes\main.py:62** -- Silent optional import -- failure hidden by try/except pass
  *Fix: Log a warning when optional import fails so it's visible*

- **\app\services\candidate\bankruptcy_service.py:26** -- Silent optional import -- failure hidden by try/except pass
  *Fix: Log a warning when optional import fails so it's visible*

- **\app\services\candidate\fssp_service.py:33** -- Silent optional import -- failure hidden by try/except pass
  *Fix: Log a warning when optional import fails so it's visible*

- **\app\services\phase1\buratino_vk_search.py:323** -- Silent optional import -- failure hidden by try/except pass
  *Fix: Log a warning when optional import fails so it's visible*

- **\app\services\phase1\telegram_discovery.py:665** -- Silent optional import -- failure hidden by try/except pass
  *Fix: Log a warning when optional import fails so it's visible*

- **\app\services\phase1\telegram_discovery.py:790** -- Silent optional import -- failure hidden by try/except pass
  *Fix: Log a warning when optional import fails so it's visible*

- **\app\services\phase1\vk_web_search.py:169** -- Silent optional import -- failure hidden by try/except pass
  *Fix: Log a warning when optional import fails so it's visible*

- **\app\services\phase2\forgot_password_oracle.py:1023** -- Silent optional import -- failure hidden by try/except pass
  *Fix: Log a warning when optional import fails so it's visible*

- **\app\services\phase2\telegram_crossref.py:419** -- Silent optional import -- failure hidden by try/except pass
  *Fix: Log a warning when optional import fails so it's visible*

- **\app\services\phase2\telegram_crossref.py:436** -- Silent optional import -- failure hidden by try/except pass
  *Fix: Log a warning when optional import fails so it's visible*

- **\app\services\phase3\court_search.py:113** -- Silent optional import -- failure hidden by try/except pass
  *Fix: Log a warning when optional import fails so it's visible*

- **\candidate_check\app\models\business_record.py:196** -- Silent optional import -- failure hidden by try/except pass
  *Fix: Log a warning when optional import fails so it's visible*

- **\candidate_check\app\routes\main.py:62** -- Silent optional import -- failure hidden by try/except pass
  *Fix: Log a warning when optional import fails so it's visible*

- **\candidate_check\app\services\candidate\bankruptcy_service.py:26** -- Silent optional import -- failure hidden by try/except pass
  *Fix: Log a warning when optional import fails so it's visible*

- **\candidate_check\app\services\candidate\fssp_service.py:33** -- Silent optional import -- failure hidden by try/except pass
  *Fix: Log a warning when optional import fails so it's visible*

- **\candidate_check\app\services\candidate\pipeline.py:260** -- Silent optional import -- failure hidden by try/except pass
  *Fix: Log a warning when optional import fails so it's visible*

- **\candidate_check\app\services\phase1\buratino_vk_search.py:323** -- Silent optional import -- failure hidden by try/except pass
  *Fix: Log a warning when optional import fails so it's visible*

- **\candidate_check\app\services\phase1\telegram_discovery.py:633** -- Silent optional import -- failure hidden by try/except pass
  *Fix: Log a warning when optional import fails so it's visible*

- **\candidate_check\app\services\phase1\telegram_discovery.py:758** -- Silent optional import -- failure hidden by try/except pass
  *Fix: Log a warning when optional import fails so it's visible*

- **\candidate_check\app\services\phase1\vk_web_search.py:149** -- Silent optional import -- failure hidden by try/except pass
  *Fix: Log a warning when optional import fails so it's visible*

- **\candidate_check\app\services\phase2\forgot_password_oracle.py:1023** -- Silent optional import -- failure hidden by try/except pass
  *Fix: Log a warning when optional import fails so it's visible*

- **\candidate_check\app\services\phase2\telegram_crossref.py:412** -- Silent optional import -- failure hidden by try/except pass
  *Fix: Log a warning when optional import fails so it's visible*

- **\candidate_check\app\services\phase2\telegram_crossref.py:429** -- Silent optional import -- failure hidden by try/except pass
  *Fix: Log a warning when optional import fails so it's visible*

- **\candidate_check\app\services\phase3\court_search.py:32** -- Silent optional import -- failure hidden by try/except pass
  *Fix: Log a warning when optional import fails so it's visible*

- **\people_search\app\services\telegram_crossref.py:412** -- Silent optional import -- failure hidden by try/except pass
  *Fix: Log a warning when optional import fails so it's visible*

- **\people_search\app\services\telegram_crossref.py:429** -- Silent optional import -- failure hidden by try/except pass
  *Fix: Log a warning when optional import fails so it's visible*

- **\people_search\app\services\telegram_search.py:633** -- Silent optional import -- failure hidden by try/except pass
  *Fix: Log a warning when optional import fails so it's visible*

- **\people_search\app\services\telegram_search.py:758** -- Silent optional import -- failure hidden by try/except pass
  *Fix: Log a warning when optional import fails so it's visible*

- **\people_search\app\services\vk_search.py:323** -- Silent optional import -- failure hidden by try/except pass
  *Fix: Log a warning when optional import fails so it's visible*

- **\people_search\app\services\vk_web_search.py:149** -- Silent optional import -- failure hidden by try/except pass
  *Fix: Log a warning when optional import fails so it's visible*

- **\app\services\candidate\pipeline.py:1538** -- Function '_run_contact_discovery' has no explicit timeout protection
  *Fix: Consider adding timeout for long-running operations*

- **\app\routes\connections.py:20** -- Database query with .all() and no .limit() or filter
  *Fix: Add .limit(1000) to prevent large result sets*

- **\app\services\phase2\marketplace_scanner.py:311** -- Database query with .all() and no .limit() or filter
  *Fix: Add .limit(1000) to prevent large result sets*

- **\app\services\candidate\contact_discovery.py:181** -- ThreadPoolExecutor not used as context manager
  *Fix: Use 'with ThreadPoolExecutor() as executor:' to ensure cleanup*

- **\app\services\candidate\contact_discovery.py:209** -- ThreadPoolExecutor not used as context manager
  *Fix: Use 'with ThreadPoolExecutor() as executor:' to ensure cleanup*

- **\app\services\candidate\pipeline.py:466** -- ThreadPoolExecutor not used as context manager
  *Fix: Use 'with ThreadPoolExecutor() as executor:' to ensure cleanup*

- **\app\services\candidate\pipeline.py:569** -- ThreadPoolExecutor not used as context manager
  *Fix: Use 'with ThreadPoolExecutor() as executor:' to ensure cleanup*

- **\app\services\candidate\pipeline.py:646** -- ThreadPoolExecutor not used as context manager
  *Fix: Use 'with ThreadPoolExecutor() as executor:' to ensure cleanup*

- **\app\services\candidate\pipeline.py:829** -- ThreadPoolExecutor not used as context manager
  *Fix: Use 'with ThreadPoolExecutor() as executor:' to ensure cleanup*

- **\app\services\candidate\pipeline.py:1191** -- ThreadPoolExecutor not used as context manager
  *Fix: Use 'with ThreadPoolExecutor() as executor:' to ensure cleanup*

- **\app\services\candidate\pipeline.py:1545** -- ThreadPoolExecutor not used as context manager
  *Fix: Use 'with ThreadPoolExecutor() as executor:' to ensure cleanup*

- **\app\services\candidate\pipeline.py:1706** -- ThreadPoolExecutor not used as context manager
  *Fix: Use 'with ThreadPoolExecutor() as executor:' to ensure cleanup*

- **\app\services\phase2\email_discovery.py:90** -- ThreadPoolExecutor not used as context manager
  *Fix: Use 'with ThreadPoolExecutor() as executor:' to ensure cleanup*

- **\app\services\phase2\email_discovery.py:909** -- ThreadPoolExecutor not used as context manager
  *Fix: Use 'with ThreadPoolExecutor() as executor:' to ensure cleanup*

- **\app\services\phase2\phone_discovery.py:86** -- ThreadPoolExecutor not used as context manager
  *Fix: Use 'with ThreadPoolExecutor() as executor:' to ensure cleanup*

- **EGRUL** -- EGRUL returned HTTP 404
  *Fix: EGRUL may be blocking requests -- check IP/headers*

- **OpenSanctions** -- OpenSanctions returned HTTP 401
  *Fix: Sanctions check may not work*

- **\app\routes\candidate_check.py:636** -- Potentially blocking operation in route: resp = http_requests.post(
  *Fix: Move heavy operations to background thread*

- **\app\routes\candidate_check.py:652** -- Potentially blocking operation in route: resp = http_requests.post(
  *Fix: Move heavy operations to background thread*

- **\app\routes\main.py:42** -- Potentially blocking operation in route: result = subprocess.run(
  *Fix: Move heavy operations to background thread*

- **\app\routes\phase1.py:376** -- Potentially blocking operation in route: profile_r = http_requests.get('https://api.vk.com/method/use
  *Fix: Move heavy operations to background thread*

- **\app\routes\phase1.py:404** -- Potentially blocking operation in route: wall_r = http_requests.get('https://api.vk.com/method/wall.g
  *Fix: Move heavy operations to background thread*

- **\app\routes\phase2.py:1095** -- Potentially blocking operation in route: time.sleep(0.2)
  *Fix: Move heavy operations to background thread*

## LOW PRIORITY (13)
*Nice to have improvements*

- \app\services\candidate\pipeline.py: 'sanctions_svc' used without None check after assignment
- \app\services\candidate\pipeline.py: 'net_searcher' used without None check after assignment
- \app\services\candidate\pipeline.py: 'stage2_executor' used without None check after assignment
- \app\services\candidate\pipeline.py: 'searcher' used without None check after assignment
- \app\services\candidate\pipeline.py: 'casebook' used without None check after assignment
- \app\services\candidate\pipeline.py: 'svc' used without None check after assignment
- \app\services\candidate\pipeline.py: 'discovery' used without None check after assignment
- \app\services\candidate\pipeline.py: 'wave3_pool' used without None check after assignment
- \app\services\candidate\pipeline.py: 'phone_intel' used without None check after assignment
- \app\services\candidate\pipeline.py: 'contact_service' used without None check after assignment
- \app\services\candidate\pipeline.py: '_beh_pool' used without None check after assignment
- \app\services\candidate\pipeline.py: 'scorer' used without None check after assignment
- \app\models\investigation.py: Potentially large JSON serialization at line 153

---

## FINDINGS BY AGENT

| Agent | Critical | High | Medium | Low | Total |
|-------|----------|------|--------|-----|-------|
| ERROR_COVERAGE | 0 | 0 | 0 | 12 | 12 |
| EXTERNAL_SERVICES | 0 | 0 | 2 | 0 | 2 |
| IMPORT_CHAIN | 0 | 0 | 30 | 0 | 30 |
| PERFORMANCE | 0 | 0 | 6 | 1 | 7 |
| PIPELINE_FLOW | 0 | 0 | 1 | 0 | 1 |
| THREAD_SAFETY | 0 | 0 | 12 | 0 | 12 |
| TIMEOUT_SCANNER | 0 | 0 | 2 | 0 | 2 |

---

## ACTION PLAN

### Immediate (fix today):

### This week:

---

## HOW TO RE-RUN THIS AUDIT
```bash
cd C:\Users\fedor\ibp
python scripts/audit/run_full_audit.py
```

Report will be regenerated at: `scripts/audit/INFRASTRUCTURE_REPORT.md`
