"""add audit_log table

Revision ID: d4e5f6a7b8c9
Revises: b1c2d3e4f5a6
Create Date: 2026-05-23

Append-only audit log: who ran what check, when, from where.
Required for B2B accountability and 152-FZ compliance.
"""
from alembic import op
import sqlalchemy as sa


revision = 'd4e5f6a7b8c9'
down_revision = 'b1c2d3e4f5a6'
branch_labels = None
depends_on = None


def _table_exists(name):
    bind = op.get_bind()
    return sa.inspect(bind).has_table(name)


def _idx_exists(name, table):
    bind = op.get_bind()
    return any(i['name'] == name for i in sa.inspect(bind).get_indexes(table))


def upgrade():
    if not _table_exists('audit_log'):
        op.create_table(
            'audit_log',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=True),
            sa.Column('ip_address', sa.String(45), nullable=True),
            sa.Column('action', sa.String(64), nullable=False),
            sa.Column('outcome', sa.String(16), nullable=False),
            sa.Column('target_type', sa.String(64), nullable=True),
            sa.Column('target_id', sa.String(36), nullable=True),
            sa.Column('metadata', sa.Text(), nullable=True),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
            sa.PrimaryKeyConstraint('id'),
        )
    if not _idx_exists('ix_audit_log_created_at', 'audit_log'):
        op.create_index('ix_audit_log_created_at', 'audit_log', ['created_at'])
    if not _idx_exists('ix_audit_log_user_id', 'audit_log'):
        op.create_index('ix_audit_log_user_id', 'audit_log', ['user_id'])
    if not _idx_exists('ix_audit_log_action', 'audit_log'):
        op.create_index('ix_audit_log_action', 'audit_log', ['action'])


def downgrade():
    op.drop_index('ix_audit_log_action', table_name='audit_log')
    op.drop_index('ix_audit_log_user_id', table_name='audit_log')
    op.drop_index('ix_audit_log_created_at', table_name='audit_log')
    op.drop_table('audit_log')
