"""
Targeted follow-up check:
  - Completed dossier: look for PDF export, check content quality
  - Chat: send with correct #send-btn
  - Zombie running check
"""

import sys, io
from pathlib import Path
from playwright.sync_api import sync_playwright

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BASE = "http://127.0.0.1:5000"
SHOTS = Path("scripts/inspect_shots")
USER = "Fedor"
PASS = "vdohnoviteligorborisovichportnoisozdatelfedorigorevichportnoiproductluchshebyratino9"

# From DB query — completed check ID (most recent complete)
COMPLETE_CHECK_ID = "0a094c091f384628af77c48157da5d3b"
# Zombie check (status=running, may be stuck)
ZOMBIE_CHECK_ID   = "940fdfe10f184899a98b1868a9d39702"

issues = []

def flag(screen, msg):
    issues.append({"screen": screen, "msg": msg})
    print(f"  [!!] [{screen}] {msg}")

def ok(msg):
    print(f"  [ok] {msg}")

def info(msg):
    print(f"  [..]  {msg}")

def shot(page, name):
    p = SHOTS / f"T_{name}.png"
    page.screenshot(path=str(p), full_page=True)
    print(f"  [img] {name} — {page.url}")


with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, slow_mo=300)
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    page = ctx.new_page()

    # Login
    page.goto(BASE + "/login")
    page.fill("input[name=username]", USER)
    page.fill("input[name=password]", PASS)
    page.click("button[type=submit]")
    page.wait_for_url(f"{BASE}/dashboard", timeout=8000)
    ok("Logged in")

    # ─────────────────────────────────────────────────────────────
    # TEST 1 — COMPLETED DOSSIER
    # ─────────────────────────────────────────────────────────────
    print("\n══════════════════════════════════════════")
    print(" DOSSIER (completed check)")
    print("══════════════════════════════════════════")
    page.goto(BASE + f"/candidate/dossier/{COMPLETE_CHECK_ID}")
    page.wait_for_load_state("networkidle")
    shot(page, "dossier_completed")
    info(f"URL: {page.url}")
    info(f"Title: {page.title()}")

    body = page.inner_text("body")
    info(f"Page text length: {len(body)} chars")

    if "/candidate/progress/" in page.url:
        flag("dossier", "Completed check STILL redirects to progress page (status mismatch?)")
    elif "/candidate/dossier/" in page.url:
        ok("Dossier page loaded (not redirected to progress)")

    # PDF export
    pdf = page.locator("a[href*=pdf], a[href*=export], button:has-text('PDF'), button:has-text('Скачать')").count()
    info(f"PDF/export buttons: {pdf}")
    if pdf == 0:
        flag("dossier", "No PDF/export button on completed dossier")
    else:
        ok(f"PDF/export found ({pdf})")

    # Risk score visible
    risk = page.locator("[class*=risk-score],[class*=risk_score],[id*=risk]").count()
    info(f"Risk score elements: {risk}")
    risk_text = ""
    if risk:
        try:
            risk_text = page.locator("[class*=risk-score],[class*=risk_score]").first.inner_text()
            info(f"Risk score text: {risk_text[:80]!r}")
        except:
            pass

    # Content sections
    content_checks = {
        "AI summary":    "AI EXECUTIVE SUMMARY,AI-резюме,Резюме,РЕЗЮМЕ",
        "FSSP":          "ФССП,исполнительн",
        "courts":        "Суд,арбитраж,дело",
        "business":      "бизнес,компани,учредит",
        "sanctions":     "санкц,ограничени",
    }
    for section, hints in content_checks.items():
        found = any(h.lower() in body.lower() for h in hints.split(","))
        if found:
            ok(f"Content section '{section}' present")
        else:
            flag("dossier", f"Content section '{section}' missing from completed dossier")

    # Empty data count
    no_data = body.lower().count("нет данных") + body.lower().count("не найдено") + body.lower().count("не обнаружен")
    info(f"'No data' occurrences: {no_data}")

    # Traceback check
    if "Traceback" in body:
        flag("dossier", "Python traceback visible in dossier!")

    shot(page, "dossier_scroll")

    # ─────────────────────────────────────────────────────────────
    # TEST 2 — ZOMBIE CHECK
    # ─────────────────────────────────────────────────────────────
    print("\n══════════════════════════════════════════")
    print(" ZOMBIE CHECK (status=running in DB)")
    print("══════════════════════════════════════════")
    page.goto(BASE + f"/candidate/dossier/{ZOMBIE_CHECK_ID}")
    page.wait_for_load_state("networkidle")
    shot(page, "zombie_check")
    info(f"Zombie check URL: {page.url}")
    info(f"Title: {page.title()}")
    zombie_body = page.inner_text("body")

    if "/candidate/progress/" in page.url:
        info("Zombie redirected to progress page (status=running, in-memory task may be gone)")
        # Check if progress page shows something useful or is stuck
        info(f"Progress page text length: {len(zombie_body)} chars")
        stage_done = zombie_body.lower().count("выполн") + zombie_body.lower().count("готово") + zombie_body.lower().count("✓")
        stage_err  = zombie_body.lower().count("ошибк") + zombie_body.lower().count("error")
        info(f"Done-stage markers: {stage_done}  Error markers: {stage_err}")
        if len(zombie_body) < 500:
            flag("zombie", "Progress page for zombie check has very little content")
    elif "/candidate/dossier/" in page.url:
        ok("Zombie check loaded as dossier (status was corrected or check completed)")

    # ─────────────────────────────────────────────────────────────
    # TEST 3 — CHAT (correct button)
    # ─────────────────────────────────────────────────────────────
    print("\n══════════════════════════════════════════")
    print(" CHAT (using #send-btn)")
    print("══════════════════════════════════════════")
    page.goto(BASE + "/chat/")
    page.wait_for_load_state("networkidle")
    shot(page, "chat_initial")
    info(f"Chat URL: {page.url}")

    # Verify elements
    input_el = page.locator("#chat-input")
    send_btn  = page.locator("#send-btn")
    if input_el.count() == 0:
        flag("chat", "#chat-input not found")
    if send_btn.count() == 0:
        flag("chat", "#send-btn not found")
    else:
        ok("Chat #chat-input and #send-btn found")

    # Existing messages
    msgs_before = page.locator(".msg-bubble").count()
    info(f"Messages before send: {msgs_before}")

    # Send a message
    TEST_MSG = "тест проверочного сообщения — Playwright"
    input_el.fill(TEST_MSG)
    shot(page, "chat_filled")
    send_btn.click()
    page.wait_for_timeout(2000)
    shot(page, "chat_after_send")
    info(f"URL after send: {page.url}")

    if page.url != BASE + "/chat/":
        flag("chat", f"Chat navigated away after send! URL: {page.url}")
    else:
        ok("Chat stayed on /chat/ after send")

    # Message visible
    msgs_after = page.locator(".msg-bubble").count()
    info(f"Messages after send: {msgs_after}")
    body_after = page.inner_text("body")
    if TEST_MSG in body_after:
        ok("Sent message visible in chat UI")
    else:
        flag("chat", "Sent message NOT visible in chat after send")

    # Send via Enter key
    input_el.fill("второй тест — Enter key")
    input_el.press("Enter")
    page.wait_for_timeout(1500)
    shot(page, "chat_enter_key")
    msgs_enter = page.locator(".msg-bubble").count()
    info(f"Messages after Enter-key send: {msgs_enter}")
    if msgs_enter > msgs_after:
        ok("Enter-key send works")
    else:
        flag("chat", "Enter-key send did not add a message")

    # Pin a message
    pin_btns = page.locator(".msg-actions button[title='Закрепить']").all()
    info(f"Pin buttons visible: {len(pin_btns)}")
    if pin_btns:
        pin_btns[0].click()
        page.wait_for_timeout(1000)
        shot(page, "chat_pinned")
        ok("Pin button clicked")

    browser.close()

# ─────────────────────────────────────────────────────────────────
print("\n" + "═"*60)
print(f" TARGETED CHECK COMPLETE — {len(issues)} issues found")
print("═"*60)
for i, iss in enumerate(issues, 1):
    print(f"  {i}. [{iss['screen']}] {iss['msg']}")
