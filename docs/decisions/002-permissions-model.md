# 002 — Permissions Model

**Date:** 2026-05-23
**Status:** Decided

## What we chose

All access decisions go through `app/permissions.py`. No scattered `if user.role == 'admin'`
checks in route handlers. Templates may hide/show navigation, but route access is enforced
server-side.

Current model (two roles):

```python
# app/permissions.py

def is_admin(user) -> bool: ...
def can_access_check(user, check) -> bool: ...
```

Route decorators (`@login_required`, `@admin_required`) remain in `app/routes/auth.py`
but delegate their logic to `permissions.py`.

Current role rules:
- `admin` — Fedor/admin access; can see the Users list, open a selected user's investigations, and access/delete any check
- `user`  — sees only their own checks, subject to free-tier limits

## Why

Before this change, permission logic was duplicated in three places:
- `_RU_COUNTRIES` check in `auth.py` (unrelated, but same pattern of scattered config)
- `admin_required` decorator in `auth.py`
- `_check_owner_or_admin()` inline helper in `candidate_check.py`

As IBP gains org-level access (B2B teams), more roles, or per-check sharing,
having one module to change is essential. Scattered checks turn into audit failures.

## Tradeoff accepted

The current model is intentionally simple (two roles, ownership by user_id).
It is not a full RBAC/ABAC system. When IBP adds org-level membership or
check-sharing between teammates, `permissions.py` is the one file to extend.

## Rule going forward

- Any new route that gates on role or ownership calls a function from `permissions.py`.
- New permission rules are added to `permissions.py` first, then called from routes.
- Never add `if user.role == '...'` directly inside a route handler.
