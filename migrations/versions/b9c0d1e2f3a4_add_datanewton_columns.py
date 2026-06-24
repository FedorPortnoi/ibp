"""add datanewton columns to company_checks

Revision ID: b9c0d1e2f3a4
Revises: a8b9c0d1e2f3
Create Date: 2026-06-24

"""
from alembic import op
import sqlalchemy as sa

revision = 'b9c0d1e2f3a4'
down_revision = 'a8b9c0d1e2f3'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('company_checks') as batch_op:
        batch_op.add_column(sa.Column('risks_data', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('tax_info_data', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('blocked_accounts_data', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('inspections_data', sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table('company_checks') as batch_op:
        batch_op.drop_column('inspections_data')
        batch_op.drop_column('blocked_accounts_data')
        batch_op.drop_column('tax_info_data')
        batch_op.drop_column('risks_data')
