"""add deferred columns

Revision ID: b1c2d3e4f5a6
Revises: 20059de8b625
Create Date: 2026-05-23

Adds all columns that were previously added via inline _migrate_* helpers
in create_app(). This migration is idempotent — skips any column that already
exists, so it is safe to run on both fresh and existing databases.
"""
from alembic import op
import sqlalchemy as sa


revision = 'b1c2d3e4f5a6'
down_revision = '20059de8b625'
branch_labels = None
depends_on = None


def _col_exists(table: str, col: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return col in {c['name'] for c in insp.get_columns(table)}


def _idx_exists(idx: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    for table in insp.get_table_names():
        for ix in insp.get_indexes(table):
            if ix['name'] == idx:
                return True
    return False


def upgrade():
    # --- candidate_checks ---
    cc_cols = [
        ('task_id',           sa.String(36)),
        ('task_progress',     sa.Integer()),
        ('task_stage',        sa.String(50)),
        ('task_message',      sa.String(500)),
        ('task_log',          sa.Text()),
        ('task_error',        sa.Text()),
        ('task_started_at',   sa.DateTime()),
        ('photo_path',        sa.String(500)),
        ('group_analysis',    sa.Text()),
        ('activity_patterns', sa.Text()),
        ('vk_snapshot',       sa.Text()),
        ('connected_checks',  sa.Text()),
        ('risk_score',        sa.Integer()),
        ('pledge_records',    sa.Text()),
        ('geo_intelligence',  sa.Text()),
        ('user_id',           sa.Integer()),
        ('pd_consent',        sa.Boolean()),
        ('pd_consent_at',     sa.DateTime()),
    ]
    for col_name, col_type in cc_cols:
        if not _col_exists('candidate_checks', col_name):
            op.add_column('candidate_checks', sa.Column(col_name, col_type, nullable=True))

    if not _idx_exists('ix_candidate_checks_task_id'):
        op.create_index('ix_candidate_checks_task_id', 'candidate_checks', ['task_id'])

    # --- users ---
    if not _col_exists('users', 'email'):
        op.add_column('users', sa.Column('email', sa.String(120), nullable=True))

    # --- chat_messages ---
    if not _col_exists('chat_messages', 'is_pinned'):
        op.add_column('chat_messages', sa.Column('is_pinned', sa.Boolean(), nullable=True))

    if not _idx_exists('idx_chat_messages_user_id'):
        try:
            op.create_index('idx_chat_messages_user_id', 'chat_messages', ['user_id'])
        except Exception:
            pass  # index may already exist under a different mechanism


def downgrade():
    pass
