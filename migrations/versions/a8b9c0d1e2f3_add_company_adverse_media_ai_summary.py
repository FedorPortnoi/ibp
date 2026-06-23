"""add company adverse_media, fssp_data, ai_summary columns

Revision ID: a8b9c0d1e2f3
Revises: 40f0c1f7867f
Create Date: 2026-06-23 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'a8b9c0d1e2f3'
down_revision = '40f0c1f7867f'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('company_checks', schema=None) as batch_op:
        batch_op.add_column(sa.Column('adverse_media', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('fssp_data', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('ai_summary', sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table('company_checks', schema=None) as batch_op:
        batch_op.drop_column('ai_summary')
        batch_op.drop_column('fssp_data')
        batch_op.drop_column('adverse_media')
