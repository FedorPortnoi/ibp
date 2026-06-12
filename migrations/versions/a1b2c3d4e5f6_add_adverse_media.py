"""add adverse_media column to candidate_checks

Revision ID: a1b2c3d4e5f6
Revises: f9a0b1c2d3e4
Create Date: 2026-06-12 22:30:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'a1b2c3d4e5f6'
down_revision = 'f9a0b1c2d3e4'
branch_labels = None
depends_on = None


def upgrade():
    try:
        op.add_column(
            'candidate_checks',
            sa.Column('adverse_media', sa.Text(), nullable=True),
        )
    except Exception:
        pass


def downgrade():
    with op.batch_alter_table('candidate_checks', schema=None) as batch_op:
        batch_op.drop_column('adverse_media')
