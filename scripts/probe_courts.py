"""Probe court sources: sudact.ru and sudebnye-resheniya."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import requests
from bs4 import BeautifulSoup
import re

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,*/*;q=0.8',
    'Accept-Language': 'ru-RU,ru;q=0.9',
}

# ── sudact.ru ──────────────────────────────────────────────────────────
print('=== sudact.ru ===')
try:
    r = requests.get(
        'https://sudact.ru/regular/doc/?regular-txt=Ivanov+Ivan',
        headers=HEADERS, timeout=12
    )
    print(f'Status: {r.status_code}, size: {len(r.text)}b')
    soup = BeautifulSoup(r.text, 'lxml')
    title = soup.find('title')
    print(f'Title: {title.text.strip()[:80] if title else None}')
    items_ul   = soup.select('ul.results > li')
    items_bsr  = soup.select('.bsr-item')
    items_tbl  = soup.select('#resultTable tr')
    print(f'ul.results>li: {len(items_ul)}, .bsr-item: {len(items_bsr)}, #resultTable tr: {len(items_tbl)}')
    page_text = soup.get_text(strip=True)
    print(f'Visible text length: {len(page_text)}')
    print(f'Snippet: {page_text[:300]}')
except Exception as e:
    print(f'sudact ERROR: {type(e).__name__}: {e}')

print()

# ── sudebnye-resheniya.rf ──────────────────────────────────────────────
print('=== sudebnye-resheniya.rf ===')
base = 'https://xn--90afdbaav0bd1afy6eub5d.xn--p1ai'
try:
    s = requests.Session()
    s.headers.update(HEADERS)
    resp = s.get(base + '/', timeout=12)
    print(f'GET /: {resp.status_code}, size: {len(resp.text)}b')

    has_field = 'simpleSearch[_token]' in resp.text
    print(f'CSRF field present: {has_field}')

    # Try all three token extraction patterns from the service
    token = None
    for pat in [
        r'name="simpleSearch\[_token\]"[^>]+value="([^"]+)"',
        r'value="([^"]+)"[^>]+name="simpleSearch\[_token\]"',
        r'id="simpleSearch__token"[^>]+value="([^"]+)"',
    ]:
        m = re.search(pat, resp.text)
        if m:
            token = m.group(1)
            print(f'Token found via pattern #{["a","b","c"][["name-first","value-first","id-based"].index(["name-first","value-first","id-based"][0 if pat.startswith("r.n") else 1 if pat.startswith("r.v") else 2])]}: length {len(token)}')
            break

    if not token:
        soup_sr = BeautifulSoup(resp.text, 'lxml')
        title_sr = soup_sr.find('title')
        print(f'Title: {title_sr.text.strip()[:80] if title_sr else None}')
        print(f'Body snippet: {soup_sr.get_text(strip=True)[:200]}')
    else:
        form_data = {
            'simpleSearch[person_info][0][person]': 'Petrov Petr Petrovich',
            'simpleSearch[person_info][0][person_status]': '',
            'simpleSearch[content]': '',
            'simpleSearch[case_number]': '',
            'simpleSearch[case_vid]': '',
            'simpleSearch[case_stage]': '',
            'simpleSearch[_token]': token,
            'simpleSearch[search]': '',
        }
        r2 = s.post(base + '/simple_filter', data=form_data, timeout=15, allow_redirects=True)
        print(f'POST /simple_filter: {r2.status_code}, size: {len(r2.text)}b')
        print(f'Final URL: {r2.url[:80]}')
        soup2 = BeautifulSoup(r2.text, 'lxml')
        count_el = soup2.select_one('div.count')
        tables = soup2.select('table.table-bordered')
        list_div = soup2.select_one('#list')
        print(f'#list present: {bool(list_div)}, tables: {len(tables)}')
        if count_el:
            print(f'Count text: {count_el.get_text(strip=True)[:80]}')
        if tables:
            print(f'Table[0]: {tables[0].get_text(" ", strip=True)[:200]}')

except Exception as e:
    print(f'SR ERROR: {type(e).__name__}: {e}')
