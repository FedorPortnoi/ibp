"""Probe rusprofile.ru — round 3: search_results chunk + find correct search URL."""
import re
import time
import requests
from bs4 import BeautifulSoup

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
    'Accept': 'text/html,application/xhtml+xml,*/*;q=0.8',
    'Referer': 'https://www.rusprofile.ru/',
}
JSON_HEADERS = {**HEADERS, 'Accept': 'application/json, */*; q=0.01', 'X-Requested-With': 'XMLHttpRequest'}

s = requests.Session()
s.headers.update(HEADERS)

# ── Step 1: fetch search_results JS chunk ─────────────────────────────────────
print('STEP 1 — search_results chunk')
chunk_url = 'https://www.rusprofile.ru/assets/search_results.QtbrtU1E.js'
r = s.get(chunk_url, timeout=15)
print(f'  Status: {r.status_code}  Size: {len(r.text):,}')
if r.status_code == 200:
    js = r.text
    api_paths = re.findall(r'["\`](/(?:api|ajax|v\d|search|suggest|person|fl)[/a-zA-Z0-9_\-\?=&.]{2,80})["\`]', js)
    print(f'  API path candidates: {len(api_paths)}')
    for p in sorted(set(api_paths))[:40]:
        print(f'    {p}')
    fetches = re.findall(r'(?:fetch|axios)\s*[\.(]\s*["\`]([^""\`\n]{5,100})["\`]', js)
    for f in fetches[:20]:
        print(f'  fetch: {f}')
    # all strings with "search" or "query" in them
    hints = re.findall(r'["\`][^""\`\n]{0,30}(?:query|search|person|type=fl|suggest)[^""\`\n]{0,50}["\`]', js, re.I)
    for h in sorted(set(hints))[:30]:
        print(f'  hint: {h}')

# ── Step 2: fetch app_pre bundle (often has route table) ──────────────────────
print()
print('STEP 2 — app_pre bundle (route table)')
r2 = s.get('https://www.rusprofile.ru/assets/app_pre.-vaXfBKK.js', timeout=20)
print(f'  Status: {r2.status_code}  Size: {len(r2.text):,}')
if r2.status_code == 200:
    js2 = r2.text
    routes = re.findall(r'path:\s*["\`]([^""\`\n]{3,80})["\`]', js2)
    print(f'  Route paths: {len(routes)}')
    for rt in sorted(set(routes))[:40]:
        print(f'    {rt}')
    api2 = re.findall(r'["\`](/(?:api|ajax|v\d)[/a-zA-Z0-9_\-\?=&.]{2,80})["\`]', js2)
    for p in sorted(set(api2))[:20]:
        print(f'  api: {p}')

# ── Step 3: try /search-advanced and look at homepage form action ─────────────
print()
print('STEP 3 — /search-advanced + homepage form')
r3 = s.get('https://www.rusprofile.ru/search-advanced', timeout=10)
print(f'  /search-advanced: {r3.status_code}')

# Grab form action from homepage to find the real search URL
r4 = s.get('https://www.rusprofile.ru/', timeout=10)
soup = BeautifulSoup(r4.text, 'lxml')
forms = soup.find_all('form')
for f in forms:
    print(f'  form action: {f.get("action","")}  method: {f.get("method","")}')
    for inp in f.find_all('input'):
        print(f'    input name={inp.get("name","")} type={inp.get("type","")} value={inp.get("value","")}')

# Also check if there's a search input that reveals the correct URL format
search_inputs = soup.find_all('input', {'type': ['search', 'text']})
for si in search_inputs[:5]:
    print(f'  search input: {si}')

# Links on homepage that contain "search"
search_links = [a['href'] for a in soup.find_all('a', href=True) if 'search' in a.get('href','')]
for sl in search_links[:10]:
    print(f'  search link: {sl}')
