"""
Subscription Model
==================
Monthly subscription with stub payment (YooKassa-ready).
Free tier: 2 checks per week without payment.
"""

from datetime import datetime, timedelta

from app import db

# Free tier limit — resets every Monday
FREE_CHECKS_PER_WEEK = 2


class Subscription(db.Model):
    __tablename__ = 'subscriptions'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'),
                        nullable=False, unique=True)
    status = db.Column(db.String(16), nullable=False, default='inactive')
    # 'active' | 'inactive' | 'expired'
    started_at = db.Column(db.DateTime, nullable=True)
    expires_at = db.Column(db.DateTime, nullable=True)
    auto_renew = db.Column(db.Boolean, default=False)
    payment_id = db.Column(db.String(128), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow,
                           onupdate=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('subscription',
                                                       uselist=False))

    @property
    def is_active(self) -> bool:
        if self.status != 'active':
            return False
        if self.expires_at and datetime.utcnow() > self.expires_at:
            return False
        return True

    @property
    def is_free_tier(self) -> bool:
        """User has no paid subscription (may have free checks remaining)."""
        return not self.is_active

    @property
    def days_left(self) -> int:
        if not self.expires_at:
            return 0
        delta = self.expires_at - datetime.utcnow()
        return max(0, delta.days)

    def free_checks_used_this_week(self) -> int:
        """Count checks started by this user in the current ISO week (Mon-Sun)."""
        from app.models.candidate_check import CandidateCheck
        now = datetime.utcnow()
        # Monday 00:00 of current week
        week_start = now - timedelta(days=now.weekday())
        week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
        return CandidateCheck.query.filter(
            CandidateCheck.user_id == self.user_id,
            CandidateCheck.created_at >= week_start,
        ).count()

    def free_checks_remaining(self) -> int:
        """How many free checks left this week (paid = unlimited)."""
        if self.is_active:
            return 999
        return max(0, FREE_CHECKS_PER_WEEK - self.free_checks_used_this_week())

    def can_run_check(self) -> bool:
        """Can this user start a new check right now?"""
        if self.is_active:
            return True
        return self.free_checks_remaining() > 0

    def activate(self, payment_id: str = 'stub', auto_renew: bool = False):
        self.status = 'active'
        self.started_at = datetime.utcnow()
        self.expires_at = datetime.utcnow() + timedelta(days=30)
        self.auto_renew = auto_renew
        self.payment_id = payment_id
        self.updated_at = datetime.utcnow()

    def __repr__(self):
        return f'<Subscription user={self.user_id} status={self.status} expires={self.expires_at}>'
