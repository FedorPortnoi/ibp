"""Suite 1: Verify all pages load without errors."""
import time
import sys
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:5000"
PAGES = [
    ("/", "Homepage/redirect"),
    ("/phase1/new", "Phase 1 -- New Investigation"),
    ("/investigations", "Investigations List"),
    ("/dashboard", "Dashboard"),
    ("/vk/callback", "VK OAuth Callback"),
    ("/api/vk/token-status", "VK Token Status API"),
    ("/nonexistent-page-xyz", "404 Error Page"),
]


def run():
    results = []
    console_errors = []
    start = time.time()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        page.on("console", lambda msg: console_errors.append(f"[{msg.type}] {msg.text}") if msg.type == "error" else None)

        for path, name in PAGES:
            try:
                response = page.goto(f"{BASE}{path}", wait_until="domcontentloaded", timeout=15000)
                status = response.status if response else "no response"
                content = page.content()

                has_traceback = "Traceback" in content
                has_template_error = "TemplateSyntaxError" in content or "UndefinedError" in content
                has_500 = status == 500

                if path == "/nonexistent-page-xyz":
                    ok = status == 404 and not has_traceback
                    note = f"status={status}, custom 404={'yes' if not has_traceback else 'NO -- raw traceback!'}"
                elif path == "/api/vk/token-status":
                    ok = status == 200
                    note = f"status={status}, JSON API"
                else:
                    ok = status in [200, 302] and not has_traceback and not has_template_error
                    note = f"status={status}"
                    if has_traceback:
                        note += " TRACEBACK IN PAGE"
                    if has_template_error:
                        note += " TEMPLATE ERROR"
                    if has_500:
                        note += " 500 ERROR"

                slug = path.replace("/", "_").strip("_") or "root"
                page.screenshot(path=f"tests/screenshots/suite1_{slug}.png")

                icon = "PASS" if ok else "FAIL"
                results.append((icon, name, note))
                print(f"  [{icon}] {name}: {note}")

            except Exception as e:
                results.append(("FAIL", name, f"EXCEPTION: {e}"))
                print(f"  [FAIL] {name}: EXCEPTION: {e}")

        browser.close()

    elapsed = time.time() - start
    passed = sum(1 for r in results if r[0] == "PASS")
    print(f"\n  Time: {elapsed:.1f}s")
    print(f"  Screenshots: tests/screenshots/suite1_*.png")
    print(f"  Result: {passed}/{len(results)} passed")

    if console_errors:
        print(f"\n  Browser console errors:")
        for err in console_errors[:10]:
            print(f"    {err}")

    return passed == len(results)


if __name__ == "__main__":
    print("=" * 60)
    print("SUITE 1: PAGE LOAD SMOKE TEST")
    print("=" * 60)
    success = run()
    sys.exit(0 if success else 1)
