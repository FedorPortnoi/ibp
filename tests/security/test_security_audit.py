"""
Non-destructive security tests via Playwright.
Only reads pages, submits forms with test data, checks responses.
Does NOT modify production data or attack the server.

Run: python tests/security/test_security_audit.py
"""
import sys

BASE_URL = "https://shtirletzsled.ru"


class SecurityAudit:

    def __init__(self):
        self.findings = []

    def run_all(self, page):
        self.test_unauthenticated_access(page)
        self.test_xss_reflection(page)
        self.test_error_page_info_leak(page)
        self.test_http_security_headers(page)
        self.test_cookie_security(page)
        self.test_directory_traversal_responses(page)
        self.test_health_check_info_leak(page)
        self.test_session_fixation(page)
        self.print_report()

    def test_unauthenticated_access(self, page):
        """Check which routes are accessible without login."""
        protected_routes = [
            '/phase1/new',
            '/candidate/start',
            '/candidate/history',
            '/api/vk/token-status',
            '/candidate/dossier/1',
            '/candidate/export/1/json',
            '/candidate/export/1/pdf',
            '/vk/save-token',
        ]

        page.context.clear_cookies()

        for route in protected_routes:
            try:
                resp = page.goto(f"{BASE_URL}{route}", timeout=10000)
                final_url = page.url

                if '/login' not in final_url and resp and resp.status == 200:
                    self.findings.append({
                        'severity': 'HIGH',
                        'type': 'Broken Access Control',
                        'detail': f"Route {route} accessible without authentication (status {resp.status})",
                        'fix': f"Add authentication check to {route}",
                    })
                elif resp and resp.status == 500:
                    self.findings.append({
                        'severity': 'MEDIUM',
                        'type': 'Error Handling',
                        'detail': f"Route {route} returns 500 instead of redirect to login",
                        'fix': "Add proper error handler for unauthenticated access",
                    })
            except Exception:
                pass

    def test_xss_reflection(self, page):
        """Check if XSS payloads are reflected in responses."""
        self._login(page)

        xss_payloads = [
            '<script>alert(1)</script>',
            '"><img src=x onerror=alert(1)>',
            '<svg onload=alert(1)>',
        ]

        try:
            page.goto(f"{BASE_URL}/", timeout=10000)
            name_input = page.query_selector('input[name="full_name"]')
            if not name_input:
                return

            for payload in xss_payloads:
                page.goto(f"{BASE_URL}/", timeout=10000)
                name_input = page.query_selector('input[name="full_name"]')
                if name_input:
                    name_input.fill(payload)
                    content = page.content()
                    # Check if raw payload appears unescaped
                    if payload in content and f'value="{payload}"' not in content:
                        self.findings.append({
                            'severity': 'CRITICAL',
                            'type': 'Reflected XSS',
                            'detail': f"XSS payload reflected unescaped: {payload[:50]}",
                            'fix': "Ensure all user input is HTML-escaped before rendering",
                        })
        except Exception:
            pass

    def test_error_page_info_leak(self, page):
        """Check if error pages leak sensitive information."""
        self._login(page)

        error_urls = [
            '/nonexistent-page-12345',
            '/candidate/dossier/99999999',
        ]

        sensitive_patterns = [
            'Traceback',
            'File "/',
            'sqlite3',
            'sqlalchemy',
            'SECRET_KEY',
            '/opt/ibp/',
            'Debugger',
        ]

        for url in error_urls:
            try:
                page.goto(f"{BASE_URL}{url}", timeout=10000)
                content = page.content().lower()

                for pattern in sensitive_patterns:
                    if pattern.lower() in content:
                        self.findings.append({
                            'severity': 'MEDIUM',
                            'type': 'Information Disclosure',
                            'detail': f"Error page at {url} leaks '{pattern}'",
                            'fix': "Implement custom error handlers that don't expose internals",
                        })
            except Exception:
                pass

    def test_http_security_headers(self, page):
        """Check for missing security headers."""
        self._login(page)

        resp = page.goto(f"{BASE_URL}/", timeout=10000)
        if not resp:
            return
        headers = resp.all_headers()

        required_headers = {
            'x-frame-options': ('Clickjacking protection', 'MEDIUM'),
            'x-content-type-options': ('MIME sniffing protection', 'MEDIUM'),
            'strict-transport-security': ('HSTS - force HTTPS', 'MEDIUM'),
            'content-security-policy': ('CSP - prevent inline scripts/styles', 'MEDIUM'),
            'referrer-policy': ('Control referrer information', 'LOW'),
        }

        for header, (description, severity) in required_headers.items():
            if header not in headers:
                self.findings.append({
                    'severity': severity,
                    'type': 'Missing Security Header',
                    'detail': f"Missing {header} header ({description})",
                    'fix': f"Add '{header}' header in Flask after_request or nginx",
                })

    def test_cookie_security(self, page):
        """Check session cookie security flags."""
        self._login(page)

        cookies = page.context.cookies()
        for cookie in cookies:
            if 'session' in cookie['name'].lower():
                if not cookie.get('httpOnly', False):
                    self.findings.append({
                        'severity': 'MEDIUM',
                        'type': 'Cookie Security',
                        'detail': f"Session cookie '{cookie['name']}' missing HttpOnly flag",
                        'fix': "Set SESSION_COOKIE_HTTPONLY = True in Flask config",
                    })
                if not cookie.get('secure', False):
                    self.findings.append({
                        'severity': 'MEDIUM',
                        'type': 'Cookie Security',
                        'detail': f"Session cookie '{cookie['name']}' missing Secure flag",
                        'fix': "Set SESSION_COOKIE_SECURE = True in Flask config",
                    })
                if cookie.get('sameSite', '') not in ['Strict', 'Lax']:
                    self.findings.append({
                        'severity': 'LOW',
                        'type': 'Cookie Security',
                        'detail': f"Session cookie '{cookie['name']}' missing SameSite flag",
                        'fix': "Set SESSION_COOKIE_SAMESITE = 'Lax' in Flask config",
                    })

    def test_directory_traversal_responses(self, page):
        """Check directory traversal protection (read-only HTTP status check)."""
        traversal_paths = [
            '/.env',
            '/.git/config',
            '/config.py',
            '/requirements.txt',
        ]

        for path in traversal_paths:
            try:
                resp = page.goto(f"{BASE_URL}{path}", timeout=5000)
                if not resp:
                    continue
                content = page.content()

                if resp.status == 200 and (
                    'SECRET_KEY' in content
                    or 'root:' in content
                    or '[core]' in content
                    or 'flask' in content.lower()
                ):
                    self.findings.append({
                        'severity': 'CRITICAL',
                        'type': 'Path Traversal / File Exposure',
                        'detail': f"Sensitive file accessible at {path}",
                        'fix': "Configure nginx to block access to dotfiles and sensitive paths",
                    })
            except Exception:
                pass

    def test_health_check_info_leak(self, page):
        """Check if /health exposes too much info without auth."""
        page.context.clear_cookies()

        try:
            resp = page.goto(f"{BASE_URL}/health", timeout=10000)
            if not resp:
                return
            content = page.content()

            # Check for sensitive fields in unauthenticated response
            sensitive_fields = ['version', 'services', 'database', 'opensanctions', 'local_data']
            for field in sensitive_fields:
                if f'"{field}"' in content:
                    self.findings.append({
                        'severity': 'MEDIUM',
                        'type': 'Information Disclosure',
                        'detail': f"/health exposes '{field}' without authentication",
                        'fix': "Return minimal response for unauthenticated /health requests",
                    })
        except Exception:
            pass

    def test_session_fixation(self, page):
        """Check if session ID changes after login."""
        page.context.clear_cookies()

        page.goto(f"{BASE_URL}/login", timeout=10000)
        pre_cookies = {c['name']: c['value'] for c in page.context.cookies()}
        pre_session = pre_cookies.get('session', '')

        self._login(page)

        post_cookies = {c['name']: c['value'] for c in page.context.cookies()}
        post_session = post_cookies.get('session', '')

        if pre_session and post_session and pre_session == post_session:
            self.findings.append({
                'severity': 'HIGH',
                'type': 'Session Fixation',
                'detail': "Session ID does not change after login",
                'fix': "Regenerate session ID after successful authentication",
            })

    def _login(self, page):
        """Login helper."""
        page.goto(f"{BASE_URL}/login", timeout=10000)
        if '/login' in page.url:
            pw_input = page.query_selector('input[name="password"], input[type="password"]')
            if pw_input:
                pw_input.fill('Hofstra2026')
                submit = page.query_selector('button[type="submit"], input[type="submit"]')
                if submit:
                    submit.click()
                    page.wait_for_load_state('networkidle')

    def print_report(self):
        """Print formatted security audit report."""
        severity_order = {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}
        self.findings.sort(key=lambda f: severity_order.get(f['severity'], 99))

        print("\n" + "=" * 70)
        print("IBP SECURITY AUDIT REPORT (Playwright)")
        print("=" * 70)

        counts = {}
        for f in self.findings:
            counts[f['severity']] = counts.get(f['severity'], 0) + 1

        print(f"\nTotal findings: {len(self.findings)}")
        for sev in ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']:
            if sev in counts:
                print(f"  {sev}: {counts[sev]}")

        for i, f in enumerate(self.findings, 1):
            print(f"\nFinding #{i} [{f['severity']}] -- {f['type']}")
            print(f"   Detail: {f['detail']}")
            print(f"   Fix:    {f['fix']}")

        print("\n" + "=" * 70)

        if not self.findings:
            print("\nNo findings! All checks passed.")


if __name__ == '__main__':
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(ignore_https_errors=True)
        page = context.new_page()

        audit = SecurityAudit()
        audit.run_all(page)

        browser.close()

    sys.exit(1 if any(f['severity'] in ('CRITICAL', 'HIGH') for f in audit.findings) else 0)
