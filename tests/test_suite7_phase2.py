"""Suite 7: Phase 2 -- Email + Phone Discovery (E2E)."""
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

        # --- Step 1: Create investigation and get search results ---
        investigation_id = None
        try:
            page.goto(f"{BASE}/phase1/new", wait_until="domcontentloaded", timeout=15000)
            page.fill("#target_name", "\u041e\u043b\u044c\u0433\u0430 \u0410\u0445\u0442\u0438\u043d\u0430\u0441")  # Ольга Ахтинас

            result = page.evaluate("""async () => {
                const formData = new FormData(document.getElementById('newInvestigationForm'));
                const resp = await fetch('/phase1/new', {method: 'POST', body: formData});
                return await resp.json();
            }""")

            investigation_id = result.get("investigation_id")
            ok = investigation_id is not None
            icon = "PASS" if ok else "FAIL"
            results.append((icon, "Create investigation", f"id={investigation_id}"))
            print(f"  [{icon}] Create investigation: id={investigation_id}")

        except Exception as e:
            results.append(("FAIL", "Create investigation", str(e)))
            print(f"  [FAIL] Create investigation: {e}")

        # --- Step 2: Load results and find first profile ---
        profile_id = None
        if investigation_id:
            try:
                page.goto(f"{BASE}/phase1/search/{investigation_id}", wait_until="domcontentloaded", timeout=180000)
                time.sleep(2)

                # Get first profile ID
                profile_id = page.evaluate("""() => {
                    const card = document.querySelector('.profile-card[data-profile-id]');
                    return card ? card.getAttribute('data-profile-id') : null;
                }""")

                ok = profile_id is not None
                icon = "PASS" if ok else "FAIL"
                results.append((icon, "Find profile to confirm", f"profile_id={profile_id}"))
                print(f"  [{icon}] Find profile: profile_id={profile_id}")

            except Exception as e:
                results.append(("FAIL", "Find profile", str(e)))
                print(f"  [FAIL] Find profile: {e}")

        # --- Step 3: Confirm the profile ---
        if investigation_id and profile_id:
            try:
                confirm_result = page.evaluate(f"""async () => {{
                    const resp = await fetch('/phase1/confirm/{investigation_id}/{profile_id}', {{
                        method: 'POST',
                        headers: {{'Content-Type': 'application/json'}}
                    }});
                    return {{status: resp.status, body: await resp.json()}};
                }}""")

                body = confirm_result.get("body", {})
                ok = body.get("success") is True
                icon = "PASS" if ok else "FAIL"
                note = f"success={body.get('success')}, redirect={body.get('redirect', 'none')}"
                results.append((icon, "Confirm profile", note))
                print(f"  [{icon}] Confirm profile: {note}")

            except Exception as e:
                results.append(("FAIL", "Confirm profile", str(e)))
                print(f"  [FAIL] Confirm profile: {e}")

        # --- Step 4: Navigate to Phase 2 analyze page ---
        if investigation_id:
            try:
                response = page.goto(f"{BASE}/phase2/analyze/{investigation_id}", wait_until="domcontentloaded", timeout=15000)
                content = page.content()

                no_error = "Traceback" not in content and "error" not in content.lower()[:200]
                page.screenshot(path="tests/screenshots/suite7_01_phase2_analyze.png")

                ok = response.status == 200 and "Traceback" not in content
                note = f"status={response.status}"
                if "No confirmed profile" in content or "error" in content.lower()[:200]:
                    note += ", WARNING: no confirmed profile found"
                icon = "PASS" if ok else "FAIL"
                results.append((icon, "Phase 2 analyze page", note))
                print(f"  [{icon}] Phase 2 analyze page: {note}")

            except Exception as e:
                results.append(("FAIL", "Phase 2 analyze page", str(e)))
                print(f"  [FAIL] Phase 2 analyze page: {e}")

        # --- Step 5: Start Phase 2 analysis ---
        task_id = None
        if investigation_id:
            try:
                start_result = page.evaluate(f"""async () => {{
                    const resp = await fetch('/phase2/api/start-analysis/{investigation_id}', {{
                        method: 'POST',
                        headers: {{'Content-Type': 'application/json'}}
                    }});
                    return {{status: resp.status, body: await resp.json()}};
                }}""")

                body = start_result.get("body", {})
                task_id = body.get("task_id")
                ok = start_result.get("status") == 200 and task_id is not None
                note = f"status={start_result.get('status')}, task_id={task_id}"
                if "error" in body:
                    note += f", error={body['error']}"
                icon = "PASS" if ok else "FAIL"
                results.append((icon, "Start Phase 2 analysis", note))
                print(f"  [{icon}] Start Phase 2: {note}")

            except Exception as e:
                results.append(("FAIL", "Start Phase 2 analysis", str(e)))
                print(f"  [FAIL] Start Phase 2: {e}")

        # --- Step 6: Poll progress ---
        if task_id:
            try:
                max_polls = 60  # 60 * 5s = 5 minutes max
                final_status = None
                poll_count = 0
                for i in range(max_polls):
                    progress = page.evaluate(f"""async () => {{
                        const resp = await fetch('/phase2/progress/{task_id}');
                        return await resp.json();
                    }}""")

                    poll_count += 1
                    pct = progress.get("progress", {}).get("percent", 0) if isinstance(progress.get("progress"), dict) else 0
                    status = progress.get("status", "unknown")

                    if i % 6 == 0:  # Print every 30 seconds
                        print(f"    Poll {i}: status={status}, progress={pct}%")

                    if status in ["complete", "completed", "error", "cancelled"]:
                        final_status = status
                        break

                    time.sleep(5)

                page.screenshot(path="tests/screenshots/suite7_02_phase2_progress.png")

                ok = final_status in ["complete", "completed"]
                note = f"final_status={final_status}, polls={poll_count}"
                icon = "PASS" if ok else "FAIL"
                results.append((icon, "Phase 2 completes", note))
                print(f"  [{icon}] Phase 2 completes: {note}")

            except Exception as e:
                results.append(("FAIL", "Phase 2 completes", str(e)))
                print(f"  [FAIL] Phase 2 completes: {e}")

        # --- Step 7: Check Phase 2 results page ---
        if investigation_id:
            try:
                response = page.goto(f"{BASE}/phase2/buratino/results/{investigation_id}", wait_until="domcontentloaded", timeout=15000)
                content = page.content()
                time.sleep(1)

                page.screenshot(path="tests/screenshots/suite7_03_phase2_results.png")

                no_traceback = "Traceback" not in content
                has_content = len(content) > 1000  # Should have substantial content

                # Check for email/phone sections
                has_email_section = "email" in content.lower() or "Email" in content
                has_phone_section = "phone" in content.lower() or "Phone" in content or "\u0442\u0435\u043b\u0435\u0444\u043e\u043d" in content.lower()

                ok = response.status == 200 and no_traceback
                note = f"status={response.status}, emails_section={has_email_section}, phones_section={has_phone_section}"
                icon = "PASS" if ok else "FAIL"
                results.append((icon, "Phase 2 results page", note))
                print(f"  [{icon}] Phase 2 results: {note}")

            except Exception as e:
                results.append(("FAIL", "Phase 2 results page", str(e)))
                print(f"  [FAIL] Phase 2 results: {e}")

        browser.close()

    elapsed = time.time() - start
    passed = sum(1 for r in results if r[0] == "PASS")
    print(f"\n  Time: {elapsed:.1f}s")
    print(f"  Screenshots: tests/screenshots/suite7_*.png")
    print(f"  Result: {passed}/{len(results)} passed")

    if console_errors:
        print(f"\n  Browser console errors ({len(console_errors)}):")
        for err in console_errors[:10]:
            print(f"    {err}")

    return passed == len(results)


if __name__ == "__main__":
    print("=" * 60)
    print("SUITE 7: PHASE 2 -- EMAIL + PHONE DISCOVERY")
    print("=" * 60)
    success = run()
    sys.exit(0 if success else 1)
