"""
Sherlock Search Service
=======================
Searches for usernames using Sherlock (400+ sites).
Complements Maigret with different site coverage.

Install: pip install sherlock-project

Author: IBP Project
"""

import subprocess
import re
import time
import os
import json
from typing import List, Dict, Optional, Callable
from pathlib import Path

# Import Russia filter
from app.services.russia_filter import (
    filter_results,
    sort_by_priority,
    is_russia_relevant,
    detect_platform
)


class SherlockSearch:
    """
    Service to run Sherlock username searches with Russia filtering.
    
    Sherlock searches 400+ sites and has different coverage than Maigret.
    Running both gives ~15-25% more results.
    """
    
    def __init__(self, timeout: int = 60, apply_russia_filter: bool = True):
        """
        Initialize Sherlock search service.
        
        Args:
            timeout: Timeout per username search in seconds
            apply_russia_filter: If True, filter results to Russia-relevant only
        """
        self.timeout = timeout
        self.apply_russia_filter = apply_russia_filter
    
    def is_installed(self) -> bool:
        """Check if Sherlock is installed."""
        try:
            result = subprocess.run(
                ['sherlock', '--version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False
    
    def search_username(self, username: str) -> Dict:
        """
        Search for a single username using Sherlock.
        
        Args:
            username: Username to search for
            
        Returns:
            Dict with 'accounts' list and 'error' if any
        """
        # Create temp output directory
        output_dir = Path("temp_sherlock")
        output_dir.mkdir(exist_ok=True)
        output_file = output_dir / f"{username}.txt"
        
        # Build command
        cmd = [
            'sherlock',
            username,
            '--output', str(output_file),
            '--timeout', str(self.timeout),
            '--print-found'  # Only print found accounts
        ]
        
        try:
            # Run Sherlock
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout + 60,  # Extra buffer for slow sites
                encoding='utf-8',
                errors='replace'
            )
            
            # Parse output - Sherlock prints URLs directly
            accounts = self._parse_output(result.stdout, username)
            
            # Also check the output file if it exists
            if output_file.exists():
                with open(output_file, 'r', encoding='utf-8', errors='replace') as f:
                    file_content = f.read()
                    file_accounts = self._parse_file_output(file_content, username)
                    
                    # Merge accounts (avoid duplicates)
                    seen_urls = {a['url'] for a in accounts}
                    for acc in file_accounts:
                        if acc['url'] not in seen_urls:
                            accounts.append(acc)
                            seen_urls.add(acc['url'])
                
                # Cleanup
                try:
                    output_file.unlink()
                except:
                    pass
            
            # Apply Russia filter if enabled
            if self.apply_russia_filter:
                original_count = len(accounts)
                accounts = filter_results(accounts)
                accounts = sort_by_priority(accounts)
                
                return {
                    'username': username,
                    'accounts': accounts,
                    'count': len(accounts),
                    'original_count': original_count,
                    'filtered_count': len(accounts),
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
                'error': 'Sherlock not installed. Run: pip install sherlock-project'
            }
        except Exception as e:
            return {
                'username': username,
                'accounts': [],
                'count': 0,
                'error': str(e)
            }
    
    def _parse_output(self, output: str, username: str) -> List[Dict]:
        """
        Parse Sherlock stdout to extract found accounts.
        
        Sherlock output format:
        [+] SiteName: https://example.com/username
        
        Args:
            output: Raw stdout from Sherlock
            username: The username that was searched
            
        Returns:
            List of account dictionaries
        """
        accounts = []
        seen_urls = set()
        
        # Pattern to match: [+] or [*] followed by site name and URL
        pattern = r'\[\+\]\s*([^:]+):\s*(https?://[^\s]+)'
        
        for line in output.split('\n'):
            match = re.search(pattern, line)
            if match:
                site_name = match.group(1).strip()
                url = match.group(2).strip()
                
                # Skip duplicates
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                
                accounts.append({
                    'site_name': site_name,
                    'url': url,
                    'username': username,
                    'source': 'sherlock'
                })
        
        return accounts
    
    def _parse_file_output(self, content: str, username: str) -> List[Dict]:
        """
        Parse Sherlock output file (contains just URLs).
        
        Args:
            content: File content
            username: The username that was searched
            
        Returns:
            List of account dictionaries
        """
        accounts = []
        seen_urls = set()
        
        # File contains one URL per line
        url_pattern = r'(https?://[^\s]+)'
        
        for line in content.split('\n'):
            line = line.strip()
            if not line:
                continue
                
            match = re.search(url_pattern, line)
            if match:
                url = match.group(1)
                
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                
                # Try to extract site name from URL
                site_name = self._extract_site_name(url)
                
                accounts.append({
                    'site_name': site_name,
                    'url': url,
                    'username': username,
                    'source': 'sherlock'
                })
        
        return accounts
    
    def _extract_site_name(self, url: str) -> str:
        """Extract a readable site name from URL."""
        try:
            # Remove protocol
            url_clean = re.sub(r'https?://', '', url)
            # Get domain
            domain = url_clean.split('/')[0]
            # Remove www.
            domain = re.sub(r'^www\.', '', domain)
            # Get main part
            parts = domain.split('.')
            if len(parts) >= 2:
                return parts[-2].capitalize()
            return domain.capitalize()
        except:
            return "Unknown"
    
    def search_multiple_usernames(
        self,
        usernames: List[str],
        progress_callback: Optional[Callable[[int, int, str, int], None]] = None
    ) -> Dict:
        """
        Search multiple usernames sequentially.
        
        Args:
            usernames: List of usernames to search
            progress_callback: Function(current, total, username, found_count)
            
        Returns:
            Dict with all found accounts and statistics
        """
        all_accounts = []
        seen_urls = set()
        total = len(usernames)
        start_time = time.time()
        original_total = 0
        
        print(f"\n🔍 Sherlock: Searching {total} usernames...")
        
        for i, username in enumerate(usernames, 1):
            # Report progress
            if progress_callback:
                progress_callback(i, total, username, len(all_accounts))
            
            # Print to terminal
            print(f"  [{i}/{total}] Sherlock: {username}")
            
            # Search
            result = self.search_username(username)
            
            # Track original count
            if 'original_count' in result:
                original_total += result['original_count']
            
            # Add unique accounts
            for account in result.get('accounts', []):
                url = account.get('url', '')
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    all_accounts.append(account)
            
            if result.get('count', 0) > 0:
                print(f"      ✓ Found {result['count']} accounts")
            
            # Small delay
            time.sleep(0.2)
        
        elapsed = time.time() - start_time
        
        # Sort by priority
        all_accounts = sort_by_priority(all_accounts)
        
        print(f"  ✅ Sherlock complete: {len(all_accounts)} Russia-relevant accounts")
        
        return {
            'accounts': all_accounts,
            'total_found': len(all_accounts),
            'original_found': original_total,
            'usernames_searched': total,
            'search_time_seconds': elapsed,
            'source': 'sherlock'
        }


# =============================================================================
# TESTING
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Sherlock Search Test")
    print("=" * 60)
    
    search = SherlockSearch(timeout=30, apply_russia_filter=True)
    
    # Check if installed
    if not search.is_installed():
        print("❌ Sherlock not installed!")
        print("   Run: pip install sherlock-project")
        exit(1)
    
    print("✅ Sherlock is installed")
    
    # Test search
    test_username = "fedor"
    print(f"\nSearching for: {test_username}")
    print("-" * 40)
    
    result = search.search_username(test_username)
    
    if result['error']:
        print(f"Error: {result['error']}")
    else:
        print(f"Original results: {result.get('original_count', 'N/A')}")
        print(f"After filter: {result['count']}")
        
        print(f"\nAccounts found:")
        for acc in result['accounts'][:10]:
            platform = acc.get('platform', acc.get('site_name', 'Unknown'))
            print(f"  - {platform}: {acc['url']}")
        
        if result['count'] > 10:
            print(f"  ... and {result['count'] - 10} more")
