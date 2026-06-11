"""add general source_statuses column to candidate_checks

Revision ID: f9a0b1c2d3e4
Revises: e8f9a0b1c2d3
Create Date: 2026-06-11 02:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'f9a0b1c2d3e4'
down_revision = 'e8f9a0b1c2d3'
branch_labels = None
depends_on = None


def upgrade():
    try:
        op.add_column(
            'candidate_checks',
            sa.Column('source_statuses', sa.Text(), nullable=True),
        )
    except Exception:
        pass


def downgrade():
    with op.batch_alter_table('candidate_checks', schema=None) as batch_op:
        batch_op.drop_column('source_statuses')
