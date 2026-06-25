"""
Probe script for bsr.sudrf.ru — run on the production server (Russian IP).

Usage:
    cd /opt/ibp && source venv/bin/activate
    python scripts/probe_bsr.py "Граб Артём Александрович"

Saves:
    /tmp/bsr_probe_plain.html    — raw HTTP response (no JS)
    /tmp/bsr_probe_xhr.json      — any XHR/API response (if found)
    /tmp/bsr_probe_playwright.html — Playwright-rendered HTML (if available)

Reports:
    - HTTP status code and headers
    - Whether the page requires JS to render results
    - What search form elements exist
    - What API endpoints are called (from <script> tags)
    - Playwright result structure (selectors, result count)
"""

import sys
import json
import time
import os
import re
import requests
from bs4 import BeautifulSoup

NAME = sys.argv[1] if len(sys.argv) > 1 else "Граб Артём Александрович"
BASE = "https://bsr.sudrf.ru"
PORTAL = f"{BASE}/bigs/portal.html"
TIMEOUT = 20

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
}

SEP = "=" * 70


# ── 1. Plain HTTP GET on portal ─────────────────────────────────────────────
print(f"\n{SEP}")
print("STEP 1 — Plain HTTP GET on portal page")
print(SEP)
try:
    r = requests.get(PORTAL, headers=HEADERS, timeout=TIMEOUT)
    print(f"Status: {r.status_code}")
    print(f"Content-Type: {r.headers.get('content-type', '?')}")
    print(f"Body size: {len(r.content)} bytes")

    with open("/tmp/bsr_probe_plain.html", "wb") as f:
        f.write(r.content)
    print("Saved: /tmp/bsr_probe_plain.html")

    soup = BeautifulSoup(r.text, "html.parser")

    # Check if it's a meaningful page or a JS shell
    body_text = soup.get_text(strip=True)
    print(f"Visible text length: {len(body_text)} chars")
    print(f"First 400 chars of visible text:\n  {body_text[:400]}")

    # Find all forms
    forms = soup.find_all("form")
    print(f"\nForms found: {len(forms)}")
    for i, form in enumerate(forms):
        print(f"  Form {i}: action={form.get('action')} method={form.get('method')}")
        for inp in form.find_all(["input", "select", "textarea"]):
            print(f"    {inp.name}: name={inp.get('name')} type={inp.get('type')} id={inp.get('id')}")

    # Find script tags — look for API endpoint hints
    scripts = soup.find_all("script")
    print(f"\nScript tags: {len(scripts)}")
    api_hints = []
    for s in scripts:
        src = s.get("src", "")
        content = s.string or ""
        # Look for URL patterns in script content
        urls_in_script = re.findall(r'["\']([/\w\-\.]+(?:api|search|sugg|bsr|query|find)[/\w\-\.?=&]*)["\']',
                                    content, re.IGNORECASE)
        if urls_in_script:
            api_hints.extend(urls_in_script)
        if src:
            print(f"  <script src=\"{src}\">")

    if api_hints:
        print(f"\nAPI-like URLs found in scripts:")
        for u in set(api_hints):
            print(f"  {u}")

    # Find any data- attributes or ng-* / v- / react patterns
    react_markers = soup.find_all(attrs={"id": re.compile(r"root|app|main", re.I)})
    ng_markers = soup.find_all(attrs=lambda k, v: k and k.startswith("ng-"))
    vue_markers = soup.find_all(attrs=lambda k, v: k and (k.startswith("v-") or k.startswith(":") or k.startswith("@")))
    print(f"\nSPA markers: React-root={len(react_markers)}, Angular={len(ng_markers)}, Vue={len(vue_markers)}")

    # Check for known anti-bot signals
    for marker in ["ddos-guard", "cloudflare", "captcha", "recaptcha", "cf-ray", "challenge"]:
        if marker.lower() in r.text.lower():
            print(f"  ⚠️  Anti-bot marker detected: '{marker}'")

except Exception as e:
    print(f"ERROR: {e}")


# ── 2. Probe known API endpoints with GET ───────────────────────────────────
print(f"\n{SEP}")
print("STEP 2 — Probe likely API endpoints (plain HTTP)")
print(SEP)

name_enc = requests.utils.quote(NAME)
candidates = [
    f"{BASE}/bigs/sugg?q={name_enc}&doc_type=SOLUTION",
    f"{BASE}/bigs/sugg?q={name_enc}",
    f"{BASE}/bigs/sug?q={name_enc}",
    f"{BASE}/bigs/search?q={name_enc}",
    f"{BASE}/bigs/portal.html?q={name_enc}",
]

api_headers = {**HEADERS, "Accept": "application/json, text/plain, */*",
               "X-Requested-With": "XMLHttpRequest",
               "Referer": PORTAL}

for url in candidates:
    try:
        r2 = requests.get(url, headers=api_headers, timeout=10)
        ct = r2.headers.get("content-type", "")
        print(f"\nGET {url}")
        print(f"  Status: {r2.status_code}  Content-Type: {ct}  Size: {len(r2.content)}")
        if "json" in ct:
            print(f"  JSON RESPONSE — saving to /tmp/bsr_probe_xhr.json")
            with open("/tmp/bsr_probe_xhr.json", "w") as f:
                json.dump(r2.json(), f, ensure_ascii=False, indent=2)
            print(f"  Keys: {list(r2.json().keys()) if isinstance(r2.json(), dict) else 'list'}")
        elif r2.status_code == 200:
            preview = r2.text[:300].replace("\n", " ")
            print(f"  Preview: {preview}")
    except Exception as e:
        print(f"  ERROR: {e}")


# ── 3. Playwright probe ──────────────────────────────────────────────────────
print(f"\n{SEP}")
print("STEP 3 — Playwright probe (headless Chromium)")
print(SEP)

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    print("Playwright available — launching browser...")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            timeout=20000,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        try:
            page = browser.new_page(
                user_agent=HEADERS["User-Agent"],
                viewport={"width": 1280, "height": 900},
            )
            page.set_default_timeout(25000)

            # Intercept XHR/fetch requests to capture API calls
            api_calls = []
            def on_request(req):
                if req.resource_type in ("xhr", "fetch"):
                    api_calls.append({"url": req.url, "method": req.method,
                                      "post_data": req.post_data})

            page.on("request", on_request)

            print(f"  Navigating to {PORTAL} ...")
            page.goto(PORTAL, wait_until="networkidle", timeout=30000)
            print("  Page loaded.")

            # Log all XHR/fetch calls captured during load
            print(f"\n  XHR/fetch calls captured on load ({len(api_calls)}):")
            for call in api_calls[:20]:
                print(f"    [{call['method']}] {call['url']}")
                if call.get("post_data"):
                    print(f"          body: {call['post_data'][:200]}")

            # Find the search input
            page_html = page.content()
            soup2 = BeautifulSoup(page_html, "html.parser")
            body_text2 = soup2.get_text(strip=True)
            print(f"\n  Rendered text length: {len(body_text2)} chars (vs {len(body_text)} plain)")
            print(f"  First 500 chars:\n    {body_text2[:500]}")

            # Check all inputs
            inputs = page.query_selector_all("input, textarea, select")
            print(f"\n  Input elements ({len(inputs)}):")
            for inp in inputs:
                try:
                    print(f"    tag={inp.evaluate('el => el.tagName')} "
                          f"name={inp.get_attribute('name')} "
                          f"id={inp.get_attribute('id')} "
                          f"type={inp.get_attribute('type')} "
                          f"placeholder={inp.get_attribute('placeholder')}")
                except Exception:
                    pass

            # Now try to search
            api_calls.clear()
            print(f"\n  Attempting search for '{NAME}' ...")

            # Try common search input selectors
            search_input = None
            for sel in ["input[type='text']", "input[type='search']", "input[placeholder*='поис']",
                        "input[placeholder*='фамилия']", "input[placeholder*='имя']",
                        "input[name*='name']", "input[name*='person']", "input[name*='fio']",
                        "#searchInput", "#query", ".search-input input", "input"]:
                try:
                    el = page.query_selector(sel)
                    if el and el.is_visible():
                        search_input = el
                        print(f"  Found search input via selector: '{sel}'")
                        break
                except Exception:
                    continue

            if search_input:
                search_input.fill(NAME)
                time.sleep(1)
                # Try pressing Enter or finding a submit button
                page.keyboard.press("Enter")
                time.sleep(3)
                try:
                    page.wait_for_load_state("networkidle", timeout=15000)
                except Exception:
                    pass

                print(f"\n  XHR/fetch calls after search ({len(api_calls)}):")
                for call in api_calls[:20]:
                    print(f"    [{call['method']}] {call['url']}")
                    if call.get("post_data"):
                        print(f"          body: {call['post_data'][:400]}")

                # Save rendered HTML
                result_html = page.content()
                with open("/tmp/bsr_probe_playwright.html", "wb") as f:
                    f.write(result_html.encode("utf-8"))
                print(f"  Saved rendered HTML: /tmp/bsr_probe_playwright.html")

                # Count potential result elements
                soup3 = BeautifulSoup(result_html, "html.parser")
                result_text = soup3.get_text(strip=True)
                print(f"  Rendered result text length: {len(result_text)} chars")
                print(f"  Result text sample:\n    {result_text[:800]}")

                # Try to find result elements
                for sel in [".result", ".bsr-item", "tr[class*='result']", "li[class*='result']",
                             "[class*='case']", "[class*='decision']", "article", ".card",
                             "table tr", "ul li"]:
                    els = page.query_selector_all(sel)
                    if els:
                        print(f"  Selector '{sel}': {len(els)} elements")
                        try:
                            print(f"    First element text: {els[0].inner_text()[:200]}")
                        except Exception:
                            pass
                        break
            else:
                print("  ⚠️  No search input found on rendered page")

            with open("/tmp/bsr_probe_playwright.html", "wb") as f:
                f.write(page.content().encode("utf-8"))

        finally:
            browser.close()
            print("\n  Browser closed cleanly.")

except ImportError:
    print("Playwright not available — skipping Step 3")
except Exception as e:
    print(f"Playwright error: {e}")
    import traceback
    traceback.print_exc()

print(f"\n{SEP}")
print("PROBE COMPLETE")
print(f"Files written to /tmp/bsr_probe_*.html / .json")
print("Paste the full output back to Claude.")
print(SEP)
