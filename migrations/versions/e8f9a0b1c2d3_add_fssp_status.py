"""add fssp_status column to candidate_checks

Revision ID: e8f9a0b1c2d3
Revises: d7e8f9a0b1c2
Create Date: 2026-06-11 01:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'e8f9a0b1c2d3'
down_revision = 'd7e8f9a0b1c2'
branch_labels = None
depends_on = None


def upgrade():
    try:
        op.add_column(
            'candidate_checks',
            sa.Column('fssp_status', sa.String(length=20), nullable=True),
        )
    except Exception:
        pass


def downgrade():
    with op.batch_alter_table('candidate_checks', schema=None) as batch_op:
        batch_op.drop_column('fssp_status')
