"""
AGENT 2: PIPELINE FLOW TRACER
==============================
Traces every code path through the 9-stage pipeline.
Detects: missing stage handlers, stages that can't complete,
progress % that never reaches 100, stages with no error handling.
"""

import ast
import re
import json
from pathlib import Path

PROJECT_ROOT = Path(r"C:\Users\fedor\ibp")
findings = []

def add_finding(severity, file, line, issue, recommendation):
    findings.append({
        'agent': 'PIPELINE_FLOW',
        'severity': severity,
        'file': str(file).replace(str(PROJECT_ROOT), ''),
        'line': line,
        'issue': issue,
        'recommendation': recommendation,
    })
    icon = {'CRITICAL': '[!!!]', 'HIGH': '[!!]', 'MEDIUM': '[!]', 'LOW': '[~]'}[severity]
    print(f"  {icon} [{severity}] {file}:{line} -- {issue[:80]}")

# -- Scan 1: Trace pipeline stages --
def scan_pipeline_stages():
    print("\n[AGENT 2] Tracing pipeline stages...")

    pipeline_file = PROJECT_ROOT / 'app' / 'services' / 'candidate' / 'pipeline.py'
    source = pipeline_file.read_text(encoding='utf-8')
    lines = source.split('\n')

    stage_patterns = {
        'stage_0': r'[Ss]tage\s*[_\s]?0|identity|Identity',
        'stage_1': r'[Ss]tage\s*[_\s]?1|registr|Registr',
        'stage_2': r'[Ss]tage\s*[_\s]?2|security|Security|sanction',
        'stage_3': r'[Ss]tage\s*[_\s]?3|social|Social|vk|VK',
        'stage_4': r'[Ss]tage\s*[_\s]?4|contact|Contact',
        'stage_5': r'[Ss]tage\s*[_\s]?5|deep|Deep|analysis',
        'stage_6': r'[Ss]tage\s*[_\s]?6|behav|Behav',
        'stage_7': r'[Ss]tage\s*[_\s]?7|risk|Risk|scor',
        'stage_8': r'[Ss]tage\s*[_\s]?8|report|Report|dossier',
    }

    stages_found = {}
    for stage, pattern in stage_patterns.items():
        matches = [(i+1, line) for i, line in enumerate(lines)
                   if re.search(pattern, line)]
        stages_found[stage] = matches
        count = len(matches)
        icon = 'OK' if count > 0 else 'MISSING'
        print(f"  [{icon}] {stage}: {count} references found")

        if count == 0:
            add_finding(
                'HIGH', pipeline_file, 0,
                f"{stage} has NO references in pipeline -- stage may be missing",
                f"Add {stage} implementation to pipeline.py"
            )

    # Check progress percentages
    percent_pattern = r'percent\s*=\s*(\d+)|update.*?(\d+)\s*%|set_percent.*?(\d+)'
    percents = []
    for i, line in enumerate(lines):
        match = re.search(percent_pattern, line)
        if match:
            pct = int(match.group(1) or match.group(2) or match.group(3) or 0)
            percents.append((i+1, pct))

    if percents:
        max_pct = max(p for _, p in percents)
        if max_pct < 95:
            add_finding(
                'HIGH', pipeline_file, 0,
                f"Pipeline max progress is {max_pct}% -- never reaches 100%",
                "Add final stage that sets progress to 100%"
            )
        print(f"  Progress range: 0% -> {max_pct}%")

        sorted_pcts = sorted(set(p for _, p in percents))
        for i in range(len(sorted_pcts) - 1):
            gap = sorted_pcts[i+1] - sorted_pcts[i]
            if gap > 20:
                add_finding(
                    'MEDIUM', pipeline_file, 0,
                    f"Progress gap: {sorted_pcts[i]}% -> {sorted_pcts[i+1]}% ({gap}% jump)",
                    "Add intermediate progress updates in this range"
                )

# -- Scan 2: Find stages with no timeout --
def scan_stage_timeouts():
    print("\n[AGENT 2] Scanning for missing stage timeouts...")

    pipeline_file = PROJECT_ROOT / 'app' / 'services' / 'candidate' / 'pipeline.py'
    source = pipeline_file.read_text(encoding='utf-8')
    lines = source.split('\n')

    current_func = None
    func_start = 0
    func_has_timeout = False

    timeout_keywords = ['timeout', 'wait_for', 'asyncio.wait_for',
                        'TIMEOUT', 'time.sleep', 'max_wait', 'deadline']

    for i, line in enumerate(lines):
        if re.match(r'\s*def (run_|_stage|_run_|stage_)', line):
            if current_func and not func_has_timeout:
                add_finding(
                    'HIGH', pipeline_file, func_start,
                    f"Function '{current_func}' has NO timeout protection",
                    "Add asyncio.wait_for() or threading.Timer() timeout"
                )
            current_func = re.match(r'\s*def (\w+)', line).group(1)
            func_start = i + 1
            func_has_timeout = False

        if current_func and any(kw in line for kw in timeout_keywords):
            func_has_timeout = True

# -- Scan 3: Find exception swallowing --
def scan_exception_handling():
    print("\n[AGENT 2] Scanning exception handling in pipeline...")

    pipeline_file = PROJECT_ROOT / 'app' / 'services' / 'candidate' / 'pipeline.py'
    source = pipeline_file.read_text(encoding='utf-8')

    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        add_finding(
            'CRITICAL', pipeline_file, e.lineno,
            f"SYNTAX ERROR in pipeline.py: {e.msg}",
            "Fix syntax error immediately -- server cannot start"
        )
        return

    lines = source.split('\n')

    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            body_code = '\n'.join(
                ast.unparse(stmt) if hasattr(ast, 'unparse') else ''
                for stmt in node.body
            )

            if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
                add_finding(
                    'HIGH', pipeline_file, node.lineno,
                    f"Silent exception handler at line {node.lineno} -- error swallowed",
                    "Add at least: logger.warning(f'Error: {{e}}') before pass"
                )

            has_log = any(
                keyword in body_code
                for keyword in ['log', 'print', 'warning', 'error', 'info', 'debug']
            )

            if not has_log and len(node.body) > 0:
                add_finding(
                    'MEDIUM', pipeline_file, node.lineno,
                    f"Exception caught but not logged at line {node.lineno}",
                    "Add logger.warning() or logger.error() to exception handler"
                )

# -- Scan 4: Check stage result storage --
def scan_result_storage():
    print("\n[AGENT 2] Scanning pipeline result storage...")

    pipeline_file = PROJECT_ROOT / 'app' / 'services' / 'candidate' / 'pipeline.py'
    source = pipeline_file.read_text(encoding='utf-8')
    lines = source.split('\n')

    db_commits = [(i+1, line.strip()) for i, line in enumerate(lines)
                  if 'db.session.commit()' in line or 'db.session.flush()' in line]

    print(f"  db.session.commit() calls: {len(db_commits)}")

    if len(db_commits) < 5:
        add_finding(
            'MEDIUM', pipeline_file, 0,
            f"Only {len(db_commits)} db commits in pipeline -- results may be lost on crash",
            "Add db.session.commit() after each major stage completes"
        )

    for line_num, commit_line in db_commits:
        start = max(0, line_num - 10)
        end = min(len(lines), line_num + 5)
        context = '\n'.join(lines[start:end])
        if 'try:' not in context and 'except' not in context:
            add_finding(
                'HIGH', pipeline_file, line_num,
                f"db.session.commit() at line {line_num} not in try/except",
                "Wrap in try/except with db.session.rollback() on error"
            )

# -- Scan 5: Find infinite loop risks --
def scan_infinite_loops():
    print("\n[AGENT 2] Scanning for infinite loop risks...")

    service_files = list((PROJECT_ROOT / 'app' / 'services').rglob('*.py'))

    for pyfile in service_files:
        try:
            source = pyfile.read_text(encoding='utf-8', errors='ignore')
            lines = source.split('\n')

            for i, line in enumerate(lines):
                if re.match(r'\s*while\s+True\s*:', line):
                    context = lines[i:i+20]
                    has_break = any('break' in l or 'return' in l for l in context)
                    has_timeout = any(
                        any(kw in l for kw in ['timeout', 'time.time', 'deadline', 'max_'])
                        for l in context
                    )

                    if not has_break:
                        add_finding(
                            'HIGH', pyfile, i+1,
                            f"while True loop with no visible break",
                            "Add explicit break condition or timeout"
                        )
                    elif not has_timeout:
                        add_finding(
                            'MEDIUM', pyfile, i+1,
                            f"while True loop with break but no timeout protection",
                            "Add time-based timeout to prevent infinite polling"
                        )
        except:
            pass

# -- Main --
if __name__ == '__main__':
    print("=" * 70)
    print("AGENT 2: PIPELINE FLOW TRACER")
    print("=" * 70)

    scan_pipeline_stages()
    scan_stage_timeouts()
    scan_exception_handling()
    scan_result_storage()
    scan_infinite_loops()

    print(f"\nAgent 2 complete: {len(findings)} findings")

    output = PROJECT_ROOT / 'scripts' / 'audit' / 'agent2_results.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, 'w', encoding='utf-8') as f:
        json.dump(findings, f, ensure_ascii=False, indent=2)
