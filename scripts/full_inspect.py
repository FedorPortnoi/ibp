"""
Comprehensive visual + functional inspection of every Stirlitz workflow.
Reports issues found; does NOT fix anything.
Run: python scripts/full_inspect.py
"""

import json, sys, io, time
from pathlib import Path
from playwright.sync_api import sync_playwright, Page, ConsoleMessage

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BASE = "http://127.0.0.1:5000"
SHOTS = Path("scripts/inspect_shots")
SHOTS.mkdir(parents=True, exist_ok=True)

USER = "Fedor"
PASS = "vdohnoviteligorborisovichportnoisozdatelfedorigorevichportnoiproductluchshebyratino9"
TEST_INN_PERSON  = "773605001337"   # valid 12-digit individual
TEST_INN_COMPANY = "7736050003"     # valid 10-digit company (Gazprom)

issues = []
console_errors = []
alerts_seen = []


def shot(page: Page, name: str):
    p = SHOTS / f"{name}.png"
    page.screenshot(path=str(p), full_page=True)
    print(f"  [img] {name} — {page.url}")


def flag(screen: str, msg: str):
    issues.append({"screen": screen, "msg": msg})
    print(f"  [!!] [{screen}] {msg}")


def ok(msg: str):
    print(f"  [ok] {msg}")


def info(msg: str):
    print(f"  [..]  {msg}")


def check_page_errors(page: Page, screen: str):
    """Look for Python tracebacks, 404/500 text, and Flask error pages in the rendered HTML."""
    try:
        body = page.inner_text("body")
    except Exception:
        return
    if "Traceback (most recent call last)" in body:
        flag(screen, "Python traceback visible in page!")
    if "Internal Server Error" in body:
        flag(screen, "500 Internal Server Error visible in page")
    if "Not Found" in body and "404" in page.title():
        flag(screen, "404 Not Found page")
    if "CSRF" in body and "missing" in body.lower():
        flag(screen, "CSRF token error visible in page")


def check_nav(page: Page, screen: str):
    """Verify nav links are present and reasonable."""
    links = [a.get_attribute("href") for a in page.locator("nav a, header a").all()]
    info(f"nav links: {links}")
    for href in links:
        if href and href not in ("/", "#"):
            # spot-check each nav link doesn't 404
            pass  # done in nav_audit section
    return links


def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=300)
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        page = ctx.new_page()

        # Collect console errors
        def on_console(msg: ConsoleMessage):
            if msg.type in ("error", "warning"):
                console_errors.append({"type": msg.type, "text": msg.text[:200]})
        page.on("console", on_console)
        page.on("dialog", lambda d: (alerts_seen.append(d.message), d.dismiss()))
        page.on("pageerror", lambda e: console_errors.append({"type": "pageerror", "text": str(e)[:200]}))

        # ─────────────────────────────────────────────────────────────
        # SECTION 1 — LOGIN
        # ─────────────────────────────────────────────────────────────
        print("\n══════════════════════════════════════════")
        print(" 1. LOGIN PAGE")
        print("══════════════════════════════════════════")
        page.goto(BASE + "/login")
        page.wait_for_load_state("networkidle")
        shot(page, "01_login")
        check_page_errors(page, "login")

        # Fields present?
        for name in ("username", "password"):
            if page.locator(f"input[name={name}]").count() == 0:
                flag("login", f"Missing input[name={name}]")
        ok("Login fields present") if not any("login" in i["screen"] for i in issues) else None

        # Marketing content check
        hero_text = page.inner_text("body")
        info(f"Page text length: {len(hero_text)} chars")
        shot(page, "01b_login_scroll")

        # Wrong password → error
        page.fill("input[name=username]", "Fedor")
        page.fill("input[name=password]", "wrongpassword123")
        page.click("button[type=submit]")
        page.wait_for_load_state("networkidle")
        shot(page, "02_login_wrong_pass")
        has_err = (page.locator("#flash-err.on, .auth-err.on").count() > 0 or
                   page.locator("text=Неверн").count() > 0)
        if not has_err:
            flag("login", "Wrong-password error NOT shown")
        else:
            ok("Wrong-password error shown")

        # Successful login
        page.fill("input[name=username]", USER)
        page.fill("input[name=password]", PASS)
        page.click("button[type=submit]")
        try:
            page.wait_for_url(f"{BASE}/dashboard", timeout=8000)
            ok(f"Login succeeded → {page.url}")
        except Exception:
            flag("login", f"Login did not redirect to /dashboard — at {page.url}")
            browser.close()
            return
        shot(page, "03_post_login_dashboard")

        # ─────────────────────────────────────────────────────────────
        # SECTION 2 — DASHBOARD
        # ─────────────────────────────────────────────────────────────
        print("\n══════════════════════════════════════════")
        print(" 2. DASHBOARD")
        print("══════════════════════════════════════════")
        check_page_errors(page, "dashboard")
        shot(page, "04_dashboard_full")

        title = page.title()
        info(f"Title: {title}")
        if "СЛЕД" not in title and "Stirlitz" not in title and "IBP" not in title:
            flag("dashboard", f"Unexpected page title: {title!r}")

        cards = page.locator("text=Физическое лицо, text=Юридическое лицо").count()
        info(f"Investigation type cards visible: {cards}")

        nav_links = check_nav(page, "dashboard")

        # Username shown in nav?
        nav_text = page.locator("nav, header").first.inner_text()
        if "Fedor" not in nav_text and USER not in nav_text:
            flag("dashboard", "Username not visible in nav")
        else:
            ok("Username visible in nav")

        # ADMIN badge shown?
        if "ADMIN" not in nav_text and "admin" not in nav_text.lower():
            flag("dashboard", "ADMIN role badge not visible in nav for admin user")
        else:
            ok("ADMIN badge visible")

        # Logout button reachable?
        logout_btn = page.locator("form[action*=logout] button").count()
        if logout_btn == 0:
            flag("dashboard", "No logout button found in nav")
        else:
            ok(f"Logout button found ({logout_btn} instances)")

        # ─────────────────────────────────────────────────────────────
        # SECTION 3 — CANDIDATE FORM
        # ─────────────────────────────────────────────────────────────
        print("\n══════════════════════════════════════════")
        print(" 3. CANDIDATE CHECK FORM  /candidate/new")
        print("══════════════════════════════════════════")
        page.goto(BASE + "/candidate/new")
        page.wait_for_load_state("networkidle")
        shot(page, "05_candidate_form_empty")
        check_page_errors(page, "candidate_form")

        if page.url != BASE + "/candidate/new":
            flag("candidate_form", f"Redirected away: {page.url}")
        else:
            ok("Candidate form loaded")

        # Required fields
        for fname in ("full_name", "date_of_birth", "inn", "pd_consent"):
            if page.locator(f"input[name={fname}]").count() == 0:
                flag("candidate_form", f"Required field missing: {fname}")

        # Optional fields
        optional = ("passport", "region", "registered_address", "phone", "email")
        for fname in optional:
            present = page.locator(f"input[name={fname}], textarea[name={fname}]").count() > 0
            info(f"Optional field '{fname}': {'present' if present else 'MISSING'}")

        # Quality indicator
        qi = page.locator("#quality-indicator, [id*=quality]").count()
        info(f"Quality indicator: {qi}")

        # Check mode options
        modes = page.locator("input[name=check_mode]").count()
        info(f"Check mode options: {modes}")
        if modes < 2:
            flag("candidate_form", f"Expected 2 check mode options, found {modes}")

        # Photo upload
        photo = page.locator("input[name=photo], input[type=file]").count()
        info(f"Photo upload field: {photo}")
        if photo == 0:
            flag("candidate_form", "No photo upload field found")

        # PD consent checkbox + label
        if page.locator("input[name=pd_consent]").count() == 0:
            flag("candidate_form", "PD consent checkbox missing")
        if page.get_by_text("персональных данных").count() == 0 and \
           page.get_by_text("согласие").count() == 0:
            flag("candidate_form", "PD consent label text not found")

        # Submit button visible and enabled (admin has no free-tier limit)
        btn = page.locator("#candidate-submit-btn")
        if btn.count() == 0:
            flag("candidate_form", "#candidate-submit-btn not found")
        else:
            disabled = btn.get_attribute("disabled")
            info(f"Submit button disabled attr: {disabled!r}")

        # HTML5 validation: try empty submit
        console_errors_before = len(console_errors)
        page.evaluate("document.getElementById('candidate-form').dispatchEvent(new Event('submit'))")
        page.wait_for_timeout(500)

        # Fill form
        page.fill("input[name=full_name]", "Иванов Петр Сергеевич")
        page.fill("input[name=date_of_birth]", "1985-03-15")
        page.fill("input[name=inn]", TEST_INN_PERSON)
        cb = page.locator("input[name=pd_consent]")
        if cb.count() and not cb.is_checked():
            cb.check()
        qm = page.locator("input[name=check_mode][value=quick]")
        if qm.count():
            qm.check()
        shot(page, "06_candidate_form_filled")

        # Check quality indicator updated
        qi_text = page.locator("#quality-indicator").inner_text() if page.locator("#quality-indicator").count() else ""
        info(f"Quality indicator text after fill: {qi_text[:80]!r}")
        if "Стандартная" not in qi_text and "Расширенная" not in qi_text and "Полная" not in qi_text:
            flag("candidate_form", f"Quality indicator did not update after fill: {qi_text[:60]!r}")

        # INN validation UI
        inn_err = page.locator("#inn-error")
        if inn_err.count() and not "hidden" in (inn_err.get_attribute("class") or ""):
            flag("candidate_form", f"INN error shown for valid INN: {inn_err.inner_text()}")

        # ─────────────────────────────────────────────────────────────
        # SECTION 4 — CANDIDATE SUBMIT + PROGRESS
        # ─────────────────────────────────────────────────────────────
        print("\n══════════════════════════════════════════")
        print(" 4. CANDIDATE SUBMIT → PROGRESS")
        print("══════════════════════════════════════════")
        alerts_seen.clear()
        try:
            with page.expect_navigation(wait_until="networkidle", timeout=10000):
                page.click("#candidate-submit-btn")
        except Exception as nav_e:
            info(f"Candidate submit nav exception: {nav_e}")
            try:
                page.wait_for_load_state("networkidle", timeout=5000)
            except Exception:
                pass
        shot(page, "07_after_candidate_submit")

        if alerts_seen:
            flag("candidate_submit", f"JS alert after submit: {alerts_seen}")
            alerts_seen.clear()

        progress_url = page.url
        info(f"URL after submit: {progress_url}")

        if "/candidate/progress/" in progress_url:
            ok(f"Redirected to progress page")
        elif "/candidate/new" in progress_url:
            flag("candidate_submit", "Still on form — submit did not navigate")
        else:
            flag("candidate_submit", f"Unexpected URL: {progress_url}")

        # ─────────────────────────────────────────────────────────────
        # SECTION 5 — PROGRESS PAGE
        # ─────────────────────────────────────────────────────────────
        if "/candidate/progress/" in progress_url:
            print("\n══════════════════════════════════════════")
            print(" 5. PROGRESS PAGE")
            print("══════════════════════════════════════════")
            check_page_errors(page, "progress")
            shot(page, "08_progress_initial")

            # Page title / candidate name shown
            body_text = page.inner_text("body")
            if "Иванов" not in body_text:
                flag("progress", "Candidate name not visible on progress page")
            else:
                ok("Candidate name shown on progress page")

            # Pipeline stages listed
            stages = page.locator("[class*=stage], [class*=step], [class*=pipeline]").count()
            info(f"Stage elements: {stages}")
            if stages == 0:
                flag("progress", "No pipeline stages visible")

            # Status indicators (spinning, pending, done)
            spin = page.locator("[class*=spin], [class*=load], .stage-pending").count()
            info(f"Spinning/loading indicators: {spin}")

            # Wait 5 seconds and see if progress updates
            page.wait_for_timeout(5000)
            shot(page, "09_progress_5s")
            body_after = page.inner_text("body")
            if body_after == body_text:
                info("Progress page content unchanged after 5s (may be polling via SSE/fetch)")
            else:
                ok("Progress page content updated after 5s")

            info(f"URL at 5s: {page.url}")

        # ─────────────────────────────────────────────────────────────
        # SECTION 6 — CANDIDATE HISTORY
        # ─────────────────────────────────────────────────────────────
        print("\n══════════════════════════════════════════")
        print(" 6. CANDIDATE HISTORY  /candidate/history")
        print("══════════════════════════════════════════")
        page.goto(BASE + "/candidate/history")
        page.wait_for_load_state("networkidle")
        shot(page, "10_candidate_history")
        check_page_errors(page, "candidate_history")

        if page.url != BASE + "/candidate/history":
            flag("candidate_history", f"Redirected to {page.url}")
        else:
            ok("Candidate history loaded")

        # Count rows
        rows = page.locator("table tbody tr").count()
        card_rows = page.locator("a[href*='/candidate/dossier/'], a[href*='/candidate/confirm/']").count()
        info(f"Table rows: {rows} | Candidate links: {card_rows}")

        # Search/filter present?
        search = page.locator("input[type=search], input[placeholder*=поиск], input[placeholder*=Поиск]").count()
        info(f"Search input: {search}")

        # Status labels visible?
        statuses = page.locator("[class*=status], [class*=badge]").count()
        info(f"Status badges: {statuses}")

        # Export buttons?
        export = page.locator("a[href*=export], button:has-text('Скачать'), button:has-text('PDF')").count()
        info(f"Export buttons on history: {export}")

        # ─────────────────────────────────────────────────────────────
        # SECTION 7 — DOSSIER (find the most recent completed one)
        # ─────────────────────────────────────────────────────────────
        print("\n══════════════════════════════════════════")
        print(" 7. DOSSIER PAGE")
        print("══════════════════════════════════════════")
        dossier_links = [
            a.get_attribute("href") for a in
            page.locator("a[href*='/candidate/dossier/']").all()
        ]
        info(f"Dossier links on history page: {len(dossier_links)}")

        if dossier_links:
            dossier_url = BASE + dossier_links[0] if not dossier_links[0].startswith("http") else dossier_links[0]
            page.goto(dossier_url)
            page.wait_for_load_state("networkidle")
            shot(page, "11_dossier_top")
            check_page_errors(page, "dossier")
            ok(f"Dossier loaded: {page.url}")

            body = page.inner_text("body")
            info(f"Dossier page text length: {len(body)} chars")

            # Sections check — keep CSS and text= selectors separate
            def sec_count(css_sel, text_hint):
                c = page.locator(css_sel).count()
                if text_hint:
                    c += page.get_by_text(text_hint, exact=False).count()
                return c

            sections = {
                "risk_score":   ("[class*=risk-score],[class*=risk_score],[id*=risk]", None),
                "court_records":("[id*=court],[class*=court]", "Суд"),
                "fssp":         ("[id*=fssp]", "ФССП"),
                "sanctions":    ("[id*=sanction]", "Санкц"),
                "connections":  ("[id*=connect]", "Связи"),
            }
            for sec_name, (sel, hint) in sections.items():
                count = sec_count(sel, hint)
                info(f"Section '{sec_name}': {count} elements")
                if count == 0:
                    flag("dossier", f"Section '{sec_name}' not found in dossier")

            # Export buttons
            pdf_btns = page.locator("a[href*=pdf], a[href*=export], button:has-text('PDF'), button:has-text('Скачать')").count()
            info(f"Export/PDF buttons: {pdf_btns}")
            if pdf_btns == 0:
                flag("dossier", "No export/PDF button on dossier")

            # No-data occurrences
            no_data = body.lower().count("нет данных") + body.lower().count("не найдено") + body.lower().count("данные отсутствуют")
            info(f"'No data' occurrences: {no_data}")

            # Any visible errors
            err_text = page.locator("[class*=error]:visible, .alert-danger:visible").count()
            if err_text > 0:
                flag("dossier", f"{err_text} visible error elements on dossier")

            shot(page, "11b_dossier_full")

            # Test PDF export link
            pdf_link = page.locator("a[href*=pdf], a[href*=export]").first
            if pdf_link.count() > 0:
                pdf_href = pdf_link.get_attribute("href")
                info(f"PDF link: {pdf_href}")
                # Navigate to PDF endpoint, check it returns something
                resp_status = page.evaluate(f"""async () => {{
                    const r = await fetch('{pdf_href}');
                    return r.status;
                }}""")
                info(f"PDF endpoint status: {resp_status}")
                if resp_status not in (200, 202):
                    flag("dossier", f"PDF endpoint returned {resp_status}")
        else:
            info("No completed dossiers yet — pipeline may still be running")

        # ─────────────────────────────────────────────────────────────
        # SECTION 8 — COMPANY FORM
        # ─────────────────────────────────────────────────────────────
        print("\n══════════════════════════════════════════")
        print(" 8. COMPANY FORM  /company/new")
        print("══════════════════════════════════════════")
        page.goto(BASE + "/company/new")
        page.wait_for_load_state("networkidle")
        shot(page, "12_company_form_empty")
        check_page_errors(page, "company_form")

        if page.url != BASE + "/company/new":
            flag("company_form", f"Redirected to {page.url}")
        else:
            ok("Company form loaded")

        # Fields
        inn_f = page.locator("input[name=inn]")
        if inn_f.count() == 0:
            flag("company_form", "INN field missing")

        name_f = page.locator("input[name=query_name]")
        info(f"Optional name field: {name_f.count()}")

        # Quality indicator
        qi_co = page.locator("#quality-indicator").count()
        info(f"Company quality indicator: {qi_co}")

        # Submit starts disabled
        submit_disabled = page.locator("#co-submit-btn[disabled]").count()
        info(f"Submit button starts disabled: {submit_disabled > 0}")
        if submit_disabled == 0:
            flag("company_form", "Company submit button should start disabled (INN not yet entered)")

        # Fill INN → button should enable
        inn_f.fill(TEST_INN_COMPANY)
        inn_f.dispatch_event("input")
        page.wait_for_timeout(500)
        shot(page, "13_company_form_filled")

        submit_enabled = page.locator("#co-submit-btn:not([disabled])").count()
        if submit_enabled == 0:
            flag("company_form", "Submit button not enabled after valid INN entry")
        else:
            ok("Submit button enabled after valid INN")

        qi_text_co = page.locator("#quality-indicator").inner_text() if page.locator("#quality-indicator").count() else ""
        info(f"Company quality indicator after INN: {qi_text_co[:60]!r}")

        # Submit
        alerts_seen.clear()
        try:
            with page.expect_navigation(wait_until="networkidle", timeout=10000):
                page.click("#co-submit-btn")
        except Exception as nav_e:
            info(f"Company submit nav exception: {nav_e}")
            try:
                page.wait_for_load_state("networkidle", timeout=5000)
            except Exception:
                pass
        shot(page, "14_company_after_submit")

        if alerts_seen:
            flag("company_submit", f"JS alert after company submit: {alerts_seen}")
            alerts_seen.clear()

        co_progress_url = page.url
        info(f"URL after company submit: {co_progress_url}")
        if "/company/progress/" in co_progress_url:
            ok("Company check started → progress page")
        else:
            flag("company_submit", f"Unexpected URL after submit: {co_progress_url}")

        # ─────────────────────────────────────────────────────────────
        # SECTION 9 — COMPANY PROGRESS + HISTORY
        # ─────────────────────────────────────────────────────────────
        if "/company/progress/" in co_progress_url:
            print("\n══════════════════════════════════════════")
            print(" 9. COMPANY PROGRESS PAGE")
            print("══════════════════════════════════════════")
            check_page_errors(page, "company_progress")
            shot(page, "15_company_progress")

            body = page.inner_text("body")
            info(f"Company progress text length: {len(body)} chars")
            if TEST_INN_COMPANY not in body and "7736050003" not in body:
                flag("company_progress", "Company INN not visible on progress page")

        print("\n══════════════════════════════════════════")
        print(" 10. COMPANY HISTORY  /company/history")
        print("══════════════════════════════════════════")
        page.goto(BASE + "/company/history")
        page.wait_for_load_state("networkidle")
        shot(page, "16_company_history")
        check_page_errors(page, "company_history")

        body = page.inner_text("body")
        if TEST_INN_COMPANY in body:
            ok("Company INN found in history")
        else:
            flag("company_history", "Just-submitted company INN not found in history page")

        # Count company rows (div-based, not table)
        co_items = page.locator(f"a[href*='/company/']").count()
        info(f"Company links in history: {co_items}")

        # ─────────────────────────────────────────────────────────────
        # SECTION 11 — ADMIN PANEL
        # ─────────────────────────────────────────────────────────────
        print("\n══════════════════════════════════════════")
        print(" 11. ADMIN PANEL  /admin/users/")
        print("══════════════════════════════════════════")
        page.goto(BASE + "/admin/users/")
        page.wait_for_load_state("networkidle")
        shot(page, "17_admin_users")
        check_page_errors(page, "admin")

        if "admin" not in page.url:
            flag("admin", f"Admin page redirected to {page.url}")
        else:
            ok("Admin panel loaded")

        admin_body = page.inner_text("body")
        user_rows = page.locator("table tbody tr").count()
        info(f"User rows: {user_rows}")
        if user_rows == 0:
            flag("admin", "Admin panel shows 0 users (expected at least Fedor)")

        # Check Fedor is there
        if "Fedor" not in admin_body:
            flag("admin", "Fedor not listed in admin panel")
        else:
            ok("Fedor listed in admin panel")

        # Check for leftover test users
        test_indicators = ["lktest", "fix_h1", "locktest", "teststring", "testv4reg"]
        for t in test_indicators:
            if t.lower() in admin_body.lower():
                flag("admin", f"Test user still present: '{t}'")

        # Open user detail
        open_links = page.locator("a:has-text('Открыть'), a:has-text('Open'), a[href*='/admin/users/']").all()
        info(f"'Open user' links: {len(open_links)}")
        if open_links:
            first_href = open_links[0].get_attribute("href")
            info(f"First user link: {first_href}")
            if first_href:
                page.goto(BASE + first_href if first_href.startswith("/") else first_href)
                page.wait_for_load_state("networkidle")
                shot(page, "17b_admin_user_detail")
                check_page_errors(page, "admin_user_detail")
                info(f"User detail URL: {page.url}")

        # ─────────────────────────────────────────────────────────────
        # SECTION 12 — CHAT
        # ─────────────────────────────────────────────────────────────
        print("\n══════════════════════════════════════════")
        print(" 12. CHAT PAGE  /chat/")
        print("══════════════════════════════════════════")
        page.goto(BASE + "/chat/")
        page.wait_for_load_state("networkidle")
        shot(page, "18_chat")
        check_page_errors(page, "chat")

        if "/chat" not in page.url:
            flag("chat", f"Chat redirected to {page.url}")
        else:
            ok("Chat page loaded")

        # Input + send button
        input_el = page.locator("textarea, input[type=text]:not([name=username]):not([name=inn])").first
        send_btn = page.locator("button:has-text('Отправить'), button:has-text('Send'), button[type=submit]").first

        if input_el.count() == 0:
            flag("chat", "No text input on chat page")
        else:
            ok("Chat input found")
            # Try sending a message
            input_el.fill("тест проверочного сообщения")
            shot(page, "18b_chat_filled")
            if send_btn.count() > 0:
                send_btn.click()
                page.wait_for_timeout(2000)
                shot(page, "18c_chat_sent")
                body_after = page.inner_text("body")
                if "тест проверочного сообщения" in body_after:
                    ok("Chat message sent and visible")
                else:
                    flag("chat", "Sent message not visible in chat after sending")
            else:
                flag("chat", "No send button on chat page")

        # Message history
        msgs = page.locator("[class*=message], [class*=msg], .chat-message").count()
        info(f"Message elements: {msgs}")

        # ─────────────────────────────────────────────────────────────
        # SECTION 13 — SUBSCRIBE PAGE
        # ─────────────────────────────────────────────────────────────
        print("\n══════════════════════════════════════════")
        print(" 13. SUBSCRIBE PAGE  /subscribe")
        print("══════════════════════════════════════════")
        page.goto(BASE + "/subscribe")
        page.wait_for_load_state("networkidle")
        shot(page, "19_subscribe")
        info(f"Subscribe URL (admin redirects to /candidate/new): {page.url}")
        # Admin users redirect to /candidate/new — expected
        if "/candidate/new" in page.url:
            ok("Admin redirected from /subscribe to /candidate/new (expected)")
        check_page_errors(page, "subscribe")

        # ─────────────────────────────────────────────────────────────
        # SECTION 14 — NAV AUDIT: every link
        # ─────────────────────────────────────────────────────────────
        print("\n══════════════════════════════════════════")
        print(" 14. FULL NAV LINK AUDIT")
        print("══════════════════════════════════════════")
        page.goto(BASE + "/dashboard")
        page.wait_for_load_state("networkidle")

        nav_links = list(set(
            a.get_attribute("href") for a in
            page.locator("nav a, header a").all()
            if a.get_attribute("href")
        ))
        info(f"Unique nav links: {nav_links}")

        for href in nav_links:
            if not href or href == "/" or href.startswith("#") or "logout" in href:
                continue
            skip = ("/set-lang", "/vk-callback")
            if any(href.startswith(s) for s in skip):
                continue

            test_url = BASE + href if href.startswith("/") else href
            resp = page.evaluate(f"async () => (await fetch('{test_url}', {{redirect:'follow'}})).status")
            info(f"  {href} → HTTP {resp}")
            if resp == 404:
                flag("navigation", f"Nav link {href} → 404")
            elif resp == 500:
                flag("navigation", f"Nav link {href} → 500")

        # ─────────────────────────────────────────────────────────────
        # SECTION 15 — LOGOUT
        # ─────────────────────────────────────────────────────────────
        print("\n══════════════════════════════════════════")
        print(" 15. LOGOUT")
        print("══════════════════════════════════════════")
        page.goto(BASE + "/dashboard")
        page.wait_for_load_state("networkidle")
        shot(page, "20_pre_logout")

        logout_form = page.locator("form[action*=logout]").first
        if logout_form.count() > 0:
            page.locator("form[action*=logout] button").first.click()
            page.wait_for_load_state("networkidle")
            shot(page, "21_post_logout")
            if "/login" in page.url:
                ok("Logout → /login")
            else:
                flag("logout", f"Logout ended at {page.url}")

            # Verify session killed
            page.goto(BASE + "/dashboard")
            page.wait_for_load_state("networkidle")
            if page.url.endswith("/login"):
                ok("Post-logout /dashboard → /login (session cleared)")
            else:
                flag("logout", f"Dashboard accessible after logout! URL: {page.url}")
        else:
            flag("logout", "No logout form found")

        # ─────────────────────────────────────────────────────────────
        # CONSOLE ERRORS SUMMARY
        # ─────────────────────────────────────────────────────────────
        print("\n══════════════════════════════════════════")
        print(" CONSOLE ERRORS / JS WARNINGS")
        print("══════════════════════════════════════════")
        # Filter noise (CDN, font warnings etc)
        real_errors = [e for e in console_errors if
                       not any(x in e["text"] for x in
                               ("favicon", "fonts.google", "cdn.tailwindcss",
                                "Failed to load resource", "ERR_BLOCKED", "net::ERR"))]
        if real_errors:
            for e in real_errors[:20]:
                print(f"  [{e['type']}] {e['text'][:120]}")
                flag("console", f"[{e['type']}] {e['text'][:100]}")
        else:
            ok("No JS console errors")

        browser.close()

    # ─────────────────────────────────────────────────────────────────
    # FINAL REPORT
    # ─────────────────────────────────────────────────────────────────
    print("\n" + "═"*60)
    print(f" INSPECTION COMPLETE — {len(issues)} issues found")
    print("═"*60)
    for i, iss in enumerate(issues, 1):
        print(f"\n  {i}. [{iss['screen']}]")
        print(f"     {iss['msg']}")

    report = {
        "issues": issues,
        "console_errors": real_errors if 'real_errors' in dir() else [],
        "screenshots": str(SHOTS.absolute()),
    }
    Path("scripts/inspect_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2)
    )
    print(f"\n  Screenshots: {SHOTS.absolute()}")
    print(f"  Report: scripts/inspect_report.json")
    return issues


if __name__ == "__main__":
    run()
