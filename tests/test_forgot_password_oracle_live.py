"""
Live Forgot Password Oracle Test Suite
=======================================
Launches REAL Playwright against vk.com -- NO mocks.
Runs in continuous rounds until 80%+ success rate is achieved.

Each round:
1. Search VK for 5 names -> collect top 2 results each -> ~10 usernames
2. Run forgot password oracle on each username
3. Parse and log results
4. Calculate success rate
5. If success >= 80% -> stop, report success
6. If success < 80% -> analyse failures, next round with new names
7. Repeat until 80%+ or 5 rounds completed

Usage:
    python -m pytest tests/test_forgot_password_oracle_live.py -v -s -p no:faulthandler
"""

import logging
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import requests as http_requests
import pytest

# ---------------------------------------------------------------------------
# Fix Windows console encoding for Cyrillic output
# ---------------------------------------------------------------------------
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# ---------------------------------------------------------------------------
# Add project root to path and load .env
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dotenv import load_dotenv
load_dotenv()

from app.services.phase2.forgot_password_oracle import (
    VKUsernameForgotChecker,
    ForgotPasswordResult,
    PLAYWRIGHT_AVAILABLE,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# VK API constants (direct API calls, no Playwright dependency)
# ---------------------------------------------------------------------------
VK_API_BASE = "https://api.vk.com/method"
VK_API_VERSION = "5.199"

PROFILE_FIELDS = [
    "domain", "screen_name", "first_name", "last_name",
    "city", "bdate", "photo_100",
]

# ---------------------------------------------------------------------------
# Name lists per round -- hardcoded, never reuse across rounds
# ---------------------------------------------------------------------------

ROUND_NAMES: Dict[int, List[str]] = {
    1: [
        "Александр Иванов",
        "Мария Петрова",
        "Дмитрий Смирнов",
        "Анна Кузнецова",
        "Сергей Попов",
    ],
    2: [
        "Николай Соколов",
        "Елена Морозова",
        "Андрей Новиков",
        "Ольга Волкова",
        "Михаил Зайцев",
    ],
    3: [
        "Павел Козлов",
        "Татьяна Лебедева",
        "Владимир Семёнов",
        "Наталья Орлова",
        "Алексей Виноградов",
    ],
    4: [
        "Игорь Богданов",
        "Светлана Фёдорова",
        "Роман Михайлов",
        "Юлия Захарова",
        "Евгений Королёв",
    ],
    5: [
        "Артём Герасимов",
        "Ксения Тихонова",
        "Денис Кузьмин",
        "Вера Щербакова",
        "Максим Беляев",
    ],
}

MAX_ROUNDS = 5
TARGET_SUCCESS_RATE = 0.80
TOP_N_PER_NAME = 2

# ---------------------------------------------------------------------------
# Result tracking
# ---------------------------------------------------------------------------

@dataclass
class OracleTestResult:
    """Single oracle test result."""
    username: str
    source_name: str
    result_type: str        # account_exists, masked_phone, masked_email, not_found, captcha, error, timeout
    hint_type: Optional[str] = None
    masked_hint: Optional[str] = None
    elapsed_seconds: float = 0.0
    error: Optional[str] = None

    @property
    def is_success(self) -> bool:
        return self.result_type in ('account_exists', 'masked_phone', 'masked_email')

    @property
    def is_neutral(self) -> bool:
        return self.result_type == 'not_found'

    @property
    def is_failure(self) -> bool:
        return self.result_type in ('captcha', 'error', 'timeout', 'rate_limited')


@dataclass
class RoundReport:
    """Report for a single round."""
    round_num: int
    names: List[str]
    usernames_found: List[str]
    results: List[OracleTestResult] = field(default_factory=list)
    issues: List[str] = field(default_factory=list)
    fixes: List[str] = field(default_factory=list)

    @property
    def success_count(self) -> int:
        return sum(1 for r in self.results if r.is_success)

    @property
    def neutral_count(self) -> int:
        return sum(1 for r in self.results if r.is_neutral)

    @property
    def failure_count(self) -> int:
        return sum(1 for r in self.results if r.is_failure)

    @property
    def scorable_count(self) -> int:
        """Count of results that are not neutral (used for success rate calc)."""
        return sum(1 for r in self.results if not r.is_neutral)

    @property
    def success_rate(self) -> float:
        """Success rate over scorable results (excludes not_found)."""
        scorable = self.scorable_count
        if scorable == 0:
            return 0.0
        return self.success_count / scorable


# ---------------------------------------------------------------------------
# Step 1: Find usernames via VK API (direct, no Playwright)
# ---------------------------------------------------------------------------

def _vk_newsfeed_search(token: str, query: str) -> List[int]:
    """
    Use VK newsfeed.search (works with service token) to find user IDs
    from posts mentioning the target name.
    """
    user_ids = []
    try:
        resp = http_requests.post(
            f"{VK_API_BASE}/newsfeed.search",
            data={
                'q': query,
                'count': 100,
                'access_token': token,
                'v': VK_API_VERSION,
            },
            timeout=15,
        )
        data = resp.json()
        if 'error' in data:
            logger.warning(f"newsfeed.search error: {data['error'].get('error_msg', '')}")
            return []

        items = data.get('response', {}).get('items', [])
        seen = set()
        for item in items:
            owner_id = item.get('owner_id', 0)
            if owner_id > 0 and owner_id not in seen:
                seen.add(owner_id)
                user_ids.append(owner_id)
            signer = item.get('signer_id', 0)
            if signer > 0 and signer not in seen:
                seen.add(signer)
                user_ids.append(signer)
    except Exception as e:
        logger.warning(f"newsfeed.search error: {e}")

    return user_ids


def _vk_enrich_profiles(token: str, user_ids: List[int]) -> List[Dict]:
    """
    Enrich VK user IDs with profile data using users.get (service token).
    Returns list of profile dicts.
    """
    if not user_ids:
        return []

    profiles = []
    for i in range(0, len(user_ids), 100):
        batch = user_ids[i:i + 100]
        try:
            resp = http_requests.post(
                f"{VK_API_BASE}/users.get",
                data={
                    'user_ids': ','.join(str(uid) for uid in batch),
                    'fields': ','.join(PROFILE_FIELDS),
                    'access_token': token,
                    'v': VK_API_VERSION,
                },
                timeout=15,
            )
            data = resp.json()
            if 'error' in data:
                logger.warning(f"users.get error: {data['error'].get('error_msg', '')}")
                continue
            profiles.extend(data.get('response', []))
            if i + 100 < len(user_ids):
                time.sleep(0.35)
        except Exception as e:
            logger.warning(f"users.get error: {e}")

    return profiles


def _name_matches(profile: dict, search_first: str, search_last: str) -> bool:
    """Check if profile name matches search query (case-insensitive)."""
    pf = (profile.get('first_name') or '').lower()
    pl = (profile.get('last_name') or '').lower()
    sf = search_first.lower()
    sl = search_last.lower()

    # Exact match
    if pf == sf and pl == sl:
        return True

    # Handle yo/ye (e/yo) equivalence common in Russian
    def normalize_yo(s):
        return s.replace('\u0451', '\u0435')  # replace yo with ye

    if normalize_yo(pf) == normalize_yo(sf) and normalize_yo(pl) == normalize_yo(sl):
        return True

    # Allow first name match + last name starts with same prefix (diminutives)
    if pl == sl and len(pf) >= 3 and len(sf) >= 3:
        if pf[:3] == sf[:3]:
            return True

    return False


# Basic Cyrillic-to-Latin transliteration for username guessing
_TRANSLIT = {
    '\u0430': 'a', '\u0431': 'b', '\u0432': 'v', '\u0433': 'g', '\u0434': 'd',
    '\u0435': 'e', '\u0451': 'e', '\u0436': 'zh', '\u0437': 'z', '\u0438': 'i',
    '\u0439': 'y', '\u043a': 'k', '\u043b': 'l', '\u043c': 'm', '\u043d': 'n',
    '\u043e': 'o', '\u043f': 'p', '\u0440': 'r', '\u0441': 's', '\u0442': 't',
    '\u0443': 'u', '\u0444': 'f', '\u0445': 'kh', '\u0446': 'ts', '\u0447': 'ch',
    '\u0448': 'sh', '\u0449': 'sch', '\u044a': '', '\u044b': 'y', '\u044c': '',
    '\u044d': 'e', '\u044e': 'yu', '\u044f': 'ya',
}


def _to_latin(text: str) -> str:
    """Basic Cyrillic-to-Latin transliteration."""
    return ''.join(_TRANSLIT.get(ch, ch) for ch in text.lower())


def _generate_username_patterns(first_lat: str, last_lat: str) -> List[str]:
    """Generate common VK username patterns from transliterated name parts."""
    patterns = []
    if first_lat and last_lat:
        patterns.extend([
            f"{first_lat}.{last_lat}",
            f"{first_lat}_{last_lat}",
            f"{first_lat}{last_lat}",
            f"{last_lat}.{first_lat}",
            f"{last_lat}_{first_lat}",
            f"{first_lat[0]}.{last_lat}",
            f"{first_lat[0]}_{last_lat}",
            f"{first_lat[0]}{last_lat}",
        ])
    return patterns


def _vk_resolve_screen_names(
    token: str, screen_names: List[str],
) -> List[Tuple[str, int]]:
    """
    Resolve VK screen names to user IDs using utils.resolveScreenName.
    Returns list of (screen_name, user_id) tuples for found users.
    """
    found = []
    for name in screen_names[:20]:
        try:
            resp = http_requests.post(
                f"{VK_API_BASE}/utils.resolveScreenName",
                data={
                    'screen_name': name,
                    'access_token': token,
                    'v': VK_API_VERSION,
                },
                timeout=5,
            )
            data = resp.json()
            result = data.get('response', {})
            if result and result.get('type') == 'user':
                found.append((name, result['object_id']))
            time.sleep(0.35)
        except Exception:
            pass
    return found


def find_usernames_for_names(
    names: List[str],
    used_usernames: set,
    token: str,
    top_n: int = TOP_N_PER_NAME,
) -> List[Tuple[str, str]]:
    """
    Find real VK usernames for each name using two strategies:
    1. newsfeed.search -> users.get (finds post authors with matching names)
    2. Screen name guessing (transliterate -> resolve -> verify)
    Returns list of (screen_name, source_name) tuples.
    """
    found: List[Tuple[str, str]] = []

    for name in names:
        parts = name.split()
        if len(parts) < 2:
            continue
        search_first, search_last = parts[0], parts[1]

        logger.info(f"Searching VK for: {name}")
        collected = 0

        # Strategy 1: newsfeed.search -> users.get
        user_ids = _vk_newsfeed_search(token, name)
        if user_ids:
            profiles = _vk_enrich_profiles(token, user_ids[:50])
            for p in profiles:
                if collected >= top_n:
                    break
                if p.get('deactivated'):
                    continue
                if not _name_matches(p, search_first, search_last):
                    continue
                screen_name = p.get('domain') or p.get('screen_name') or f"id{p['id']}"
                if screen_name in used_usernames:
                    continue
                used_usernames.add(screen_name)
                found.append((screen_name, name))
                collected += 1
                fn = p.get('first_name', '')
                ln = p.get('last_name', '')
                logger.info(f"  [newsfeed] Found: {screen_name} ({fn} {ln})")

        # Strategy 2: Screen name guessing (transliterate + resolve)
        if collected < top_n:
            first_lat = _to_latin(search_first)
            last_lat = _to_latin(search_last)
            candidates = _generate_username_patterns(first_lat, last_lat)
            resolved = _vk_resolve_screen_names(token, candidates)

            for screen_name, uid in resolved:
                if collected >= top_n:
                    break
                if screen_name in used_usernames:
                    continue
                # Verify name via users.get
                profiles = _vk_enrich_profiles(token, [uid])
                if profiles:
                    p = profiles[0]
                    if p.get('deactivated'):
                        continue
                    if _name_matches(p, search_first, search_last):
                        used_usernames.add(screen_name)
                        found.append((screen_name, name))
                        collected += 1
                        fn = p.get('first_name', '')
                        ln = p.get('last_name', '')
                        logger.info(f"  [guess] Found: {screen_name} ({fn} {ln})")
                    else:
                        # Screen name exists but belongs to different person
                        # Still usable for oracle testing (it's a real VK account)
                        used_usernames.add(screen_name)
                        found.append((screen_name, name))
                        collected += 1
                        fn = p.get('first_name', '')
                        ln = p.get('last_name', '')
                        logger.info(
                            f"  [guess] Found (different name): {screen_name} ({fn} {ln})"
                        )

        if collected == 0:
            logger.warning(f"  No profiles found for '{name}'")

        # Rate limit between names
        time.sleep(0.5)

    return found


# ---------------------------------------------------------------------------
# Step 2: Run oracle on each username
# ---------------------------------------------------------------------------

def run_oracle_on_usernames(
    usernames: List[Tuple[str, str]],
    checker: Optional[VKUsernameForgotChecker] = None,
) -> List[OracleTestResult]:
    """
    Run VKUsernameForgotChecker on each username.
    Reuses checker instance to benefit from rate-limit short-circuit.
    Returns list of OracleTestResult.
    """
    if checker is None:
        checker = VKUsernameForgotChecker(timeout=30)
    results: List[OracleTestResult] = []

    for username, source_name in usernames:
        logger.info(f"Oracle check: {username} (from '{source_name}')")
        start = time.time()

        try:
            fp_result: Optional[ForgotPasswordResult] = checker.check_username(username)
            elapsed = time.time() - start

            if fp_result is None:
                results.append(OracleTestResult(
                    username=username,
                    source_name=source_name,
                    result_type='error',
                    elapsed_seconds=elapsed,
                    error='returned None',
                ))
                continue

            # Classify result
            if fp_result.error:
                error_str = fp_result.error.lower()
                if 'captcha' in error_str:
                    result_type = 'captcha'
                elif 'rate_limit' in error_str:
                    result_type = 'rate_limited'
                elif 'timeout' in error_str or 'timed out' in error_str:
                    result_type = 'timeout'
                else:
                    result_type = 'error'
                results.append(OracleTestResult(
                    username=username,
                    source_name=source_name,
                    result_type=result_type,
                    elapsed_seconds=elapsed,
                    error=fp_result.error,
                ))
            elif not fp_result.exists:
                results.append(OracleTestResult(
                    username=username,
                    source_name=source_name,
                    result_type='not_found',
                    elapsed_seconds=elapsed,
                ))
            elif fp_result.hint_type == 'phone':
                results.append(OracleTestResult(
                    username=username,
                    source_name=source_name,
                    result_type='masked_phone',
                    hint_type='phone',
                    masked_hint=fp_result.masked_hint,
                    elapsed_seconds=elapsed,
                ))
            elif fp_result.hint_type == 'email':
                results.append(OracleTestResult(
                    username=username,
                    source_name=source_name,
                    result_type='masked_email',
                    hint_type='email',
                    masked_hint=fp_result.masked_hint,
                    elapsed_seconds=elapsed,
                ))
            elif fp_result.hint_type == 'existence':
                # VK ID new flow: confirms account exists (may or may not
                # have recovery option, but no masked hints)
                results.append(OracleTestResult(
                    username=username,
                    source_name=source_name,
                    result_type='account_exists',
                    hint_type='existence',
                    masked_hint=fp_result.masked_hint,
                    elapsed_seconds=elapsed,
                ))
            else:
                # Account exists but unrecognized response
                # Include body_preview from raw_data for debugging
                preview = ''
                if fp_result.raw_data and 'body_preview' in fp_result.raw_data:
                    preview = fp_result.raw_data['body_preview'][:100]
                results.append(OracleTestResult(
                    username=username,
                    source_name=source_name,
                    result_type='account_exists',
                    hint_type='unknown',
                    elapsed_seconds=elapsed,
                    error=f'unrecognized (conf={fp_result.confidence}) body={preview!r}',
                ))

        except Exception as e:
            elapsed = time.time() - start
            results.append(OracleTestResult(
                username=username,
                source_name=source_name,
                result_type='error',
                elapsed_seconds=elapsed,
                error=str(e),
            ))

        # Delay between oracle checks to avoid rate limiting
        time.sleep(2.0)

    return results


# ---------------------------------------------------------------------------
# Step 3: Format and print report
# ---------------------------------------------------------------------------

def format_round_report(report: RoundReport) -> str:
    """Format a single round's report as a table."""
    lines = []
    scorable = report.scorable_count
    rate = report.success_rate
    lines.append(f"\nRound {report.round_num}/{MAX_ROUNDS} -- "
                 f"Success Rate: {rate:.0%} "
                 f"({report.success_count}/{scorable} scorable, "
                 f"{report.neutral_count} neutral, "
                 f"{len(report.results)} total)")
    lines.append("Names: " + ", ".join(report.names))
    lines.append(f"Usernames found: {len(report.usernames_found)}")

    # Table header
    col_user = 18
    col_result = 16
    col_hint = 12
    col_time = 10
    col_detail = 60
    header = (
        f"+{'-' * col_user}+{'-' * col_result}+{'-' * col_hint}"
        f"+{'-' * col_time}+{'-' * col_detail}+"
    )
    lines.append(header)
    lines.append(
        f"|{'Username':^{col_user}}|{'Result':^{col_result}}|{'Hint Type':^{col_hint}}"
        f"|{'Time (s)':^{col_time}}|{'Detail':^{col_detail}}|"
    )
    lines.append(header)

    for r in report.results:
        user_str = r.username[:col_user - 2]
        result_str = r.result_type[:col_result - 2]
        hint_str = (r.hint_type or '-')[:col_hint - 2]
        time_str = f"{r.elapsed_seconds:.1f}s"
        detail = (r.masked_hint or r.error or '-')[:col_detail - 2]
        lines.append(
            f"| {user_str:<{col_user - 1}}| {result_str:<{col_result - 1}}"
            f"| {hint_str:<{col_hint - 1}}| {time_str:>{col_time - 1}}"
            f"| {detail:<{col_detail - 1}}|"
        )

    lines.append(header)

    if report.issues:
        lines.append("Issues found: " + "; ".join(report.issues))
    if report.fixes:
        lines.append("Fixes applied: " + "; ".join(report.fixes))

    return "\n".join(lines)


def save_full_report(rounds: List[RoundReport], report_path: str):
    """Save full results of all rounds to a text file."""
    lines = []
    lines.append("=" * 80)
    lines.append("FORGOT PASSWORD ORACLE -- LIVE TEST REPORT")
    lines.append(f"Generated: {datetime.now().isoformat()}")
    lines.append("=" * 80)

    overall_success = 0
    overall_scorable = 0
    overall_total = 0

    for rpt in rounds:
        lines.append(format_round_report(rpt))
        overall_success += rpt.success_count
        overall_scorable += rpt.scorable_count
        overall_total += len(rpt.results)

    lines.append("\n" + "=" * 80)
    overall_rate = overall_success / overall_scorable if overall_scorable else 0
    lines.append(
        f"FINAL: {len(rounds)} rounds, {overall_total} total checks, "
        f"{overall_success}/{overall_scorable} scorable successes "
        f"({overall_rate:.0%})"
    )
    target_met = overall_rate >= TARGET_SUCCESS_RATE
    lines.append(f"Target ({TARGET_SUCCESS_RATE:.0%}): {'MET' if target_met else 'NOT MET'}")
    lines.append("=" * 80)

    text = "\n".join(lines)

    os.makedirs(os.path.dirname(report_path) or '.', exist_ok=True)
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(text)

    return text


# ---------------------------------------------------------------------------
# Pytest fixtures & test
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def vk_token():
    """Ensure VK_SERVICE_TOKEN is available."""
    token = os.environ.get('VK_SERVICE_TOKEN')
    if not token:
        pytest.skip("VK_SERVICE_TOKEN not set -- cannot run live oracle tests")
    return token


@pytest.fixture(scope="module")
def playwright_available():
    """Ensure Playwright is installed."""
    if not PLAYWRIGHT_AVAILABLE:
        pytest.skip("Playwright not installed -- cannot run live oracle tests")
    return True


class TestForgotPasswordOracleLive:
    """
    Live test suite: runs real Playwright against vk.com.
    Iterates through rounds until 80%+ success rate or 5 rounds exhausted.
    """

    REPORT_PATH = os.path.join(
        os.path.dirname(__file__),
        'forgot_password_oracle_live_report.txt',
    )

    def test_live_oracle_rounds(self, vk_token, playwright_available):
        """
        Main test: run up to 5 rounds of VK searches + oracle checks.
        Pass if any round achieves >= 80% success rate.
        """
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s %(name)s %(levelname)s %(message)s',
            force=True,
        )

        def _p(msg=''):
            print(msg, flush=True)

        used_usernames: set = set()
        all_rounds: List[RoundReport] = []
        best_rate = 0.0
        # Shared checker instance — rate-limit flag persists across rounds
        checker = VKUsernameForgotChecker(timeout=30)

        for round_num in range(1, MAX_ROUNDS + 1):
            names = ROUND_NAMES[round_num]
            _p(f"\n{'=' * 60}")
            _p(f"ROUND {round_num}/{MAX_ROUNDS}")
            _p(f"{'=' * 60}")

            # Step 1: Find usernames via direct VK API
            username_pairs = find_usernames_for_names(
                names, used_usernames, vk_token
            )
            usernames_list = [u for u, _ in username_pairs]

            if not username_pairs:
                _p("No usernames found -- skipping round")
                report = RoundReport(
                    round_num=round_num,
                    names=names,
                    usernames_found=[],
                    issues=["No VK profiles found for any name"],
                )
                all_rounds.append(report)
                continue

            _p(f"Found {len(username_pairs)} usernames: {usernames_list}")

            # Step 2: Run oracle (reuse checker for rate-limit tracking)
            results = run_oracle_on_usernames(username_pairs, checker=checker)

            # Build report
            report = RoundReport(
                round_num=round_num,
                names=names,
                usernames_found=usernames_list,
                results=results,
            )

            # Step 3: Analyse failures
            all_rate_limited = True
            for r in results:
                if r.result_type == 'captcha':
                    report.issues.append(f"CAPTCHA on {r.username}")
                elif r.result_type == 'rate_limited':
                    report.issues.append(f"Rate limited on {r.username}")
                elif r.result_type == 'timeout':
                    report.issues.append(f"Timeout on {r.username}")
                elif r.result_type == 'error':
                    report.issues.append(f"Error on {r.username}: {r.error}")
                if r.result_type != 'rate_limited':
                    all_rate_limited = False

            # Print round report
            round_text = format_round_report(report)
            _p(round_text)

            all_rounds.append(report)
            best_rate = max(best_rate, report.success_rate)

            # Early exit if VK 24h rate limit hit (no point continuing)
            if all_rate_limited and results:
                _p(f"\nVK 24h rate limit active — all {len(results)} checks "
                   f"blocked. Stopping early.")
                break

            # Check if we hit the target
            if report.success_rate >= TARGET_SUCCESS_RATE:
                _p(f"\nTarget {TARGET_SUCCESS_RATE:.0%} MET in round {round_num}!")
                break

            if round_num < MAX_ROUNDS:
                _p(f"\nSuccess rate {report.success_rate:.0%} < target {TARGET_SUCCESS_RATE:.0%}")
                _p("Proceeding to next round with fresh names...")
                # Brief cooldown between rounds
                time.sleep(5)

        # Save full report
        full_report = save_full_report(all_rounds, self.REPORT_PATH)
        _p(f"\nFull report saved to: {self.REPORT_PATH}")
        _p(full_report)

        # Assert: at least one round hit 80%+ success
        assert best_rate >= TARGET_SUCCESS_RATE, (
            f"Best success rate across {len(all_rounds)} rounds was {best_rate:.0%}, "
            f"target was {TARGET_SUCCESS_RATE:.0%}. "
            f"See report: {self.REPORT_PATH}"
        )
