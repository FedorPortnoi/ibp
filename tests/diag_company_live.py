#!/usr/bin/env python3
"""
Company pipeline live diagnostic — run on production server to verify
all external sources for Тип 02 (company / ИП) checks.

Usage (from ~/ibp with venv active):
    python tests/diag_company_live.py

Test subject: ПАО Сбербанк (INN 7707083893) — guaranteed to be in
every Russian registry. Replace TEST_INN below if you need a different one.

Costs: 1 DataNewton request (bankruptcy lookup).
       parser-api.com arbitr + FSSP calls burn 1 quota each.
       dadata.ru call burns 1 of 500/day free tier.

Exit code: 0 = all clear, 1 = failures found.
"""

import json
import os
import sys

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))
except ImportError:
    pass

GREEN  = '\033[92m'
YELLOW = '\033[93m'
RED    = '\033[91m'
BLUE   = '\033[94m'
RESET  = '\033[0m'
BOLD   = '\033[1m'

failures: list[str] = []
warnings: list[str] = []

TEST_INN = '7707083893'   # ПАО Сбербанк — replace if needed
TEST_LABEL = 'ПАО Сбербанк'


def section(title: str) -> None:
    print(f'\n{BOLD}{"─" * 62}{RESET}')
    print(f'{BOLD}  {title}{RESET}')
    print(f'{BOLD}{"─" * 62}{RESET}')


def ok(msg: str)   -> None: print(f'  {GREEN}PASS{RESET}  {msg}')
def warn(msg: str) -> None: warnings.append(msg); print(f'  {YELLOW}WARN{RESET}  {msg}')
def fail(msg: str) -> None: failures.append(msg); print(f'  {RED}FAIL{RESET}  {msg}')
def info(msg: str) -> None: print(f'  {BLUE}INFO{RESET}  {msg}')


# ── Check 1: Environment variables ────────────────────────────────────────────
section('1. Environment variables')

parser_key     = os.environ.get('PARSER_API_KEY', '').strip()
datanewton_key = os.environ.get('DATANEWTON_API_KEY', '').strip()
dadata_key     = os.environ.get('DADATA_API_KEY', '').strip()
anthropic_key  = os.environ.get('ANTHROPIC_API_KEY', '').strip()

def _masked(k: str) -> str:
    return f'{k[:4]}...{k[-4:]}' if len(k) >= 8 else '****'

if parser_key:
    ok(f'PARSER_API_KEY     ({_masked(parser_key)})  — courts + FSSP')
else:
    fail('PARSER_API_KEY not set — courts (kad.arbitr) and FSSP will not run')

if datanewton_key:
    ok(f'DATANEWTON_API_KEY ({_masked(datanewton_key)})  — bankruptcy, risks, tax, contracts, inspections')
else:
    warn('DATANEWTON_API_KEY not set — bankruptcy, risks, tax info, gov contracts, inspections skipped')

if dadata_key:
    ok(f'DADATA_API_KEY     ({_masked(dadata_key)})  — financial data')
else:
    warn('DADATA_API_KEY not set — financial data (revenues, profit, tax system) unavailable')

if anthropic_key:
    ok(f'ANTHROPIC_API_KEY  ({_masked(anthropic_key)})  — AI executive summary')
else:
    warn('ANTHROPIC_API_KEY not set — AI summary will be skipped')


# ── Check 2: parser-api.com quota ─────────────────────────────────────────────
section('2. parser-api.com quota  (free call)')

arbitr_quota = fssp_quota = None

if not parser_key:
    info('Skipping — no PARSER_API_KEY')
else:
    try:
        r = requests.get('https://parser-api.com/stat/', params={'key': parser_key}, timeout=15)
        if r.status_code in (401, 403):
            fail(f'PARSER_API_KEY rejected (HTTP {r.status_code})')
        elif r.status_code == 200:
            try:
                stat = r.json()
                info(f'Raw /stat/ response:\n{json.dumps(stat, ensure_ascii=False, indent=4)}')
                for entry in (stat if isinstance(stat, list) else [stat]):
                    svc = (entry.get('service') or '').lower()
                    remaining = entry.get('month_limit', 0) - entry.get('month_request_count', 0)
                    if 'arbitr' in svc:
                        arbitr_quota = remaining
                    elif 'fssp' in svc:
                        fssp_quota = remaining

                for label, quota in [('arbitr (courts)', arbitr_quota), ('fssp (company)', fssp_quota)]:
                    if quota is None:
                        info(f'{label}: quota field not found in stat response')
                    elif quota <= 0:
                        fail(f'{label}: quota EXHAUSTED ({quota} remaining)')
                    elif quota < 10:
                        warn(f'{label}: quota critically low ({quota} remaining)')
                    else:
                        ok(f'{label}: {quota} requests remaining')
            except ValueError:
                warn(f'/stat/ non-JSON: {r.text[:200]}')
        else:
            warn(f'/stat/ HTTP {r.status_code}: {r.text[:200]}')
    except requests.Timeout:
        warn('Timeout reaching parser-api.com')
    except requests.ConnectionError as exc:
        fail(f'Cannot reach parser-api.com: {exc}')


# ── Check 3: EGRUL lookup (egrul.org — no key, no quota cost) ─────────────────
section(f'3. EGRUL lookup  —  {TEST_LABEL} (INN {TEST_INN})')

try:
    r = requests.get(
        f'https://egrul.org/api/v1/company/{TEST_INN}',
        headers={'Accept': 'application/json', 'User-Agent': 'Stirlitz/1.0'},
        timeout=20,
    )
    info(f'HTTP {r.status_code}')
    if r.status_code == 200:
        try:
            data = r.json()
            name = (data.get('name') or data.get('short_name') or
                    (data.get('data') or {}).get('name') or '')
            info(f'Response keys: {list(data.keys())[:10]}')
            if name:
                ok(f'EGRUL returned company name: {name}')
            else:
                warn(f'EGRUL responded 200 but no name field — check response structure')
                info(f'Response (first 500 chars): {json.dumps(data, ensure_ascii=False)[:500]}')
        except ValueError:
            warn(f'Non-JSON response: {r.text[:300]}')
    elif r.status_code == 429:
        warn('egrul.org rate-limited (100 req/day) — try again tomorrow or use a different source')
    elif r.status_code == 404:
        fail(f'egrul.org returned 404 for INN {TEST_INN} — source may be down')
    else:
        warn(f'egrul.org HTTP {r.status_code}: {r.text[:200]}')
except requests.Timeout:
    warn('Timeout reaching egrul.org (20s)')
except requests.ConnectionError as exc:
    fail(f'Cannot reach egrul.org: {exc}')


# ── Check 4: Courts via reputation.su (no key, should always work) ────────────
section(f'4. Courts  —  reputation.su  (no auth)')

try:
    r = requests.get(
        'https://reputation.su/search',
        params={'query': TEST_INN, 'type': 'inn'},
        headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json, text/html, */*',
        },
        timeout=20,
        allow_redirects=True,
    )
    info(f'HTTP {r.status_code}  content-length={len(r.content)}')
    if r.status_code == 200:
        ok(f'reputation.su reachable (HTTP 200, {len(r.content)} bytes)')
        if TEST_INN in r.text or 'дел' in r.text.lower() or 'case' in r.text.lower():
            ok('Court case data appears to be present in response')
        else:
            info('Response received but no obvious case markers — may be JS-rendered')
    elif r.status_code == 403:
        warn('reputation.su returned 403 — geo-blocked or rate-limited from this IP')
    else:
        warn(f'reputation.su HTTP {r.status_code}')
except requests.Timeout:
    warn('Timeout reaching reputation.su (20s) — may be slow from this server')
except requests.ConnectionError as exc:
    fail(f'Cannot reach reputation.su: {exc}')


# ── Check 5: FSSP company search via parser-api.com (costs 1 quota) ──────────
section(f'5. FSSP company  —  parser-api.com search_ur_by_inn  (1 quota request)')

if not parser_key:
    info('Skipping — no PARSER_API_KEY')
elif fssp_quota is not None and fssp_quota <= 0:
    warn('Skipping — FSSP quota exhausted')
else:
    info(f'Searching FSSP for INN {TEST_INN} ({TEST_LABEL})')
    try:
        r = requests.get(
            'https://parser-api.com/parser/fssp_api/search_ur_by_inn',
            params={'key': parser_key, 'inn': TEST_INN},
            timeout=30,
        )
        info(f'HTTP {r.status_code}')
        if r.status_code == 429:
            fail('FSSP company quota exhausted (429)')
        elif r.status_code in (401, 403):
            fail(f'Auth rejected ({r.status_code}) — check PARSER_API_KEY')
        elif r.status_code in (200, 400):
            try:
                data = r.json()
                done  = data.get('done')
                items = data.get('result') or []
                err   = data.get('error', '')
                info(f'done={done}  result_count={len(items)}  error={err!r}')
                info(f'Full response:\n{json.dumps(data, ensure_ascii=False, indent=4)[:800]}')
                if err or data.get('error_code'):
                    # After our fix, this returns 'skipped' → DataNewton fallback
                    warn(f'API error: {err} (code={data.get("error_code")}) — pipeline falls to DataNewton fallback')
                elif done == 1:
                    ok(f'FSSP company search done=1, {len(items)} proceeding(s)')
                else:
                    ok(f'FSSP company search done={done}, result=[] — clean read (no enforcement proceedings)')
            except ValueError:
                fail(f'Non-JSON response: {r.text[:300]}')
        else:
            warn(f'Unexpected HTTP {r.status_code}: {r.text[:200]}')
    except requests.Timeout:
        warn('Timeout for FSSP company search (30s)')
    except requests.ConnectionError as exc:
        fail(f'Connection error: {exc}')


# ── Check 6: DataNewton — bankruptcy lookup (costs 1 quota) ──────────────────
section(f'6. DataNewton bankruptcy  (costs 1 quota request)')

if not datanewton_key:
    info('Skipping — no DATANEWTON_API_KEY')
else:
    info(f'Looking up bankruptcy for INN {TEST_INN} ({TEST_LABEL})')
    try:
        r = requests.get(
            f'https://api.datanewton.ru/v1/bankruptcy/',
            params={'inn': TEST_INN, 'key': datanewton_key},
            headers={'Accept': 'application/json', 'User-Agent': 'Stirlitz/1.0'},
            timeout=20,
        )
        info(f'HTTP {r.status_code}')
        if r.status_code == 429:
            fail('DataNewton quota exhausted (429) — bankruptcy, risks, tax, contracts all affected')
        elif r.status_code in (401, 403):
            fail(f'DataNewton auth rejected ({r.status_code}) — check DATANEWTON_API_KEY')
        elif r.status_code == 200:
            try:
                data = r.json()
                info(f'Response: {json.dumps(data, ensure_ascii=False, indent=4)[:600]}')
                ok('DataNewton reachable and key is valid')
            except ValueError:
                warn(f'Non-JSON 200 response: {r.text[:200]}')
        elif r.status_code == 404:
            ok('DataNewton reachable — 404 = no bankruptcy record for this INN (expected)')
        else:
            warn(f'DataNewton HTTP {r.status_code}: {r.text[:200]}')
    except requests.Timeout:
        warn('Timeout reaching DataNewton (20s)')
    except requests.ConnectionError as exc:
        fail(f'Cannot reach DataNewton: {exc}')


# ── Check 7: dadata.ru — financial lookup (costs 1 of 500/day) ───────────────
section(f'7. dadata.ru financial data  (costs 1 of 500 free daily requests)')

if not dadata_key:
    info('Skipping — no DADATA_API_KEY')
else:
    info(f'Looking up financial data for INN {TEST_INN} ({TEST_LABEL})')
    try:
        r = requests.post(
            'https://suggestions.dadata.ru/suggestions/api/4_1/rs/findById/party',
            json={'query': TEST_INN, 'count': 1},
            headers={
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'Authorization': f'Token {dadata_key}',
            },
            timeout=15,
        )
        info(f'HTTP {r.status_code}')
        if r.status_code == 401:
            fail('dadata.ru auth rejected (401) — check DADATA_API_KEY')
        elif r.status_code == 429:
            warn('dadata.ru rate-limited (429) — 500/day quota may be exhausted')
        elif r.status_code == 200:
            try:
                data = r.json()
                suggestions = data.get('suggestions') or []
                if suggestions:
                    s = suggestions[0]
                    name = s.get('value', '')
                    inn_resp = (s.get('data') or {}).get('inn', '')
                    ok(f'dadata returned: {name} (INN {inn_resp})')
                    ok('dadata.ru reachable and key is valid')
                else:
                    warn(f'dadata returned empty suggestions for INN {TEST_INN}')
            except ValueError:
                warn(f'Non-JSON response: {r.text[:200]}')
        else:
            warn(f'dadata.ru HTTP {r.status_code}: {r.text[:200]}')
    except requests.Timeout:
        warn('Timeout reaching dadata.ru (15s)')
    except requests.ConnectionError as exc:
        fail(f'Cannot reach dadata.ru: {exc}')


# ── Check 8: Import smoke test ────────────────────────────────────────────────
section('8. Import smoke test  (no network)')

try:
    from app.services.company.egrul_service     import EGRULService
    from app.services.company.company_court_service import CompanyCourtSearch
    from app.services.company.datanewton_service import (
        is_available as dn_available, lookup_bankruptcy, lookup_risks,
        lookup_tax_info, lookup_blocked_accounts, lookup_gov_contracts,
    )
    from app.services.company.financial_service  import FinancialService
    from app.services.parser_api                 import fssp_search_ur, is_available as pa_available
    ok('All company pipeline service modules import cleanly')

    ok(f'parser_api.is_available()     = {pa_available()}  (PARSER_API_KEY)')
    ok(f'datanewton.is_available()     = {dn_available()}  (DATANEWTON_API_KEY)')
except ImportError as exc:
    fail(f'Import failed: {exc}')


# ── Summary ────────────────────────────────────────────────────────────────────
section('Summary')

if failures:
    print(f'\n{RED}{BOLD}FAILURES:{RESET}')
    for f in failures:
        print(f'  {RED}✗{RESET} {f}')
if warnings:
    print(f'\n{YELLOW}{BOLD}WARNINGS:{RESET}')
    for w in warnings:
        print(f'  {YELLOW}!{RESET} {w}')

if not failures and not warnings:
    print(f'\n  {GREEN}{BOLD}All checks passed — company pipeline looks healthy.{RESET}')
elif failures:
    print(f'\n  {RED}{BOLD}{len(failures)} failure(s){RESET} — fix these first.')
    sys.exit(1)
else:
    print(f'\n  {YELLOW}{BOLD}{len(warnings)} warning(s){RESET} — review above.')

sys.exit(0)
