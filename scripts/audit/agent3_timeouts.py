"""
AGENT 3: TIMEOUT SCANNER
=========================
Scans EVERY external HTTP call, database query, and I/O operation.
Detects: missing timeouts, timeouts that are too long,
operations that can block forever.
"""

import ast
import re
import json
from pathlib import Path

PROJECT_ROOT = Path(r"C:\Users\fedor\ibp")
findings = []

def add_finding(severity, file, line, issue, recommendation):
    findings.append({
        'agent': 'TIMEOUT_SCANNER',
        'severity': severity,
        'file': str(file).replace(str(PROJECT_ROOT), ''),
        'line': line,
        'issue': issue,
        'recommendation': recommendation,
    })
    icon = {'CRITICAL': '[!!!]', 'HIGH': '[!!]', 'MEDIUM': '[!]', 'LOW': '[~]'}[severity]
    print(f"  {icon} [{severity}] {file}:{line} -- {issue[:80]}")

def scan_http_timeouts():
    print("\n[AGENT 3] Scanning HTTP request timeouts...")

    service_files = list((PROJECT_ROOT / 'app').rglob('*.py'))

    http_patterns = [
        r'requests\.(get|post|put|delete|patch|head)\(',
        r'httpx\.(get|post|put|delete|AsyncClient)\(',
        r'aiohttp\.(ClientSession|get|post)\(',
        r'urllib\.request',
        r'self\.session\.(get|post|put|delete)\(',
        r'self\._session\.(get|post|put|delete)\(',
        r'http_requests\.(get|post)\(',
        r'_requests\.(get|post)\(',
    ]
    # False positive patterns — Flask session, SQLAlchemy db.session, Telethon
    false_positive_patterns = [
        r'session\.get\([\'"]',       # Flask session.get('key')
        r'db\.session\.',             # SQLAlchemy db.session
        r'await.*client',             # Telethon client (handled separately)
        r'cls\._client',              # Telethon singleton
    ]

    for pyfile in service_files:
        if '__pycache__' in str(pyfile):
            continue
        try:
            source = pyfile.read_text(encoding='utf-8', errors='ignore')
            lines = source.split('\n')

            for i, line in enumerate(lines):
                is_http_call = any(re.search(p, line) for p in http_patterns)
                if not is_http_call:
                    continue

                # Skip false positives
                is_false_positive = any(re.search(fp, line) for fp in false_positive_patterns)
                if is_false_positive:
                    continue

                # Use 15-line context for multi-line calls
                context = '\n'.join(lines[i:min(len(lines), i+15)])

                has_timeout = 'timeout=' in context or 'Timeout(' in context

                if not has_timeout:
                    add_finding(
                        'HIGH', pyfile, i+1,
                        f"HTTP call with NO timeout: {line.strip()[:70]}",
                        "Add timeout=10 or httpx.Timeout(10.0)"
                    )
                else:
                    timeout_match = re.search(r'timeout\s*=\s*(\d+)', context)
                    if timeout_match:
                        timeout_val = int(timeout_match.group(1))
                        if timeout_val > 120:  # Only flag very long timeouts (>2min)
                            add_finding(
                                'MEDIUM', pyfile, i+1,
                                f"HTTP timeout too long: {timeout_val}s (line {i+1})",
                                f"Reduce to 15s max for external services"
                            )
        except:
            pass

def scan_telethon_timeouts():
    print("\n[AGENT 3] Scanning Telethon/Telegram timeouts...")

    tg_files = list((PROJECT_ROOT / 'app' / 'services').rglob('*.py'))

    telethon_ops = [
        r'client\.connect\(',
        r'await.*SearchRequest',
        r'await.*GetHistoryRequest',
        r'await.*ImportContactsRequest',
        r'client\(.*Request',
        r'loop\.run_until_complete',
    ]

    for pyfile in tg_files:
        if '__pycache__' in str(pyfile) or not pyfile.exists():
            continue
        try:
            source = pyfile.read_text(encoding='utf-8', errors='ignore')
            lines = source.split('\n')

            for i, line in enumerate(lines):
                is_tg_op = any(re.search(p, line) for p in telethon_ops)
                if not is_tg_op:
                    continue

                context = '\n'.join(lines[max(0,i-8):min(len(lines), i+10)])
                has_timeout = any(kw in context for kw in
                                  ['wait_for', 'timeout', 'asyncio.wait_for',
                                   'RuntimeError', 'TimeoutError'])

                if not has_timeout:
                    add_finding(
                        'CRITICAL', pyfile, i+1,
                        f"Telethon operation with NO timeout: {line.strip()[:70]}",
                        "Wrap in asyncio.wait_for(..., timeout=10)"
                    )
        except:
            pass

def scan_playwright_timeouts():
    print("\n[AGENT 3] Scanning Playwright timeouts...")

    service_files = list((PROJECT_ROOT / 'app').rglob('*.py'))

    playwright_ops = [
        r'page\.goto\(',
        r'page\.click\(',
        r'page\.fill\(',
        r'page\.wait_for_selector\(',
        r'page\.wait_for_load_state\(',
    ]
    # Exclude: page.wait_for_timeout() is a deliberate sleep, not an op needing timeout
    # Exclude: browser.new_page(), playwright.chromium.launch — not blocking on network

    for pyfile in service_files:
        if '__pycache__' in str(pyfile):
            continue
        try:
            source = pyfile.read_text(encoding='utf-8', errors='ignore')
            lines = source.split('\n')

            for i, line in enumerate(lines):
                is_pw_op = any(re.search(p, line) for p in playwright_ops)
                if not is_pw_op:
                    continue

                # Skip page.wait_for_timeout — it IS a timeout/sleep
                if 'wait_for_timeout' in line:
                    continue

                # Use 10-line context for multi-line Playwright calls
                context = '\n'.join(lines[i:min(len(lines), i+10)])
                has_timeout = 'timeout=' in context

                if not has_timeout:
                    add_finding(
                        'HIGH', pyfile, i+1,
                        f"Playwright op without timeout: {line.strip()[:70]}",
                        "Add timeout=15000 (ms) to Playwright operations"
                    )
        except:
            pass

def scan_database_timeouts():
    print("\n[AGENT 3] Scanning database operation risks...")

    service_files = list((PROJECT_ROOT / 'app').rglob('*.py'))

    for pyfile in service_files:
        if '__pycache__' in str(pyfile):
            continue
        try:
            source = pyfile.read_text(encoding='utf-8', errors='ignore')
            lines = source.split('\n')

            for i, line in enumerate(lines):
                if '.all()' in line and '.limit(' not in line:
                    # Check broader context for .limit() or .filter_by() (constrained query)
                    context = '\n'.join(lines[max(0,i-5):min(len(lines), i+3)])
                    if '.limit(' in context or '.first()' in context:
                        continue
                    # Only flag truly unbounded queries (no filter at all)
                    has_filter = '.filter(' in context or '.filter_by(' in context or \
                                 '.query.get(' in context
                    if not has_filter:
                        add_finding(
                            'MEDIUM', pyfile, i+1,
                            f"Database query with .all() and no .limit() or filter",
                            "Add .limit(1000) to prevent large result sets"
                        )
        except:
            pass

def scan_holehe_timeouts():
    print("\n[AGENT 3] Scanning Holehe timeouts...")

    # Check holehe execution entry point in email_discovery.py
    holehe_file = PROJECT_ROOT / 'app' / 'services' / 'phase2' / 'email_discovery.py'
    if not holehe_file.exists():
        print("  email_discovery.py not found")
        return

    source = holehe_file.read_text(encoding='utf-8', errors='ignore')

    # Check if the main holehe execution has a timeout
    has_timeout = ('timeout' in source.lower() and 'holehe' in source.lower()) or \
                  'shutdown' in source or 'wait_for' in source or 'cancel_futures' in source

    if not has_timeout:
        add_finding(
            'HIGH', holehe_file, 0,
            "Holehe execution has no overall timeout or shutdown mechanism",
            "Add ThreadPoolExecutor shutdown(wait=False, cancel_futures=True) with timeout"
        )
    else:
        print("  Holehe execution has timeout/shutdown protection")

# -- Main --
if __name__ == '__main__':
    print("=" * 70)
    print("AGENT 3: TIMEOUT SCANNER")
    print("=" * 70)

    scan_http_timeouts()
    scan_telethon_timeouts()
    scan_playwright_timeouts()
    scan_database_timeouts()
    scan_holehe_timeouts()

    print(f"\nAgent 3 complete: {len(findings)} findings")

    output = PROJECT_ROOT / 'scripts' / 'audit' / 'agent3_results.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, 'w', encoding='utf-8') as f:
        json.dump(findings, f, ensure_ascii=False, indent=2)
