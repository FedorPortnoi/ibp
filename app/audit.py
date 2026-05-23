"""
Audit service for IBP.

Write an audit log entry for any significant user action. This is the only
place that writes to the audit_log table.

Design rules:
- Never raises. A failed audit write logs a warning but never blocks the request.
- Called from request context when available; ip_address falls back to None otherwise.
- All writes are synchronous — audit inserts are fast single-row writes.

Canonical action names:
  auth.login          — successful login
  auth.login_failed   — wrong credentials
  auth.logout         — user logged out
  check.start         — pipeline started
  check.delete        — check record deleted
  check.export_pdf    — PDF exported
  check.export_json   — JSON exported
  subscription.activate — subscription activated (stub or real)

See docs/decisions/004-audit-log.md.
"""

import logging
from typing import Any

logger = logging.getLogger('ibp.audit')


def log(
    action: str,
    *,
    outcome: str = 'success',
    user_id: int | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    ip_address: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Write one audit log entry. Never raises."""
    try:
        from flask import has_request_context, request as flask_request
        from app import db
        from app.models.audit_log import AuditLog

        ip = ip_address
        if ip is None and has_request_context():
            ip = flask_request.remote_addr

        entry = AuditLog(
            action=action,
            outcome=outcome,
            user_id=user_id,
            target_type=target_type,
            target_id=target_id,
            ip_address=ip,
        )
        if metadata:
            entry.extra = metadata

        db.session.add(entry)
        db.session.commit()

    except Exception as exc:
        logger.warning(f"Audit write failed for action={action!r}: {exc}")
