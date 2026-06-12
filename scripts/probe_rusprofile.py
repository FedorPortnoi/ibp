"""Probe rusprofile.ru for JSON API endpoints."""
import re
import json
import time
import requests

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
}
JSON_HEADERS = {
    **HEADERS,
    'Accept': 'application/json, text/javascript, */*; q=0.01',
    'X-Requested-With': 'XMLHttpRequest',
}

s = requests.Session()
s.headers.update(HEADERS)

TEST_NAME = 'Иванов Иван Иванович'
TEST_INN  = '7707123456'

# ── Step 1: load the FL search page, look for API hints ───────────────────────
print('=' * 60)
print('STEP 1 — FL search page')
r = s.get(
    'https://www.rusprofile.ru/search',
    params={'query': TEST_NAME, 'type': 'fl'},
    timeout=15,
)
print(f'Status: {r.status_code}  Content-Type: {r.headers.get("Content-Type","")}')

# Harvest any /api/ or /ajax/ paths from the HTML
api_paths = re.findall(r'["\'](/(?:api|ajax|search-api|suggest)[^"\']{2,80})["\']', r.text)
for p in sorted(set(api_paths))[:30]:
    print('  hint:', p)

# Any JS bundle URLs that might reveal more
bundles = re.findall(r'src=["\']([^"\']+\.js[^"\']*)["\']', r.text)
print(f'  JS bundles: {len(bundles)}')
for b in bundles[:5]:
    print('   ', b)

# ── Step 2: try common JSON search endpoints ──────────────────────────────────
print()
print('=' * 60)
print('STEP 2 — probing candidate JSON endpoints')

candidates = [
    f'https://www.rusprofile.ru/search?query={requests.utils.quote(TEST_NAME)}&type=fl',
    f'https://www.rusprofile.ru/api/search?query={requests.utils.quote(TEST_NAME)}&type=fl',
    f'https://www.rusprofile.ru/ajax/search?query={requests.utils.quote(TEST_NAME)}&type=fl',
    f'https://www.rusprofile.ru/search.json?query={requests.utils.quote(TEST_NAME)}&type=fl',
    f'https://www.rusprofile.ru/api/persons/search?query={requests.utils.quote(TEST_NAME)}',
    f'https://www.rusprofile.ru/api/fl?query={requests.utils.quote(TEST_NAME)}',
]

for url in candidates:
    try:
        resp = s.get(url, headers=JSON_HEADERS, timeout=10)
        ct = resp.headers.get('Content-Type', '')
        is_json = 'json' in ct or (resp.text.strip().startswith('{') or resp.text.strip().startswith('['))
        print(f'  {resp.status_code}  json={is_json}  {url[:80]}')
        if is_json and resp.status_code == 200:
            print('  *** JSON HIT ***')
            print(resp.text[:400])
        time.sleep(0.5)
    except Exception as e:
        print(f'  ERR  {url[:80]}  — {e}')

# ── Step 3: look at a person profile page for AJAX hints ─────────────────────
print()
print('=' * 60)
print('STEP 3 — fetch a real person profile page, look for AJAX calls')

# First get search results to find a real person href
from bs4 import BeautifulSoup
r2 = s.get(
    'https://www.rusprofile.ru/search',
    params={'query': TEST_NAME, 'type': 'fl'},
    timeout=15,
)
soup = BeautifulSoup(r2.text, 'lxml')
items = soup.select('.list-element')
print(f'  Search result items: {len(items)}')

link = None
if items:
    a = items[0].select_one('a.list-element__title')
    if a:
        link = a.get('href')
        print(f'  First person href: {link}')

if link:
    time.sleep(0.5)
    r3 = s.get(f'https://www.rusprofile.ru{link}', timeout=15)
    print(f'  Profile page status: {r3.status_code}')
    ajax_hints = re.findall(r'["\'](/(?:api|ajax|person)[^"\']{2,80})["\']', r3.text)
    for h in sorted(set(ajax_hints))[:20]:
        print('  ajax hint:', h)
    # Look for any fetch/axios calls
    fetch_urls = re.findall(r'fetch\(["\']([^"\']+)["\']', r3.text)
    for u in fetch_urls[:10]:
        print('  fetch:', u)
