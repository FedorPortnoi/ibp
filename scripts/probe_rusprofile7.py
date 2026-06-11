# -*- coding: utf-8 -*-
"""Probe rusprofile.ru — round 7: nail down ajax.php + person search + advanced_search chunks."""
import re, time, sys, json, requests

sys.stdout.reconfigure(encoding='utf-8')

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'ru-RU,ru;q=0.9',
    'Referer': 'https://www.rusprofile.ru/',
}
AJAX_H = {**HEADERS, 'Accept': 'application/json, */*; q=0.01', 'X-Requested-With': 'XMLHttpRequest'}

s = requests.Session()
s.headers.update(HEADERS)

# ── 1. explore action=search fully ────────────────────────────────────────────
print('=== action=search — full response ===')
r = s.get('https://www.rusprofile.ru/ajax.php',
          params={'action': 'search', 'query': 'Иванов Иван Иванович', 'type': 'fl'},
          headers=AJAX_H, timeout=10)
print(f'Status: {r.status_code}')
try:
    data = r.json()
    print(f'Top-level keys: {list(data.keys())}')
    if 'ul' in data:
        print(f'ul count: {data.get("ul_count")}  sample record keys: {list(data["ul"][0].keys()) if data["ul"] else []}')
        print(json.dumps(data['ul'][0], ensure_ascii=False, indent=2) if data['ul'] else 'empty')
    if 'fl' in data:
        print(f'fl count: {data.get("fl_count")}')
        print(json.dumps(data['fl'][0], ensure_ascii=False, indent=2) if data['fl'] else 'empty')
    # print full first 2000 chars
    print('RAW:', r.text[:2000])
except Exception as e:
    print(f'Parse error: {e}  raw: {r.text[:300]}')

# ── 2. try action=search with type=fl and without ─────────────────────────────
print()
print('=== action=search type variants ===')
for params in [
    {'action': 'search', 'query': 'Иванов Иван Иванович'},
    {'action': 'search', 'query': 'Иванов Иван Иванович', 'type': 'fl'},
    {'action': 'search', 'query': 'Иванов Иван Иванович', 'searchType': 'person'},
    {'action': 'search', 'query': 'Иванов Иван Иванович', 'search_type': 'fl'},
]:
    resp = s.get('https://www.rusprofile.ru/ajax.php', params=params, headers=AJAX_H, timeout=10)
    try:
        d = resp.json()
        keys = list(d.keys())
        fl = d.get('fl', d.get('persons', d.get('people', [])))
        print(f'  {params}  -> keys={keys}  fl={len(fl) if isinstance(fl,list) else fl}')
    except:
        print(f'  {params}  -> {resp.status_code} {resp.text[:80]}')
    time.sleep(0.3)

# ── 3. fetch advanced_search JS chunks and grep for API calls ─────────────────
print()
print('=== advanced_search chunks ===')
chunk_files = [
    'js/pages/advanced_search/index.ts.Csqk-5xl.js',
    'js/pages/advanced_search/fields.ts.CHcwYuHK.js',
    'js/pages/advanced_search/renderSearchList.ts.CNLIGedw.js',
    'js/pages/fl.js.qLqt4bxl.js',
    'js/pages/search_results.js.DvIA1wKW.js',
    'js/pages/moresearch.js.CpPxtvg9.js',
]
for fn in chunk_files:
    rj = s.get(f'https://www.rusprofile.ru/assets/{fn}', timeout=10)
    print(f'  {rj.status_code}  {len(rj.text):>8,}  {fn}')
    if rj.status_code == 200 and len(rj.text) > 200:
        js = rj.text
        # ajax calls
        ajax = re.findall(r'ajax\.php[^"\'`\s]{0,100}', js)
        for a in sorted(set(ajax))[:10]:
            print(f'    ajax: {a}')
        # action= values
        actions = re.findall(r'action[=:]\s*["\`]([^""\`\n]{2,40})["\`]', js)
        for a in sorted(set(actions))[:15]:
            print(f'    action: {a}')
        # fetch/get calls
        fetches = re.findall(r'(?:fetch|\.get|\.post)\s*\(\s*["\`]([^""\`\n]{5,80})["\`]', js)
        for f in sorted(set(fetches))[:10]:
            print(f'    fetch: {f}')
        # param names
        params_found = re.findall(r'["\`](query|name|fio|lastName|firstName|inn|type|searchType|search_type|fl|person)["\`]', js)
        print(f'    param hints: {sorted(set(params_found))}')
    time.sleep(0.2)

# ── 4. try persons_search with proper Referer + session cookie ────────────────
print()
print('=== persons_search with session warm-up ===')
# warm up session by visiting the search-advanced page first
s2 = requests.Session()
s2.headers.update(HEADERS)
_ = s2.get('https://www.rusprofile.ru/search-advanced', timeout=10)
time.sleep(0.5)
for params in [
    {'action': 'persons_search', 'query': 'Иванов Иван Иванович'},
    {'action': 'persons_search', 'name': 'Иванов Иван Иванович'},
    {'action': 'persons_search', 'fio': 'Иванов Иван Иванович'},
    {'action': 'search_advanced', 'query': 'Иванов Иван Иванович', 'type': 'fl'},
]:
    resp = s2.get('https://www.rusprofile.ru/ajax.php', params=params,
                  headers={**AJAX_H, 'Referer': 'https://www.rusprofile.ru/search-advanced'},
                  timeout=10)
    try:
        d = resp.json()
        print(f'  {list(params.values())[1]}  code={d.get("code")}  success={d.get("success")}  keys={list(d.keys())}')
        if d.get('success') is not False:
            print(f'  DATA: {json.dumps(d, ensure_ascii=False)[:400]}')
    except:
        print(f'  {resp.status_code} {resp.text[:100]}')
    time.sleep(0.4)
