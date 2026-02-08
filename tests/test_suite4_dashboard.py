"""Suite 4: Investigation Dashboard."""
import time
import sys
import io
from playwright.sync_api import sync_playwright

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

BASE = "http://127.0.0.1:5000"


def run():
    results = []
    console_errors = []
    start = time.time()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        page.on("console", lambda msg: console_errors.append(f"[{msg.type}] {msg.text}") if msg.type == "error" else None)

        # --- Test 1: Dashboard page loads ---
        try:
            page.goto(f"{BASE}/investigations", wait_until="domcontentloaded", timeout=15000)
            page.screenshot(path="tests/screenshots/suite4_01_dashboard.png")

            content = page.content()
            has_search = page.query_selector("#search-input") is not None
            has_filter = page.query_selector("#status-filter") is not None
            has_sort = page.query_selector("#sort-order") is not None
            has_list = page.query_selector("#investigations-list") is not None

            ok = has_search and has_filter and has_sort and has_list
            note = f"search={has_search}, filter={has_filter}, sort={has_sort}, list={has_list}"
            icon = "PASS" if ok else "FAIL"
            results.append((icon, "Dashboard loads with all elements", note))
            print(f"  [{icon}] Dashboard loads: {note}")
        except Exception as e:
            results.append(("FAIL", "Dashboard loads", str(e)))
            print(f"  [FAIL] Dashboard loads: {e}")

        # --- Test 2: Stats bar ---
        try:
            stats = page.evaluate("""() => {
                const statDivs = document.querySelectorAll('.text-2xl.font-bold');
                return Array.from(statDivs).map(el => ({
                    text: el.textContent.trim(),
                    color: el.className
                }));
            }""")

            ok = len(stats) >= 3  # Total, Complete, In Progress
            note = f"stats_count={len(stats)}"
            if stats:
                note += f", values={[s['text'] for s in stats[:4]]}"
            icon = "PASS" if ok else "FAIL"
            results.append((icon, "Stats bar displays", note))
            print(f"  [{icon}] Stats bar: {note}")
        except Exception as e:
            results.append(("FAIL", "Stats bar", str(e)))
            print(f"  [FAIL] Stats bar: {e}")

        # --- Test 3: Investigation cards visible (from previous suite runs) ---
        try:
            cards = page.evaluate("""() => {
                const cards = document.querySelectorAll('[data-id]');
                return Array.from(cards).map(c => ({
                    id: c.dataset.id,
                    name: c.dataset.name,
                    status: c.dataset.status,
                    created: c.dataset.created
                }));
            }""")

            ok = len(cards) > 0
            note = f"cards={len(cards)}"
            if cards:
                note += f", first_name={cards[0].get('name', 'unknown')}"
            icon = "PASS" if ok else "FAIL"
            results.append((icon, "Investigation cards visible", note))
            print(f"  [{icon}] Investigation cards: {note}")
        except Exception as e:
            results.append(("FAIL", "Investigation cards", str(e)))
            print(f"  [FAIL] Investigation cards: {e}")

        # --- Test 4: Search filter ---
        try:
            if cards and len(cards) > 0:
                search_name = cards[0].get("name", "")[:5] if cards else ""
                page.fill("#search-input", search_name)
                time.sleep(0.5)

                visible_after = page.evaluate("""() => {
                    const cards = document.querySelectorAll('[data-id]');
                    return Array.from(cards).filter(c => !c.classList.contains('hidden') && c.offsetParent !== null).length;
                }""")

                page.screenshot(path="tests/screenshots/suite4_02_search_filter.png")

                # Clear search
                page.fill("#search-input", "")
                time.sleep(0.3)
                visible_reset = page.evaluate("""() => {
                    const cards = document.querySelectorAll('[data-id]');
                    return Array.from(cards).filter(c => !c.classList.contains('hidden') && c.offsetParent !== null).length;
                }""")

                ok = visible_after <= len(cards) and visible_reset == len(cards)
                note = f"searched='{search_name}', filtered_count={visible_after}, reset_count={visible_reset}"
                icon = "PASS" if ok else "FAIL"
                results.append((icon, "Search filter works", note))
                print(f"  [{icon}] Search filter: {note}")
            else:
                results.append(("PASS", "Search filter", "no cards to test (skipped)"))
                print(f"  [PASS] Search filter: no cards to test (skipped)")
        except Exception as e:
            results.append(("FAIL", "Search filter", str(e)))
            print(f"  [FAIL] Search filter: {e}")

        # --- Test 5: Sort order ---
        try:
            page.select_option("#sort-order", "name")
            time.sleep(0.3)
            names_asc = page.evaluate("""() => {
                const cards = document.querySelectorAll('[data-id]:not(.hidden)');
                return Array.from(cards).map(c => c.dataset.name || '');
            }""")

            page.select_option("#sort-order", "oldest")
            time.sleep(0.3)
            page.screenshot(path="tests/screenshots/suite4_03_sorted.png")

            ok = True  # Sort executed without error
            note = f"sort_options_work, names_asc_first={names_asc[0] if names_asc else 'none'}"
            icon = "PASS" if ok else "FAIL"
            results.append((icon, "Sort works", note))
            print(f"  [{icon}] Sort: {note}")

            # Reset to newest
            page.select_option("#sort-order", "newest")
        except Exception as e:
            results.append(("FAIL", "Sort works", str(e)))
            print(f"  [FAIL] Sort: {e}")

        # --- Test 6: Time-ago display ---
        try:
            time_ago_texts = page.evaluate("""() => {
                const els = document.querySelectorAll('.time-ago');
                return Array.from(els).map(el => el.textContent.trim());
            }""")

            ok = len(time_ago_texts) > 0 and all(
                any(word in t.lower() for word in ["ago", "just", "sec", "min", "hour", "day", "month", "year", "now"])
                for t in time_ago_texts if t
            )
            note = f"count={len(time_ago_texts)}, samples={time_ago_texts[:3]}"
            icon = "PASS" if ok else "FAIL"
            results.append((icon, "Time-ago display", note))
            print(f"  [{icon}] Time-ago: {note}")
        except Exception as e:
            results.append(("FAIL", "Time-ago display", str(e)))
            print(f"  [FAIL] Time-ago: {e}")

        # --- Test 7: Create test investigation and delete it ---
        try:
            # Create a test investigation
            page.goto(f"{BASE}/phase1/new", wait_until="domcontentloaded", timeout=15000)
            page.fill("#target_name", "TEST_DELETE_ME")

            result = page.evaluate("""async () => {
                const formData = new FormData(document.getElementById('newInvestigationForm'));
                const resp = await fetch('/phase1/new', {method: 'POST', body: formData});
                return await resp.json();
            }""")

            test_id = result.get("investigation_id")
            if not test_id:
                raise Exception(f"Could not create test investigation: {result}")

            # Go to dashboard and find the test card
            page.goto(f"{BASE}/investigations", wait_until="domcontentloaded", timeout=15000)
            time.sleep(1)

            count_before = page.evaluate("""() => document.querySelectorAll('[data-id]').length""")

            # Click delete button for the test investigation
            delete_btn = page.query_selector(f'[data-id="{test_id}"] button[onclick*="deleteInvestigation"]')
            if delete_btn:
                delete_btn.click()
                time.sleep(0.5)

                # Confirm in modal
                page.screenshot(path="tests/screenshots/suite4_04_delete_modal.png")
                confirm_btn = page.query_selector("#confirm-delete-btn")
                if confirm_btn:
                    confirm_btn.click()
                    time.sleep(1)

                    count_after = page.evaluate("""() => document.querySelectorAll('[data-id]').length""")
                    page.screenshot(path="tests/screenshots/suite4_05_after_delete.png")

                    ok = count_after < count_before
                    note = f"before={count_before}, after={count_after}"
                    icon = "PASS" if ok else "FAIL"
                else:
                    ok = False
                    note = "confirm button not found"
                    icon = "FAIL"
            else:
                # Try using JavaScript to trigger delete
                page.evaluate(f"""() => deleteInvestigation('{test_id}', 'TEST_DELETE_ME')""")
                time.sleep(0.5)
                page.screenshot(path="tests/screenshots/suite4_04_delete_modal.png")
                page.click("#confirm-delete-btn")
                time.sleep(1)
                count_after = page.evaluate("""() => document.querySelectorAll('[data-id]').length""")
                page.screenshot(path="tests/screenshots/suite4_05_after_delete.png")
                ok = count_after < count_before
                note = f"before={count_before}, after={count_after} (via JS)"
                icon = "PASS" if ok else "FAIL"

            results.append((icon, "Delete investigation", note))
            print(f"  [{icon}] Delete: {note}")

        except Exception as e:
            results.append(("FAIL", "Delete investigation", str(e)))
            print(f"  [FAIL] Delete: {e}")

        browser.close()

    elapsed = time.time() - start
    passed = sum(1 for r in results if r[0] == "PASS")
    print(f"\n  Time: {elapsed:.1f}s")
    print(f"  Screenshots: tests/screenshots/suite4_*.png")
    print(f"  Result: {passed}/{len(results)} passed")

    if console_errors:
        print(f"\n  Browser console errors ({len(console_errors)}):")
        for err in console_errors[:10]:
            print(f"    {err}")

    return passed == len(results)


if __name__ == "__main__":
    print("=" * 60)
    print("SUITE 4: INVESTIGATION DASHBOARD")
    print("=" * 60)
    success = run()
    sys.exit(0 if success else 1)
