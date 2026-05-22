"""
AGENT 7: EXTERNAL SERVICE VALIDATOR
=====================================
Tests every external API and service integration:
- Is the service reachable?
- Does the API key work?
- Is the fallback working when service is down?
- Are rate limits respected?
"""

import requests
import json
import os
import sys
from pathlib import Path
from datetime import datetime
from time import perf_counter

PROJECT_ROOT = Path(r"C:\Users\fedor\ibp")
findings = []

def add_finding(severity, service, issue, recommendation, diagnostics=None):
    finding = {
        'agent': 'EXTERNAL_SERVICES',
        'severity': severity,
        'service': service,
        'issue': issue,
        'recommendation': recommendation,
    }
    if diagnostics:
        finding['diagnostics'] = diagnostics
    findings.append(finding)
    icon = {'CRITICAL': '[!!!]', 'HIGH': '[!!]', 'MEDIUM': '[!]', 'LOW': '[~]'}[severity]
    print(f"  {icon} [{severity}] {service} -- {issue[:80]}")

def load_env():
    env_file = PROJECT_ROOT / '.env'
    env = {}
    if env_file.exists():
        for line in env_file.read_text().split('\n'):
            if '=' in line and not line.startswith('#'):
                key, _, val = line.partition('=')
                env[key.strip()] = val.strip()
    return env

def get_config_value(env, *names):
    for name in names:
        value = (env.get(name) or os.environ.get(name) or '').strip()
        if value:
            return value
    return ''

def request_probe(method, url, timeout=(3.05, 10), **kwargs):
    started = perf_counter()
    headers = {'User-Agent': 'IBP-Agent7/1.0'}
    headers.update(kwargs.pop('headers', {}) or {})
    try:
        with requests.request(
            method,
            url,
            timeout=timeout,
            allow_redirects=False,
            headers=headers,
            stream=True,
            **kwargs
        ) as response:
            elapsed_ms = int((perf_counter() - started) * 1000)
            return {
                'ok': True,
                'method': method,
                'url': url,
                'status_code': response.status_code,
                'elapsed_ms': elapsed_ms,
                'location': response.headers.get('Location'),
                'server': response.headers.get('Server'),
            }
    except requests.ConnectTimeout as exc:
        error_type = 'connect_timeout'
        error = str(exc)
    except requests.ReadTimeout as exc:
        error_type = 'read_timeout'
        error = str(exc)
    except requests.Timeout as exc:
        error_type = 'timeout'
        error = str(exc)
    except requests.ConnectionError as exc:
        error_type = 'connection_error'
        error = str(exc)
    except requests.RequestException as exc:
        error_type = exc.__class__.__name__
        error = str(exc)

    elapsed_ms = int((perf_counter() - started) * 1000)
    return {
        'ok': False,
        'method': method,
        'url': url,
        'error_type': error_type,
        'error': error,
        'elapsed_ms': elapsed_ms,
    }

def describe_probe(label, probe):
    if probe.get('ok'):
        status = f"HTTP {probe['status_code']} in {probe['elapsed_ms']}ms"
        if probe.get('location'):
            status += f" -> {probe['location']}"
        return f"{label}: {status}"
    return (
        f"{label}: {probe.get('error_type')} after "
        f"{probe.get('elapsed_ms')}ms ({probe.get('error')})"
    )

def production_recommendation(base_url, health_probe, root_probe, readiness_probe=None):
    if health_probe.get('error_type') == 'read_timeout':
        if root_probe.get('ok'):
            diagnosis = (
                "TCP/TLS and the front door respond, but /health does not finish. "
                "This points to a stale deploy with a blocking health route, a saturated app "
                "worker, or an upstream route-specific hang."
            )
        elif root_probe.get('error_type') == 'read_timeout':
            diagnosis = (
                "Both /health and / accept the connection but do not return. "
                "This points to hung/saturated gunicorn workers or a reverse-proxy upstream stall."
            )
        else:
            diagnosis = (
                "/health read timed out and the root probe did not confirm a healthy front door. "
                "Check DNS/TLS/proxy reachability before focusing on Flask."
            )
    elif health_probe.get('error_type') in ('connect_timeout', 'connection_error'):
        diagnosis = (
            "The client could not establish a reliable connection to production. "
            "This points to DNS, firewall, provider, nginx, or host availability."
        )
    else:
        diagnosis = (
            "Production health did not return a successful response. "
            "Use the comparison probes below to separate app, proxy, and network failure."
        )

    return (
        f"{diagnosis} No SSH required: run "
        f"`curl.exe -v --connect-timeout 3 --max-time 15 {base_url}/health`, "
        f"`curl.exe -v --connect-timeout 3 --max-time 15 {base_url}/ready`, "
        f"and compare with `curl.exe -I --connect-timeout 3 --max-time 15 {base_url}/`. "
        "If / redirects or returns headers while /health times out, redeploy code containing the "
        "dependency-free public health route and restart the web service from the provider panel. "
        "If /health passes but /ready returns 503, focus on DB credentials, migrations, connection "
        "limits, and local data files. "
        "If both time out, check provider status, DNS, firewall, and nginx/load balancer health. "
        "When SSH is available, verify `curl -sf http://localhost:5000/health` inside the host/container "
        "plus `curl -sf http://localhost:5000/ready`, then inspect `docker compose logs --tail=100` "
        "or `journalctl -u ibp -n 100`."
    )

def test_vk_api(env):
    print("\n[AGENT 7] Testing VK API...")

    token = env.get('VK_SERVICE_TOKEN') or env.get('VK_USER_TOKEN') or env.get('VK_TOKEN')

    if not token:
        add_finding('HIGH', 'VK API', 'No VK token found in .env',
                    'Set VK_SERVICE_TOKEN in .env')
        return

    try:
        r = requests.get(
            'https://api.vk.com/method/users.get',
            params={'user_ids': '1', 'access_token': token, 'v': '5.199'},
            timeout=10
        )
        data = r.json()

        if 'error' in data:
            error = data['error']
            add_finding('CRITICAL', 'VK API',
                        f"VK API error: {error.get('error_msg', 'Unknown')} (code {error.get('error_code')})",
                        'Check VK token validity')
        else:
            print(f"  [OK] VK API working -- token valid")
    except Exception as e:
        add_finding('HIGH', 'VK API', f"VK API unreachable: {e}",
                    'Check network connectivity to api.vk.com')

def test_egrul(env):
    print("\n[AGENT 7] Testing EGRUL/nalog.ru...")

    base_url = 'https://egrul.nalog.ru'
    query = '7707083893'  # Public Sberbank INN fixture.
    headers = {
        'User-Agent': 'IBP-Agent7/1.0',
        'Accept': 'application/json, text/html, */*;q=0.8',
        'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'Origin': base_url,
        'Referer': f'{base_url}/',
        'X-Requested-With': 'XMLHttpRequest',
    }
    diagnostics = {'query': query, 'steps': []}

    try:
        token_response = requests.post(
            f'{base_url}/',
            data={'query': query},
            headers=headers,
            timeout=15,
        )
        diagnostics['steps'].append({
            'name': 'token',
            'status_code': token_response.status_code,
            'content_type': token_response.headers.get('Content-Type'),
        })

        if token_response.status_code != 200:
            severity = 'HIGH' if token_response.status_code in (403, 429) else 'MEDIUM'
            add_finding(severity, 'EGRUL',
                        f"EGRUL token endpoint returned HTTP {token_response.status_code}",
                        'Check egrul.nalog.ru availability and anti-bot/rate-limit status',
                        diagnostics)
            return

        try:
            token_data = token_response.json()
        except ValueError:
            add_finding('MEDIUM', 'EGRUL',
                        'EGRUL token endpoint returned non-JSON response',
                        'Inspect egrul.nalog.ru response; service may be showing maintenance or anti-bot HTML',
                        diagnostics)
            return

        token = token_data.get('t', '')
        captcha_required = bool(token_data.get('captchaRequired'))
        diagnostics['token_present'] = bool(token)
        diagnostics['captcha_required'] = captcha_required

        if captcha_required:
            add_finding('LOW', 'EGRUL',
                        'EGRUL requires CAPTCHA; automatic lookup is in degraded mode',
                        'No credential fix is available; keep manual EGRUL URL fallback and retry later',
                        diagnostics)
            return
        if not token:
            add_finding('MEDIUM', 'EGRUL',
                        'EGRUL did not return a search token',
                        'Verify the two-step EGRUL token flow and request headers',
                        diagnostics)
            return

        result_headers = {
            'User-Agent': 'IBP-Agent7/1.0',
            'Accept': 'application/json, text/html, */*;q=0.8',
            'Referer': f'{base_url}/',
            'X-Requested-With': 'XMLHttpRequest',
        }
        for attempt in range(3):
            if attempt:
                import time
                time.sleep(1)
            result_response = requests.get(
                f'{base_url}/search-result/{token}',
                headers=result_headers,
                timeout=15,
            )
            step = {
                'name': f'result_{attempt + 1}',
                'status_code': result_response.status_code,
                'content_type': result_response.headers.get('Content-Type'),
            }
            diagnostics['steps'].append(step)

            if result_response.status_code != 200:
                continue

            try:
                result_data = result_response.json()
            except ValueError:
                add_finding('MEDIUM', 'EGRUL',
                            'EGRUL result endpoint returned non-JSON response',
                            'Inspect egrul.nalog.ru response; service may be showing maintenance or anti-bot HTML',
                            diagnostics)
                return

            if result_data.get('status') == 'wait':
                continue

            rows = result_data.get('rows')
            if isinstance(rows, list):
                print(f"  [OK] EGRUL token flow working -- returned {len(rows)} results")
                return

            add_finding('MEDIUM', 'EGRUL',
                        'EGRUL returned unexpected result response format',
                        'Update parser/audit expectations for current EGRUL JSON schema',
                        diagnostics)
            return

        add_finding('MEDIUM', 'EGRUL',
                    'EGRUL result endpoint did not return a usable response',
                    'Retry later and inspect diagnostics for HTTP status or wait-state loops',
                    diagnostics)
    except requests.Timeout:
        add_finding('HIGH', 'EGRUL', 'EGRUL request timed out',
                    'Increase timeout or add retry logic',
                    diagnostics)
    except requests.RequestException as e:
        add_finding('HIGH', 'EGRUL', f"EGRUL unreachable: {e}",
                    'Check network connectivity to egrul.nalog.ru',
                    diagnostics)

def test_sudact(env):
    print("\n[AGENT 7] Testing sudact.ru...")

    try:
        r = requests.get('https://sudact.ru', timeout=10,
                         headers={'User-Agent': 'Mozilla/5.0'})
        if r.status_code == 200:
            print(f"  [OK] sudact.ru reachable")
        elif r.status_code == 403:
            add_finding('HIGH', 'sudact.ru',
                        'sudact.ru returning 403 -- IP blocked',
                        'Court search via Playwright may fail -- verify Playwright can access')
        else:
            add_finding('MEDIUM', 'sudact.ru',
                        f"sudact.ru returned HTTP {r.status_code}",
                        'Monitor sudact.ru availability')
    except Exception as e:
        add_finding('HIGH', 'sudact.ru', f"sudact.ru unreachable: {e}",
                    'sudact.ru may be down')

def test_leakcheck(env):
    print("\n[AGENT 7] Testing LeakCheck public API...")

    try:
        r = requests.get(
            'https://leakcheck.io/api/public?check=test@test.com',
            timeout=10
        )
        if r.status_code == 200:
            print(f"  [OK] LeakCheck API reachable")
        else:
            add_finding('LOW', 'LeakCheck',
                        f"LeakCheck returned HTTP {r.status_code}",
                        'LeakCheck may have changed API')
    except Exception as e:
        add_finding('LOW', 'LeakCheck', f"LeakCheck unreachable: {e}",
                    'Phone/email breach search will be skipped')

def test_hudsonrock(env):
    print("\n[AGENT 7] Testing HudsonRock API...")

    try:
        r = requests.get(
            'https://cavalier.hudsonrock.com/api/json/v2/osint-tools/search-by-email?email=test@test.com',
            timeout=10
        )
        if r.status_code in (200, 429, 401):
            print(f"  [OK] HudsonRock API reachable (status {r.status_code})")
        else:
            add_finding('LOW', 'HudsonRock',
                        f"HudsonRock returned HTTP {r.status_code}",
                        'Breach search from HudsonRock may not work')
    except Exception as e:
        add_finding('LOW', 'HudsonRock', f"HudsonRock unreachable: {e}",
                    'Breach search will be skipped')

def test_nominatim(env):
    print("\n[AGENT 7] Testing Nominatim geocoding...")

    try:
        r = requests.get(
            'https://nominatim.openstreetmap.org/search',
            params={'q': 'Moscow Russia', 'format': 'json', 'limit': 1},
            headers={'User-Agent': 'SLED-IBP/1.0'},
            timeout=10
        )
        if r.status_code == 200 and r.json():
            print(f"  [OK] Nominatim geocoding working")
        else:
            add_finding('LOW', 'Nominatim',
                        'Nominatim returned empty results',
                        'Geo intelligence map may not show locations')
    except Exception as e:
        add_finding('LOW', 'Nominatim', f"Nominatim unreachable: {e}",
                    'Geo mapping will fall back to hardcoded coords')

def test_opensanctions(env):
    print("\n[AGENT 7] Testing OpenSanctions...")

    api_base = 'https://api.opensanctions.org'
    api_key = get_config_value(
        env, 'OPENSANCTIONS_API_KEY', 'OPEN_SANCTIONS_API_KEY'
    )
    diagnostics = {'credentials_configured': bool(api_key)}

    root_probe = request_probe('GET', f'{api_base}/')
    diagnostics['root'] = root_probe
    if not root_probe.get('ok'):
        add_finding('MEDIUM', 'OpenSanctions',
                    f"OpenSanctions API front door unreachable: {root_probe.get('error_type')}",
                    'Check network connectivity to api.opensanctions.org',
                    diagnostics)
        return
    if root_probe['status_code'] >= 500:
        add_finding('MEDIUM', 'OpenSanctions',
                    f"OpenSanctions API front door returned HTTP {root_probe['status_code']}",
                    'Retry later or check https://status.opensanctions.org/',
                    diagnostics)
        return

    headers = {
        'User-Agent': 'IBP-Agent7/1.0',
        'Accept': 'application/json',
    }
    if api_key:
        lower_key = api_key.lower()
        headers['Authorization'] = (
            api_key
            if lower_key.startswith('apikey ') or lower_key.startswith('bearer ')
            else f'ApiKey {api_key}'
        )

    try:
        r = requests.get(
            f'{api_base}/search/default',
            params={'q': 'test', 'limit': 1},
            headers=headers,
            timeout=10,
        )
        diagnostics['search_status_code'] = r.status_code

        if not api_key:
            if r.status_code == 401:
                add_finding('LOW', 'OpenSanctions',
                            'OpenSanctions API key not configured; remote sanctions screening is in degraded mode',
                            'Set OPENSANCTIONS_API_KEY to enable live OpenSanctions checks, or accept this degraded mode intentionally',
                            diagnostics)
            elif r.status_code == 200:
                print("  [OK] OpenSanctions API reachable without configured credentials")
            else:
                add_finding('LOW', 'OpenSanctions',
                            f"OpenSanctions unauthenticated probe returned HTTP {r.status_code}",
                            'Set OPENSANCTIONS_API_KEY for authenticated checks; inspect endpoint status if degraded mode was not expected',
                            diagnostics)
            return

        if r.status_code == 200:
            print(f"  [OK] OpenSanctions API reachable -- credentials accepted")
        elif r.status_code in (401, 403):
            add_finding('HIGH', 'OpenSanctions',
                        f"OpenSanctions credentials rejected (HTTP {r.status_code})",
                        'Verify OPENSANCTIONS_API_KEY/OPEN_SANCTIONS_API_KEY without printing the secret',
                        diagnostics)
        elif r.status_code == 429:
            add_finding('MEDIUM', 'OpenSanctions',
                        'OpenSanctions rate limited',
                        'Add delays between requests',
                        diagnostics)
        elif r.status_code >= 500:
            add_finding('MEDIUM', 'OpenSanctions',
                        f"OpenSanctions returned HTTP {r.status_code}",
                        'Retry later or check https://status.opensanctions.org/',
                        diagnostics)
        else:
            add_finding('MEDIUM', 'OpenSanctions',
                        f"OpenSanctions returned HTTP {r.status_code}",
                        'Inspect API response/schema and credentials',
                        diagnostics)
    except requests.RequestException as e:
        add_finding('MEDIUM', 'OpenSanctions', f"OpenSanctions unreachable: {e}",
                    'International sanctions check will be skipped',
                    diagnostics)

def test_production_server(env):
    print("\n[AGENT 7] Testing production server health...")

    base_url = (env.get('IBP_PRODUCTION_URL') or 'https://shtirletzsled.ru').strip().rstrip('/')
    health_url = f"{base_url}/health"
    readiness_url = f"{base_url}/ready"
    health_probe = request_probe('GET', health_url)
    readiness_probe = request_probe('GET', readiness_url)

    if health_probe.get('ok') and health_probe['status_code'] == 200:
        if readiness_probe.get('ok') and readiness_probe['status_code'] == 200:
            print(f"  [OK] Production server healthy -- {describe_probe('/health', health_probe)}")
            print(f"  [OK] Production server ready -- {describe_probe('/ready', readiness_probe)}")
            return

        diagnostics = {
            'health': health_probe,
            'readiness': readiness_probe,
        }
        print(f"  [OK] Production server healthy -- {describe_probe('/health', health_probe)}")
        print(f"  [diag] {describe_probe('/ready', readiness_probe)}")

        if readiness_probe.get('ok') and readiness_probe['status_code'] == 503:
            add_finding('HIGH', 'Production Server',
                        '/health passes but /ready reports degraded readiness',
                        production_recommendation(base_url, health_probe, {}, readiness_probe),
                        diagnostics)
            return
        if readiness_probe.get('ok') and readiness_probe['status_code'] == 404:
            add_finding('MEDIUM', 'Production Server',
                        '/ready is not deployed on production',
                        'Redeploy the current code so production exposes separate /health and /ready probes.',
                        diagnostics)
            return
        ready_status = (
            readiness_probe.get('error_type')
            or f"HTTP {readiness_probe.get('status_code')}"
        )
        add_finding('HIGH', 'Production Server',
                    f"/ready returned {ready_status}",
                    production_recommendation(base_url, health_probe, {}, readiness_probe),
                    diagnostics)
        return

    root_probe = request_probe('HEAD', f"{base_url}/")
    diagnostics = {
        'health': health_probe,
        'readiness': readiness_probe,
        'root': root_probe,
    }
    print(f"  [diag] {describe_probe('/health', health_probe)}")
    print(f"  [diag] {describe_probe('/ready', readiness_probe)}")
    print(f"  [diag] {describe_probe('/', root_probe)}")

    if health_probe.get('ok') and health_probe['status_code'] == 502:
        add_finding('CRITICAL', 'Production Server',
                    '502 Bad Gateway -- gunicorn is down or nginx cannot reach it',
                    'Restart the web service from the provider panel; when SSH is available run `systemctl restart ibp` or `docker compose up -d` and inspect upstream logs.',
                    diagnostics)
    elif health_probe.get('ok') and health_probe['status_code'] == 504:
        add_finding('CRITICAL', 'Production Server',
                    '504 Gateway Timeout -- nginx reached an upstream that did not respond',
                    production_recommendation(base_url, health_probe, root_probe, readiness_probe),
                    diagnostics)
    elif not health_probe.get('ok'):
        issue = (
            f"Production /health probe failed: {health_probe.get('error_type')} "
            f"after {health_probe.get('elapsed_ms')}ms"
        )
        add_finding('CRITICAL', 'Production Server',
                    issue,
                    production_recommendation(base_url, health_probe, root_probe, readiness_probe),
                    diagnostics)
    else:
        add_finding('HIGH', 'Production Server',
                    f"/health returned HTTP {health_probe['status_code']}",
                    production_recommendation(base_url, health_probe, root_probe, readiness_probe),
                    diagnostics)

# -- Main --
if __name__ == '__main__':
    print("=" * 70)
    print("AGENT 7: EXTERNAL SERVICE VALIDATOR")
    print("=" * 70)

    env = load_env()

    test_vk_api(env)
    test_egrul(env)
    test_sudact(env)
    test_leakcheck(env)
    test_hudsonrock(env)
    test_nominatim(env)
    test_opensanctions(env)
    test_production_server(env)

    print(f"\nAgent 7 complete: {len(findings)} findings")

    output = PROJECT_ROOT / 'scripts' / 'audit' / 'agent7_results.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, 'w', encoding='utf-8') as f:
        json.dump(findings, f, ensure_ascii=False, indent=2)
