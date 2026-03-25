"""
Subscription Model
==================
Monthly subscription with stub payment (YooKassa-ready).
"""

from datetime import datetime, timedelta

from app import db


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
    amount = db.Column(db.Integer, default=1500)  # rub
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
    def days_left(self) -> int:
        if not self.expires_at:
            return 0
        delta = self.expires_at - datetime.utcnow()
        return max(0, delta.days)

    def activate(self, payment_id: str = 'stub', auto_renew: bool = False):
        self.status = 'active'
        self.started_at = datetime.utcnow()
        self.expires_at = datetime.utcnow() + timedelta(days=30)
        self.auto_renew = auto_renew
        self.payment_id = payment_id
        self.updated_at = datetime.utcnow()

    def __repr__(self):
        return f'<Subscription user={self.user_id} status={self.status} expires={self.expires_at}>'
