# -*- coding: utf-8 -*-
"""Probe rusprofile.ru — round 6: full manifest + ajax.php + vendor bundle."""
import re, time, sys, json, requests

sys.stdout.reconfigure(encoding='utf-8')

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'ru-RU,ru;q=0.9',
}
JSON_H = {**HEADERS, 'Accept': 'application/json, */*; q=0.01', 'X-Requested-With': 'XMLHttpRequest'}

s = requests.Session()
s.headers.update(HEADERS)

# ── 1. full Vite manifest — find all search-related chunks ────────────────────
print('=== Vite manifest: search-related entries ===')
r = s.get('https://www.rusprofile.ru/assets/.vite/manifest.json', timeout=10)
manifest = r.json()
search_entries = {k: v for k, v in manifest.items() if any(
    x in k.lower() for x in ['search', 'person', 'fl', 'suggest', 'query', 'result']
)}
print(f'  Total manifest entries: {len(manifest)}')
print(f'  Search-related: {len(search_entries)}')
for k, v in search_entries.items():
    print(f'  {k}  ->  {v.get("file","")}')

# Also list all non-css entries
print()
print('=== All JS chunk files ===')
js_files = [(k, v['file']) for k, v in manifest.items() if v.get('file','').endswith('.js')]
for k, f in sorted(js_files, key=lambda x: x[1]):
    print(f'  {f}')

# ── 2. probe ajax.php with search-like actions ────────────────────────────────
print()
print('=== ajax.php probing ===')
base = 'https://www.rusprofile.ru/ajax.php'
actions = [
    'search', 'search_fl', 'search_person', 'suggest', 'suggest_fl',
    'search_persons', 'fl_search', 'persons_search', 'autocomplete',
    'search_advanced', 'get_persons',
]
for action in actions:
    for method in ['get', 'post']:
        params = {'action': action, 'query': 'Иванов Иван', 'type': 'fl'}
        try:
            if method == 'get':
                resp = s.get(base, params=params, headers=JSON_H, timeout=6)
            else:
                resp = s.post(base, data=params, headers=JSON_H, timeout=6)
            ct = resp.headers.get('Content-Type','')
            is_json = 'json' in ct or resp.text.strip()[:1] in ('{','[')
            snippet = resp.text[:80].replace('\n','') if resp.status_code != 404 else ''
            print(f'  {method.upper()}  {resp.status_code}  json={is_json}  action={action}  {snippet}')
            if is_json and resp.status_code == 200:
                print(f'  *** HIT *** {resp.text[:400]}')
        except Exception as e:
            print(f'  {method.upper()}  ERR  action={action}  {e}')
        time.sleep(0.2)

# ── 3. fetch the largest chunk in the manifest and grep for API paths ─────────
print()
print('=== largest JS chunk ===')
js_sizes = []
for k, v in manifest.items():
    f = v.get('file','')
    if f.endswith('.js') and not f.startswith('shared/'):
        js_sizes.append(f)

# fetch a few likely candidates
candidates = [f for f in js_sizes if any(x in f for x in ['vendor','core','search','main','app'])]
for fn in candidates[:5]:
    url = f'https://www.rusprofile.ru/assets/{fn}'
    rj = s.get(url, timeout=15)
    print(f'  {rj.status_code}  {len(rj.text):>10,}  {fn}')
    if rj.status_code == 200 and len(rj.text) > 5000:
        js = rj.text
        api_paths = re.findall(r'["\`](/(?:api|ajax|v\d|suggest)[/a-zA-Z0-9_\-?.=&]{2,60})["\`]', js)
        for p in sorted(set(api_paths))[:20]:
            print(f'      api: {p}')
        fetches = re.findall(r'\.(?:get|post)\s*\(\s*["\`]([^""\`\n]{5,80})["\`]', js)
        for f2 in sorted(set(fetches))[:20]:
            print(f'      fetch: {f2}')
    time.sleep(0.3)
