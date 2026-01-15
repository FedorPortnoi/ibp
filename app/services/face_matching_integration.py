"""
Face Matching Integration for IBP Combined Search
==================================================
Drop-in integration for the Ultimate Face Matcher.

This module provides:
1. FaceMatchingService - Simple API for combined_search.py
2. Auto-cleanup - Guaranteed no disk bloat
3. Progress callbacks - Real-time updates
4. Memory efficient - Stream processing

USAGE IN combined_search.py:
============================

from face_matching_integration import FaceMatchingService

# In your CombinedSearch class:
class CombinedSearch:
    def __init__(self, ...):
        ...
        self.face_matcher = FaceMatchingService()
    
    def run_search_with_face_matching(self, name, target_photo_path, ...):
        # ... run Maigret/Sherlock to get accounts ...
        
        # Run face matching
        if target_photo_path and self.face_matcher.is_available():
            accounts = self.face_matcher.match_accounts(
                accounts=accounts,
                target_photo_path=target_photo_path,
                progress_callback=self._face_progress_callback
            )
        
        return accounts

Author: IBP Project
"""

import os
import gc
from typing import List, Dict, Optional, Callable, Any
from dataclasses import dataclass

# Import the main matcher
try:
    from ultimate_face_matcher import (
        UltimateFaceMatcher,
        AccountMatchResult,
        Config,
        FACE_RECOGNITION_AVAILABLE
    )
    MATCHER_AVAILABLE = True
except ImportError:
    MATCHER_AVAILABLE = False
    FACE_RECOGNITION_AVAILABLE = False


@dataclass
class FaceMatchStats:
    """Statistics from face matching run."""
    total_accounts: int = 0
    accounts_checked: int = 0
    face_matches: int = 0
    total_photos_checked: int = 0
    total_faces_found: int = 0
    best_match_similarity: float = 0.0
    best_match_url: str = ""


class FaceMatchingService:
    """
    High-level face matching service for IBP.
    
    Features:
    - Simple one-method API
    - Automatic cleanup
    - Progress callbacks
    - Statistics tracking
    """
    
    def __init__(self,
                 match_threshold: float = 40.0,
                 max_photos_per_profile: int = 50,
                 delay_between_photos: float = 0.3,
                 delay_between_profiles: float = 1.0,
                 proxy: Optional[str] = None):
        """
        Initialize the face matching service.
        
        Args:
            match_threshold: Minimum similarity % for a match
            max_photos_per_profile: Max photos to check per account
            delay_between_photos: Delay between photo downloads
            delay_between_profiles: Delay between profiles
            proxy: Optional proxy URL (e.g., for Russian VPN)
        """
        self.match_threshold = match_threshold
        self.max_photos = max_photos_per_profile
        self.delay_photos = delay_between_photos
        self.delay_profiles = delay_between_profiles
        self.proxy = proxy
        
        self._matcher: Optional[UltimateFaceMatcher] = None
        self._stats: Optional[FaceMatchStats] = None
    
    def is_available(self) -> bool:
        """Check if face matching is available."""
        return MATCHER_AVAILABLE and FACE_RECOGNITION_AVAILABLE
    
    def get_availability_message(self) -> str:
        """Get message about face matching availability."""
        if not MATCHER_AVAILABLE:
            return "ultimate_face_matcher module not found"
        if not FACE_RECOGNITION_AVAILABLE:
            return "face_recognition library not installed. Install with: pip install face_recognition"
        return "Face matching available and ready"
    
    def match_accounts(self,
                      accounts: List[Dict],
                      target_photo_path: str,
                      progress_callback: Optional[Callable] = None) -> List[Dict]:
        """
        Run face matching on a list of accounts.
        
        This is the MAIN METHOD to use.
        
        Args:
            accounts: List of account dicts with 'url' field
            target_photo_path: Path to target's photo
            progress_callback: Optional callback(phase, current, total, message)
                              phase: 'loading', 'matching', 'complete'
                              
        Returns:
            Same accounts list with face matching info added:
            - face_checked: bool
            - face_match: bool  
            - face_similarity: float (0-100)
            - photos_checked: int
            - photos_with_faces: int
            - match_photo_url: str
            - match_photo_type: str
        """
        self._stats = FaceMatchStats(total_accounts=len(accounts))
        
        if not self.is_available():
            print(f"⚠️ Face matching unavailable: {self.get_availability_message()}")
            for acc in accounts:
                acc['face_checked'] = False
                acc['face_match'] = False
            return accounts
        
        if not target_photo_path or not os.path.exists(target_photo_path):
            print(f"⚠️ Target photo not found: {target_photo_path}")
            for acc in accounts:
                acc['face_checked'] = False
                acc['face_match'] = False
            return accounts
        
        try:
            # Initialize matcher
            self._matcher = UltimateFaceMatcher(
                match_threshold=self.match_threshold,
                max_photos_per_profile=self.max_photos,
                delay_between_photos=self.delay_photos,
                delay_between_profiles=self.delay_profiles,
                proxy=self.proxy
            )
            
            # Load target
            if progress_callback:
                progress_callback('loading', 0, 1, 'Loading target photo...')
            
            result = self._matcher.load_target(target_photo_path)
            
            if not result['success']:
                print(f"❌ Failed to load target: {result.get('error')}")
                for acc in accounts:
                    acc['face_checked'] = False
                    acc['face_match'] = False
                return accounts
            
            if progress_callback:
                progress_callback('loading', 1, 1, 'Target loaded successfully')
            
            # Extract valid URLs
            urls = [acc.get('url', '') for acc in accounts if acc.get('url')]
            total = len(urls)
            
            # Create URL to account mapping
            url_to_account = {acc.get('url', ''): acc for acc in accounts}
            
            # Process each account
            for i, url in enumerate(urls, 1):
                if progress_callback:
                    progress_callback('matching', i, total, f'Checking {url[:50]}...')
                
                # Match this account
                match_result = self._matcher.match_single_account(url)
                
                # Update statistics
                self._stats.accounts_checked += 1
                self._stats.total_photos_checked += match_result.photos_checked
                self._stats.total_faces_found += match_result.photos_with_faces
                
                if match_result.is_match:
                    self._stats.face_matches += 1
                    if match_result.best_similarity > self._stats.best_match_similarity:
                        self._stats.best_match_similarity = match_result.best_similarity
                        self._stats.best_match_url = url
                
                # Update account
                if url in url_to_account:
                    acc = url_to_account[url]
                    acc['face_checked'] = True
                    acc['face_match'] = match_result.is_match
                    acc['face_similarity'] = match_result.best_similarity
                    acc['photos_checked'] = match_result.photos_checked
                    acc['photos_with_faces'] = match_result.photos_with_faces
                    acc['match_photo_url'] = match_result.match_photo_url
                    acc['match_photo_type'] = match_result.match_photo_type
                
                # Progress update with result
                if progress_callback:
                    status = '✅ MATCH' if match_result.is_match else '❌ No match'
                    progress_callback('matching', i, total, 
                                    f'{status} ({match_result.best_similarity:.1f}%) - {url[:40]}')
            
            if progress_callback:
                progress_callback('complete', total, total, 
                                f'Complete: {self._stats.face_matches} matches')
            
        except Exception as e:
            print(f"❌ Face matching error: {e}")
            import traceback
            traceback.print_exc()
            
        finally:
            # ALWAYS cleanup
            self._cleanup()
        
        # Mark unchecked accounts
        for acc in accounts:
            if 'face_checked' not in acc:
                acc['face_checked'] = False
                acc['face_match'] = False
        
        # Sort: face matches first, then by similarity
        accounts.sort(key=lambda x: (
            x.get('face_match', False),
            x.get('face_similarity', 0)
        ), reverse=True)
        
        return accounts
    
    def get_stats(self) -> Optional[FaceMatchStats]:
        """Get statistics from the last run."""
        return self._stats
    
    def _cleanup(self):
        """Cleanup matcher resources."""
        if self._matcher:
            self._matcher.cleanup()
            self._matcher = None
        gc.collect()


class FaceMatchingPipeline:
    """
    Complete pipeline for IBP Phase 1 face matching.
    
    Integrates with the existing combined_search workflow.
    """
    
    def __init__(self, 
                 match_threshold: float = 40.0,
                 max_photos_per_profile: int = 50):
        """Initialize pipeline."""
        self.service = FaceMatchingService(
            match_threshold=match_threshold,
            max_photos_per_profile=max_photos_per_profile
        )
    
    def process_search_results(self,
                              accounts: List[Dict],
                              target_photo_path: Optional[str] = None,
                              progress_callback: Optional[Callable] = None) -> Dict[str, Any]:
        """
        Process accounts from combined search with face matching.
        
        Args:
            accounts: Accounts from Maigret/Sherlock
            target_photo_path: Path to target's photo (optional)
            progress_callback: Progress callback
            
        Returns:
            Dict with:
            - accounts: Updated accounts list
            - stats: FaceMatchStats
            - face_matching_ran: bool
        """
        result = {
            'accounts': accounts,
            'stats': None,
            'face_matching_ran': False
        }
        
        # Skip if no target photo or service unavailable
        if not target_photo_path:
            print("ℹ️ No target photo provided - skipping face matching")
            return result
        
        if not self.service.is_available():
            print(f"ℹ️ {self.service.get_availability_message()}")
            return result
        
        # Run face matching
        print("\n" + "=" * 60)
        print("🔍 FACE MATCHING PHASE")
        print("=" * 60)
        print(f"  Target: {target_photo_path}")
        print(f"  Accounts: {len(accounts)}")
        
        accounts = self.service.match_accounts(
            accounts=accounts,
            target_photo_path=target_photo_path,
            progress_callback=progress_callback
        )
        
        stats = self.service.get_stats()
        
        result['accounts'] = accounts
        result['stats'] = stats
        result['face_matching_ran'] = True
        
        # Print summary
        if stats:
            print(f"\n📊 Face Matching Summary:")
            print(f"  Accounts checked: {stats.accounts_checked}/{stats.total_accounts}")
            print(f"  Photos checked: {stats.total_photos_checked}")
            print(f"  Faces found: {stats.total_faces_found}")
            print(f"  Matches: {stats.face_matches}")
            if stats.best_match_url:
                print(f"  Best match: {stats.best_match_similarity:.1f}% - {stats.best_match_url}")
        
        return result


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def check_face_recognition_installation() -> Dict[str, Any]:
    """
    Check if face_recognition is properly installed.
    
    Returns:
        Dict with installation status and instructions
    """
    result = {
        'installed': FACE_RECOGNITION_AVAILABLE,
        'matcher_available': MATCHER_AVAILABLE,
        'ready': MATCHER_AVAILABLE and FACE_RECOGNITION_AVAILABLE,
        'instructions': []
    }
    
    if not FACE_RECOGNITION_AVAILABLE:
        result['instructions'].extend([
            "pip install face_recognition",
            "",
            "If that fails on Windows:",
            "  1. pip install cmake",
            "  2. pip install dlib",
            "  3. pip install face_recognition",
            "",
            "Or use pre-built wheel:",
            "  pip install https://github.com/jloh02/dlib/releases/download/v19.22/dlib-19.22.99-cp310-cp310-win_amd64.whl"
        ])
    
    if not MATCHER_AVAILABLE:
        result['instructions'].append(
            "Make sure ultimate_face_matcher.py is in the same directory or Python path"
        )
    
    return result


def quick_face_match(target_photo: str, 
                    account_url: str,
                    max_photos: int = 20) -> Dict[str, Any]:
    """
    Quick face matching for a single account.
    
    Useful for testing or one-off checks.
    
    Args:
        target_photo: Path to target's photo
        account_url: Single account URL
        max_photos: Max photos to check
        
    Returns:
        Dict with match result
    """
    if not FACE_RECOGNITION_AVAILABLE:
        return {'error': 'face_recognition not installed'}
    
    with UltimateFaceMatcher(max_photos_per_profile=max_photos) as matcher:
        load_result = matcher.load_target(target_photo)
        if not load_result['success']:
            return {'error': load_result.get('error')}
        
        result = matcher.match_single_account(account_url)
        
        return {
            'is_match': result.is_match,
            'similarity': result.best_similarity,
            'photos_checked': result.photos_checked,
            'faces_found': result.photos_with_faces,
            'match_photo_url': result.match_photo_url if result.is_match else None
        }


# =============================================================================
# TESTING
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Face Matching Integration - IBP Project")
    print("=" * 60)
    
    # Check installation
    status = check_face_recognition_installation()
    
    if status['ready']:
        print("✅ Face matching is ready to use!")
    else:
        print("❌ Face matching not ready")
        print("\nInstallation instructions:")
        for instruction in status['instructions']:
            print(f"  {instruction}")
    
    print("\n📖 Usage in your code:")
    print("""
    from face_matching_integration import FaceMatchingService
    
    service = FaceMatchingService()
    
    if service.is_available():
        accounts = service.match_accounts(
            accounts=[{'url': 'https://vk.com/user1'}, ...],
            target_photo_path='target.jpg'
        )
        
        for acc in accounts:
            if acc.get('face_match'):
                print(f"MATCH: {acc['url']} - {acc['face_similarity']}%")
    """)
