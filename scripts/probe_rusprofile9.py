# -*- coding: utf-8 -*-
"""Probe rusprofile.ru — round 9: POST /ajax/search/advanced + CSRF + person page."""
import re, time, sys, json, requests
from bs4 import BeautifulSoup

sys.stdout.reconfigure(encoding='utf-8')

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'ru-RU,ru;q=0.9',
}

def fresh(referer='https://www.rusprofile.ru/'):
    s = requests.Session()
    s.headers.update(HEADERS)
    r = s.get(referer, timeout=10)
    # grab any csrf token from page
    soup = BeautifulSoup(r.text, 'lxml')
    csrf = ''
    for meta in soup.find_all('meta'):
        n = meta.get('name','')
        if 'csrf' in n.lower() or 'token' in n.lower():
            csrf = meta.get('content','')
            print(f'  CSRF meta: name={n} value={csrf[:30]}')
    for inp in soup.find_all('input'):
        n = inp.get('name','')
        if 'csrf' in n.lower() or 'token' in n.lower():
            csrf = inp.get('value','')
            print(f'  CSRF input: name={n} value={csrf[:30]}')
    print(f'  Cookies after page load: {dict(s.cookies)}')
    time.sleep(0.5)
    return s, csrf

# ── 1. POST /ajax/search/advanced with JSON body ──────────────────────────────
print('=== POST /ajax/search/advanced ===')
s, csrf = fresh('https://www.rusprofile.ru/search-advanced')

bodies = [
    {'query': 'Иванов Иван Иванович', 'type': 'fl'},
    {'query': 'Иванов Иван Иванович', 'searchType': 'fl'},
    {'query': 'Иванов Иван Иванович', 'person': True},
    {'query': 'Иванов Иван Иванович'},
    {'fio': 'Иванов Иван Иванович'},
]
for body in bodies:
    hdrs = {**HEADERS,
            'Accept': 'application/json, */*',
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest',
            'Referer': 'https://www.rusprofile.ru/search-advanced',
            'Origin': 'https://www.rusprofile.ru'}
    if csrf:
        hdrs['X-CSRF-Token'] = csrf
    resp = s.post('https://www.rusprofile.ru/ajax/search/advanced',
                  json=body, headers=hdrs, timeout=10)
    try:
        d = resp.json()
        print(f'  {resp.status_code}  code={d.get("code")}  keys={list(d.keys())}  body_keys={list(body.keys())}')
        if d.get('code') not in (255, 10004) and d.get('success') is not False:
            print(f'  HIT: {json.dumps(d, ensure_ascii=False)[:400]}')
    except:
        print(f'  {resp.status_code}  {resp.text[:100]}')
    time.sleep(0.4)

# ── 2. try a real person profile URL — check if it still works ────────────────
print()
print('=== real person profile page ===')
# rusprofile person URLs look like: /person/ivanov-ii-INNLAST6
# try known patterns
s2, _ = fresh()
test_person_urls = [
    'https://www.rusprofile.ru/person/ivanov-ii-183511206113',
    'https://www.rusprofile.ru/person',
    'https://www.rusprofile.ru/search?query=Иванов&type=fl',
    'https://www.rusprofile.ru/search/fl?query=Иванов+Иван+Иванович',
    'https://www.rusprofile.ru/fl?name=Иванов+Иван+Иванович',
]
for url in test_person_urls:
    r = s2.get(url, timeout=10)
    soup = BeautifulSoup(r.text, 'lxml')
    items = soup.select('.list-element, .search-result-item, [class*="person-card"]')
    print(f'  {r.status_code}  items={len(items)}  url={url[:70]}')
    time.sleep(0.3)

# ── 3. look at the full advanced_search index chunk more carefully ─────────────
print()
print('=== advanced_search index chunk — fetch call detail ===')
rj = requests.get('https://www.rusprofile.ru/assets/js/pages/advanced_search/index.ts.Csqk-5xl.js', timeout=10)
js = rj.text
# find the actual fetch call to /ajax/search/advanced
idx = js.find('/ajax/search/advanced')
if idx >= 0:
    snippet = js[max(0, idx-300):idx+300]
    print(f'  Context around /ajax/search/advanced:')
    print(f'  {snippet}')
# find FormData or JSON body construction
formdata = re.findall(r'FormData[^;]{0,300}', js)
for f in formdata[:5]:
    print(f'  FormData: {f[:200]}')
body_constructs = re.findall(r'(?:body|data|payload)\s*[:=]\s*\{[^}]{10,200}\}', js)
for b in body_constructs[:5]:
    print(f'  body: {b[:200]}')
# find all string literals in chunk
strings = re.findall(r'["\`]([a-zA-Z_][a-zA-Z0-9_]{0,30})["\`]', js)
print(f'  All string literals: {sorted(set(strings))}')
