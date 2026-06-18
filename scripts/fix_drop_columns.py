"""
Fix: drop unused columns from candidate_checks and subscriptions.

Bypasses Alembic batch_alter_table because candidate_checks has an orphaned
FK to a non-existent 'investigations' table, which causes both batch reflection
and SQLite DROP COLUMN to fail.

Recreates the table from scratch (the safe SQLite way) and stamps the migration.

Run:  python3 scripts/fix_drop_columns.py
"""
import sqlite3
import re
import os
import sys

MIGRATION_ID = '40f0c1f7867f'
DROP_COLS = {'investigation_id', 'report_path', 'task_started_at'}

# Locate the SQLite DB
candidates = [
    '/opt/ibp/instance/ibp.db',
    '/opt/ibp/ibp.db',
    '/opt/ibp/app.db',
]
db_path = None
for p in candidates:
    if os.path.exists(p):
        db_path = p
        break

if not db_path:
    found = []
    for root, _dirs, files in os.walk('/opt/ibp'):
        for f in files:
            if f.endswith('.db'):
                found.append(os.path.join(root, f))
    if not found:
        sys.exit('ERROR: Could not find SQLite DB under /opt/ibp')
    db_path = found[0]

print(f'DB: {db_path}')

conn = sqlite3.connect(db_path)
cur = conn.cursor()
cur.execute('PRAGMA foreign_keys=OFF')

# ── Rebuild candidate_checks without the 3 dead columns + orphaned FK ──────

cur.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='candidate_checks'")
row = cur.fetchone()
if not row:
    sys.exit('ERROR: candidate_checks table not found')
old_sql = row[0]

cur.execute('PRAGMA table_info(candidate_checks)')
all_cols = [r[1] for r in cur.fetchall()]
keep_cols = [c for c in all_cols if c not in DROP_COLS]
print(f'Keeping {len(keep_cols)} columns: {keep_cols}')

# Build new CREATE TABLE without dropped columns and without the FK line
new_sql = re.sub(
    r'CREATE TABLE\s+["\']?candidate_checks["\']?',
    'CREATE TABLE _cc_new',
    old_sql,
    flags=re.IGNORECASE,
)
filtered = [
    line for line in new_sql.split('\n')
    if not any(col in line for col in DROP_COLS)
    and 'investigations' not in line.lower()
]
new_sql = re.sub(r',(\s*\n\s*\))', r'\1', '\n'.join(filtered))
print(f'\nNew schema:\n{new_sql}\n')

cur.execute(new_sql)
cols = ', '.join(keep_cols)
cur.execute(f'INSERT INTO _cc_new ({cols}) SELECT {cols} FROM candidate_checks')
cur.execute('DROP TABLE candidate_checks')
cur.execute('ALTER TABLE _cc_new RENAME TO candidate_checks')
print('candidate_checks rebuilt')

# ── Drop subscriptions.amount (no FK, plain DROP COLUMN works) ─────────────

try:
    cur.execute('ALTER TABLE subscriptions DROP COLUMN amount')
    print('subscriptions.amount dropped')
except Exception as e:
    print(f'subscriptions.amount: {e}')

# ── Stamp migration as applied in alembic_version ──────────────────────────

cur.execute(f"UPDATE alembic_version SET version_num='{MIGRATION_ID}'")
if cur.rowcount == 0:
    cur.execute(f"INSERT INTO alembic_version VALUES ('{MIGRATION_ID}')")
print(f'Migration {MIGRATION_ID} stamped')

cur.execute('PRAGMA foreign_keys=ON')
conn.commit()
conn.close()
print('\nAll done.')
