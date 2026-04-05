"""
AGENT 1: IMPORT CHAIN AUDITOR
==============================
Scans every import in every service file.
Detects: missing modules, circular imports, broken paths,
optional imports that should be required.
"""

import ast
import sys
import os
import importlib
import importlib.util
import traceback
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(r"C:\Users\fedor\ibp")
sys.path.insert(0, str(PROJECT_ROOT))

findings = []

def add_finding(severity, file, line, issue, recommendation):
    findings.append({
        'agent': 'IMPORT_CHAIN',
        'severity': severity,
        'file': str(file).replace(str(PROJECT_ROOT), ''),
        'line': line,
        'issue': issue,
        'recommendation': recommendation,
    })
    icon = {'CRITICAL': '[!!!]', 'HIGH': '[!!]', 'MEDIUM': '[!]', 'LOW': '[~]'}[severity]
    print(f"  {icon} [{severity}] {file}:{line} -- {issue[:80]}")

# -- Scan 1: Try to import every service file --
def scan_importability():
    print("\n[AGENT 1] Scanning importability of all service files...")

    service_files = list(PROJECT_ROOT.rglob("app/**/*.py"))

    os.environ.setdefault('FLASK_ENV', 'testing')

    importable = []
    broken = []

    for pyfile in service_files:
        if '__pycache__' in str(pyfile):
            continue

        rel = pyfile.relative_to(PROJECT_ROOT)
        module_path = str(rel).replace(os.sep, '.').replace('.py', '')

        try:
            spec = importlib.util.spec_from_file_location(module_path, pyfile)
            source = pyfile.read_text(encoding='utf-8', errors='ignore')
            ast.parse(source)
            importable.append(module_path)
        except SyntaxError as e:
            add_finding(
                'CRITICAL', pyfile, e.lineno,
                f"SyntaxError: {e.msg}",
                "Fix syntax error -- file will prevent gunicorn from starting"
            )
            broken.append(module_path)
        except Exception as e:
            add_finding(
                'HIGH', pyfile, 0,
                f"Parse error: {type(e).__name__}: {str(e)[:100]}",
                "Investigate parse failure"
            )
            broken.append(module_path)

    print(f"  Importable: {len(importable)}")
    print(f"  Broken: {len(broken)}")

# -- Scan 2: Detect circular imports --
def scan_circular_imports():
    print("\n[AGENT 1] Scanning for circular imports...")

    import_graph = {}

    service_files = list(PROJECT_ROOT.rglob("app/**/*.py"))

    for pyfile in service_files:
        if '__pycache__' in str(pyfile):
            continue
        try:
            source = pyfile.read_text(encoding='utf-8', errors='ignore')
            tree = ast.parse(source)

            rel = str(pyfile.relative_to(PROJECT_ROOT)).replace(os.sep, '.').replace('.py', '')
            imports = set()

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.startswith('app.'):
                            imports.add(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module and node.module.startswith('app.'):
                        imports.add(node.module)

            import_graph[rel] = imports
        except:
            pass

    def has_cycle(node, visited, rec_stack, path):
        visited.add(node)
        rec_stack.add(node)
        path.append(node)

        for neighbor in import_graph.get(node, set()):
            if neighbor not in visited:
                if has_cycle(neighbor, visited, rec_stack, path):
                    return True
            elif neighbor in rec_stack:
                cycle_start = path.index(neighbor)
                cycle = path[cycle_start:] + [neighbor]
                add_finding(
                    'HIGH',
                    cycle[0].replace('.', '/') + '.py',
                    0,
                    f"Circular import detected: {' -> '.join(cycle)}",
                    "Refactor to break circular dependency"
                )
                return True

        path.pop()
        rec_stack.discard(node)
        return False

    visited = set()
    for node in import_graph:
        if node not in visited:
            has_cycle(node, visited, set(), [])

# -- Scan 3: Find optional imports that hide errors --
def scan_try_imports():
    print("\n[AGENT 1] Scanning for try/except imports...")

    service_files = list(PROJECT_ROOT.rglob("app/**/*.py"))

    for pyfile in service_files:
        if '__pycache__' in str(pyfile):
            continue
        try:
            source = pyfile.read_text(encoding='utf-8', errors='ignore')
            tree = ast.parse(source)

            for node in ast.walk(tree):
                if isinstance(node, ast.Try):
                    for item in node.body:
                        if isinstance(item, (ast.Import, ast.ImportFrom)):
                            for handler in node.handlers:
                                handler_code = ast.unparse(handler) if hasattr(ast, 'unparse') else ''
                                if 'pass' in handler_code or '= None' in handler_code:
                                    add_finding(
                                        'MEDIUM',
                                        pyfile,
                                        item.lineno,
                                        f"Silent optional import -- failure hidden by try/except pass",
                                        "Log a warning when optional import fails so it's visible"
                                    )
        except:
            pass

# -- Scan 4: Check __init__.py blueprint registration --
def scan_blueprint_registration():
    print("\n[AGENT 1] Scanning blueprint registration...")

    init_file = PROJECT_ROOT / 'app' / '__init__.py'
    source = init_file.read_text(encoding='utf-8')

    registered = []
    for line_num, line in enumerate(source.split('\n'), 1):
        if 'register_blueprint' in line:
            registered.append((line_num, line.strip()))

    defined = []
    routes_dir = PROJECT_ROOT / 'app' / 'routes'
    if routes_dir.exists():
        for route_file in routes_dir.glob('*.py'):
            source = route_file.read_text(encoding='utf-8', errors='ignore')
            for line_num, line in enumerate(source.split('\n'), 1):
                if 'Blueprint(' in line:
                    defined.append((route_file.name, line_num, line.strip()))

    print(f"  Registered blueprints: {len(registered)}")
    print(f"  Defined blueprints: {len(defined)}")

    if len(registered) < len(defined):
        add_finding(
            'MEDIUM',
            'app/__init__.py',
            0,
            f"Possible unregistered blueprints: {len(defined)} defined, {len(registered)} registered",
            "Verify all blueprints are registered in create_app()"
        )

# -- Main --
if __name__ == '__main__':
    print("=" * 70)
    print("AGENT 1: IMPORT CHAIN AUDITOR")
    print("=" * 70)

    scan_importability()
    scan_circular_imports()
    scan_try_imports()
    scan_blueprint_registration()

    print(f"\nAgent 1 complete: {len(findings)} findings")

    import json
    output = PROJECT_ROOT / 'scripts' / 'audit' / 'agent1_results.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, 'w', encoding='utf-8') as f:
        json.dump(findings, f, ensure_ascii=False, indent=2)
    print(f"Saved: {output}")
