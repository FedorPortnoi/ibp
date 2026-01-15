"""
URL/Profile Validator
=====================
Validates that URLs actually exist and lead to real profiles.

Author: IBP Project
"""

import requests
import time
from typing import Optional, Dict, List
from urllib.parse import urlparse


class ProfileValidator:
    """
    Validates profile URLs to check if they actually exist.
    
    Features:
    - HEAD request first (fast)
    - Falls back to GET if needed
    - Platform-specific validation
    - Rate limiting support
    """
    
    # User agent to use for requests
    USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    
    # Status codes that indicate profile exists
    VALID_STATUS_CODES = {200, 201, 202, 301, 302, 303, 307, 308}
    
    # Status codes that indicate profile doesn't exist
    INVALID_STATUS_CODES = {404, 410, 451}
    
    def __init__(self, timeout: int = 10, delay: float = 0.5):
        """
        Initialize the validator.
        
        Args:
            timeout: Request timeout in seconds
            delay: Delay between requests in seconds
        """
        self.timeout = timeout
        self.delay = delay
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': self.USER_AGENT,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5,ru;q=0.3',
        })
    
    def validate_url(self, url: str) -> bool:
        """
        Check if a URL leads to an existing profile.
        
        Args:
            url: The URL to validate
            
        Returns:
            True if profile exists, False otherwise
        """
        if not url or not url.startswith('http'):
            return False
        
        try:
            # Try HEAD request first (faster)
            response = self.session.head(
                url, 
                timeout=self.timeout,
                allow_redirects=True
            )
            
            # Check status code
            if response.status_code in self.VALID_STATUS_CODES:
                return True
            elif response.status_code in self.INVALID_STATUS_CODES:
                return False
            
            # If HEAD didn't give clear answer, try GET
            response = self.session.get(
                url,
                timeout=self.timeout,
                allow_redirects=True
            )
            
            if response.status_code in self.VALID_STATUS_CODES:
                # Additional check: make sure we didn't get redirected to error page
                return not self._is_error_page(response, url)
            
            return False
            
        except requests.exceptions.Timeout:
            # Timeout might mean the page exists but is slow
            return False
        except requests.exceptions.ConnectionError:
            return False
        except requests.exceptions.TooManyRedirects:
            return False
        except Exception as e:
            return False
    
    def _is_error_page(self, response: requests.Response, original_url: str) -> bool:
        """Check if response is an error page (e.g., "user not found")."""
        # Check if we were redirected to a very different URL
        final_url = response.url.lower()
        original_parsed = urlparse(original_url.lower())
        final_parsed = urlparse(final_url)
        
        # If redirected to different domain, probably error
        if original_parsed.netloc != final_parsed.netloc:
            # Allow redirects within same base domain
            if not final_parsed.netloc.endswith(original_parsed.netloc):
                return True
        
        # Check content for common error indicators
        content_lower = response.text.lower()[:5000]  # Check first 5000 chars
        
        error_indicators = [
            'user not found',
            'page not found',
            'profile not found',
            'пользователь не найден',
            'страница не найдена',
            'this account doesn\'t exist',
            'this page isn\'t available',
            'sorry, this page',
            'doesn\'t exist',
            'has been deleted',
            'был удален',
            'заблокирован',
            'suspended',
            'banned',
        ]
        
        for indicator in error_indicators:
            if indicator in content_lower:
                return True
        
        return False
    
    def validate_urls(self, urls: List[str]) -> Dict[str, bool]:
        """
        Validate multiple URLs.
        
        Args:
            urls: List of URLs to validate
            
        Returns:
            Dict mapping URL to validity (True/False)
        """
        results = {}
        
        for url in urls:
            results[url] = self.validate_url(url)
            time.sleep(self.delay)
        
        return results


# =============================================================================
# TEST
# =============================================================================

if __name__ == "__main__":
    validator = ProfileValidator(timeout=10, delay=0.3)
    
    test_urls = [
        "https://github.com/torvalds",
        "https://github.com/thisdoesnotexist12345",
        "https://vk.com/durov",
    ]
    
    print("Testing URL validation:")
    print("=" * 60)
    
    for url in test_urls:
        exists = validator.validate_url(url)
        status = "✓ EXISTS" if exists else "✗ NOT FOUND"
        print(f"{status}: {url}")
        time.sleep(0.5)
