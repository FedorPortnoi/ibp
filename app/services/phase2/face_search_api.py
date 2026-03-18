"""
API-Based Facial Recognition Service for IBP Phase 2
=====================================================
Searches Search4faces, Yandex Images, and FaceCheck.ID
to discover social media profiles from a target photo.

This is MORE POWERFUL than local face_recognition because it
DISCOVERS new profiles rather than just comparing known photos.

Services:
- Search4faces: VK, OK, TikTok, Clubhouse (90%+ of Russians use VK)
- Yandex Images: Russian internet reverse image search
- FaceCheck.ID: 560+ million faces globally
"""

import asyncio
import aiohttp
import requests
from bs4 import BeautifulSoup
import logging
import time
import re
import json
import base64
import random
import os
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse, unquote, quote
import hashlib

logger = logging.getLogger(__name__)


@dataclass
class FaceMatch:
    """Represents a face match from API services"""
    platform: str  # vk, ok, tiktok, instagram, etc.
    profile_url: str
    profile_name: Optional[str] = None
    profile_username: Optional[str] = None
    similarity_score: float = 0.0  # 0.0 to 1.0
    photo_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    source_service: str = ""  # search4faces, yandex, facecheck
    metadata: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            'platform': self.platform,
            'profile_url': self.profile_url,
            'profile_name': self.profile_name,
            'profile_username': self.profile_username,
            'similarity_score': self.similarity_score,
            'photo_url': self.photo_url,
            'thumbnail_url': self.thumbnail_url,
            'source_service': self.source_service,
            'metadata': self.metadata
        }


# User agents for rotation
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
]


def get_random_user_agent() -> str:
    return random.choice(USER_AGENTS)


class Search4FacesService:
    """
    Search4faces.com - Best for Russian social media (VK, OK, TikTok, Clubhouse)
    Searches millions of indexed photos from Russian social networks.
    """

    BASE_URL = "https://search4faces.com"

    # Database endpoints
    DATABASES = {
        'vk': '/vk00/index.html',
        'vkok': '/vkok00/index.html',  # VK + OK combined
        'ok': '/ok00/index.html',
        'tiktok': '/tt00/index.html',
        'clubhouse': '/ch00/index.html',
    }

    def __init__(self):
        self.session = requests.Session()
        self._update_headers()
        self.rate_limit_delay = 3.0  # Seconds between requests

    def _update_headers(self):
        """Update session headers with random user agent"""
        self.session.headers.update({
            'User-Agent': get_random_user_agent(),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })

    async def search_face(
        self,
        image_path: str,
        databases: List[str] = None,
        max_results: int = 20
    ) -> List[FaceMatch]:
        """
        Search for face matches on Search4faces.

        Args:
            image_path: Path to the target photo
            databases: List of databases to search ['vk', 'ok', 'tiktok', 'clubhouse']
                      Default: ['vk', 'ok'] (most useful for Russia)
            max_results: Maximum results per database

        Returns:
            List of FaceMatch objects with discovered profiles
        """
        if databases is None:
            databases = ['vk', 'ok']

        matches = []

        for db in databases:
            if db not in self.DATABASES:
                logger.warning(f"Unknown database: {db}")
                continue

            try:
                logger.info(f"Searching {db.upper()} database on Search4faces...")
                db_matches = await self._search_database(image_path, db, max_results)
                matches.extend(db_matches)
                logger.info(f"Search4faces {db.upper()}: Found {len(db_matches)} matches")

                # Rate limiting - be respectful
                await asyncio.sleep(self.rate_limit_delay + random.uniform(0, 1))

            except Exception as e:
                logger.error(f"Search4faces {db} search failed: {e}")
                continue

        return matches

    async def _search_database(
        self,
        image_path: str,
        database: str,
        max_results: int
    ) -> List[FaceMatch]:
        """Search a specific database on Search4faces"""

        matches = []

        try:
            # Read and encode image
            with open(image_path, 'rb') as f:
                image_data = f.read()

            # Get the search page first to establish session
            db_url = self.BASE_URL + self.DATABASES[database]
            self._update_headers()

            # Try API endpoint first
            api_matches = await self._try_api_search(image_data, database, max_results)
            if api_matches:
                return api_matches

            # Fallback to form submission
            return await self._try_form_search(image_path, image_data, database, max_results)

        except Exception as e:
            logger.error(f"Search4faces database search error: {e}")

        return matches

    async def _try_api_search(
        self,
        image_data: bytes,
        database: str,
        max_results: int
    ) -> List[FaceMatch]:
        """Try to use Search4faces API directly"""
        matches = []

        try:
            # The site uses a specific API endpoint
            api_url = f"{self.BASE_URL}/api/search/{database}"

            # Prepare multipart form data
            files = {
                'photo': ('photo.jpg', image_data, 'image/jpeg'),
            }
            data = {
                'count': str(max_results),
            }

            response = self.session.post(
                api_url,
                files=files,
                data=data,
                timeout=60
            )

            if response.status_code == 200:
                try:
                    result = response.json()
                    matches = self._parse_api_response(result, database)
                except json.JSONDecodeError:
                    # Not JSON, might be HTML
                    matches = self._parse_html_response(response.text, database)

        except Exception as e:
            logger.debug(f"API search failed, will try form: {e}")

        return matches

    async def _try_form_search(
        self,
        image_path: str,
        image_data: bytes,
        database: str,
        max_results: int
    ) -> List[FaceMatch]:
        """Try to submit search via web form"""
        matches = []

        try:
            # Get the search page
            db_url = self.BASE_URL + self.DATABASES[database]
            page_response = self.session.get(db_url, timeout=30)

            if page_response.status_code != 200:
                return matches

            # Parse the page for form action and any tokens
            soup = BeautifulSoup(page_response.text, 'html.parser')

            # Find the upload form
            form = soup.find('form', {'enctype': 'multipart/form-data'})
            if not form:
                form = soup.find('form')

            if form:
                action = form.get('action', '')
                if not action.startswith('http'):
                    action = urljoin(self.BASE_URL, action)

                # Get hidden inputs
                hidden_inputs = {}
                for hidden in form.find_all('input', {'type': 'hidden'}):
                    name = hidden.get('name')
                    value = hidden.get('value', '')
                    if name:
                        hidden_inputs[name] = value

                # Submit the form with the image
                files = {
                    'photo': ('photo.jpg', image_data, 'image/jpeg'),
                }

                response = self.session.post(
                    action or db_url,
                    files=files,
                    data=hidden_inputs,
                    timeout=60,
                    allow_redirects=True
                )

                if response.status_code == 200:
                    matches = self._parse_html_response(response.text, database)

        except Exception as e:
            logger.error(f"Form search failed: {e}")

        return matches

    def _parse_api_response(self, data: dict, database: str) -> List[FaceMatch]:
        """Parse JSON API response"""
        matches = []

        try:
            results = data.get('results', data.get('faces', data.get('data', [])))

            for result in results:
                # Extract profile URL
                url = result.get('url', result.get('profile_url', result.get('link', '')))
                if not url:
                    continue

                # Extract similarity score
                score = result.get('score', result.get('similarity', result.get('confidence', 0)))
                if isinstance(score, str):
                    score = float(score.replace('%', ''))
                if score > 1:
                    score = score / 100  # Convert percentage to decimal

                match = FaceMatch(
                    platform=database,
                    profile_url=url,
                    profile_name=result.get('name', result.get('full_name', '')),
                    profile_username=self._extract_username(url),
                    similarity_score=float(score),
                    photo_url=result.get('photo', result.get('photo_url', result.get('image', ''))),
                    thumbnail_url=result.get('thumbnail', result.get('thumb', '')),
                    source_service='search4faces',
                    metadata={
                        'database': database,
                        'raw_data': result
                    }
                )
                matches.append(match)

        except Exception as e:
            logger.error(f"Failed to parse API response: {e}")

        return matches

    def _parse_html_response(self, html: str, database: str) -> List[FaceMatch]:
        """Parse HTML search results page"""
        matches = []

        try:
            soup = BeautifulSoup(html, 'html.parser')

            # Look for result cards/items
            result_selectors = [
                '.result-item',
                '.face-result',
                '.search-result',
                '.card',
                '[class*="result"]',
                '[class*="face"]',
            ]

            results = []
            for selector in result_selectors:
                results = soup.select(selector)
                if results:
                    break

            # If no structured results, look for links to social profiles
            if not results:
                results = soup.find_all('a', href=True)

            for item in results:
                try:
                    # Try to extract profile link
                    if item.name == 'a':
                        url = item.get('href', '')
                    else:
                        link = item.find('a', href=True)
                        url = link.get('href', '') if link else ''

                    if not url:
                        continue

                    # Filter for social media URLs
                    if not self._is_social_url(url):
                        continue

                    # Make URL absolute
                    if not url.startswith('http'):
                        url = urljoin(self.BASE_URL, url)

                    # Extract similarity score if present
                    score = 0.0
                    score_elem = item.find(class_=re.compile(r'score|percent|similarity'))
                    if score_elem:
                        score_text = score_elem.get_text()
                        score_match = re.search(r'(\d+(?:\.\d+)?)', score_text)
                        if score_match:
                            score = float(score_match.group(1))
                            if score > 1:
                                score = score / 100

                    # Extract name
                    name = ''
                    name_elem = item.find(class_=re.compile(r'name|title'))
                    if name_elem:
                        name = name_elem.get_text().strip()

                    # Extract photo URL
                    photo_url = ''
                    img = item.find('img')
                    if img:
                        photo_url = img.get('src', img.get('data-src', ''))
                        if photo_url and not photo_url.startswith('http'):
                            photo_url = urljoin(self.BASE_URL, photo_url)

                    platform = self._detect_platform(url)

                    match = FaceMatch(
                        platform=platform or database,
                        profile_url=url,
                        profile_name=name,
                        profile_username=self._extract_username(url),
                        similarity_score=score or 0.5,  # Default if not found
                        photo_url=photo_url,
                        source_service='search4faces',
                        metadata={'database': database}
                    )
                    matches.append(match)

                except Exception as e:
                    logger.debug(f"Error parsing result item: {e}")
                    continue

        except Exception as e:
            logger.error(f"Failed to parse HTML response: {e}")

        return matches

    @staticmethod
    def _is_social_url(url: str) -> bool:
        """Check if URL is a social media profile"""
        social_domains = [
            'vk.com', 'vkontakte.ru',
            'ok.ru', 'odnoklassniki.ru',
            'tiktok.com',
            'instagram.com',
            'facebook.com', 'fb.com',
            't.me', 'telegram.me',
            'twitter.com', 'x.com',
            'clubhouse.com',
        ]
        return any(domain in url.lower() for domain in social_domains)

    @staticmethod
    def _detect_platform(url: str) -> Optional[str]:
        """Detect platform from URL"""
        url_lower = url.lower()
        if 'vk.com' in url_lower or 'vkontakte' in url_lower:
            return 'vk'
        elif 'ok.ru' in url_lower or 'odnoklassniki' in url_lower:
            return 'ok'
        elif 'tiktok.com' in url_lower:
            return 'tiktok'
        elif 'instagram.com' in url_lower:
            return 'instagram'
        elif 'facebook.com' in url_lower or 'fb.com' in url_lower:
            return 'facebook'
        elif 't.me' in url_lower or 'telegram' in url_lower:
            return 'telegram'
        elif 'twitter.com' in url_lower or 'x.com' in url_lower:
            return 'twitter'
        elif 'clubhouse' in url_lower:
            return 'clubhouse'
        return None

    @staticmethod
    def _extract_username(url: str) -> Optional[str]:
        """Extract username from profile URL"""
        patterns = {
            'vk.com': r'vk\.com/([^/?#]+)',
            'ok.ru': r'ok\.ru/(?:profile/)?([^/?#]+)',
            'tiktok.com': r'tiktok\.com/@([^/?#]+)',
            'instagram.com': r'instagram\.com/([^/?#]+)',
            'facebook.com': r'facebook\.com/([^/?#]+)',
            't.me': r't\.me/([^/?#]+)',
            'twitter.com': r'twitter\.com/([^/?#]+)',
            'x.com': r'x\.com/([^/?#]+)',
        }

        for domain, pattern in patterns.items():
            if domain in url.lower():
                match = re.search(pattern, url, re.IGNORECASE)
                if match:
                    username = match.group(1)
                    # Filter out reserved paths
                    if username.lower() not in ['profile', 'user', 'id', 'public', 'groups', 'pages']:
                        return username
        return None


class YandexImageSearch:
    """
    Yandex Images reverse search - excellent for Russian internet.
    Finds where the face/image appears online.
    """

    SEARCH_URL = "https://yandex.ru/images/search"
    UPLOAD_URL = "https://yandex.ru/images/search"

    def __init__(self):
        self.session = requests.Session()
        self._update_headers()

    def _update_headers(self):
        self.session.headers.update({
            'User-Agent': get_random_user_agent(),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
        })

    async def search_face(self, image_path: str) -> List[FaceMatch]:
        """
        Reverse image search on Yandex.
        Returns URLs where the face appears, filtered for social media.
        """
        matches = []

        try:
            logger.info("Searching Yandex Images...")
            self._update_headers()

            # Read image
            with open(image_path, 'rb') as f:
                image_data = f.read()

            # Method 1: Try CBIR (Content-Based Image Retrieval) URL
            cbir_url = await self._get_cbir_url(image_data)
            if cbir_url:
                matches = await self._fetch_results(cbir_url)

            # Method 2: Try direct upload if CBIR failed
            if not matches:
                matches = await self._try_direct_upload(image_data)

        except Exception as e:
            logger.error(f"Yandex Image search failed: {e}")

        return matches

    async def _get_cbir_url(self, image_data: bytes) -> Optional[str]:
        """Upload image and get CBIR search URL"""
        try:
            # Yandex uses a special upload endpoint
            upload_url = "https://yandex.ru/images/search?rpt=imageview&format=json&request="

            files = {
                'upfile': ('photo.jpg', image_data, 'image/jpeg')
            }

            response = self.session.post(
                "https://yandex.ru/images/search?rpt=imageview",
                files=files,
                data={'rpt': 'imageview'},
                timeout=30,
                allow_redirects=False
            )

            # Check for redirect to results page
            if response.status_code in (301, 302, 303):
                return response.headers.get('Location')

            # Try to extract CBIR ID from response
            if response.status_code == 200:
                # Look for cbir_id in the response
                cbir_match = re.search(r'cbir_id=([^&"]+)', response.text)
                if cbir_match:
                    cbir_id = cbir_match.group(1)
                    return f"https://yandex.ru/images/search?cbir_id={cbir_id}&rpt=imageview"

        except Exception as e:
            logger.debug(f"CBIR URL extraction failed: {e}")

        return None

    async def _try_direct_upload(self, image_data: bytes) -> List[FaceMatch]:
        """Try direct form upload to Yandex Images"""
        matches = []

        try:
            # Get the search page first
            page = self.session.get("https://yandex.ru/images/", timeout=15)

            files = {'upfile': ('photo.jpg', image_data, 'image/jpeg')}

            response = self.session.post(
                "https://yandex.ru/images/search",
                files=files,
                data={'rpt': 'imageview'},
                timeout=30,
                allow_redirects=True
            )

            if response.status_code == 200:
                matches = self._extract_social_links(response.text)

        except Exception as e:
            logger.debug(f"Direct upload failed: {e}")

        return matches

    async def _fetch_results(self, url: str) -> List[FaceMatch]:
        """Fetch and parse results from CBIR URL"""
        matches = []

        try:
            response = self.session.get(url, timeout=30, allow_redirects=True)
            if response.status_code == 200:
                matches = self._extract_social_links(response.text)
        except Exception as e:
            logger.debug(f"Results fetch failed: {e}")

        return matches

    def _extract_social_links(self, html: str) -> List[FaceMatch]:
        """Extract social media profile links from Yandex results"""
        matches = []
        seen_urls = set()

        soup = BeautifulSoup(html, 'html.parser')

        # Social media domains to look for
        social_domains = {
            'vk.com': 'vk',
            'ok.ru': 'ok',
            'odnoklassniki.ru': 'ok',
            'instagram.com': 'instagram',
            'facebook.com': 'facebook',
            't.me': 'telegram',
            'tiktok.com': 'tiktok',
            'twitter.com': 'twitter',
            'x.com': 'twitter',
        }

        # Find all links in results
        for link in soup.find_all('a', href=True):
            url = link.get('href', '')

            # Handle Yandex redirect URLs
            if 'yandex' in url and ('url=' in url or 'text=' in url):
                url_match = re.search(r'(?:url|text)=([^&]+)', url)
                if url_match:
                    url = unquote(url_match.group(1))

            # Check if it's a social media URL
            for domain, platform in social_domains.items():
                if domain in url.lower():
                    # Clean the URL
                    clean_url = self._clean_url(url)

                    if clean_url and clean_url.lower() not in seen_urls:
                        seen_urls.add(clean_url.lower())

                        match = FaceMatch(
                            platform=platform,
                            profile_url=clean_url,
                            profile_username=Search4FacesService._extract_username(clean_url),
                            similarity_score=0.6,  # Yandex doesn't give scores
                            source_service='yandex_images',
                            metadata={'raw_url': url}
                        )
                        matches.append(match)
                    break

        logger.info(f"Yandex Images: Found {len(matches)} social media links")
        return matches

    @staticmethod
    def _clean_url(url: str) -> Optional[str]:
        """Clean and validate URL"""
        try:
            # Handle encoded URLs
            if '%' in url:
                url = unquote(url)

            parsed = urlparse(url)
            if parsed.scheme in ('http', 'https') and parsed.netloc:
                # Remove query params for cleaner profile URLs
                clean = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                return clean.rstrip('/')

        except Exception as e:
            logger.debug(f"[FaceSearchAPI] URL cleanup failed: {e}")

        return None


class FaceCheckService:
    """
    FaceCheck.ID - 560+ million faces globally.
    Good fallback when Russian-specific services don't find results.

    Note: This service may require browser automation for full functionality.
    """

    BASE_URL = "https://facecheck.id"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': get_random_user_agent(),
        })

    async def search_face(self, image_path: str) -> List[FaceMatch]:
        """
        Search FaceCheck.ID for face matches.
        Note: This service may have CAPTCHAs and rate limits.
        """
        matches = []

        try:
            logger.info("Searching FaceCheck.ID...")

            # Read and encode image
            with open(image_path, 'rb') as f:
                image_data = f.read()

            # Try API approach
            matches = await self._try_api_search(image_data)

            if not matches:
                logger.warning("FaceCheck.ID may require browser automation for full functionality")

        except Exception as e:
            logger.error(f"FaceCheck.ID search failed: {e}")

        return matches

    async def _try_api_search(self, image_data: bytes) -> List[FaceMatch]:
        """Try to use FaceCheck API"""
        matches = []

        try:
            # Get the main page to establish session
            self.session.get(self.BASE_URL, timeout=15)

            # Try uploading
            files = {'file': ('photo.jpg', image_data, 'image/jpeg')}

            response = self.session.post(
                f"{self.BASE_URL}/api/upload",
                files=files,
                timeout=60
            )

            if response.status_code == 200:
                try:
                    data = response.json()
                    matches = self._parse_results(data)
                except json.JSONDecodeError:
                    pass

        except Exception as e:
            logger.debug(f"FaceCheck API search failed: {e}")

        return matches

    def _parse_results(self, data: dict) -> List[FaceMatch]:
        """Parse FaceCheck API response"""
        matches = []

        results = data.get('results', data.get('faces', []))

        for result in results:
            url = result.get('url', result.get('link', ''))
            if not url:
                continue

            score = result.get('score', result.get('confidence', 0))
            if isinstance(score, str):
                score = float(score.replace('%', ''))
            if score > 1:
                score = score / 100

            match = FaceMatch(
                platform=Search4FacesService._detect_platform(url) or 'unknown',
                profile_url=url,
                profile_name=result.get('name', ''),
                profile_username=Search4FacesService._extract_username(url),
                similarity_score=float(score),
                photo_url=result.get('image', ''),
                source_service='facecheck',
                metadata=result
            )
            matches.append(match)

        return matches


class ApiFaceSearchService:
    """
    Main service that coordinates all API-based face searches.
    Use this class for comprehensive face searching across all services.
    """

    def __init__(self):
        self.search4faces = Search4FacesService()
        self.yandex = YandexImageSearch()
        self.facecheck = FaceCheckService()

    async def search_all_services(
        self,
        image_path: str,
        services: List[str] = None,
        databases: List[str] = None
    ) -> Dict[str, List[FaceMatch]]:
        """
        Search all face recognition services.

        Args:
            image_path: Path to target photo
            services: List of services to use ['search4faces', 'yandex', 'facecheck']
                     Default: ['search4faces', 'yandex']
            databases: For search4faces - which databases ['vk', 'ok', 'tiktok']
                      Default: ['vk', 'ok']

        Returns:
            Dict mapping service name to list of matches
        """
        if not os.path.exists(image_path):
            logger.error(f"Image not found: {image_path}")
            return {}

        if services is None:
            services = ['search4faces', 'yandex']

        if databases is None:
            databases = ['vk', 'ok']

        results = {}

        # Run searches
        if 'search4faces' in services:
            try:
                matches = await self.search4faces.search_face(image_path, databases=databases)
                results['search4faces'] = matches
                logger.info(f"Search4faces: Found {len(matches)} matches")
            except Exception as e:
                logger.error(f"Search4faces failed: {e}")
                results['search4faces'] = []

        if 'yandex' in services:
            try:
                # Add delay between services
                await asyncio.sleep(2)
                matches = await self.yandex.search_face(image_path)
                results['yandex'] = matches
                logger.info(f"Yandex: Found {len(matches)} matches")
            except Exception as e:
                logger.error(f"Yandex failed: {e}")
                results['yandex'] = []

        if 'facecheck' in services:
            try:
                await asyncio.sleep(2)
                matches = await self.facecheck.search_face(image_path)
                results['facecheck'] = matches
                logger.info(f"FaceCheck: Found {len(matches)} matches")
            except Exception as e:
                logger.error(f"FaceCheck failed: {e}")
                results['facecheck'] = []

        return results

    async def search_and_merge(
        self,
        image_path: str,
        services: List[str] = None,
        databases: List[str] = None
    ) -> List[FaceMatch]:
        """
        Search all services and merge results, removing duplicates.

        Args:
            image_path: Path to target photo
            services: Services to use (default: search4faces, yandex)
            databases: Databases for search4faces (default: vk, ok)

        Returns:
            Merged and deduplicated list of FaceMatch objects
        """
        all_results = await self.search_all_services(image_path, services, databases)

        # Merge and deduplicate
        seen_urls = set()
        merged = []

        # Priority order: search4faces > yandex > facecheck
        priority_order = ['search4faces', 'yandex', 'facecheck']

        for service in priority_order:
            for match in all_results.get(service, []):
                url_key = match.profile_url.lower().rstrip('/')

                if url_key not in seen_urls:
                    seen_urls.add(url_key)
                    merged.append(match)

        # Sort by similarity score (highest first)
        merged.sort(key=lambda x: x.similarity_score, reverse=True)

        logger.info(f"Total unique profiles found: {len(merged)}")
        return merged


# Convenience functions
def search_faces_sync(image_path: str, services: List[str] = None) -> List[FaceMatch]:
    """Synchronous wrapper for face search"""
    service = ApiFaceSearchService()
    return asyncio.run(service.search_and_merge(image_path, services))


async def search_faces_async(image_path: str, services: List[str] = None) -> List[FaceMatch]:
    """Async face search"""
    service = ApiFaceSearchService()
    return await service.search_and_merge(image_path, services)


# Test function
async def test_face_search(image_path: str = None):
    """Test the face search services"""

    print("\n" + "=" * 60)
    print("API-BASED FACE SEARCH TEST")
    print("=" * 60)

    # Check for test image
    if image_path and os.path.exists(image_path):
        pass
    else:
        test_paths = [
            "test_photo.jpg",
            "uploads/test.jpg",
            "/tmp/test_face.jpg",
            "app/static/uploads/test.jpg",
        ]
        for path in test_paths:
            if os.path.exists(path):
                image_path = path
                break

    if not image_path or not os.path.exists(image_path):
        print("\n[!] No test image found!")
        print("\nTo test, provide an image path:")
        print("  python -c \"")
        print("  import asyncio")
        print("  from app.services.phase2.face_search_api import test_face_search")
        print("  asyncio.run(test_face_search('/path/to/photo.jpg'))\"")
        print("\nServices available:")
        print("  - Search4faces (VK, OK, TikTok, Clubhouse)")
        print("  - Yandex Images (Russian internet)")
        print("  - FaceCheck.ID (Global - 560M+ faces)")
        return []

    print(f"\nUsing image: {image_path}")
    print(f"File size: {os.path.getsize(image_path) / 1024:.1f} KB")

    service = ApiFaceSearchService()

    # Test Search4faces
    print("\n--- Testing Search4faces (VK, OK) ---")
    try:
        s4f_results = await service.search4faces.search_face(image_path, databases=['vk'])
        print(f"Found {len(s4f_results)} matches")
        for match in s4f_results[:3]:
            print(f"  [{match.similarity_score:.0%}] {match.platform}: {match.profile_url}")
    except Exception as e:
        print(f"  Error: {e}")

    # Test Yandex
    print("\n--- Testing Yandex Images ---")
    try:
        await asyncio.sleep(2)
        yandex_results = await service.yandex.search_face(image_path)
        print(f"Found {len(yandex_results)} social media links")
        for match in yandex_results[:3]:
            print(f"  {match.platform}: {match.profile_url}")
    except Exception as e:
        print(f"  Error: {e}")

    # Merged results
    print("\n--- Merged Results ---")
    merged = await service.search_and_merge(image_path)
    print(f"Total unique profiles: {len(merged)}")
    for match in merged[:5]:
        print(f"  [{match.similarity_score:.0%}] {match.platform}: {match.profile_url}")
        print(f"      (via {match.source_service})")

    print("\n" + "=" * 60)
    return merged


if __name__ == "__main__":
    import sys
    image = sys.argv[1] if len(sys.argv) > 1 else None
    asyncio.run(test_face_search(image))
