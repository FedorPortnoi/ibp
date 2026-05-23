"""
Centralized permission checks for IBP.

All yes/no access decisions go through this module.
Routes import from here rather than scattering ad-hoc role checks in handlers.

Current roles:
  admin — sees all checks, unrestricted
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
    """Admin sees all checks; regular users see only their own."""
    return user is not None and (user.is_admin or check.user_id == user.id)
