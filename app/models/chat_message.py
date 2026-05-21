"""
ChatMessage Model
=================
Personal scratchpad messages per user (like Telegram Favorites).
"""

import json
from datetime import datetime

from app import db


class ChatMessage(db.Model):
    __tablename__ = 'chat_messages'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    content = db.Column(db.Text, nullable=False)
    is_pinned = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def to_dict(self):
        return {
            'id': self.id,
            'content': self.content,
            'is_pinned': self.is_pinned,
            'created_at': self.created_at.strftime('%Y-%m-%dT%H:%M:%SZ'),
        }
