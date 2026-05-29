"""
Chat Routes
===========
Personal scratchpad — like Telegram Favorites.
All routes scoped to the logged-in user; each user sees only their own messages.
"""

import logging
from flask import Blueprint, render_template, request, jsonify, session, abort

from app import db, limiter
from app.models.chat_message import ChatMessage

chat_bp = Blueprint('chat', __name__, url_prefix='/chat')
logger = logging.getLogger(__name__)

_MAX_CONTENT = 4000


def _uid():
    uid = session.get('user_id')
    if not uid:
        abort(401)
    return uid


@chat_bp.route('/')
def chat_page():
    return render_template('chat.html')


@chat_bp.route('/api/messages', methods=['GET'])
def get_messages():
    uid = _uid()
    msgs = (
        ChatMessage.query
        .filter_by(user_id=uid)
        .order_by(ChatMessage.is_pinned.desc(), ChatMessage.created_at.asc())
        .limit(500)
        .all()
    )
    return jsonify([m.to_dict() for m in msgs])


@chat_bp.route('/api/messages', methods=['POST'])
@limiter.limit('60 per minute')
def post_message():
    uid = _uid()
    data = request.get_json(silent=True) or {}
    content = str(data.get('content', '')).strip()

    if not content:
        return jsonify({'error': 'Пустое сообщение'}), 400
    if len(content) > _MAX_CONTENT:
        return jsonify({'error': f'Максимум {_MAX_CONTENT} символов'}), 400

    msg = ChatMessage(user_id=uid, content=content)
    db.session.add(msg)
    db.session.commit()
    return jsonify(msg.to_dict()), 201


@chat_bp.route('/api/messages/<int:msg_id>', methods=['DELETE'])
def delete_message(msg_id):
    uid = _uid()
    msg = db.session.get(ChatMessage, msg_id)
    if not msg:
        abort(404)
    if msg.user_id != uid:
        abort(403)
    db.session.delete(msg)
    db.session.commit()
    return jsonify({'ok': True})


@chat_bp.route('/api/messages/<int:msg_id>/pin', methods=['POST'])
def toggle_pin(msg_id):
    uid = _uid()
    msg = db.session.get(ChatMessage, msg_id)
    if not msg:
        abort(404)
    if msg.user_id != uid:
        abort(403)
    msg.is_pinned = not msg.is_pinned
    db.session.commit()
    return jsonify({'is_pinned': msg.is_pinned})
