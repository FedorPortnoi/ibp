"""
Sherlock Integration for IBP
==============================
Wraps Sherlock for username enumeration across 400+ sites.
Sherlock complements Snoop and Maigret with different site coverage.

Sherlock can be installed as:
- pip package: `pip install sherlock-project`
- Local tool at OSINT_TOOLS_DIR/sherlock/

Usage:
    from app.services.sherlock_search import SherlockSearchService

    svc = SherlockSearchService()
    if svc.available:
        results = svc.search_username("username")
        found = svc.get_found_profiles(results)
"""

import json
import logging
import os
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


def _resolve_sherlock() -> Optional[str]:
    """
    Resolve sherlock executable.
    Priority: pip-installed module > OSINT_TOOLS_DIR > ~/osint_tools/sherlock
    """
    # 1. pip-installed
    try:
        result = subprocess.run(
            ['sherlock', '--version'],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            return 'cli'
    except Exception:
        pass

    # 2. Python module
    try:
        result = subprocess.run(
            ['python', '-m', 'sherlock_project', '--version'],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            return 'module'
    except Exception:
        pass

    # 3. OSINT_TOOLS_DIR
    osint_dir = os.environ.get('OSINT_TOOLS_DIR')
    if osint_dir:
        candidate = Path(osint_dir) / 'sherlock'
        if (candidate / 'sherlock.py').exists():
            return str(candidate / 'sherlock.py')
        # sherlock_project package layout
        main = candidate / 'sherlock_project' / '__main__.py'
        if main.exists():
            return str(main)

    # 4. Home directory
    home_candidate = Path.home() / 'osint_tools' / 'sherlock'
    if (home_candidate / 'sherlock.py').exists():
        return str(home_candidate / 'sherlock.py')

    return None


class SherlockSearchService:
    """
    Wrapper for Sherlock username search tool.

    Sherlock searches 400+ sites for username matches.
    Output is parsed from JSON or stdout.
    """

    def __init__(self):
        self._sherlock_path = _resolve_sherlock()
        self._available = None

    @property
    def available(self) -> bool:
        """Check if Sherlock is installed and can be executed."""
        if self._available is not None:
            return self._available

        self._available = self._sherlock_path is not None
        if not self._available:
            logger.info("Sherlock not available")

        return self._available

    def search_username(
        self,
        username: str,
        timeout: int = 180,
    ) -> List[Dict]:
        """
        Search for username across 400+ sites using Sherlock.

        Args:
            username: Username to search for
            timeout: Max seconds (default 3 min)

        Returns:
            List of dicts with keys: platform, url, status, confidence, source
        """
        if not self.available:
            return []

        if not username or len(username) < 2:
            return []

        username = username.strip()
        results = []

        try:
            import tempfile
            with tempfile.TemporaryDirectory() as tmpdir:
                output_file = Path(tmpdir) / f'{username}.json'

                # Build command
                if self._sherlock_path == 'cli':
                    cmd = ['sherlock']
                elif self._sherlock_path == 'module':
                    cmd = ['python', '-m', 'sherlock_project']
                else:
                    cmd = ['python', self._sherlock_path]

                cmd.extend([
                    username,
                    '--output', str(Path(tmpdir) / username),
                    '--folderoutput', tmpdir,
                    '--json', str(output_file),
                    '--no-color',
                    '--timeout', '10',
                ])

                env = os.environ.copy()
                env['PYTHONIOENCODING'] = 'utf-8'

                logger.info(f"Running Sherlock for '{username}'")

                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    env=env,
                    encoding='utf-8',
                    errors='replace',
                )

                # Parse JSON output
                if output_file.exists():
                    results = self._parse_json_output(output_file)
                elif proc.stdout:
                    results = self._parse_stdout(proc.stdout)

        except subprocess.TimeoutExpired:
            logger.warning(f"Sherlock timed out after {timeout}s for '{username}'")
        except Exception as e:
            logger.error(f"Sherlock search failed: {e}")

        found_count = len([r for r in results if r.get('status') == 'found'])
        logger.info(f"Sherlock found {found_count} profiles for '{username}'")
        return results

    def _parse_json_output(self, json_path: Path) -> List[Dict]:
        """Parse Sherlock JSON output file."""
        results = []
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            if isinstance(data, dict):
                for site_name, info in data.items():
                    if isinstance(info, dict):
                        status_raw = (info.get('status', '') or '').lower()
                        url = info.get('url_user', info.get('url', ''))
                        is_found = status_raw in ('claimed', 'found') or bool(url)
                        results.append({
                            'platform': site_name,
                            'url': url,
                            'status': 'found' if is_found else 'not_found',
                            'country': '',
                            'http_status': str(info.get('http_status', '')),
                            'response_time': float(info.get('response_time_s', 0)),
                            'confidence': 0.70 if is_found else 0.0,
                            'source': 'sherlock',
                        })
        except Exception as e:
            logger.error(f"Failed to parse Sherlock JSON: {e}")
        return results

    def _parse_stdout(self, stdout: str) -> List[Dict]:
        """Parse Sherlock stdout as fallback."""
        results = []
        for line in stdout.split('\n'):
            line = line.strip()
            if not line:
                continue
            # Pattern: [+] SiteName: https://...
            match = re.match(r'^\[?\+\]?\s*(.+?):\s*(https?://\S+)', line)
            if match:
                results.append({
                    'platform': match.group(1).strip(),
                    'url': match.group(2).strip(),
                    'status': 'found',
                    'country': '',
                    'http_status': '',
                    'response_time': 0.0,
                    'confidence': 0.65,
                    'source': 'sherlock',
                })
        return results

    def get_found_profiles(self, results: List[Dict]) -> List[Dict]:
        """Filter results to only found profiles."""
        return [r for r in results if r.get('status') == 'found']


# Singleton
sherlock_search = SherlockSearchService()
