# INFRASTRUCTURE AUDIT REPORT
**Generated:** 2026-05-14 03:20 UTC
**Project:** IBP (shtirletzsled.ru)

---

## HEALTH SCORE: 75/100 -- GOOD
> Minor issues found

| Severity | Count | Points Deducted (capped) |
|----------|-------|--------------------------|
| CRITICAL | 1 | 25 |
| HIGH | 0 | 0 |
| MEDIUM | 0 | 0 |
| LOW | 1 | 0 |
| **TOTAL** | **2** | **25** |

---

## CRITICAL ISSUES (1)
*These MUST be fixed immediately -- they cause crashes or data loss*

### [EXTERNAL_SERVICES] Production Server
**Issue:** Production /health probe failed: read_timeout after 10730ms

**Fix:** TCP/TLS and the front door respond, but /health does not finish. This points to a stale deploy with a blocking health route, a saturated app worker, or an upstream route-specific hang. No SSH required: run `curl.exe -v --connect-timeout 3 --max-time 15 https://shtirletzsled.ru/health`, `curl.exe -v --connect-timeout 3 --max-time 15 https://shtirletzsled.ru/ready`, and compare with `curl.exe -I --connect-timeout 3 --max-time 15 https://shtirletzsled.ru/`. If / redirects or returns headers while /health times out, redeploy code containing the dependency-free public health route and restart the web service from the provider panel. If /health passes but /ready returns 503, focus on DB credentials, migrations, connection limits, and local data files. If both time out, check provider status, DNS, firewall, and nginx/load balancer health. When SSH is available, verify `curl -sf http://localhost:5000/health` inside the host/container plus `curl -sf http://localhost:5000/ready`, then inspect `docker compose logs --tail=100` or `journalctl -u ibp -n 100`.

---

## HIGH PRIORITY (0)
*Fix these soon -- they cause freezes, errors, or data quality issues*

## MEDIUM PRIORITY (0)
*Address in next development cycle*

## LOW PRIORITY (1)
*Nice to have improvements*

- OpenSanctions: OpenSanctions API key not configured; remote sanctions screening is in degraded mode

---

## FINDINGS BY AGENT

| Agent | Critical | High | Medium | Low | Total |
|-------|----------|------|--------|-----|-------|
| EXTERNAL_SERVICES | 1 | 0 | 0 | 1 | 2 |

---

## ACTION PLAN

### Immediate (fix today):
1. **Production Server**: TCP/TLS and the front door respond, but /health does not finish. This points to a stale deploy with a blocking health route, a saturated app worker, or an upstream route-specific hang. No SSH required: run `curl.exe -v --connect-timeout 3 --max-time 15 https://shtirletzsled.ru/health`, `curl.exe -v --connect-timeout 3 --max-time 15 https://shtirletzsled.ru/ready`, and compare with `curl.exe -I --connect-timeout 3 --max-time 15 https://shtirletzsled.ru/`. If / redirects or returns headers while /health times out, redeploy code containing the dependency-free public health route and restart the web service from the provider panel. If /health passes but /ready returns 503, focus on DB credentials, migrations, connection limits, and local data files. If both time out, check provider status, DNS, firewall, and nginx/load balancer health. When SSH is available, verify `curl -sf http://localhost:5000/health` inside the host/container plus `curl -sf http://localhost:5000/ready`, then inspect `docker compose logs --tail=100` or `journalctl -u ibp -n 100`.

### This week:

---

## HOW TO RE-RUN THIS AUDIT
```bash
cd C:\Users\fedor\ibp
python scripts/audit/run_full_audit.py
```

Report will be regenerated at: `scripts/audit/INFRASTRUCTURE_REPORT.md`
