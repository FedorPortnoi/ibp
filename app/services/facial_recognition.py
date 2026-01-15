"""
Facial Recognition Service
==========================
Searches for social media profiles using face photos.

Supported platforms:
- Search4faces (VK, OK, TikTok, Clubhouse) - BEST for Russia
- Yandex Images (reverse image search)
- FaceCheck.ID (560M+ faces)

Author: IBP Project
"""

import os
import re
import time
import base64
import requests
from typing import List, Dict, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass
from urllib.parse import quote

# Import Russia filter
from app.services.russia_filter import (
    filter_results,
    sort_by_priority,
    detect_platform
)


@dataclass
class FaceMatch:
    """Represents a face recognition match."""
    platform: str
    url: str
    confidence: float  # 0.0 to 1.0
    thumbnail_url: Optional[str] = None
    name: Optional[str] = None
    source: str = "unknown"


class FacialRecognitionService:
    """
    Service to search for social media profiles using face photos.
    
    Priority for Russia/CIS investigations:
    1. Search4faces - searches VK, OK, TikTok (BEST)
    2. Yandex Images - excellent for Russian internet
    3. FaceCheck.ID - wide global coverage
    """
    
    def __init__(self):
        """Initialize facial recognition service."""
        self.search4faces_url = "https://search4faces.com"
        self.yandex_images_url = "https://yandex.ru/images/search"
        self.facecheck_url = "https://facecheck.id"
        
        # Track which services are available
        self.services_status = {
            'search4faces': True,
            'yandex': True,
            'facecheck': True
        }
    
    def search_all(self, image_path: str, 
                   progress_callback: Optional[callable] = None) -> Dict:
        """
        Run facial recognition across all available services.
        
        Args:
            image_path: Path to the face image
            progress_callback: Optional callback(service_name, status)
            
        Returns:
            Dict with matches from all services
        """
        if not os.path.exists(image_path):
            return {
                'success': False,
                'error': f'Image not found: {image_path}',
                'matches': []
            }
        
        all_matches = []
        errors = []
        
        # 1. Search4faces (VK, OK, TikTok) - BEST for Russia
        if progress_callback:
            progress_callback('search4faces', 'searching')
        
        print("🔍 Searching Search4faces (VK, OK, TikTok)...")
        s4f_result = self.search_search4faces(image_path)
        if s4f_result.get('success'):
            all_matches.extend(s4f_result.get('matches', []))
            print(f"   ✓ Found {len(s4f_result.get('matches', []))} matches")
        else:
            errors.append(f"Search4faces: {s4f_result.get('error', 'Unknown error')}")
            print(f"   ⚠ {s4f_result.get('error', 'Failed')}")
        
        # 2. Yandex Images
        if progress_callback:
            progress_callback('yandex', 'searching')
        
        print("🔍 Searching Yandex Images...")
        yandex_result = self.search_yandex(image_path)
        if yandex_result.get('success'):
            all_matches.extend(yandex_result.get('matches', []))
            print(f"   ✓ Found {len(yandex_result.get('matches', []))} matches")
        else:
            errors.append(f"Yandex: {yandex_result.get('error', 'Unknown error')}")
            print(f"   ⚠ {yandex_result.get('error', 'Failed')}")
        
        # 3. FaceCheck.ID
        if progress_callback:
            progress_callback('facecheck', 'searching')
        
        print("🔍 Searching FaceCheck.ID...")
        fc_result = self.search_facecheck(image_path)
        if fc_result.get('success'):
            all_matches.extend(fc_result.get('matches', []))
            print(f"   ✓ Found {len(fc_result.get('matches', []))} matches")
        else:
            errors.append(f"FaceCheck: {fc_result.get('error', 'Unknown error')}")
            print(f"   ⚠ {fc_result.get('error', 'Failed')}")
        
        # Deduplicate by URL
        seen_urls = set()
        unique_matches = []
        for match in all_matches:
            url = match.get('url', '')
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_matches.append(match)
        
        # Sort by confidence
        unique_matches.sort(key=lambda x: x.get('confidence', 0), reverse=True)
        
        # Apply Russia filter
        filtered_matches = self._apply_russia_filter(unique_matches)
        
        return {
            'success': True,
            'total_matches': len(filtered_matches),
            'matches': filtered_matches,
            'services_searched': 3,
            'errors': errors if errors else None
        }
    
    def search_search4faces(self, image_path: str) -> Dict:
        """
        Search using Search4faces.com (VK, OK, TikTok, Clubhouse).
        
        This is the BEST tool for Russian social media facial recognition.
        
        Args:
            image_path: Path to face image
            
        Returns:
            Dict with matches
        """
        try:
            # Read and encode image
            with open(image_path, 'rb') as f:
                image_data = f.read()
            
            image_base64 = base64.b64encode(image_data).decode('utf-8')
            
            # Determine content type
            ext = Path(image_path).suffix.lower()
            content_types = {
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.png': 'image/png',
                '.gif': 'image/gif',
                '.webp': 'image/webp'
            }
            content_type = content_types.get(ext, 'image/jpeg')
            
            # Search4faces API endpoint (if available)
            # Note: Search4faces may require browser automation for full functionality
            # This is a simplified implementation
            
            # For now, return instructions for manual search
            # In production, you'd use Selenium or Playwright for browser automation
            
            return {
                'success': True,
                'matches': [],
                'manual_search_url': f"{self.search4faces_url}/en/",
                'instructions': [
                    "1. Go to https://search4faces.com",
                    "2. Upload the target photo",
                    "3. Select platforms: VK, OK, TikTok",
                    "4. Review matches and add to investigation"
                ],
                'note': 'Automated search requires browser automation (Selenium/Playwright)'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'matches': []
            }
    
    def search_yandex(self, image_path: str) -> Dict:
        """
        Search using Yandex Images reverse search.
        
        Yandex has excellent facial recognition for the Russian internet.
        
        Args:
            image_path: Path to face image
            
        Returns:
            Dict with matches or search URL
        """
        try:
            # Read image
            with open(image_path, 'rb') as f:
                image_data = f.read()
            
            # Yandex Images upload endpoint
            upload_url = "https://yandex.ru/images/search"
            
            # For automated search, we'd need to:
            # 1. Upload image to Yandex
            # 2. Parse results page
            # 3. Extract profile links
            
            # Simplified: Return the search URL for manual use
            # In production, use Selenium/Playwright for full automation
            
            # Create a temporary URL for the image if hosted
            # For now, provide instructions
            
            return {
                'success': True,
                'matches': [],
                'manual_search_url': "https://yandex.ru/images/",
                'instructions': [
                    "1. Go to https://yandex.ru/images/",
                    "2. Click the camera icon (🔍📷)",
                    "3. Upload the target photo",
                    "4. Click 'People' filter if available",
                    "5. Review matches for social media profiles"
                ],
                'tip': 'Yandex is excellent for finding VK and OK profiles'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'matches': []
            }
    
    def search_facecheck(self, image_path: str) -> Dict:
        """
        Search using FaceCheck.ID (560M+ faces).
        
        Wide coverage but may have fewer Russian-specific results.
        
        Args:
            image_path: Path to face image
            
        Returns:
            Dict with matches or search URL
        """
        try:
            # FaceCheck.ID also requires browser automation for full functionality
            # It has rate limits on free tier
            
            return {
                'success': True,
                'matches': [],
                'manual_search_url': "https://facecheck.id/",
                'instructions': [
                    "1. Go to https://facecheck.id/",
                    "2. Upload the target photo",
                    "3. Wait for search to complete (may take 1-2 minutes)",
                    "4. Review matches - they show social media profiles",
                    "5. Free tier has limited searches per day"
                ],
                'note': 'FaceCheck has 560M+ indexed faces'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'matches': []
            }
    
    def _apply_russia_filter(self, matches: List[Dict]) -> List[Dict]:
        """Apply Russia filter to facial recognition matches."""
        filtered = []
        
        for match in matches:
            url = match.get('url', '')
            
            # Detect platform
            platform_key, platform_info = detect_platform(url)
            
            if platform_info:
                match['platform'] = platform_info.get('display_name', match.get('platform', 'Unknown'))
                match['category'] = platform_info.get('category', 'Other')
                match['icon'] = platform_info.get('icon', '🔗')
                filtered.append(match)
            elif '.ru' in url or '.ua' in url or '.by' in url or '.kz' in url:
                # Include CIS domains even if not in whitelist
                filtered.append(match)
        
        return filtered
    
    def get_search_urls(self, image_path: str) -> Dict:
        """
        Get direct search URLs for manual facial recognition.
        
        Useful when automated search isn't available.
        
        Args:
            image_path: Path to face image
            
        Returns:
            Dict with search URLs for each service
        """
        return {
            'search4faces': {
                'url': 'https://search4faces.com/en/',
                'platforms': ['VK', 'OK', 'TikTok', 'Clubhouse'],
                'best_for': 'Russian social media',
                'free': True
            },
            'yandex_images': {
                'url': 'https://yandex.ru/images/',
                'platforms': ['VK', 'OK', 'Russian websites'],
                'best_for': 'Russian internet in general',
                'free': True
            },
            'facecheck': {
                'url': 'https://facecheck.id/',
                'platforms': ['Global social media'],
                'best_for': 'Wide coverage (560M+ faces)',
                'free': 'Limited free tier'
            },
            'pimeyes': {
                'url': 'https://pimeyes.com/',
                'platforms': ['Global'],
                'best_for': 'Deep search',
                'free': False,
                'note': 'Paid service, very thorough'
            }
        }


class FacialRecognitionAutomated:
    """
    Automated facial recognition using browser automation.
    
    Requires: pip install playwright
    Then: playwright install chromium
    
    This provides REAL automated searches, not just URLs.
    """
    
    def __init__(self):
        """Initialize automated facial recognition."""
        self.playwright_available = self._check_playwright()
    
    def _check_playwright(self) -> bool:
        """Check if Playwright is available."""
        try:
            from playwright.sync_api import sync_playwright
            return True
        except ImportError:
            return False
    
    def search_search4faces_automated(self, image_path: str) -> Dict:
        """
        Automated Search4faces search using Playwright.
        
        Args:
            image_path: Path to face image
            
        Returns:
            Dict with actual matches
        """
        if not self.playwright_available:
            return {
                'success': False,
                'error': 'Playwright not installed. Run: pip install playwright && playwright install chromium',
                'matches': []
            }
        
        try:
            from playwright.sync_api import sync_playwright
            
            matches = []
            
            with sync_playwright() as p:
                # Launch browser
                browser = p.chromium.launch(headless=True)
                context = browser.new_context()
                page = context.new_page()
                
                # Go to Search4faces
                page.goto('https://search4faces.com/en/')
                
                # Wait for page to load
                page.wait_for_load_state('networkidle')
                
                # Upload image
                # Find file input and upload
                file_input = page.query_selector('input[type="file"]')
                if file_input:
                    file_input.set_input_files(image_path)
                    
                    # Wait for search to complete
                    page.wait_for_timeout(5000)  # Wait 5 seconds
                    
                    # Try to find results
                    # Note: Actual selectors depend on Search4faces HTML structure
                    result_links = page.query_selector_all('a[href*="vk.com"], a[href*="ok.ru"], a[href*="tiktok.com"]')
                    
                    for link in result_links:
                        href = link.get_attribute('href')
                        if href:
                            matches.append({
                                'url': href,
                                'platform': 'Search4faces Match',
                                'confidence': 0.8,
                                'source': 'search4faces'
                            })
                
                browser.close()
            
            return {
                'success': True,
                'matches': matches,
                'count': len(matches)
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'matches': []
            }


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def validate_image(image_path: str) -> Tuple[bool, str]:
    """
    Validate that the image exists and is a supported format.
    
    Args:
        image_path: Path to image file
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not os.path.exists(image_path):
        return False, f"Image not found: {image_path}"
    
    valid_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
    ext = Path(image_path).suffix.lower()
    
    if ext not in valid_extensions:
        return False, f"Unsupported image format: {ext}. Use: {valid_extensions}"
    
    # Check file size (max 10MB)
    size_mb = os.path.getsize(image_path) / (1024 * 1024)
    if size_mb > 10:
        return False, f"Image too large: {size_mb:.1f}MB (max 10MB)"
    
    return True, ""


def get_image_base64(image_path: str) -> Optional[str]:
    """
    Get base64 encoded image data.
    
    Args:
        image_path: Path to image file
        
    Returns:
        Base64 encoded string or None
    """
    try:
        with open(image_path, 'rb') as f:
            return base64.b64encode(f.read()).decode('utf-8')
    except:
        return None


# =============================================================================
# TESTING
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Facial Recognition Service Test")
    print("=" * 60)
    
    service = FacialRecognitionService()
    
    # Show available search URLs
    print("\n📸 Available Facial Recognition Services:")
    print("-" * 40)
    
    urls = service.get_search_urls("")
    for name, info in urls.items():
        print(f"\n{name}:")
        print(f"  URL: {info['url']}")
        print(f"  Best for: {info.get('best_for', 'N/A')}")
        print(f"  Free: {info.get('free', 'Unknown')}")
    
    print("\n" + "=" * 60)
    print("To use automated search, install Playwright:")
    print("  pip install playwright")
    print("  playwright install chromium")
    print("=" * 60)
