"""
Full investigator E2E walkthrough for Stirlitz (IBP).
Navigates every screen, takes screenshots, reports issues.
Run with: python scripts/e2e_walkthrough.py
"""

import os, sys, time, json, io
from pathlib import Path

# Force UTF-8 stdout so Cyrillic text in titles/content doesn't crash on cp1252 consoles
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from playwright.sync_api import sync_playwright, Page

BASE_URL = "http://127.0.0.1:5000"
SCREENSHOT_DIR = Path("scripts/e2e_screenshots")
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

ADMIN_USER = "Fedor"
ADMIN_PASS = "vdohnoviteligorborisovichportnoisozdatelfedorigorevichportnoiproductluchshebyratino9"

# Valid Russian INN for test candidate (12-digit individual)
TEST_INN = "773605001337"
# Valid company INN (Gazprom)
COMPANY_INN = "7736050003"

issues = []
alerts_seen = []

def shot(page: Page, name: str):
    path = SCREENSHOT_DIR / f"{name}.png"
    page.screenshot(path=str(path), full_page=True)
    print(f"  [shot] {name} @ {page.url}")
    return path

def flag(screen: str, problem: str):
    issues.append({"screen": screen, "problem": problem})
    print(f"  [!!] [{screen}] {problem}")

def ok(msg: str):
    print(f"  [ok] {msg}")


def run_walkthrough():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, slow_mo=100)
        ctx = browser.new_context(viewport={"width": 1400, "height": 900})
        page = ctx.new_page()

        # Capture and dismiss all alerts
        def on_dialog(dialog):
            msg = dialog.message
            alerts_seen.append(msg)
            print(f"  [alert] {msg[:100]}")
            dialog.dismiss()
        page.on("dialog", on_dialog)

        # ── 1. LOGIN PAGE ─────────────────────────────────────────────
        print("\n=== [1] LOGIN PAGE ===")
        page.goto(BASE_URL + "/login")
        page.wait_for_load_state("networkidle")
        shot(page, "01_login")

        # Confirm we are on the login/marketing page (not dashboard)
        if page.url != BASE_URL + "/login":
            flag("login", f"Navigated away from /login immediately — ended at {page.url}")
        else:
            ok("Login page loaded")

        # Check login form exists
        username_count = page.locator("input[name=username]").count()
        password_count = page.locator("input[name=password]").count()
        if username_count == 0:
            flag("login", "No username input found")
        if password_count == 0:
            flag("login", "No password input found")

        # Test wrong password → should show error
        page.fill("input[name=username]", "Fedor")
        page.fill("input[name=password]", "wrongpassword")
        page.click("button[type=submit]")
        page.wait_for_load_state("networkidle")
        shot(page, "02_login_wrong_pass")

        # Error message check: look for flash-err div with 'on' class, or any error text
        has_error = (
            page.locator("#flash-err.on").count() > 0 or
            page.locator(".auth-err.on").count() > 0 or
            page.locator("text=Неверн").count() > 0 or
            page.locator("text=Invalid").count() > 0
        )
        if not has_error:
            flag("login", "Wrong password: no visible error message shown to user")
        else:
            ok("Wrong password error message visible")

        # Log in correctly
        page.fill("input[name=username]", ADMIN_USER)
        page.fill("input[name=password]", ADMIN_PASS)
        page.click("button[type=submit]")
        page.wait_for_url(f"{BASE_URL}/dashboard", timeout=8000)
        shot(page, "03_logged_in_dashboard")
        ok(f"Logged in -> {page.url}")

        # ── 2. DASHBOARD ──────────────────────────────────────────────
        print("\n=== [2] DASHBOARD ===")
        page_title = page.title()
        print(f"  title: {page_title}")
        shot(page, "04_dashboard")

        # Check for the two investigation type cards
        phys_card = page.locator("text=Физическое лицо").count()
        jur_card = page.locator("text=Юридическое лицо").count()
        if phys_card == 0:
            flag("dashboard", "No 'Физическое лицо' card on dashboard")
        if jur_card == 0:
            flag("dashboard", "No 'Юридическое лицо' card on dashboard")

        # Check navigation
        nav = page.locator("nav, .nav, header").first
        nav_html = nav.inner_html() if nav.count() > 0 else ""
        nav_links = [a.get_attribute("href") for a in page.locator("nav a, header a").all()]
        print(f"  nav links: {nav_links}")
        if not any("/candidate" in (l or "") or "/company" in (l or "") or
                   "history" in (l or "") or "расследован" in nav_html.lower()
                   for l in nav_links):
            flag("dashboard", "Navigation doesn't contain investigation links")

        # Check for logout option (logout is a form POST button, not an <a> link)
        logout = page.locator("a[href*=logout], form[action*=logout] button").count()
        if logout == 0:
            flag("dashboard", "No logout link/button visible in nav")

        # ── 3. CANDIDATE FORM ─────────────────────────────────────────
        print("\n=== [3] CANDIDATE FORM ===")
        page.goto(BASE_URL + "/candidate/new")
        page.wait_for_load_state("networkidle")
        shot(page, "05_candidate_new")

        if page.url != BASE_URL + "/candidate/new":
            flag("candidate_new", f"Redirected away from /candidate/new to {page.url}")
        else:
            ok("Candidate form loaded")

        # Inspect form fields
        fields = {f.get_attribute("name"): f.get_attribute("type") or "text"
                  for f in page.locator("input, select, textarea").all()
                  if f.get_attribute("name")}
        print(f"  form fields: {list(fields.keys())}")

        # Check key fields exist
        expected = ["full_name", "date_of_birth", "inn", "pd_consent"]
        for field in expected:
            if not any(field in k for k in fields):
                flag("candidate_new", f"Missing expected field: {field}")

        # Check PD consent label is visible and clear
        consent_label_count = (
            page.locator("label[for*=consent], .consent-label").count() +
            page.get_by_text("персональных данных").count()
        )
        if consent_label_count == 0:
            flag("candidate_new", "PD consent label not visible — user may not understand the checkbox")

        # Check "Быстрый" / "Полный" mode options
        mode_opts = page.locator("input[name=check_mode], .mode-option").count()
        if mode_opts == 0:
            flag("candidate_new", "No check mode (Быстрый/Полный) options found")

        # Quality indicator?
        quality = page.locator("[class*=quality], [id*=quality], .progress-bar").count()
        print(f"  quality indicator widgets: {quality}")

        # ── 4. SUBMIT CANDIDATE FORM ──────────────────────────────────
        print("\n=== [4] SUBMIT CANDIDATE FORM ===")
        # Fill in valid data
        page.fill("input[name=full_name]", "Иванов Петр Сергеевич")
        page.fill("input[name=date_of_birth]", "1985-03-15")
        page.fill("input[name=inn]", TEST_INN)

        # Check pd_consent checkbox
        consent_cb = page.locator("input[name=pd_consent]")
        if consent_cb.count() > 0 and not consent_cb.is_checked():
            consent_cb.check()

        # Select mode
        quick_mode = page.locator("input[name=check_mode][value=quick]")
        if quick_mode.count() > 0:
            quick_mode.check()

        shot(page, "06_candidate_filled")

        page.click("#candidate-submit-btn")
        page.wait_for_timeout(3000)  # give JS time to run + potential alert dismiss

        shot(page, "07_after_candidate_submit")
        print(f"  URL after submit: {page.url}")
        if alerts_seen:
            print(f"  alerts triggered: {alerts_seen}")
            alerts_seen.clear()

        # Check if we got a redirect to progress or confirmation
        if "/candidate/" in page.url and "/new" not in page.url:
            ok(f"Candidate check started -> {page.url}")
        elif page.url == BASE_URL + "/candidate/new":
            # Still on form — check for validation errors
            errors = page.locator("[class*=error], .flash, .alert").all()
            for e in errors:
                t = e.inner_text().strip()
                if t:
                    flag("candidate_new", f"Validation error shown: {t[:80]}")
        else:
            flag("candidate_new", f"Unexpected URL after form submit: {page.url}")

        progress_url = page.url

        # ── 5. PROGRESS PAGE ──────────────────────────────────────────
        if "/progress" in page.url or ("/candidate/" in page.url and "/new" not in page.url):
            print("\n=== [5] PROGRESS PAGE ===")
            shot(page, "08_progress")

            progress_bar = page.locator(".progress, [class*=progress], [class*=stage], [role=progressbar]").count()
            print(f"  progress indicators: {progress_bar}")
            if progress_bar == 0:
                flag("candidate_progress", "No progress indicator visible on progress page")

            stage_items = page.locator("[class*=stage], [class*=step], .pipeline-step").count()
            print(f"  stage items: {stage_items}")

            # Check for SSE or polling update mechanism
            page.wait_for_timeout(2000)
            shot(page, "09_progress_2s")
            print(f"  URL at 2s: {page.url}")

        # ── 6. CANDIDATE HISTORY ──────────────────────────────────────
        print("\n=== [6] CANDIDATE HISTORY ===")
        page.goto(BASE_URL + "/candidate/history")
        page.wait_for_load_state("networkidle")
        shot(page, "10_candidate_history")

        if page.url != BASE_URL + "/candidate/history":
            flag("candidate_history", f"Redirected from history to {page.url}")
        else:
            ok("Candidate history loaded")

        rows = page.locator("table tbody tr, .check-row, .history-item").count()
        print(f"  history rows: {rows}")
        if rows == 0:
            flag("candidate_history", "History shows 0 items — the check we just ran is not appearing")

        # Check that each row has name, date, status, and a link
        links = page.locator("a[href*='/candidate/']").all()
        print(f"  candidate links in history: {len(links)}")

        # ── 7. FIND A COMPLETED DOSSIER ───────────────────────────────
        print("\n=== [7] DOSSIER PAGE ===")
        # Look for any completed dossier link
        dossier_found = False
        all_links = [a.get_attribute("href") or "" for a in page.locator("a[href*='/candidate/']").all()]
        for href in all_links:
            if "/candidate/" in href and "/new" not in href and "/history" not in href and "/progress" not in href:
                full_url = BASE_URL + href if not href.startswith("http") else href
                page.goto(full_url)
                page.wait_for_load_state("networkidle")
                current = page.url
                if "/dossier" in current or ("/candidate/" in current and "/progress" not in current):
                    dossier_found = True
                    shot(page, "11_dossier")
                    ok(f"Dossier loaded: {current}")
                    _inspect_dossier(page, "candidate_dossier")
                    break

        if not dossier_found:
            print("  [info] No completed dossier found yet (pipeline may be running)")

        # ── 8. COMPANY FORM ───────────────────────────────────────────
        print("\n=== [8] COMPANY FORM ===")
        page.goto(BASE_URL + "/company/new")
        page.wait_for_load_state("networkidle")
        shot(page, "12_company_new")

        if page.url != BASE_URL + "/company/new":
            flag("company_new", f"Redirected from /company/new to {page.url}")
        else:
            ok("Company form loaded")

        company_fields = {f.get_attribute("name"): f.get_attribute("type")
                         for f in page.locator("input, select, textarea").all()
                         if f.get_attribute("name")}
        print(f"  company form fields: {list(company_fields.keys())}")

        inn_field = page.locator("input[name=inn], input[name=INN]")
        if inn_field.count() == 0:
            flag("company_new", "No INN field in company form")
        else:
            inn_field.first.fill(COMPANY_INN)
            inn_field.first.dispatch_event("input")  # trigger JS INN validator to enable submit btn
            shot(page, "13_company_filled")
            page.wait_for_selector("#co-submit-btn:not([disabled])", timeout=3000)
            page.click("#co-submit-btn")
            page.wait_for_timeout(3000)
            shot(page, "14_company_after_submit")
            print(f"  URL after company submit: {page.url}")
            if alerts_seen:
                print(f"  alerts: {alerts_seen}")
                alerts_seen.clear()
            if "/company/" in page.url and "/new" not in page.url:
                ok(f"Company check started -> {page.url}")
            else:
                flag("company_new", f"Company form submit didn't start check — at {page.url}")

        # ── 9. COMPANY HISTORY ────────────────────────────────────────
        print("\n=== [9] COMPANY HISTORY ===")
        page.goto(BASE_URL + "/company/history")
        page.wait_for_load_state("networkidle")
        shot(page, "15_company_history")
        company_rows = page.locator("table tbody tr, .check-row, .history-item").count()
        print(f"  company history rows: {company_rows}")

        # ── 10. ADMIN PANEL ───────────────────────────────────────────
        print("\n=== [10] ADMIN PANEL ===")
        page.goto(BASE_URL + "/admin/users")
        page.wait_for_load_state("networkidle")
        shot(page, "16_admin_users")

        if "admin" not in page.url and page.url != BASE_URL + "/admin/users":
            flag("admin", f"Admin panel redirected to {page.url}")
        else:
            user_rows = page.locator("table tbody tr").count()
            print(f"  user rows in admin: {user_rows}")
            if user_rows == 0:
                flag("admin", "Admin panel shows 0 users (expected at least Fedor)")

            # Check for management actions
            delete_btns = page.locator("button:has-text('Удалить'), a:has-text('Delete'), button[class*=delete]").count()
            print(f"  delete/manage buttons: {delete_btns}")

            # Check for junk test users
            all_usernames = [el.inner_text() for el in page.locator("table tbody tr td:first-child").all()]
            test_user_count = sum(1 for u in all_usernames if "test" in u.lower() or "fix_h1" in u.lower() or "lktest" in u.lower())
            if test_user_count > 0:
                flag("admin", f"{test_user_count} leftover test users in DB: {[u for u in all_usernames if 'test' in u.lower() or 'fix_h1' in u.lower() or 'lktest' in u.lower()][:5]}")

        # ── 11. CHAT PAGE ─────────────────────────────────────────────
        print("\n=== [11] CHAT PAGE ===")
        page.goto(BASE_URL + "/chat")
        page.wait_for_load_state("networkidle")
        shot(page, "17_chat")

        if page.url != BASE_URL + "/chat":
            flag("chat", f"Chat redirected to {page.url}")
        else:
            ok("Chat page loaded")
            textarea = page.locator("textarea, input[type=text]:not([name=username])").count()
            if textarea == 0:
                flag("chat", "No text input on chat page")
            send_btn = page.locator("button:has-text('Отправить'), button:has-text('Send'), button[type=submit]").count()
            if send_btn == 0:
                flag("chat", "No send button on chat page")

        # ── 12. SUBSCRIPTION PAGE ─────────────────────────────────────
        print("\n=== [12] SUBSCRIBE PAGE ===")
        page.goto(BASE_URL + "/subscribe")
        page.wait_for_load_state("networkidle")
        shot(page, "18_subscribe")
        print(f"  subscribe URL: {page.url}")

        # ── 13. NAVIGATION AUDIT (from logged-in state) ───────────────
        print("\n=== [13] NAV AUDIT ===")
        page.goto(BASE_URL + "/dashboard")
        page.wait_for_load_state("networkidle")
        nav_links = [a.get_attribute("href") for a in page.locator("nav a, header a, .navbar a, .sidebar a").all()]
        print(f"  nav links: {nav_links}")
        shot(page, "19_nav_audit")

        # Try each nav link
        for href in nav_links:
            if href and href.startswith("/") and href not in ("/vk-callback", "/set-lang/ru", "/set-lang/en"):
                page.goto(BASE_URL + href)
                page.wait_for_load_state("networkidle", timeout=5000)
                if "404" in page.title() or page.locator("text=Not Found").count() > 0:
                    flag("navigation", f"Nav link {href} -> 404")
                elif page.url.endswith("/login"):
                    flag("navigation", f"Nav link {href} -> redirected to /login (auth issue?)")

        # ── 14. LOGOUT ────────────────────────────────────────────────
        print("\n=== [14] LOGOUT ===")
        page.goto(BASE_URL + "/dashboard")
        page.wait_for_load_state("networkidle")
        shot(page, "20_before_logout")

        logout = page.locator("form[action*=logout] button, a[href*=logout]").first
        if logout.count() == 0:
            flag("logout", "No logout button found in navigation")
        else:
            if page.locator("form[action*=logout]").count() > 0:
                page.locator("form[action*=logout] button").first.click()
            else:
                logout.click()
            page.wait_for_load_state("networkidle")
            shot(page, "21_after_logout")
            print(f"  After logout URL: {page.url}")
            if "/login" in page.url:
                ok("Logout redirected to /login")
            else:
                flag("logout", f"After logout ended at unexpected URL: {page.url}")

            # Verify session is cleared — try to access protected page
            page.goto(BASE_URL + "/dashboard")
            page.wait_for_load_state("networkidle")
            if page.url.endswith("/login"):
                ok("Post-logout auth enforcement works")
            else:
                flag("logout", f"After logout, /dashboard accessible (session not cleared): {page.url}")

        browser.close()

    # ── REPORT ────────────────────────────────────────────────────────
    print("\n" + "="*60)
    print(f"WALKTHROUGH DONE — {len(issues)} issues found")
    print("="*60)
    for i, issue in enumerate(issues, 1):
        print(f"\n{i}. [{issue['screen']}]\n   {issue['problem']}")

    report = {"issues": issues, "screenshots": str(SCREENSHOT_DIR.absolute())}
    Path("scripts/e2e_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
    return issues


def _inspect_dossier(page: Page, name: str):
    """Audit a dossier page."""
    text = page.inner_text("body")
    url = page.url

    if "Traceback" in text or "AttributeError" in text or "TypeError" in text:
        flag(name, "Python traceback visible in page!")

    # Key sections expected in a dossier
    sections = [
        ("риск", "risk section"),
        ("источник", "source attribution"),
    ]
    for kw, label in sections:
        if kw.lower() not in text.lower():
            flag(name, f"Dossier missing expected section: {label} ('{kw}' not found)")

    # Check risk score widget
    score = page.locator("[class*=risk], [class*=score], .risk-score").count()
    print(f"  dossier risk score widgets: {score}")

    # Check for export buttons
    export = page.locator("a[href*=pdf], a[href*=export], button:has-text('PDF'), button:has-text('Скачать')").count()
    print(f"  export buttons: {export}")
    if export == 0:
        flag(name, "No PDF/export button on dossier page")

    # Data quality
    no_data_count = text.lower().count("нет данных") + text.lower().count("данные отсутствуют") + text.lower().count("не найдено")
    print(f"  'no data' occurrences: {no_data_count}")

    print(f"  page text length: {len(text)}")


if __name__ == "__main__":
    run_walkthrough()
