"""Admin-only user investigation views."""

from flask import Blueprint, render_template, abort
from sqlalchemy import func

from app import db
from app.models.candidate_check import CandidateCheck
from app.models.user import User
from app.routes.auth import admin_required


admin_users_bp = Blueprint('admin_users', __name__, url_prefix='/admin/users')


@admin_users_bp.route('/')
@admin_required
def list_users():
    """Show all users before exposing their investigation history."""
    stats = (
        db.session.query(
            CandidateCheck.user_id.label('user_id'),
            func.count(CandidateCheck.id).label('check_count'),
            func.max(CandidateCheck.created_at).label('last_check_at'),
        )
        .group_by(CandidateCheck.user_id)
        .subquery()
    )

    rows = (
        db.session.query(User, stats.c.check_count, stats.c.last_check_at)
        .outerjoin(stats, stats.c.user_id == User.id)
        .order_by(User.role.asc(), User.created_at.desc())
        .all()
    )

    return render_template('admin_users.html', rows=rows)


@admin_users_bp.route('/<int:user_id>/investigations')
@admin_required
def user_investigations(user_id):
    """Show investigations for one selected user."""
    selected_user = db.session.get(User, user_id)
    if not selected_user:
        abort(404)
    checks = (
        CandidateCheck.query
        .filter_by(user_id=selected_user.id)
        .order_by(CandidateCheck.created_at.desc())
        .all()
    )

    return render_template(
        'admin_user_investigations.html',
        selected_user=selected_user,
        checks=checks,
    )
