"""drop unused columns candidate_check subscription

Drops investigation_id, report_path, task_started_at from candidate_checks
(plus the orphaned FK to non-existent 'investigations' table) and drops
subscriptions.amount.

Uses table-rebuild instead of ALTER TABLE DROP COLUMN because the orphaned FK
causes DROP COLUMN to fail even on SQLite 3.35+ when the FK is embedded in
the table DDL.  Idempotent: safe to run when the columns are already gone.

Revision ID: 40f0c1f7867f
Revises: b2c3d4e5f6a7
Create Date: 2026-06-18 23:06:03.102555
"""
import re

import sqlalchemy as sa
from alembic import op

revision = '40f0c1f7867f'
down_revision = 'b2c3d4e5f6a7'
branch_labels = None
depends_on = None

_DEAD = {'investigation_id', 'report_path', 'task_started_at'}


def upgrade():
    conn = op.get_bind()
    conn.execute(sa.text('PRAGMA foreign_keys=OFF'))

    pragma = conn.execute(
        sa.text('PRAGMA table_info(candidate_checks)')
    ).fetchall()
    existing = {r[1] for r in pragma}

    if _DEAD & existing:
        row = conn.execute(
            sa.text(
                "SELECT sql FROM sqlite_master "
                "WHERE type='table' AND name='candidate_checks'"
            )
        ).fetchone()
        old_sql = row[0]

        new_sql = re.sub(
            r'CREATE TABLE\s+["\']?candidate_checks["\']?',
            'CREATE TABLE _cc_new',
            old_sql,
            flags=re.IGNORECASE,
        )
        filtered = [
            line for line in new_sql.split('\n')
            if not any(col in line for col in _DEAD)
            and 'investigations' not in line.lower()
        ]
        new_sql = re.sub(r',(\s*\n\s*\))', r'\1', '\n'.join(filtered))

        keep_cols = [c for c in existing if c not in _DEAD]
        cols = ', '.join(keep_cols)
        conn.execute(sa.text(new_sql))
        conn.execute(sa.text(
            f'INSERT INTO _cc_new ({cols}) SELECT {cols} FROM candidate_checks'
        ))
        conn.execute(sa.text('DROP TABLE candidate_checks'))
        conn.execute(sa.text('ALTER TABLE _cc_new RENAME TO candidate_checks'))

    pragma2 = conn.execute(
        sa.text('PRAGMA table_info(subscriptions)')
    ).fetchall()
    if any(r[1] == 'amount' for r in pragma2):
        conn.execute(sa.text('ALTER TABLE subscriptions DROP COLUMN amount'))

    conn.execute(sa.text('PRAGMA foreign_keys=ON'))


def downgrade():
    pass  # these columns are permanently retired; downgrade is a no-op
