#!/usr/bin/env python3
"""
Test: судебныерешения.рф — calls the actual integrated production code path.

Run from /opt/ibp on the server (Russian IP):
    python3 scripts/test_court_playwright.py
    python3 scripts/test_court_playwright.py "Иванов Иван Иванович"
"""

import sys
import os
import time
import logging

# Point at the repo root so app imports resolve
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Show all court-related log output
logging.basicConfig(level=logging.INFO, format='%(levelname)s %(name)s: %(message)s')

DEFAULT_NAME = 'Граб Артём Александрович'


def run(name: str):
    print(f"\n{'='*60}")
    print(f"Testing integrated судебныерешения.рф Playwright path")
    print(f"Target: {name}")
    print(f"{'='*60}\n")

    try:
        from app.services.phase3.court_search import CourtRecordSearch, PLAYWRIGHT_AVAILABLE
    except Exception as e:
        print(f"ERROR: could not import CourtRecordSearch: {e}")
        sys.exit(1)

    if not PLAYWRIGHT_AVAILABLE:
        print("ERROR: Playwright not installed on this machine.")
        print("Run: pip install playwright && playwright install chromium")
        sys.exit(1)

    print(f"Playwright: available")
    searcher = CourtRecordSearch(timeout=90)

    statuses: dict = {}
    t0 = time.time()
    results = searcher._search_sudebnye_resheniya_playwright(name, status_out=statuses)
    elapsed = time.time() - t0

    print(f"\n--- Result ---")
    print(f"Elapsed:  {elapsed:.1f}s")
    print(f"Status:   {statuses.get('судебныерешения.рф', 'not set')}")
    print(f"Cases:    {len(results)}")

    for i, case in enumerate(results[:15], 1):
        print(f"\n  [{i}] {case.case_number}")
        print(f"       Court: {case.court_name}")
        print(f"       Date:  {case.date}  Type: {case.case_type}  Role: {case.role}")
        if case.url:
            print(f"       URL:   {case.url}")

    if len(results) > 15:
        print(f"\n  ... and {len(results) - 15} more")

    print()


if __name__ == '__main__':
    name = ' '.join(sys.argv[1:]) if len(sys.argv) > 1 else DEFAULT_NAME
    if len(sys.argv) == 1:
        print(f"No name given — using default: {DEFAULT_NAME}")
    run(name)
