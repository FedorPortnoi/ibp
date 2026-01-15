"""
Combined Search Service v7.0 - TRUE BATCH PROCESSING
=====================================================
Runs Maigret and Sherlock ONCE each with all usernames.

Performance: 190 minutes → 3-5 minutes

Author: IBP Project
Version: 7.0
"""

import os
import sys
import json
import time
import subprocess
import tempfile
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Callable, Any
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import re

from app.services.username_generator_v2 import EnhancedUsernameGenerator
from app.services.strict_platform_filter import StrictPlatformFilter, RUSSIA_PLATFORMS
from app.services.url_validator import ProfileValidator


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

    def elapsed_time(self) -> str:
        elapsed = time.time() - self.start_time
        minutes = int(elapsed // 60)
        seconds = int(elapsed % 60)
        return f"{minutes}m {seconds}s"

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


class CombinedSearchService:
    """
    OSINT search service with TRUE batch processing.

    Pipeline:
    1. Generate usernames (15 realistic variations)
    2. Run Maigret ONCE with all usernames (batch)
    3. Run Sherlock ONCE with all usernames (batch)
    4. Filter to Russia-relevant platforms
    5. Validate URLs in parallel
    6. Face matching (if photo provided)
    7. Deduplicate and sort
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

        self.username_generator = EnhancedUsernameGenerator(max_results=self.max_usernames)
        self.platform_filter = StrictPlatformFilter()
        self.url_validator = ProfileValidator(timeout=10, delay=request_delay)

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
            Config.DELAY_BETWEEN_PHOTOS = 0.2
            Config.GC_EVERY_N_PHOTOS = 5
            self._ultimate_matcher = UltimateFaceMatcher()
            return self._ultimate_matcher
        except ImportError as e:
            print(f"Could not load UltimateFaceMatcher: {e}")
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

        print("\n" + "="*60)
        print("IBP Combined Search v7.0 - BATCH MODE")
        print("="*60)
        print(f"Target: {target_name}")
        print(f"Photo: {'Yes' if target_photo_path else 'No'}")
        print("="*60)

        try:
            # PHASE 1: Generate usernames
            self._update_progress(phase="generating_usernames", current_step=1,
                                  message="Generating username variations...")

            print(f"\n[1/7] Generating usernames...")
            usernames = self.username_generator.generate_usernames(target_name, max_results=self.max_usernames)

            if not usernames:
                name_parts = target_name.lower().replace(' ', '').strip()
                usernames = [name_parts, name_parts[:8], f"{name_parts}1"]

            print(f"      Generated {len(usernames)} usernames: {', '.join(usernames)}")
            self._update_progress(items_total=len(usernames))

            # PHASE 2-3: Run Maigret + Sherlock in parallel (BATCH)
            self._update_progress(phase="searching", current_step=2,
                                  message="Running Maigret + Sherlock (batch)...")

            print(f"\n[2-3/7] Running Maigret + Sherlock in parallel...")

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
                            print(f"      Maigret: {len(maigret_results)} accounts")
                        else:
                            sherlock_results = result
                            print(f"      Sherlock: {len(sherlock_results)} accounts")
                    except Exception as e:
                        print(f"      Error: {e}")

            all_results = maigret_results + sherlock_results
            total_raw = len(all_results)
            print(f"      Total raw: {total_raw} accounts")
            self._update_progress(accounts_found=total_raw)

            # PHASE 4: Platform filter
            self._update_progress(phase="filtering", current_step=4,
                                  message="Filtering platforms...")

            print(f"\n[4/7] Filtering to Russia-relevant platforms...")
            filtered_results = self.platform_filter.filter_results(all_results)
            print(f"      Filtered: {total_raw} -> {len(filtered_results)}")

            # PHASE 5: Validate URLs
            self._update_progress(phase="validating", current_step=5,
                                  items_total=len(filtered_results),
                                  message="Validating URLs...")

            print(f"\n[5/7] Validating URLs...")
            validated_results = self._validate_urls_parallel(filtered_results)
            print(f"      Validated: {len(validated_results)} accounts exist")
            self._update_progress(accounts_validated=len(validated_results))

            # PHASE 6: Face matching
            if target_photo_path and self.enable_face_matching and validated_results:
                self._update_progress(phase="face_matching", current_step=6,
                                      items_total=len(validated_results),
                                      message="Face matching...")

                print(f"\n[6/7] Face matching...")
                validated_results = self._run_face_matching(validated_results, target_photo_path)
                face_matching_enabled = True
            else:
                print(f"\n[6/7] Face matching skipped")

            # PHASE 7: Deduplicate and sort
            self._update_progress(phase="finalizing", current_step=7,
                                  message="Finalizing...")

            print(f"\n[7/7] Finalizing results...")
            final_results = self._deduplicate_and_sort(validated_results)
            face_matches = [r for r in final_results if r.get('face_match', False)]

            self._update_progress(phase="complete",
                                  message=f"Found {len(final_results)} accounts")

            print("\n" + "="*60)
            print("COMPLETE")
            print(f"  Accounts: {len(final_results)}")
            print(f"  Face matches: {len(face_matches)}")
            print(f"  Time: {self.progress.elapsed_time()}")
            print("="*60)

            return {
                'success': True,
                'results': final_results,
                'accounts': final_results,
                'stats': {
                    'usernames_searched': len(usernames),
                    'usernames_generated': len(usernames),
                    'raw_accounts': total_raw,
                    'accounts_found': total_raw,
                    'accounts_filtered': len(filtered_results),
                    'accounts_validated': len(validated_results),
                    'accounts_final': len(final_results),
                    'face_matches': len(face_matches),
                    'photos_scanned': self.progress.photos_scanned,
                    'face_matching_enabled': face_matching_enabled,
                    'search_time': self.progress.elapsed_time()
                }
            }

        except Exception as e:
            import traceback
            traceback.print_exc()
            self._update_progress(phase="error", message=f"Error: {str(e)}")
            return {
                'success': False,
                'results': all_results,
                'accounts': all_results,
                'error': str(e),
                'stats': {'search_time': self.progress.elapsed_time()}
            }

    def _run_maigret_batch(self, usernames: List[str]) -> List[Dict]:
        """
        Run Maigret ONCE with all usernames.

        Maigret supports multiple usernames: maigret user1 user2 user3
        """
        results = []
        temp_dir = tempfile.mkdtemp(prefix="maigret_")

        try:
            print(f"      Maigret: searching {len(usernames)} usernames...")

            # Maigret batch command - all usernames as arguments
            cmd = [
                'maigret',
                *usernames,
                '--folderoutput', temp_dir,
                '--timeout', str(self.timeout),
                '--no-progressbar',
                '--retries', '0'
            ]

            # Total timeout scales with username count but caps at 5 minutes
            total_timeout = min(300, self.timeout * len(usernames) + 60)

            try:
                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=total_timeout,
                    encoding='utf-8',
                    errors='replace'
                )

                # Parse stdout for [+] lines
                results.extend(self._parse_maigret_output(proc.stdout, usernames))

                # Also check for JSON/CSV output files
                for f in Path(temp_dir).glob('*.txt'):
                    try:
                        content = f.read_text(encoding='utf-8', errors='replace')
                        # Extract username from filename
                        username = f.stem.replace('report_', '').split('_')[0]
                        if username in usernames:
                            results.extend(self._parse_maigret_file(content, username))
                    except:
                        pass

            except subprocess.TimeoutExpired:
                print(f"      Maigret: timeout after {total_timeout}s")
            except FileNotFoundError:
                print(f"      Maigret: not installed (pip install maigret)")

        except Exception as e:
            print(f"      Maigret error: {e}")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        # Deduplicate by URL
        seen = set()
        unique = []
        for r in results:
            url = r.get('url', '').lower().rstrip('/')
            if url and url not in seen:
                seen.add(url)
                unique.append(r)

        return unique

    def _parse_maigret_output(self, output: str, usernames: List[str]) -> List[Dict]:
        """Parse Maigret stdout for found accounts."""
        results = []
        current_username = usernames[0] if usernames else ''

        for line in output.split('\n'):
            # Detect username being searched
            for un in usernames:
                if f'Checking username {un}' in line or f'username: {un}' in line.lower():
                    current_username = un
                    break

            # Found account: [+] SiteName: https://...
            match = re.search(r'\[\+\]\s*([^:]+):\s*(https?://[^\s]+)', line)
            if match:
                site = match.group(1).strip()
                url = match.group(2).strip()

                # Try to detect username from URL
                detected = current_username
                for un in usernames:
                    if un.lower() in url.lower():
                        detected = un
                        break

                results.append({
                    'platform': re.sub(r'\s*\[.*\]', '', site).strip(),
                    'url': url,
                    'username': detected,
                    'source': 'maigret'
                })

        return results

    def _parse_maigret_file(self, content: str, username: str) -> List[Dict]:
        """Parse Maigret output file."""
        results = []
        for line in content.split('\n'):
            match = re.search(r'(https?://[^\s]+)', line)
            if match:
                url = match.group(1).strip()
                results.append({
                    'platform': self._extract_platform(url),
                    'url': url,
                    'username': username,
                    'source': 'maigret'
                })
        return results

    def _run_sherlock_batch(self, usernames: List[str]) -> List[Dict]:
        """
        Run Sherlock ONCE with all usernames.

        Sherlock supports multiple usernames: sherlock user1 user2 user3
        """
        results = []

        try:
            print(f"      Sherlock: searching {len(usernames)} usernames...")

            cmd = [
                'sherlock',
                *usernames,
                '--print-found',
                '--timeout', str(self.timeout)
            ]

            total_timeout = min(300, self.timeout * len(usernames) + 60)

            try:
                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=total_timeout,
                    encoding='utf-8',
                    errors='replace'
                )

                results = self._parse_sherlock_output(proc.stdout, usernames)

            except subprocess.TimeoutExpired:
                print(f"      Sherlock: timeout after {total_timeout}s")
            except FileNotFoundError:
                print(f"      Sherlock: not installed (pip install sherlock-project)")

        except Exception as e:
            print(f"      Sherlock error: {e}")

        # Deduplicate
        seen = set()
        unique = []
        for r in results:
            url = r.get('url', '').lower().rstrip('/')
            if url and url not in seen:
                seen.add(url)
                unique.append(r)

        return unique

    def _parse_sherlock_output(self, output: str, usernames: List[str]) -> List[Dict]:
        """Parse Sherlock stdout for found accounts."""
        results = []
        current_username = usernames[0] if usernames else ''

        for line in output.split('\n'):
            # Detect username header
            for un in usernames:
                if f'Checking username {un}' in line:
                    current_username = un
                    break

            # Found: [+] SiteName: https://...
            match = re.search(r'\[\+\]\s*([^:]+):\s*(https?://[^\s]+)', line)
            if match:
                site = match.group(1).strip()
                url = match.group(2).strip()

                detected = current_username
                for un in usernames:
                    if un.lower() in url.lower():
                        detected = un
                        break

                results.append({
                    'platform': site,
                    'url': url,
                    'username': detected,
                    'source': 'sherlock'
                })

        return results

    def _extract_platform(self, url: str) -> str:
        """Extract platform name from URL."""
        try:
            url_clean = re.sub(r'https?://', '', url)
            domain = url_clean.split('/')[0]
            domain = re.sub(r'^www\.', '', domain)
            parts = domain.split('.')
            if len(parts) >= 2:
                return parts[-2].capitalize()
            return domain.capitalize()
        except:
            return "Unknown"

    def _validate_urls_parallel(self, accounts: List[Dict], max_workers: int = 10) -> List[Dict]:
        """Validate URLs in parallel."""
        if not accounts:
            return []

        validated = []
        total = len(accounts)

        def validate_one(account):
            url = account.get('url', '')
            try:
                if self.url_validator.validate_url(url):
                    account['validated'] = True
                    return account
            except:
                pass
            return None

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(validate_one, acc): acc for acc in accounts}
            for i, future in enumerate(as_completed(futures), 1):
                self._update_progress(items_processed=i, message=f"Validating ({i}/{total})...")
                try:
                    result = future.result(timeout=15)
                    if result:
                        validated.append(result)
                except:
                    pass

        return validated

    def _run_face_matching(self, accounts: List[Dict], target_photo_path: str) -> List[Dict]:
        """Run face matching on accounts."""
        matcher = self._load_ultimate_matcher()
        if matcher is None:
            print("      Face matching not available")
            return accounts

        try:
            with matcher:
                if not matcher.load_target(target_photo_path):
                    print("      Could not detect face in target photo")
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
                        account['photos_with_faces'] = result.photos_with_faces
                        account['match_photo_url'] = result.match_photo_url or ''

                        self._update_progress(photos_scanned=self.progress.photos_scanned + result.photos_checked)

                        if result.is_match:
                            self._update_progress(face_matches_found=self.progress.face_matches_found + 1)
                            print(f"      MATCH: {platform} ({result.best_similarity:.1f}%)")
                    except Exception as e:
                        account['face_checked'] = False
                        account['face_match'] = False

                    time.sleep(self.request_delay)

        except Exception as e:
            print(f"      Face matching error: {e}")

        return accounts

    def _deduplicate_and_sort(self, results: List[Dict]) -> List[Dict]:
        """Deduplicate and sort results (face matches first)."""
        seen = set()
        unique = []

        for r in results:
            url = r.get('url', '').lower().rstrip('/')
            if url and url not in seen:
                seen.add(url)
                unique.append(r)

        platform_priority = {
            'vk': 1, 'vkontakte': 1,
            'telegram': 2, 't.me': 2,
            'instagram': 3,
            'ok': 4, 'odnoklassniki': 4,
            'mail.ru': 5, 'my.mail.ru': 5
        }

        def sort_key(r):
            is_match = r.get('face_match', False)
            similarity = r.get('face_similarity', 0)
            platform = r.get('platform', '').lower()
            priority = platform_priority.get(platform, 99)
            return (not is_match, -similarity, priority)

        return sorted(unique, key=sort_key)


def run_search(name: str,
               photo_path: Optional[str] = None,
               max_usernames: int = 15,
               max_photos_per_profile: int = 20) -> Dict:
    """Simple function to run a search."""
    service = CombinedSearchService(
        max_usernames=max_usernames,
        max_photos_per_profile=max_photos_per_profile
    )
    return service.search(name, photo_path)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python combined_search.py <name> [photo_path]")
        sys.exit(1)

    name = sys.argv[1]
    photo = sys.argv[2] if len(sys.argv) > 2 else None

    results = run_search(name, photo)

    if results['success']:
        print(f"\nResults:")
        for i, r in enumerate(results['results'][:20], 1):
            match = "MATCH" if r.get('face_match') else ""
            print(f"  {i}. [{r['platform']}] {r['url']} {match}")
