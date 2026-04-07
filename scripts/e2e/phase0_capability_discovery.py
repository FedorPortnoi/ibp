"""
PHASE 0: CAPABILITY DISCOVERY
==============================
Discover what the system can find before running candidate tests.
Sets the minimum standard for all subsequent test phases.
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
REPORT_FILE = Path(r"C:\Users\fedor\ibp\.e2e_test\capability_report.json")

with open(CONFIG_FILE, encoding='utf-8') as _f:
    _config = json.load(_f)
BASE_URL = _config['base_url']
USERNAME = _config['username']
PASSWORD = _config['password']

SESSION = requests.Session()
CSRF_TOKEN = ''
capabilities = {}


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
    print(f"OK Authenticated as {USERNAME}")
    return True


def probe_endpoints():
    endpoints = [
        ("GET",  "/candidate/new",              "New check form"),
        ("GET",  "/candidate/history",           "Check history"),
        ("GET",  "/health",                       "Health check"),
    ]

    alive = []
    dead = []
    for method, path, label in endpoints:
        try:
            r = SESSION.get(f"{BASE_URL}{path}", timeout=10)
            status = "OK" if r.status_code < 500 else "FAIL"
            alive.append((path, label, r.status_code))
            print(f"  {status} {method} {path} [{label}] -> {r.status_code}")
        except Exception as e:
            dead.append((path, label, str(e)))
            print(f"  FAIL {method} {path} [{label}] -> ERROR: {e}")

    capabilities['endpoints'] = {'alive': alive, 'dead': dead}


def start_candidate(payload):
    """Submit a candidate check. Returns (check_id, task_id) or (None, None)."""
    headers = {
        'X-CSRFToken': CSRF_TOKEN,
        'Content-Type': 'application/json',
        'Referer': f'{BASE_URL}/candidate/new',
    }
    r = SESSION.post(f"{BASE_URL}/candidate/start", json=payload, headers=headers, timeout=30)
    if r.status_code != 200:
        print(f"  Start failed: HTTP {r.status_code} — {r.text[:200]}")
        return None, None
    data = r.json()
    return data.get('check_id'), data.get('task_id')


def poll_to_completion(check_id, task_id, max_wait=300):
    """Poll progress until complete or timeout. Returns final status."""
    start = time.time()
    last_pct = -1

    while time.time() - start < max_wait:
        try:
            r = SESSION.get(f"{BASE_URL}/candidate/progress/{task_id}/status", timeout=15)
            if r.status_code == 404:
                print(f"  Progress 404 for task {task_id}")
                return 'error'
            if r.status_code != 200:
                time.sleep(20)
                continue

            prog = r.json()
            pct = prog.get('percent_complete', 0)
            status = prog.get('status', '?')

            if pct != last_pct:
                stage = prog.get('current_stage', '?')
                print(f"  [{pct:3d}%] {stage}")
                last_pct = pct

            if status in ('complete', 'done'):
                return 'complete'
            if status == 'error':
                return 'error'

        except requests.Timeout:
            pass
        except Exception as e:
            print(f"  Poll error: {e}")

        time.sleep(20)  # Slow polling to avoid 429 rate limits

    return 'timeout'


def detect_sources_with_data(dossier):
    sources = {}

    # EGRUL / Business
    biz = dossier.get('business_records', [])
    sources['EGRUL'] = 'REAL' if biz else 'EMPTY'

    # Courts
    courts = dossier.get('court_records', [])
    sources['COURTS'] = 'REAL' if courts else 'EMPTY'

    # FSSP
    fssp = dossier.get('fssp_records', [])
    sources['FSSP'] = 'REAL' if fssp else 'EMPTY'

    # VK
    vk = dossier.get('social_media_profiles', [])
    if vk:
        demo_ids = {'123456789', '987654321', '111111111'}
        vk_ids = set()
        for p in (vk if isinstance(vk, list) else []):
            vk_ids.add(str(p.get('vk_id', p.get('platform_id', ''))))
        sources['VK'] = 'DEMO' if vk_ids & demo_ids else 'REAL'
    else:
        sources['VK'] = 'EMPTY'

    # Sanctions
    sanctions = dossier.get('sanctions_results', [])
    sources['SANCTIONS'] = 'REAL' if sanctions else 'EMPTY'

    # Contacts
    contacts = dossier.get('contact_discoveries', {})
    sources['CONTACTS'] = 'REAL' if contacts else 'EMPTY'

    # Risk score
    risk_data = dossier.get('risk_assessment', {})
    risk = risk_data.get('risk_score', 0)
    sources['RISK_SCORE'] = 'REAL' if risk else 'EMPTY'

    # Geo
    geo = dossier.get('geo_intelligence', {})
    sources['GEO'] = 'REAL' if geo else 'EMPTY'

    for src, status in sources.items():
        icon = 'OK' if status == 'REAL' else ('WARN' if status == 'DEMO' else 'EMPTY')
        print(f"  {icon} {src}: {status}")

    return sources


def probe_data_sources():
    """Run a test check on a known candidate to discover system capabilities."""
    print("\nProbing data sources with known test candidate (Sudin)...")

    payload = {
        "full_name": "Судин Артем Алексеевич",
        "date_of_birth": "1990-11-29",
        "inn": "232308435186",
        "passport": "0319 231799",
        "phone": "+79676573634",
        "registered_address": "г. Абинск ул. Мира д. 222",
        "check_mode": "quick",
        "pd_consent": True
    }

    check_id, task_id = start_candidate(payload)
    if not check_id:
        print("  FAIL: Could not start probe candidate")
        return

    print(f"  Task ID: {task_id}, Check ID: {check_id}")

    status = poll_to_completion(check_id, task_id, max_wait=300)
    print(f"  Pipeline status: {status}")

    # Wait a bit for report generation
    time.sleep(5)

    # Fetch dossier JSON
    r = SESSION.get(f"{BASE_URL}/candidate/export/{check_id}/json", timeout=30)
    if r.status_code == 200:
        dossier = r.json()
        print(f"\n  Dossier fields: {len(dossier)}")
        print(f"  Top-level keys: {list(dossier.keys())}")

        sources = detect_sources_with_data(dossier)
        capabilities['probe_candidate'] = {
            'name': 'Судин Артем Алексеевич',
            'check_id': check_id,
            'dossier_keys': list(dossier.keys()),
            'sources_with_data': sources
        }
    else:
        print(f"  WARN: Could not export dossier: {r.status_code}")


if __name__ == '__main__':
    print("=" * 70)
    print("PHASE 0: CAPABILITY DISCOVERY")
    print("=" * 70)

    authenticate()
    probe_endpoints()
    probe_data_sources()

    capabilities['timestamp'] = datetime.utcnow().isoformat()
    with open(REPORT_FILE, 'w', encoding='utf-8') as f:
        json.dump(capabilities, f, ensure_ascii=False, indent=2, default=str)

    print(f"\nCapability report saved: {REPORT_FILE}")
    sources = capabilities.get('probe_candidate', {}).get('sources_with_data', {})
    real_sources = [s for s, v in sources.items() if v == 'REAL']
    demo_sources = [s for s, v in sources.items() if v == 'DEMO']
    empty_sources = [s for s, v in sources.items() if v == 'EMPTY']
    print(f"  REAL: {', '.join(real_sources)}")
    print(f"  DEMO: {', '.join(demo_sources)}")
    print(f"  EMPTY: {', '.join(empty_sources)}")
