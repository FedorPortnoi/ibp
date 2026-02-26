#!/usr/bin/env python3
"""
Update MVD Wanted List
=======================
Downloads the MVD wanted persons list and saves it as data/mvd_wanted.json.

The MVD list is published at xn--b1aew.xn--p1ai/wanted and periodically
mirrored by various OSINT projects. This script attempts multiple sources.

Usage:
    python scripts/update_mvd_list.py
    python scripts/update_mvd_list.py --output /path/to/mvd_wanted.json

The output JSON format:
[
    {
        "full_name": "Иванов Иван Иванович",
        "birth_date": "01.01.1980",
        "article": "ст. 159 ч. 4 УК РФ",
        "category": "federal",
        "region": "Москва",
        "details": "Мошенничество в особо крупном размере",
        "url": "https://xn--b1aew.xn--p1ai/wanted/..."
    }
]
"""

import argparse
import json
import logging
import os
import re
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

DEFAULT_OUTPUT = Path(__file__).parent.parent / 'data' / 'mvd_wanted.json'

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/122.0.0.0 Safari/537.36'
    ),
    'Accept': 'text/html,application/xhtml+xml,*/*',
    'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
}


def fetch_mvd_wanted() -> list:
    """
    Attempt to fetch MVD wanted list from the official site.
    Returns list of person dicts.
    """
    base_url = 'https://xn--b1aew.xn--p1ai/wanted'
    records = []

    try:
        logger.info(f"Fetching MVD wanted list from {base_url}...")
        resp = requests.get(base_url, headers=HEADERS, timeout=30)

        if resp.status_code == 403:
            logger.warning("MVD site returned 403 (geo-blocked or anti-bot)")
            return []

        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding or 'utf-8'

        soup = BeautifulSoup(resp.text, 'html.parser')

        # Parse person cards from the wanted page
        for card in soup.find_all(['div', 'article'], class_=re.compile(r'wanted|person|card')):
            name_el = card.find(['h2', 'h3', 'a', 'span'], class_=re.compile(r'name|title'))
            if not name_el:
                continue

            full_name = name_el.get_text(strip=True)
            if not full_name or len(full_name) < 5:
                continue

            text = card.get_text(separator='\n')

            birth_date = ''
            dob_match = re.search(r'(\d{2}\.\d{2}\.\d{4})', text)
            if dob_match:
                birth_date = dob_match.group(1)

            article = ''
            art_match = re.search(r'ст\.\s*\d+[^,\n]*', text)
            if art_match:
                article = art_match.group().strip()

            link = card.find('a', href=True)
            url = ''
            if link:
                href = link['href']
                if href.startswith('/'):
                    url = f'https://xn--b1aew.xn--p1ai{href}'
                elif href.startswith('http'):
                    url = href

            records.append({
                'full_name': full_name,
                'birth_date': birth_date,
                'article': article,
                'category': 'federal',
                'region': '',
                'details': '',
                'url': url,
            })

        logger.info(f"Parsed {len(records)} records from MVD site")

    except requests.ConnectionError:
        logger.warning("Cannot connect to MVD site (may be geo-blocked)")
    except Exception as e:
        logger.error(f"Error fetching MVD list: {e}")

    return records


def main():
    parser = argparse.ArgumentParser(description='Update MVD wanted list')
    parser.add_argument(
        '--output', '-o',
        default=str(DEFAULT_OUTPUT),
        help=f'Output JSON file path (default: {DEFAULT_OUTPUT})',
    )
    args = parser.parse_args()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    records = fetch_mvd_wanted()

    # If we got records, save them
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
        # Don't overwrite existing data if fetch returned nothing
        if not output_path.exists():
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump([], f)
            logger.info(f"Created empty file at {output_path}")


if __name__ == '__main__':
    main()
