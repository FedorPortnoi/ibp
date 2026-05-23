"""
Audit Log Model
===============
Records who did what and when. Required for B2B accountability and 152-FZ compliance.
One row per significant user action. Never deleted — append-only.
"""

import json
from datetime import datetime
from app import db


class AuditLog(db.Model):
    __tablename__ = 'audit_log'

    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Who
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'),
                        nullable=True, index=True)
    ip_address = db.Column(db.String(45), nullable=True)  # 45 chars covers IPv6

    # What
    action = db.Column(db.String(64), nullable=False, index=True)
    outcome = db.Column(db.String(16), nullable=False, default='success')  # success/failure/denied

    # On what
    target_type = db.Column(db.String(64), nullable=True)
    target_id = db.Column(db.String(36), nullable=True)

    # Extra context (JSON) — named 'extra' to avoid shadowing SQLAlchemy's metadata attribute
    _extra = db.Column('metadata', db.Text, nullable=True)

    @property
    def extra(self):
        if not self._extra:
            return {}
        try:
            return json.loads(self._extra)
        except (json.JSONDecodeError, TypeError):
            return {}

    @extra.setter
    def extra(self, value):
        self._extra = json.dumps(value, ensure_ascii=False, default=str) if value else None

    def __repr__(self):
        return f'<AuditLog {self.id}: {self.action} by user={self.user_id} [{self.outcome}]>'
