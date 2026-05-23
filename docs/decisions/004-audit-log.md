# 004 — Audit Log

**Date:** 2026-05-23
**Status:** Decided

## What we chose

A dedicated `audit_log` table records every significant user action:

| Action | Trigger |
|---|---|
| `auth.login` | Successful login |
| `auth.login_failed` | Wrong credentials |
| `auth.logout` | Logout (future) |
| `check.start` | Pipeline started — logs full_name, INN, mode |
| `check.delete` | Check record deleted |
| `check.export_pdf` | PDF exported (future) |
| `check.export_json` | JSON exported (future) |
| `subscription.activate` | Subscription activated |

The write interface is a single function in `app/audit.py`:

```python
audit.log(action, user_id=..., target_type=..., target_id=..., metadata={...})
```

Design rules:
- Never raises — a failed audit write logs a warning but never blocks the request.
- Request context is used automatically to capture IP; falls back to None in
  background threads.
- Append-only — audit rows are never deleted or updated.

## Why

IBP is sold to B2B clients (HR departments, corporate security). They need to
show regulators and their own management who queried whom and when. This is not
optional under 152-FZ — processing personal data requires a clear audit trail
of who initiated each check.

Without a log, there is no answer to: "which of our employees ran a background
check on this candidate at 11pm on a Saturday?"

## Tradeoff accepted

The current log is simple: no retention policy, no viewer UI, no admin dashboard.
Rows accumulate indefinitely in the `audit_log` table. This is acceptable at
pre-production scale. When IBP has real B2B clients, add:
- Admin UI to browse and filter logs by user/action/date
- Retention policy (e.g., purge entries older than 2 years)
- Log export (CSV) for compliance reporting
