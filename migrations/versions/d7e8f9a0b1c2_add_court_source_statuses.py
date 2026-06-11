"""add court_source_statuses column to candidate_checks

Revision ID: d7e8f9a0b1c2
Revises: c5d6e7f8a9b0
Create Date: 2026-06-11 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'd7e8f9a0b1c2'
down_revision = 'c5d6e7f8a9b0'
branch_labels = None
depends_on = None


def upgrade():
    try:
        op.add_column(
            'candidate_checks',
            sa.Column('court_source_statuses', sa.Text(), nullable=True),
        )
    except Exception:
        pass


def downgrade():
    with op.batch_alter_table('candidate_checks', schema=None) as batch_op:
        batch_op.drop_column('court_source_statuses')
