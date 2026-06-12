# -*- coding: utf-8 -*-
"""Probe rusprofile.ru — round 10: person profile page structure + INN-based URL."""
import re, time, sys, json, requests
from bs4 import BeautifulSoup

sys.stdout.reconfigure(encoding='utf-8')

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'ru-RU,ru;q=0.9',
    'Referer': 'https://www.rusprofile.ru/',
}

s = requests.Session()
s.headers.update(HEADERS)

# ── 1. full parse of the person profile page we know works ───────────────────
print('=== person profile page full parse ===')
url = 'https://www.rusprofile.ru/person/ivanov-ii-183511206113'
r = s.get(url, timeout=15)
print(f'Status: {r.status_code}  URL: {r.url}')
soup = BeautifulSoup(r.text, 'lxml')

# all list-element items
items = soup.select('.list-element')
print(f'list-element items: {len(items)}')
for item in items:
    a = item.select_one('a.list-element__title')
    row = item.select_one('.list-element__row-info')
    track = a.get('data-track-click','') if a else ''
    name = a.get_text(strip=True) if a else ''
    info = row.get_text(' ', strip=True) if row else ''
    status_el = item.select_one('.list-element__text.danger')
    status = status_el.get_text(strip=True) if status_el else 'Действующее'
    print(f'  [{track}] {name}  |  {info[:80]}  |  {status}')

# person name on the page
h1 = soup.select_one('h1, .person-name, [class*="person-title"]')
print(f'  Page title/name: {h1.get_text(strip=True) if h1 else "not found"}')

# ── 2. test URL variations — does INN alone work as a suffix? ────────────────
print()
print('=== URL format variations ===')
# format: /person/SLUG-INN or /person/INN
test_cases = [
    '/person/ivanov-ii-183511206113',      # surname-initials-inn (known working)
    '/person/183511206113',                 # just INN?
    '/person/ivanov-183511206113',          # just surname-inn?
    '/person/ii-183511206113',              # just initials-inn?
]
for path in test_cases:
    resp = s.get(f'https://www.rusprofile.ru{path}', timeout=10)
    soup2 = BeautifulSoup(resp.text, 'lxml')
    items2 = soup2.select('.list-element')
    redir = resp.url
    print(f'  {resp.status_code}  items={len(items2)}  redir={redir[35:] if len(redir)>35 else redir}  path={path}')
    time.sleep(0.3)

# ── 3. find the INN in the known URL — confirm it's a real personal INN ───────
print()
print('=== check INN 183511206113 ===')
r2 = s.get('https://egrul.nalog.ru/', timeout=10)
# just check length: 12 digits = personal INN
inn = '183511206113'
print(f'  INN length: {len(inn)} (12=personal, 10=company)')

# ── 4. try to find person URL by INN using nalog.ru data ─────────────────────
# Given we have the INN from the pipeline, can we construct the rusprofile URL?
# Pattern seems: /person/TRANSLITERATED_LASTNAME-INITIALS-INN
# Try with a candidate we know: Зобов Андрей Борисович
print()
print('=== construct URL from known candidate (Зобов Андрей Борисович) ===')
# Transliteration: Зобов -> zobov, А.Б. -> ab
test_urls = [
    '/person/zobov-ab-230804395297',
    '/person/zobov-230804395297',
    '/person/230804395297',
]
for path in test_urls:
    resp = s.get(f'https://www.rusprofile.ru{path}', timeout=10)
    soup3 = BeautifulSoup(resp.text, 'lxml')
    items3 = soup3.select('.list-element')
    h1 = soup3.select_one('h1')
    print(f'  {resp.status_code}  items={len(items3)}  h1={h1.get_text(strip=True)[:40] if h1 else ""}  path={path}')
    time.sleep(0.3)

# ── 5. check if /person/INN redirects to correct person page ─────────────────
print()
print('=== /person/INN redirect test (no allow_redirects) ===')
resp_nr = s.get('https://www.rusprofile.ru/person/183511206113',
                allow_redirects=False, timeout=10)
print(f'  Status: {resp_nr.status_code}  Location: {resp_nr.headers.get("Location","")}')
