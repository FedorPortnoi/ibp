"""
Snoop Integration for IBP
=========================
Wraps Snoop (5,372 sites, 2,600+ Russian) for username enumeration.
Snoop is best for Russian/CIS OSINT with VK, OK, Mail.ru, Habr, etc.

Usage:
    from app.services.snoop_search import SnoopSearchService

    snoop = SnoopSearchService()
    if snoop.available:
        results = snoop.search_username("username")
        found = snoop.get_found_profiles(results)
"""

import subprocess
import os
import csv
import logging
import time
import re
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# Snoop paths relative to project root
PROJECT_ROOT = Path(__file__).parent.parent.parent
SNOOP_DIR = PROJECT_ROOT / "snoop"
SNOOP_SCRIPT = SNOOP_DIR / "snoop.py"


class SnoopSearchService:
    """
    Wrapper for Snoop username search tool.

    Snoop searches 5,372+ sites including 2,600+ Russian sites,
    making it ideal for Russia/CIS OSINT investigations.

    Output is parsed from CSV files that Snoop generates.
    """

    # Russian platform keywords for filtering
    RUSSIAN_PLATFORMS = {
        'vk', 'вконтакте', 'vkontakte', 'ok.ru', 'одноклассники', 'odnoklassniki',
        'mail.ru', 'my.mail', 'yandex', 'яндекс', 'habr', 'хабр', 'pikabu', 'пикабу',
        'telegram', 'rutube', 'livejournal', 'drive2', 'avito', 'wildberries',
        'ozon', 'rambler', 'sberbank', 'tinkoff', 'headhunter', 'hh.ru', 'superjob',
        'ivi', 'kinopoisk', 'sports.ru', 'championat', 'fontanka', 'gazeta.ru',
        'rbc', 'lenta.ru', 'vedomosti', 'kommersant', '2gis', 'zoon', 'yell',
        'flamp', 'irecommend', 'otzovik', 'banki.ru', 'auto.ru', 'drom.ru',
        'youla', 'cian', 'domofond', 'irr.ru', 'farpost', 'moyareklama'
    }

    # Country codes for Russian/CIS regions
    RUSSIAN_COUNTRY_CODES = {'RU', 'UA', 'BY', 'KZ', 'UZ', 'AM', 'AZ', 'GE', 'MD', 'KG', 'TJ', 'TM'}

    def __init__(self):
        """Initialize Snoop search service."""
        self.snoop_dir = SNOOP_DIR
        self.snoop_script = SNOOP_SCRIPT
        self._available = None
        self._last_search_time = 0

    @property
    def available(self) -> bool:
        """Check if Snoop is installed and can be executed."""
        if self._available is not None:
            return self._available

        if not self.snoop_script.exists():
            logger.warning(f"Snoop not found at {self.snoop_script}")
            self._available = False
            return False

        # Check dependencies by trying to import them
        try:
            result = subprocess.run(
                ['python', '-c', 'import requests, rich, colorama; print("ok")'],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=str(self.snoop_dir),
                encoding='utf-8',
                errors='replace'
            )
            if 'ok' in result.stdout:
                self._available = True
                logger.info("Snoop is available")
            else:
                self._available = False
                logger.warning(f"Snoop dependency check failed: {result.stderr[:200]}")
        except Exception as e:
            logger.warning(f"Snoop availability check failed: {e}")
            self._available = False

        return self._available

    def _get_results_dir(self) -> Path:
        """Get Snoop results directory (varies by version/platform)."""
        # Source version on Windows: results in snoop dir
        source_results = self.snoop_dir / "results" / "nicknames"
        if source_results.exists():
            return source_results

        # Build version: results in LOCALAPPDATA/snoop
        localappdata = os.environ.get('LOCALAPPDATA', '')
        if localappdata:
            build_results = Path(localappdata) / "snoop" / "results" / "nicknames"
            if build_results.exists():
                return build_results

        # Create source results dir
        source_results.mkdir(parents=True, exist_ok=True)
        return source_results

    def _find_csv_file(self, username: str) -> Optional[Path]:
        """Find CSV results file for a username."""
        results_dir = self._get_results_dir()
        csv_dir = results_dir / "csv"

        if not csv_dir.exists():
            return None

        # Try exact match first
        csv_file = csv_dir / f"{username}.csv"
        if csv_file.exists():
            return csv_file

        # Try case-insensitive search
        for f in csv_dir.glob("*.csv"):
            if f.stem.lower() == username.lower():
                return f

        return None

    def _parse_csv_results(self, csv_path: Path) -> List[Dict]:
        """Parse Snoop CSV output file."""
        results = []

        try:
            # Snoop uses UTF-8-BOM and semicolon delimiter for Russian Windows
            # Try different encodings and delimiters
            for encoding in ['utf-8-sig', 'utf-8', 'cp1251']:
                for delimiter in [';', ',']:
                    try:
                        with open(csv_path, 'r', encoding=encoding, newline='') as f:
                            # Read first line to detect format
                            first_line = f.readline()
                            f.seek(0)

                            if delimiter not in first_line:
                                continue

                            reader = csv.DictReader(f, delimiter=delimiter)

                            for row in reader:
                                # Handle both Russian and English column names
                                platform = row.get('Ресурс') or row.get('Resource') or ''
                                geo = row.get('Гео') or row.get('Geo') or ''
                                url_base = row.get('Url') or ''
                                url_user = row.get('Ссылка_на_профиль') or row.get('Url_username') or ''
                                status = row.get('Статус') or row.get('Status') or ''
                                http_code = row.get('Статус_http') or row.get('Http_code') or ''
                                response_time = row.get('Отклик/сек') or row.get('Response/s') or '0'

                                # Skip metadata rows at end of file
                                if not platform or platform.startswith('«') or platform.startswith('БД'):
                                    continue

                                # Determine if found
                                is_found = status.lower() in ['найден!', 'found', 'claimed', 'найден']

                                # Parse response time
                                try:
                                    resp_time = float(response_time.replace(',', '.'))
                                except (ValueError, AttributeError):
                                    resp_time = 0.0

                                results.append({
                                    'platform': platform.strip(),
                                    'url': url_user.strip() if url_user else url_base.strip(),
                                    'status': 'found' if is_found else 'not_found',
                                    'country': geo.strip(),
                                    'http_status': http_code,
                                    'response_time': resp_time,
                                    'confidence': 0.75 if is_found else 0.0,
                                    'source': 'snoop'
                                })

                            if results:
                                return results

                    except (UnicodeDecodeError, csv.Error):
                        continue

        except Exception as e:
            logger.error(f"Failed to parse Snoop CSV {csv_path}: {e}")

        return results

    def _parse_txt_results(self, txt_path: Path) -> List[Dict]:
        """Parse Snoop TXT output as fallback."""
        results = []

        try:
            with open(txt_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('GEO') or line.startswith('Запрашиваемый'):
                        continue

                    # Format: "GEO  |  Platform ... | URL"
                    parts = line.split('|')
                    if len(parts) >= 3:
                        geo = parts[0].strip()
                        platform = parts[1].strip()
                        url = parts[2].strip()

                        results.append({
                            'platform': platform,
                            'url': url,
                            'status': 'found',
                            'country': geo,
                            'http_status': '200',
                            'response_time': 0.0,
                            'confidence': 0.75,
                            'source': 'snoop'
                        })

        except Exception as e:
            logger.error(f"Failed to parse Snoop TXT {txt_path}: {e}")

        return results

    def search_username(
        self,
        username: str,
        timeout: int = 300,
        russian_only: bool = False
    ) -> List[Dict]:
        """
        Search for username across 5,372+ sites using Snoop.

        Args:
            username: Username to search for
            timeout: Max seconds for search (default 5 min)
            russian_only: If True, only return Russian/CIS results

        Returns:
            List of dicts with keys:
                - platform: str (site name)
                - url: str (profile URL)
                - status: str ("found" | "not_found")
                - country: str (country code like RU, US)
                - http_status: str
                - response_time: float (seconds)
                - confidence: float (0.0-1.0)
                - source: str ("snoop")
        """
        if not self.available:
            logger.warning("Snoop is not available")
            return []

        # Validate username
        if not username or len(username) < 2:
            logger.warning(f"Invalid username: {username}")
            return []

        # Clean username
        username = username.strip()

        results = []

        try:
            # Build command with environment to handle encoding
            env = os.environ.copy()
            env['PYTHONIOENCODING'] = 'utf-8'
            env['PYTHONLEGACYWINDOWSSTDIO'] = '0'

            # Snoop command - use quiet mode and found-only for speed
            cmd = [
                'python', str(self.snoop_script),
                username,
                '-f',  # Only print found
                '-n',  # Disable colors/browser/progress (reduces encoding issues)
            ]

            logger.info(f"Running Snoop: {' '.join(cmd)}")

            # Run Snoop
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(self.snoop_dir),
                env=env,
                encoding='utf-8',
                errors='replace'
            )

            if proc.returncode != 0:
                logger.warning(f"Snoop returned code {proc.returncode}")
                # Still try to parse any results that were saved

            # Parse results from CSV file
            csv_file = self._find_csv_file(username)
            if csv_file:
                results = self._parse_csv_results(csv_file)
                logger.info(f"Parsed {len(results)} results from {csv_file}")
            else:
                # Try TXT as fallback
                txt_dir = self._get_results_dir() / "txt"
                txt_file = txt_dir / f"{username}.txt"
                if txt_file.exists():
                    results = self._parse_txt_results(txt_file)
                    logger.info(f"Parsed {len(results)} results from TXT")

            # Parse stdout as last resort
            if not results and proc.stdout:
                results = self._parse_stdout(proc.stdout)

        except subprocess.TimeoutExpired:
            logger.warning(f"Snoop timed out after {timeout}s for '{username}'")
            # Still try to get partial results
            csv_file = self._find_csv_file(username)
            if csv_file:
                results = self._parse_csv_results(csv_file)

        except Exception as e:
            logger.error(f"Snoop search failed: {e}")

        # Filter to Russian-only if requested
        if russian_only:
            results = self.get_russian_profiles(results)

        found_count = len([r for r in results if r.get('status') == 'found'])
        logger.info(f"Snoop found {found_count} profiles for '{username}' (total checked: {len(results)})")

        return results

    def _parse_stdout(self, stdout: str) -> List[Dict]:
        """Parse Snoop stdout as last resort."""
        results = []

        if not stdout:
            return []

        for line in stdout.split('\n'):
            line = line.strip()
            if not line:
                continue

            # Snoop found lines: "[+] Platform: https://..."
            # Or with country: "RU  Platform: https://..."

            # Pattern 1: [+] Platform: URL
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
                    'source': 'snoop'
                })
                continue

            # Pattern 2: GEO  Platform: URL
            match = re.match(r'^([A-Z]{2})\s+(.+?):\s*(https?://\S+)', line)
            if match:
                results.append({
                    'platform': match.group(2).strip(),
                    'url': match.group(3).strip(),
                    'status': 'found',
                    'country': match.group(1).strip(),
                    'http_status': '',
                    'response_time': 0.0,
                    'confidence': 0.70,
                    'source': 'snoop'
                })

        return results

    def get_found_profiles(self, results: List[Dict]) -> List[Dict]:
        """Filter results to only found profiles."""
        return [r for r in results if r.get('status') == 'found']

    def get_russian_profiles(self, results: List[Dict]) -> List[Dict]:
        """Filter results to Russian/CIS platforms only."""
        russian_results = []

        for r in results:
            if r.get('status') != 'found':
                continue

            platform = r.get('platform', '').lower()
            url = r.get('url', '').lower()
            country = r.get('country', '').upper()

            # Check by country code
            if country in self.RUSSIAN_COUNTRY_CODES:
                russian_results.append(r)
                continue

            # Check by platform name or URL
            for kw in self.RUSSIAN_PLATFORMS:
                if kw in platform or kw in url:
                    russian_results.append(r)
                    break

        return russian_results

    def sort_results(
        self,
        results: List[Dict],
        russian_first: bool = True
    ) -> List[Dict]:
        """Sort results with Russian platforms first, then by confidence."""

        def sort_key(r):
            is_russian = False
            platform = r.get('platform', '').lower()
            url = r.get('url', '').lower()
            country = r.get('country', '').upper()

            if country in self.RUSSIAN_COUNTRY_CODES:
                is_russian = True
            else:
                for kw in self.RUSSIAN_PLATFORMS:
                    if kw in platform or kw in url:
                        is_russian = True
                        break

            return (
                0 if (russian_first and is_russian) else 1,
                -r.get('confidence', 0),
                r.get('platform', '')
            )

        return sorted(results, key=sort_key)


# Singleton instance
snoop_search = SnoopSearchService()


def search_username_snoop(username: str, russian_only: bool = False) -> List[Dict]:
    """
    Convenience function to search username via Snoop.

    Args:
        username: Username to search
        russian_only: Only return Russian/CIS platforms

    Returns:
        List of found profile dicts
    """
    results = snoop_search.search_username(username, russian_only=russian_only)
    return snoop_search.get_found_profiles(results)
