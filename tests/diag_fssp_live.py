#!/usr/bin/env python3
"""
FSSP live diagnostic — run on the production server to identify why
FSSP returns no data for candidates.

Usage (from ~/ibp with venv active):
    python tests/diag_fssp_live.py

Costs: at most 2 FSSP quota requests (1 with DOB, 1 without DOB).
       Quota check (/stat/) is free.

Exit code: 0 = all clear, 1 = failures found.
"""

import json
import os
import sys

import requests

# ── Path setup (so app.* imports work when run directly) ──────────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load .env if present (mirrors how the app boots)
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))
except ImportError:
    pass

# ── Output helpers ─────────────────────────────────────────────────────────────
GREEN  = '\033[92m'
YELLOW = '\033[93m'
RED    = '\033[91m'
BLUE   = '\033[94m'
RESET  = '\033[0m'
BOLD   = '\033[1m'

failures: list[str] = []
warnings: list[str] = []


def section(title: str) -> None:
    print(f'\n{BOLD}{"─" * 62}{RESET}')
    print(f'{BOLD}  {title}{RESET}')
    print(f'{BOLD}{"─" * 62}{RESET}')


def ok(msg: str)   -> None: print(f'  {GREEN}PASS{RESET}  {msg}')
def warn(msg: str) -> None: warnings.append(msg); print(f'  {YELLOW}WARN{RESET}  {msg}')
def fail(msg: str) -> None: failures.append(msg); print(f'  {RED}FAIL{RESET}  {msg}')
def info(msg: str) -> None: print(f'  {BLUE}INFO{RESET}  {msg}')


# ── Check 1: environment variables ────────────────────────────────────────────
section('1. Environment variables')

key = os.environ.get('PARSER_API_KEY', '').strip()
if not key:
    fail('PARSER_API_KEY is not set')
    info('Without this key the app falls back to checko.ru → direct FSSP (CAPTCHA-blocked).')
    info('Dossier will show "Проверка неполная" or falsely-green "Нет".')
else:
    masked = f'{key[:4]}...{key[-4:]}' if len(key) >= 8 else '****'
    ok(f'PARSER_API_KEY is set  ({masked})')

fssp_token = os.environ.get('FSSP_API_TOKEN', '').strip()
if fssp_token:
    ok(f'FSSP_API_TOKEN is set (official FSSP API, optional secondary path)')
else:
    info('FSSP_API_TOKEN not set — optional, parser-api.com is the primary path')


# ── Check 2: quota (free call) ────────────────────────────────────────────────
section('2. parser-api.com quota  (free — does not burn a search request)')

fssp_quota_remaining: int | None = None

if not key:
    info('Skipping — no PARSER_API_KEY')
else:
    try:
        r = requests.get('https://parser-api.com/stat/', params={'key': key}, timeout=15)
        if r.status_code in (401, 403):
            fail(f'PARSER_API_KEY rejected by parser-api.com (HTTP {r.status_code}) — key is wrong or expired')
        elif r.status_code == 200:
            try:
                stat = r.json()
                info(f'Raw /stat/ response:\n{json.dumps(stat, ensure_ascii=False, indent=4)}')
                # Flatten and look for FSSP quota fields
                for k, v in (stat.items() if isinstance(stat, dict) else []):
                    if 'fssp' in k.lower():
                        info(f'FSSP quota field  →  {k}: {v}')
                        if isinstance(v, (int, float)):
                            fssp_quota_remaining = int(v)
                if fssp_quota_remaining is not None:
                    if fssp_quota_remaining <= 0:
                        fail(f'FSSP quota exhausted: {fssp_quota_remaining} requests remaining')
                        fail('This is why searches return no data — the API silently returns empty on 429.')
                    elif fssp_quota_remaining < 10:
                        warn(f'FSSP quota critically low: {fssp_quota_remaining} requests remaining')
                    else:
                        ok(f'FSSP quota OK: {fssp_quota_remaining} requests remaining')
                else:
                    ok('Quota endpoint reachable and key is valid (quota field not found — see raw above)')
            except ValueError:
                warn(f'/stat/ returned non-JSON (HTTP 200): {r.text[:300]}')
        else:
            warn(f'/stat/ returned HTTP {r.status_code}: {r.text[:200]}')
    except requests.Timeout:
        warn('Timeout reaching parser-api.com (/stat/) after 15s')
    except requests.ConnectionError as exc:
        fail(f'Cannot reach parser-api.com: {exc}')


# ── Check 3: live FSSP search WITH date of birth (costs 1 quota request) ─────
section('3. Live FSSP search  WITH date of birth  (costs 1 quota request)')

SHOULD_SKIP_LIVE = not key or (fssp_quota_remaining is not None and fssp_quota_remaining <= 0)

# Generic test name — common enough to exercise the API without targeting anyone.
TEST_LAST   = 'Иванов'
TEST_FIRST  = 'Иван'
TEST_PATRON = 'Иванович'
TEST_DOB    = '1980-06-15'          # YYYY-MM-DD format the service expects

if SHOULD_SKIP_LIVE:
    info('Skipping live search (no key or quota exhausted)')
else:
    info(f'Searching: {TEST_LAST} {TEST_FIRST} {TEST_PATRON}, DOB {TEST_DOB}')
    params_with_dob = {
        'key': key,
        'lastName':   TEST_LAST,
        'firstName':  TEST_FIRST,
        'patronymic': TEST_PATRON,
        'dob':        TEST_DOB,
    }
    try:
        r = requests.get(
            'https://parser-api.com/parser/fssp_api/search_fiz',
            params=params_with_dob,
            timeout=30,
        )
        info(f'HTTP {r.status_code}')
        if r.status_code == 429:
            fail('FSSP quota exhausted (HTTP 429) — this is why searches return empty')
        elif r.status_code in (401, 403):
            fail(f'PARSER_API_KEY rejected during search (HTTP {r.status_code})')
        elif r.status_code == 200:
            try:
                data = r.json()
                done       = data.get('done')
                result_raw = data.get('result') or []
                error_msg  = data.get('error', '')
                info(f'done={done}  result_count={len(result_raw)}  error={error_msg!r}')
                info(f'Full response:\n{json.dumps(data, ensure_ascii=False, indent=4)[:2000]}')
                if done == 1:
                    ok('API returned done=1 — search completed, FSSP is working')
                    if result_raw:
                        ok(f'{len(result_raw)} enforcement proceeding(s) found for test name')
                    else:
                        ok('No proceedings for test name (done=1, result=[]) — that is a valid clean read')
                else:
                    # done=0 is returned for "not found" by parser-api.com
                    if result_raw:
                        ok(f'done={done} but {len(result_raw)} result(s) present — treating as ok')
                    else:
                        info(f'done={done}, no results — API ran but found nothing for test name')
                        ok('Search WITH DOB executed successfully (done≠1 + empty result = clean read)')
            except ValueError:
                fail(f'Response is not JSON: {r.text[:400]}')
        else:
            warn(f'Unexpected HTTP {r.status_code}: {r.text[:300]}')
    except requests.Timeout:
        warn('FSSP search timed out after 30s — parser-api.com may be overloaded')
    except requests.ConnectionError as exc:
        fail(f'Connection error during FSSP search: {exc}')


# ── Check 4: live FSSP search WITHOUT date of birth ───────────────────────────
section('4. Live FSSP search  WITHOUT date of birth  (costs 1 quota request)')
info('This shows what happens when a candidate is submitted without a DOB.')

if SHOULD_SKIP_LIVE:
    info('Skipping live search (no key or quota exhausted)')
else:
    params_no_dob = {
        'key':        key,
        'lastName':   TEST_LAST,
        'firstName':  TEST_FIRST,
        'patronymic': TEST_PATRON,
        # dob intentionally omitted
    }
    info(f'Searching: {TEST_LAST} {TEST_FIRST} {TEST_PATRON}, NO DOB')
    try:
        r = requests.get(
            'https://parser-api.com/parser/fssp_api/search_fiz',
            params=params_no_dob,
            timeout=30,
        )
        info(f'HTTP {r.status_code}')
        try:
            data = r.json()
            done      = data.get('done')
            result_raw = data.get('result') or []
            error_msg  = data.get('error', '')
            info(f'done={done}  result_count={len(result_raw)}  error={error_msg!r}')
            info(f'Full response:\n{json.dumps(data, ensure_ascii=False, indent=4)[:800]}')

            if data.get('error_code') or data.get('error'):
                ok(f'API explicitly rejects missing DOB: error={data.get("error")!r} (code={data.get("error_code")})')
                ok('parser_api.fssp_search_fiz now returns status="skipped" for this case → pipeline falls through to checko.ru')
            elif not result_raw and done != 1:
                warn('Search WITHOUT DOB returned no results (done≠1, result=[])')
                warn('The pipeline maps this to status="empty" → dossier shows green "Нет".')
                warn('This is a FALSE CLEAN if DOB is required but missing.')
            elif result_raw:
                info(f'Search without DOB still returned {len(result_raw)} result(s) — DOB is optional for this name')
        except ValueError:
            info(f'Non-JSON response: {r.text[:300]}')
    except Exception as exc:
        info(f'Search without DOB raised: {exc}')


# ── Check 5: DOB pipeline path (no network) ───────────────────────────────────
section('5. DOB handling in the pipeline  (no network)')

info('In pipeline.py the DOB is extracted as:')
info('    dob_str = date_of_birth.strftime("%Y-%m-%d") if date_of_birth else None')
info('    search_fssp_via_parser_api(full_name, dob_str)')
info('')
info('In fssp_service.search_fssp_via_parser_api():')
info('    raw, status = parser_api.fssp_search_fiz(... dob_iso or "", ...)')
info('')
info('So if the candidate has NO date of birth entered in the form:')
info('  • dob_str = None')
info('  • The API receives dob="" (empty string)')
info('  • The FSSP API may return done=0, result=[]')
info('  • The pipeline maps this to status="empty"')
info('  • The dossier shows green "Нет" — a FALSE CLEAN')
warn('Always enter date of birth when checking candidates via Stirlitz.')

# ── Check 6: import smoke test ────────────────────────────────────────────────
section('6. Import smoke test  (no network)')

try:
    from app.services import parser_api as _pa
    from app.services.candidate.fssp_service import (
        FSSPService,
        search_fssp_via_parser_api,
        _fssp_record_from_parser,
    )
    ok('All FSSP service modules import cleanly')

    # Verify the key reading path is consistent with Check 1
    assert _pa.is_available() == bool(key), 'Key availability mismatch between env and parser_api module'
    ok(f'parser_api.is_available() = {_pa.is_available()} (matches env check)')
except ImportError as exc:
    fail(f'Import failed: {exc}')
except AssertionError as exc:
    fail(str(exc))


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
    print(f'\n  {GREEN}{BOLD}All checks passed — FSSP integration looks healthy.{RESET}')
    print('  If candidates still show "Нет": they are likely genuinely clean,')
    print('  or they were checked without a date of birth (see Check 4 above).')
elif failures:
    print(f'\n  {RED}{BOLD}{len(failures)} failure(s){RESET} — fix these first.')
    sys.exit(1)
else:
    print(f'\n  {YELLOW}{BOLD}{len(warnings)} warning(s){RESET} — review above.')

sys.exit(0)
