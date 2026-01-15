"""
Profile Photo Scraper
=====================
Scrapes photos from social media profiles for face comparison.

Features:
- Scrapes profile picture + photos from posts/albums
- Device-friendly: processes one at a time with delays
- Handles multiple platforms: VK, OK, Telegram, GitHub, etc.
- Saves images temporarily for face comparison

⚠️ OPSEC: Use VPN when scraping Russian social media!

Author: IBP Project
"""

import os
import re
import time
import hashlib
import requests
from typing import List, Dict, Optional, Tuple
from pathlib import Path
from urllib.parse import urljoin, urlparse
from dataclasses import dataclass


@dataclass
class ScrapedPhoto:
    """Represents a scraped photo."""
    url: str
    local_path: str
    source_platform: str
    photo_type: str  # 'profile', 'post', 'album'
    downloaded: bool = False
    has_face: bool = False
    face_similarity: float = 0.0


class ProfilePhotoScraper:
    """
    Scrapes photos from social media profiles.
    
    Device-friendly settings:
    - 2 second delay between requests
    - Downloads one image at a time
    - Limits total photos per profile
    - Cleans up temp files after processing
    """
    
    def __init__(self, 
                 temp_dir: str = "temp_photos",
                 delay_seconds: float = 2.0,
                 max_photos_per_profile: int = 20,
                 timeout: int = 30):
        """
        Initialize scraper.
        
        Args:
            temp_dir: Directory to store temporary photos
            delay_seconds: Delay between requests (device-friendly)
            max_photos_per_profile: Maximum photos to scrape per profile
            timeout: Request timeout in seconds
        """
        self.temp_dir = Path(temp_dir)
        self.temp_dir.mkdir(exist_ok=True)
        
        self.delay = delay_seconds
        self.max_photos = max_photos_per_profile
        self.timeout = timeout
        
        # Session with headers to avoid blocks
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
        })
    
    def scrape_profile(self, url: str, 
                       progress_callback: Optional[callable] = None) -> List[ScrapedPhoto]:
        """
        Scrape photos from a profile URL.
        
        Args:
            url: Profile URL
            progress_callback: Optional callback(status_message)
            
        Returns:
            List of ScrapedPhoto objects
        """
        platform = self._detect_platform(url)
        
        if progress_callback:
            progress_callback(f"Scraping {platform}: {url}")
        
        print(f"  📷 Scraping photos from {platform}...")
        
        # Route to platform-specific scraper
        scrapers = {
            'vk': self._scrape_vk,
            'ok': self._scrape_ok,
            'telegram': self._scrape_telegram,
            'github': self._scrape_github,
            'instagram': self._scrape_instagram,
            'twitter': self._scrape_twitter,
            'youtube': self._scrape_youtube,
            'tiktok': self._scrape_tiktok,
            'facebook': self._scrape_facebook,
            'linkedin': self._scrape_linkedin,
        }
        
        scraper = scrapers.get(platform, self._scrape_generic)
        
        try:
            photo_urls = scraper(url)
            
            # Limit photos
            photo_urls = photo_urls[:self.max_photos]
            
            # Download photos
            photos = []
            for i, photo_url in enumerate(photo_urls):
                if progress_callback:
                    progress_callback(f"Downloading photo {i+1}/{len(photo_urls)}")
                
                photo = self._download_photo(photo_url, platform)
                if photo and photo.downloaded:
                    photos.append(photo)
                
                # Device-friendly delay
                time.sleep(self.delay)
            
            print(f"    ✓ Downloaded {len(photos)} photos")
            return photos
            
        except Exception as e:
            print(f"    ⚠️ Error scraping {platform}: {e}")
            return []
    
    def _detect_platform(self, url: str) -> str:
        """Detect platform from URL."""
        url_lower = url.lower()
        
        platforms = {
            'vk.com': 'vk',
            'vkontakte.ru': 'vk',
            'ok.ru': 'ok',
            'odnoklassniki.ru': 'ok',
            't.me': 'telegram',
            'telegram.me': 'telegram',
            'github.com': 'github',
            'instagram.com': 'instagram',
            'twitter.com': 'twitter',
            'x.com': 'twitter',
            'youtube.com': 'youtube',
            'tiktok.com': 'tiktok',
            'facebook.com': 'facebook',
            'fb.com': 'facebook',
            'linkedin.com': 'linkedin',
        }
        
        for domain, platform in platforms.items():
            if domain in url_lower:
                return platform
        
        return 'generic'
    
    def _scrape_vk(self, url: str) -> List[str]:
        """
        Scrape photos from VK profile.
        
        VK Structure:
        - Profile photo: /photo-XXXX_XXXX
        - Photos album: vk.com/albums{id}
        - Wall posts may contain photos
        """
        photo_urls = []
        
        try:
            # Get main profile page
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            html = response.text
            
            # Extract profile photo
            # VK profile photos are usually in data-src or src attributes
            profile_patterns = [
                r'<img[^>]+class="[^"]*profile[^"]*"[^>]+src="([^"]+)"',
                r'<img[^>]+src="(https://sun[^"]+\.jpg[^"]*)"',
                r'"photo_200":"([^"]+)"',
                r'"photo_400":"([^"]+)"',
                r'"photo_max":"([^"]+)"',
            ]
            
            for pattern in profile_patterns:
                matches = re.findall(pattern, html)
                for match in matches:
                    if match and 'camera' not in match.lower():
                        photo_url = match.replace('\\/', '/')
                        if photo_url not in photo_urls:
                            photo_urls.append(photo_url)
            
            # Try to get photos from the photos page
            # Extract user ID first
            user_id_match = re.search(r'vk\.com/([a-zA-Z0-9_.]+)', url)
            if user_id_match:
                user_id = user_id_match.group(1)
                photos_url = f"https://vk.com/photos{user_id}"
                
                time.sleep(self.delay)
                
                try:
                    photos_response = self.session.get(photos_url, timeout=self.timeout)
                    if photos_response.status_code == 200:
                        photos_html = photos_response.text
                        
                        # Extract photo URLs from photos page
                        photo_matches = re.findall(
                            r'(https://sun[a-zA-Z0-9.-]+/[^"]+\.jpg[^"]*)',
                            photos_html
                        )
                        
                        for photo_url in photo_matches[:self.max_photos]:
                            photo_url = photo_url.replace('\\/', '/')
                            if photo_url not in photo_urls:
                                photo_urls.append(photo_url)
                except:
                    pass
            
        except Exception as e:
            print(f"    VK scrape error: {e}")
        
        return photo_urls[:self.max_photos]
    
    def _scrape_ok(self, url: str) -> List[str]:
        """
        Scrape photos from Odnoklassniki (OK.ru) profile.
        """
        photo_urls = []
        
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            html = response.text
            
            # OK.ru photo patterns
            patterns = [
                r'"photoUrl":"([^"]+)"',
                r'src="(https://[^"]+\.ok\.ru/[^"]+\.jpg[^"]*)"',
                r'data-src="(https://[^"]+\.ok\.ru/[^"]+\.jpg[^"]*)"',
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, html)
                for match in matches:
                    photo_url = match.replace('\\/', '/')
                    if photo_url not in photo_urls:
                        photo_urls.append(photo_url)
            
        except Exception as e:
            print(f"    OK.ru scrape error: {e}")
        
        return photo_urls[:self.max_photos]
    
    def _scrape_telegram(self, url: str) -> List[str]:
        """
        Scrape photos from Telegram channel/user.
        
        Note: Telegram profiles usually only have one profile photo visible.
        """
        photo_urls = []
        
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            html = response.text
            
            # Telegram t.me profile photo
            patterns = [
                r'<img[^>]+class="[^"]*tgme_page_photo_image[^"]*"[^>]+src="([^"]+)"',
                r'style="background-image:url\(\'([^\']+)\'\)"',
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, html)
                for match in matches:
                    if match not in photo_urls:
                        photo_urls.append(match)
            
        except Exception as e:
            print(f"    Telegram scrape error: {e}")
        
        return photo_urls[:self.max_photos]
    
    def _scrape_github(self, url: str) -> List[str]:
        """
        Scrape avatar from GitHub profile.
        
        GitHub usually only has one profile avatar.
        """
        photo_urls = []
        
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            html = response.text
            
            # GitHub avatar
            patterns = [
                r'<img[^>]+class="[^"]*avatar[^"]*"[^>]+src="([^"]+)"',
                r'<img[^>]+alt="[^"]*avatar[^"]*"[^>]+src="([^"]+)"',
                r'(https://avatars\.githubusercontent\.com/[^"?\s]+)',
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, html, re.IGNORECASE)
                for match in matches:
                    # Get larger version of avatar
                    if 'avatars.githubusercontent.com' in match:
                        # Remove size parameter to get full size
                        match = re.sub(r'\?.*$', '', match)
                        match = re.sub(r'&s=\d+', '', match)
                    
                    if match not in photo_urls:
                        photo_urls.append(match)
            
        except Exception as e:
            print(f"    GitHub scrape error: {e}")
        
        return photo_urls[:self.max_photos]
    
    def _scrape_instagram(self, url: str) -> List[str]:
        """
        Scrape photos from Instagram.
        
        Note: Instagram heavily blocks scraping. May need login or API.
        """
        photo_urls = []
        
        try:
            response = self.session.get(url, timeout=self.timeout)
            html = response.text
            
            # Instagram profile photo (if accessible)
            patterns = [
                r'"profile_pic_url":"([^"]+)"',
                r'"profile_pic_url_hd":"([^"]+)"',
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, html)
                for match in matches:
                    photo_url = match.replace('\\u0026', '&').replace('\\/', '/')
                    if photo_url not in photo_urls:
                        photo_urls.append(photo_url)
            
        except Exception as e:
            print(f"    Instagram scrape error (may be blocked): {e}")
        
        return photo_urls[:self.max_photos]
    
    def _scrape_twitter(self, url: str) -> List[str]:
        """Scrape photos from Twitter/X profile."""
        photo_urls = []
        
        try:
            # Twitter blocks most scraping, try Nitter as alternative
            nitter_url = url.replace('twitter.com', 'nitter.net').replace('x.com', 'nitter.net')
            
            response = self.session.get(nitter_url, timeout=self.timeout)
            html = response.text
            
            patterns = [
                r'<img[^>]+src="(/pic/[^"]+)"',
                r'(https://pbs\.twimg\.com/[^"]+)',
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, html)
                for match in matches:
                    if match.startswith('/'):
                        match = f"https://nitter.net{match}"
                    if match not in photo_urls and 'emoji' not in match:
                        photo_urls.append(match)
            
        except Exception as e:
            print(f"    Twitter scrape error: {e}")
        
        return photo_urls[:self.max_photos]
    
    def _scrape_youtube(self, url: str) -> List[str]:
        """Scrape avatar from YouTube channel."""
        photo_urls = []
        
        try:
            response = self.session.get(url, timeout=self.timeout)
            html = response.text
            
            # YouTube channel avatar
            patterns = [
                r'"avatar":\{"thumbnails":\[\{"url":"([^"]+)"',
                r'"thumbnails":\[\{"url":"(https://yt3[^"]+)"',
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, html)
                for match in matches:
                    if match not in photo_urls:
                        photo_urls.append(match)
            
        except Exception as e:
            print(f"    YouTube scrape error: {e}")
        
        return photo_urls[:self.max_photos]
    
    def _scrape_tiktok(self, url: str) -> List[str]:
        """Scrape avatar from TikTok profile."""
        photo_urls = []
        
        try:
            response = self.session.get(url, timeout=self.timeout)
            html = response.text
            
            patterns = [
                r'"avatarLarger":"([^"]+)"',
                r'"avatarMedium":"([^"]+)"',
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, html)
                for match in matches:
                    photo_url = match.replace('\\u002F', '/')
                    if photo_url not in photo_urls:
                        photo_urls.append(photo_url)
            
        except Exception as e:
            print(f"    TikTok scrape error: {e}")
        
        return photo_urls[:self.max_photos]
    
    def _scrape_facebook(self, url: str) -> List[str]:
        """Scrape photos from Facebook (very limited without login)."""
        print(f"    ⚠️ Facebook requires login - skipping photo scrape")
        return []
    
    def _scrape_linkedin(self, url: str) -> List[str]:
        """Scrape photos from LinkedIn (very limited without login)."""
        print(f"    ⚠️ LinkedIn requires login - skipping photo scrape")
        return []
    
    def _scrape_generic(self, url: str) -> List[str]:
        """Generic scraper for unknown platforms."""
        photo_urls = []
        
        try:
            response = self.session.get(url, timeout=self.timeout)
            html = response.text
            
            # Try to find any image that might be a profile photo
            patterns = [
                r'<img[^>]+src="([^"]+\.(?:jpg|jpeg|png|webp)[^"]*)"',
                r'<img[^>]+data-src="([^"]+\.(?:jpg|jpeg|png|webp)[^"]*)"',
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, html, re.IGNORECASE)
                for match in matches:
                    # Filter out common non-profile images
                    if any(skip in match.lower() for skip in ['icon', 'logo', 'banner', 'emoji', 'button']):
                        continue
                    
                    # Make absolute URL
                    if match.startswith('//'):
                        match = 'https:' + match
                    elif match.startswith('/'):
                        parsed = urlparse(url)
                        match = f"{parsed.scheme}://{parsed.netloc}{match}"
                    
                    if match not in photo_urls:
                        photo_urls.append(match)
            
        except Exception as e:
            print(f"    Generic scrape error: {e}")
        
        return photo_urls[:self.max_photos]
    
    def _download_photo(self, photo_url: str, platform: str) -> Optional[ScrapedPhoto]:
        """
        Download a single photo to temp directory.
        
        Args:
            photo_url: URL of photo
            platform: Platform name
            
        Returns:
            ScrapedPhoto object or None
        """
        try:
            # Generate unique filename from URL hash
            url_hash = hashlib.md5(photo_url.encode()).hexdigest()[:12]
            ext = self._get_extension(photo_url)
            filename = f"{platform}_{url_hash}{ext}"
            local_path = self.temp_dir / filename
            
            # Skip if already downloaded
            if local_path.exists():
                return ScrapedPhoto(
                    url=photo_url,
                    local_path=str(local_path),
                    source_platform=platform,
                    photo_type='scraped',
                    downloaded=True
                )
            
            # Download
            response = self.session.get(photo_url, timeout=self.timeout)
            response.raise_for_status()
            
            # Check if it's actually an image
            content_type = response.headers.get('content-type', '')
            if 'image' not in content_type and 'octet-stream' not in content_type:
                return None
            
            # Save to file
            with open(local_path, 'wb') as f:
                f.write(response.content)
            
            # Verify file size (skip tiny images that are probably icons)
            if local_path.stat().st_size < 1000:  # Less than 1KB
                local_path.unlink()
                return None
            
            return ScrapedPhoto(
                url=photo_url,
                local_path=str(local_path),
                source_platform=platform,
                photo_type='scraped',
                downloaded=True
            )
            
        except Exception as e:
            print(f"      Download error: {e}")
            return None
    
    def _get_extension(self, url: str) -> str:
        """Get file extension from URL."""
        url_path = urlparse(url).path.lower()
        
        if '.png' in url_path:
            return '.png'
        elif '.webp' in url_path:
            return '.webp'
        elif '.gif' in url_path:
            return '.gif'
        else:
            return '.jpg'
    
    def cleanup(self, photos: List[ScrapedPhoto] = None):
        """
        Clean up downloaded photos.
        
        Args:
            photos: Specific photos to clean, or all if None
        """
        if photos:
            for photo in photos:
                try:
                    if photo.local_path and os.path.exists(photo.local_path):
                        os.unlink(photo.local_path)
                except:
                    pass
        else:
            # Clean all temp photos
            try:
                for file in self.temp_dir.iterdir():
                    if file.is_file():
                        file.unlink()
            except:
                pass
    
    def scrape_multiple_profiles(self, urls: List[str],
                                  progress_callback: Optional[callable] = None) -> Dict[str, List[ScrapedPhoto]]:
        """
        Scrape photos from multiple profiles.
        
        Args:
            urls: List of profile URLs
            progress_callback: Optional callback(current, total, status)
            
        Returns:
            Dict mapping URL to list of ScrapedPhoto
        """
        results = {}
        total = len(urls)
        
        print(f"\n📸 Scraping photos from {total} profiles...")
        print(f"   (Device-safe mode: {self.delay}s delay between requests)")
        
        for i, url in enumerate(urls, 1):
            if progress_callback:
                progress_callback(i, total, f"Scraping {url}")
            
            print(f"\n  [{i}/{total}] {url}")
            
            photos = self.scrape_profile(url)
            results[url] = photos
            
            # Extra delay between profiles
            if i < total:
                time.sleep(self.delay)
        
        total_photos = sum(len(photos) for photos in results.values())
        print(f"\n✅ Scraped {total_photos} photos from {total} profiles")
        
        return results


# =============================================================================
# TESTING
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Profile Photo Scraper Test")
    print("=" * 60)
    
    scraper = ProfilePhotoScraper(
        delay_seconds=2.0,
        max_photos_per_profile=5
    )
    
    # Test with a GitHub profile (most reliable for testing)
    test_url = "https://github.com/torvalds"
    
    print(f"\nTest URL: {test_url}")
    print("-" * 40)
    
    photos = scraper.scrape_profile(test_url)
    
    print(f"\nResults:")
    for photo in photos:
        print(f"  - {photo.local_path}")
        print(f"    URL: {photo.url[:60]}...")
    
    # Cleanup
    scraper.cleanup(photos)
    print("\n✅ Cleaned up temp files")
