"""Probe reputation.su search endpoint."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import requests
from bs4 import BeautifulSoup
from urllib.parse import quote

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,*/*;q=0.8',
    'Accept-Language': 'ru-RU,ru;q=0.9',
}

name = 'Иванов Иван Иванович'
url = f'https://reputation.su/search?query={quote(name)}'
print(f'GET {url}')

try:
    r = requests.get(url, headers=HEADERS, timeout=15)
    print(f'Status: {r.status_code}, size: {len(r.text)}b')
    soup = BeautifulSoup(r.text, 'lxml')
    title = soup.find('title')
    print(f'Title: {title.text.strip()[:80] if title else None}')

    cards = soup.select('div.srch-card__affairs-box')
    print(f'Cards found: {len(cards)}')

    if cards:
        c = cards[0]
        print(f'\nCard[0] HTML snippet:')
        print(c.prettify()[:800])
    else:
        # Check what selectors exist
        all_divs = soup.find_all('div', class_=True)
        classes = set()
        for d in all_divs[:50]:
            classes.update(d.get('class', []))
        print(f'Available div classes: {sorted(classes)[:30]}')
        print(f'Body snippet: {soup.get_text(strip=True)[:300]}')

except Exception as e:
    print(f'ERROR: {type(e).__name__}: {e}')
