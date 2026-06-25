#!/usr/bin/env python3
"""
Standalone test: судебныерешения.рф via Playwright
===================================================
Run from the server (Russian IP) to verify Playwright can pass DDoS-Guard
and retrieve court case results. No app imports — copy and run anywhere.

Usage:
    python3 test_court_playwright.py "Иванов Иван Иванович"
    python3 test_court_playwright.py "Граб Артём Александрович"
"""

import sys
import re
import time

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("ERROR: playwright not installed. Run: pip install playwright && playwright install chromium")
    sys.exit(1)

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("ERROR: beautifulsoup4 not installed. Run: pip install beautifulsoup4 lxml")
    sys.exit(1)

BASE = 'https://xn--90afdbaav0bd1afy6eub5d.xn--p1ai'  # судебныерешения.рф
TIMEOUT_MS = 60_000  # 60s for DDoS-Guard to clear


def run(name: str):
    print(f"\n{'='*60}")
    print(f"Target: {name}")
    print(f"Site:   судебныерешения.рф")
    print(f"{'='*60}\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/122.0.0.0 Safari/537.36'
            ),
            locale='ru-RU',
            timezone_id='Europe/Moscow',
            viewport={'width': 1280, 'height': 800},
        )
        page = context.new_page()

        # ── Step 1: Load homepage, wait for DDoS-Guard to clear ──────────
        print("[1/4] Loading homepage (waiting for DDoS-Guard to clear)...")
        t0 = time.time()
        try:
            page.goto(BASE + '/', wait_until='networkidle', timeout=TIMEOUT_MS)
        except Exception as e:
            print(f"      goto() raised: {e}")
            print("      Trying domcontentloaded fallback...")
            try:
                page.goto(BASE + '/', wait_until='domcontentloaded', timeout=TIMEOUT_MS)
            except Exception as e2:
                print(f"      domcontentloaded also failed: {e2}")
                browser.close()
                return

        elapsed = time.time() - t0
        html = page.content()
        print(f"      Page loaded in {elapsed:.1f}s — {len(html)} bytes")

        # Check if DDoS-Guard challenge is still up
        if 'ddos-guard' in html.lower() or 'checking your browser' in html.lower():
            print("      DDoS-Guard still showing — waiting 10 more seconds...")
            time.sleep(10)
            html = page.content()
            if 'ddos-guard' in html.lower():
                print("FAIL: DDoS-Guard did not clear. IP may be datacenter-flagged.")
                browser.close()
                return
            print("      Cleared after wait.")

        # ── Step 2: Find the search form ──────────────────────────────────
        print("[2/4] Looking for search form...")

        # Try to find the search input field directly
        search_input = None
        selectors_to_try = [
            'input[name="simpleSearch[person_info][0][person]"]',
            'input[placeholder*="ФИО"]',
            'input[placeholder*="фамилия"]',
            'input[placeholder*="имя"]',
            'form input[type="text"]',
        ]
        for sel in selectors_to_try:
            try:
                page.wait_for_selector(sel, timeout=5000)
                search_input = sel
                print(f"      Found input via: {sel}")
                break
            except Exception:
                continue

        if not search_input:
            print("      No input found — dumping page text (first 2000 chars):")
            print(page.inner_text('body')[:2000])
            browser.close()
            return

        # ── Step 3: Fill and submit search ───────────────────────────────
        print(f"[3/4] Filling search form with '{name}'...")
        page.fill(search_input, name)
        time.sleep(1)  # brief pause before submit

        # Find and click the submit button
        submit_clicked = False
        for btn_sel in ['button[type="submit"]', 'input[type="submit"]', 'button.btn-primary', 'button']:
            try:
                page.click(btn_sel, timeout=3000)
                submit_clicked = True
                print(f"      Clicked submit via: {btn_sel}")
                break
            except Exception:
                continue

        if not submit_clicked:
            # Try pressing Enter in the input field
            page.press(search_input, 'Enter')
            print("      Pressed Enter to submit")

        # Wait for results to load
        print("      Waiting for results...")
        try:
            page.wait_for_load_state('networkidle', timeout=30000)
        except Exception:
            pass  # might time out but page may still have results

        # ── Step 4: Parse results ─────────────────────────────────────────
        print("[4/4] Parsing results...")
        html = page.content()
        browser.close()

    soup = BeautifulSoup(html, 'lxml')

    # Count info
    count_el = soup.select_one('div.count, .count-info, .results-count')
    if count_el:
        print(f"\nCount block: {count_el.get_text(strip=True)}")

    # Results in #list
    list_div = soup.select_one('#list')
    if not list_div:
        page_text = soup.get_text()
        if 'не найдено' in page_text.lower() or 'ничего не найдено' in page_text.lower():
            print("\nRESULT: Source responded — NO CASES FOUND for this name.")
        else:
            print("\nRESULT: #list div not found. Page text (first 1000 chars):")
            print(page_text[:1000])
        return

    tables = list_div.select('table.table-bordered')
    if not tables:
        print("\nRESULT: #list found but no result tables inside it.")
        print("Page text sample:", list_div.get_text()[:500])
        return

    print(f"\nRESULT: {len(tables)} case(s) found\n")
    for i, table in enumerate(tables[:10], 1):
        rows = table.select('tr')
        if len(rows) < 1:
            continue
        tds1 = rows[0].select('td')
        court = tds1[0].get_text(strip=True) if tds1 else '?'
        link = tds1[1].select_one('a') if len(tds1) > 1 else None
        case_num = link.get_text(strip=True) if link else '?'
        href = (link.get('href', '') if link else '')
        date = ''
        if len(rows) > 1:
            tds2 = rows[1].select('td')
            if tds2:
                dm = re.search(r'\d{2}\.\d{2}\.\d{4}', tds2[0].get_text())
                if dm:
                    date = dm.group(0)
        url = f"{BASE}{href}" if href.startswith('/') else href
        print(f"  [{i}] {case_num} | {court} | {date}")
        if url:
            print(f"       {url}")

    if len(tables) > 10:
        print(f"  ... and {len(tables) - 10} more")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        # Default test person — run with no arguments to test quickly
        name = 'Граб Артём Александрович'
        print(f"No name given — using default: {name}")
    else:
        name = ' '.join(sys.argv[1:])
    run(name)
