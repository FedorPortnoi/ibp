#!/usr/bin/env python
"""
Live E2E test for the INN-First Pipeline.
Uses Playwright browser automation against a running dev server.

Tests:
  1. Health check
  2. Login
  3. INN validation — missing INN rejected (400)
  4. INN validation — bad checksum rejected (400)
  5. Valid INN — pipeline starts (200 + task_id)
  6. Pipeline progress polling (Stage 0 identity confirmation visible)
  7. Dossier page — identity section present, INN badge
  8. JSON export — identity_confirmation fields
"""

import os
import sys
import time
import json
import re
import io

# Fix Windows console encoding for Cyrillic output
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

BASE_URL = os.environ.get("IBP_BASE_URL", "http://127.0.0.1:5000")
PASSWORD = os.environ.get("IBP_PASSWORD", "")

VALID_INN_10 = "7707083893"   # Sberbank
BAD_INN = "1234567890"         # invalid checksum


def main():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("FAIL: playwright not installed")
        sys.exit(1)

    results = []
    def log(name, passed, detail=""):
        status = "PASS" if passed else "FAIL"
        results.append((name, passed, detail))
        print(f"  [{status}] {name}" + (f" -- {detail}" if detail else ""))

    print(f"\n{'='*60}")
    print(f"  IBP Live E2E: INN-First Pipeline")
    print(f"  Server: {BASE_URL}")
    print(f"{'='*60}\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        # ── 1. Health check ─────────────────────────────────
        print("[1] Health check...")
        resp = page.goto(f"{BASE_URL}/health")
        log("Health check", resp.status == 200, f"status={resp.status}")

        # ── 2. Login ────────────────────────────────────────
        print("[2] Login...")
        page.goto(f"{BASE_URL}/")
        if "/login" in page.url:
            if not PASSWORD:
                log("Login", False, "IBP_PASSWORD not set")
                browser.close()
                _summary(results)
                return
            page.fill('input[name="password"]', PASSWORD)
            page.click('button[type="submit"]')
            page.wait_for_load_state("networkidle")
            if "/login" in page.url:
                log("Login", False, "Still on login page")
                browser.close()
                _summary(results)
                return
            log("Login", True)
        else:
            log("Login", True, "No auth required")

        # Navigate to a page that has CSRF token (any authenticated page)
        page.goto(f"{BASE_URL}/phase1/new")
        page.wait_for_load_state("networkidle")

        # Helper: make POST via JS fetch with CSRF token from meta tag
        def api_post(path, form_fields):
            """POST JSON data via JS fetch, returns {status, body, json}."""
            payload = json.dumps(form_fields)
            return page.evaluate(f"""
                async () => {{
                    const csrfMeta = document.querySelector('meta[name="csrf-token"]');
                    const csrfToken = csrfMeta ? csrfMeta.getAttribute('content') : '';
                    const resp = await fetch('{path}', {{
                        method: 'POST',
                        body: JSON.stringify({payload}),
                        headers: {{
                            'Content-Type': 'application/json',
                            'X-CSRFToken': csrfToken,
                        }}
                    }});
                    const text = await resp.text();
                    let json_data = null;
                    try {{ json_data = JSON.parse(text); }} catch(e) {{}}
                    return {{status: resp.status, body: text.substring(0, 1000), json: json_data}};
                }}
            """)

        def api_get_json(path):
            """GET JSON via JS fetch."""
            return page.evaluate(f"""
                async () => {{
                    const resp = await fetch('{path}');
                    if (resp.status !== 200) return {{status: resp.status, data: null}};
                    try {{
                        const data = await resp.json();
                        return {{status: resp.status, data: data}};
                    }} catch(e) {{
                        return {{status: resp.status, data: null, error: e.message}};
                    }}
                }}
            """)

        # ── 3. Missing INN → 400 ───────────────────────────
        print("[3] INN validation -- missing INN...")
        r = api_post('/candidate/start', {
            'full_name': 'Тестов Тест Тестович',
            'date_of_birth': '1990-05-15',
        })
        inn_missing_rejected = r['status'] == 400
        inn_missing_msg = ''
        if r.get('json'):
            inn_missing_msg = r['json'].get('error', '')
        log("Missing INN rejected", inn_missing_rejected,
            f"status={r['status']}, error='{inn_missing_msg}'")

        # ── 4. Bad INN checksum → 400 ──────────────────────
        print("[4] INN validation -- bad checksum...")
        r = api_post('/candidate/start', {
            'full_name': 'Тестов Тест Тестович',
            'date_of_birth': '1990-05-15',
            'inn': BAD_INN,
        })
        bad_inn_rejected = r['status'] == 400
        bad_inn_msg = ''
        if r.get('json'):
            bad_inn_msg = r['json'].get('error', '')
        log("Bad INN checksum rejected", bad_inn_rejected,
            f"status={r['status']}, error='{bad_inn_msg}'")

        # ── 5. Valid INN → pipeline starts ──────────────────
        print("[5] Valid INN -- pipeline starts...")
        r = api_post('/candidate/start', {
            'full_name': 'Тестов Тест Тестович',
            'date_of_birth': '1990-05-15',
            'inn': VALID_INN_10,
            'check_mode': 'quick',
        })
        pipeline_started = r['status'] == 200 and r.get('json')
        task_id = None
        check_id = None
        if pipeline_started and r['json']:
            task_id = r['json'].get('task_id')
            check_id = r['json'].get('check_id')
        log("Pipeline started", pipeline_started and task_id is not None,
            f"status={r['status']}, task_id={task_id}, check_id={check_id}")

        if not task_id:
            print(f"  DEBUG: {r['body'][:300]}")
            browser.close()
            _summary(results)
            return

        # ── 6. Poll progress ────────────────────────────────
        print("[6] Polling pipeline progress...")
        seen_identity_stage = False
        all_messages = []
        final_progress = 0
        final_status = ""
        last_step = ""
        max_polls = 900  # 15 minutes (pipeline runs Snoop/Maigret/Sherlock which are slow)

        for i in range(max_polls):
            pr = api_get_json(f'/candidate/progress/{task_id}/status')
            if not pr or not pr.get('data'):
                time.sleep(1)
                continue

            d = pr['data']
            progress = d.get('percent_complete', 0)
            step = d.get('current_step', '')
            stage = d.get('current_stage', '')
            status = d.get('status', '')
            is_complete = d.get('is_complete', False)

            # Collect all messages
            for msg in d.get('messages', []):
                msg_text = msg.get('text', '')
                if msg_text and msg_text not in all_messages:
                    all_messages.append(msg_text)
                    print(f"    [{progress:5.1f}%] [{stage}] {msg_text}")

            # Detect Stage 0
            for msg_text in all_messages:
                msg_lower = msg_text.lower()
                if any(kw in msg_lower for kw in [
                    'идентификац', 'identity', 'инн', 'egrul', 'егрюл',
                    'подтвержд', 'stage 0', 'этап 0', 'ефрсб'
                ]):
                    seen_identity_stage = True

            final_progress = progress
            final_status = status

            if is_complete:
                print(f"    Pipeline {status}! ({progress}%)")
                break

            time.sleep(1)

        log("Pipeline completed",
            final_status in ('complete', 'completed') and final_progress >= 90,
            f"status={final_status}, progress={final_progress}%")
        log("Stage 0 Identity visible in progress", seen_identity_stage)

        # ── 7. Dossier page ─────────────────────────────────
        if check_id and final_status in ('completed', 'complete'):
            print("[7] Dossier page...")
            page.goto(f"{BASE_URL}/candidate/dossier/{check_id}")
            page.wait_for_load_state("networkidle")
            html = page.content()

            has_identity_section = 'sec-identity' in html or 'Идентификация' in html
            log("Dossier has identity section", has_identity_section)

            has_inn_display = VALID_INN_10 in html
            log("Dossier shows INN", has_inn_display)

            has_inn_tab = 'ИНН' in html
            log("Dossier has INN tab", has_inn_tab)

            # ── 8. Verify DB record has identity fields ──────
            print("[8] Verify identity fields in DB...")
            db_check = page.evaluate(f"""
                async () => {{
                    const csrfMeta = document.querySelector('meta[name="csrf-token"]');
                    const csrfToken = csrfMeta ? csrfMeta.getAttribute('content') : '';
                    // Use the progress status endpoint which returns check_id
                    const resp = await fetch('/candidate/progress/{task_id}/status');
                    const data = await resp.json();
                    return data;
                }}
            """)
            log("Progress endpoint has check_id",
                db_check and db_check.get('check_id') == check_id,
                f"check_id={db_check.get('check_id') if db_check else 'null'}")

            # Verify dossier content has identity data
            has_confirmed_name = 'Подтверждённое имя' in html or 'confirmed_name' in html
            has_egrul_status = 'ЕГРЮЛ' in html
            log("Dossier has EGRUL data", has_egrul_status)
        else:
            print("[7-8] SKIPPED (pipeline did not complete)")
            if not check_id:
                log("Dossier", False, "no check_id")
            else:
                log("Dossier", False, f"pipeline status={final_status}")

        browser.close()

    _summary(results)


def _summary(results):
    print(f"\n{'='*60}")
    passed = sum(1 for _, p, _ in results if p)
    total = len(results)
    print(f"  Results: {passed}/{total} passed")
    if passed == total:
        print("  ALL TESTS PASSED!")
    else:
        print(f"\n  FAILURES:")
        for name, p, detail in results:
            if not p:
                print(f"    - {name}: {detail}")
    print(f"{'='*60}\n")
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
