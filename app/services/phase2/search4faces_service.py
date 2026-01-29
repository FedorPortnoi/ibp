"""
Search4faces Facial Recognition Service
=======================================
Searches VK/OK databases for matching faces.
100% FREE, unlimited searches.

Based on: https://search4faces.com/en/
Bellingcat reference: https://bellingcat.gitbook.io/toolkit/more/all-tools/search4faces

Database info:
- vkok: VK & OK avatars (312M faces, 2022-2024)
- vk01: VK profile photos (1.1B faces, 2019-2023)
- vkokn: Newer database
"""

import requests
from bs4 import BeautifulSoup
from typing import List, Optional
from dataclasses import dataclass
import time
import logging
import re
import os

logger = logging.getLogger(__name__)


@dataclass
class FaceMatch:
    """A face match result from Search4faces."""
    platform: str  # 'vk' or 'ok'
    profile_url: str
    username: Optional[str] = None
    similarity_score: Optional[float] = None
    thumbnail_url: Optional[str] = None
    name: Optional[str] = None
    age: Optional[int] = None
    city: Optional[str] = None


@dataclass
class Search4FacesResults:
    """Results from a Search4faces search."""
    success: bool
    matches: List[FaceMatch]
    database_searched: str
    error: Optional[str] = None


# Search4faces configuration
BASE_URL = "https://search4faces.com"
DATABASES = {
    'vkok': '/en/vkok/index.html',      # VK & OK avatars (newer)
    'vk01': '/en/vk01/index.html',      # VK profile photos (larger)
    'vkokn': '/en/vkokn/index.html',    # Newest database
}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9,ru;q=0.8',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Referer': 'https://search4faces.com/en/',
    'Origin': 'https://search4faces.com'
}


def search_by_photo(
    image_path: str = None,
    image_url: str = None,
    image_bytes: bytes = None,
    database: str = 'vkok',
    max_results: int = 50
) -> Search4FacesResults:
    """
    Search for faces matching the provided image.

    Args:
        image_path: Path to local image file
        image_url: URL of image to search
        image_bytes: Raw image bytes
        database: Which database to search ('vkok', 'vk01', 'vkokn')
        max_results: Maximum results to return

    Returns:
        Search4FacesResults with matching profiles
    """
    if database not in DATABASES:
        return Search4FacesResults(
            success=False,
            matches=[],
            database_searched=database,
            error=f"Invalid database. Use: {list(DATABASES.keys())}"
        )

    session = requests.Session()
    session.headers.update(HEADERS)

    try:
        # Step 1: Get the search page (for cookies/tokens)
        page_url = f"{BASE_URL}{DATABASES[database]}"
        page_resp = session.get(page_url, timeout=15)
        page_resp.raise_for_status()

        # Step 2: Prepare image data
        if image_path:
            if not os.path.exists(image_path):
                return Search4FacesResults(
                    success=False,
                    matches=[],
                    database_searched=database,
                    error=f"Image file not found: {image_path}"
                )
            with open(image_path, 'rb') as f:
                image_data = f.read()
            filename = os.path.basename(image_path)
            # Determine content type
            ext = filename.lower().split('.')[-1]
            content_type = {
                'jpg': 'image/jpeg',
                'jpeg': 'image/jpeg',
                'png': 'image/png',
                'webp': 'image/webp',
                'gif': 'image/gif'
            }.get(ext, 'image/jpeg')

        elif image_url:
            try:
                img_resp = requests.get(image_url, timeout=15)
                img_resp.raise_for_status()
                image_data = img_resp.content
                filename = 'photo.jpg'
                content_type = img_resp.headers.get('Content-Type', 'image/jpeg')
            except Exception as e:
                return Search4FacesResults(
                    success=False,
                    matches=[],
                    database_searched=database,
                    error=f"Failed to download image: {e}"
                )

        elif image_bytes:
            image_data = image_bytes
            filename = 'photo.jpg'
            content_type = 'image/jpeg'

        else:
            return Search4FacesResults(
                success=False,
                matches=[],
                database_searched=database,
                error="No image provided"
            )

        # Step 3: Upload image and search
        # Search4faces uses multipart form upload
        # The actual upload endpoint may vary - trying common patterns
        upload_endpoints = [
            f"{BASE_URL}/upload/{database}",
            f"{BASE_URL}/api/upload",
            f"{BASE_URL}/en/{database}/search",
        ]

        files = {
            'photo': (filename, image_data, content_type)
        }

        data = {
            'db': database,
            'age_min': '0',
            'age_max': '100',
            'gender': '',  # Empty for any gender
            'country': '',
            'city': ''
        }

        upload_resp = None
        for endpoint in upload_endpoints:
            try:
                upload_resp = session.post(
                    endpoint,
                    files=files,
                    data=data,
                    timeout=60
                )
                if upload_resp.status_code == 200:
                    break
            except Exception:
                continue

        if upload_resp is None or upload_resp.status_code != 200:
            # Fallback: try to parse results from the main page response
            # Some versions of search4faces return results directly
            logger.warning("Direct upload failed, trying alternative method")

            # Try form-based submission to the index page
            form_data = {
                'photo': (filename, image_data, content_type)
            }
            upload_resp = session.post(
                page_url,
                files=form_data,
                data=data,
                timeout=60
            )

        # Step 4: Parse results
        matches = parse_search_results(upload_resp.text if upload_resp else '', database)

        return Search4FacesResults(
            success=True,
            matches=matches[:max_results],
            database_searched=database
        )

    except requests.exceptions.Timeout:
        return Search4FacesResults(
            success=False,
            matches=[],
            database_searched=database,
            error="Request timed out"
        )
    except Exception as e:
        logger.error(f"Search4faces error: {e}")
        return Search4FacesResults(
            success=False,
            matches=[],
            database_searched=database,
            error=str(e)
        )


def parse_search_results(html: str, database: str) -> List[FaceMatch]:
    """Parse search results HTML to extract matches."""
    matches = []

    if not html:
        return matches

    soup = BeautifulSoup(html, 'html.parser')

    # Find result cards (multiple possible selectors)
    result_selectors = [
        '.result-card',
        '.face-result',
        '.search-result',
        '.result-item',
        '.face-card',
        '[class*="result"]',
        '.card',
    ]

    result_cards = []
    for selector in result_selectors:
        cards = soup.select(selector)
        if cards:
            result_cards = cards
            break

    # If no cards found, try to find links to VK/OK profiles directly
    if not result_cards:
        # Find all links to VK/OK
        vk_links = soup.find_all('a', href=re.compile(r'vk\.com/'))
        ok_links = soup.find_all('a', href=re.compile(r'ok\.ru/'))

        for link in vk_links + ok_links:
            href = link.get('href', '')
            if not href:
                continue

            # Determine platform
            if 'vk.com' in href:
                platform = 'vk'
            elif 'ok.ru' in href:
                platform = 'ok'
            else:
                continue

            # Extract username
            username = extract_username(href, platform)

            # Try to get thumbnail
            img = link.find('img')
            thumbnail = img.get('src') if img else None

            # Try to get name from link text or nearby elements
            name = link.get_text(strip=True) or None

            matches.append(FaceMatch(
                platform=platform,
                profile_url=href,
                username=username,
                thumbnail_url=thumbnail,
                name=name
            ))

    else:
        for card in result_cards:
            try:
                # Extract profile link
                link = card.select_one('a[href*="vk.com"], a[href*="ok.ru"]')
                if not link:
                    # Try parent or child elements
                    link = card.find_parent('a')
                    if not link or ('vk.com' not in str(link.get('href', '')) and 'ok.ru' not in str(link.get('href', ''))):
                        link = card.find('a')

                if not link:
                    continue

                profile_url = link.get('href', '')
                if not profile_url:
                    continue

                # Determine platform
                if 'vk.com' in profile_url:
                    platform = 'vk'
                elif 'ok.ru' in profile_url:
                    platform = 'ok'
                else:
                    continue

                # Extract username from URL
                username = extract_username(profile_url, platform)

                # Extract similarity score if available
                score_selectors = ['.similarity', '.score', '.match-percent', '[class*="score"]', '[class*="percent"]']
                similarity = None
                for selector in score_selectors:
                    score_elem = card.select_one(selector)
                    if score_elem:
                        score_text = score_elem.get_text()
                        numbers = re.findall(r'(\d+\.?\d*)', score_text)
                        if numbers:
                            similarity = float(numbers[0])
                            break

                # Extract thumbnail
                thumb = card.select_one('img')
                thumbnail_url = thumb.get('src') if thumb else None

                # Extract name if available
                name_selectors = ['.name', '.username', '.title', 'h3', 'h4', '.user-name']
                name = None
                for selector in name_selectors:
                    name_elem = card.select_one(selector)
                    if name_elem:
                        name = name_elem.get_text(strip=True)
                        break

                matches.append(FaceMatch(
                    platform=platform,
                    profile_url=profile_url,
                    username=username,
                    similarity_score=similarity,
                    thumbnail_url=thumbnail_url,
                    name=name
                ))

            except Exception as e:
                logger.warning(f"Error parsing result card: {e}")
                continue

    return matches


def extract_username(url: str, platform: str) -> Optional[str]:
    """Extract username from profile URL."""
    if platform == 'vk':
        match = re.search(r'vk\.com/([a-zA-Z0-9_.]+)', url)
    elif platform == 'ok':
        match = re.search(r'ok\.ru/(?:profile/)?([a-zA-Z0-9_.]+)', url)
    else:
        return None

    return match.group(1) if match else None


def search_all_databases(
    image_path: str = None,
    image_url: str = None,
    image_bytes: bytes = None,
    max_results_per_db: int = 20
) -> List[FaceMatch]:
    """
    Search all databases and combine results.

    Args:
        image_path/url/bytes: Image to search
        max_results_per_db: Max results from each database

    Returns:
        Combined list of matches (deduplicated)
    """
    all_matches = []
    seen_urls = set()

    # Search main databases
    databases_to_search = ['vkok', 'vk01']

    for db_name in databases_to_search:
        logger.info(f"Searching {db_name} database...")

        result = search_by_photo(
            image_path=image_path,
            image_url=image_url,
            image_bytes=image_bytes,
            database=db_name,
            max_results=max_results_per_db
        )

        if result.success:
            for match in result.matches:
                if match.profile_url not in seen_urls:
                    all_matches.append(match)
                    seen_urls.add(match.profile_url)

            logger.info(f"Found {len(result.matches)} matches in {db_name}")
        else:
            logger.warning(f"Search4faces {db_name} failed: {result.error}")

        # Rate limit between database searches
        time.sleep(2)

    return all_matches


def search_vk_only(
    image_path: str = None,
    image_url: str = None,
    image_bytes: bytes = None,
    max_results: int = 50
) -> Search4FacesResults:
    """
    Search only VK database (largest, 1.1B faces).

    Args:
        image_path/url/bytes: Image to search
        max_results: Maximum results to return

    Returns:
        Search4FacesResults
    """
    return search_by_photo(
        image_path=image_path,
        image_url=image_url,
        image_bytes=image_bytes,
        database='vk01',
        max_results=max_results
    )


def search_vk_ok_combined(
    image_path: str = None,
    image_url: str = None,
    image_bytes: bytes = None,
    max_results: int = 50
) -> Search4FacesResults:
    """
    Search combined VK+OK avatars database.

    Args:
        image_path/url/bytes: Image to search
        max_results: Maximum results to return

    Returns:
        Search4FacesResults
    """
    return search_by_photo(
        image_path=image_path,
        image_url=image_url,
        image_bytes=image_bytes,
        database='vkok',
        max_results=max_results
    )
