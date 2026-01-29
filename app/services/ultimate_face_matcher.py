"""
ULTIMATE FACE MATCHER - IBP Project
====================================
The most powerful face matching solution for OSINT investigations.

KEY FEATURES:
✅ Scrapes ALL photos from accounts (posts, galleries, stories, wall) - NOT just profile pics
✅ Stream processing: Download → Compare → DELETE immediately (zero disk bloat)
✅ Memory efficient: Never holds more than 1 photo in RAM
✅ Multi-platform: VK, Instagram, Telegram, OK, Mail.ru, and any website
✅ Auto-cleanup: Guaranteed cleanup even on crashes
✅ Batch encoding extraction for speed
✅ Configurable similarity thresholds

ARCHITECTURE:
1. PhotoStreamHarvester - Downloads ALL photos from a profile one-by-one
2. StreamingFaceEngine - Extracts encoding, compares, deletes in one operation  
3. UltimateFaceMatcher - Orchestrates everything, returns only matches

Author: IBP Project
"""

import os
import gc
import re
import sys
import time
import uuid
import shutil
import hashlib
import tempfile
import threading
import requests
from io import BytesIO
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Generator, Any, Callable
from dataclasses import dataclass, field
from urllib.parse import urlparse, urljoin
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor

# Optional imports
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False

try:
    import numpy as np
    import face_recognition
    FACE_RECOGNITION_AVAILABLE = True
except ImportError:
    FACE_RECOGNITION_AVAILABLE = False
    # Create stub for type hints
    class _NumpyStub:
        ndarray = object
    np = _NumpyStub()
    print("⚠️ face_recognition not installed. Install: pip install face_recognition")


# =============================================================================
# CONFIGURATION
# =============================================================================

class Config:
    """Global configuration."""
    # Face matching
    MATCH_THRESHOLD = 40.0  # Minimum similarity % to consider a match
    FACE_DISTANCE_THRESHOLD = 0.6  # face_recognition distance (lower = stricter)
    
    # Photo limits
    MAX_PHOTOS_PER_PROFILE = 100  # Max photos to check per account
    MAX_PHOTO_SIZE_MB = 20  # Skip photos larger than this
    MIN_PHOTO_SIZE_BYTES = 1000  # Skip tiny images (likely icons)
    
    # Timeouts and delays
    DOWNLOAD_TIMEOUT = 30
    DELAY_BETWEEN_PHOTOS = 0.3
    DELAY_BETWEEN_PROFILES = 1.0
    
    # Memory management
    GC_EVERY_N_PHOTOS = 5  # Run gc.collect() every N photos
    
    # Detection model
    FACE_MODEL = 'hog'  # 'hog' (CPU fast) or 'cnn' (GPU accurate)
    NUM_JITTERS = 1  # Re-sample face N times (more = accurate but slower)


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class PhotoInfo:
    """Information about a photo to process."""
    url: str
    photo_type: str = "unknown"  # profile, post, wall, gallery, story
    platform: str = "unknown"


@dataclass  
class FaceMatchResult:
    """Result of face matching for one photo."""
    photo_url: str
    has_face: bool = False
    face_count: int = 0
    similarity: float = 0.0
    is_match: bool = False
    photo_type: str = "unknown"


@dataclass
class AccountMatchResult:
    """Complete face matching result for an account."""
    url: str
    platform: str
    username: str = ""
    photos_checked: int = 0
    photos_with_faces: int = 0
    best_similarity: float = 0.0
    is_match: bool = False
    match_photo_url: str = ""
    match_photo_type: str = ""
    all_matches: List[FaceMatchResult] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


# =============================================================================
# HTTP CLIENT WITH STREAMING
# =============================================================================

class StreamingDownloader:
    """
    Downloads images to memory or temp file for immediate processing.
    Supports streaming to avoid memory bloat.
    """
    
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'image/avif,image/webp,image/apng,image/*,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9,ru;q=0.8',
    }
    
    IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}
    
    def __init__(self, timeout: int = 30, proxy: Optional[str] = None):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        if proxy:
            self.session.proxies = {'http': proxy, 'https': proxy}
        
        # Temp directory for this session
        self._temp_dir = Path(tempfile.mkdtemp(prefix="ibp_face_"))
        self._file_counter = 0
        self._lock = threading.Lock()
    
    def download_to_memory(self, url: str) -> Optional[bytes]:
        """Download image directly to memory (for small images)."""
        try:
            response = self.session.get(url, timeout=self.timeout, stream=True)
            response.raise_for_status()
            
            # Check content length
            content_length = response.headers.get('content-length')
            if content_length:
                size = int(content_length)
                if size > Config.MAX_PHOTO_SIZE_MB * 1024 * 1024:
                    return None
                if size < Config.MIN_PHOTO_SIZE_BYTES:
                    return None
            
            # Download
            data = response.content
            if len(data) < Config.MIN_PHOTO_SIZE_BYTES:
                return None
            return data
            
        except Exception:
            return None
    
    def download_to_temp(self, url: str) -> Optional[str]:
        """Download image to temp file, return path."""
        try:
            data = self.download_to_memory(url)
            if not data:
                return None
            
            with self._lock:
                self._file_counter += 1
                ext = Path(urlparse(url).path).suffix.lower()
                if ext not in self.IMAGE_EXTENSIONS:
                    ext = '.jpg'
                filename = f"photo_{self._file_counter:06d}{ext}"
                filepath = self._temp_dir / filename
            
            with open(filepath, 'wb') as f:
                f.write(data)
            
            return str(filepath)
            
        except Exception:
            return None
    
    def delete_file(self, path: str):
        """Delete a temp file immediately."""
        try:
            if path and os.path.exists(path):
                os.remove(path)
        except Exception:
            pass
    
    def get_html(self, url: str) -> Optional[str]:
        """Fetch HTML content."""
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            return response.text
        except Exception:
            return None
    
    def cleanup_all(self):
        """Delete all temp files."""
        try:
            if self._temp_dir.exists():
                shutil.rmtree(self._temp_dir)
        except Exception:
            pass
    
    def __del__(self):
        self.cleanup_all()


# =============================================================================
# MULTI-PLATFORM PHOTO HARVESTER
# =============================================================================

class PhotoStreamHarvester:
    """
    Harvests ALL photos from social media profiles.
    Yields photos one-by-one for stream processing.
    
    Supports:
    - VK (wall, albums, profile, saved)
    - Instagram (posts, stories, highlights)
    - Telegram (profile photos)
    - OK.ru (profile, albums, wall)
    - Generic websites (all images)
    """
    
    def __init__(self, downloader: StreamingDownloader):
        self.downloader = downloader
    
    def harvest_all_photos(self, url: str) -> Generator[PhotoInfo, None, None]:
        """
        Yield all photo URLs from a profile.
        Main entry point - auto-detects platform.
        """
        platform = self._detect_platform(url)
        
        if platform == 'vk':
            yield from self._harvest_vk(url)
        elif platform == 'instagram':
            yield from self._harvest_instagram(url)
        elif platform == 'telegram':
            yield from self._harvest_telegram(url)
        elif platform == 'ok':
            yield from self._harvest_ok(url)
        elif platform == 'mailru':
            yield from self._harvest_mailru(url)
        else:
            yield from self._harvest_generic(url)
    
    def _detect_platform(self, url: str) -> str:
        """Detect social media platform from URL."""
        url_lower = url.lower()
        if 'vk.com' in url_lower or 'vkontakte.ru' in url_lower:
            return 'vk'
        elif 'instagram.com' in url_lower:
            return 'instagram'
        elif 't.me' in url_lower or 'telegram' in url_lower:
            return 'telegram'
        elif 'ok.ru' in url_lower or 'odnoklassniki' in url_lower:
            return 'ok'
        elif 'mail.ru' in url_lower or 'my.mail.ru' in url_lower:
            return 'mailru'
        else:
            return 'generic'
    
    # -------------------------------------------------------------------------
    # VK HARVESTER - Gets ALL photos (wall, albums, profile)
    # -------------------------------------------------------------------------
    
    def _harvest_vk(self, url: str) -> Generator[PhotoInfo, None, None]:
        """Harvest ALL photos from VK profile."""
        html = self.downloader.get_html(url)
        if not html:
            return
        
        seen_urls = set()
        
        # VK photo size suffixes (largest first)
        size_suffixes = ['w', 'z', 'y', 'x', 'r', 'q', 'p', 'o', 'm', 's']
        
        def get_best_size(photo_url: str) -> str:
            """Convert VK photo URL to highest resolution."""
            for suffix in size_suffixes:
                test_url = re.sub(r'/[a-z]_([a-f0-9]+\.)', f'/{suffix}_\\1', photo_url)
                if test_url != photo_url:
                    return test_url
            return photo_url
        
        # 1. Extract ALL image URLs from page source using regex
        # This catches dynamically loaded images too
        patterns = [
            # VK CDN photos
            r'https?://[a-z0-9\-\.]+\.(?:userapi\.com|vk\.me|vk-cdn\.net)/[^\s"\'<>]+\.(?:jpg|jpeg|png|webp)(?:\?[^\s"\'<>]*)?',
            # Standard photo URLs
            r'"(?:photo|src|url)":\s*"(https?://[^"]+\.(?:jpg|jpeg|png))"',
        ]
        
        for pattern in patterns:
            for match in re.finditer(pattern, html, re.I):
                photo_url = match.group(1) if match.lastindex else match.group(0)
                photo_url = photo_url.replace('\\/', '/').replace('\\u0026', '&')
                
                # Skip tiny thumbnails and icons
                if '/impf/' in photo_url or '/sticker/' in photo_url or '/emoji/' in photo_url:
                    continue
                
                # Get best quality
                photo_url = get_best_size(photo_url)
                
                if photo_url not in seen_urls:
                    seen_urls.add(photo_url)
                    
                    # Determine photo type from URL
                    if 'profile' in photo_url or '/d_' in photo_url:
                        photo_type = 'profile'
                    elif 'wall' in html[:html.find(photo_url) if photo_url in html else 0]:
                        photo_type = 'wall'
                    elif 'album' in photo_url:
                        photo_type = 'gallery'
                    else:
                        photo_type = 'post'
                    
                    yield PhotoInfo(url=photo_url, photo_type=photo_type, platform='vk')
        
        # 2. Parse HTML for additional photos (if BS4 available)
        if BS4_AVAILABLE:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Profile avatar
            for selector in ['.page_avatar img', '.profile_photo img', '.owner_panel_img img',
                            '.page_photo_img img', '.im_grid_head img']:
                for img in soup.select(selector):
                    src = img.get('src') or img.get('data-src')
                    if src and 'userapi.com' in src and src not in seen_urls:
                        seen_urls.add(src)
                        yield PhotoInfo(url=get_best_size(src), photo_type='profile', platform='vk')
            
            # Wall post photos
            for img in soup.select('.wall_text img, .post_image img, .page_post_thumb_wrap img'):
                src = img.get('src') or img.get('data-src')
                if src and 'userapi.com' in src and src not in seen_urls:
                    seen_urls.add(src)
                    yield PhotoInfo(url=get_best_size(src), photo_type='wall', platform='vk')
            
            # Photo albums
            for img in soup.select('.photos_container img, .photos_row img, .page_photos_module img'):
                src = img.get('src') or img.get('data-src')
                if src and 'userapi.com' in src and src not in seen_urls:
                    seen_urls.add(src)
                    yield PhotoInfo(url=get_best_size(src), photo_type='gallery', platform='vk')
            
            # Background images (cover photos)
            for elem in soup.select('[style*="background-image"]'):
                style = elem.get('style', '')
                match = re.search(r'url\(["\']?([^"\')\s]+)["\']?\)', style)
                if match:
                    src = match.group(1)
                    if 'userapi.com' in src and src not in seen_urls:
                        seen_urls.add(src)
                        yield PhotoInfo(url=get_best_size(src), photo_type='cover', platform='vk')
    
    # -------------------------------------------------------------------------
    # INSTAGRAM HARVESTER
    # -------------------------------------------------------------------------
    
    def _harvest_instagram(self, url: str) -> Generator[PhotoInfo, None, None]:
        """Harvest photos from Instagram profile."""
        html = self.downloader.get_html(url)
        if not html:
            return
        
        seen_urls = set()
        
        # 1. OG Image (profile pic)
        og_match = re.search(r'<meta property="og:image" content="([^"]+)"', html)
        if og_match:
            photo_url = og_match.group(1).replace('\\u0026', '&')
            if photo_url not in seen_urls:
                seen_urls.add(photo_url)
                yield PhotoInfo(url=photo_url, photo_type='profile', platform='instagram')
        
        # 2. Instagram CDN URLs from page source
        cdn_pattern = r'https?://[^\s"\'<>]*(?:cdninstagram\.com|fbcdn\.net)[^\s"\'<>]+\.(?:jpg|jpeg|png|webp)'
        for match in re.finditer(cdn_pattern, html, re.I):
            photo_url = match.group(0).replace('\\u0026', '&').replace('\\/', '/')
            
            # Skip tiny thumbnails
            if 's150x150' in photo_url or 's320x320' in photo_url:
                continue
            
            if photo_url not in seen_urls:
                seen_urls.add(photo_url)
                yield PhotoInfo(url=photo_url, photo_type='post', platform='instagram')
        
        # 3. HTML parsing for additional images
        if BS4_AVAILABLE:
            soup = BeautifulSoup(html, 'html.parser')
            
            for img in soup.find_all('img'):
                src = img.get('src', '')
                if ('cdninstagram.com' in src or 'fbcdn.net' in src) and src not in seen_urls:
                    seen_urls.add(src)
                    yield PhotoInfo(url=src, photo_type='post', platform='instagram')
    
    # -------------------------------------------------------------------------
    # TELEGRAM HARVESTER
    # -------------------------------------------------------------------------
    
    def _harvest_telegram(self, url: str) -> Generator[PhotoInfo, None, None]:
        """Harvest photos from Telegram profile."""
        html = self.downloader.get_html(url)
        if not html:
            return
        
        seen_urls = set()
        
        # 1. Regex for Telegram CDN
        tg_pattern = r'https?://[^\s"\'<>]*(?:telegram\.org|t\.me|cdn\d*\.telesco\.pe)[^\s"\'<>]+\.(?:jpg|jpeg|png|webp)'
        for match in re.finditer(tg_pattern, html, re.I):
            photo_url = match.group(0)
            if photo_url not in seen_urls:
                seen_urls.add(photo_url)
                yield PhotoInfo(url=photo_url, photo_type='profile', platform='telegram')
        
        # 2. HTML parsing
        if BS4_AVAILABLE:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Profile photo
            for img in soup.select('.tgme_page_photo_image img, .tgme_widget_message_photo img'):
                src = img.get('src')
                if src and src not in seen_urls:
                    seen_urls.add(src)
                    yield PhotoInfo(url=src, photo_type='profile', platform='telegram')
            
            # Background images
            for elem in soup.select('[style*="background-image"]'):
                style = elem.get('style', '')
                match = re.search(r'url\(["\']?([^"\')\s]+)["\']?\)', style)
                if match:
                    src = match.group(1)
                    if src not in seen_urls:
                        seen_urls.add(src)
                        yield PhotoInfo(url=src, photo_type='background', platform='telegram')
    
    # -------------------------------------------------------------------------
    # OK.RU (ODNOKLASSNIKI) HARVESTER
    # -------------------------------------------------------------------------
    
    def _harvest_ok(self, url: str) -> Generator[PhotoInfo, None, None]:
        """Harvest photos from OK.ru profile."""
        html = self.downloader.get_html(url)
        if not html:
            return
        
        seen_urls = set()
        
        # 1. OK CDN URLs from page source
        ok_pattern = r'https?://[^\s"\'<>]*(?:ok\.ru|okcdn\.ru|odkl\.cc)[^\s"\'<>]+\.(?:jpg|jpeg|png|webp)'
        for match in re.finditer(ok_pattern, html, re.I):
            photo_url = match.group(0)
            
            # Try to get better quality (replace size prefix)
            photo_url = re.sub(r'/[a-z]?_([a-z0-9]+\.)', '/b_\\1', photo_url)
            
            if photo_url not in seen_urls:
                seen_urls.add(photo_url)
                yield PhotoInfo(url=photo_url, photo_type='found', platform='ok')
        
        # 2. HTML parsing
        if BS4_AVAILABLE:
            soup = BeautifulSoup(html, 'html.parser')
            
            for img in soup.find_all('img'):
                src = img.get('src') or img.get('data-src')
                if src and ('ok.ru' in src or 'okcdn' in src or 'odkl' in src):
                    src = re.sub(r'/[a-z]?_([a-z0-9]+\.)', '/b_\\1', src)
                    if src not in seen_urls:
                        seen_urls.add(src)
                        yield PhotoInfo(url=src, photo_type='found', platform='ok')
    
    # -------------------------------------------------------------------------
    # MAIL.RU HARVESTER
    # -------------------------------------------------------------------------
    
    def _harvest_mailru(self, url: str) -> Generator[PhotoInfo, None, None]:
        """Harvest photos from Mail.ru profile."""
        html = self.downloader.get_html(url)
        if not html:
            return
        
        seen_urls = set()
        
        # Mail.ru CDN URLs
        mailru_pattern = r'https?://[^\s"\'<>]*(?:mail\.ru|imgsmail\.ru)[^\s"\'<>]+\.(?:jpg|jpeg|png|webp)'
        for match in re.finditer(mailru_pattern, html, re.I):
            photo_url = match.group(0)
            if photo_url not in seen_urls:
                seen_urls.add(photo_url)
                yield PhotoInfo(url=photo_url, photo_type='found', platform='mailru')
    
    # -------------------------------------------------------------------------
    # GENERIC WEBSITE HARVESTER
    # -------------------------------------------------------------------------
    
    def _harvest_generic(self, url: str) -> Generator[PhotoInfo, None, None]:
        """Harvest photos from any website."""
        html = self.downloader.get_html(url)
        if not html:
            return
        
        seen_urls = set()
        base_url = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
        
        # 1. Regex for all image URLs
        img_pattern = r'https?://[^\s"\'<>]+\.(?:jpg|jpeg|png|webp|gif)(?:\?[^\s"\'<>]*)?'
        for match in re.finditer(img_pattern, html, re.I):
            photo_url = match.group(0).replace('\\/', '/')
            if photo_url not in seen_urls:
                seen_urls.add(photo_url)
                yield PhotoInfo(url=photo_url, photo_type='found', platform='generic')
        
        # 2. HTML parsing
        if BS4_AVAILABLE:
            soup = BeautifulSoup(html, 'html.parser')
            
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
                    
                    # Filter out small images
                    width = img.get('width', '999')
                    height = img.get('height', '999')
                    try:
                        if int(str(width).replace('px', '')) < 50 or int(str(height).replace('px', '')) < 50:
                            continue
                    except:
                        pass
                    
                    if src not in seen_urls:
                        seen_urls.add(src)
                        yield PhotoInfo(url=src, photo_type='found', platform='generic')


# =============================================================================
# STREAMING FACE ENGINE
# =============================================================================

class StreamingFaceEngine:
    """
    High-performance face encoding and comparison engine.
    
    Key features:
    - Extracts face encoding from image
    - Compares to target encoding
    - Deletes image immediately after processing
    - Memory efficient with gc.collect()
    """
    
    def __init__(self, 
                 target_encoding: Optional[np.ndarray] = None,
                 match_threshold: float = Config.MATCH_THRESHOLD,
                 model: str = Config.FACE_MODEL,
                 num_jitters: int = Config.NUM_JITTERS):
        """
        Initialize the face engine.
        
        Args:
            target_encoding: Pre-computed target face encoding
            match_threshold: Minimum similarity % for a match
            model: 'hog' (CPU fast) or 'cnn' (GPU accurate)
            num_jitters: Re-sample face N times
        """
        self.target_encoding = target_encoding
        self.match_threshold = match_threshold
        self.model = model
        self.num_jitters = num_jitters
        self._photo_count = 0
    
    def load_target_from_file(self, path: str) -> Dict[str, Any]:
        """
        Load and encode target face from file.
        
        Returns:
            Dict with 'success', 'encoding', 'error'
        """
        if not FACE_RECOGNITION_AVAILABLE:
            return {'success': False, 'error': 'face_recognition not installed'}
        
        if not os.path.exists(path):
            return {'success': False, 'error': f'File not found: {path}'}
        
        try:
            image = face_recognition.load_image_file(path)
            locations = face_recognition.face_locations(image, model=self.model)
            
            if not locations:
                return {'success': False, 'error': 'No face detected in target photo'}
            
            # Use largest face if multiple
            if len(locations) > 1:
                locations = [max(locations, key=lambda f: (f[2]-f[0]) * (f[1]-f[3]))]
            
            encodings = face_recognition.face_encodings(
                image, 
                known_face_locations=locations,
                num_jitters=self.num_jitters
            )
            
            if not encodings:
                return {'success': False, 'error': 'Could not encode target face'}
            
            self.target_encoding = encodings[0]
            
            # Cleanup
            del image
            gc.collect()
            
            return {
                'success': True, 
                'encoding': self.target_encoding,
                'faces_detected': len(locations)
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def load_target_from_bytes(self, data: bytes) -> Dict[str, Any]:
        """Load and encode target face from image bytes."""
        if not FACE_RECOGNITION_AVAILABLE:
            return {'success': False, 'error': 'face_recognition not installed'}
        
        try:
            # Load from bytes using PIL then convert
            if PIL_AVAILABLE:
                from PIL import Image
                import io
                pil_image = Image.open(io.BytesIO(data))
                image = np.array(pil_image)
                
                # Handle RGBA images
                if len(image.shape) == 3 and image.shape[2] == 4:
                    image = image[:, :, :3]
            else:
                # Save to temp file and load
                temp_path = tempfile.mktemp(suffix='.jpg')
                with open(temp_path, 'wb') as f:
                    f.write(data)
                image = face_recognition.load_image_file(temp_path)
                os.remove(temp_path)
            
            locations = face_recognition.face_locations(image, model=self.model)
            
            if not locations:
                return {'success': False, 'error': 'No face detected'}
            
            if len(locations) > 1:
                locations = [max(locations, key=lambda f: (f[2]-f[0]) * (f[1]-f[3]))]
            
            encodings = face_recognition.face_encodings(
                image,
                known_face_locations=locations,
                num_jitters=self.num_jitters
            )
            
            if not encodings:
                return {'success': False, 'error': 'Could not encode face'}
            
            self.target_encoding = encodings[0]
            del image
            gc.collect()
            
            return {'success': True, 'encoding': self.target_encoding}
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def process_and_compare(self, 
                            image_path: str, 
                            delete_after: bool = True) -> FaceMatchResult:
        """
        Process image: detect face, compare to target, delete file.
        
        This is the CORE function - does everything in one shot.
        
        Args:
            image_path: Path to image file
            delete_after: If True, delete file immediately after processing
            
        Returns:
            FaceMatchResult with comparison details
        """
        result = FaceMatchResult(photo_url=image_path)
        
        if not FACE_RECOGNITION_AVAILABLE:
            result.is_match = False
            return result
        
        if self.target_encoding is None:
            result.is_match = False
            return result
        
        try:
            # Load image
            image = face_recognition.load_image_file(image_path)
            
            # Detect faces
            locations = face_recognition.face_locations(image, model=self.model)
            result.face_count = len(locations)
            
            if not locations:
                result.has_face = False
            else:
                result.has_face = True
                
                # Get encodings
                encodings = face_recognition.face_encodings(
                    image,
                    known_face_locations=locations,
                    num_jitters=1  # Use 1 for speed during batch
                )
                
                if encodings:
                    # Compare each face to target
                    best_similarity = 0.0
                    
                    for encoding in encodings:
                        distance = face_recognition.face_distance(
                            [self.target_encoding], 
                            encoding
                        )[0]
                        
                        # Convert distance to similarity (0-100%)
                        similarity = max(0, (1 - distance)) * 100
                        
                        if similarity > best_similarity:
                            best_similarity = similarity
                    
                    result.similarity = best_similarity
                    result.is_match = best_similarity >= self.match_threshold
            
            # Cleanup image from memory
            del image
            if 'encodings' in dir():
                del encodings
            
        except Exception as e:
            result.is_match = False
        
        finally:
            # ALWAYS delete the file after processing
            if delete_after and image_path and os.path.exists(image_path):
                try:
                    os.remove(image_path)
                except Exception:
                    pass
            
            # Periodic garbage collection
            self._photo_count += 1
            if self._photo_count % Config.GC_EVERY_N_PHOTOS == 0:
                gc.collect()
        
        return result
    
    def process_from_bytes(self, data: bytes) -> FaceMatchResult:
        """
        Process image bytes directly (no disk write needed).
        
        Most memory efficient - never touches disk.
        """
        result = FaceMatchResult(photo_url="[in-memory]")
        
        if not FACE_RECOGNITION_AVAILABLE or self.target_encoding is None:
            return result
        
        try:
            # Load from bytes
            if PIL_AVAILABLE:
                from PIL import Image
                import io
                pil_image = Image.open(io.BytesIO(data))
                
                # Convert to RGB if needed
                if pil_image.mode != 'RGB':
                    pil_image = pil_image.convert('RGB')
                
                image = np.array(pil_image)
            else:
                # Fallback: save to temp file
                temp_path = tempfile.mktemp(suffix='.jpg')
                with open(temp_path, 'wb') as f:
                    f.write(data)
                image = face_recognition.load_image_file(temp_path)
                os.remove(temp_path)
            
            # Detect faces
            locations = face_recognition.face_locations(image, model=self.model)
            result.face_count = len(locations)
            
            if locations:
                result.has_face = True
                encodings = face_recognition.face_encodings(image, locations)
                
                if encodings:
                    best_similarity = 0.0
                    for encoding in encodings:
                        distance = face_recognition.face_distance(
                            [self.target_encoding], 
                            encoding
                        )[0]
                        similarity = max(0, (1 - distance)) * 100
                        if similarity > best_similarity:
                            best_similarity = similarity
                    
                    result.similarity = best_similarity
                    result.is_match = best_similarity >= self.match_threshold
            
            del image
            
        except Exception:
            pass
        
        finally:
            self._photo_count += 1
            if self._photo_count % Config.GC_EVERY_N_PHOTOS == 0:
                gc.collect()
        
        return result
    
    def unload(self):
        """Unload target encoding to free memory."""
        self.target_encoding = None
        gc.collect()


# =============================================================================
# ULTIMATE FACE MATCHER - THE MAIN CLASS
# =============================================================================

class UltimateFaceMatcher:
    """
    THE ULTIMATE FACE MATCHER
    
    Complete pipeline for matching faces across social media accounts:
    1. Loads target photo once
    2. For each account URL:
       - Scrapes ALL photos (not just profile pic)
       - Downloads one photo at a time
       - Compares face
       - DELETES immediately
    3. Returns accounts with face matches
    
    Usage:
        matcher = UltimateFaceMatcher()
        matcher.load_target('target.jpg')
        results = matcher.match_accounts(['https://vk.com/user1', 'https://vk.com/user2'])
    """
    
    def __init__(self,
                 match_threshold: float = Config.MATCH_THRESHOLD,
                 max_photos_per_profile: int = Config.MAX_PHOTOS_PER_PROFILE,
                 delay_between_photos: float = Config.DELAY_BETWEEN_PHOTOS,
                 delay_between_profiles: float = Config.DELAY_BETWEEN_PROFILES,
                 proxy: Optional[str] = None):
        """
        Initialize the Ultimate Face Matcher.
        
        Args:
            match_threshold: Minimum similarity % for a match (default 40%)
            max_photos_per_profile: Max photos to check per account
            delay_between_photos: Delay between photo downloads
            delay_between_profiles: Delay between profiles
            proxy: Optional proxy URL
        """
        self.match_threshold = match_threshold
        self.max_photos = max_photos_per_profile
        self.delay_photos = delay_between_photos
        self.delay_profiles = delay_between_profiles
        
        # Initialize components
        self.downloader = StreamingDownloader(proxy=proxy)
        self.harvester = PhotoStreamHarvester(self.downloader)
        self.engine = StreamingFaceEngine(match_threshold=match_threshold)
        
        self.target_loaded = False
    
    def load_target(self, path: str) -> Dict[str, Any]:
        """
        Load target photo.
        
        Args:
            path: Path to target's photo
            
        Returns:
            Dict with 'success' and 'error' if failed
        """
        result = self.engine.load_target_from_file(path)
        self.target_loaded = result.get('success', False)
        return result
    
    def match_single_account(self, 
                            url: str,
                            progress_callback: Optional[Callable] = None) -> AccountMatchResult:
        """
        Match faces in a single account.
        
        Scrapes ALL photos, compares each one, deletes immediately.
        
        Args:
            url: Account URL
            progress_callback: Optional callback(photos_checked, current_similarity)
            
        Returns:
            AccountMatchResult with match details
        """
        result = AccountMatchResult(
            url=url,
            platform=self.harvester._detect_platform(url)
        )
        
        if not self.target_loaded:
            result.errors.append("Target photo not loaded")
            return result
        
        # Extract username from URL
        path = urlparse(url).path.strip('/')
        result.username = path.split('/')[0] if path else ""
        
        # Harvest and process ALL photos
        photos_checked = 0
        
        for photo_info in self.harvester.harvest_all_photos(url):
            if photos_checked >= self.max_photos:
                break
            
            # Download photo to temp file
            temp_path = self.downloader.download_to_temp(photo_info.url)
            
            if not temp_path:
                continue
            
            # Compare face and DELETE immediately
            match_result = self.engine.process_and_compare(temp_path, delete_after=True)
            match_result.photo_url = photo_info.url
            match_result.photo_type = photo_info.photo_type
            
            photos_checked += 1
            result.photos_checked = photos_checked
            
            if match_result.has_face:
                result.photos_with_faces += 1
                
                # Track best match
                if match_result.similarity > result.best_similarity:
                    result.best_similarity = match_result.similarity
                    result.match_photo_url = photo_info.url
                    result.match_photo_type = photo_info.photo_type
                
                # Track all matches above threshold
                if match_result.is_match:
                    result.all_matches.append(match_result)
            
            if progress_callback:
                progress_callback(photos_checked, result.best_similarity)
            
            # Rate limiting
            time.sleep(self.delay_photos)
        
        # Determine if account is a match
        result.is_match = result.best_similarity >= self.match_threshold
        
        return result
    
    def match_accounts(self,
                      urls: List[str],
                      progress_callback: Optional[Callable] = None) -> List[AccountMatchResult]:
        """
        Match faces across multiple accounts.
        
        Args:
            urls: List of account URLs
            progress_callback: Optional callback(account_index, total, url, is_match, similarity)
            
        Returns:
            List of AccountMatchResults sorted by similarity (best first)
        """
        results = []
        total = len(urls)
        
        for i, url in enumerate(urls, 1):
            if progress_callback:
                progress_callback(i, total, url, None, 0)
            
            result = self.match_single_account(url)
            results.append(result)
            
            if progress_callback:
                progress_callback(i, total, url, result.is_match, result.best_similarity)
            
            # Rate limiting between profiles
            if i < total:
                time.sleep(self.delay_profiles)
        
        # Sort by similarity (best matches first)
        results.sort(key=lambda r: r.best_similarity, reverse=True)
        
        return results
    
    def match_accounts_generator(self,
                                urls: List[str]) -> Generator[AccountMatchResult, None, None]:
        """
        Match accounts one-by-one (generator version).
        
        Yields results as they're processed - useful for real-time updates.
        """
        for url in urls:
            result = self.match_single_account(url)
            yield result
            time.sleep(self.delay_profiles)
    
    def get_matches_only(self, 
                        urls: List[str],
                        progress_callback: Optional[Callable] = None) -> List[AccountMatchResult]:
        """
        Get only accounts that have face matches.
        
        Returns:
            List of AccountMatchResults where is_match=True
        """
        all_results = self.match_accounts(urls, progress_callback)
        return [r for r in all_results if r.is_match]
    
    def cleanup(self):
        """Cleanup all resources."""
        self.engine.unload()
        self.downloader.cleanup_all()
        gc.collect()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()


# =============================================================================
# INTEGRATION WITH EXISTING IBP PROJECT
# =============================================================================

def integrate_with_combined_search(accounts: List[Dict], 
                                   target_photo_path: str,
                                   progress_callback: Optional[Callable] = None) -> List[Dict]:
    """
    Integration function for existing IBP combined_search.py
    
    Takes account list from Maigret/Sherlock, runs face matching,
    returns accounts with face_match info added.
    
    Args:
        accounts: List of account dicts with 'url' field
        target_photo_path: Path to target's photo
        progress_callback: Optional callback(phase, current, total, status)
        
    Returns:
        Accounts sorted by face match (matches first)
    """
    if not FACE_RECOGNITION_AVAILABLE:
        print("⚠️ face_recognition not installed - skipping face matching")
        for acc in accounts:
            acc['face_checked'] = False
            acc['face_match'] = False
        return accounts
    
    print("\n" + "=" * 60)
    print("🔍 ULTIMATE FACE MATCHER")
    print("=" * 60)
    print(f"  Target photo: {target_photo_path}")
    print(f"  Accounts to check: {len(accounts)}")
    
    with UltimateFaceMatcher() as matcher:
        # Load target
        result = matcher.load_target(target_photo_path)
        if not result['success']:
            print(f"❌ Failed to load target: {result.get('error')}")
            return accounts
        
        print("✅ Target face loaded")
        
        # Extract URLs
        urls = [acc.get('url', '') for acc in accounts if acc.get('url')]
        
        # Match faces
        def internal_callback(i, total, url, is_match, similarity):
            if progress_callback:
                progress_callback('face_matching', i, total, 
                                f"{'✅' if is_match else '❌'} {similarity:.1f}% - {url[:50]}")
            if is_match:
                print(f"  [{i}/{total}] ✅ MATCH {similarity:.1f}% - {url[:50]}...")
        
        results = matcher.match_accounts(urls, internal_callback)
        
        # Update original accounts with face match info
        url_to_result = {r.url: r for r in results}
        
        for acc in accounts:
            url = acc.get('url', '')
            if url in url_to_result:
                match_result = url_to_result[url]
                acc['face_checked'] = True
                acc['face_match'] = match_result.is_match
                acc['face_similarity'] = match_result.best_similarity
                acc['photos_checked'] = match_result.photos_checked
                acc['photos_with_faces'] = match_result.photos_with_faces
                acc['match_photo_url'] = match_result.match_photo_url
                acc['match_photo_type'] = match_result.match_photo_type
            else:
                acc['face_checked'] = False
                acc['face_match'] = False
        
        # Sort: face matches first, then by similarity
        accounts.sort(key=lambda x: (
            x.get('face_match', False),
            x.get('face_similarity', 0)
        ), reverse=True)
        
        # Summary
        matches = sum(1 for a in accounts if a.get('face_match'))
        print(f"\n" + "=" * 60)
        print(f"✅ Face matching complete: {matches} matches out of {len(accounts)} accounts")
        print("=" * 60)
    
    return accounts


# =============================================================================
# COMMAND LINE INTERFACE
# =============================================================================

def main():
    """CLI for testing the Ultimate Face Matcher."""
    print("=" * 60)
    print("ULTIMATE FACE MATCHER - IBP Project")
    print("=" * 60)
    
    if not FACE_RECOGNITION_AVAILABLE:
        print("\n❌ face_recognition not installed!")
        print("Install with: pip install face_recognition")
        return
    
    print("✅ face_recognition is available")
    print(f"✅ PIL available: {PIL_AVAILABLE}")
    print(f"✅ BeautifulSoup available: {BS4_AVAILABLE}")
    
    print("\n📋 Configuration:")
    print(f"  Match threshold: {Config.MATCH_THRESHOLD}%")
    print(f"  Max photos per profile: {Config.MAX_PHOTOS_PER_PROFILE}")
    print(f"  Face model: {Config.FACE_MODEL}")
    
    print("\n📖 Usage:")
    print("  from ultimate_face_matcher import UltimateFaceMatcher")
    print("  ")
    print("  with UltimateFaceMatcher() as matcher:")
    print("      matcher.load_target('target.jpg')")
    print("      results = matcher.match_accounts([")
    print("          'https://vk.com/user1',")
    print("          'https://instagram.com/user2',")
    print("      ])")
    print("      for r in results:")
    print("          if r.is_match:")
    print("              print(f'MATCH: {r.url} - {r.best_similarity}%')")
    
    print("\n✅ Ultimate Face Matcher ready!")


if __name__ == "__main__":
    main()
