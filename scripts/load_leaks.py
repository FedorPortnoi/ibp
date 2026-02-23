#!/usr/bin/env python3
"""
Leak Data Loader CLI
=====================
Import CSV/JSONL leak dumps into the unified LeakDB SQLite database.

Usage:
    python scripts/load_leaks.py vk_2012   ./data/raw/vk_2012_100m.csv
    python scripts/load_leaks.py getcontact ./data/raw/getcontact_dump.jsonl
    python scripts/load_leaks.py telco      ./data/raw/beeline_2021.csv --carrier beeline
    python scripts/load_leaks.py telco      ./data/raw/mts_2022.csv    --carrier mts --dedup

Features:
    - Auto-normalizes phones to +7XXXXXXXXXX
    - Deduplication by phone+name (--dedup flag)
    - Progress bar (tqdm, optional)
    - Schema validation per source type
    - Streaming reader — handles multi-GB files without loading into RAM
"""

import argparse
import csv
import json
import os
import sys
import time

try:
    from charset_normalizer import from_bytes as detect_encoding
except ImportError:
    detect_encoding = None

# Add project root to path so we can import app modules
PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, PROJECT_ROOT)

from app.utils.phone import normalize_phone

try:
    from tqdm import tqdm
except ImportError:
    tqdm = None  # graceful fallback


# ---------------------------------------------------------------------------
# Parsers — one per source type
# ---------------------------------------------------------------------------

def parse_vk2012_row(row: dict) -> dict:
    """
    VK 2012 CSV columns (expected):
        phone, email, username, first_name, last_name, password_hash
    """
    phone = normalize_phone(row.get('phone', ''))
    first = (row.get('first_name') or '').strip()
    last = (row.get('last_name') or '').strip()
    name = f"{first} {last}".strip() or None
    return {
        'phone': phone if phone.startswith('+7') else None,
        'email': (row.get('email') or '').strip() or None,
        'name': name,
        'username': (row.get('username') or '').strip() or None,
        'password_hash': (row.get('password_hash') or row.get('password') or '').strip() or None,
        'source': 'vk_2012',
        'confidence': 0.85,
    }


def parse_getcontact_row(row: dict) -> dict:
    """
    GetContact JSONL or CSV columns:
        phone, name, tags (comma-separated or JSON array)
    """
    phone = normalize_phone(row.get('phone', ''))
    tags_raw = row.get('tags', '')
    if isinstance(tags_raw, str):
        try:
            tags = json.loads(tags_raw)
        except (json.JSONDecodeError, TypeError):
            tags = [t.strip() for t in tags_raw.split(',') if t.strip()]
    elif isinstance(tags_raw, list):
        tags = tags_raw
    else:
        tags = []

    return {
        'phone': phone if phone.startswith('+7') else None,
        'name': (row.get('name') or row.get('display_name') or '').strip() or None,
        'source': 'getcontact',
        'confidence': 0.80,
        'extra': {'tags': tags} if tags else None,
    }


def parse_telco_row(row: dict, carrier: str = 'unknown') -> dict:
    """
    Telco CSV columns:
        phone, passport, full_name, address, subscriber_since
    Example:
        +79123456789,**** **** 12 345678,Иванов Иван Иванович,Москва ул Ленина 15,2020-01-01
    """
    phone = normalize_phone(row.get('phone', ''))
    return {
        'phone': phone if phone.startswith('+7') else None,
        'name': (row.get('full_name') or row.get('name') or '').strip() or None,
        'passport': (row.get('passport') or '').strip() or None,
        'address': (row.get('address') or '').strip() or None,
        'source': 'telco',
        'confidence': 0.95,
        'extra': {
            'carrier': carrier,
            'subscriber_since': (row.get('subscriber_since') or '').strip() or None,
        },
    }


PARSERS = {
    'vk_2012': parse_vk2012_row,
    'getcontact': parse_getcontact_row,
    'telco': parse_telco_row,
}


# ---------------------------------------------------------------------------
# Encoding & delimiter detection
# ---------------------------------------------------------------------------

def detect_file_encoding(path: str) -> str:
    """
    Auto-detect file encoding.
    Reads first 64KB and uses charset-normalizer (if installed) to detect.
    Falls back to trying common Russian encodings, then UTF-8.
    """
    with open(path, 'rb') as f:
        raw = f.read(65536)

    # Quick check: valid UTF-8?
    try:
        raw.decode('utf-8')
        print("  Encoding detected: utf-8 (BOM/valid UTF-8)")
        return 'utf-8'
    except UnicodeDecodeError:
        pass

    # Try charset-normalizer if available
    if detect_encoding is not None:
        result = detect_encoding(raw)
        best = result.best()
        if best and best.encoding and best.coherence > 0.5:
            detected = best.encoding
            # Normalize common aliases
            alias_map = {
                'windows-1251': 'cp1251',
                'iso-8859-5': 'cp1251',
            }
            detected = alias_map.get(detected.lower(), detected)
            print(f"  Encoding detected: {detected} (confidence: {best.coherence:.0%})")
            return detected

    # Fallback: try common Russian encodings
    for enc in ('cp1251', 'koi8-r', 'iso-8859-5'):
        try:
            raw.decode(enc)
            print(f"  Encoding detected: {enc} (fallback heuristic)")
            return enc
        except (UnicodeDecodeError, LookupError):
            continue

    print("  Encoding: defaulting to utf-8")
    return 'utf-8'


def detect_delimiter(path: str, encoding: str) -> str:
    """
    Auto-detect CSV delimiter using csv.Sniffer on first few lines.
    Falls back to comma.
    """
    try:
        with open(path, 'r', encoding=encoding, errors='replace') as f:
            sample = f.read(8192)

        dialect = csv.Sniffer().sniff(sample, delimiters=',;\t|')
        detected = dialect.delimiter
        delim_names = {',': 'comma', ';': 'semicolon', '\t': 'tab', '|': 'pipe'}
        print(f"  Delimiter detected: {delim_names.get(detected, repr(detected))}")
        return detected
    except csv.Error:
        return ','


# ---------------------------------------------------------------------------
# File readers
# ---------------------------------------------------------------------------

def iter_csv(path: str, encoding: str = 'utf-8', delimiter: str = ','):
    """Stream CSV rows as dicts with configurable encoding and delimiter."""
    with open(path, 'r', encoding=encoding, errors='replace') as f:
        # Sniff if there's a header row
        sample = f.read(4096)
        f.seek(0)

        has_header = True
        try:
            has_header = csv.Sniffer().has_header(sample)
        except csv.Error:
            pass

        if has_header:
            reader = csv.DictReader(f, delimiter=delimiter)
        else:
            # No header — generate column names col_0, col_1, ...
            first_line = f.readline()
            num_cols = len(first_line.split(delimiter))
            f.seek(0)
            fieldnames = [f'col_{i}' for i in range(num_cols)]
            reader = csv.DictReader(f, fieldnames=fieldnames, delimiter=delimiter)

        for row in reader:
            yield row


def iter_jsonl(path: str, encoding: str = 'utf-8'):
    """Stream JSONL rows as dicts."""
    with open(path, 'r', encoding=encoding, errors='replace') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def iter_file(path: str, encoding: str = None, delimiter: str = None):
    """
    Auto-detect file format, encoding, and delimiter.

    Priority: user-specified → auto-detected → defaults (UTF-8, comma)
    """
    ext = os.path.splitext(path)[1].lower()

    # Resolve encoding
    file_encoding = encoding or detect_file_encoding(path)

    if ext in ('.jsonl', '.json', '.ndjson'):
        return iter_jsonl(path, encoding=file_encoding)

    # Resolve delimiter for CSV
    file_delimiter = delimiter or detect_delimiter(path, file_encoding)
    return iter_csv(path, encoding=file_encoding, delimiter=file_delimiter)


def count_lines(path: str) -> int:
    """Fast line count for progress bar."""
    count = 0
    with open(path, 'rb') as f:
        for _ in f:
            count += 1
    return max(count - 1, 0)  # subtract header for CSV


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

def load_file(
    source_type: str,
    file_path: str,
    db_path: str = None,
    dedup: bool = False,
    carrier: str = 'unknown',
    batch_size: int = 5000,
    encoding: str = None,
    delimiter: str = None,
) -> dict:
    """
    Load a leak file into the database.

    Returns stats dict: {inserted, skipped, errors, elapsed}
    """
    from app.services.phase2.sources.leak_sources import LeakDB

    if not os.path.isfile(file_path):
        print(f"Error: file not found: {file_path}")
        sys.exit(1)

    parser = PARSERS.get(source_type)
    if not parser:
        print(f"Error: unknown source type '{source_type}'. Choose from: {list(PARSERS.keys())}")
        sys.exit(1)

    db = LeakDB(db_path) if db_path else LeakDB.get_instance()

    # Dedup set
    seen = set() if dedup else None

    # Stats
    inserted = 0
    skipped = 0
    errors = 0
    batch: list = []
    start = time.time()

    # Count lines for progress bar
    total = None
    if tqdm:
        total = count_lines(file_path)

    rows = iter_file(file_path, encoding=encoding, delimiter=delimiter)
    if tqdm and total:
        rows = tqdm(rows, total=total, desc=f"Loading {source_type}", unit=" rows")

    for raw_row in rows:
        try:
            if source_type == 'telco':
                record = parser(raw_row, carrier=carrier)
            else:
                record = parser(raw_row)

            # Validate: must have at least phone or email
            if not record.get('phone') and not record.get('email'):
                skipped += 1
                continue

            # Dedup check
            if seen is not None:
                dedup_key = (record.get('phone', ''), (record.get('name') or '').lower())
                if dedup_key in seen:
                    skipped += 1
                    continue
                seen.add(dedup_key)

            batch.append(record)

            if len(batch) >= batch_size:
                db.insert_batch(batch, batch_size=batch_size)
                inserted += len(batch)
                batch = []

        except Exception as e:
            errors += 1
            if errors <= 10:
                print(f"  Row error: {e}")

    # Flush remaining
    if batch:
        db.insert_batch(batch, batch_size=batch_size)
        inserted += len(batch)

    elapsed = time.time() - start

    stats = {
        'inserted': inserted,
        'skipped': skipped,
        'errors': errors,
        'elapsed': round(elapsed, 1),
        'rate': round(inserted / elapsed) if elapsed > 0 else 0,
    }

    print(f"\nDone: {inserted:,} inserted, {skipped:,} skipped, {errors} errors "
          f"in {elapsed:.1f}s ({stats['rate']:,} rows/s)")
    print(f"Total in DB ({source_type}): {db.count(source_type):,}")

    return stats


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description='Load leak CSV/JSONL into IBP LeakDB',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/load_leaks.py vk_2012   ./data/raw/vk_2012.csv
  python scripts/load_leaks.py getcontact ./data/raw/getcontact.jsonl --dedup
  python scripts/load_leaks.py telco      ./data/raw/beeline.csv --carrier beeline
        """,
    )
    parser.add_argument('source', choices=list(PARSERS.keys()),
                        help='Source type to load')
    parser.add_argument('file', help='Path to CSV or JSONL file')
    parser.add_argument('--db', default=None,
                        help='Custom database path (default: data/leaks/all_leaks.db)')
    parser.add_argument('--dedup', action='store_true',
                        help='Deduplicate by phone+name')
    parser.add_argument('--carrier', default='unknown',
                        help='Carrier name for telco source (beeline, mts, megafon)')
    parser.add_argument('--batch-size', type=int, default=5000,
                        help='Insert batch size (default: 5000)')
    parser.add_argument('--encoding', default=None,
                        help='Force file encoding (e.g., cp1251, utf-8). Auto-detected if omitted.')
    parser.add_argument('--delimiter', default=None,
                        help='Force CSV delimiter (e.g., ";" or "|"). Auto-detected if omitted.')

    args = parser.parse_args()

    print(f"Loading {args.source} from {args.file}")
    if args.dedup:
        print("  Deduplication: ON")
    if args.encoding:
        print(f"  Encoding override: {args.encoding}")
    if args.delimiter:
        print(f"  Delimiter override: {repr(args.delimiter)}")

    load_file(
        source_type=args.source,
        file_path=args.file,
        db_path=args.db,
        dedup=args.dedup,
        carrier=args.carrier,
        batch_size=args.batch_size,
        encoding=args.encoding,
        delimiter=args.delimiter,
    )


if __name__ == '__main__':
    main()
