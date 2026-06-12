# -*- coding: utf-8 -*-
"""Probe rusprofile.ru — round 8: /ajax/search/advanced endpoint."""
import re, time, sys, json, requests

sys.stdout.reconfigure(encoding='utf-8')

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'ru-RU,ru;q=0.9',
}
AJAX_H = {**HEADERS, 'Accept': 'application/json, */*; q=0.01',
          'X-Requested-With': 'XMLHttpRequest',
          'Referer': 'https://www.rusprofile.ru/search-advanced'}

def fresh():
    s = requests.Session()
    s.headers.update(HEADERS)
    # warm up with page load to get session cookie
    s.get('https://www.rusprofile.ru/search-advanced', timeout=10)
    time.sleep(0.5)
    return s

# ── 1. probe /ajax/search/advanced ───────────────────────────────────────────
print('=== /ajax/search/advanced ===')
s = fresh()
for params in [
    {'query': 'Иванов Иван Иванович', 'type': 'fl'},
    {'query': 'Иванов Иван Иванович', 'type': 'person'},
    {'query': 'Иванов Иван Иванович'},
    {'name': 'Иванов Иван Иванович', 'type': 'fl'},
    {'query': 'Иванов Иван Иванович', 'searchType': 'fl'},
    {'fio': 'Иванов Иван', 'type': 'fl'},
]:
    resp = s.get('https://www.rusprofile.ru/ajax/search/advanced',
                 params=params, headers=AJAX_H, timeout=10)
    ct = resp.headers.get('Content-Type','')
    is_json = 'json' in ct or resp.text.strip()[:1] in ('{','[')
    try:
        d = resp.json()
        fl = d.get('fl', d.get('persons', d.get('people', d.get('results', '?'))))
        ul = d.get('ul', d.get('companies', '?'))
        print(f'  {resp.status_code}  keys={list(d.keys())}  fl={type(fl).__name__}:{len(fl) if isinstance(fl,list) else fl}  params={list(params.items())}')
        if isinstance(fl, list) and fl:
            print(f'  FL HIT! sample: {json.dumps(fl[0], ensure_ascii=False)[:300]}')
    except:
        print(f'  {resp.status_code}  raw={resp.text[:120]}  params={list(params.keys())}')
    time.sleep(0.4)

# ── 2. look at the advanced_search index chunk more carefully ─────────────────
print()
print('=== advanced_search/index.ts chunk — full API analysis ===')
rj = requests.get('https://www.rusprofile.ru/assets/js/pages/advanced_search/index.ts.Csqk-5xl.js', timeout=10)
js = rj.text

# find all strings that look like URL paths
all_paths = re.findall(r'["\`](/[a-zA-Z][a-zA-Z0-9/_\-?=&.]{3,80})["\`]', js)
print(f'All paths in chunk:')
for p in sorted(set(all_paths)):
    print(f'  {p}')

# find all object keys / param names
param_names = re.findall(r'["\`]([a-zA-Z_][a-zA-Z0-9_]{1,30})["\`]\s*:', js)
print(f'Param/key names used:')
for p in sorted(set(param_names))[:40]:
    print(f'  {p}')

# find complete fetch calls
fetch_full = re.findall(r'fetch\(([^)]{10,200})\)', js)
for f in fetch_full[:10]:
    print(f'  fetch call: {f[:200]}')

# find any XHR / axios patterns
xhr = re.findall(r'(?:XMLHttpRequest|axios|\.ajax)[^;]{10,200}', js)
for x in xhr[:10]:
    print(f'  xhr: {x[:150]}')

# ── 3. try action=search with very short query on fresh session ───────────────
print()
print('=== action=search fresh session — short queries ===')
s2 = fresh()
for q in ['Иванов', 'Иванов Иван', '7707123456']:
    resp = s2.get('https://www.rusprofile.ru/ajax.php',
                  params={'action': 'search', 'query': q},
                  headers={**AJAX_H, 'Referer': 'https://www.rusprofile.ru/'},
                  timeout=10)
    try:
        d = resp.json()
        keys = list(d.keys())
        ul = d.get('ul', [])
        fl = d.get('fl', [])
        print(f'  q={q!r}  code={d.get("code")}  keys={keys}  ul={len(ul) if isinstance(ul,list) else ul}  fl={len(fl) if isinstance(fl,list) else fl}')
        if ul and isinstance(ul, list):
            print(f'  UL sample keys: {list(ul[0].keys())}')
        if fl and isinstance(fl, list):
            print(f'  FL sample: {json.dumps(fl[0], ensure_ascii=False)[:200]}')
    except:
        print(f'  q={q!r}  {resp.status_code} {resp.text[:100]}')
    time.sleep(0.5)
