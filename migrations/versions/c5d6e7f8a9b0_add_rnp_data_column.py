"""add rnp_data column to company_checks

Revision ID: c5d6e7f8a9b0
Revises: a3b4c5d6e7f8
Create Date: 2026-06-10 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'c5d6e7f8a9b0'
down_revision = 'a3b4c5d6e7f8'
branch_labels = None
depends_on = None


def upgrade():
    try:
        op.add_column('company_checks', sa.Column('rnp_data', sa.Text(), nullable=True))
    except Exception:
        pass


def downgrade():
    with op.batch_alter_table('company_checks', schema=None) as batch_op:
        batch_op.drop_column('rnp_data')
