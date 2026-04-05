"""
MASTER AUDIT RUNNER
====================
Runs all 8 agents in sequence, then aggregates results.
"""

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(r"C:\Users\fedor\ibp")
PYTHON = sys.executable

agents = [
    ('Agent 1: Import Chain', 'scripts/audit/agent1_imports.py'),
    ('Agent 2: Pipeline Flow', 'scripts/audit/agent2_pipeline_flow.py'),
    ('Agent 3: Timeouts', 'scripts/audit/agent3_timeouts.py'),
    ('Agent 4: Thread Safety', 'scripts/audit/agent4_thread_safety.py'),
    ('Agent 5: Error Coverage', 'scripts/audit/agent5_error_coverage.py'),
    ('Agent 6: Database', 'scripts/audit/agent6_database.py'),
    ('Agent 7: External Services', 'scripts/audit/agent7_external_services.py'),
    ('Agent 8: Performance', 'scripts/audit/agent8_performance.py'),
]

print("=" * 70)
print("FULL INFRASTRUCTURE AUDIT")
print("=" * 70)
print(f"Running {len(agents)} agents...\n")

for name, script in agents:
    print(f"\n{'~'*60}")
    print(f"> {name}")
    print(f"{'~'*60}")

    script_path = PROJECT_ROOT / script
    if not script_path.exists():
        print(f"  WARNING: Script not found: {script}")
        continue

    result = subprocess.run(
        [PYTHON, str(script_path)],
        capture_output=False,
        cwd=str(PROJECT_ROOT)
    )

    if result.returncode != 0:
        print(f"  WARNING: Agent exited with code {result.returncode}")

# Run aggregator
print(f"\n{'~'*60}")
print("> Agent 9: Aggregating results...")
print(f"{'~'*60}")

agg_script = PROJECT_ROOT / 'scripts' / 'audit' / 'agent9_aggregator.py'
subprocess.run([PYTHON, str(agg_script)], cwd=str(PROJECT_ROOT))

print(f"\nAUDIT COMPLETE")
print(f"Report: {PROJECT_ROOT / 'scripts' / 'audit' / 'INFRASTRUCTURE_REPORT.md'}")
