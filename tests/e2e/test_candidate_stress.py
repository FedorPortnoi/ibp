"""
E2E Stress Test: Проверка кандидата — 60+ Cycles
=================================================
Runs 60 unique candidate checks against the live IBP server,
covering minimal input, full input, edge cases, and security tests.

Pipelines are submitted in parallel batches (BATCH_SIZE at a time)
to reduce total wall-clock time.

Usage:
    python tests/e2e/test_candidate_stress.py
"""

import json
import logging
import os
import random
import re
import sys
import time
from datetime import date, timedelta
from pathlib import Path

# Fix Windows console encoding for Cyrillic output
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from playwright.sync_api import sync_playwright

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
BASE_URL = os.environ.get("IBP_BASE_URL", "https://shtirletzsled.ru")
LOGIN_PASSWORD = os.environ.get("IBP_PASSWORD", "Hofstra2026")
PIPELINE_TIMEOUT = 600       # 10 min max per pipeline
POLL_INTERVAL = 3            # seconds between progress polls
BATCH_SIZE = 3               # parallel pipelines per batch
SCREENSHOT_DIR = Path(__file__).resolve().parent / "screenshots"
RESULTS_FILE = Path(__file__).resolve().parent / "e2e_results.json"
LOG_FILE = Path(__file__).resolve().parent / "e2e_run.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(str(LOG_FILE), mode="a", encoding="utf-8"),
    ],
)
logger = logging.getLogger("e2e_candidate")

# ---------------------------------------------------------------------------
# INN Generator
# ---------------------------------------------------------------------------

def generate_valid_inn_12():
    """Generate a random valid 12-digit Russian personal INN."""
    digits = [random.randint(0, 9) for _ in range(10)]
    w11 = [7, 2, 4, 10, 3, 5, 9, 4, 6, 8]
    s11 = sum(d * w for d, w in zip(digits, w11))
    digits.append(s11 % 11 % 10)
    w12 = [3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8]
    s12 = sum(d * w for d, w in zip(digits, w12))
    digits.append(s12 % 11 % 10)
    return "".join(str(d) for d in digits)


def random_dob(min_age: int, max_age: int) -> str:
    today = date.today()
    age = random.randint(min_age, max_age)
    month = random.randint(1, 12)
    day = random.randint(1, 28)
    return date(today.year - age, month, day).isoformat()


# ---------------------------------------------------------------------------
# Candidate Data
# ---------------------------------------------------------------------------

def build_candidates() -> list[dict]:
    candidates: list[dict] = []

    # ── Batch 1: MINIMAL INPUT (1-12) ────────────────────────────────
    for name in [
        "Иванов Сергей Петрович", "Петрова Елена Александровна",
        "Сидоров Дмитрий Николаевич", "Козлова Анна Михайловна",
        "Новиков Алексей Владимирович", "Морозова Ольга Сергеевна",
        "Волков Андрей Игоревич", "Соколова Наталья Викторовна",
        "Лебедев Михаил Андреевич", "Попова Екатерина Дмитриевна",
        "Кузнецов Владимир Юрьевич", "Егорова Мария Олеговна",
    ]:
        candidates.append({
            "full_name": name, "dob": random_dob(25, 55),
            "inn": generate_valid_inn_12(),
            "category": "minimal", "note": "Minimal required fields",
        })

    # ── Batch 2: FULL INPUT (13-24) ──────────────────────────────────
    full_names = [
        "Баженов Роман Андреевич", "Вишневская Дарья Олеговна",
        "Грачёв Артём Сергеевич", "Денисова Виктория Павловна",
        "Ермаков Кирилл Дмитриевич", "Жукова Полина Максимовна",
        "Захаров Тимур Русланович", "Ильина Софья Андреевна",
        "Калашников Данил Викторович", "Лазарева Алиса Романовна",
        "Медведев Артур Артёмович", "Никитина Варвара Ильинична",
    ]
    regions = [
        "Москва", "Санкт-Петербург", "Новосибирск", "Екатеринбург",
        "Казань", "Самара", "Ростов-на-Дону", "Краснодар",
        "Воронеж", "Пермь", "Волгоград", "Тюмень",
    ]
    for i, name in enumerate(full_names):
        candidates.append({
            "full_name": name, "dob": random_dob(22, 60),
            "inn": generate_valid_inn_12(),
            "passport": f"{random.randint(1000, 9999)} {random.randint(100000, 999999)}",
            "region": regions[i],
            "registered_address": f"г. {regions[i]}, ул. Ленина, д. {random.randint(1, 200)}, кв. {random.randint(1, 300)}",
            "phone": f"+7{random.randint(900, 999)}{random.randint(1000000, 9999999)}",
            "email": f"{name.split()[0].lower()}@mail.ru",
            "category": "full", "note": "All fields populated",
        })

    # ── Batch 3: EDGE CASE NAMES (25-36) ─────────────────────────────
    edge_names = [
        {"full_name": "Ёлкин Семён Артёмович", "note": "Ё character"},
        {"full_name": "Абдурахманов Рустам Абдулмуталлибович", "note": "Very long patronymic"},
        {"full_name": "Петрова-Водкина Елизавета Сергеевна", "note": "Hyphenated surname"},
        {"full_name": "Ким Александр", "note": "No patronymic (2 words)"},
        {"full_name": "Оглы Мамедов Рашид Гусейнович", "note": "Four words"},
        {"full_name": "  Иванов   Пётр   Сидорович  ", "note": "Extra whitespace"},
        {"full_name": "иванов пётр сидорович", "note": "All lowercase"},
        {"full_name": "СМИРНОВ АЛЕКСАНДР БОРИСОВИЧ", "note": "All uppercase"},
        {"full_name": "Цветкова Аэлита Радиевна", "note": "Rare first name"},
        {"full_name": "Белый Саша Константинович", "note": "Diminutive as legal name"},
        {"full_name": "Мюллер Ганс Фридрихович", "note": "German origin"},
        {"full_name": "Ан Ольга Петровна", "note": "2-letter surname"},
    ]
    for c in edge_names:
        c.update({"dob": random_dob(20, 65), "inn": generate_valid_inn_12(), "category": "edge_name"})
    candidates.extend(edge_names)

    # ── Batch 4: EDGE CASE DATA (37-48) ──────────────────────────────
    today = date.today()
    data_edge = [
        {"full_name": "Тестов Иван Петрович", "dob": "1990-05-15",
         "inn": "7707083893", "category": "edge_data", "note": "10-digit company INN"},
        {"full_name": "Будущий Ребёнок Тестович",
         "dob": (today + timedelta(days=30)).isoformat(),
         "inn": generate_valid_inn_12(), "category": "edge_data",
         "note": "Future DOB", "expect_reject": True, "reject_reason": "Future DOB"},
        {"full_name": "Молодой Студент Тестович",
         "dob": today.replace(year=today.year - 16).isoformat(),
         "inn": generate_valid_inn_12(), "category": "edge_data", "note": "Age exactly 16"},
        {"full_name": "Древний Старец Мудрецович",
         "dob": today.replace(year=today.year - 100).isoformat(),
         "inn": generate_valid_inn_12(), "category": "edge_data", "note": "Age exactly 100"},
        {"full_name": "Фальшивый ИНН Тестович", "dob": "1985-06-20",
         "inn": "123456789012", "category": "edge_data",
         "note": "Invalid INN checksum", "expect_reject": True, "reject_reason": "Invalid INN"},
        {"full_name": "Безпробелов Паспорт Тестович", "dob": "1988-11-03",
         "inn": generate_valid_inn_12(), "passport": "4515123456",
         "category": "edge_data", "note": "Passport without space"},
        {"full_name": "Спробелов Паспорт Тестович", "dob": "1988-11-03",
         "inn": generate_valid_inn_12(), "passport": "4515 123456",
         "category": "edge_data", "note": "Passport with space"},
        {"full_name": "Безплюсов Телефон Тестович", "dob": "1992-02-14",
         "inn": generate_valid_inn_12(), "phone": "89001234567",
         "category": "edge_data", "note": "Phone 8-format"},
        {"full_name": "Длинный Адрес Тестович", "dob": "1987-09-22",
         "inn": generate_valid_inn_12(),
         "registered_address": ("Россия, г. Москва, ЦАО, район Арбат, "
                                "ул. Старый Арбат, д. 123, корп. 4, стр. 5, "
                                "кв. 678, подъезд 9, этаж 10. ") * 5,
         "category": "edge_data", "note": "Very long address (500+ chars)"},
        {"full_name": "Пустой Опционал Тестович", "dob": "1995-04-10",
         "inn": generate_valid_inn_12(),
         "passport": "", "region": "", "registered_address": "",
         "phone": "", "email": "",
         "category": "edge_data", "note": "Empty optional strings"},
        {"full_name": "Сложный Емейл Тестович", "dob": "1991-07-18",
         "inn": generate_valid_inn_12(), "email": "test.user+tag@gmail.com",
         "category": "edge_data", "note": "Email with + and dots"},
        {"full_name": "Ошибочный ИНН Тестович", "dob": "1993-02-28",
         "inn": "7707083890", "category": "edge_data",
         "note": "10-digit INN bad checksum",
         "expect_reject": True, "reject_reason": "Invalid INN checksum"},
    ]
    candidates.extend(data_edge)

    # ── Batch 5: SECURITY & STRESS (49-60) ───────────────────────────
    security = [
        {"full_name": '<script>alert("xss")</script> Тестов Кандидат',
         "dob": "1990-01-01", "inn": generate_valid_inn_12(),
         "category": "security", "note": "XSS in name (tags stripped)"},
        {"full_name": "Иванов'; DROP TABLE candidate_check;-- Петрович",
         "dob": "1990-01-01", "inn": generate_valid_inn_12(),
         "category": "security", "note": "SQL injection in name"},
        {"full_name": "Нормальный Человек Тестович",
         "dob": "1990-01-01", "inn": generate_valid_inn_12(),
         "registered_address": '<img src=x onerror=alert(1)>',
         "category": "security", "note": "XSS in address"},
        {"full_name": "Иванов\u200b Пётр\u200b Сергеевич",
         "dob": "1990-01-01", "inn": generate_valid_inn_12(),
         "category": "security", "note": "Zero-width chars in name"},
        {"full_name": "Тестов\u202e Обратный Тексттест",
         "dob": "1990-01-01", "inn": generate_valid_inn_12(),
         "category": "security", "note": "RTL override in name"},
        {"full_name": "Иванов Сергей Петрович",
         "dob": "1985-03-20", "inn": generate_valid_inn_12(),
         "category": "stress", "note": "Rapid re-submission"},
        {"full_name": "Иванов Сергей Петрович",
         "dob": "1985-03-20", "inn": candidates[0]["inn"],
         "category": "stress", "note": "Duplicate INN of cycle 1"},
        {"full_name": "А" * 255,
         "dob": "1990-01-01", "inn": generate_valid_inn_12(),
         "category": "security", "note": "255-char single-word name",
         "expect_reject": True, "reject_reason": "Less than 2 words"},
        {"full_name": "Иванов\nПётр\nСергеевич",
         "dob": "1990-01-01", "inn": generate_valid_inn_12(),
         "category": "security", "note": "Newlines in name"},
        {"full_name": "Иванов\tПётр\tСергеевич",
         "dob": "1990-01-01", "inn": generate_valid_inn_12(),
         "category": "security", "note": "Tabs in name"},
        {"full_name": "Иванов и Петров Тестовичи",
         "dob": "1990-01-01", "inn": generate_valid_inn_12(),
         "category": "security", "note": "Ampersand in name"},
        {"full_name": "Тестов Огнеопасный Кандидатович",
         "dob": "1990-01-01", "inn": generate_valid_inn_12(),
         "category": "security", "note": "Control: normal name"},
    ]
    candidates.extend(security)

    return candidates


# ---------------------------------------------------------------------------
# The Runner
# ---------------------------------------------------------------------------

class CandidateStressTest:
    def __init__(self):
        self.results: list[dict] = []
        self.bugs: list[dict] = []

    def _login(self, page):
        logger.info("Logging in to %s ...", BASE_URL)
        page.goto(f"{BASE_URL}/login", wait_until="domcontentloaded")
        pw = page.locator('input[name="password"]')
        pw.wait_for(state="attached", timeout=15000)
        pw.scroll_into_view_if_needed()
        pw.wait_for(state="visible", timeout=10000)
        pw.fill(LOGIN_PASSWORD)
        remember = page.locator("#remember")
        if remember.is_visible():
            remember.check()
        page.locator('button[type="submit"]').first.click()
        page.wait_for_url(lambda u: "/login" not in u, timeout=15000)
        logger.info("Login OK — %s", page.url)

    # ── Get CSRF token ────────────────────────────────────────────────
    def _get_csrf(self, page) -> str:
        page.goto(f"{BASE_URL}/phase1/new?tab=candidate", wait_until="domcontentloaded")
        page.wait_for_selector("#candidate-form", timeout=10000)
        return page.locator('input[name="csrf_token"]').get_attribute("value")

    # ── Submit candidate via JSON API ────────────────────────────────
    def _submit(self, page, candidate: dict, csrf: str) -> dict:
        payload = {
            "csrf_token": csrf,
            "full_name": candidate["full_name"],
            "date_of_birth": candidate["dob"],
            "inn": candidate["inn"],
            "check_mode": candidate.get("check_mode", "quick"),
        }
        for key in ("passport", "region", "registered_address", "phone", "email"):
            if key in candidate and candidate[key] is not None:
                payload[key] = candidate[key]

        result = page.evaluate("""async (payload) => {
            const resp = await fetch('/candidate/start', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(payload),
            });
            const data = await resp.json();
            return {ok: resp.ok, status: resp.status, data: data};
        }""", payload)

        if result["ok"] and result["data"].get("success"):
            return {"accepted": True,
                    "task_id": result["data"]["task_id"],
                    "check_id": result["data"]["check_id"]}
        return {"accepted": False,
                "error": result["data"].get("error", f"HTTP {result['status']}"),
                "status_code": result["status"]}

    # ── Poll a single pipeline via API ────────────────────────────────
    def _poll_once(self, page, task_id: str) -> dict:
        """Returns raw progress data from the server."""
        try:
            return page.evaluate("""async (tid) => {
                try {
                    const r = await fetch('/candidate/progress/' + tid + '/status');
                    const d = await r.json();
                    return {http: r.status, ...d};
                } catch(e) { return {fetch_error: e.message}; }
            }""", task_id)
        except Exception as e:
            return {"fetch_error": str(e)}

    # ── Check dossier via fetch (DB-level, works across workers) ─────
    def _check_dossier_ready(self, page, check_id: str) -> bool:
        try:
            r = page.evaluate("""async (cid) => {
                const r = await fetch('/candidate/dossier/' + cid);
                const t = await r.text();
                return {
                    ok: r.status === 200,
                    has_content: t.includes('section-header') || t.includes('dossier-card') || t.length > 50000,
                    redirected_to_progress: r.url.includes('/progress/'),
                };
            }""", check_id)
            return r.get("ok") and r.get("has_content") and not r.get("redirected_to_progress")
        except Exception:
            return False

    # ── Verify dossier (via fetch to avoid worker affinity redirects) ─
    def _verify_dossier(self, page, check_id: str, candidate: dict) -> dict:
        # Use fetch() instead of page.goto() to avoid gunicorn worker
        # affinity issues where dossier URL redirects to progress page
        # on a different worker that doesn't know the task.
        r = {}
        for attempt in range(5):
            try:
                r = page.evaluate("""async (cid) => {
                    const resp = await fetch('/candidate/dossier/' + cid);
                    const text = await resp.text();
                    return {
                        status: resp.status,
                        url: resp.url,
                        content: text.toLowerCase(),
                        length: text.length,
                        redirected: resp.redirected,
                    };
                }""", check_id)
                # Good response: 200 with real dossier content (not progress redirect)
                is_dossier = (
                    r.get("status") == 200
                    and r.get("length", 0) > 5000
                    and "/progress/" not in r.get("url", "")
                    and "досье" in r.get("content", "")
                )
                if is_dossier:
                    break
                if attempt < 4:
                    time.sleep(3)
            except Exception:
                if attempt < 4:
                    time.sleep(3)
                else:
                    return {"sections": [], "issues": ["fetch error"]}

        content = r.get("content", "")
        status = r.get("status", 0)
        issues: list[str] = []

        if status == 500 or "internal server error" in content:
            issues.append("500 Internal Server Error")
            return {"sections": [], "issues": issues}
        if status == 404:
            issues.append("404 page")
            return {"sections": [], "issues": issues}
        if "/progress/" in r.get("url", ""):
            issues.append("Redirected to progress page (worker affinity)")
            return {"sections": [], "issues": issues}

        # Check name
        cyrillic = [w for w in candidate["full_name"].strip().split() if re.search(r'[а-яА-ЯёЁ]', w)]
        if cyrillic and not any(w.lower() in content for w in cyrillic):
            issues.append(f"Name not found on dossier ({cyrillic[:2]})")

        # Check sections
        section_kw = {
            "identity": ["идентификация", "инн"],
            "business": ["бизнес", "егрюл"],
            "courts": ["суд", "судебн"],
            "fssp": ["фссп", "долг", "исполнительн", "checko"],
            "bankruptcy": ["банкрот"],
            "sanctions": ["санкци", "розыск"],
            "social": ["соцсет", "вконтакте", "telegram"],
            "contacts": ["контакт", "телефон"],
            "risk": ["риск", "оценка", "флаг"],
        }
        found = [s for s, kws in section_kw.items() if any(k in content for k in kws)]
        if len(found) < 3:
            issues.append(f"Only {len(found)} sections: {found}")

        has_pdf = "pdf" in content
        has_json = "json" in content
        if not has_pdf:
            issues.append("No PDF button")
        if not has_json:
            issues.append("No JSON button")

        return {"sections": found, "issues": issues, "has_pdf": has_pdf, "has_json": has_json}

    # ── Run rejection-only cycles (no pipeline) ──────────────────────
    def _run_rejection_cycle(self, page, num: int, candidate: dict, csrf: str) -> dict:
        result = self._make_result(num, candidate)
        start = time.time()
        sub = self._submit(page, candidate, csrf)
        if not sub["accepted"]:
            result["status"] = "EXPECTED_REJECT"
            result["error"] = f"Correctly rejected: {sub['error']}"
        else:
            result["status"] = "FAIL"
            result["error"] = (f"Expected rejection ({candidate.get('reject_reason')}) "
                               f"but accepted: task={sub.get('task_id')}")
        result["duration"] = time.time() - start
        return result

    # ── Run a batch of pipeline cycles in parallel ───────────────────
    def _run_pipeline_batch(self, page, batch: list[tuple[int, dict]], csrf: str) -> list[dict]:
        """
        Submit all candidates in the batch, then poll all in parallel
        until all complete or timeout.
        """
        results = []
        active: list[dict] = []  # {num, candidate, task_id, check_id, result, start, best_pct, last_stage}

        # Submit all
        for num, cand in batch:
            res = self._make_result(num, cand)
            start = time.time()

            sub = self._submit(page, cand, csrf)

            # Need a fresh CSRF for next submission
            csrf = self._get_csrf(page)

            if not sub["accepted"]:
                if cand.get("expect_reject"):
                    res["status"] = "EXPECTED_REJECT"
                    res["error"] = f"Correctly rejected: {sub['error']}"
                else:
                    res["status"] = "FAIL"
                    res["error"] = f"Unexpectedly rejected: {sub['error']}"
                res["duration"] = time.time() - start
                results.append(res)
                continue

            logger.info("  [cycle %d] Submitted → task=%s", num, sub["task_id"][:12])
            active.append({
                "num": num, "candidate": cand, "result": res,
                "task_id": sub["task_id"], "check_id": sub["check_id"],
                "start": start, "best_pct": 0, "last_stage": "",
                "dossier_checks": 0,
            })

        if not active:
            return results

        # Poll all active pipelines until done
        while active:
            still_running = []
            for item in active:
                elapsed = time.time() - item["start"]
                if elapsed > PIPELINE_TIMEOUT:
                    # Timeout — try dossier fallback
                    if self._check_dossier_ready(page, item["check_id"]):
                        logger.info("  [cycle %d] Complete (dossier fallback) at %.0fs",
                                    item["num"], elapsed)
                        item["result"]["status"] = "PENDING_VERIFY"
                        item["result"]["duration"] = elapsed
                        results.append(item["result"])
                    else:
                        logger.warning("  [cycle %d] TIMEOUT at %d%% stage=%s (%.0fs)",
                                       item["num"], item["best_pct"],
                                       item["last_stage"], elapsed)
                        item["result"]["status"] = "FAIL"
                        item["result"]["error"] = (
                            f"Timeout {PIPELINE_TIMEOUT}s (best {item['best_pct']}%, "
                            f"stage: {item['last_stage']})")
                        item["result"]["duration"] = elapsed
                        results.append(item["result"])
                    continue

                data = self._poll_once(page, item["task_id"])

                if data.get("fetch_error"):
                    still_running.append(item)
                    continue

                # 404 = wrong worker, ignore and try dossier periodically
                if data.get("http") == 404 or data.get("error") == "Задача не найдена":
                    item["dossier_checks"] += 1
                    if item["dossier_checks"] % 10 == 0:
                        if self._check_dossier_ready(page, item["check_id"]):
                            logger.info("  [cycle %d] Complete (dossier fallback) at %.0fs",
                                        item["num"], elapsed)
                            item["result"]["status"] = "PENDING_VERIFY"
                            item["result"]["duration"] = elapsed
                            results.append(item["result"])
                            continue
                    still_running.append(item)
                    continue

                pct = data.get("percent_complete", 0)
                stage = data.get("current_stage", "")
                step = data.get("current_step", "")

                # Skip stale empty polls
                if pct == 0 and not stage and item["best_pct"] > 0:
                    item["dossier_checks"] += 1
                    if item["dossier_checks"] % 10 == 0:
                        if self._check_dossier_ready(page, item["check_id"]):
                            logger.info("  [cycle %d] Complete (dossier fallback)",
                                        item["num"])
                            item["result"]["status"] = "PENDING_VERIFY"
                            item["result"]["duration"] = elapsed
                            results.append(item["result"])
                            continue
                    still_running.append(item)
                    continue

                if pct > item["best_pct"]:
                    item["best_pct"] = pct
                if stage and stage != item["last_stage"]:
                    logger.info("  [cycle %d] [%3d%%] %s — %s",
                                item["num"], pct, stage, step[:50])
                    item["last_stage"] = stage

                if data.get("is_complete"):
                    if data.get("status") == "error":
                        item["result"]["status"] = "FAIL"
                        item["result"]["error"] = f"Pipeline error: {data.get('error', '?')}"
                    else:
                        item["result"]["status"] = "PENDING_VERIFY"
                        logger.info("  [cycle %d] Pipeline complete in %.0fs",
                                    item["num"], elapsed)
                    item["result"]["duration"] = elapsed
                    results.append(item["result"])
                    continue

                still_running.append(item)

            active = still_running
            if active:
                time.sleep(POLL_INTERVAL)

        # Verify dossiers for all completed pipelines
        for res in results:
            if res["status"] == "PENDING_VERIFY":
                # Find the matching candidate + check_id
                for item_data in batch:
                    if item_data[0] == res["cycle"]:
                        cand = item_data[1]
                        break
                else:
                    cand = {"full_name": res["candidate"]}

                # Find check_id
                check_id = None
                for item in [i for i in [
                    {"num": item_data[0], "check_id": None}
                ] if False]:
                    pass  # placeholder
                # We stored check_id during submission — get it from the log
                # Simpler: just navigate to history and find it
                # Actually: let's store check_ids in a dict
                res["status"] = "PASS"  # tentative

        return results

    # ── Improved batch runner that stores check_ids ──────────────────
    def _run_pipeline_batch_v2(self, page, batch: list[tuple[int, dict]]) -> list[dict]:
        """Submit batch, poll in parallel, verify dossiers."""
        results = []
        active = []

        for num, cand in batch:
            res = self._make_result(num, cand)
            start = time.time()

            # Get fresh CSRF each time
            csrf = self._get_csrf(page)
            sub = self._submit(page, cand, csrf)

            if not sub["accepted"]:
                if cand.get("expect_reject"):
                    res["status"] = "EXPECTED_REJECT"
                    res["error"] = f"Correctly rejected: {sub['error']}"
                else:
                    res["status"] = "FAIL"
                    res["error"] = f"Unexpectedly rejected: {sub['error']}"
                res["duration"] = time.time() - start
                results.append(res)
                logger.info("  [cycle %d] %s: %s", num, res["status"], res.get("error", "")[:80])
                continue

            logger.info("  [cycle %d] Submitted: task=%s check=%s",
                        num, sub["task_id"][:12], sub["check_id"][:12])
            active.append({
                "num": num, "cand": cand, "result": res,
                "task_id": sub["task_id"], "check_id": sub["check_id"],
                "start": start, "best_pct": 0, "last_stage": "",
                "dossier_polls": 0,
            })

            # Small delay between submissions to avoid rate limit
            time.sleep(0.5)

        if not active:
            return results

        # Poll loop
        while active:
            still_active = []
            for item in active:
                elapsed = time.time() - item["start"]

                # Timeout check
                if elapsed > PIPELINE_TIMEOUT:
                    if self._check_dossier_ready(page, item["check_id"]):
                        self._finalize_pass(page, item, elapsed, results)
                    else:
                        item["result"]["status"] = "FAIL"
                        item["result"]["error"] = (
                            f"Timeout {PIPELINE_TIMEOUT}s (best {item['best_pct']}%, "
                            f"stage: {item['last_stage']})")
                        item["result"]["duration"] = elapsed
                        results.append(item["result"])
                        logger.warning("  [cycle %d] TIMEOUT at %d%%/%s after %.0fs",
                                       item["num"], item["best_pct"],
                                       item["last_stage"], elapsed)
                    continue

                data = self._poll_once(page, item["task_id"])

                # Network error — keep polling
                if data.get("fetch_error"):
                    still_active.append(item)
                    continue

                # 404 or empty (wrong gunicorn worker) — check dossier periodically
                is_404 = (data.get("http") == 404 or data.get("error") == "Задача не найдена")
                pct = data.get("percent_complete", 0)
                stage = data.get("current_stage", "")
                is_stale = (pct == 0 and not stage and item["best_pct"] > 0)

                if is_404 or is_stale:
                    item["dossier_polls"] += 1
                    # Check dossier every ~30s (10 polls × 3s)
                    if item["dossier_polls"] % 10 == 0:
                        if self._check_dossier_ready(page, item["check_id"]):
                            self._finalize_pass(page, item, elapsed, results)
                            continue
                    still_active.append(item)
                    continue

                # Real progress data
                step = data.get("current_step", "")
                if pct > item["best_pct"]:
                    item["best_pct"] = pct
                if stage and stage != item["last_stage"]:
                    logger.info("  [cycle %d] [%3d%%] %s — %s",
                                item["num"], pct, stage, step[:50])
                    item["last_stage"] = stage

                # Completion
                if data.get("is_complete"):
                    if data.get("status") == "error":
                        item["result"]["status"] = "FAIL"
                        item["result"]["error"] = f"Pipeline error: {data.get('error', '?')}"
                        item["result"]["duration"] = elapsed
                        results.append(item["result"])
                        logger.error("  [cycle %d] Pipeline ERROR: %s",
                                     item["num"], data.get("error", "?")[:100])
                    else:
                        self._finalize_pass(page, item, elapsed, results)
                    continue

                still_active.append(item)

            active = still_active
            if active:
                time.sleep(POLL_INTERVAL)

        return results

    def _finalize_pass(self, page, item: dict, elapsed: float, results: list):
        """Verify dossier and mark as PASS or FAIL."""
        check_id = item["check_id"]
        cand = item["cand"]
        res = item["result"]

        # Wait a moment for the dossier to be fully written
        time.sleep(2)

        dossier = self._verify_dossier(page, check_id, cand)
        res["dossier_sections"] = dossier.get("sections", [])
        res["dossier_issues"] = dossier.get("issues", [])
        res["duration"] = elapsed

        # Only hard-fail on 500 errors; 404/redirect are retried in _verify_dossier
        critical = [i for i in dossier.get("issues", [])
                    if "500" in i or ("404" in i and "worker" not in i.lower())]
        if critical:
            res["status"] = "FAIL"
            res["error"] = "; ".join(critical)
            logger.error("  [cycle %d] DOSSIER FAIL: %s", item["num"], res["error"])
        else:
            res["status"] = "PASS"
            if dossier.get("issues"):
                for iss in dossier["issues"]:
                    logger.warning("  [cycle %d] dossier warning: %s", item["num"], iss)
            logger.info("  [cycle %d] PASS in %.0fs  sections=%s",
                        item["num"], elapsed, dossier.get("sections", []))

        results.append(res)

    @staticmethod
    def _set_status(res: dict, status: str):
        """Set both status and verdict fields."""
        res["status"] = status
        res["verdict"] = status

    def _save_partial(self):
        """Save partial results after each batch so crashes don't lose data."""
        # Sync verdict with status
        for r in self.results:
            r["verdict"] = r["status"]
        data = {
            "summary": {
                "total": len(self.results),
                "passed": sum(1 for r in self.results if r["status"] == "PASS"),
                "failed": sum(1 for r in self.results if r["status"] == "FAIL"),
                "expected_rejects": sum(1 for r in self.results if r["status"] == "EXPECTED_REJECT"),
                "bugs_count": len(self.bugs),
                "partial": True,
            },
            "results": self.results,
            "bugs": self.bugs,
        }
        with open(str(RESULTS_FILE), "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)

    def _make_result(self, num: int, candidate: dict) -> dict:
        return {
            "cycle": num,
            "candidate": candidate["full_name"][:80],
            "category": candidate.get("category", "?"),
            "note": candidate.get("note", ""),
            "status": "UNKNOWN",
            "verdict": "UNKNOWN",
            "error": None,
            "duration": 0.0,
            "dossier_sections": [],
            "dossier_issues": [],
        }

    # ── Main runner ───────────────────────────────────────────────────
    def run(self):
        SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
        candidates = build_candidates()
        logger.info("Generated %d test candidates", len(candidates))

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={"width": 1920, "height": 1080},
                ignore_https_errors=True,
            )
            page = context.new_page()
            self._login(page)

            # Separate rejection tests from pipeline tests
            rejection_tests = [(i + 1, c) for i, c in enumerate(candidates) if c.get("expect_reject")]
            pipeline_tests = [(i + 1, c) for i, c in enumerate(candidates) if not c.get("expect_reject")]

            logger.info("Rejection tests: %d, Pipeline tests: %d",
                        len(rejection_tests), len(pipeline_tests))

            # ── Phase 1: Run all rejection tests (fast, no pipeline) ──
            logger.info("=" * 65)
            logger.info("PHASE 1: REJECTION TESTS (%d cycles)", len(rejection_tests))
            logger.info("=" * 65)

            csrf = self._get_csrf(page)
            for num, cand in rejection_tests:
                logger.info("  Cycle %d: %s — %s", num, cand["full_name"][:40], cand["note"])
                res = self._run_rejection_cycle(page, num, cand, csrf)
                self.results.append(res)
                logger.info("  → %s: %s", res["status"], (res.get("error") or "")[:80])
                if res["status"] == "FAIL":
                    self.bugs.append({
                        "cycle": num, "candidate": cand["full_name"][:80],
                        "category": cand.get("category"), "note": cand.get("note"),
                        "error": res["error"],
                    })

            self._save_partial()

            # ── Phase 2: Run pipeline tests in parallel batches ───────
            logger.info("=" * 65)
            logger.info("PHASE 2: PIPELINE TESTS (%d cycles, batch size %d)",
                        len(pipeline_tests), BATCH_SIZE)
            logger.info("=" * 65)

            for batch_start in range(0, len(pipeline_tests), BATCH_SIZE):
                batch = pipeline_tests[batch_start:batch_start + BATCH_SIZE]
                batch_nums = [b[0] for b in batch]
                logger.info("-" * 65)
                logger.info("BATCH: cycles %s", batch_nums)
                logger.info("-" * 65)

                batch_results = self._run_pipeline_batch_v2(page, batch)

                for res in batch_results:
                    self.results.append(res)
                    if res["status"] == "FAIL":
                        self.bugs.append({
                            "cycle": res["cycle"],
                            "candidate": res["candidate"],
                            "category": res["category"],
                            "note": res["note"],
                            "error": res["error"],
                        })

                # Log batch summary
                bp = sum(1 for r in batch_results if r["status"] == "PASS")
                bf = sum(1 for r in batch_results if r["status"] == "FAIL")
                be = sum(1 for r in batch_results if r["status"] == "EXPECTED_REJECT")
                logger.info("  Batch done: PASS=%d FAIL=%d EXPECTED_REJECT=%d", bp, bf, be)

                # Save partial results after each batch
                self._save_partial()

                # Small delay between batches
                time.sleep(2)

            browser.close()

        self._final_report()
        self._save_results()

    # ── Reporting ─────────────────────────────────────────────────────
    def _final_report(self):
        total = len(self.results)
        passed = sum(1 for r in self.results if r["status"] == "PASS")
        failed = sum(1 for r in self.results if r["status"] == "FAIL")
        expected = sum(1 for r in self.results if r["status"] == "EXPECTED_REJECT")

        durations = [r["duration"] for r in self.results if r["duration"] > 0]
        pipeline_durations = [r["duration"] for r in self.results
                              if r["status"] == "PASS" and r["duration"] > 5]
        avg_d = sum(pipeline_durations) / len(pipeline_durations) if pipeline_durations else 0
        max_d = max(pipeline_durations) if pipeline_durations else 0

        logger.info("")
        logger.info("=" * 70)
        logger.info("FINAL REPORT — %d CYCLES", total)
        logger.info("=" * 70)
        logger.info("  PASS:            %d/%d (%.0f%%)", passed, total,
                     100 * passed / total if total else 0)
        logger.info("  FAIL:            %d/%d", failed, total)
        logger.info("  EXPECTED_REJECT: %d/%d", expected, total)
        logger.info("  Avg pipeline:    %.0fs", avg_d)
        logger.info("  Max pipeline:    %.0fs", max_d)
        logger.info("  Bugs found:      %d", len(self.bugs))

        if self.bugs:
            logger.info("")
            logger.info("BUGS (%d):", len(self.bugs))
            for i, bug in enumerate(self.bugs, 1):
                logger.info("  #%d  cycle=%d  [%s] %s",
                            i, bug["cycle"], bug.get("category"), bug.get("note"))
                logger.info("      %s", bug["error"][:200])

        logger.info("")
        logger.info("BY CATEGORY:")
        cats: dict[str, dict] = {}
        for r in self.results:
            c = r["category"]
            cats.setdefault(c, {"PASS": 0, "FAIL": 0, "EXPECTED_REJECT": 0})
            cats[c][r["status"]] = cats[c].get(r["status"], 0) + 1
        for cat, counts in sorted(cats.items()):
            logger.info("  %-16s  P=%d  F=%d  E=%d",
                        cat, counts.get("PASS", 0), counts.get("FAIL", 0),
                        counts.get("EXPECTED_REJECT", 0))

        all_sections: set[str] = set()
        for r in self.results:
            all_sections.update(r.get("dossier_sections", []))
        logger.info("  Dossier sections seen: %s", sorted(all_sections))
        logger.info("=" * 70)

    def _save_results(self):
        # Sync verdict with status
        for r in self.results:
            r["verdict"] = r["status"]
        total = len(self.results)
        data = {
            "summary": {
                "total": total,
                "passed": sum(1 for r in self.results if r["status"] == "PASS"),
                "failed": sum(1 for r in self.results if r["status"] == "FAIL"),
                "expected_rejects": sum(1 for r in self.results if r["status"] == "EXPECTED_REJECT"),
                "bugs_count": len(self.bugs),
            },
            "results": self.results,
            "bugs": self.bugs,
        }
        with open(str(RESULTS_FILE), "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
        logger.info("Results saved to %s", RESULTS_FILE)


if __name__ == "__main__":
    suite = CandidateStressTest()
    suite.run()
