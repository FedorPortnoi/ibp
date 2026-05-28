"""
User Model
==========
Multi-user authentication with role-based access.
Roles: 'admin' (Fedor/admin access) | 'user' (own checks only).
"""

from datetime import datetime

import bcrypt

from app import db


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(16), nullable=False, default='user')  # 'admin' | 'user'
    email = db.Column(db.String(120), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

    checks = db.relationship('CandidateCheck', backref='user', lazy='dynamic')

    def set_password(self, password: str):
        self.password_hash = bcrypt.hashpw(
            password.encode('utf-8'), bcrypt.gensalt()
        ).decode('utf-8')

    def check_password(self, password: str) -> bool:
        return bcrypt.checkpw(
            password.encode('utf-8'), self.password_hash.encode('utf-8')
        )

    @property
    def is_admin(self) -> bool:
        return self.role == 'admin'

    def __repr__(self):
        return f'<User {self.username} ({self.role})>'
