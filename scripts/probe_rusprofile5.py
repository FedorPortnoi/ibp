# -*- coding: utf-8 -*-
"""Probe rusprofile.ru — round 5: find manifest + all lazy chunks + actual API."""
import re, time, sys, json, requests
from bs4 import BeautifulSoup

sys.stdout.reconfigure(encoding='utf-8')

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'ru-RU,ru;q=0.9',
    'Accept': 'text/html,*/*;q=0.8',
}
s = requests.Session()
s.headers.update(HEADERS)

# ── 1. look for Vite manifest (lists ALL chunks) ──────────────────────────────
print('=== Vite manifest candidates ===')
for path in [
    '/assets/manifest.json', '/.vite/manifest.json',
    '/manifest.json', '/asset-manifest.json',
    '/assets/.vite/manifest.json',
]:
    r = s.get(f'https://www.rusprofile.ru{path}', timeout=8)
    print(f'  {r.status_code}  {path}')
    if r.status_code == 200 and 'json' in r.headers.get('Content-Type',''):
        print(r.text[:500])
    time.sleep(0.2)

# ── 2. mine app_main for ALL chunk filenames ───────────────────────────────────
print()
print('=== chunk filenames in app_main ===')
r = s.get('https://www.rusprofile.ru/assets/app_main.QIEH0mKY.js', timeout=10)
js = r.text
chunks = re.findall(r'["\`](\.?/[^""\`\s]{5,80}\.js[^""\`\s]*)["\`]', js)
unique = sorted(set(chunks))
print(f'  Found {len(unique)} chunk refs')
for c in unique:
    print(f'    {c}')

# ── 3. grep app_main for anything that looks like an API call ─────────────────
print()
print('=== API / URL patterns in app_main ===')
for pat in [
    r'["\`](/[a-z][a-z0-9/_\-]{3,60}\?[^""\`\n]{3,60})["\`]',   # paths with query string
    r'(?:url|path|endpoint|api).*?["\`]([^""\`\n]{5,80})["\`]',   # url= / path= assignments
    r'["\`](https?://[^""\`\n]{10,80})["\`]',                      # full URLs
]:
    hits = re.findall(pat, js, re.I)
    for h in sorted(set(hits))[:15]:
        print(f'  {h}')

# ── 4. deep-search the search-advanced page HTML for any data attributes ───────
print()
print('=== /search-advanced data attrs ===')
r2 = s.get('https://www.rusprofile.ru/search-advanced', timeout=10)
soup = BeautifulSoup(r2.text, 'lxml')
# data- attributes often carry API config in Vue/React SPAs
for tag in soup.find_all(True):
    for k, v in tag.attrs.items():
        if k.startswith('data-') and len(str(v)) > 3:
            print(f'  {tag.name}[{k}] = {str(v)[:80]}')

# ── 5. try the ACTUAL search via POST with JSON body ──────────────────────────
print()
print('=== JSON POST attempts ===')
endpoints = [
    '/search-advanced',
    '/api/search',
    '/api/v1/search',
    '/api/persons',
    '/api/fl/search',
]
payload = {'query': 'Иванов Иван Иванович', 'type': 'fl', 'page': 1}
for ep in endpoints:
    resp = s.post(
        f'https://www.rusprofile.ru{ep}',
        json=payload,
        headers={**HEADERS,
                 'Content-Type': 'application/json',
                 'Accept': 'application/json',
                 'X-Requested-With': 'XMLHttpRequest',
                 'Referer': 'https://www.rusprofile.ru/search-advanced'},
        timeout=8,
    )
    ct = resp.headers.get('Content-Type','')
    is_json = 'json' in ct or resp.text.strip().startswith('{')
    print(f'  {resp.status_code}  json={is_json}  {ep}')
    if is_json and resp.status_code < 400:
        print(f'  >>> {resp.text[:300]}')
    time.sleep(0.3)
