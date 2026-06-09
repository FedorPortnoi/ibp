"""add sanctions_meta and gov_contracts_data to company_checks

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-06-09 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'f2a3b4c5d6e7'
down_revision = 'e1f2a3b4c5d6'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE company_checks ADD COLUMN IF NOT EXISTS sanctions_meta TEXT")
    op.execute("ALTER TABLE company_checks ADD COLUMN IF NOT EXISTS gov_contracts_data TEXT")


def downgrade():
    with op.batch_alter_table('company_checks', schema=None) as batch_op:
        batch_op.drop_column('gov_contracts_data')
        batch_op.drop_column('sanctions_meta')
