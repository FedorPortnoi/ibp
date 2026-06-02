from datetime import datetime
from app import db


class LoginAttempt(db.Model):
    __tablename__ = 'login_attempts'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username_lower = db.Column(db.String(64), index=True, nullable=False)
    attempted_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
