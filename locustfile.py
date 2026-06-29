"""
Stirlitz (IBP) — Locust load test
===================================
Tests every user-facing workflow under concurrent load.
Pipeline runs are intentionally avoided — invalid INN/form data
is used so the server rejects at validation, zero external API calls.

Run:
    venv/Scripts/locust -f locustfile.py --host http://127.0.0.1:5000

Then open http://localhost:8089 and configure users + ramp-up rate.
Suggested start: 10 users, ramp 2/s. Then try 25, 50, 100.
"""

import json
import os
import random
import string
import time
from locust import HttpUser, task, between, events
from locust.exception import RescheduleTask


# ─── Credentials ────────────────────────────────────────────────────────────
ADMIN_USER = os.environ.get("LOCUST_ADMIN_USER", "Fedor")
ADMIN_PASS = os.environ.get("LOCUST_ADMIN_PASS", "")

# Invalid INN values — server rejects these at validation, pipeline never starts.
# NOTE: "000...0" passes the Russian INN checksum algorithm (all zeros → all
# check digits are 0), so it actually starts pipelines. Use "111...1" instead.
INVALID_INN_PERSON  = "111111111111"   # 12-digit, fails INN checksum
INVALID_INN_COMPANY = "1111111111"     # 10-digit, fails INN checksum


def _csrf(response):
    """Extract CSRF token from <meta name='csrf-token'> in an HTML response."""
    try:
        text = response.text
        idx = text.find('name="csrf-token"')
        if idx == -1:
            return ""
        content_start = text.find('content="', idx) + len('content="')
        content_end = text.find('"', content_start)
        return text[content_start:content_end]
    except Exception:
        return ""


def _rand_str(n=8):
    return "".join(random.choices(string.ascii_lowercase, k=n))


# ─── Base user class with session management ─────────────────────────────────
class StirUser(HttpUser):
    """
    Base class. Each Locust user logs in with admin credentials
    and gets its own session cookie — realistic because the server
    issues a unique session per login even for the same account.
    """
    abstract = True
    wait_time = between(1, 3)

    def on_start(self):
        self.csrf = ""
        self.logged_in = False
        self._login()

    def _login(self):
        # GET login page → extract CSRF
        resp = self.client.get("/login", name="/login [GET]")
        if resp.status_code != 200:
            return
        self.csrf = _csrf(resp)

        # POST credentials
        resp = self.client.post(
            "/login",
            data={
                "username": ADMIN_USER,
                "password": ADMIN_PASS,
                "csrf_token": self.csrf,
            },
            allow_redirects=True,
            name="/login [POST]",
        )
        if resp.status_code == 200 and "dashboard" in resp.url:
            self.logged_in = True
            self.csrf = _csrf(resp)
        else:
            # Could be rate-limited — back off and retry once
            time.sleep(2)
            self.logged_in = False

    def _refresh_csrf(self, url="/dashboard"):
        """Re-fetch CSRF from a page (token rotates per session)."""
        resp = self.client.get(url, name=f"{url} [csrf-refresh]")
        if resp.status_code == 200:
            new = _csrf(resp)
            if new:
                self.csrf = new

    def _get_json(self, url, name=None):
        return self.client.get(url, headers={"Accept": "application/json"}, name=name or url)

    def _post_json(self, url, payload, name=None):
        return self.client.post(
            url,
            json=payload,
            headers={
                "Content-Type": "application/json",
                "X-CSRFToken": self.csrf,
            },
            name=name or url,
        )

    def _require_login(self):
        if not self.logged_in:
            self._login()
        if not self.logged_in:
            raise RescheduleTask()


# ─── Full user flow: reads, writes, forms ────────────────────────────────────
class FullUser(StirUser):
    """Simulates a real analyst: navigates history, opens dossiers, sends chat."""
    wait_time = between(1, 4)

    # ── Read-heavy tasks (weight=3 = called 3x as often as weight=1) ──────────

    @task(3)
    def view_dashboard(self):
        self._require_login()
        self.client.get("/dashboard", name="/dashboard")

    @task(3)
    def view_candidate_history(self):
        self._require_login()
        resp = self.client.get("/candidate/history", name="/candidate/history")
        # If history has any dossier links, open a random one
        if resp.status_code == 200 and '/candidate/dossier/' in resp.text:
            text = resp.text
            start = text.find('/candidate/dossier/')
            end = text.find('"', start)
            url = text[start:end]
            if url:
                self.client.get(url, name="/candidate/dossier/[id]")

    @task(3)
    def view_company_history(self):
        self._require_login()
        self.client.get("/company/history", name="/company/history")

    @task(2)
    def view_chat(self):
        self._require_login()
        self.client.get("/chat/", name="/chat/")
        self._get_json("/chat/api/messages", name="/chat/api/messages [GET]")

    @task(2)
    def view_candidate_new(self):
        self._require_login()
        self.client.get("/candidate/new", name="/candidate/new")

    @task(2)
    def view_company_new(self):
        self._require_login()
        self.client.get("/company/new", name="/company/new")

    # ── Write tasks (lighter weight) ──────────────────────────────────────────

    @task(1)
    def send_chat_message(self):
        self._require_login()
        msg = f"load test message {_rand_str(6)} at {time.time():.0f}"
        resp = self._post_json(
            "/chat/api/messages",
            {"content": msg},
            name="/chat/api/messages [POST]",
        )
        # Delete the message we just created to avoid DB bloat
        if resp.status_code == 201:
            try:
                msg_id = resp.json().get("id")
                if msg_id:
                    self.client.delete(
                        f"/chat/api/messages/{msg_id}",
                        headers={"X-CSRFToken": self.csrf},
                        name="/chat/api/messages/[id] [DELETE]",
                    )
            except Exception:
                pass

    @task(1)
    def submit_candidate_invalid(self):
        """Submit candidate form with invalid INN — server must reject with 400, NO pipeline."""
        self._require_login()
        self._refresh_csrf("/candidate/new")
        with self.client.post(
            "/candidate/start",
            json={
                "full_name": "Тест Нагрузочный Тест",
                "date_of_birth": "1990-01-01",
                "inn": INVALID_INN_PERSON,
                "pd_consent": True,
                "check_mode": "quick",
            },
            headers={"Content-Type": "application/json", "X-CSRFToken": self.csrf},
            name="/candidate/start [invalid INN]",
            catch_response=True,
        ) as resp:
            if resp.status_code == 400:
                resp.success()   # 400 = validation reject = correct behaviour
            elif resp.status_code != 200:
                resp.failure(f"Unexpected {resp.status_code}: {resp.text[:100]}")

    @task(1)
    def submit_company_invalid(self):
        """Submit company form with invalid INN — server must reject with 400, NO pipeline."""
        self._require_login()
        self._refresh_csrf("/company/new")
        with self.client.post(
            "/company/start",
            json={"inn": INVALID_INN_COMPANY},
            headers={"Content-Type": "application/json", "X-CSRFToken": self.csrf},
            name="/company/start [invalid INN]",
            catch_response=True,
        ) as resp:
            if resp.status_code == 400:
                resp.success()   # validation reject = correct
            elif resp.status_code != 200:
                resp.failure(f"Unexpected {resp.status_code}: {resp.text[:100]}")

    @task(1)
    def vk_token_status(self):
        """Lightweight API endpoint — polled by every page via JS."""
        self._require_login()
        self.client.get("/api/vk/token-status", name="/api/vk/token-status")

    # ── Admin-only tasks ───────────────────────────────────────────────────────

    @task(1)
    def view_admin_users(self):
        self._require_login()
        self.client.get("/admin/users/", name="/admin/users/")

    @task(1)
    def view_subscribe(self):
        """Admin gets redirected to /candidate/new — tests redirect path."""
        self._require_login()
        self.client.get("/subscribe", name="/subscribe", allow_redirects=True)


# ─── Light reader — browser that just pages through the UI ──────────────────
class BrowserUser(StirUser):
    """Simulates a passive analyst who just reads pages without submitting."""
    wait_time = between(2, 6)

    @task(4)
    def browse_history(self):
        self._require_login()
        self.client.get("/candidate/history", name="/candidate/history")

    @task(3)
    def browse_dashboard(self):
        self._require_login()
        self.client.get("/dashboard", name="/dashboard")

    @task(2)
    def browse_company_history(self):
        self._require_login()
        self.client.get("/company/history", name="/company/history")

    @task(1)
    def browse_chat(self):
        self._require_login()
        self.client.get("/chat/", name="/chat/")

    @task(1)
    def check_vk_status(self):
        self._require_login()
        self.client.get("/api/vk/token-status", name="/api/vk/token-status")


# ─── Event hooks: log rate-limit hits ────────────────────────────────────────
@events.request.add_listener
def on_request(request_type, name, response_time, response_length,
               response, context, exception, **kwargs):
    if response and response.status_code == 429:
        print(f"  [RATE LIMIT 429] {request_type} {name} after {response_time:.0f}ms")
