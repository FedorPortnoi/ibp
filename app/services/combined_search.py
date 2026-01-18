"""
Combined Search Service v8.0 - FIXED
=====================================
Actually returns results now.

Changes from v7:
- Skip URL validation (was removing all results)
- Better stdout parsing for Maigret/Sherlock
- Debug logging to see what's happening
- Relaxed filtering

Author: IBP Project
Version: 8.0
"""

import os
import sys
import json
import time
import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import List, Dict, Optional, Callable, Any
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed
import re

from app.services.username_generator import SmartUsernameGenerator
from app.services.telegram_search import check_telegram_usernames


@dataclass
class SearchProgress:
    """Tracks search progress for UI updates."""
    phase: str = "initializing"
    current_step: int = 0
    total_steps: int = 7
    current_item: str = ""
    items_processed: int = 0
    items_total: int = 0
    accounts_found: int = 0
    accounts_validated: int = 0
    face_matches_found: int = 0
    photos_scanned: int = 0
    message: str = "Starting search..."
    errors: List[str] = field(default_factory=list)
    start_time: float = field(default_factory=time.time)
    debug_log: List[str] = field(default_factory=list)

    def elapsed_time(self) -> str:
        elapsed = time.time() - self.start_time
        minutes = int(elapsed // 60)
        seconds = int(elapsed % 60)
        return f"{minutes}m {seconds}s"

    def log(self, msg: str):
        self.debug_log.append(f"[{self.elapsed_time()}] {msg}")
        print(f"DEBUG: {msg}")

    def to_dict(self) -> Dict:
        return {
            'phase': self.phase,
            'current_step': self.current_step,
            'total_steps': self.total_steps,
            'current_item': self.current_item,
            'items_processed': self.items_processed,
            'items_total': self.items_total,
            'accounts_found': self.accounts_found,
            'accounts_validated': self.accounts_validated,
            'face_matches_found': self.face_matches_found,
            'photos_scanned': self.photos_scanned,
            'message': self.message,
            'errors': self.errors,
            'elapsed_time': self.elapsed_time(),
            'percent_complete': int((self.current_step / self.total_steps) * 100) if self.total_steps > 0 else 0
        }


# Priority platforms (shown first, but others still included)
PRIORITY_PLATFORMS = {
    'vk', 'vkontakte', 'ok', 'odnoklassniki', 'telegram', 't.me',
    'instagram', 'facebook', 'twitter', 'x', 'youtube', 'tiktok',
    'linkedin', 'github', 'reddit', 'twitch', 'discord', 'steam'
}


class CombinedSearchService:
    """
    OSINT search service - FIXED version that actually returns results.

    Pipeline:
    1. Generate usernames
    2. Run Maigret (batch)
    3. Run Sherlock (batch)
    4. Light filtering (prioritize, don't exclude)
    5. Face matching (if photo)
    6. Sort and return
    """

    DEFAULT_MAX_USERNAMES = 15
    DEFAULT_TIMEOUT = 30

    def __init__(self,
                 max_usernames: int = DEFAULT_MAX_USERNAMES,
                 request_delay: float = 0.3,
                 enable_face_matching: bool = True,
                 max_photos_per_profile: int = 20,
                 timeout: int = DEFAULT_TIMEOUT):
        self.max_usernames = min(max_usernames, 25)
        self.request_delay = request_delay
        self.enable_face_matching = enable_face_matching
        self.max_photos_per_profile = max_photos_per_profile
        self.timeout = timeout

        self.username_generator = SmartUsernameGenerator(max_results=self.max_usernames)

        self._ultimate_matcher = None
        self._face_available = None
        self.progress = SearchProgress()
        self.progress_callback = None

    def _check_face_recognition(self) -> bool:
        if self._face_available is not None:
            return self._face_available
        try:
            import face_recognition
            self._face_available = True
            return True
        except ImportError:
            self._face_available = False
            return False

    def _load_ultimate_matcher(self):
        if self._ultimate_matcher is not None:
            return self._ultimate_matcher
        if not self._check_face_recognition():
            return None
        try:
            from app.services.ultimate_face_matcher import UltimateFaceMatcher, Config
            Config.MAX_PHOTOS_PER_PROFILE = self.max_photos_per_profile
            Config.MATCH_THRESHOLD = 40.0
            self._ultimate_matcher = UltimateFaceMatcher()
            return self._ultimate_matcher
        except ImportError as e:
            self.progress.log(f"Could not load UltimateFaceMatcher: {e}")
            return None

    def _update_progress(self, **kwargs):
        for key, value in kwargs.items():
            if hasattr(self.progress, key):
                setattr(self.progress, key, value)
        if self.progress_callback:
            self.progress_callback(self.progress.to_dict())

    def search(self,
               target_name: str,
               target_photo_path: Optional[str] = None,
               progress_callback: Optional[Callable] = None) -> Dict[str, Any]:
        """Run search pipeline."""
        self.progress = SearchProgress()
        self.progress_callback = progress_callback

        all_results = []
        face_matching_enabled = False

        self.progress.log(f"Starting search for: {target_name}")
        self.progress.log(f"Photo provided: {bool(target_photo_path)}")

        try:
            # PHASE 1: Generate usernames
            self._update_progress(phase="generating_usernames", current_step=1,
                                  message="Generating username variations...")

            self.progress.log("Phase 1: Generating usernames")
            usernames = self.username_generator.generate_usernames(target_name, max_results=self.max_usernames)

            if not usernames:
                name_parts = target_name.lower().replace(' ', '').strip()
                usernames = [name_parts, name_parts[:8], f"{name_parts}1"]

            self.progress.log(f"Generated {len(usernames)} usernames: {usernames}")
            self._update_progress(items_total=len(usernames))

            # PHASE 2: Telegram search (fast, direct API)
            self._update_progress(phase="telegram_search", current_step=2,
                                  message="Checking Telegram...")

            self.progress.log("Phase 2: Telegram search (fast)")
            telegram_results = check_telegram_usernames(usernames)
            self.progress.log(f"Telegram found {len(telegram_results)} accounts")

            # PHASE 3-4: Run Maigret + Sherlock in parallel
            self._update_progress(phase="searching", current_step=3,
                                  message="Running Maigret + Sherlock...")

            self.progress.log("Phase 3-4: Running Maigret + Sherlock")

            maigret_results = []
            sherlock_results = []

            with ThreadPoolExecutor(max_workers=2) as executor:
                maigret_future = executor.submit(self._run_maigret_batch, usernames)
                sherlock_future = executor.submit(self._run_sherlock_batch, usernames)

                for future in as_completed([maigret_future, sherlock_future]):
                    try:
                        result = future.result()
                        if future == maigret_future:
                            maigret_results = result
                            self.progress.log(f"Maigret returned {len(maigret_results)} results")
                        else:
                            sherlock_results = result
                            self.progress.log(f"Sherlock returned {len(sherlock_results)} results")
                    except Exception as e:
                        self.progress.log(f"Search error: {e}")

            all_results = telegram_results + maigret_results + sherlock_results
            self.progress.log(f"Total raw results: {len(all_results)}")
            self._update_progress(accounts_found=len(all_results))

            # PHASE 5: Light filtering (prioritize but don't exclude)
            self._update_progress(phase="filtering", current_step=5,
                                  message="Processing results...")

            self.progress.log("Phase 5: Sorting results (priority platforms first)")
            sorted_results = self._sort_by_priority(all_results)
            self.progress.log(f"After sorting: {len(sorted_results)} results")

            # PHASE 6: Face matching (if enabled)
            if target_photo_path and self.enable_face_matching and sorted_results:
                self._update_progress(phase="face_matching", current_step=6,
                                      items_total=len(sorted_results),
                                      message="Face matching...")

                self.progress.log("Phase 6: Face matching")
                sorted_results = self._run_face_matching(sorted_results, target_photo_path)
                face_matching_enabled = True
            else:
                self.progress.log("Phase 6: Face matching skipped")

            # PHASE 7: Deduplicate
            self._update_progress(phase="finalizing", current_step=7,
                                  message="Finalizing...")

            self.progress.log("Phase 7: Deduplicating")
            final_results = self._deduplicate(sorted_results)
            self.progress.log(f"Final results: {len(final_results)}")

            face_matches = [r for r in final_results if r.get('face_match', False)]

            self._update_progress(phase="complete", accounts_validated=len(final_results),
                                  message=f"Found {len(final_results)} accounts")

            self.progress.log(f"Search complete: {len(final_results)} accounts, {len(face_matches)} face matches")

            return {
                'success': True,
                'results': final_results,
                'accounts': final_results,
                'debug_log': self.progress.debug_log,
                'stats': {
                    'usernames_searched': len(usernames),
                    'usernames_generated': len(usernames),
                    'raw_accounts': len(all_results),
                    'accounts_found': len(all_results),
                    'telegram_found': len(telegram_results),
                    'maigret_found': len(maigret_results),
                    'sherlock_found': len(sherlock_results),
                    'accounts_final': len(final_results),
                    'face_matches': len(face_matches),
                    'photos_scanned': self.progress.photos_scanned,
                    'face_matching_enabled': face_matching_enabled,
                    'search_time': self.progress.elapsed_time()
                }
            }

        except Exception as e:
            import traceback
            self.progress.log(f"ERROR: {e}")
            traceback.print_exc()
            self._update_progress(phase="error", message=f"Error: {str(e)}")
            return {
                'success': False,
                'results': all_results,
                'accounts': all_results,
                'error': str(e),
                'debug_log': self.progress.debug_log,
                'stats': {'search_time': self.progress.elapsed_time()}
            }

    def _run_maigret_batch(self, usernames: List[str]) -> List[Dict]:
        """Run Maigret in chunks to avoid site skipping with many usernames."""
        results = []

        # Split usernames into chunks of 2 to avoid Maigret output truncation bug
        # With 3+ usernames, VK URLs get truncated in stdout
        CHUNK_SIZE = 2
        chunks = [usernames[i:i + CHUNK_SIZE] for i in range(0, len(usernames), CHUNK_SIZE)]

        self.progress.log(f"Maigret: searching {len(usernames)} usernames in {len(chunks)} chunks of max {CHUNK_SIZE}")

        for chunk_idx, chunk in enumerate(chunks):
            temp_dir = tempfile.mkdtemp(prefix="maigret_")

            try:
                self.progress.log(f"Maigret chunk {chunk_idx + 1}/{len(chunks)}: {chunk}")

                cmd = [
                    'maigret',
                    *chunk,
                    '-a',  # All sites - critical for finding all accounts
                    '--folderoutput', temp_dir,
                    '--timeout', str(self.timeout),
                    '--retries', '0'
                ]

                # Timeout per chunk - needs to be longer for -a (all sites) mode
                # With 2600+ sites, each username takes ~60-90 seconds
                chunk_timeout = 90 * len(chunk) + 60  # ~90s per username + buffer

                try:
                    proc = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        timeout=chunk_timeout,
                        encoding='utf-8',
                        errors='replace'
                    )

                    self.progress.log(f"Maigret chunk {chunk_idx + 1} stdout: {len(proc.stdout)} chars")

                    # Parse stdout for [+] lines
                    stdout_results = self._parse_osint_output(proc.stdout, chunk, 'maigret')
                    self.progress.log(f"Maigret chunk {chunk_idx + 1} parsed: {len(stdout_results)} results")
                    results.extend(stdout_results)

                    # Also parse output files
                    for f in Path(temp_dir).iterdir():
                        if f.suffix in ['.txt', '.json', '.csv']:
                            try:
                                content = f.read_text(encoding='utf-8', errors='replace')
                                file_results = self._parse_osint_output(content, chunk, 'maigret')
                                if file_results:
                                    self.progress.log(f"Maigret file {f.name}: {len(file_results)} results")
                                results.extend(file_results)
                            except Exception as e:
                                self.progress.log(f"Error reading {f.name}: {e}")

                except subprocess.TimeoutExpired:
                    self.progress.log(f"Maigret chunk {chunk_idx + 1} timeout after {chunk_timeout}s")
                except FileNotFoundError:
                    self.progress.log("Maigret not installed")
                    break  # No point continuing if maigret isn't installed

            except Exception as e:
                self.progress.log(f"Maigret chunk {chunk_idx + 1} error: {e}")
            finally:
                shutil.rmtree(temp_dir, ignore_errors=True)

        # Deduplicate
        unique = self._deduplicate(results)
        self.progress.log(f"Maigret final: {len(unique)} unique results from {len(results)} raw")
        return unique

    def _run_sherlock_batch(self, usernames: List[str]) -> List[Dict]:
        """Run Sherlock with all usernames at once."""
        results = []

        try:
            self.progress.log(f"Sherlock: searching {len(usernames)} usernames")

            cmd = [
                'sherlock',
                *usernames,
                '--print-found',
                '--timeout', str(self.timeout)
            ]

            total_timeout = min(300, self.timeout * len(usernames) + 120)

            try:
                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=total_timeout,
                    encoding='utf-8',
                    errors='replace'
                )

                self.progress.log(f"Sherlock stdout length: {len(proc.stdout)}")

                results = self._parse_osint_output(proc.stdout, usernames, 'sherlock')
                self.progress.log(f"Sherlock parsed: {len(results)} results")

            except subprocess.TimeoutExpired:
                self.progress.log(f"Sherlock timeout after {total_timeout}s")
            except FileNotFoundError:
                self.progress.log("Sherlock not installed")

        except Exception as e:
            self.progress.log(f"Sherlock error: {e}")

        unique = self._deduplicate(results)
        self.progress.log(f"Sherlock final: {len(unique)} unique results")
        return unique

    def _parse_osint_output(self, output: str, usernames: List[str], source: str) -> List[Dict]:
        """Parse Maigret/Sherlock output for found accounts."""
        results = []
        current_username = usernames[0] if usernames else 'unknown'

        for line in output.split('\n'):
            # Update current username if we see a header
            for un in usernames:
                if f'Checking username {un}' in line or f'username: {un}' in line.lower():
                    current_username = un
                    break

            # Look for [+] SiteName: URL pattern
            # Handle various formats:
            # [+] GitHub: https://github.com/user
            # on 5: [+] GitHub: https://github.com/user
            match = re.search(r'\[\+\]\s*([^:]+?):\s*(https?://[^\s]+)', line)
            if match:
                site = match.group(1).strip()
                url = match.group(2).strip()

                # Clean site name
                site = re.sub(r'\s*\[.*?\]', '', site).strip()

                # Detect username from URL
                detected_user = current_username
                for un in usernames:
                    if un.lower() in url.lower():
                        detected_user = un
                        break

                results.append({
                    'platform': site,
                    'url': url,
                    'username': detected_user,
                    'source': source
                })

            # Also look for bare URLs
            elif 'http' in line and '[+]' not in line and '[-]' not in line and '[*]' not in line:
                url_match = re.search(r'(https?://[^\s]+)', line)
                if url_match:
                    url = url_match.group(1).strip()
                    # Extract platform from URL
                    platform = self._extract_platform(url)
                    if platform != 'Unknown':
                        results.append({
                            'platform': platform,
                            'url': url,
                            'username': current_username,
                            'source': source
                        })

        return results

    def _extract_platform(self, url: str) -> str:
        """Extract platform name from URL."""
        platform_map = {
            'vk.com': 'VK',
            'ok.ru': 'OK',
            't.me': 'Telegram',
            'telegram': 'Telegram',
            'instagram.com': 'Instagram',
            'facebook.com': 'Facebook',
            'twitter.com': 'Twitter',
            'x.com': 'X',
            'youtube.com': 'YouTube',
            'tiktok.com': 'TikTok',
            'linkedin.com': 'LinkedIn',
            'github.com': 'GitHub',
            'reddit.com': 'Reddit',
            'twitch.tv': 'Twitch',
            'discord': 'Discord',
            'steam': 'Steam',
            'soundcloud.com': 'SoundCloud',
            'spotify.com': 'Spotify',
            'pinterest.com': 'Pinterest',
            'tumblr.com': 'Tumblr',
            'medium.com': 'Medium',
            'behance.net': 'Behance',
            'dribbble.com': 'Dribbble',
            'flickr.com': 'Flickr',
            'deviantart.com': 'DeviantArt',
            'wordpress.com': 'WordPress',
            'blogger.com': 'Blogger',
            'mail.ru': 'Mail.ru',
            'yandex': 'Yandex',
        }

        url_lower = url.lower()
        for pattern, name in platform_map.items():
            if pattern in url_lower:
                return name

        # Extract from domain
        try:
            domain = re.sub(r'https?://', '', url).split('/')[0]
            domain = re.sub(r'^www\.', '', domain)
            parts = domain.split('.')
            if len(parts) >= 2:
                return parts[-2].capitalize()
        except:
            pass

        return 'Unknown'

    def _sort_by_priority(self, results: List[Dict]) -> List[Dict]:
        """Sort results with priority platforms first."""
        def priority_key(r):
            platform = r.get('platform', '').lower()
            # Check if any priority keyword is in platform name
            for p in PRIORITY_PLATFORMS:
                if p in platform:
                    return (0, platform)
            return (1, platform)

        return sorted(results, key=priority_key)

    def _deduplicate(self, results: List[Dict]) -> List[Dict]:
        """Remove duplicate URLs."""
        seen = set()
        unique = []
        for r in results:
            url = r.get('url', '').lower().rstrip('/')
            if url and url not in seen:
                seen.add(url)
                unique.append(r)
        return unique

    def _run_face_matching(self, accounts: List[Dict], target_photo_path: str) -> List[Dict]:
        """Run face matching on accounts."""
        matcher = self._load_ultimate_matcher()
        if matcher is None:
            self.progress.log("Face matching not available")
            return accounts

        try:
            with matcher:
                if not matcher.load_target(target_photo_path):
                    self.progress.log("Could not detect face in target photo")
                    return accounts

                total = len(accounts)
                for i, account in enumerate(accounts, 1):
                    url = account.get('url', '')
                    platform = account.get('platform', 'unknown')

                    self._update_progress(items_processed=i, current_item=url,
                                          message=f"Face matching: {platform} ({i}/{total})")

                    try:
                        result = matcher.match_single_account(url)
                        account['face_checked'] = True
                        account['face_match'] = result.is_match
                        account['face_similarity'] = round(result.best_similarity, 1)
                        account['photos_checked'] = result.photos_checked

                        self._update_progress(photos_scanned=self.progress.photos_scanned + result.photos_checked)

                        if result.is_match:
                            self._update_progress(face_matches_found=self.progress.face_matches_found + 1)
                    except Exception as e:
                        account['face_checked'] = False
                        account['face_match'] = False

                    time.sleep(self.request_delay)

        except Exception as e:
            self.progress.log(f"Face matching error: {e}")

        return accounts


def run_search(name: str,
               photo_path: Optional[str] = None,
               max_usernames: int = 15) -> Dict:
    """Simple function to run a search."""
    service = CombinedSearchService(max_usernames=max_usernames)
    return service.search(name, photo_path)


# Diagnostic function
def run_diagnostic(username: str = "testuser") -> Dict:
    """Run diagnostics to see what's working."""
    results = {
        'maigret_installed': False,
        'sherlock_installed': False,
        'maigret_output': '',
        'sherlock_output': '',
        'maigret_results': [],
        'sherlock_results': [],
    }

    # Test Maigret
    try:
        proc = subprocess.run(
            ['maigret', '--version'],
            capture_output=True, text=True, timeout=10
        )
        results['maigret_installed'] = True
        results['maigret_version'] = proc.stdout.strip()
    except:
        pass

    # Test Sherlock
    try:
        proc = subprocess.run(
            ['sherlock', '--version'],
            capture_output=True, text=True, timeout=10
        )
        results['sherlock_installed'] = True
        results['sherlock_version'] = proc.stdout.strip()
    except:
        pass

    # Run quick Maigret search
    if results['maigret_installed']:
        try:
            proc = subprocess.run(
                ['maigret', username, '--timeout', '15'],
                capture_output=True, text=True, timeout=60,
                encoding='utf-8', errors='replace'
            )
            results['maigret_output'] = proc.stdout[:2000]
            # Parse results
            for line in proc.stdout.split('\n'):
                match = re.search(r'\[\+\]\s*([^:]+?):\s*(https?://[^\s]+)', line)
                if match:
                    results['maigret_results'].append({
                        'platform': match.group(1).strip(),
                        'url': match.group(2).strip()
                    })
        except Exception as e:
            results['maigret_error'] = str(e)

    return results


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python combined_search.py <name> [photo_path]")
        print("       python combined_search.py --diagnostic")
        sys.exit(1)

    if sys.argv[1] == '--diagnostic':
        print("Running diagnostics...")
        diag = run_diagnostic()
        print(json.dumps(diag, indent=2, default=str))
    else:
        name = sys.argv[1]
        photo = sys.argv[2] if len(sys.argv) > 2 else None
        results = run_search(name, photo)
        print(f"\nResults: {len(results.get('results', []))} accounts found")
        for r in results.get('results', [])[:10]:
            print(f"  [{r['platform']}] {r['url']}")
