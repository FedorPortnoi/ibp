"""
IBP User Simulation Test - 9 Russian Targets
=============================================
Tests the full Phase 1 -> Phase 2 workflow with diverse Russian names.
Uses direct API calls + page navigation for reliability.
"""

import json
import time
import sys
import os
import io
import traceback
import requests
from datetime import datetime

# Fix Windows console encoding for Cyrillic output
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

BASE = "http://127.0.0.1:5000"
SSDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "screenshots", "user_sim")
os.makedirs(SSDIR, exist_ok=True)

TARGETS = [
    {"key": "01_kuznetsov", "name": "Дмитрий Кузнецов"},
    {"key": "02_volkova", "name": "Екатерина Волкова"},
    {"key": "03_novikov", "name": "Фёдор Новиков"},
    {"key": "04_scherbakova", "name": "Анастасия Щербакова"},
    {"key": "05_chernyshev", "name": "Ярослав Чернышёв"},
    {"key": "06_belousova", "name": "Юлия Белоусова"},
    {"key": "07_lebedev", "name": "Евгений Лебедев"},
    {"key": "08_kozlova", "name": "Алёна Козлова"},
    {"key": "09_zhukova", "name": "Ксения Жукова"},
]


def ss(page, name):
    """Safe screenshot."""
    try:
        page.screenshot(path=os.path.join(SSDIR, f"{name}.png"), timeout=8000)
    except Exception:
        pass


def test_one(page, target, idx):
    """Test one target: Phase 1 search + Phase 2 analysis."""
    key, name = target["key"], target["name"]
    R = {"name": name, "key": key, "p1_count": 0, "p1_time": 0, "p1_profiles": [],
         "p2_emails": 0, "p2_phones": 0, "p2_time": 0, "issues": []}

    print(f"\n{'='*60}")
    print(f"TARGET {idx+1}/9: {name}")
    print(f"{'='*60}")

    # === PHASE 1: Create investigation via API ===
    print(f"  [P1] Creating investigation...")
    p1_start = time.time()
    try:
        resp = requests.post(f"{BASE}/phase1/new", data={"target_name": name}, timeout=10)
        data = resp.json()
        if not data.get("success"):
            R["issues"].append(f"API error: {data.get('error', 'unknown')}")
            return R
        inv_id = data["investigation_id"]
        redirect_url = data["redirect"]
        print(f"  [P1] Investigation {inv_id[:8]}... created")
    except Exception as e:
        R["issues"].append(f"API create error: {e}")
        return R

    # === PHASE 1: Load search results page (this triggers VK search synchronously) ===
    print(f"  [P1] Loading search results (VK search runs server-side)...")
    try:
        page.goto(f"{BASE}{redirect_url}", wait_until="domcontentloaded", timeout=120000)
        p1_time = time.time() - p1_start
        R["p1_time"] = round(p1_time, 1)
        print(f"  [P1] Page loaded in {p1_time:.1f}s")
    except PlaywrightTimeout:
        p1_time = time.time() - p1_start
        R["p1_time"] = round(p1_time, 1)
        R["issues"].append(f"Search page timeout ({p1_time:.0f}s)")
        ss(page, f"{key}_timeout")
        return R

    time.sleep(1)
    ss(page, f"{key}_01_results")

    # === Extract profiles ===
    try:
        profiles = page.evaluate("""() => {
            return Array.from(document.querySelectorAll('.profile-card')).map(c => ({
                name: c.querySelector('h3')?.textContent?.trim() || '',
                user: c.querySelector('p.text-violet, .text-violet')?.textContent?.trim() || '',
                sim: c.dataset.similarity || '0',
                pid: c.dataset.profileId || '',
            }));
        }""")
        R["p1_count"] = len(profiles)
        R["p1_profiles"] = profiles[:10]
        print(f"  [P1] Found {len(profiles)} profiles")
        for p in profiles[:5]:
            print(f"       {p['name']} ({p['user']}) sim={p['sim']}%")
    except Exception as e:
        R["issues"].append(f"Extract error: {e}")
        return R

    if R["p1_count"] == 0:
        R["issues"].append("No profiles found (demo mode)")
        return R

    # === PHASE 1->2: Confirm first profile ===
    first_pid = profiles[0]["pid"]
    print(f"  [P1->2] Confirming profile {first_pid}...")
    try:
        resp = requests.post(f"{BASE}/phase1/confirm/{inv_id}/{first_pid}",
                           json={}, timeout=10)
        data = resp.json()
        if not data.get("success"):
            R["issues"].append(f"Confirm error: {data.get('error')}")
            return R
        analyze_url = data.get("redirect", f"/phase2/analyze/{inv_id}")
        print(f"  [P1->2] Confirmed. Redirect: {analyze_url}")
    except Exception as e:
        R["issues"].append(f"Confirm API error: {e}")
        return R

    # === PHASE 2: Start analysis via API (more reliable than page auto-start) ===
    print(f"  [P2] Starting analysis via API...")
    p2_start = time.time()
    task_id = None

    try:
        resp = requests.post(f"{BASE}/phase2/api/start-analysis/{inv_id}",
                           json={}, timeout=10)
        data = resp.json()
        if data.get("success") and data.get("task_id"):
            task_id = data["task_id"]
            print(f"  [P2] Task {task_id[:8]}... started")
        else:
            R["issues"].append(f"P2 start error: {data.get('error', 'unknown')}")
            return R
    except Exception as e:
        R["issues"].append(f"P2 start API error: {e}")
        return R

    # === Poll progress via API (not DOM) ===
    print(f"  [P2] Waiting for analysis (max 4min)...")
    for tick in range(240):
        time.sleep(1)
        try:
            resp = requests.get(f"{BASE}/phase2/progress/{task_id}", timeout=5)
            state = resp.json()
        except Exception:
            continue

        status = state.get("status", "")
        pct = state.get("percent_complete", 0)
        step = state.get("current_step", "")

        if status == "complete":
            p2t = time.time() - p2_start
            R["p2_time"] = round(p2t, 1)
            print(f"  [P2] Complete in {p2t:.1f}s")
            break

        if status == "error":
            p2t = time.time() - p2_start
            R["p2_time"] = round(p2t, 1)
            err = state.get("error", "unknown error")
            R["issues"].append(f"Phase 2 error: {err}")
            print(f"  [P2] ERROR: {err}")
            break

        if status == "cancelled":
            p2t = time.time() - p2_start
            R["p2_time"] = round(p2t, 1)
            R["issues"].append("Phase 2 cancelled")
            break

        if tick % 15 == 0 and tick > 0:
            print(f"  [P2] {pct}% - {step}")
    else:
        p2t = time.time() - p2_start
        R["p2_time"] = round(p2t, 1)
        R["issues"].append(f"Phase 2 timeout ({p2t:.0f}s)")

    # === Get results via API ===
    try:
        resp = requests.get(f"{BASE}/phase2/results/{task_id}", timeout=10)
        rdata = resp.json()
        if rdata.get("status") == "success" and rdata.get("results"):
            res = rdata["results"]
            R["p2_emails"] = res.get("emails_found", 0)
            R["p2_phones"] = res.get("phones_found", 0)
            print(f"  [P2] Results: {R['p2_emails']} emails, {R['p2_phones']} phones")
    except Exception as e:
        print(f"  [WARN] Results fetch: {e}")

    # === Screenshot results page ===
    try:
        page.goto(f"{BASE}/phase2/buratino/results/{inv_id}",
                 wait_until="domcontentloaded", timeout=15000)
        time.sleep(2)
        ss(page, f"{key}_04_results")
    except Exception:
        pass

    # === Dashboard check ===
    try:
        page.goto(f"{BASE}/investigations", wait_until="domcontentloaded", timeout=10000)
        ss(page, f"{key}_05_dashboard")
    except Exception:
        pass

    return R


def main():
    results = []
    t0 = datetime.now()
    print("=" * 70)
    print("IBP USER SIMULATION TEST - 9 RUSSIAN TARGETS")
    print(f"Started: {t0.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    # Quick server check
    try:
        r = requests.get(BASE, timeout=5)
        print(f"[OK] Server running (status {r.status_code})")
    except Exception as e:
        print(f"[FATAL] Server not reachable: {e}")
        return

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1280, "height": 900}, locale="ru-RU")
        page = ctx.new_page()

        for i, t in enumerate(TARGETS):
            try:
                r = test_one(page, t, i)
                results.append(r)
                # Quick summary
                iss = f" ISSUES={len(r['issues'])}" if r['issues'] else ""
                print(f"  >> P1={r['p1_count']} P2={r['p2_emails']}em/{r['p2_phones']}ph{iss}")
            except Exception as e:
                print(f"  [FATAL] {t['name']}: {e}")
                traceback.print_exc()
                results.append({"name": t["name"], "key": t["key"],
                              "p1_count": 0, "p1_time": 0, "p2_emails": 0, "p2_phones": 0,
                              "p2_time": 0, "issues": [f"Fatal: {e}"]})

        browser.close()

    # === Final Report ===
    t1 = datetime.now()
    elapsed = (t1 - t0).total_seconds()
    print(f"\n\n{'='*70}")
    print(f"FINAL REPORT | {t1.strftime('%Y-%m-%d %H:%M')} | {elapsed:.0f}s ({elapsed/60:.1f}m)")
    print(f"{'='*70}\n")

    tp1, tem, tph, tiss = 0, 0, 0, 0
    for i, r in enumerate(results):
        tp1 += r["p1_count"]; tem += r["p2_emails"]; tph += r["p2_phones"]
        tiss += len(r.get("issues", []))
        iss = f" | {len(r['issues'])} issues" if r.get("issues") else ""
        print(f"  {i+1}. {r['name']:25s} P1={r['p1_count']:3d} ({r['p1_time']}s) "
              f"P2: {r['p2_emails']}em {r['p2_phones']}ph ({r['p2_time']}s){iss}")

    print(f"\n  TOTALS: {tp1} profiles | {tem} emails | {tph} phones | {tiss} issues")

    p1t = [r["p1_time"] for r in results if r["p1_time"] > 0]
    p2t = [r["p2_time"] for r in results if r["p2_time"] > 0]
    if p1t: print(f"  Avg P1: {sum(p1t)/len(p1t):.1f}s  (min={min(p1t)}s max={max(p1t)}s)")
    if p2t: print(f"  Avg P2: {sum(p2t)/len(p2t):.1f}s  (min={min(p2t)}s max={max(p2t)}s)")

    if tiss:
        print(f"\n  ALL ISSUES:")
        for r in results:
            for iss in r.get("issues", []):
                print(f"    [{r['key']}] {iss}")

    with open(os.path.join(SSDIR, "results.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n  Saved: {SSDIR}/results.json")


if __name__ == "__main__":
    main()
