"""
Maigret Integration for IBP
=============================
Wraps Maigret for username enumeration across 3,000+ sites.
Maigret is complementary to Snoop — it has different site coverage
and better detection of social media profiles.

Maigret can be installed as:
- pip package: `pip install maigret`
- Local tool at OSINT_TOOLS_DIR/maigret/

Usage:
    from app.services.maigret_search import MaigretSearchService

    svc = MaigretSearchService()
    if svc.available:
        results = svc.search_username("username")
        found = svc.get_found_profiles(results)
"""

import json
import logging
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


def _resolve_maigret() -> Optional[str]:
    """
    Resolve maigret executable.
    Priority: pip-installed module > OSINT_TOOLS_DIR > ~/osint_tools/maigret
    """
    # 1. pip-installed (available as `maigret` or `python -m maigret`)
    try:
        result = subprocess.run(
            [sys.executable, '-m', 'maigret', '--version'],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            return 'module'
    except Exception as e:
        logger.debug(f"[Maigret] Module not found: {e}")

    # 1b. Check if maigret is available as a standalone command
    import shutil
    if shutil.which('maigret'):
        return 'standalone'

    # 2. OSINT_TOOLS_DIR
    osint_dir = os.environ.get('OSINT_TOOLS_DIR')
    if osint_dir:
        candidate = Path(osint_dir) / 'maigret'
        if (candidate / 'maigret.py').exists():
            return str(candidate / 'maigret.py')
        # Could also be a venv
        if (candidate / 'maigret').exists():
            return str(candidate / 'maigret')

    # 3. Home directory
    home_candidate = Path.home() / 'osint_tools' / 'maigret'
    if (home_candidate / 'maigret.py').exists():
        return str(home_candidate / 'maigret.py')

    return None


class MaigretSearchService:
    """
    Wrapper for Maigret username search tool.

    Maigret searches 3,000+ sites for username matches.
    Output is parsed from JSON files that Maigret generates.
    """

    def __init__(self):
        self._maigret_path = _resolve_maigret()
        self._available = None

    @property
    def available(self) -> bool:
        """Check if Maigret is installed and can be executed."""
        if self._available is not None:
            return self._available

        if self._maigret_path == 'module':
            self._available = True
        elif self._maigret_path == 'standalone':
            self._available = True
        elif self._maigret_path and Path(self._maigret_path).exists():
            self._available = True
        else:
            self._available = False
            logger.warning(
                "Maigret not available. "
                "Install: pip install maigret OR set OSINT_TOOLS_DIR env var."
            )

        return self._available

    def search_username(
        self,
        username: str,
        timeout: int = 300,
    ) -> List[Dict]:
        """
        Search for username across 3,000+ sites using Maigret.

        Args:
            username: Username to search for
            timeout: Max seconds (default 5 min)

        Returns:
            List of dicts with keys: platform, url, status, confidence, source
        """
        if not self.available:
            return []

        if not username or len(username) < 2:
            return []

        username = username.strip()
        username = username.replace('/', '').replace('\\', '').replace('\0', '')
        username = username.replace('..', '').replace('~', '')
        if not username or len(username) < 2:
            logger.warning(f"Username rejected after sanitization")
            return []
        results = []

        try:
            import tempfile
            with tempfile.TemporaryDirectory() as tmpdir:
                output_file = Path(tmpdir) / f'{username}.json'

                # Build command
                if self._maigret_path == 'module':
                    cmd = [sys.executable, '-m', 'maigret']
                elif self._maigret_path == 'standalone':
                    cmd = ['maigret']
                else:
                    cmd = ['python', self._maigret_path]

                cmd.extend([
                    username,
                    '--json', 'simple',
                    '-o', str(output_file),
                    '--no-color',
                    '--timeout', '10',
                ])

                env = os.environ.copy()
                env['PYTHONIOENCODING'] = 'utf-8'

                logger.info(f"Running Maigret for '{username}'")

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
            logger.warning(f"Maigret timed out after {timeout}s for '{username}'")
        except Exception as e:
            logger.error(f"Maigret search failed: {e}")

        found_count = len([r for r in results if r.get('status') == 'found'])
        logger.info(f"Maigret found {found_count} profiles for '{username}'")
        return results

    def _parse_json_output(self, json_path: Path) -> List[Dict]:
        """Parse Maigret JSON output file."""
        results = []
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Maigret simple JSON: {"site_name": {"url": "...", "status": "Claimed"}}
            if isinstance(data, dict):
                for site_name, info in data.items():
                    if isinstance(info, dict):
                        status_raw = info.get('status', '').lower()
                        is_found = status_raw in ('claimed', 'found')
                        results.append({
                            'platform': site_name,
                            'url': info.get('url_user', info.get('url', '')),
                            'status': 'found' if is_found else 'not_found',
                            'country': info.get('country', ''),
                            'http_status': str(info.get('http_status', '')),
                            'response_time': 0.0,
                            'confidence': 0.75 if is_found else 0.0,
                            'source': 'maigret',
                        })
        except Exception as e:
            logger.error(f"Failed to parse Maigret JSON: {e}")
        return results

    def _parse_stdout(self, stdout: str) -> List[Dict]:
        """Parse Maigret stdout as fallback."""
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
                    'confidence': 0.70,
                    'source': 'maigret',
                })
        return results

    def get_found_profiles(self, results: List[Dict]) -> List[Dict]:
        """Filter results to only found profiles."""
        return [r for r in results if r.get('status') == 'found']
