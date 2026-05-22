"""
AGENT 5: ERROR HANDLER COVERAGE
=================================
Maps every code path that can raise an exception.
Finds: unhandled exceptions, bare excepts, missing rollbacks,
routes with no error handling.
"""

import ast
import re
import json
from pathlib import Path

PROJECT_ROOT = Path(r"C:\Users\fedor\ibp")
findings = []

def add_finding(severity, file, line, issue, recommendation):
    findings.append({
        'agent': 'ERROR_COVERAGE',
        'severity': severity,
        'file': str(file).replace(str(PROJECT_ROOT), ''),
        'line': line,
        'issue': issue,
        'recommendation': recommendation,
    })
    icon = {'CRITICAL': '[!!!]', 'HIGH': '[!!]', 'MEDIUM': '[!]', 'LOW': '[~]'}[severity]
    print(f"  {icon} [{severity}] {file}:{line} -- {issue[:80]}")

def scan_bare_excepts():
    print("\n[AGENT 5] Scanning for bare except clauses...")

    service_files = list((PROJECT_ROOT / 'app').rglob('*.py'))

    for pyfile in service_files:
        if '__pycache__' in str(pyfile):
            continue
        try:
            source = pyfile.read_text(encoding='utf-8', errors='ignore')
            tree = ast.parse(source)

            for node in ast.walk(tree):
                if isinstance(node, ast.ExceptHandler):
                    if node.type is None:
                        add_finding(
                            'HIGH', pyfile, node.lineno,
                            f"Bare 'except:' at line {node.lineno} -- catches EVERYTHING including SystemExit",
                            "Use 'except Exception as e:' and log the error"
                        )
        except SyntaxError:
            pass
        except:
            pass

def scan_missing_rollbacks():
    print("\n[AGENT 5] Scanning for db commits without rollback on error...")

    service_files = list((PROJECT_ROOT / 'app').rglob('*.py'))

    for pyfile in service_files:
        if '__pycache__' in str(pyfile):
            continue
        try:
            source = pyfile.read_text(encoding='utf-8', errors='ignore')
            lines = source.split('\n')

            for i, line in enumerate(lines):
                if 'db.session.commit()' in line:
                    # Use 30-line context in both directions (pipeline has deep nesting)
                    context_start = max(0, i-30)
                    context_end = min(len(lines), i+30)
                    context = '\n'.join(lines[context_start:context_end])

                    has_try = 'try:' in context
                    has_rollback = 'rollback()' in context

                    if has_try and not has_rollback:
                        add_finding(
                            'HIGH', pyfile, i+1,
                            f"db.session.commit() in try block without rollback on except",
                            "Add 'db.session.rollback()' in except block"
                        )
        except:
            pass

def scan_route_error_handling():
    print("\n[AGENT 5] Scanning Flask route error handling...")

    routes_dir = PROJECT_ROOT / 'app' / 'routes'
    if not routes_dir.exists():
        return

    for route_file in routes_dir.glob('*.py'):
        try:
            source = route_file.read_text(encoding='utf-8', errors='ignore')
            lines = source.split('\n')

            in_route = False
            route_start = 0
            route_has_try = False
            current_route = ''

            for i, line in enumerate(lines):
                if '@' in line and ('route(' in line or 'bp.route(' in line or
                                     'app.route(' in line or '_bp.route(' in line):
                    in_route = True
                    route_start = i + 1
                    route_has_try = False
                    current_route = line.strip()

                if in_route:
                    if 'try:' in line:
                        route_has_try = True

                    if i > route_start + 2 and '@' in line and 'route(' in line:
                        if not route_has_try:
                            add_finding(
                                'MEDIUM', route_file, route_start,
                                f"Route '{current_route[:50]}' has no try/except error handling",
                                "Add try/except to return proper error response instead of 500"
                            )
                        in_route = False
        except:
            pass

def scan_pipeline_stage_guards():
    print("\n[AGENT 5] Scanning pipeline stage error guards...")

    pipeline_file = PROJECT_ROOT / 'app' / 'services' / 'candidate' / 'pipeline.py'
    if not pipeline_file.exists():
        return

    source = pipeline_file.read_text(encoding='utf-8', errors='ignore')
    lines = source.split('\n')

    stage_calls = []
    for i, line in enumerate(lines):
        if re.search(r'(run_stage|_stage\d|stage_\d|run_.*analysis|run_.*discovery)', line):
            if '(' in line and 'def ' not in line:
                stage_calls.append((i+1, line.strip()))

    for line_num, call in stage_calls:
        # Use 20-line context (executor.submit calls have try/except further up)
        context_start = max(0, line_num - 20)
        context_end = min(len(lines), line_num + 10)
        context = '\n'.join(lines[context_start:context_end])

        has_try = 'try:' in context
        has_except = 'except' in context
        # executor.submit() handles errors via Future.result() or as_completed()
        is_executor_context = 'submit(' in context or 'executor' in context or \
                              'pool.submit' in context or 'future' in context.lower()

        if (not has_try or not has_except) and not is_executor_context:
            add_finding(
                'HIGH', pipeline_file, line_num,
                f"Stage call '{call[:50]}' not wrapped in try/except",
                "Pipeline stage must be in try/except to prevent total pipeline crash"
            )

def scan_unhandled_none():
    print("\n[AGENT 5] Scanning for potential None dereferences...")

    pipeline_file = PROJECT_ROOT / 'app' / 'services' / 'candidate' / 'pipeline.py'
    if not pipeline_file.exists():
        return

    source = pipeline_file.read_text(encoding='utf-8', errors='ignore')
    lines = source.split('\n')

    for i, line in enumerate(lines):
        call_match = re.search(r'\w+\s*=\s*([A-Za-z_]\w*)\(', line)
        if call_match and i + 1 < len(lines):
            callee = call_match.group(1)
            # Constructors and executor factories do not return None in normal Python
            # semantics; flagging them creates noise instead of actionable findings.
            if callee[:1].isupper():
                continue
            if ' or {}' in line or ' or dict()' in line:
                continue
            next_line = lines[i+1]
            var_match = re.match(r'\s*(\w+)\s*=', line)
            if var_match:
                var = var_match.group(1)
                if f'{var}.' in next_line and 'if ' not in next_line:
                    context = '\n'.join(lines[max(0,i-2):i+3])
                    if 'if ' + var not in context and var + ' is not None' not in context:
                        add_finding(
                            'LOW', pipeline_file, i+2,
                            f"'{var}' used without None check after assignment",
                            f"Add 'if {var}:' check before using '{var}.'"
                        )

# -- Main --
if __name__ == '__main__':
    print("=" * 70)
    print("AGENT 5: ERROR HANDLER COVERAGE")
    print("=" * 70)

    scan_bare_excepts()
    scan_missing_rollbacks()
    scan_route_error_handling()
    scan_pipeline_stage_guards()
    scan_unhandled_none()

    print(f"\nAgent 5 complete: {len(findings)} findings")

    output = PROJECT_ROOT / 'scripts' / 'audit' / 'agent5_results.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, 'w', encoding='utf-8') as f:
        json.dump(findings, f, ensure_ascii=False, indent=2)
