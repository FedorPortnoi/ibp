"""
AGENT 8: MEMORY & PERFORMANCE SCANNER
========================================
Scans for:
- Memory leaks (unbounded growth)
- File handles not closed
- Large in-memory data structures
- Blocking operations on main thread
- Missing cleanup on task completion
"""

import ast
import re
import json
from pathlib import Path

PROJECT_ROOT = Path(r"C:\Users\fedor\ibp")
findings = []

def add_finding(severity, file, line, issue, recommendation):
    findings.append({
        'agent': 'PERFORMANCE',
        'severity': severity,
        'file': str(file).replace(str(PROJECT_ROOT), ''),
        'line': line,
        'issue': issue,
        'recommendation': recommendation,
    })
    icon = {'CRITICAL': '[!!!]', 'HIGH': '[!!]', 'MEDIUM': '[!]', 'LOW': '[~]'}[severity]
    print(f"  {icon} [{severity}] {file}:{line} -- {issue[:80]}")

def scan_file_handles():
    print("\n[AGENT 8] Scanning for unclosed file handles...")

    service_files = list((PROJECT_ROOT / 'app').rglob('*.py'))

    for pyfile in service_files:
        if '__pycache__' in str(pyfile):
            continue
        try:
            source = pyfile.read_text(encoding='utf-8', errors='ignore')
            lines = source.split('\n')

            for i, line in enumerate(lines):
                if re.search(r'open\(', line) and 'with open' not in line:
                    context = '\n'.join(lines[i:min(len(lines), i+20)])
                    if '.close()' not in context and 'with' not in line:
                        add_finding(
                            'MEDIUM', pyfile, i+1,
                            f"File opened without 'with' statement -- may not be closed",
                            "Use 'with open(...) as f:' to ensure file is closed"
                        )
        except:
            pass

def scan_candidate_tasks_growth():
    print("\n[AGENT 8] Scanning candidate_tasks cleanup...")

    pipeline_file = PROJECT_ROOT / 'app' / 'services' / 'candidate' / 'pipeline.py'
    if not pipeline_file.exists():
        return

    source = pipeline_file.read_text(encoding='utf-8', errors='ignore')

    has_cleanup = 'cleanup' in source.lower() and 'candidate_tasks' in source
    if not has_cleanup:
        add_finding(
            'HIGH', pipeline_file, 0,
            "No cleanup mechanism for candidate_tasks dict -- unbounded memory growth",
            "Add periodic cleanup to remove completed tasks older than 1 hour"
        )

    cleanup_match = re.search(r'cleanup.*?(\d+)', source)
    if cleanup_match:
        interval = int(cleanup_match.group(1))
        if interval > 7200:
            add_finding(
                'MEDIUM', pipeline_file, 0,
                f"Task cleanup interval is {interval}s -- tasks kept too long",
                "Reduce cleanup interval to 3600s (1 hour)"
            )

def scan_large_json_serialization():
    print("\n[AGENT 8] Scanning for large JSON serialization...")

    service_files = list((PROJECT_ROOT / 'app').rglob('*.py'))

    for pyfile in service_files:
        if '__pycache__' in str(pyfile):
            continue
        try:
            source = pyfile.read_text(encoding='utf-8', errors='ignore')
            lines = source.split('\n')

            for i, line in enumerate(lines):
                if 'json.dumps' in line or 'json.dump' in line:
                    context = '\n'.join(lines[max(0,i-5):i+2])
                    if any(large in context for large in
                           ['court_records', 'vk_posts', 'social_profiles',
                            'friends', 'behavioral']):
                        add_finding(
                            'LOW', pyfile, i+1,
                            f"Potentially large JSON serialization at line {i+1}",
                            "Consider limiting records count before serialization"
                        )
        except:
            pass

def scan_blocking_main_thread():
    print("\n[AGENT 8] Scanning for blocking operations on main thread...")

    routes_dir = PROJECT_ROOT / 'app' / 'routes'
    if not routes_dir.exists():
        return

    blocking_patterns = [
        r'time\.sleep\(',
        r'requests\.(get|post)',
        r'subprocess\.',
        r'os\.system\(',
    ]

    for route_file in routes_dir.glob('*.py'):
        try:
            source = route_file.read_text(encoding='utf-8', errors='ignore')
            lines = source.split('\n')

            in_route_func = False
            for i, line in enumerate(lines):
                if re.match(r'def \w+\(', line):
                    in_route_func = True

                if in_route_func:
                    for pattern in blocking_patterns:
                        if re.search(pattern, line):
                            add_finding(
                                'MEDIUM', route_file, i+1,
                                f"Potentially blocking operation in route: {line.strip()[:60]}",
                                "Move heavy operations to background thread"
                            )
        except:
            pass

def scan_playwright_browser_cleanup():
    print("\n[AGENT 8] Scanning Playwright browser cleanup...")

    service_files = list((PROJECT_ROOT / 'app').rglob('*.py'))

    for pyfile in service_files:
        if '__pycache__' in str(pyfile):
            continue
        try:
            source = pyfile.read_text(encoding='utf-8', errors='ignore')

            if 'playwright' not in source.lower() and 'browser' not in source.lower():
                continue

            lines = source.split('\n')

            for i, line in enumerate(lines):
                if 'browser.launch()' in line or 'chromium.launch()' in line:
                    context = '\n'.join(lines[i:min(len(lines), i+50)])
                    has_close = 'browser.close()' in context or 'await browser.close' in context
                    has_with = 'async with playwright' in context or 'with sync_playwright' in context

                    if not has_close and not has_with:
                        add_finding(
                            'HIGH', pyfile, i+1,
                            f"Browser launched but browser.close() not found nearby",
                            "Always close browser in finally block to prevent memory leaks"
                        )
        except:
            pass

# -- Main --
if __name__ == '__main__':
    print("=" * 70)
    print("AGENT 8: MEMORY & PERFORMANCE SCANNER")
    print("=" * 70)

    scan_file_handles()
    scan_candidate_tasks_growth()
    scan_large_json_serialization()
    scan_blocking_main_thread()
    scan_playwright_browser_cleanup()

    print(f"\nAgent 8 complete: {len(findings)} findings")

    output = PROJECT_ROOT / 'scripts' / 'audit' / 'agent8_results.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, 'w', encoding='utf-8') as f:
        json.dump(findings, f, ensure_ascii=False, indent=2)
