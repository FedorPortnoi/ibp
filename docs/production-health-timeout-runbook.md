# Production Health Timeout Runbook

## Scope

Use this when `https://shtirletzsled.ru/health` times out from a local audit or uptime check and SSH access is not guaranteed.

The public `/health` endpoint is intended to be a cheap liveness check. It must not call the database or external APIs for unauthenticated requests. Use public `/ready` for deploy readiness; it checks the database and local data files, but it must not call external APIs. Detailed service diagnostics are reserved for authenticated browser sessions.

## No-SSH Triage

Run these from a local terminal:

```powershell
curl.exe -v --connect-timeout 3 --max-time 15 https://shtirletzsled.ru/health
curl.exe -v --connect-timeout 3 --max-time 15 https://shtirletzsled.ru/ready
curl.exe -I --connect-timeout 3 --max-time 15 https://shtirletzsled.ru/
Resolve-DnsName shtirletzsled.ru
Test-NetConnection shtirletzsled.ru -Port 443
```

Interpretation:

- `/` returns headers or redirects, but `/health` read-times-out: the front door is reachable and the Flask health route or app worker is likely blocked. Redeploy the version where unauthenticated `/health` returns `{"status":"ok"}` before DB/external probes, then restart the web service from the provider panel.
- `/health` passes but `/ready` returns 503: the process is alive, but the database readiness probe failed. Inspect database credentials, migrations, connection limits, and app worker logs.
- `/ready` returns 200 with missing local data flags: the process and DB are ready, but offline security list refresh needs attention.
- Both `/` and `/health` read-timeout: the reverse proxy can accept connections but the upstream may be hung or saturated. Restart from the provider panel and inspect provider deploy/runtime logs.
- DNS or TCP fails: treat it as provider, DNS, firewall, load balancer, or host availability before debugging Flask code.
- HTTP 502/504: nginx or the provider proxy cannot get a timely upstream response. Restart the web service and inspect upstream logs when access is available.

## With SSH Or Console Access

```bash
curl -sf http://localhost:5000/health
curl -sf http://localhost:5000/ready
docker compose ps
docker compose logs --tail=100
journalctl -u ibp -n 100 --no-pager
```

Expected public health response:

```json
{"status":"ok"}
```

Expected public readiness response:

```json
{"database":true,"local_data":{"extremist_list":true,"mvd_wanted":true},"status":"ok"}
```

If local container health passes but public health fails, focus on nginx/proxy routing, TLS termination, firewall rules, and provider network status.

## Audit

Run the focused external-services audit:

```powershell
cd C:\Users\fedor\ibp
python scripts\audit\agent7_external_services.py
```

Agent 7 records both `/health` and `/` probe diagnostics in `scripts/audit/agent7_results.json` so the report distinguishes route-specific hangs from front-door or network failures.
