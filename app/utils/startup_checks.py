"""
IBP Startup Checks
==================
Validates dependencies and configuration on server boot.
Prints a clear status table. Does NOT block startup on non-critical failures.
"""

import os
from datetime import datetime


def _safe_print(text):
    """Print with fallback for Windows consoles that can't handle Unicode."""
    import sys
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode('ascii', 'replace').decode('ascii'))


def run_startup_checks():
    """Run all startup checks and print status table."""
    _safe_print("\n" + "=" * 58)
    _safe_print(f"  IBP STARTUP CHECKS -- {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    _safe_print("=" * 58)

    checks = [
        check_database,
        check_vk_token,
        check_playwright,
        check_holehe,
        check_telethon,
        check_snoop,
        check_maigret,
        check_sherlock,
        check_opensanctions,
        check_local_security_data,
        check_python,
    ]

    # Use ASCII-safe icons for Windows console compatibility
    icon_map = {'ok': '[OK]', 'warn': '[!!]', 'fail': '[FAIL]'}

    for check_fn in checks:
        try:
            status, msg = check_fn()
            icon = icon_map.get(status, '[??]')
            _safe_print(f"  {icon} {msg}")
        except Exception as e:
            _safe_print(f"  [FAIL] {check_fn.__name__}: Error -- {e}")

    _safe_print("=" * 58 + "\n")


def check_database():
    """Check if database exists and is readable."""
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '..', 'instance', 'ibp.db')
    if os.path.exists(db_path):
        size_kb = os.path.getsize(db_path) / 1024
        try:
            import sqlite3
            conn = sqlite3.connect(db_path)
            cursor = conn.execute("SELECT COUNT(*) FROM candidate_checks")
            count = cursor.fetchone()[0]
            conn.close()
            return 'ok', f'Database: ibp.db ({size_kb:.0f} KB, {count} candidate checks)'
        except Exception as e:
            return 'warn', f'Database: ibp.db exists ({size_kb:.0f} KB) but query failed -- {e}'
    return 'warn', 'Database: ibp.db not found (will be created on first run)'


def check_vk_token():
    """Check VK token validity via vk_token_manager.get_token_status()."""
    from app.utils.vk_token_manager import get_token_status
    from app.utils.logger import mask_token

    result = get_token_status()

    if not result['token_set']:
        return 'warn', 'VK Token: Not set -- set VK_SERVICE_TOKEN in .env'

    token = os.environ.get('VK_SERVICE_TOKEN') or os.environ.get('VK_TOKEN', '')
    masked = mask_token(token) if token else '?'

    if result['valid'] is True:
        return 'ok', f'VK Token: Valid ({masked})'
    if result['valid'] is False:
        return 'fail', f'VK Token: Invalid ({masked}) -- {result["error"]}'
    # valid is None — timeout or unknown error
    return 'warn', f'VK Token: Set ({masked}) -- {result["error"]}'


def check_playwright():
    """Check if Playwright is installed."""
    try:
        from playwright.sync_api import sync_playwright
        return 'ok', 'Playwright: Installed'
    except ImportError:
        return 'warn', 'Playwright: Not installed -- run `pip install playwright && playwright install chromium`'


def check_holehe():
    """Check if Holehe is available."""
    try:
        import holehe
        version = getattr(holehe, '__version__', 'unknown')
        return 'ok', f'Holehe: v{version}'
    except ImportError:
        return 'warn', 'Holehe: Not installed -- run `pip install holehe`'


def check_telethon():
    """Check Telegram session status."""
    try:
        import telethon
        api_id = os.environ.get('TELEGRAM_API_ID')
        if not api_id:
            return 'warn', 'Telethon: Installed but TELEGRAM_API_ID not set'

        # Check session file at canonical location: tg_session/ibp_session.session
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        project_root = os.path.join(project_root, '..')
        session_file = os.path.join(project_root, 'tg_session', 'ibp_session.session')
        session_file = os.path.normpath(session_file)

        if os.path.exists(session_file):
            size_kb = os.path.getsize(session_file) / 1024
            if size_kb < 0.1:
                return 'warn', f'Telethon: Session file corrupt ({size_kb:.1f} KB) -- run: python scripts/auth_telegram.py'
            return 'ok', f'Telethon: Session found ({size_kb:.1f} KB)'
        return 'warn', 'Telethon: No session -- run: python scripts/auth_telegram.py'
    except ImportError:
        return 'warn', 'Telethon: Not installed -- Telegram features disabled'
    except Exception:
        return 'warn', 'Telethon: Installed, session check skipped'


def check_snoop():
    """Check if Snoop is available."""
    osint_dir = os.environ.get('OSINT_TOOLS_DIR')
    paths = []
    if osint_dir:
        paths.append(os.path.join(osint_dir, 'snoop'))
    paths.extend([
        os.path.join(os.path.expanduser('~'), 'osint_tools', 'snoop'),
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '..', 'snoop'),
    ])
    for p in paths:
        if os.path.isdir(p):
            return 'ok', f'Snoop: Found at {p}'
    return 'warn', 'Snoop: Not found -- username enumeration disabled'


def check_maigret():
    """Check if Maigret is available."""
    try:
        from app.services.maigret_search import MaigretSearchService
        svc = MaigretSearchService()
        if svc.available:
            return 'ok', 'Maigret: Available'
        return 'warn', 'Maigret: Not installed -- pip install maigret'
    except Exception:
        return 'warn', 'Maigret: Not installed'


def check_sherlock():
    """Check if Sherlock is available."""
    try:
        from app.services.sherlock_search import SherlockSearchService
        svc = SherlockSearchService()
        if svc.available:
            return 'ok', 'Sherlock: Available'
        return 'warn', 'Sherlock: Not installed -- pip install sherlock-project'
    except Exception:
        return 'warn', 'Sherlock: Not installed'


def check_opensanctions():
    """Check if OpenSanctions API is reachable."""
    try:
        from app.services.candidate.opensanctions_service import OpenSanctionsService
        svc = OpenSanctionsService(timeout=5)
        if svc.is_reachable():
            return 'ok', 'OpenSanctions: API reachable'
        return 'warn', 'OpenSanctions: API unreachable'
    except Exception:
        return 'warn', 'OpenSanctions: Check failed'


def check_local_security_data():
    """Check if local security databases exist."""
    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '..', 'data')
    mvd = os.path.exists(os.path.join(data_dir, 'mvd_wanted.json'))
    ext = os.path.exists(os.path.join(data_dir, 'extremist_list.json'))
    if mvd and ext:
        return 'ok', 'Security data: MVD + Extremist lists present'
    parts = []
    if not mvd:
        parts.append('MVD missing')
    if not ext:
        parts.append('Extremist missing')
    return 'warn', f'Security data: {", ".join(parts)} -- run scripts/update_*.py'


def check_python():
    """Report Python version."""
    import sys
    return 'ok', f'Python: {sys.version.split()[0]}'
