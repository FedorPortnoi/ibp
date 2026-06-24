"""Minimal Playwright session diagnostic."""
import sys
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:5000"
USER = "Fedor"
PASS = "vdohnoviteligorborisovichportnoisozdatelfedorigorevichportnoiproductluchshebyratino9"

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context()
        page = ctx.new_page()

        # Auto-dismiss alerts
        page.on("dialog", lambda d: (print(f"  [ALERT] {d.message[:80]}"), d.dismiss()))

        # Step 1: Go to /login
        page.goto(BASE + "/login")
        page.wait_for_load_state("networkidle")
        print(f"1) /login -> actual URL: {page.url}")
        cookies = ctx.cookies()
        print(f"   cookies: {[(c['name'], c.get('secure'), c.get('sameSite')) for c in cookies]}")

        # Step 2: Is there a session cookie already?
        session_cookie = next((c for c in cookies if c['name'] == 'session'), None)
        print(f"   session: {session_cookie['value'][:30] if session_cookie else 'NONE'}")

        # Step 3: Check if login form exists
        username_count = page.locator("input[name=username]").count()
        print(f"   input[name=username] count: {username_count}")

        # Step 4: Log in
        if username_count > 0:
            page.fill("input[name=username]", USER)
            page.fill("input[name=password]", PASS)
            page.click("button[type=submit]")
            page.wait_for_load_state("networkidle")

        print(f"2) After login click -> URL: {page.url}")
        cookies2 = ctx.cookies()
        sc2 = next((c for c in cookies2 if c['name'] == 'session'), None)
        print(f"   session cookie: {sc2['value'][:30] if sc2 else 'NONE'}")
        print(f"   secure flag: {sc2.get('secure') if sc2 else 'N/A'}")

        # Step 5: Navigate to candidate form
        page.goto(BASE + "/candidate/new")
        page.wait_for_load_state("networkidle")
        print(f"3) /candidate/new -> URL: {page.url}")
        cookies3 = ctx.cookies()
        sc3 = next((c for c in cookies3 if c['name'] == 'session'), None)
        print(f"   session cookie: {sc3['value'][:30] if sc3 else 'NONE'}")

        # Step 6: Try to POST to /candidate/start via fetch (simulating what the JS does)
        result = page.evaluate("""async () => {
            const resp = await fetch('/candidate/start', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    full_name: 'Иванов Петр Сергеевич',
                    date_of_birth: '1985-03-15',
                    inn: '123456789012',
                    pd_consent: 'true',
                    check_mode: 'quick'
                })
            });
            const text = await resp.text();
            return {status: resp.status, url: resp.url, body: text.substring(0, 200)};
        }""")
        print(f"4) fetch /candidate/start -> status: {result['status']}")
        print(f"   final URL: {result['url']}")
        print(f"   body: {result['body'][:150]}")

        browser.close()

run()
