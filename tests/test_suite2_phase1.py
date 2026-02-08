"""Suite 2: Phase 1 Search -- Full Flow (VK People Search)."""
import time
import sys
import json
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:5000"


def submit_phase1(page, name):
    """Submit a Phase 1 search via fetch and return the JSON response."""
    result = page.evaluate(f"""async () => {{
        const formData = new FormData();
        formData.append('target_name', '{name}');
        const resp = await fetch('/phase1/new', {{method: 'POST', body: formData}});
        return {{status: resp.status, body: await resp.json()}};
    }}""")
    return result


def run():
    results = []
    console_errors = []
    start = time.time()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        page.on("console", lambda msg: console_errors.append(f"[{msg.type}] {msg.text}") if msg.type == "error" else None)

        # --- Test 1: Navigate to Phase 1 new investigation page ---
        try:
            page.goto(f"{BASE}/phase1/new", wait_until="domcontentloaded", timeout=15000)
            form = page.query_selector("#newInvestigationForm")
            name_input = page.query_selector("#target_name")
            submit_btn = page.query_selector("#submitBtn")

            ok = form is not None and name_input is not None and submit_btn is not None
            page.screenshot(path="tests/screenshots/suite2_01_empty_form.png")
            icon = "PASS" if ok else "FAIL"
            results.append((icon, "Phase 1 form loads", f"form={'yes' if form else 'NO'}, input={'yes' if name_input else 'NO'}"))
            print(f"  [{icon}] Phase 1 form loads")
        except Exception as e:
            results.append(("FAIL", "Phase 1 form loads", str(e)))
            print(f"  [FAIL] Phase 1 form loads: {e}")

        # --- Test 2: Submit Cyrillic name ---
        investigation_id = None
        try:
            page.goto(f"{BASE}/phase1/new", wait_until="domcontentloaded", timeout=15000)
            page.fill("#target_name", "\u0422\u0438\u0445\u043e\u043d \u041f\u043e\u0440\u0442\u043d\u043e\u0439")
            page.screenshot(path="tests/screenshots/suite2_02_filled_form.png")

            t0 = time.time()
            result = page.evaluate("""async () => {
                const formData = new FormData(document.getElementById('newInvestigationForm'));
                const resp = await fetch('/phase1/new', {method: 'POST', body: formData});
                return {status: resp.status, body: await resp.json()};
            }""")
            create_time = time.time() - t0

            body = result.get("body", {})
            ok = body.get("success") is True and "investigation_id" in body
            investigation_id = body.get("investigation_id")
            note = f"success={body.get('success')}, id={investigation_id}, create_time={create_time:.1f}s"
            icon = "PASS" if ok else "FAIL"
            results.append((icon, "Create investigation (Cyrillic)", note))
            print(f"  [{icon}] Create investigation (Cyrillic): {note}")

        except Exception as e:
            results.append(("FAIL", "Create investigation (Cyrillic)", str(e)))
            print(f"  [FAIL] Create investigation (Cyrillic): {e}")

        # --- Test 3: Load search results page ---
        if investigation_id:
            try:
                t0 = time.time()
                page.goto(f"{BASE}/phase1/search/{investigation_id}", wait_until="domcontentloaded", timeout=180000)
                search_time = time.time() - t0
                time.sleep(2)
                page.screenshot(path="tests/screenshots/suite2_03_search_results.png")

                content = page.content()

                # Check for profiles in page - look for common patterns
                has_results_text = any(term in content for term in ["profile", "vk.com", "Найдено", "результат", "confirm", "data-profile"])
                has_error = "Traceback" in content or "Internal Server Error" in content

                # Try to extract profile names for verification
                profile_names = page.evaluate("""() => {
                    const cards = document.querySelectorAll('[data-profile-id], .profile-card, .result-card, .vk-result');
                    return Array.from(cards).map(c => c.textContent.trim().substring(0, 100));
                }""")

                ok = has_results_text and not has_error
                note = f"time={search_time:.1f}s, has_results={has_results_text}, profiles_found={len(profile_names)}"
                icon = "PASS" if ok else "FAIL"
                results.append((icon, "Search results (Cyrillic)", note))
                print(f"  [{icon}] Search results (Cyrillic): {note}")

                if profile_names:
                    for pn in profile_names[:3]:
                        print(f"    Profile: {pn[:60]}...")

            except Exception as e:
                results.append(("FAIL", "Search results (Cyrillic)", str(e)))
                print(f"  [FAIL] Search results (Cyrillic): {e}")

        # --- Test 4: Submit Latin name ---
        try:
            page.goto(f"{BASE}/phase1/new", wait_until="domcontentloaded", timeout=15000)
            page.fill("#target_name", "Tikhon Portnoi")

            t0 = time.time()
            result = page.evaluate("""async () => {
                const formData = new FormData(document.getElementById('newInvestigationForm'));
                const resp = await fetch('/phase1/new', {method: 'POST', body: formData});
                return {status: resp.status, body: await resp.json()};
            }""")
            create_time = time.time() - t0

            body = result.get("body", {})
            latin_id = body.get("investigation_id")
            ok = body.get("success") is True

            if latin_id:
                t0 = time.time()
                page.goto(f"{BASE}/phase1/search/{latin_id}", wait_until="domcontentloaded", timeout=180000)
                latin_search_time = time.time() - t0
                time.sleep(2)
                page.screenshot(path="tests/screenshots/suite2_04_latin_results.png")
                content = page.content()
                has_error = "Traceback" in content or "Internal Server Error" in content
                ok = ok and not has_error
                note = f"id={latin_id}, search_time={latin_search_time:.1f}s"
            else:
                note = f"creation failed: {body}"

            icon = "PASS" if ok else "FAIL"
            results.append((icon, "Latin name search", note))
            print(f"  [{icon}] Latin name search: {note}")

        except Exception as e:
            results.append(("FAIL", "Latin name search", str(e)))
            print(f"  [FAIL] Latin name search: {e}")

        # --- Test 5: Submit empty name ---
        try:
            page.goto(f"{BASE}/phase1/new", wait_until="domcontentloaded", timeout=15000)
            result = page.evaluate("""async () => {
                const formData = new FormData();
                formData.append('target_name', '');
                const resp = await fetch('/phase1/new', {method: 'POST', body: formData});
                return {status: resp.status, body: await resp.text()};
            }""")

            status = result.get("status", 0)
            ok = status == 400
            page.screenshot(path="tests/screenshots/suite2_05_empty_name.png")
            icon = "PASS" if ok else "FAIL"
            note = f"status={status} (expected 400)"
            results.append((icon, "Empty name rejected", note))
            print(f"  [{icon}] Empty name rejected: {note}")

        except Exception as e:
            results.append(("FAIL", "Empty name rejected", str(e)))
            print(f"  [FAIL] Empty name rejected: {e}")

        browser.close()

    elapsed = time.time() - start
    passed = sum(1 for r in results if r[0] == "PASS")
    print(f"\n  Time: {elapsed:.1f}s")
    print(f"  Screenshots: tests/screenshots/suite2_*.png")
    print(f"  Result: {passed}/{len(results)} passed")

    if console_errors:
        print(f"\n  Browser console errors ({len(console_errors)}):")
        for err in console_errors[:10]:
            print(f"    {err}")

    return passed == len(results)


if __name__ == "__main__":
    print("=" * 60)
    print("SUITE 2: PHASE 1 SEARCH -- FULL FLOW")
    print("=" * 60)
    success = run()
    sys.exit(0 if success else 1)
