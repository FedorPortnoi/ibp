"""
Centralized permission checks for IBP.

All yes/no access decisions go through this module.
Routes import from here rather than scattering ad-hoc role checks in handlers.

Current roles:
  admin — Fedor/admin role; can access any user's check via admin flows
  user  — sees only their own checks, subject to free-tier limits

See docs/decisions/002-permissions-model.md.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.candidate_check import CandidateCheck


def is_admin(user: User | None) -> bool:
    return user is not None and user.is_admin


def can_access_check(user: User | None, check: CandidateCheck) -> bool:
    """Admin may access any check; regular users may access only their own."""
    return user is not None and (user.is_admin or check.user_id == user.id)


def enforce_free_tier_limit(user) -> tuple[bool, object]:
    """Check whether a non-admin user is within their free-tier check quota.

    Uses BEGIN IMMEDIATE to serialise the read-then-write against SQLite so
    concurrent requests cannot both pass the guard (TOCTOU).

    Returns:
        (True, None)  — allowed; caller should proceed.
        (False, response) — limit exceeded; caller must return the response.
    """
    if not user or user.is_admin:
        return True, None

    from app import db
    from app.models.subscription import Subscription
    from flask import jsonify

    try:
        db.session.execute(db.text("BEGIN IMMEDIATE"))
    except Exception:
        db.session.rollback()

    _sub = Subscription.query.filter_by(user_id=user.id).first()
    if not _sub:
        _sub = Subscription(user_id=user.id, status='inactive')
        db.session.add(_sub)
        try:
            db.session.flush()
        except Exception:
            db.session.rollback()

    if not _sub.can_run_check():
        db.session.rollback()
        return False, (
            jsonify({'error': (
                'Лимит бесплатных проверок исчерпан (2 в неделю). '
                'Оформите подписку для безлимитного доступа.'
            )}),
            403,
        )

    return True, None
