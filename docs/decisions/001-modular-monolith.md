# 001 — Modular Monolith Architecture

**Date:** 2026-05-23
**Status:** Decided

## What we chose

IBP is structured as a modular monolith: one deployable Flask app, one database,
one codebase — but split clearly by responsibility.

Natural module boundaries for IBP:

```
checks/          — 9-stage pipeline, CandidateCheck
subjects/        — people being investigated (future: richer entity)
users/           — auth, org membership
permissions/     — centralized role and ownership checks
billing/         — subscriptions, free tier limits
integrations/    — VK, Telegram, FSSP, OpenSanctions, AI
audit/           — consent log, check history (future)
reporting/       — PDF/JSON export, dossier assembly
market/          — Russia-first: INN, RUB, +7, 152-FZ
```

The basic flow in every feature area:

```
route handler
  -> service / domain logic
    -> database (SQLAlchemy)
```

Business rules live in services, not in route handlers or templates.

## Why

IBP is a single-product tool at pre-production scale. Microservices would add
deployment, networking, and debugging complexity with no benefit at this stage.

A modular monolith keeps deployment simple (one gunicorn process, one SQLite/Postgres)
while enforcing the discipline that prevents spaghetti code: each module owns its
own logic and does not casually reach into another module's internals.

## Tradeoff accepted

If IBP grows into multiple independent products (e.g., a checks API sold separately
from a HR-platform front-end), the monolith will need to be split. At that point,
the module boundaries already exist and the split is mechanical, not a rewrite.

## Rule going forward

- Extract to microservices only when there is a genuine operational reason
  (independent scaling, independent deployment cadence, different language/runtime).
- Extract a shared library only after the same pattern appears in three places.
- Delete dead modules aggressively; do not let abandoned ideas accumulate.
