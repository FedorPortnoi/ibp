"""Probe rusprofile.ru — round 2: extract routes from JS bundle + try correct URLs."""
import re
import json
import time
import requests
from bs4 import BeautifulSoup

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
    'Accept': 'text/html,application/xhtml+xml,*/*;q=0.8',
}

s = requests.Session()
s.headers.update(HEADERS)

TEST_NAME = 'Иванов Иван Иванович'

# ── Step 1: fetch homepage to get current bundle filenames ────────────────────
print('STEP 1 — homepage')
r = s.get('https://www.rusprofile.ru/', timeout=15)
print(f'  Status: {r.status_code}')
bundles = re.findall(r'src=["\'](/assets/[^"\']+\.js)["\']', r.text)
print(f'  Bundles found: {bundles}')

# ── Step 2: try real search URLs that might work now ─────────────────────────
print()
print('STEP 2 — trying current search URL patterns')
test_urls = [
    'https://www.rusprofile.ru/search?query=Иванов+Иван+Иванович&type=fl',
    'https://www.rusprofile.ru/search?query=Иванов&type=fl',
    'https://www.rusprofile.ru/persons/search?name=Иванов+Иван+Иванович',
    'https://www.rusprofile.ru/fl/search?query=Иванов+Иван+Иванович',
    'https://www.rusprofile.ru/search?q=Иванов+Иван+Иванович&type=fl',
]
for url in test_urls:
    try:
        resp = s.get(url, timeout=10, allow_redirects=True)
        ct = resp.headers.get('Content-Type', '')
        print(f'  {resp.status_code}  {resp.url[:90]}')
        print(f'          CT: {ct[:60]}')
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'lxml')
            items = soup.select('.list-element, .search-result, [class*="person"], [class*="result"]')
            print(f'          items found: {len(items)}')
        time.sleep(0.3)
    except Exception as e:
        print(f'  ERR  {url[:70]}  {e}')

# ── Step 3: pull main JS bundle and grep for API/route patterns ───────────────
print()
print('STEP 3 — scanning JS bundle for API routes')
if bundles:
    bundle_url = f'https://www.rusprofile.ru{bundles[-1]}'
    print(f'  Fetching: {bundle_url}')
    try:
        rb = s.get(bundle_url, timeout=20)
        js = rb.text
        print(f'  Bundle size: {len(js):,} chars')

        # Find API path patterns
        api_paths = re.findall(r'["\`](/(?:api|ajax|v\d)[/a-zA-Z0-9_\-?=&]{3,80})["\`]', js)
        print(f'  API path candidates: {len(api_paths)}')
        for p in sorted(set(api_paths))[:30]:
            print(f'    {p}')

        # Find fetch/axios calls
        fetches = re.findall(r'(?:fetch|axios\.get|axios\.post)\(["\`]([^""\`]{5,100})["\`]', js)
        for f in fetches[:20]:
            print(f'  fetch/axios: {f}')

        # Find search-related strings
        search_hints = re.findall(r'["\`][^""\`]{0,20}(?:search|person|fl|suggest)[^""\`]{0,40}["\`]', js, re.I)
        for h in sorted(set(search_hints))[:30]:
            if '/' in h or 'query' in h.lower() or 'name' in h.lower():
                print(f'  search hint: {h}')
    except Exception as e:
        print(f'  ERR fetching bundle: {e}')
else:
    print('  No bundles found on homepage')
