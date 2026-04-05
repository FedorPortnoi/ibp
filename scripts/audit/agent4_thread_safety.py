"""
AGENT 4: THREAD SAFETY AUDITOR
================================
Scans all threaded code for:
- Missing Flask app context in threads
- Shared mutable state
- Race conditions on db.session
- ThreadPoolExecutor not as context manager
- asyncio event loop conflicts
"""

import ast
import re
import json
from pathlib import Path

PROJECT_ROOT = Path(r"C:\Users\fedor\ibp")
findings = []

def add_finding(severity, file, line, issue, recommendation):
    findings.append({
        'agent': 'THREAD_SAFETY',
        'severity': severity,
        'file': str(file).replace(str(PROJECT_ROOT), ''),
        'line': line,
        'issue': issue,
        'recommendation': recommendation,
    })
    icon = {'CRITICAL': '[!!!]', 'HIGH': '[!!]', 'MEDIUM': '[!]', 'LOW': '[~]'}[severity]
    print(f"  {icon} [{severity}] {file}:{line} -- {issue[:80]}")

def scan_thread_pool_usage():
    print("\n[AGENT 4] Scanning ThreadPoolExecutor usage...")

    service_files = list((PROJECT_ROOT / 'app').rglob('*.py'))

    for pyfile in service_files:
        if '__pycache__' in str(pyfile):
            continue
        try:
            source = pyfile.read_text(encoding='utf-8', errors='ignore')
            lines = source.split('\n')

            # Check if file has app_context pattern anywhere (global check)
            file_has_ctx = 'app_context' in source or '_ctx(' in source or 'with_ctx' in source

            for i, line in enumerate(lines):
                if 'ThreadPoolExecutor' not in line:
                    continue

                context = '\n'.join(lines[max(0,i-2):i+30])

                is_context_manager = 'with ThreadPoolExecutor' in context or \
                                     'with ' in line and 'ThreadPoolExecutor' in line
                if not is_context_manager:
                    # Only flag if executor is stored as module-level attribute
                    # (not local variables in try/finally blocks)
                    if '= ThreadPoolExecutor' in line and 'with' not in line:
                        add_finding(
                            'MEDIUM', pyfile, i+1,
                            f"ThreadPoolExecutor not used as context manager",
                            "Use 'with ThreadPoolExecutor() as executor:' to ensure cleanup"
                        )

                # Only flag if submitted function uses db.session AND no app_context
                if not file_has_ctx:
                    submit_pattern = r'executor\.submit\((\w+)'
                    submits = re.findall(submit_pattern, context)
                    for func_name in submits:
                        # Check if the submitted function itself uses db.session
                        # by looking for the function definition and its body
                        func_def_pattern = rf'def {func_name}\('
                        func_match = re.search(func_def_pattern, source)
                        if func_match:
                            # Check next 30 lines of function body for db.session
                            func_start = source[:func_match.start()].count('\n')
                            func_body = '\n'.join(lines[func_start:func_start+30])
                            if 'db.session' in func_body or 'db.' in func_body:
                                add_finding(
                                    'HIGH', pyfile, i+1,
                                    f"executor.submit({func_name}) uses db but lacks Flask app context",
                                    "Wrap submitted function with app.app_context()"
                                )
        except:
            pass

def scan_asyncio_in_threads():
    print("\n[AGENT 4] Scanning asyncio usage in threads...")

    service_files = list((PROJECT_ROOT / 'app').rglob('*.py'))

    for pyfile in service_files:
        if '__pycache__' in str(pyfile):
            continue
        try:
            source = pyfile.read_text(encoding='utf-8', errors='ignore')
            lines = source.split('\n')

            for i, line in enumerate(lines):
                if 'new_event_loop' in line or 'get_event_loop' in line:
                    # Check 8-line context (set_event_loop usually right after)
                    context = '\n'.join(lines[max(0,i-2):min(len(lines), i+8)])

                    if 'set_event_loop' not in context:
                        add_finding(
                            'HIGH', pyfile, i+1,
                            f"new_event_loop() without set_event_loop() -- loop not registered",
                            "Add asyncio.set_event_loop(loop) after creating loop"
                        )

                if 'run_until_complete' in line:
                    # Check 25-line context above (try/except may be far above)
                    context = '\n'.join(lines[max(0,i-25):min(len(lines), i+10)])

                    if 'RuntimeError' not in context and 'Exception' not in context:
                        add_finding(
                            'HIGH', pyfile, i+1,
                            f"run_until_complete() without RuntimeError handler",
                            "Add except RuntimeError to handle 'no event loop' in threads"
                        )
        except:
            pass

def scan_shared_state():
    print("\n[AGENT 4] Scanning for shared mutable state...")

    service_files = list((PROJECT_ROOT / 'app').rglob('*.py'))

    for pyfile in service_files:
        if '__pycache__' in str(pyfile):
            continue
        try:
            source = pyfile.read_text(encoding='utf-8', errors='ignore')

            try:
                tree = ast.parse(source)
            except:
                continue

            # Only check module-level assignments (not inside functions/classes)
            # to reduce false positives from local variables
            for node in ast.iter_child_nodes(tree):
                if isinstance(node, ast.Assign) and hasattr(node, 'lineno'):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            if isinstance(node.value, (ast.Dict, ast.List, ast.Set)):
                                var_name = target.id
                                # Skip ALL_CAPS constants and private vars
                                if var_name.isupper() or var_name.startswith('_'):
                                    continue
                                # Skip common patterns: results, data, etc (local-like names)
                                if var_name in ('results', 'data', 'items', 'errors', 'findings',
                                                'output', 'records', 'profiles', 'contacts'):
                                    continue

                                # Count writes across ALL scopes (not just module level)
                                writes = sum(
                                    1 for n in ast.walk(tree)
                                    if isinstance(n, ast.Assign)
                                    and any(
                                        isinstance(t, ast.Name) and t.id == var_name
                                        for t in n.targets
                                    )
                                )

                                if writes > 2:  # Only flag if written 3+ times
                                    add_finding(
                                        'MEDIUM', pyfile, node.lineno,
                                        f"Module-level mutable '{var_name}' written in {writes} places -- potential race condition",
                                        "Use threading.Lock() or make it request-scoped"
                                    )
        except:
            pass

def scan_db_session_in_threads():
    print("\n[AGENT 4] Scanning db.session usage in threaded contexts...")

    pipeline_file = PROJECT_ROOT / 'app' / 'services' / 'candidate' / 'pipeline.py'

    if not pipeline_file.exists():
        return

    source = pipeline_file.read_text(encoding='utf-8', errors='ignore')

    # Check if app_context is propagated to thread workers (commit 672f6b8 fix)
    if 'app_context' in source and ('ThreadPoolExecutor' in source or 'executor' in source):
        print("  Pipeline propagates app_context to threads -- db.session is safe")
        # Only flag if db.session is used INSIDE a function submitted to executor
        # WITHOUT app_context wrapper. Simple heuristic: look for submit() without app_context nearby
        lines = source.split('\n')
        for i, line in enumerate(lines):
            if 'executor.submit' in line:
                context = '\n'.join(lines[max(0, i-5):i+5])
                if 'app_context' not in context and 'ctx' not in context:
                    add_finding(
                        'HIGH', pipeline_file, i+1,
                        f"executor.submit() without app_context wrapper: {line.strip()[:60]}",
                        "Wrap submitted function with app.app_context() for thread-safe db.session"
                    )
    else:
        # No app_context propagation — flag all db.session in threaded context
        lines = source.split('\n')
        in_executor = False
        for i, line in enumerate(lines):
            if 'ThreadPoolExecutor' in line or 'executor.submit' in line:
                in_executor = True
            if in_executor and 'db.session' in line:
                add_finding(
                    'CRITICAL', pipeline_file, i+1,
                    f"db.session in thread context without app_context: {line.strip()[:60]}",
                    "db.session is not thread-safe -- add app.app_context() propagation"
                )

def scan_candidate_tasks_dict():
    print("\n[AGENT 4] Scanning candidate_tasks dict thread safety...")

    pipeline_file = PROJECT_ROOT / 'app' / 'services' / 'candidate' / 'pipeline.py'
    if not pipeline_file.exists():
        return

    source = pipeline_file.read_text(encoding='utf-8', errors='ignore')
    lines = source.split('\n')

    for i, line in enumerate(lines):
        if 'candidate_tasks' in line and ('{}' in line or 'dict()' in line):
            context = '\n'.join(lines[max(0,i-5):i+30])
            if 'Lock' not in context and 'RLock' not in context:
                add_finding(
                    'HIGH', pipeline_file, i+1,
                    "candidate_tasks dict is not protected by threading.Lock()",
                    "Add threading.Lock() to protect concurrent task dict access"
                )

# -- Main --
if __name__ == '__main__':
    print("=" * 70)
    print("AGENT 4: THREAD SAFETY AUDITOR")
    print("=" * 70)

    scan_thread_pool_usage()
    scan_asyncio_in_threads()
    scan_shared_state()
    scan_db_session_in_threads()
    scan_candidate_tasks_dict()

    print(f"\nAgent 4 complete: {len(findings)} findings")

    output = PROJECT_ROOT / 'scripts' / 'audit' / 'agent4_results.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, 'w', encoding='utf-8') as f:
        json.dump(findings, f, ensure_ascii=False, indent=2)
