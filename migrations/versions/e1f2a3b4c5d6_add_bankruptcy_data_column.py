"""add bankruptcy_data column to company_checks

Revision ID: e1f2a3b4c5d6
Revises: b846bbbab0b3
Create Date: 2026-06-09 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'e1f2a3b4c5d6'
down_revision = 'b846bbbab0b3'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('company_checks',
        sa.Column('bankruptcy_data', sa.Text(), nullable=True)
    )


def downgrade():
    with op.batch_alter_table('company_checks', schema=None) as batch_op:
        batch_op.drop_column('bankruptcy_data')
