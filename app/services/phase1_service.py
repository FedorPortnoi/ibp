"""
Phase 1 Investigation Service - MAXIMUM COVERAGE VERSION
=========================================================
Orchestrates the Phase 1 username/social media discovery process.

Philosophy: Search EVERYTHING, show EVERYTHING, let user decide.

Workflow:
1. Generate ALL username variations (200+)
2. Search EVERY username using Maigret (2500+ sites each)
3. Compile ALL found accounts (deduplicated)
4. Show everything to user
5. User clicks through and selects the correct profile
"""

import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional, Callable

from app.services.username_generator import UsernameGenerator
from app.services.maigret_search import MaigretSearchService


class Phase1Service:
    """
    Phase 1: Social Media Discovery Service - Maximum Coverage
    
    Takes a target name, generates all possible usernames,
    searches EVERYTHING, returns ALL found accounts.
    """
    
    # Priority platforms for Russia/CIS - shown first in results
    PRIORITY_PLATFORMS = [
        'vk', 'vkontakte', 'ok', 'odnoklassniki', 'telegram',
        'instagram', 'facebook', 'twitter', 'x', 'tiktok',
        'youtube', 'linkedin', 'github', 'gitlab', 'discord',
        'twitch', 'steam', 'reddit', 'pikabu', 'habr',
        'yandex', 'mailru', 'rambler', 'livejournal'
    ]
    
    def __init__(self):
        self.username_generator = UsernameGenerator()
        self.maigret_service = MaigretSearchService()
        self.current_progress = {
            'current': 0,
            'total': 0,
            'current_username': '',
            'accounts_found': 0,
            'status': 'idle'
        }
    
    def create_investigation(self, target_name: str, 
                            photo_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a new investigation record.
        
        Args:
            target_name: The target's full name
            photo_path: Optional path to uploaded photo
            
        Returns:
            Investigation dictionary
        """
        investigation_id = str(uuid.uuid4())[:8]
        
        investigation = {
            'id': investigation_id,
            'created_at': datetime.utcnow().isoformat(),
            'status': 'created',
            'input_name': target_name,
            'input_photo_path': photo_path,
            'phase_1': {
                'generated_usernames': [],
                'usernames_searched': 0,
                'discovered_profiles': [],
                'search_stats': {
                    'total_usernames_generated': 0,
                    'total_usernames_searched': 0,
                    'total_accounts_found': 0,
                    'search_time_seconds': 0,
                    'errors': 0
                }
            },
            'confirmed_profile': None
        }
        
        return investigation
    
    def generate_usernames(self, target_name: str, max_usernames: int = 200) -> List[str]:
        """
        Generate all possible username variations.
        
        Args:
            target_name: The target's full name
            max_usernames: Maximum usernames to generate
            
        Returns:
            List of usernames
        """
        return self.username_generator.generate_usernames(
            target_name, 
            max_results=max_usernames
        )
    
    def run_full_search(self, investigation: Dict,
                        max_usernames: int = 200,
                        timeout_per_username: int = 120,
                        progress_callback: Optional[Callable] = None) -> Dict:
        """
        Run the FULL search - generate all usernames and search all of them.
        
        This is the main method - it does EVERYTHING.
        
        Args:
            investigation: Investigation dictionary
            max_usernames: Maximum usernames to search
            timeout_per_username: Timeout per username (seconds)
            progress_callback: Optional callback(progress_dict)
            
        Returns:
            Updated investigation with all results
        """
        target_name = investigation['input_name']
        start_time = datetime.now()
        
        # Update status
        investigation['status'] = 'phase_1_running'
        self.current_progress['status'] = 'generating_usernames'
        
        # === STEP 1: Generate ALL usernames ===
        print(f"\n🔍 Generating usernames for: {target_name}")
        
        all_usernames = self.generate_usernames(target_name, max_usernames)
        investigation['phase_1']['generated_usernames'] = all_usernames
        investigation['phase_1']['search_stats']['total_usernames_generated'] = len(all_usernames)
        
        print(f"✅ Generated {len(all_usernames)} username variations")
        
        # === STEP 2: Search ALL usernames ===
        print(f"\n🔍 Starting search across 2500+ sites...")
        print(f"⏱️  This will take approximately {len(all_usernames) * 1.5:.0f} minutes")
        print("-" * 50)
        
        self.current_progress['status'] = 'searching'
        self.current_progress['total'] = len(all_usernames)
        
        # Progress callback wrapper
        def internal_progress(current, total, username, found_count):
            self.current_progress['current'] = current
            self.current_progress['current_username'] = username
            self.current_progress['accounts_found'] = found_count
            
            if progress_callback:
                progress_callback(self.current_progress)
        
        # Run the search
        search_results = self.maigret_service.search_multiple_usernames(
            usernames=all_usernames,
            timeout_per_user=timeout_per_username,
            progress_callback=internal_progress
        )
        
        # === STEP 3: Process and sort results ===
        all_profiles = search_results['found_accounts']
        
        # Sort by priority (Russian platforms first)
        sorted_profiles = self._sort_by_priority(all_profiles)
        
        # === STEP 4: Update investigation ===
        investigation['phase_1']['discovered_profiles'] = sorted_profiles
        investigation['phase_1']['usernames_searched'] = search_results['total_usernames']
        investigation['phase_1']['search_stats'] = {
            'total_usernames_generated': len(all_usernames),
            'total_usernames_searched': search_results['total_usernames'],
            'total_accounts_found': len(sorted_profiles),
            'search_time_seconds': search_results['search_time_seconds'],
            'errors': search_results['stats']['errors']
        }
        
        investigation['status'] = 'phase_1_complete'
        self.current_progress['status'] = 'complete'
        
        # Print summary
        print("-" * 50)
        print(f"✅ Search complete!")
        print(f"   Usernames searched: {search_results['total_usernames']}")
        print(f"   Accounts found: {len(sorted_profiles)}")
        print(f"   Time taken: {search_results['search_time_seconds']:.1f} seconds")
        
        return investigation
    
    def _sort_by_priority(self, profiles: List[Dict]) -> List[Dict]:
        """
        Sort profiles with priority platforms first.
        VK, OK, Telegram at the top, then others.
        """
        def get_priority(profile):
            platform = profile.get('platform', '').lower()
            
            # Check against priority list
            for i, priority_platform in enumerate(self.PRIORITY_PLATFORMS):
                if priority_platform in platform:
                    return i
            
            return 999  # Low priority for unknown platforms
        
        return sorted(profiles, key=get_priority)
    
    def get_progress(self) -> Dict:
        """Get current search progress."""
        return self.current_progress.copy()
    
    def get_search_queries(self, target_name: str) -> List[str]:
        """Get search queries for manual platform searches."""
        return self.username_generator.generate_search_queries(target_name)


# For testing
if __name__ == "__main__":
    print("=" * 60)
    print("Phase 1 Service - Maximum Coverage Test")
    print("=" * 60)
    
    service = Phase1Service()
    
    # Test username generation only (no actual search)
    test_name = "Fedor Portnoi"
    
    print(f"\nGenerating usernames for: {test_name}")
    usernames = service.generate_usernames(test_name, max_usernames=100)
    
    print(f"\nGenerated {len(usernames)} usernames:")
    print("-" * 40)
    
    for i, u in enumerate(usernames[:50], 1):
        print(f"  {i:3}. {u}")
    
    if len(usernames) > 50:
        print(f"  ... and {len(usernames) - 50} more")
    
    print("\n" + "=" * 60)
    print("To run actual search, use: service.run_full_search(investigation)")
    print("=" * 60)
