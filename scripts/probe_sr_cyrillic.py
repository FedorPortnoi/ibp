"""Verify судебныерешения.рф with a Cyrillic name."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import requests, re
from bs4 import BeautifulSoup

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,*/*;q=0.8',
    'Accept-Language': 'ru-RU,ru;q=0.9',
}

base = 'https://xn--90afdbaav0bd1afy6eub5d.xn--p1ai'
s = requests.Session()
s.headers.update(HEADERS)

resp = s.get(base + '/', timeout=12)
token = None
for pat in [
    r'name="simpleSearch\[_token\]"[^>]+value="([^"]+)"',
    r'value="([^"]+)"[^>]+name="simpleSearch\[_token\]"',
    r'id="simpleSearch__token"[^>]+value="([^"]+)"',
]:
    m = re.search(pat, resp.text)
    if m:
        token = m.group(1)
        break

if not token:
    print('NO TOKEN')
    sys.exit(1)

form_data = {
    'simpleSearch[person_info][0][person]': 'Иванов Иван Иванович',
    'simpleSearch[person_info][0][person_status]': '',
    'simpleSearch[content]': '',
    'simpleSearch[case_number]': '',
    'simpleSearch[case_vid]': '',
    'simpleSearch[case_stage]': '',
    'simpleSearch[_token]': token,
    'simpleSearch[search]': '',
}
r2 = s.post(base + '/simple_filter', data=form_data, timeout=20, allow_redirects=True)
print(f'POST: {r2.status_code}, size: {len(r2.text)}b, url: {r2.url[:80]}')
soup = BeautifulSoup(r2.text, 'lxml')
count_el = soup.select_one('div.count')
tables = soup.select('table.table-bordered')
print(f'Count: {count_el.get_text(strip=True) if count_el else None}')
print(f'Tables: {len(tables)}')
if tables:
    for i, t in enumerate(tables[:2]):
        rows = t.select('tr')
        print(f'  Table {i}: {len(rows)} rows')
        for row in rows[:2]:
            print(f'    Row: {row.get_text(" ", strip=True)[:120]}')
        links = t.select('a[href]')
        if links:
            for lnk in links[:2]:
                print('    Link: ' + lnk.get_text(strip=True)[:40] + ' -> ' + lnk.get('href','')[:60])
