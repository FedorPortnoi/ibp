"""
AGENT 6: DATABASE INTEGRITY SCANNER
=====================================
Scans all database operations for:
- Missing fields that pipeline tries to write
- Orphaned JSON columns (written but never read)
- Migration drift (model vs actual DB schema)
- Large JSON columns that could cause memory issues
"""

import ast
import re
import json
import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(r"C:\Users\fedor\ibp")
findings = []

def add_finding(severity, file, line, issue, recommendation):
    findings.append({
        'agent': 'DATABASE',
        'severity': severity,
        'file': str(file).replace(str(PROJECT_ROOT), ''),
        'line': line,
        'issue': issue,
        'recommendation': recommendation,
    })
    icon = {'CRITICAL': '[!!!]', 'HIGH': '[!!]', 'MEDIUM': '[!]', 'LOW': '[~]'}[severity]
    print(f"  {icon} [{severity}] {file}:{line} -- {issue[:80]}")

def scan_model_vs_pipeline():
    print("\n[AGENT 6] Comparing model fields vs pipeline writes...")

    model_file = PROJECT_ROOT / 'app' / 'models' / 'candidate_check.py'
    pipeline_file = PROJECT_ROOT / 'app' / 'services' / 'candidate' / 'pipeline.py'

    if not model_file.exists() or not pipeline_file.exists():
        print("  Files not found")
        return

    model_source = model_file.read_text(encoding='utf-8', errors='ignore')
    # Match both `field = db.Column(` and `_field = db.Column('field', ...)`
    model_fields = re.findall(r'(\w+)\s*=\s*db\.Column\(', model_source)
    # Also extract @property names (which are the public API for _ columns)
    property_names = re.findall(r'@property\s*\n\s*def (\w+)\(self\)', model_source)
    # Build full field set: direct columns + properties + stripped underscore names
    all_model_fields = set(model_fields) | set(property_names) | {f.lstrip('_') for f in model_fields}
    print(f"  Model fields: {len(model_fields)} (+ {len(property_names)} properties)")

    pipeline_source = pipeline_file.read_text(encoding='utf-8', errors='ignore')
    pipeline_writes = re.findall(r'check\.(\w+)\s*=', pipeline_source)
    pipeline_writes = list(set(pipeline_writes))
    print(f"  Pipeline writes: {len(pipeline_writes)}")

    for field in pipeline_writes:
        if field not in all_model_fields and field not in ['id', 'created_at', 'updated_at']:
            add_finding(
                'HIGH', pipeline_file, 0,
                f"Pipeline writes to 'check.{field}' but field not in model",
                f"Add '{field}' column to CandidateCheck model and run migration"
            )

    orphan_fields = [f for f in model_fields
                     if f not in pipeline_writes
                     and f not in ['id', 'created_at', 'updated_at', 'task_id', 'user_id']]

    if orphan_fields:
        print(f"  Model fields never written by pipeline: {orphan_fields[:10]}")

def scan_actual_db_schema():
    print("\n[AGENT 6] Scanning actual SQLite schema vs model...")

    db_paths = list(PROJECT_ROOT.rglob('*.db')) + list(PROJECT_ROOT.rglob('*.sqlite3'))

    if not db_paths:
        print("  No SQLite DB found locally -- skipping schema check")
        return

    db_path = db_paths[0]
    print(f"  Found DB: {db_path.name}")

    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        print(f"  Tables: {tables}")

        if 'candidate_checks' in tables:
            cursor.execute("PRAGMA table_info(candidate_checks)")
            db_cols = [row[1] for row in cursor.fetchall()]

            model_file = PROJECT_ROOT / 'app' / 'models' / 'candidate_check.py'
            model_source = model_file.read_text(encoding='utf-8', errors='ignore')
            model_fields = re.findall(r'(\w+)\s*=\s*db\.Column\(', model_source)

            # Also extract explicit column names: _field = db.Column('field', ...)
            explicit_col_names = re.findall(r'\w+\s*=\s*db\.Column\([\'"](\w+)[\'"]', model_source)

            # Build expected DB columns: attribute names + explicit column names
            expected_in_db = set()
            for f in model_fields:
                expected_in_db.add(f)
            for f in explicit_col_names:
                expected_in_db.add(f)
            # Remove _ prefixed names that have an explicit column name mapping
            mapped_attrs = set(re.findall(r'(_\w+)\s*=\s*db\.Column\([\'"]', model_source))
            expected_in_db -= mapped_attrs

            db_cols_set = set(db_cols)
            missing_in_db = sorted(expected_in_db - db_cols_set)
            if missing_in_db:
                add_finding(
                    'CRITICAL', model_file, 0,
                    f"Fields in model but NOT in DB: {missing_in_db}",
                    "Run 'flask db upgrade' to apply pending migrations"
                )

            # For extra_in_db, also consider explicit column name mappings
            model_all = expected_in_db | mapped_attrs | set(explicit_col_names)
            extra_in_db = sorted(db_cols_set - model_all)
            if extra_in_db:
                add_finding(
                    'LOW', model_file, 0,
                    f"Fields in DB but not in current model: {extra_in_db}",
                    "Consider adding these to model or cleaning up old columns"
                )

        conn.close()
    except Exception as e:
        add_finding(
            'MEDIUM', str(db_path), 0,
            f"Could not connect to SQLite DB: {e}",
            "Verify DB is not corrupted"
        )

def scan_json_column_sizes():
    print("\n[AGENT 6] Scanning JSON column usage...")

    model_file = PROJECT_ROOT / 'app' / 'models' / 'candidate_check.py'
    if not model_file.exists():
        return

    source = model_file.read_text(encoding='utf-8', errors='ignore')

    json_cols = re.findall(r'(\w+)\s*=\s*db\.Column\((?:db\.Text|db\.JSON)', source)
    print(f"  JSON/Text columns: {len(json_cols)}")

    if len(json_cols) > 20:
        add_finding(
            'MEDIUM', model_file, 0,
            f"Model has {len(json_cols)} JSON/Text columns -- may cause memory issues for large dossiers",
            "Consider storing large data in separate tables or files"
        )

def scan_migration_status():
    print("\n[AGENT 6] Checking migration status...")

    migrations_dir = PROJECT_ROOT / 'migrations' / 'versions'
    if not migrations_dir.exists():
        add_finding(
            'MEDIUM', 'migrations/', 0,
            "No migrations directory found",
            "Run 'flask db init && flask db migrate && flask db upgrade'"
        )
        return

    migration_files = list(migrations_dir.glob('*.py'))
    print(f"  Migration files: {len(migration_files)}")

    if len(migration_files) == 0:
        add_finding(
            'HIGH', 'migrations/', 0,
            "No migration files found -- DB may be out of sync",
            "Run 'flask db migrate -m \"initial\"'"
        )

# -- Main --
if __name__ == '__main__':
    print("=" * 70)
    print("AGENT 6: DATABASE INTEGRITY SCANNER")
    print("=" * 70)

    scan_model_vs_pipeline()
    scan_actual_db_schema()
    scan_json_column_sizes()
    scan_migration_status()

    print(f"\nAgent 6 complete: {len(findings)} findings")

    output = PROJECT_ROOT / 'scripts' / 'audit' / 'agent6_results.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, 'w', encoding='utf-8') as f:
        json.dump(findings, f, ensure_ascii=False, indent=2)
