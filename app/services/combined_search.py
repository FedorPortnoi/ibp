"""
Combined Search Service v9.0 - Russia-Only
==========================================
Restricted to VK, OK, Telegram only (no Maigret/Sherlock).
Enhanced username generation (50+ usernames).

Changes from v8:
- Removed Maigret/Sherlock (too slow, too many irrelevant results)
- Added OK (Odnoklassniki) direct search
- Increased username limit to 50
- Pipeline: Telegram -> VK -> OK -> Yandex Images -> Face matching

Author: IBP Project
Version: 9.0
"""

import os
import sys
import json
import time
from typing import List, Dict, Optional, Callable, Any
from dataclasses import dataclass, field
import re

from app.services.username_generator import SmartUsernameGenerator
from app.services.telegram_search import check_telegram_usernames
from app.services.vk_search import check_vk_usernames
from app.services.ok_search import check_ok_usernames
from app.services.yandex_image_search import yandex_reverse_image_search


@dataclass
class SearchProgress:
    """Tracks search progress for UI updates."""
    phase: str = "initializing"
    current_step: int = 0
    total_steps: int = 6
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


# Russia-only platforms (VK, OK, Telegram)
ALLOWED_PLATFORMS = {
    'vk', 'vkontakte', 'ok', 'odnoklassniki', 'telegram', 't.me'
}


class CombinedSearchService:
    """
    Russia-only OSINT search service.

    Pipeline:
    1. Generate usernames (100+)
    2. Telegram direct search
    3. VK direct search
    4. OK direct search
    5. Yandex reverse image search (if photo)
    6. Face matching (if photo)
    7. Deduplicate
    """

    DEFAULT_MAX_USERNAMES = 100
    DEFAULT_TIMEOUT = 30

    def __init__(self,
                 max_usernames: int = DEFAULT_MAX_USERNAMES,
                 request_delay: float = 0.3,
                 enable_face_matching: bool = True,
                 max_photos_per_profile: int = 20,
                 timeout: int = DEFAULT_TIMEOUT):
        self.max_usernames = max_usernames  # No cap - allow 50+ usernames
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

            # PHASE 2.5: VK direct search (fast)
            self._update_progress(phase="vk_search", current_step=2,
                                  message="Checking VK profiles...")
            self.progress.log("Phase 2.5: VK direct search")
            try:
                vk_results = check_vk_usernames(usernames)
                self.progress.log(f"VK found {len(vk_results)} accounts")
            except Exception as e:
                vk_results = []
                self.progress.log(f"VK search error: {e}")

            # PHASE 3: OK (Odnoklassniki) direct search
            self._update_progress(phase="ok_search", current_step=3,
                                  message="Checking OK profiles...")
            self.progress.log("Phase 3: OK direct search")
            try:
                ok_results = check_ok_usernames(usernames)
                self.progress.log(f"OK found {len(ok_results)} accounts")
            except Exception as e:
                ok_results = []
                self.progress.log(f"OK search error: {e}")

            # PHASE 4: Yandex reverse image search (if photo provided)
            yandex_results = []
            if target_photo_path and os.path.exists(target_photo_path):
                self._update_progress(phase="yandex_search", current_step=4,
                                      message="Searching Yandex Images...")
                self.progress.log("Phase 4: Yandex reverse image search")
                try:
                    yandex_raw = yandex_reverse_image_search(target_photo_path)
                    # Filter Yandex results to only include VK/OK/Telegram
                    for r in yandex_raw:
                        url = r.get('url', '').lower()
                        if 'vk.com' in url or 'ok.ru' in url or 't.me' in url or 'telegram' in url:
                            yandex_results.append(r)
                    self.progress.log(f"Yandex found {len(yandex_raw)} raw, {len(yandex_results)} Russia-only results")
                except Exception as e:
                    self.progress.log(f"Yandex search error: {e}")
            else:
                self.progress.log("Phase 4: Yandex search skipped (no photo)")

            all_results = telegram_results + vk_results + ok_results + yandex_results
            self.progress.log(f"Total raw results: {len(all_results)}")
            self._update_progress(accounts_found=len(all_results))

            # PHASE 5: Face matching (if enabled)
            if target_photo_path and self.enable_face_matching and all_results:
                self._update_progress(phase="face_matching", current_step=5,
                                      items_total=len(all_results),
                                      message="Face matching...")

                self.progress.log("Phase 5: Face matching")
                all_results = self._run_face_matching(all_results, target_photo_path)
                face_matching_enabled = True
            else:
                self.progress.log("Phase 5: Face matching skipped")

            # PHASE 6: Deduplicate
            self._update_progress(phase="finalizing", current_step=6,
                                  message="Finalizing...")

            self.progress.log("Phase 6: Deduplicating")
            final_results = self._deduplicate(all_results)
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
                    'vk_found': len(vk_results),
                    'ok_found': len(ok_results),
                    'yandex_found': len(yandex_results),
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
               max_usernames: int = 100) -> Dict:
    """Simple function to run a search."""
    service = CombinedSearchService(max_usernames=max_usernames)
    return service.search(name, photo_path)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python combined_search.py <name> [photo_path]")
        sys.exit(1)

    name = sys.argv[1]
    photo = sys.argv[2] if len(sys.argv) > 2 else None
    results = run_search(name, photo)
    print(f"\nResults: {len(results.get('results', []))} accounts found")
    for r in results.get('results', [])[:10]:
        print(f"  [{r['platform']}] {r['url']}")
