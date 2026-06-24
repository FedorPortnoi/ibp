"""Diagnose exactly what happens when the candidate form is submitted."""
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:5000"
USER = "Fedor"
PASS = "vdohnoviteligorborisovichportnoisozdatelfedorigorevichportnoiproductluchshebyratino9"
TEST_INN = "773605001337"

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context()
        page = ctx.new_page()

        alerts = []
        page.on("dialog", lambda d: (alerts.append(d.message), d.dismiss()))

        # Log all navigations
        page.on("framenavigated", lambda f: print(f"  [nav] {f.url}") if f == page.main_frame else None)

        # Log all requests to /candidate/start
        page.on("request", lambda r: print(f"  [req] {r.method} {r.url}") if "/candidate" in r.url else None)
        page.on("response", lambda r: print(f"  [resp] {r.status} {r.url}") if "/candidate" in r.url else None)

        # Login
        page.goto(BASE + "/login")
        page.wait_for_load_state("networkidle")
        page.fill("input[name=username]", USER)
        page.fill("input[name=password]", PASS)
        page.click("button[type=submit]")
        page.wait_for_url(BASE + "/dashboard")
        print(f"Logged in. URL: {page.url}")
        print(f"Session cookie secure: {next((c.get('secure') for c in ctx.cookies() if c['name']=='session'), 'N/A')}")

        # Go to candidate form
        page.goto(BASE + "/candidate/new")
        page.wait_for_load_state("networkidle")
        print(f"\nAt /candidate/new. URL: {page.url}")

        # Fill form
        page.fill("input[name=full_name]", "Иванов Петр Сергеевич")
        page.fill("input[name=date_of_birth]", "1985-03-15")
        page.fill("input[name=inn]", TEST_INN)

        # Check pd_consent
        cb = page.locator("input[name=pd_consent]")
        if cb.count() > 0:
            if not cb.is_checked():
                cb.check()
            print(f"pd_consent checked: {cb.is_checked()}")

        # Select quick mode
        qm = page.locator("input[name=check_mode][value=quick]")
        if qm.count() > 0:
            qm.check()
            print(f"check_mode quick selected: {qm.is_checked()}")

        # Get all form values via JS
        form_data = page.evaluate("""() => {
            const fd = new FormData(document.getElementById('candidate-form'));
            const obj = {};
            for (let [k,v] of fd.entries()) { obj[k] = v; }
            return obj;
        }""")
        print(f"\nForm data that will be submitted: {form_data}")

        # Click submit, wait for navigation
        print("\nClicking submit...")
        with page.expect_navigation(timeout=10000, wait_until="networkidle") as nav_info:
            page.click("button[type=submit]")

        print(f"\nNavigation complete. Final URL: {page.url}")
        print(f"Alerts: {alerts}")

        # Print page title/content hint
        try:
            title = page.title()
            print(f"Page title: {title}")
        except:
            pass

        browser.close()

run()
