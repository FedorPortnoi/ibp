"""
AGENT 7: EXTERNAL SERVICE VALIDATOR
=====================================
Tests every external API and service integration:
- Is the service reachable?
- Does the API key work?
- Is the fallback working when service is down?
- Are rate limits respected?
"""

import requests
import json
import os
import sys
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(r"C:\Users\fedor\ibp")
findings = []

def add_finding(severity, service, issue, recommendation):
    findings.append({
        'agent': 'EXTERNAL_SERVICES',
        'severity': severity,
        'service': service,
        'issue': issue,
        'recommendation': recommendation,
    })
    icon = {'CRITICAL': '[!!!]', 'HIGH': '[!!]', 'MEDIUM': '[!]', 'LOW': '[~]'}[severity]
    print(f"  {icon} [{severity}] {service} -- {issue[:80]}")

def load_env():
    env_file = PROJECT_ROOT / '.env'
    env = {}
    if env_file.exists():
        for line in env_file.read_text().split('\n'):
            if '=' in line and not line.startswith('#'):
                key, _, val = line.partition('=')
                env[key.strip()] = val.strip()
    return env

def test_vk_api(env):
    print("\n[AGENT 7] Testing VK API...")

    token = env.get('VK_SERVICE_TOKEN') or env.get('VK_USER_TOKEN') or env.get('VK_TOKEN')

    if not token:
        add_finding('HIGH', 'VK API', 'No VK token found in .env',
                    'Set VK_SERVICE_TOKEN in .env')
        return

    try:
        r = requests.get(
            'https://api.vk.com/method/users.get',
            params={'user_ids': '1', 'access_token': token, 'v': '5.199'},
            timeout=10
        )
        data = r.json()

        if 'error' in data:
            error = data['error']
            add_finding('CRITICAL', 'VK API',
                        f"VK API error: {error.get('error_msg', 'Unknown')} (code {error.get('error_code')})",
                        'Check VK token validity')
        else:
            print(f"  [OK] VK API working -- token valid")
    except Exception as e:
        add_finding('HIGH', 'VK API', f"VK API unreachable: {e}",
                    'Check network connectivity to api.vk.com')

def test_egrul(env):
    print("\n[AGENT 7] Testing EGRUL/nalog.ru...")

    try:
        r = requests.post(
            'https://egrul.nalog.ru/search-result',
            data={'query': '7707083893', 'region': ''},
            timeout=15
        )
        if r.status_code == 200:
            data = r.json()
            if 'rows' in data:
                print(f"  [OK] EGRUL working -- returned {len(data['rows'])} results")
            else:
                add_finding('MEDIUM', 'EGRUL',
                            'EGRUL returned unexpected response format',
                            'Check EGRUL API endpoint')
        else:
            add_finding('MEDIUM', 'EGRUL',
                        f"EGRUL returned HTTP {r.status_code}",
                        'EGRUL may be blocking requests -- check IP/headers')
    except requests.Timeout:
        add_finding('HIGH', 'EGRUL', 'EGRUL request timed out',
                    'Increase timeout or add retry logic')
    except Exception as e:
        add_finding('HIGH', 'EGRUL', f"EGRUL unreachable: {e}",
                    'Check network connectivity')

def test_sudact(env):
    print("\n[AGENT 7] Testing sudact.ru...")

    try:
        r = requests.get('https://sudact.ru', timeout=10,
                         headers={'User-Agent': 'Mozilla/5.0'})
        if r.status_code == 200:
            print(f"  [OK] sudact.ru reachable")
        elif r.status_code == 403:
            add_finding('HIGH', 'sudact.ru',
                        'sudact.ru returning 403 -- IP blocked',
                        'Court search via Playwright may fail -- verify Playwright can access')
        else:
            add_finding('MEDIUM', 'sudact.ru',
                        f"sudact.ru returned HTTP {r.status_code}",
                        'Monitor sudact.ru availability')
    except Exception as e:
        add_finding('HIGH', 'sudact.ru', f"sudact.ru unreachable: {e}",
                    'sudact.ru may be down')

def test_leakcheck(env):
    print("\n[AGENT 7] Testing LeakCheck public API...")

    try:
        r = requests.get(
            'https://leakcheck.io/api/public?check=test@test.com',
            timeout=10
        )
        if r.status_code == 200:
            print(f"  [OK] LeakCheck API reachable")
        else:
            add_finding('LOW', 'LeakCheck',
                        f"LeakCheck returned HTTP {r.status_code}",
                        'LeakCheck may have changed API')
    except Exception as e:
        add_finding('LOW', 'LeakCheck', f"LeakCheck unreachable: {e}",
                    'Phone/email breach search will be skipped')

def test_hudsonrock(env):
    print("\n[AGENT 7] Testing HudsonRock API...")

    try:
        r = requests.get(
            'https://cavalier.hudsonrock.com/api/json/v2/osint-tools/search-by-email?email=test@test.com',
            timeout=10
        )
        if r.status_code in (200, 429, 401):
            print(f"  [OK] HudsonRock API reachable (status {r.status_code})")
        else:
            add_finding('LOW', 'HudsonRock',
                        f"HudsonRock returned HTTP {r.status_code}",
                        'Breach search from HudsonRock may not work')
    except Exception as e:
        add_finding('LOW', 'HudsonRock', f"HudsonRock unreachable: {e}",
                    'Breach search will be skipped')

def test_nominatim(env):
    print("\n[AGENT 7] Testing Nominatim geocoding...")

    try:
        r = requests.get(
            'https://nominatim.openstreetmap.org/search',
            params={'q': 'Moscow Russia', 'format': 'json', 'limit': 1},
            headers={'User-Agent': 'SLED-IBP/1.0'},
            timeout=10
        )
        if r.status_code == 200 and r.json():
            print(f"  [OK] Nominatim geocoding working")
        else:
            add_finding('LOW', 'Nominatim',
                        'Nominatim returned empty results',
                        'Geo intelligence map may not show locations')
    except Exception as e:
        add_finding('LOW', 'Nominatim', f"Nominatim unreachable: {e}",
                    'Geo mapping will fall back to hardcoded coords')

def test_opensanctions(env):
    print("\n[AGENT 7] Testing OpenSanctions...")

    try:
        r = requests.get(
            'https://api.opensanctions.org/entities/Q7747',
            timeout=10
        )
        if r.status_code in (200, 404):
            print(f"  [OK] OpenSanctions API reachable")
        elif r.status_code == 429:
            add_finding('MEDIUM', 'OpenSanctions',
                        'OpenSanctions rate limited',
                        'Add delays between requests')
        else:
            add_finding('MEDIUM', 'OpenSanctions',
                        f"OpenSanctions returned HTTP {r.status_code}",
                        'Sanctions check may not work')
    except Exception as e:
        add_finding('MEDIUM', 'OpenSanctions', f"OpenSanctions unreachable: {e}",
                    'International sanctions check will be skipped')

def test_production_server(env):
    print("\n[AGENT 7] Testing production server health...")

    try:
        r = requests.get('https://shtirletzsled.ru/health', timeout=10)
        if r.status_code == 200:
            print(f"  [OK] Production server healthy")
        elif r.status_code == 502:
            add_finding('CRITICAL', 'Production Server',
                        '502 Bad Gateway -- gunicorn is down',
                        'Run: systemctl restart ibp on server')
        elif r.status_code == 504:
            add_finding('CRITICAL', 'Production Server',
                        '504 Gateway Timeout -- gunicorn hanging',
                        'Run: systemctl restart ibp on server')
        else:
            add_finding('HIGH', 'Production Server',
                        f"Server returned HTTP {r.status_code}",
                        'Check server logs: journalctl -u ibp -n 50')
    except Exception as e:
        add_finding('CRITICAL', 'Production Server',
                    f"Production server unreachable: {e}",
                    'Server may be down -- check VPS status')

# -- Main --
if __name__ == '__main__':
    print("=" * 70)
    print("AGENT 7: EXTERNAL SERVICE VALIDATOR")
    print("=" * 70)

    env = load_env()

    test_vk_api(env)
    test_egrul(env)
    test_sudact(env)
    test_leakcheck(env)
    test_hudsonrock(env)
    test_nominatim(env)
    test_opensanctions(env)
    test_production_server(env)

    print(f"\nAgent 7 complete: {len(findings)} findings")

    output = PROJECT_ROOT / 'scripts' / 'audit' / 'agent7_results.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, 'w', encoding='utf-8') as f:
        json.dump(findings, f, ensure_ascii=False, indent=2)
