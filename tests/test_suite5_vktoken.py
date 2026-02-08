"""Suite 5: VK Token Management UI."""
import time
import sys
import io
import json
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

        # --- Test 1: Token status API ---
        try:
            response = page.goto(f"{BASE}/api/vk/token-status", wait_until="domcontentloaded", timeout=15000)
            content = page.inner_text("body")
            data = json.loads(content)

            has_valid = "valid" in data
            has_detail = "token_type" in data or "expires" in data or "error" in data or "masked_token" in data

            ok = has_valid and response.status == 200
            note = f"valid={data.get('valid')}, keys={list(data.keys())}"
            icon = "PASS" if ok else "FAIL"
            results.append((icon, "Token status API", note))
            print(f"  [{icon}] Token status API: {note}")
        except Exception as e:
            results.append(("FAIL", "Token status API", str(e)))
            print(f"  [FAIL] Token status API: {e}")

        # --- Test 2: Navbar VK indicator ---
        try:
            page.goto(f"{BASE}/phase1/new", wait_until="domcontentloaded", timeout=15000)
            time.sleep(2)  # Wait for token check to complete

            # Look for VK status indicator
            indicator = page.evaluate("""() => {
                // Look for elements that indicate VK status
                const els = document.querySelectorAll('[id*="vk"], [class*="vk"], [data-vk], .token-status, .vk-status');
                const allText = document.body.innerHTML;
                const hasVkIndicator = allText.includes('token-status') || allText.includes('vk-status') || allText.includes('vk_indicator');

                // Also look for colored dots (green/yellow/red)
                const dots = document.querySelectorAll('.bg-green-500, .bg-yellow-500, .bg-red-500, .text-green-400, .text-yellow-400, .text-red-400');

                return {
                    vk_elements: els.length,
                    has_indicator_html: hasVkIndicator,
                    colored_dots: dots.length
                };
            }""")

            page.screenshot(path="tests/screenshots/suite5_01_navbar.png")

            ok = indicator.get("colored_dots", 0) > 0 or indicator.get("has_indicator_html", False)
            note = f"vk_elements={indicator.get('vk_elements')}, colored_dots={indicator.get('colored_dots')}, html_indicator={indicator.get('has_indicator_html')}"
            icon = "PASS" if ok else "FAIL"
            results.append((icon, "Navbar VK indicator", note))
            print(f"  [{icon}] Navbar VK indicator: {note}")
        except Exception as e:
            results.append(("FAIL", "Navbar VK indicator", str(e)))
            print(f"  [FAIL] Navbar VK indicator: {e}")

        # --- Test 3: VK callback page ---
        try:
            response = page.goto(f"{BASE}/vk/callback", wait_until="domcontentloaded", timeout=15000)
            content = page.content()

            ok = response.status == 200 and "Traceback" not in content
            page.screenshot(path="tests/screenshots/suite5_02_vk_callback.png")
            note = f"status={response.status}"
            icon = "PASS" if ok else "FAIL"
            results.append((icon, "VK callback page", note))
            print(f"  [{icon}] VK callback page: {note}")
        except Exception as e:
            results.append(("FAIL", "VK callback page", str(e)))
            print(f"  [FAIL] VK callback page: {e}")

        # --- Test 4: Token save with invalid token ---
        try:
            result = page.evaluate("""async () => {
                const resp = await fetch('/vk/save-token', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({token: 'invalid_test_token'})
                });
                return {status: resp.status, body: await resp.text()};
            }""")

            status = result.get("status", 0)
            # Should return an error, not crash (400 or 200 with error message both acceptable)
            ok = status in [200, 400] and "Traceback" not in result.get("body", "")
            note = f"status={status}, body_preview={result.get('body', '')[:100]}"
            icon = "PASS" if ok else "FAIL"
            results.append((icon, "Save invalid token (error handling)", note))
            print(f"  [{icon}] Save invalid token: {note}")
        except Exception as e:
            results.append(("FAIL", "Save invalid token", str(e)))
            print(f"  [FAIL] Save invalid token: {e}")

        browser.close()

    elapsed = time.time() - start
    passed = sum(1 for r in results if r[0] == "PASS")
    print(f"\n  Time: {elapsed:.1f}s")
    print(f"  Screenshots: tests/screenshots/suite5_*.png")
    print(f"  Result: {passed}/{len(results)} passed")

    if console_errors:
        print(f"\n  Browser console errors ({len(console_errors)}):")
        for err in console_errors[:10]:
            print(f"    {err}")

    return passed == len(results)


if __name__ == "__main__":
    print("=" * 60)
    print("SUITE 5: VK TOKEN MANAGEMENT UI")
    print("=" * 60)
    success = run()
    sys.exit(0 if success else 1)
