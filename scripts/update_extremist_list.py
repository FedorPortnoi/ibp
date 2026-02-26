#!/usr/bin/env python3
"""
Update Extremist List
======================
Downloads the Minjust extremist organizations/persons list
and saves it as data/extremist_list.json.

The list is published at minjust.gov.ru and periodically
mirrored by various OSINT projects.

Usage:
    python scripts/update_extremist_list.py
    python scripts/update_extremist_list.py --output /path/to/extremist_list.json

The output JSON format:
[
    {
        "full_name": "Иванов Иван Иванович",
        "birth_date": "01.01.1980",
        "reason": "Участие в экстремистской организации",
        "category": "person",
        "article": "",
        "region": "",
        "details": "...",
        "url": "https://minjust.gov.ru/ru/..."
    }
]
"""

import argparse
import json
import logging
import re
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

DEFAULT_OUTPUT = Path(__file__).parent.parent / 'data' / 'extremist_list.json'

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/122.0.0.0 Safari/537.36'
    ),
    'Accept': 'text/html,application/xhtml+xml,*/*',
    'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
}

# Multiple URLs to try (minjust changes URLs periodically)
URLS = [
    'https://minjust.gov.ru/ru/extremist-materials/',
    'https://minjust.gov.ru/ru/activity/directions/942/',
    'https://minjust.gov.ru/ru/documents/7822/',
]


def fetch_extremist_list() -> list:
    """
    Attempt to fetch extremist list from Minjust website.
    Returns list of person/organization dicts.
    """
    records = []

    for url in URLS:
        try:
            logger.info(f"Trying {url}...")
            resp = requests.get(url, headers=HEADERS, timeout=30)

            if resp.status_code in (403, 451):
                logger.warning(f"{url}: blocked ({resp.status_code})")
                continue

            if resp.status_code != 200:
                logger.warning(f"{url}: HTTP {resp.status_code}")
                continue

            resp.encoding = resp.apparent_encoding or 'utf-8'
            soup = BeautifulSoup(resp.text, 'html.parser')

            # Look for list items, table rows, or numbered entries
            # Minjust lists are typically numbered entries in tables or divs
            page_text = soup.get_text(separator='\n')

            # Pattern: numbered entries with Russian names
            for m in re.finditer(
                r'(\d+)\.\s*'
                r'([А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+)?)'
                r'[,;\s]*'
                r'(?:(\d{2}\.\d{2}\.\d{4}))?'
                r'[,;\s]*'
                r'([^\n]{0,200})',
                page_text,
            ):
                full_name = m.group(2).strip()
                birth_date = m.group(3) or ''
                details = m.group(4).strip() if m.group(4) else ''

                records.append({
                    'full_name': full_name,
                    'birth_date': birth_date,
                    'reason': details[:200],
                    'category': 'person',
                    'article': '',
                    'region': '',
                    'details': details[:500],
                    'url': url,
                })

            if records:
                logger.info(f"Parsed {len(records)} records from {url}")
                break

        except requests.ConnectionError:
            logger.warning(f"Cannot connect to {url} (may be geo-blocked)")
        except Exception as e:
            logger.error(f"Error fetching from {url}: {e}")

    return records


def main():
    parser = argparse.ArgumentParser(description='Update extremist list')
    parser.add_argument(
        '--output', '-o',
        default=str(DEFAULT_OUTPUT),
        help=f'Output JSON file path (default: {DEFAULT_OUTPUT})',
    )
    args = parser.parse_args()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    records = fetch_extremist_list()

    if records:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
        logger.info(f"Saved {len(records)} records to {output_path}")
    else:
        logger.warning(
            "No records fetched. This is expected if running outside Russia.\n"
            "You can manually populate the file with data from OSINT mirrors.\n"
            f"File location: {output_path}"
        )
        if not output_path.exists():
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump([], f)
            logger.info(f"Created empty file at {output_path}")


if __name__ == '__main__':
    main()
