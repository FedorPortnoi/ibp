"""
Photo Harvester - Ultimate Multi-Platform Photo Scraper
=========================================================
Scrapes ALL photos from social media profiles (not just profile pictures).

Platforms supported:
- VK (VKontakte) - Russia's #1 social network
- Instagram - via web scraping
- Telegram - profile photos
- Odnoklassniki (OK) - Russia's #2 social network
- Generic web scraping for other platforms

Key features:
- Downloads ALL gallery/post photos, not just profile picture
- Stream processing: download → process → delete immediately
- Memory efficient with automatic cleanup
- Rate limiting and delay management
- Proxy support for geo-blocked platforms

Author: IBP Project
"""

import os
import gc
import re
import time
import uuid
import shutil
import tempfile
import hashlib
import requests
from typing import List, Dict, Optional, Generator, Tuple
from pathlib import Path
from dataclasses import dataclass, field
from urllib.parse import urlparse, urljoin
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# Optional imports with graceful fallback
try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False
    print("⚠️ BeautifulSoup not installed. Install: pip install beautifulsoup4")

try:
    import cloudscraper
    CLOUDSCRAPER_AVAILABLE = True
except ImportError:
    CLOUDSCRAPER_AVAILABLE = False


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class HarvestedPhoto:
    """Represents a downloaded photo."""
    url: str
    local_path: Optional[str] = None
    platform: str = "unknown"
    photo_type: str = "unknown"  # profile, post, gallery, story
    downloaded: bool = False
    file_size: int = 0
    error: Optional[str] = None
    
    def cleanup(self):
        """Delete the local file."""
        if self.local_path and os.path.exists(self.local_path):
            try:
                os.remove(self.local_path)
                self.local_path = None
                self.downloaded = False
            except Exception as e:
                pass


@dataclass
class HarvestResult:
    """Result of harvesting photos from a profile."""
    url: str
    platform: str
    username: str = ""
    photos: List[HarvestedPhoto] = field(default_factory=list)
    total_found: int = 0
    total_downloaded: int = 0
    errors: List[str] = field(default_factory=list)
    
    def cleanup_all(self):
        """Delete all downloaded photos."""
        for photo in self.photos:
            photo.cleanup()
        self.photos.clear()
        gc.collect()


# =============================================================================
# TEMP DIRECTORY MANAGER
# =============================================================================

class TempPhotoManager:
    """
    Manages temporary photo storage with automatic cleanup.
    Uses a unique temp directory per session.
    """
    
    def __init__(self, base_dir: Optional[str] = None):
        """Initialize temp manager with optional base directory."""
        self.session_id = str(uuid.uuid4())[:8]
        
        if base_dir:
            self.base_dir = Path(base_dir)
        else:
            self.base_dir = Path(tempfile.gettempdir()) / "ibp_photos"
        
        self.session_dir = self.base_dir / f"session_{self.session_id}"
        self.session_dir.mkdir(parents=True, exist_ok=True)
        
        self._lock = threading.Lock()
        self._file_count = 0
    
    def get_temp_path(self, url: str, extension: str = ".jpg") -> str:
        """Generate a unique temp file path for a photo URL."""
        with self._lock:
            self._file_count += 1
            # Use URL hash for unique filename
            url_hash = hashlib.md5(url.encode()).hexdigest()[:12]
            filename = f"photo_{self._file_count:04d}_{url_hash}{extension}"
            return str(self.session_dir / filename)
    
    def cleanup_file(self, path: str):
        """Delete a single file."""
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception:
            pass
    
    def cleanup_session(self):
        """Delete entire session directory."""
        try:
            if self.session_dir.exists():
                shutil.rmtree(self.session_dir)
        except Exception:
            pass
        gc.collect()
    
    def cleanup_all(self):
        """Delete all IBP temp directories (from all sessions)."""
        try:
            if self.base_dir.exists():
                shutil.rmtree(self.base_dir)
        except Exception:
            pass
        gc.collect()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup_session()


# =============================================================================
# HTTP CLIENT
# =============================================================================

class PhotoDownloader:
    """
    Robust HTTP client for downloading photos.
    Handles retries, timeouts, and various response types.
    """
    
    # Common image extensions
    IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}
    
    # Headers to mimic browser
    DEFAULT_HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9,ru;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Sec-Fetch-Dest': 'image',
        'Sec-Fetch-Mode': 'no-cors',
        'Sec-Fetch-Site': 'cross-site',
    }
    
    def __init__(self, 
                 timeout: int = 30,
                 max_retries: int = 3,
                 delay_between_downloads: float = 0.5,
                 max_file_size_mb: int = 50,
                 proxy: Optional[str] = None):
        """
        Initialize downloader.
        
        Args:
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts
            delay_between_downloads: Delay between downloads
            max_file_size_mb: Maximum file size to download
            proxy: Optional proxy URL
        """
        self.timeout = timeout
        self.max_retries = max_retries
        self.delay = delay_between_downloads
        self.max_file_size = max_file_size_mb * 1024 * 1024
        self.proxy = proxy
        
        # Session for connection pooling
        self.session = self._create_session()
    
    def _create_session(self) -> requests.Session:
        """Create a configured requests session."""
        if CLOUDSCRAPER_AVAILABLE:
            session = cloudscraper.create_scraper()
        else:
            session = requests.Session()
        
        session.headers.update(self.DEFAULT_HEADERS)
        
        if self.proxy:
            session.proxies = {
                'http': self.proxy,
                'https': self.proxy
            }
        
        return session
    
    def download(self, url: str, save_path: str) -> Tuple[bool, Optional[str]]:
        """
        Download a photo to local path.
        
        Args:
            url: Photo URL
            save_path: Local path to save
            
        Returns:
            (success, error_message)
        """
        if not url:
            return False, "Empty URL"
        
        for attempt in range(self.max_retries):
            try:
                # Add delay between attempts
                if attempt > 0:
                    time.sleep(self.delay * (attempt + 1))
                
                # Stream download for memory efficiency
                response = self.session.get(
                    url,
                    timeout=self.timeout,
                    stream=True
                )
                
                response.raise_for_status()
                
                # Check content type
                content_type = response.headers.get('content-type', '')
                if not ('image' in content_type or 'octet-stream' in content_type):
                    return False, f"Not an image: {content_type}"
                
                # Check file size from headers
                content_length = response.headers.get('content-length')
                if content_length and int(content_length) > self.max_file_size:
                    return False, f"File too large: {int(content_length) / 1024 / 1024:.1f}MB"
                
                # Download in chunks
                total_size = 0
                with open(save_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            total_size += len(chunk)
                            if total_size > self.max_file_size:
                                f.close()
                                os.remove(save_path)
                                return False, "File too large during download"
                            f.write(chunk)
                
                # Verify file was created and has content
                if os.path.exists(save_path) and os.path.getsize(save_path) > 100:
                    return True, None
                else:
                    if os.path.exists(save_path):
                        os.remove(save_path)
                    return False, "Downloaded file too small or empty"
                
            except requests.exceptions.Timeout:
                continue
            except requests.exceptions.RequestException as e:
                if attempt == self.max_retries - 1:
                    return False, str(e)
            except Exception as e:
                return False, str(e)
        
        return False, "Max retries exceeded"
    
    def get_html(self, url: str) -> Optional[str]:
        """Fetch HTML content from a URL."""
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            return response.text
        except Exception:
            return None
    
    def close(self):
        """Close the session."""
        self.session.close()


# =============================================================================
# PLATFORM-SPECIFIC SCRAPERS
# =============================================================================

class BasePlatformScraper:
    """Base class for platform-specific scrapers."""
    
    PLATFORM_NAME = "unknown"
    MAX_PHOTOS_PER_PROFILE = 50  # Default limit
    
    def __init__(self, 
                 downloader: PhotoDownloader,
                 temp_manager: TempPhotoManager,
                 max_photos: int = 50,
                 delay: float = 1.0):
        """
        Initialize scraper.
        
        Args:
            downloader: PhotoDownloader instance
            temp_manager: TempPhotoManager instance
            max_photos: Maximum photos to harvest per profile
            delay: Delay between requests
        """
        self.downloader = downloader
        self.temp_manager = temp_manager
        self.max_photos = min(max_photos, self.MAX_PHOTOS_PER_PROFILE)
        self.delay = delay
    
    def can_handle(self, url: str) -> bool:
        """Check if this scraper can handle the URL."""
        raise NotImplementedError
    
    def extract_username(self, url: str) -> str:
        """Extract username from URL."""
        raise NotImplementedError
    
    def find_photo_urls(self, url: str) -> List[Dict[str, str]]:
        """
        Find all photo URLs from a profile.
        
        Returns:
            List of dicts with 'url' and 'type' (profile, post, gallery)
        """
        raise NotImplementedError
    
    def harvest(self, url: str) -> HarvestResult:
        """
        Harvest photos from a profile URL.
        
        Returns:
            HarvestResult with downloaded photos
        """
        result = HarvestResult(
            url=url,
            platform=self.PLATFORM_NAME,
            username=self.extract_username(url)
        )
        
        try:
            # Find all photo URLs
            photo_infos = self.find_photo_urls(url)
            result.total_found = len(photo_infos)
            
            # Download each photo
            for i, info in enumerate(photo_infos[:self.max_photos]):
                photo_url = info.get('url', '')
                photo_type = info.get('type', 'unknown')
                
                if not photo_url:
                    continue
                
                # Create HarvestedPhoto object
                photo = HarvestedPhoto(
                    url=photo_url,
                    platform=self.PLATFORM_NAME,
                    photo_type=photo_type
                )
                
                # Generate temp path
                ext = Path(urlparse(photo_url).path).suffix or '.jpg'
                if ext.lower() not in PhotoDownloader.IMAGE_EXTENSIONS:
                    ext = '.jpg'
                photo.local_path = self.temp_manager.get_temp_path(photo_url, ext)
                
                # Download
                success, error = self.downloader.download(photo_url, photo.local_path)
                
                if success:
                    photo.downloaded = True
                    photo.file_size = os.path.getsize(photo.local_path) if photo.local_path else 0
                    result.total_downloaded += 1
                else:
                    photo.error = error
                    photo.local_path = None
                
                result.photos.append(photo)
                
                # Rate limiting
                if i < len(photo_infos) - 1:
                    time.sleep(self.delay)
            
        except Exception as e:
            result.errors.append(str(e))
        
        return result


class VKScraper(BasePlatformScraper):
    """
    VKontakte (VK) photo scraper.
    Scrapes profile photos and wall photos.
    """
    
    PLATFORM_NAME = "vk"
    MAX_PHOTOS_PER_PROFILE = 100
    
    # VK photo size suffixes (largest to smallest)
    PHOTO_SIZES = ['w', 'z', 'y', 'x', 'r', 'q', 'p', 'o', 'm', 's']
    
    def can_handle(self, url: str) -> bool:
        return 'vk.com' in url or 'vkontakte.ru' in url
    
    def extract_username(self, url: str) -> str:
        """Extract VK username/ID from URL."""
        parsed = urlparse(url)
        path = parsed.path.strip('/')
        
        # Handle different URL formats
        if path.startswith('id'):
            return path  # id123456
        elif '/' in path:
            return path.split('/')[0]
        else:
            return path
    
    def find_photo_urls(self, url: str) -> List[Dict[str, str]]:
        """Find photo URLs from VK profile."""
        photos = []
        
        try:
            # Get profile page HTML
            html = self.downloader.get_html(url)
            if not html or not BS4_AVAILABLE:
                return photos
            
            soup = BeautifulSoup(html, 'html.parser')
            
            # 1. Profile photo (avatar)
            avatar = soup.select_one('.page_avatar img, .profile_photo img, .owner_panel_img img')
            if avatar:
                src = avatar.get('src') or avatar.get('data-src')
                if src:
                    # Get highest resolution version
                    src = self._get_highest_res(src)
                    photos.append({'url': src, 'type': 'profile'})
            
            # 2. Photos from posts/wall
            # Look for photo attachments in wall posts
            post_photos = soup.select('.wall_text .page_post_thumb_wrap img, .post_image img, .thumb_map img')
            for img in post_photos[:30]:
                src = img.get('src') or img.get('data-src')
                if src and 'userapi.com' in src:
                    src = self._get_highest_res(src)
                    photos.append({'url': src, 'type': 'post'})
            
            # 3. Photo albums thumbnails
            album_photos = soup.select('.photos_container img, .photos_row img, .page_photos_module img')
            for img in album_photos[:20]:
                src = img.get('src') or img.get('data-src')
                if src and 'userapi.com' in src:
                    src = self._get_highest_res(src)
                    photos.append({'url': src, 'type': 'gallery'})
            
            # 4. Background/cover images
            cover = soup.select_one('.page_cover img, .profile_cover img')
            if cover:
                src = cover.get('src') or cover.get('data-src')
                if src:
                    photos.append({'url': src, 'type': 'cover'})
            
            # 5. Search for all image URLs in the page source
            # This catches dynamically loaded images
            img_pattern = re.compile(r'https?://[^\s"\'<>]+\.(?:jpg|jpeg|png|webp)(?:\?[^\s"\'<>]*)?', re.I)
            for match in img_pattern.findall(html):
                if 'userapi.com' in match and match not in [p['url'] for p in photos]:
                    photos.append({'url': self._get_highest_res(match), 'type': 'found'})
                    if len(photos) >= self.max_photos:
                        break
            
        except Exception as e:
            pass
        
        # Remove duplicates while preserving order
        seen = set()
        unique_photos = []
        for p in photos:
            if p['url'] not in seen:
                seen.add(p['url'])
                unique_photos.append(p)
        
        return unique_photos
    
    def _get_highest_res(self, url: str) -> str:
        """Convert VK photo URL to highest resolution."""
        # VK uses letter suffixes for sizes: s, m, o, p, q, r, x, y, z, w
        # Try to get the largest version
        for size in self.PHOTO_SIZES:
            test_url = re.sub(r'/[a-z]_([a-f0-9]+\.)', f'/{size}_\\1', url)
            if test_url != url:
                return test_url
        return url


class InstagramScraper(BasePlatformScraper):
    """
    Instagram photo scraper.
    Scrapes profile picture and visible post thumbnails.
    Note: Full Instagram scraping requires authentication.
    """
    
    PLATFORM_NAME = "instagram"
    MAX_PHOTOS_PER_PROFILE = 30
    
    def can_handle(self, url: str) -> bool:
        return 'instagram.com' in url
    
    def extract_username(self, url: str) -> str:
        parsed = urlparse(url)
        path = parsed.path.strip('/')
        if path:
            return path.split('/')[0]
        return ""
    
    def find_photo_urls(self, url: str) -> List[Dict[str, str]]:
        """Find photo URLs from Instagram profile."""
        photos = []
        
        try:
            html = self.downloader.get_html(url)
            if not html:
                return photos
            
            # 1. Look for profile picture in meta tags
            og_image = re.search(r'<meta property="og:image" content="([^"]+)"', html)
            if og_image:
                photos.append({'url': og_image.group(1), 'type': 'profile'})
            
            # 2. Search for image URLs in page source (Instagram CDN)
            if BS4_AVAILABLE:
                soup = BeautifulSoup(html, 'html.parser')
                
                # Profile pic
                for img in soup.select('img[alt*="profile picture"], img.be0x7'):
                    src = img.get('src')
                    if src and 'cdninstagram.com' in src:
                        photos.append({'url': src, 'type': 'profile'})
                
                # Post thumbnails
                for img in soup.select('article img, ._aagv img'):
                    src = img.get('src')
                    if src and 'cdninstagram.com' in src:
                        photos.append({'url': src, 'type': 'post'})
            
            # 3. Regex fallback for CDN URLs
            cdn_pattern = re.compile(r'https?://[^\s"\'<>]*cdninstagram\.com[^\s"\'<>]+\.(?:jpg|jpeg|png|webp)', re.I)
            for match in cdn_pattern.findall(html):
                clean_url = match.replace('\\u0026', '&')
                if clean_url not in [p['url'] for p in photos]:
                    photos.append({'url': clean_url, 'type': 'found'})
            
        except Exception:
            pass
        
        # Deduplicate
        seen = set()
        return [p for p in photos if not (p['url'] in seen or seen.add(p['url']))]


class TelegramScraper(BasePlatformScraper):
    """
    Telegram profile photo scraper.
    Scrapes from t.me profile pages.
    """
    
    PLATFORM_NAME = "telegram"
    MAX_PHOTOS_PER_PROFILE = 10
    
    def can_handle(self, url: str) -> bool:
        return 't.me' in url or 'telegram.me' in url or 'telegram.org' in url
    
    def extract_username(self, url: str) -> str:
        parsed = urlparse(url)
        path = parsed.path.strip('/')
        if path.startswith('s/'):
            path = path[2:]
        return path.split('/')[0] if path else ""
    
    def find_photo_urls(self, url: str) -> List[Dict[str, str]]:
        """Find photo URLs from Telegram profile."""
        photos = []
        
        try:
            html = self.downloader.get_html(url)
            if not html or not BS4_AVAILABLE:
                return photos
            
            soup = BeautifulSoup(html, 'html.parser')
            
            # Profile photo
            profile_photo = soup.select_one('.tgme_page_photo_image img, .tgme_widget_message_photo_wrap img')
            if profile_photo:
                src = profile_photo.get('src')
                if src:
                    photos.append({'url': src, 'type': 'profile'})
            
            # Background style images
            for elem in soup.select('[style*="background-image"]'):
                style = elem.get('style', '')
                match = re.search(r'url\(["\']?([^"\')\s]+)["\']?\)', style)
                if match:
                    photos.append({'url': match.group(1), 'type': 'background'})
            
            # Any telegram CDN images
            for img in soup.find_all('img'):
                src = img.get('src', '')
                if 'telegram' in src or 'cdn' in src:
                    photos.append({'url': src, 'type': 'found'})
            
        except Exception:
            pass
        
        seen = set()
        return [p for p in photos if not (p['url'] in seen or seen.add(p['url']))]


class OKScraper(BasePlatformScraper):
    """
    Odnoklassniki (OK.ru) photo scraper.
    Scrapes profile and available photos.
    """
    
    PLATFORM_NAME = "ok"
    MAX_PHOTOS_PER_PROFILE = 50
    
    def can_handle(self, url: str) -> bool:
        return 'ok.ru' in url or 'odnoklassniki.ru' in url
    
    def extract_username(self, url: str) -> str:
        parsed = urlparse(url)
        path = parsed.path.strip('/')
        if path.startswith('profile/'):
            return path.replace('profile/', '')
        return path.split('/')[0] if path else ""
    
    def find_photo_urls(self, url: str) -> List[Dict[str, str]]:
        """Find photo URLs from OK profile."""
        photos = []
        
        try:
            html = self.downloader.get_html(url)
            if not html or not BS4_AVAILABLE:
                return photos
            
            soup = BeautifulSoup(html, 'html.parser')
            
            # Profile photo
            avatar = soup.select_one('.entity-avatar img, .user-avatar img, .profile-user-avatar img')
            if avatar:
                src = avatar.get('src') or avatar.get('data-src')
                if src:
                    photos.append({'url': src, 'type': 'profile'})
            
            # Photo album images
            for img in soup.select('.photo-card img, .ugrid_i img, .feed-photo img'):
                src = img.get('src') or img.get('data-src')
                if src:
                    # Try to get higher resolution
                    src = re.sub(r'/[a-z]?_([a-z0-9]+\.)', '/b_\\1', src)
                    photos.append({'url': src, 'type': 'gallery'})
            
            # Wall/feed images
            for img in soup.select('.feed_img img, .media-inner img'):
                src = img.get('src') or img.get('data-src')
                if src:
                    photos.append({'url': src, 'type': 'post'})
            
        except Exception:
            pass
        
        seen = set()
        return [p for p in photos if not (p['url'] in seen or seen.add(p['url']))]


class GenericScraper(BasePlatformScraper):
    """
    Generic web scraper for any website.
    Extracts all visible images from the page.
    """
    
    PLATFORM_NAME = "generic"
    MAX_PHOTOS_PER_PROFILE = 30
    
    def can_handle(self, url: str) -> bool:
        return True  # Handles anything
    
    def extract_username(self, url: str) -> str:
        parsed = urlparse(url)
        path = parsed.path.strip('/')
        return path.split('/')[0] if path else parsed.netloc
    
    def find_photo_urls(self, url: str) -> List[Dict[str, str]]:
        """Find all image URLs from any webpage."""
        photos = []
        
        try:
            html = self.downloader.get_html(url)
            if not html:
                return photos
            
            base_url = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
            
            if BS4_AVAILABLE:
                soup = BeautifulSoup(html, 'html.parser')
                
                # Find all img tags
                for img in soup.find_all('img'):
                    src = img.get('src') or img.get('data-src') or img.get('data-lazy-src')
                    if src:
                        # Handle relative URLs
                        if src.startswith('//'):
                            src = 'https:' + src
                        elif src.startswith('/'):
                            src = urljoin(base_url, src)
                        elif not src.startswith('http'):
                            src = urljoin(url, src)
                        
                        # Filter out small images (likely icons)
                        width = img.get('width', '999')
                        height = img.get('height', '999')
                        try:
                            if int(width) >= 100 and int(height) >= 100:
                                photos.append({'url': src, 'type': 'found'})
                        except:
                            photos.append({'url': src, 'type': 'found'})
                
                # Find background images in style attributes
                for elem in soup.select('[style*="background"]'):
                    style = elem.get('style', '')
                    match = re.search(r'url\(["\']?([^"\')\s]+)["\']?\)', style)
                    if match:
                        bg_url = match.group(1)
                        if not bg_url.startswith('http'):
                            bg_url = urljoin(url, bg_url)
                        photos.append({'url': bg_url, 'type': 'background'})
            
            # Regex fallback for any image URLs
            img_pattern = re.compile(r'https?://[^\s"\'<>]+\.(?:jpg|jpeg|png|webp|gif)(?:\?[^\s"\'<>]*)?', re.I)
            for match in img_pattern.findall(html):
                if match not in [p['url'] for p in photos]:
                    photos.append({'url': match, 'type': 'found'})
            
        except Exception:
            pass
        
        seen = set()
        return [p for p in photos if not (p['url'] in seen or seen.add(p['url']))]


# =============================================================================
# MAIN HARVESTER CLASS
# =============================================================================

class PhotoHarvester:
    """
    Main photo harvesting orchestrator.
    Automatically selects the best scraper for each URL.
    """
    
    def __init__(self,
                 max_photos_per_profile: int = 50,
                 download_delay: float = 0.5,
                 request_delay: float = 1.0,
                 timeout: int = 30,
                 proxy: Optional[str] = None,
                 temp_dir: Optional[str] = None):
        """
        Initialize the harvester.
        
        Args:
            max_photos_per_profile: Max photos to download per profile
            download_delay: Delay between photo downloads
            request_delay: Delay between page requests
            timeout: HTTP request timeout
            proxy: Optional proxy URL
            temp_dir: Custom temp directory
        """
        self.max_photos = max_photos_per_profile
        self.download_delay = download_delay
        self.request_delay = request_delay
        
        # Initialize components
        self.temp_manager = TempPhotoManager(temp_dir)
        self.downloader = PhotoDownloader(
            timeout=timeout,
            delay_between_downloads=download_delay,
            proxy=proxy
        )
        
        # Initialize platform scrapers (order matters - specific before generic)
        self.scrapers = [
            VKScraper(self.downloader, self.temp_manager, max_photos_per_profile, request_delay),
            InstagramScraper(self.downloader, self.temp_manager, max_photos_per_profile, request_delay),
            TelegramScraper(self.downloader, self.temp_manager, max_photos_per_profile, request_delay),
            OKScraper(self.downloader, self.temp_manager, max_photos_per_profile, request_delay),
            GenericScraper(self.downloader, self.temp_manager, max_photos_per_profile, request_delay),
        ]
    
    def get_scraper(self, url: str) -> BasePlatformScraper:
        """Get the appropriate scraper for a URL."""
        for scraper in self.scrapers:
            if scraper.can_handle(url):
                return scraper
        return self.scrapers[-1]  # Generic scraper as fallback
    
    def harvest_profile(self, url: str) -> HarvestResult:
        """
        Harvest photos from a single profile URL.
        
        Args:
            url: Profile URL
            
        Returns:
            HarvestResult with downloaded photos
        """
        scraper = self.get_scraper(url)
        result = scraper.harvest(url)
        return result
    
    def harvest_profiles(self, 
                         urls: List[str],
                         progress_callback: Optional[callable] = None) -> List[HarvestResult]:
        """
        Harvest photos from multiple profiles.
        
        Args:
            urls: List of profile URLs
            progress_callback: Optional callback(current, total, url, photos_found)
            
        Returns:
            List of HarvestResults
        """
        results = []
        total = len(urls)
        
        for i, url in enumerate(urls, 1):
            if progress_callback:
                progress_callback(i, total, url, 0)
            
            result = self.harvest_profile(url)
            results.append(result)
            
            if progress_callback:
                progress_callback(i, total, url, result.total_downloaded)
            
            # Rate limiting between profiles
            if i < total:
                time.sleep(self.request_delay)
        
        return results
    
    def harvest_and_yield(self, url: str) -> Generator[HarvestedPhoto, None, None]:
        """
        Harvest photos one at a time (generator).
        Allows processing each photo before moving to next.
        
        Yields:
            HarvestedPhoto objects one at a time
        """
        scraper = self.get_scraper(url)
        photo_infos = scraper.find_photo_urls(url)
        
        for i, info in enumerate(photo_infos[:self.max_photos]):
            photo_url = info.get('url', '')
            photo_type = info.get('type', 'unknown')
            
            if not photo_url:
                continue
            
            photo = HarvestedPhoto(
                url=photo_url,
                platform=scraper.PLATFORM_NAME,
                photo_type=photo_type
            )
            
            # Generate temp path
            ext = Path(urlparse(photo_url).path).suffix or '.jpg'
            if ext.lower() not in PhotoDownloader.IMAGE_EXTENSIONS:
                ext = '.jpg'
            photo.local_path = self.temp_manager.get_temp_path(photo_url, ext)
            
            # Download
            success, error = self.downloader.download(photo_url, photo.local_path)
            
            if success:
                photo.downloaded = True
                photo.file_size = os.path.getsize(photo.local_path)
            else:
                photo.error = error
                photo.local_path = None
            
            yield photo
            
            # Rate limiting
            time.sleep(self.download_delay)
    
    def cleanup(self, result: Optional[HarvestResult] = None):
        """
        Cleanup downloaded photos.
        
        Args:
            result: Specific result to cleanup, or None for all
        """
        if result:
            result.cleanup_all()
        else:
            self.temp_manager.cleanup_session()
        gc.collect()
    
    def cleanup_all(self):
        """Cleanup everything including session directory."""
        self.temp_manager.cleanup_all()
        self.downloader.close()
        gc.collect()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup_all()


# =============================================================================
# TESTING
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Photo Harvester Test")
    print("=" * 60)
    
    if not BS4_AVAILABLE:
        print("\n⚠️ BeautifulSoup not installed!")
        print("Install with: pip install beautifulsoup4")
    
    # Test URL detection
    test_urls = [
        "https://vk.com/durov",
        "https://instagram.com/instagram",
        "https://t.me/durov",
        "https://ok.ru/profile/123456",
        "https://example.com/user/test",
    ]
    
    print("\n📋 URL Platform Detection Test:")
    with PhotoHarvester() as harvester:
        for url in test_urls:
            scraper = harvester.get_scraper(url)
            print(f"  {url[:40]:40} -> {scraper.PLATFORM_NAME}")
    
    print("\n✅ Photo Harvester initialized successfully")
    print("\nUsage:")
    print("  with PhotoHarvester() as harvester:")
    print("      result = harvester.harvest_profile('https://vk.com/username')")
    print("      for photo in result.photos:")
    print("          # Process photo.local_path")
    print("          photo.cleanup()  # Delete after processing")
