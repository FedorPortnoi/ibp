"""
AGENT 1: CANDIDATE RUNNER
==========================
Runs all 10 candidates through the pipeline.
Records everything. Does NOT analyze - just runs and saves.
"""

import requests
import json
import time
import os
from pathlib import Path
from datetime import datetime
from bs4 import BeautifulSoup

CONFIG_FILE = Path(r"C:\Users\fedor\ibp\.e2e_test\config.json")
CANDIDATES_FILE = Path(r"C:\Users\fedor\ibp\.e2e_test\e2e_candidates.json")
OUTPUT_DIR = Path(r"C:\Users\fedor\ibp\.e2e_test\runs")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

with open(CONFIG_FILE, encoding='utf-8') as _f:
    _config = json.load(_f)
BASE_URL = _config['base_url']
USERNAME = _config['username']
PASSWORD = _config['password']

SESSION = requests.Session()
CSRF_TOKEN = ''


def authenticate():
    global CSRF_TOKEN

    # Step 1: GET login page for initial CSRF
    r = SESSION.get(f"{BASE_URL}/login", timeout=10)
    soup = BeautifulSoup(r.text, 'html.parser')
    csrf_input = soup.find('input', {'name': 'csrf_token'})
    login_csrf = csrf_input['value'] if csrf_input else ''

    # Step 2: POST login (session regenerated — old CSRF invalidated)
    r = SESSION.post(f"{BASE_URL}/login", data={
        'username': USERNAME,
        'password': PASSWORD,
        'csrf_token': login_csrf,
    }, headers={'Referer': f'{BASE_URL}/login'}, allow_redirects=True, timeout=10)

    assert 'candidate' in r.url or 'new' in r.url, f"Login failed: ended at {r.url}"

    # Step 3: Extract fresh CSRF from post-login page (candidate/new)
    soup = BeautifulSoup(r.text, 'html.parser')
    meta_csrf = soup.find('meta', {'name': 'csrf-token'})
    if meta_csrf:
        CSRF_TOKEN = meta_csrf.get('content', '')
    else:
        csrf_input = soup.find('input', {'name': 'csrf_token'})
        CSRF_TOKEN = csrf_input['value'] if csrf_input else ''

    assert CSRF_TOKEN, "Could not extract post-login CSRF token"
    print("OK Authenticated")


def run_candidate(candidate):
    """Submit candidate, poll to completion, fetch dossier. Returns run record."""
    name = candidate['full_name']
    cid = candidate['id']
    print(f"\n{'='*60}")
    print(f"CANDIDATE {cid}: {name}")
    print(f"{'='*60}")

    run_record = {
        'candidate_id': cid,
        'full_name': name,
        'started_at': datetime.utcnow().isoformat(),
        'progress_log': [],
        'errors': [],
        'warnings': [],
        'final_status': None,
        'check_id': None,
        'task_id': None,
        'export_json': None,
        'duration_seconds': 0,
    }

    start_time = time.time()

    # Build payload matching the actual API
    inn = candidate.get('inn', '').strip()

    # INN is required by the API — if missing, expect rejection
    if not inn:
        run_record['warnings'].append('No INN provided — API will reject')

    payload = {
        "full_name": candidate['full_name'],
        "date_of_birth": candidate['date_of_birth'],
        "inn": inn,
        "passport": candidate.get('passport', ''),
        "phone": candidate.get('phone', ''),
        "registered_address": candidate.get('address', ''),
        "region": candidate.get('region', ''),
        "check_mode": "quick",
        "pd_consent": True,
    }

    # Submit
    try:
        headers = {
            'X-CSRFToken': CSRF_TOKEN,
            'Content-Type': 'application/json',
            'Referer': f'{BASE_URL}/candidate/new',
        }
        r = SESSION.post(f"{BASE_URL}/candidate/start", json=payload, headers=headers, timeout=30)

        if r.status_code != 200:
            error_text = r.text[:300]
            run_record['errors'].append(f"START FAILED: HTTP {r.status_code} — {error_text}")

            # Check if INN rejection (expected for candidate 9)
            if r.status_code == 400 and not inn:
                run_record['final_status'] = 'INN_REQUIRED_REJECTED'
                run_record['warnings'].append('Expected: API rejects empty INN')
            else:
                run_record['final_status'] = 'START_FAILED'
            run_record['duration_seconds'] = round(time.time() - start_time, 1)
            return run_record

        data = r.json()
        task_id = data.get('task_id')
        check_id = data.get('check_id')
        run_record['task_id'] = task_id
        run_record['check_id'] = check_id
        print(f"  > Pipeline started | task_id={task_id} check_id={check_id}")

    except Exception as e:
        run_record['errors'].append(f"START EXCEPTION: {e}")
        run_record['final_status'] = 'EXCEPTION'
        run_record['duration_seconds'] = round(time.time() - start_time, 1)
        return run_record

    # Poll progress (slow polling to avoid 429 rate limits)
    MAX_WAIT = 420  # 7 minutes
    HANG_THRESHOLD = 240  # 4 min at same %
    last_pct = -1
    last_pct_time = time.time()
    seen_msgs = set()

    while time.time() - start_time < MAX_WAIT:
        try:
            r = SESSION.get(
                f"{BASE_URL}/candidate/progress/{task_id}/status",
                timeout=15
            )
            if r.status_code == 404:
                run_record['errors'].append("PROGRESS 404 — task_id not found")
                break
            if r.status_code == 429:
                time.sleep(30)  # Back off on rate limit
                continue
            if r.status_code != 200:
                run_record['warnings'].append(f"PROGRESS HTTP {r.status_code}")
                time.sleep(20)
                continue

            prog = r.json()
            pct = prog.get('percent_complete', 0)
            stage = prog.get('current_stage', '?')
            status = prog.get('status', '?')
            messages = prog.get('messages', [])

            # Log new messages
            for msg in messages:
                text = msg.get('text', str(msg)) if isinstance(msg, dict) else str(msg)
                if text not in seen_msgs:
                    seen_msgs.add(text)
                    ts = datetime.utcnow().isoformat()
                    run_record['progress_log'].append({
                        'time': ts,
                        'pct': pct,
                        'msg': text,
                    })
                    print(f"  [{pct:3d}%] {text}")

                    # Detect errors in messages
                    msg_lower = text.lower()
                    if any(w in msg_lower for w in ['error', 'exception', 'traceback', 'attributeerror']):
                        run_record['errors'].append(f"PIPELINE ERROR @ {pct}%: {text}")
                    if any(w in msg_lower for w in ['timeout', 'недоступен', 'геоблок', 'unavailable']):
                        run_record['warnings'].append(f"SERVICE ISSUE @ {pct}%: {text}")

            # Hang detection
            if pct != last_pct:
                last_pct = pct
                last_pct_time = time.time()
            else:
                hung_for = time.time() - last_pct_time
                if hung_for > HANG_THRESHOLD:
                    run_record['warnings'].append(
                        f"PIPELINE HANG: stuck at {pct}% for {hung_for:.0f}s"
                    )
                    print(f"  WARN HANG: {pct}% for {hung_for:.0f}s")

            # Completion
            if status in ('complete', 'done'):
                run_record['final_status'] = 'COMPLETE'
                print(f"  OK Pipeline complete at {pct}%")
                break

            if status == 'error':
                run_record['final_status'] = 'PIPELINE_ERROR'
                error_msg = prog.get('error', 'Unknown error')
                run_record['errors'].append(f"Pipeline error: {error_msg}")
                break

        except requests.Timeout:
            run_record['warnings'].append("Progress poll timeout")
        except Exception as e:
            run_record['errors'].append(f"POLL EXCEPTION: {e}")

        time.sleep(20)  # Slow polling to avoid 429 rate limits (50/hr global)

    if run_record['final_status'] is None:
        run_record['final_status'] = 'TIMEOUT'
        run_record['errors'].append(f"Timed out after {MAX_WAIT}s")
        print(f"  FAIL TIMEOUT after {MAX_WAIT}s")

    # Fetch dossier JSON
    if check_id and run_record['final_status'] in ('COMPLETE', 'TIMEOUT', 'PIPELINE_ERROR'):
        time.sleep(3)  # Let report generation finish
        try:
            r = SESSION.get(
                f"{BASE_URL}/candidate/export/{check_id}/json",
                timeout=30
            )
            if r.status_code == 200:
                run_record['export_json'] = r.json()
                print(f"  Dossier exported: {len(r.text)} bytes")
            else:
                run_record['warnings'].append(f"Export failed: HTTP {r.status_code}")
        except Exception as e:
            run_record['warnings'].append(f"Export exception: {e}")

    run_record['duration_seconds'] = round(time.time() - start_time, 1)
    run_record['completed_at'] = datetime.utcnow().isoformat()
    return run_record


def save_run(run_record):
    cid = run_record['candidate_id']
    name = run_record['full_name'].replace(' ', '_')
    filename = OUTPUT_DIR / f"run_{cid:02d}_{name}.json"
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(run_record, f, ensure_ascii=False, indent=2)
    print(f"  Saved: {filename.name}")
    return filename


if __name__ == '__main__':
    print("=" * 70)
    print("AGENT 1: RUNNER — ALL 10 CANDIDATES")
    print("=" * 70)

    with open(CANDIDATES_FILE, encoding='utf-8') as f:
        candidates = json.load(f)

    authenticate()

    summary = []
    for candidate in candidates:
        run = run_candidate(candidate)
        save_run(run)
        summary.append({
            'id': candidate['id'],
            'name': candidate['full_name'],
            'status': run['final_status'],
            'duration': run['duration_seconds'],
            'errors': len(run['errors']),
            'warnings': len(run['warnings']),
            'check_id': run['check_id'],
        })
        # Brief pause between candidates
        print(f"\n  Waiting 10s before next candidate...")
        time.sleep(10)

    # Print summary
    print("\n" + "=" * 70)
    print("RUNNER SUMMARY")
    print("=" * 70)
    for s in summary:
        icon = 'OK' if s['status'] == 'COMPLETE' else 'FAIL'
        print(f"{icon} [{s['id']:02d}] {s['name'][:40]:<40} "
              f"{s['status']:<20} {s['duration']:>5.0f}s "
              f"E:{s['errors']} W:{s['warnings']}")

    summary_file = OUTPUT_DIR / "run_summary.json"
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"\nSummary: {summary_file}")
