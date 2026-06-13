"""add connections column to candidate_checks (Axis 2)

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-06-12 23:30:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    try:
        op.add_column(
            'candidate_checks',
            sa.Column('connections', sa.Text(), nullable=True),
        )
    except Exception:
        pass


def downgrade():
    with op.batch_alter_table('candidate_checks', schema=None) as batch_op:
        batch_op.drop_column('connections')
