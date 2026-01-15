"""
Maigret Search Service - WITH RUSSIA FILTER
============================================
Searches for usernames using Maigret and filters to Russia-relevant platforms.

Key features:
- Parses Maigret text output (most reliable)
- Filters results using russia_filter module
- Groups results by category
- Provides search statistics

Author: IBP Project
"""

import subprocess
import re
import time
from typing import List, Dict, Optional, Callable
from pathlib import Path

# Import Russia filter
from app.services.russia_filter import (
    filter_results,
    sort_by_priority,
    group_by_category,
    get_stats,
    is_russia_relevant,
    detect_platform
)


class MaigretSearch:
    """
    Service to run Maigret username searches with Russia filtering.
    """
    
    def __init__(self, timeout: int = 60, apply_russia_filter: bool = True):
        """
        Initialize Maigret search service.
        
        Args:
            timeout: Timeout per username search in seconds
            apply_russia_filter: If True, filter results to Russia-relevant only
        """
        self.timeout = timeout
        self.apply_russia_filter = apply_russia_filter
        self.found_accounts = []
    
    def search_username(self, username: str, use_all_sites: bool = False) -> Dict:
        """
        Search for a single username using Maigret.
        
        Args:
            username: Username to search for
            use_all_sites: If True, use -a flag to search all 2500+ sites
            
        Returns:
            Dict with 'accounts' list and 'error' if any
        """
        # Build command
        cmd = ['maigret', username, '--timeout', str(self.timeout)]
        
        if use_all_sites:
            cmd.append('-a')  # Search ALL sites, not just top 500
        
        try:
            # Run Maigret
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout + 30,  # Extra buffer
                encoding='utf-8',
                errors='replace'
            )
            
            # Parse the text output
            accounts = self._parse_text_output(result.stdout, username)
            
            # Apply Russia filter if enabled
            if self.apply_russia_filter:
                original_count = len(accounts)
                accounts = filter_results(accounts)
                accounts = sort_by_priority(accounts)
                filtered_count = len(accounts)
                
                return {
                    'username': username,
                    'accounts': accounts,
                    'count': len(accounts),
                    'original_count': original_count,
                    'filtered_count': filtered_count,
                    'error': None
                }
            else:
                return {
                    'username': username,
                    'accounts': accounts,
                    'count': len(accounts),
                    'error': None
                }
            
        except subprocess.TimeoutExpired:
            return {
                'username': username,
                'accounts': [],
                'count': 0,
                'error': 'Search timed out'
            }
        except FileNotFoundError:
            return {
                'username': username,
                'accounts': [],
                'count': 0,
                'error': 'Maigret not installed. Run: pip install maigret'
            }
        except Exception as e:
            return {
                'username': username,
                'accounts': [],
                'count': 0,
                'error': str(e)
            }
    
    def _parse_text_output(self, output: str, username: str) -> List[Dict]:
        """
        Parse Maigret text output to extract found accounts.
        
        Looks for lines like:
        [+] GitHub: https://github.com/fedor
        [+] VK: https://vk.com/fedor
        
        Args:
            output: Raw stdout from Maigret
            username: The username that was searched
            
        Returns:
            List of account dictionaries
        """
        accounts = []
        seen_urls = set()
        
        # Pattern to match found accounts: [+] SiteName: https://...
        # Also handles [+] SiteName [ParentSite]: https://...
        pattern = r'\[\+\]\s+([^:]+):\s+(https?://[^\s]+)'
        
        for line in output.split('\n'):
            match = re.search(pattern, line)
            if match:
                site_name = match.group(1).strip()
                url = match.group(2).strip()
                
                # Skip duplicates
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                
                # Clean up site name (remove [ParentSite] suffix)
                site_clean = re.sub(r'\s*\[.*\]', '', site_name).strip()
                
                accounts.append({
                    'site_name': site_clean,
                    'url': url,
                    'username': username,
                    'source': 'maigret'
                })
        
        return accounts
    
    def search_multiple_usernames(
        self,
        usernames: List[str],
        progress_callback: Optional[Callable[[int, int, str, int], None]] = None,
        use_all_sites: bool = False
    ) -> Dict:
        """
        Search multiple usernames sequentially with Russia filtering.
        
        Args:
            usernames: List of usernames to search
            progress_callback: Function(current, total, username, found_count)
            use_all_sites: If True, search all 2500+ sites per username
            
        Returns:
            Dict with all found accounts and statistics
        """
        all_accounts = []
        seen_urls = set()
        total = len(usernames)
        start_time = time.time()
        original_total = 0
        
        for i, username in enumerate(usernames, 1):
            # Report progress
            if progress_callback:
                progress_callback(i, total, username, len(all_accounts))
            
            # Print to terminal for debugging
            print(f"[{i}/{total}] Searching: {username}")
            
            # Search this username
            result = self.search_username(username, use_all_sites=use_all_sites)
            
            # Track original count (before filtering)
            if 'original_count' in result:
                original_total += result['original_count']
            
            # Add unique accounts
            for account in result.get('accounts', []):
                url = account.get('url', '')
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    all_accounts.append(account)
            
            # Print interim results
            if result.get('count', 0) > 0:
                print(f"    ✓ Found {result['count']} Russia-relevant accounts")
            
            # Small delay to be nice to servers
            time.sleep(0.3)
        
        elapsed = time.time() - start_time
        
        # Final sort by priority
        all_accounts = sort_by_priority(all_accounts)
        
        # Group by category
        grouped = group_by_category(all_accounts)
        
        # Calculate statistics
        stats = get_stats(original_total, len(all_accounts))
        
        # Print summary to terminal
        print("-" * 50)
        print(f"✅ Search complete!")
        print(f"   Usernames searched: {total}")
        print(f"   Raw accounts found: {original_total}")
        print(f"   After Russia filter: {len(all_accounts)}")
        print(f"   Removed: {stats['removed_count']} ({stats['removal_rate']}%)")
        print(f"   Time taken: {elapsed:.1f} seconds")
        print(f"   Unique platforms: {len(set(a.get('platform', '') for a in all_accounts))}")
        
        return {
            'accounts': all_accounts,
            'grouped': grouped,
            'total_found': len(all_accounts),
            'original_found': original_total,
            'usernames_searched': total,
            'search_time_seconds': elapsed,
            'unique_platforms': len(set(a.get('platform', '') for a in all_accounts)),
            'stats': stats
        }


# =============================================================================
# TESTING
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Maigret Search Test - WITH RUSSIA FILTER")
    print("=" * 60)
    
    # Test single username
    search = MaigretSearch(timeout=30, apply_russia_filter=True)
    
    test_username = "fedor"
    print(f"\nSearching for: {test_username}")
    print("-" * 40)
    
    result = search.search_username(test_username)
    
    if result['error']:
        print(f"Error: {result['error']}")
    else:
        print(f"\nOriginal results: {result.get('original_count', 'N/A')}")
        print(f"After filter: {result['count']}")
        
        print(f"\nRussia-relevant accounts:")
        for acc in result['accounts'][:15]:
            icon = acc.get('icon', '🔗')
            platform = acc.get('platform', acc.get('site_name', 'Unknown'))
            category = acc.get('category', 'Unknown')
            print(f"  {icon} {platform} ({category})")
            print(f"     {acc['url']}")
        
        if result['count'] > 15:
            print(f"\n  ... and {result['count'] - 15} more")
    
    print("\n" + "=" * 60)
