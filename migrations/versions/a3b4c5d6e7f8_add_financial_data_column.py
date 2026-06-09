"""add financial_data column to company_checks

Revision ID: a3b4c5d6e7f8
Revises: f2a3b4c5d6e7
Create Date: 2026-06-09 17:30:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'a3b4c5d6e7f8'
down_revision = 'f2a3b4c5d6e7'
branch_labels = None
depends_on = None


def upgrade():
    try:
        op.add_column('company_checks', sa.Column('financial_data', sa.Text(), nullable=True))
    except Exception:
        pass


def downgrade():
    with op.batch_alter_table('company_checks', schema=None) as batch_op:
        batch_op.drop_column('financial_data')
