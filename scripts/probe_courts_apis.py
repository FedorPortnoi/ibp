"""
Probe DataNewton court endpoints + parser-api.com with a real individual INN.

Usage:
    cd /opt/ibp && source venv/bin/activate
    python scripts/probe_courts_apis.py
"""
import os, json, sys
sys.path.insert(0, '/opt/ibp')

import requests

INN_INDIVIDUAL = '910811776518'   # Граб Артём Александрович (12 digits = физлицо)
NAME            = 'Граб Артём Александрович'
SEP = '=' * 70

# ── DataNewton ──────────────────────────────────────────────────────────────
dn_key = os.environ.get('DATANEWTON_API_KEY') or os.environ.get('DATA_NEWTON_API_KEY')
print(f"\n{SEP}")
print(f"DataNewton API key present: {bool(dn_key)}")
if dn_key:
    print(f"  Key prefix: {dn_key[:8]}...")

DN_BASE = 'https://api.datanewton.ru'
DN_HEADERS = {'Authorization': f'Bearer {dn_key}', 'Content-Type': 'application/json'} if dn_key else {}

dn_endpoints = [
    ('v1/courtCases',           {'inn': INN_INDIVIDUAL, 'limit': 10}),
    ('v1/arbitration-cases',    {'inn': INN_INDIVIDUAL, 'limit': 10}),
    ('v1/fssp',                 {'inn': INN_INDIVIDUAL, 'limit': 10}),
]

for path, params in dn_endpoints:
    print(f"\n{SEP}")
    print(f"DataNewton GET /{path}  params={params}")
    if not dn_key:
        print("  SKIP — no API key in environment")
        continue
    try:
        r = requests.get(f'{DN_BASE}/{path}', params=params, headers=DN_HEADERS, timeout=15)
        print(f"  Status: {r.status_code}")
        print(f"  Content-Type: {r.headers.get('content-type','?')}")
        try:
            body = r.json()
            print(f"  JSON keys: {list(body.keys()) if isinstance(body, dict) else f'list[{len(body)}]'}")
            if isinstance(body, dict):
                for k, v in body.items():
                    if isinstance(v, list):
                        print(f"    {k}: list of {len(v)} items")
                        if v:
                            print(f"      First item keys: {list(v[0].keys()) if isinstance(v[0], dict) else v[0]}")
                    else:
                        print(f"    {k}: {v}")
            elif isinstance(body, list):
                print(f"  {len(body)} items total")
                if body and isinstance(body[0], dict):
                    print(f"  First item keys: {list(body[0].keys())}")
                    print(f"  First item: {json.dumps(body[0], ensure_ascii=False)[:400]}")
        except Exception:
            print(f"  Raw body (first 500): {r.text[:500]}")
    except Exception as e:
        print(f"  ERROR: {e}")

# ── parser-api.com ──────────────────────────────────────────────────────────
papi_key = os.environ.get('PARSER_API_KEY') or os.environ.get('FSSP_API_TOKEN')
print(f"\n{SEP}")
print(f"parser-api.com key present: {bool(papi_key)}")
if papi_key:
    print(f"  Key prefix: {papi_key[:8]}...")

PAPI_BASE = 'https://parser-api.com'

# Check what services are available
print(f"\n--- parser-api.com: available services ---")
try:
    r = requests.get(f'{PAPI_BASE}/status/?format=json', timeout=10)
    print(f"  Status endpoint: {r.status_code}")
    if r.status_code == 200:
        try:
            print(f"  {json.dumps(r.json(), ensure_ascii=False, indent=2)[:1000]}")
        except Exception:
            print(f"  {r.text[:500]}")
except Exception as e:
    print(f"  ERROR: {e}")

# Try parser-api endpoints that might cover general courts
papi_court_candidates = [
    f'/parser/court_api/search_fiz?lastName=Граб&firstName=Артём&patronymic=Александрович',
    f'/parser/court_api/search?name={requests.utils.quote(NAME)}',
    f'/parser/sud_api/search_fiz?lastName=Граб&firstName=Артём',
    f'/parser/gcas_api/search?fio={requests.utils.quote(NAME)}',
    f'/parser/sudrf_api/search?name={requests.utils.quote(NAME)}',
]

for path in papi_court_candidates:
    url = f'{PAPI_BASE}{path}'
    if papi_key:
        url += f'&key={papi_key}' if '?' in url else f'?key={papi_key}'
    print(f"\n--- GET {PAPI_BASE}{path.split('?')[0]} ---")
    try:
        r = requests.get(url, timeout=10)
        print(f"  Status: {r.status_code}  Size: {len(r.content)}")
        if r.status_code not in (404, 403):
            try:
                body = r.json()
                print(f"  JSON: {json.dumps(body, ensure_ascii=False)[:400]}")
            except Exception:
                print(f"  Body: {r.text[:300]}")
    except Exception as e:
        print(f"  ERROR: {e}")

# Also try the usage stats to see what services we have access to
if papi_key:
    print(f"\n--- parser-api.com: usage stats ---")
    try:
        r = requests.get(f'{PAPI_BASE}/stat/?key={papi_key}', timeout=10)
        print(f"  Status: {r.status_code}")
        print(f"  {r.text[:1000]}")
    except Exception as e:
        print(f"  ERROR: {e}")

print(f"\n{SEP}")
print("PROBE COMPLETE — paste full output to Claude")
print(SEP)
