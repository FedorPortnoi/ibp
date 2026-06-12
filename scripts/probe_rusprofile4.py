# -*- coding: utf-8 -*-
"""Probe rusprofile.ru — round 4."""
import re, time, sys, requests
from bs4 import BeautifulSoup

# force utf-8 output
sys.stdout.reconfigure(encoding='utf-8')

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
    'Accept': 'text/html,application/xhtml+xml,*/*;q=0.8',
}
JSON_H = {**HEADERS, 'Accept': 'application/json, */*; q=0.01', 'X-Requested-With': 'XMLHttpRequest'}

s = requests.Session()
s.headers.update(HEADERS)

# ── 1. main.js page chunk (has page-level logic) ──────────────────────────────
print('=== main.js chunk ===')
r = s.get('https://www.rusprofile.ru/assets/js/pages/main.js.vOBQBPma.js', timeout=15)
print(f'Status: {r.status_code}  Size: {len(r.text):,}')
js = r.text
for p in sorted(set(re.findall(r'["\`](/[a-zA-Z0-9/_\-?=&.]{4,80})["\`]', js)))[:40]:
    print(f'  path: {p}')

# ── 2. search-advanced page — pull form + any JSON refs ───────────────────────
print()
print('=== /search-advanced ===')
r2 = s.get('https://www.rusprofile.ru/search-advanced', timeout=15)
print(f'Status: {r2.status_code}')
soup = BeautifulSoup(r2.text, 'lxml')
for form in soup.find_all('form'):
    print(f'  form action={form.get("action","")} method={form.get("method","")}')
    for i in form.find_all('input'):
        print(f'    input: name={i.get("name","")} type={i.get("type","")}')
# any links that look like search
for a in soup.find_all('a', href=True):
    h = a['href']
    if any(x in h for x in ['search','person','fl','query']):
        print(f'  link: {h}')
# new JS chunks referenced
chunks = re.findall(r'src=["\'](/assets/[^"\']+\.js)["\']', r2.text)
print(f'  chunks on page: {chunks}')

# ── 3. try the correct search URL found via /search-advanced ─────────────────
print()
print('=== trying search URL variants with Referer ===')
candidates = [
    'https://www.rusprofile.ru/search-advanced?query=Иванов+Иван+Иванович&searchType=person',
    'https://www.rusprofile.ru/search-advanced?name=Иванов+Иван+Иванович',
    'https://www.rusprofile.ru/search-advanced?query=Иванов&type=person',
    'https://www.rusprofile.ru/persons?query=Иванов+Иван+Иванович',
    'https://www.rusprofile.ru/person?query=Иванов+Иван+Иванович',
]
for url in candidates:
    resp = s.get(url, headers={**HEADERS, 'Referer': 'https://www.rusprofile.ru/'}, timeout=10)
    ct = resp.headers.get('Content-Type', '')
    soup2 = BeautifulSoup(resp.text, 'lxml')
    items = soup2.select('.list-element')
    is_json = resp.text.strip().startswith('{') or resp.text.strip().startswith('[')
    print(f'  {resp.status_code}  items={len(items)}  json={is_json}  {url[:80]}')
    time.sleep(0.4)

# ── 4. POST to /search-advanced ───────────────────────────────────────────────
print()
print('=== POST /search-advanced ===')
for payload in [
    {'query': 'Иванов Иван Иванович', 'type': 'fl'},
    {'name': 'Иванов Иван Иванович'},
    {'search': 'Иванов Иван Иванович', 'searchType': 'person'},
]:
    resp = s.post('https://www.rusprofile.ru/search-advanced',
                  data=payload,
                  headers={**JSON_H, 'Referer': 'https://www.rusprofile.ru/search-advanced'},
                  timeout=10)
    ct = resp.headers.get('Content-Type','')
    is_json = 'json' in ct or resp.text.strip().startswith('{')
    print(f'  {resp.status_code}  json={is_json}  ct={ct[:40]}  payload={list(payload.keys())}')
    if is_json:
        print(f'  RESPONSE: {resp.text[:300]}')
    time.sleep(0.4)

# ── 5. scan ALL assets listed on homepage for bigger bundles ─────────────────
print()
print('=== all asset chunks on homepage ===')
r5 = s.get('https://www.rusprofile.ru/', timeout=10)
all_js = re.findall(r'["\'](/assets/[^"\']+\.js)["\']', r5.text)
for j in sorted(set(all_js)):
    rj = s.get(f'https://www.rusprofile.ru{j}', timeout=10)
    print(f'  {rj.status_code}  {len(rj.text):>8,}  {j}')
    time.sleep(0.2)
