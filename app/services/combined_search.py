"""
Combined Search Service v10.0 - Буратино-Style
==============================================
Russia-only OSINT with confidence scoring.

Changes from v9:
- Added ProfileMatch/Phase1Result data models
- Confidence scoring for each profile
- Name similarity calculation
- Better source tracking

Pipeline: Telegram -> VK -> OK -> Yandex Images -> Face matching -> Confidence scoring

Author: IBP Project
Version: 10.0
"""

import os
import sys
import json
import time
from typing import List, Dict, Optional, Callable, Any
from dataclasses import dataclass, field
import re
from difflib import SequenceMatcher

from app.services.username_generator import SmartUsernameGenerator
from app.services.telegram_search import check_telegram_usernames
from app.services.vk_search import check_vk_usernames
from app.services.ok_search import check_ok_usernames
from app.services.yandex_image_search import yandex_reverse_image_search
from app.models.profile import ProfileMatch, Phase1Result, Platform, convert_legacy_results_to_phase1
from app.services.phase1.vk_people_search import vk_people_search
from app.services.phase1.ok_people_search import ok_people_search
from app.services.phase1.telegram_people_search import telegram_people_search
from app.services.phase1.face_search import face_search_service


@dataclass
class SearchProgress:
    """Tracks search progress for UI updates."""
    phase: str = "initializing"
    current_step: int = 0
    total_steps: int = 11
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


def calculate_name_similarity(target_name: str, found_name: str) -> float:
    """
    Calculate similarity between target name and found display name.

    Uses multiple strategies:
    1. Direct comparison (normalized)
    2. First name / last name matching
    3. Transliteration matching (Cyrillic <-> Latin)

    Returns: 0-100 similarity score
    """
    if not target_name or not found_name:
        return 0.0

    # Normalize names
    target = target_name.lower().strip()
    found = found_name.lower().strip()

    # Direct sequence matching
    direct_ratio = SequenceMatcher(None, target, found).ratio() * 100

    # Split into parts and check individual matches
    target_parts = target.split()
    found_parts = found.split()

    # Check if any target name part appears in found name
    part_matches = 0
    for tp in target_parts:
        for fp in found_parts:
            if tp in fp or fp in tp:
                part_matches += 1
                break
            # Check with SequenceMatcher for partial matches
            if SequenceMatcher(None, tp, fp).ratio() > 0.8:
                part_matches += 1
                break

    part_ratio = (part_matches / len(target_parts)) * 100 if target_parts else 0

    # Return the better match
    return max(direct_ratio, part_ratio)


def normalize_name_for_comparison(name: str) -> str:
    """
    Normalize name for comparison (handle Cyrillic/Latin, remove special chars).
    """
    # Cyrillic to Latin transliteration map
    translit_map = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
        'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
        'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
        'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'shch',
        'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya'
    }

    result = []
    for char in name.lower():
        if char in translit_map:
            result.append(translit_map[char])
        else:
            result.append(char)

    return ''.join(result)


class CombinedSearchService:
    """
    Russia-only OSINT search service with Буратино-style confidence scoring.

    Pipeline:
    1. Generate usernames (100+)
    2. VK People Search (by name - real search)
    3. OK People Search (by name - real search)
    4. Telegram People Search (by name)
    5. Telegram username search
    6. VK username search
    7. OK username search
    8. Yandex reverse image search (if photo)
    9. Face matching (if photo)
    10. Deduplicate
    11. Calculate confidence scores
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

            # PHASE 2: VK People Search (real name search, not username guessing)
            self._update_progress(phase="vk_people_search", current_step=2,
                                  message="Searching VK by name...")
            self.progress.log("Phase 2: VK People Search (by name)")
            vk_people_results = []
            try:
                # Search by original name
                vk_people_results = vk_people_search.search_people(
                    target_name,
                    limit=20,
                    target_name=target_name
                )
                self.progress.log(f"VK People Search found {len(vk_people_results)} profiles by name")

                # Also search by name variations
                variations = vk_people_search.generate_search_variations(target_name)
                for var in variations[1:3]:  # Just first 2 variations to save time
                    try:
                        more = vk_people_search.search_people(var, limit=5, target_name=target_name)
                        vk_people_results.extend(more)
                    except Exception:
                        pass
            except Exception as e:
                self.progress.log(f"VK People Search error: {e}")

            # PHASE 3: OK People Search (by name - real search)
            self._update_progress(phase="ok_people_search", current_step=3,
                                  message="Searching OK.ru by name...")
            self.progress.log("Phase 3: OK People Search (by name)")
            ok_people_results = []
            try:
                # Search by original name
                ok_people_results = ok_people_search.search_people(
                    target_name,
                    limit=20,
                    target_name=target_name
                )
                self.progress.log(f"OK People Search found {len(ok_people_results)} profiles by name")

                # Also search by name variations
                variations = ok_people_search.generate_search_variations(target_name)
                for var in variations[1:3]:  # Just first 2 variations to save time
                    try:
                        more = ok_people_search.search_people(var, limit=5, target_name=target_name)
                        ok_people_results.extend(more)
                    except Exception:
                        pass
            except Exception as e:
                self.progress.log(f"OK People Search error: {e}")

            # PHASE 4: Telegram People Search (by name)
            self._update_progress(phase="telegram_people_search", current_step=4,
                                  message="Searching Telegram by name...")
            self.progress.log("Phase 4: Telegram People Search (by name)")
            telegram_people_results = []
            try:
                telegram_people_results = telegram_people_search.search_people(
                    target_name,
                    limit=10,
                    target_name=target_name
                )
                self.progress.log(f"Telegram People Search found {len(telegram_people_results)} profiles by name")
            except Exception as e:
                self.progress.log(f"Telegram People Search error: {e}")

            # PHASE 5: Telegram username search (check if username exists)
            self._update_progress(phase="telegram_search", current_step=5,
                                  message="Checking Telegram usernames...")

            self.progress.log("Phase 5: Telegram username search")
            telegram_results = check_telegram_usernames(usernames)
            self.progress.log(f"Telegram username search found {len(telegram_results)} accounts")

            # PHASE 6: VK username search (check if username exists)
            self._update_progress(phase="vk_search", current_step=6,
                                  message="Checking VK usernames...")
            self.progress.log("Phase 6: VK username search")
            try:
                vk_results = check_vk_usernames(usernames)
                self.progress.log(f"VK username search found {len(vk_results)} accounts")
            except Exception as e:
                vk_results = []
                self.progress.log(f"VK username search error: {e}")

            # PHASE 7: OK username search
            self._update_progress(phase="ok_search", current_step=7,
                                  message="Checking OK usernames...")
            self.progress.log("Phase 7: OK username search")
            try:
                ok_results = check_ok_usernames(usernames)
                self.progress.log(f"OK username search found {len(ok_results)} accounts")
            except Exception as e:
                ok_results = []
                self.progress.log(f"OK username search error: {e}")

            # PHASE 8: Face Search (search4faces + Yandex Images)
            face_search_results = []
            if target_photo_path and os.path.exists(target_photo_path):
                self._update_progress(phase="face_search", current_step=8,
                                      message="Searching by face (search4faces)...")
                self.progress.log("Phase 8: Face search (search4faces + Yandex)")
                try:
                    face_search_results = face_search_service.search_by_photo(
                        target_photo_path,
                        target_name=target_name,
                        limit=30
                    )
                    self.progress.log(f"Face search found {len(face_search_results)} profiles")
                except Exception as e:
                    self.progress.log(f"Face search error: {e}")
            else:
                self.progress.log("Phase 8: Face search skipped (no photo)")

            # Combine all results - People Search results are prioritized, then face search
            all_results = vk_people_results + ok_people_results + telegram_people_results + face_search_results + telegram_results + vk_results + ok_results
            self.progress.log(f"Total raw results: {len(all_results)} (VK People: {len(vk_people_results)}, OK People: {len(ok_people_results)}, Telegram People: {len(telegram_people_results)}, Face Search: {len(face_search_results)})")
            self._update_progress(accounts_found=len(all_results))

            # PHASE 9: Face matching on remaining results (if enabled)
            if target_photo_path and self.enable_face_matching and all_results:
                self._update_progress(phase="face_matching", current_step=9,
                                      items_total=len(all_results),
                                      message="Face matching...")

                self.progress.log("Phase 9: Face matching")
                all_results = self._run_face_matching(all_results, target_photo_path)
                face_matching_enabled = True
            else:
                self.progress.log("Phase 9: Face matching skipped")

            # PHASE 10: Deduplicate
            self._update_progress(phase="finalizing", current_step=10,
                                  message="Finalizing...")

            self.progress.log("Phase 10: Deduplicating")
            final_results = self._deduplicate(all_results)
            self.progress.log(f"Final results: {len(final_results)}")

            # PHASE 11: Calculate confidence scores
            self.progress.log("Phase 11: Calculating confidence scores")
            final_results = self._calculate_confidence_scores(final_results, target_name)

            face_matches = [r for r in final_results if r.get('face_match', False)]
            high_confidence = [r for r in final_results if r.get('confidence_level') == 'high']

            # Sort by confidence score (highest first)
            final_results.sort(key=lambda x: x.get('confidence_score', 0), reverse=True)

            self._update_progress(phase="complete", accounts_validated=len(final_results),
                                  message=f"Found {len(final_results)} accounts ({len(high_confidence)} high confidence)")

            self.progress.log(f"Search complete: {len(final_results)} accounts, {len(face_matches)} face matches, {len(high_confidence)} high confidence")

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
                    'vk_people_found': len(vk_people_results),
                    'ok_people_found': len(ok_people_results),
                    'telegram_people_found': len(telegram_people_results),
                    'face_search_found': len(face_search_results),
                    'telegram_found': len(telegram_results),
                    'vk_found': len(vk_results),
                    'ok_found': len(ok_results),
                    'accounts_final': len(final_results),
                    'face_matches': len(face_matches),
                    'high_confidence': len(high_confidence),
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

    def _calculate_confidence_scores(self, results: List[Dict], target_name: str) -> List[Dict]:
        """
        Calculate confidence scores for each result.

        Scoring based on:
        - Face match (50 points max): face_similarity / 2
        - Name match (30 points max): name_similarity * 0.3
        - Has photo (5 points)
        - Has bio (5 points)
        - Source quality bonus (10 points for yandex/search4faces)
        """
        for r in results:
            score = 0.0

            # Calculate name similarity
            display_name = r.get('display_name', '')
            if display_name:
                name_sim = calculate_name_similarity(target_name, display_name)
                r['name_similarity'] = round(name_sim, 1)
                r['name_match'] = name_sim > 50  # Consider it a match if > 50%

                if r['name_match']:
                    score += min(30.0, name_sim * 0.3)

            # Face matching score
            if r.get('face_match', False):
                face_sim = r.get('face_similarity', 0)
                score += min(50.0, face_sim / 2)

            # Profile completeness
            if r.get('photo_url'):
                score += 5.0
            if r.get('bio'):
                score += 5.0

            # Source quality bonus
            source = r.get('source', '').lower()
            if 'yandex' in source or 'search4faces' in source:
                score += 10.0

            # Set confidence score and level
            r['confidence_score'] = round(min(100.0, score), 1)

            # Determine confidence level
            if score >= 70 or (r.get('face_match') and r.get('name_match')):
                r['confidence_level'] = 'high'
            elif score >= 40 or r.get('face_match'):
                r['confidence_level'] = 'medium'
            elif score >= 20 or r.get('name_match'):
                r['confidence_level'] = 'low'
            else:
                r['confidence_level'] = 'uncertain'

        return results

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
