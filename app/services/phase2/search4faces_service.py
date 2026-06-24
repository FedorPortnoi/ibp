"""
Search4faces Facial Recognition Service
=======================================
Searches VK/OK databases for matching faces.

Two search methods:
  1. JSON-RPC API (paid, $40+/mo) — set SEARCH4FACES_API_KEY
  2. Playwright browser automation (free, unlimited) — default fallback

Based on: https://search4faces.com/en/
API docs: https://search4faces.com/en/api.html
Bellingcat: https://bellingcat.gitbook.io/toolkit/more/all-tools/search4faces

Database info:
- vkok: VK & OK avatars (312M faces, 2022-2024)
- vk01: VK profile photos (1.1B faces, 2019-2023)
- vkokn: Newer database
"""

import base64
import json
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
API_URL = "https://search4faces.com/api/json-rpc/v1"

# Database page paths (for Playwright fallback)
DATABASE_PAGES = {
    'vkok': '/en/vkok/index.html',
    'vk01': '/en/vk01/index.html',
    'vkokn': '/en/vkokn/index.html',
}

# Database IDs for JSON-RPC API (source parameter in searchFace)
DATABASE_API_IDS = {
    'vkok': 2,   # VK + OK avatars
    'vk01': 1,   # VK profile photos
    'vkokn': 3,  # Newest database
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


def _get_image_data(image_path=None, image_url=None, image_bytes=None):
    """Prepare image data from various sources. Returns (bytes, filename, content_type) or raises."""
    if image_path:
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image file not found: {image_path}")
        with open(image_path, 'rb') as f:
            data = f.read()
        filename = os.path.basename(image_path)
        ext = filename.lower().rsplit('.', 1)[-1] if '.' in filename else 'jpg'
        ct = {'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png',
              'webp': 'image/webp', 'gif': 'image/gif'}.get(ext, 'image/jpeg')
        return data, filename, ct

    if image_url:
        logger.info(f"Downloading image from: {image_url[:80]}...")
        resp = requests.get(image_url, timeout=15, headers={
            'User-Agent': HEADERS['User-Agent'],
        })
        resp.raise_for_status()
        ct = resp.headers.get('Content-Type', 'image/jpeg')
        if len(resp.content) < 1000:
            raise ValueError(f"Downloaded image too small ({len(resp.content)} bytes) — may be a placeholder")
        return resp.content, 'photo.jpg', ct

    if image_bytes:
        if len(image_bytes) < 1000:
            raise ValueError(f"Image data too small ({len(image_bytes)} bytes)")
        return image_bytes, 'photo.jpg', 'image/jpeg'

    raise ValueError("No image provided (need image_path, image_url, or image_bytes)")


# ── Method 1: JSON-RPC API (paid) ──────────────────────────────────

def _search_via_api(image_data: bytes, database: str, max_results: int) -> Search4FacesResults:
    """Search via JSON-RPC API. Requires SEARCH4FACES_API_KEY."""
    api_key = os.environ.get('SEARCH4FACES_API_KEY', '').strip()
    if not api_key:
        return Search4FacesResults(
            success=False, matches=[], database_searched=database,
            error="SEARCH4FACES_API_KEY not set"
        )

    headers = {
        'Content-Type': 'application/json',
        'x-authorization-token': api_key,
    }

    # Step 1: detectFaces
    b64_image = base64.b64encode(image_data).decode('ascii')

    detect_payload = {
        "jsonrpc": "2.0",
        "id": "detect_1",
        "method": "detectFaces",
        "params": {
            "image": b64_image,
        }
    }

    logger.info(f"Search4Faces API: detectFaces ({len(image_data)} bytes)...")
    try:
        resp = requests.post(API_URL, json=detect_payload, headers=headers, timeout=30)
        resp.raise_for_status()
        detect_result = resp.json()
    except Exception as e:
        logger.error(f"Search4Faces API detectFaces failed: {e}")
        return Search4FacesResults(
            success=False, matches=[], database_searched=database,
            error=f"detectFaces failed: {e}"
        )

    if 'error' in detect_result:
        error_msg = detect_result['error'].get('message', str(detect_result['error']))
        logger.error(f"Search4Faces API detectFaces error: {error_msg}")
        return Search4FacesResults(
            success=False, matches=[], database_searched=database,
            error=f"detectFaces: {error_msg}"
        )

    result_data = detect_result.get('result', {})
    faces = result_data.get('faces', [])
    image_id = result_data.get('id_image')

    if not faces:
        logger.warning("Search4Faces API: no faces detected in image")
        return Search4FacesResults(
            success=True, matches=[], database_searched=database,
            error="No faces detected in image"
        )

    if not image_id:
        logger.error("Search4Faces API: no image_id returned")
        return Search4FacesResults(
            success=False, matches=[], database_searched=database,
            error="No image_id in detectFaces response"
        )

    # Use the first detected face
    face = faces[0]
    source_id = DATABASE_API_IDS.get(database, 1)

    # Step 2: searchFace
    search_payload = {
        "jsonrpc": "2.0",
        "id": "search_1",
        "method": "searchFace",
        "params": {
            "id_image": image_id,
            "face": face,
            "source": source_id,
            "hidden": False,
            "results": min(max_results, 500),
            "lang": "en",
        }
    }

    logger.info(f"Search4Faces API: searchFace (db={database}, source={source_id})...")
    try:
        resp = requests.post(API_URL, json=search_payload, headers=headers, timeout=60)
        resp.raise_for_status()
        search_result = resp.json()
    except Exception as e:
        logger.error(f"Search4Faces API searchFace failed: {e}")
        return Search4FacesResults(
            success=False, matches=[], database_searched=database,
            error=f"searchFace failed: {e}"
        )

    if 'error' in search_result:
        error_msg = search_result['error'].get('message', str(search_result['error']))
        logger.error(f"Search4Faces API searchFace error: {error_msg}")
        return Search4FacesResults(
            success=False, matches=[], database_searched=database,
            error=f"searchFace: {error_msg}"
        )

    # Parse results
    matches = []
    for item in search_result.get('result', []):
        profile_url = item.get('url', '')
        if not profile_url:
            profile_url = item.get('link', '')
        if not profile_url:
            continue

        if 'vk.com' in profile_url:
            platform = 'vk'
        elif 'ok.ru' in profile_url:
            platform = 'ok'
        else:
            platform = 'unknown'

        similarity = item.get('similarity', 0)
        if isinstance(similarity, (int, float)):
            similarity = float(similarity)
            if similarity > 1.0:
                similarity = similarity / 100.0  # Convert percentage to 0-1

        matches.append(FaceMatch(
            platform=platform,
            profile_url=profile_url,
            username=extract_username(profile_url, platform),
            similarity_score=similarity,
            thumbnail_url=item.get('image') or item.get('photo'),
            name=item.get('name'),
            age=item.get('age'),
            city=item.get('city'),
        ))

    logger.info(f"Search4Faces API: {len(matches)} matches in {database}")
    return Search4FacesResults(success=True, matches=matches, database_searched=database)


# ── Method 2: Playwright browser automation (free) ────────────────

def _search_via_playwright(image_data: bytes, filename: str, database: str, max_results: int) -> Search4FacesResults:
    """Search via browser automation. Free, no API key needed."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.warning("Playwright not installed — cannot use free Search4Faces search")
        return Search4FacesResults(
            success=False, matches=[], database_searched=database,
            error="Playwright not installed (pip install playwright && playwright install chromium)"
        )

    page_path = DATABASE_PAGES.get(database)
    if not page_path:
        return Search4FacesResults(
            success=False, matches=[], database_searched=database,
            error=f"Unknown database: {database}"
        )

    page_url = f"{BASE_URL}{page_path}"

    # Save image to temp file for upload
    import tempfile
    ext = 'jpg'
    if filename.lower().endswith('.png'):
        ext = 'png'
    temp_path = None

    try:
        with tempfile.NamedTemporaryFile(suffix=f'.{ext}', delete=False) as tmp:
            tmp.write(image_data)
            temp_path = tmp.name

        logger.info(f"Search4Faces Playwright: opening {page_url}...")

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, timeout=15000)
            try:
                page = browser.new_page(
                    user_agent=HEADERS['User-Agent'],
                    viewport={'width': 1280, 'height': 900},
                )

                # Navigate to the database search page
                page.goto(page_url, wait_until='networkidle', timeout=30000)
                time.sleep(1)

                # Find the file input and upload the image
                # Search4Faces uses <input type="file"> for photo upload
                file_input = page.query_selector('input[type="file"]')
                if not file_input:
                    # Try common selectors
                    for sel in ['input[accept*="image"]', '#photo', '#file', '.upload input']:
                        file_input = page.query_selector(sel)
                        if file_input:
                            break

                if not file_input:
                    logger.error("Search4Faces Playwright: no file input found on page")
                    return Search4FacesResults(
                        success=False, matches=[], database_searched=database,
                        error="No file input found on search page"
                    )

                logger.info("Search4Faces Playwright: uploading image...")
                file_input.set_input_files(temp_path)

                # Wait for upload processing — site may auto-submit or enable the button
                time.sleep(3)

                # Click the search/submit button (force=True bypasses disabled state)
                search_btn = page.query_selector('button[type="submit"], input[type="submit"], .search-btn, #search, button:has-text("Search"), button:has-text("Поиск")')
                if search_btn:
                    try:
                        search_btn.click(force=True, timeout=5000)
                    except Exception:
                        page.keyboard.press('Enter')
                else:
                    page.keyboard.press('Enter')

                # Wait for results to load
                logger.info("Search4Faces Playwright: waiting for results...")
                try:
                    # Wait for result cards or VK/OK links to appear
                    page.wait_for_selector(
                        'a[href*="vk.com/"], a[href*="ok.ru/"], .result, [class*="result"]',
                        timeout=45000
                    )
                    time.sleep(2)  # Extra wait for dynamic rendering
                except Exception as e:
                    # Page might have loaded but with no results
                    logger.info(f"Search4Faces Playwright: no result elements appeared (may be no matches): {e}")

                # Get page content and parse
                html = page.content()
            finally:
                browser.close()

        # Parse the results HTML
        matches = parse_search_results(html, database)
        logger.info(f"Search4Faces Playwright: {len(matches)} matches in {database}")

        return Search4FacesResults(
            success=True,
            matches=matches[:max_results],
            database_searched=database,
        )

    except Exception as e:
        logger.error(f"Search4Faces Playwright error: {e}")
        return Search4FacesResults(
            success=False, matches=[], database_searched=database,
            error=f"Playwright error: {e}"
        )
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except Exception as e:
                logger.debug(f"[Search4Faces] Temp file cleanup failed: {e}")


# ── Main entry point ────────────────────────────────────────────────

def search_by_photo(
    image_path: str = None,
    image_url: str = None,
    image_bytes: bytes = None,
    database: str = 'vkok',
    max_results: int = 50
) -> Search4FacesResults:
    """
    Search for faces matching the provided image.

    Tries JSON-RPC API first (if SEARCH4FACES_API_KEY set),
    then falls back to Playwright browser automation.

    Args:
        image_path: Path to local image file
        image_url: URL of image to search
        image_bytes: Raw image bytes
        database: Which database to search ('vkok', 'vk01', 'vkokn')
        max_results: Maximum results to return

    Returns:
        Search4FacesResults with matching profiles
    """
    valid_dbs = set(DATABASE_PAGES.keys())
    if database not in valid_dbs:
        return Search4FacesResults(
            success=False, matches=[], database_searched=database,
            error=f"Invalid database. Use: {list(valid_dbs)}"
        )

    # Prepare image
    try:
        image_data, filename, content_type = _get_image_data(image_path, image_url, image_bytes)
    except Exception as e:
        logger.error(f"Search4Faces image preparation failed: {e}")
        return Search4FacesResults(
            success=False, matches=[], database_searched=database,
            error=str(e)
        )

    logger.info(f"Search4Faces: searching {database} ({len(image_data)} bytes image)...")

    # Method 1: Try JSON-RPC API if key is available
    api_key = os.environ.get('SEARCH4FACES_API_KEY', '').strip()
    if api_key:
        result = _search_via_api(image_data, database, max_results)
        if result.success and result.matches:
            return result
        if result.success and not result.matches:
            logger.info(f"Search4Faces API returned 0 matches for {database}")
            return result
        # API failed — fall through to Playwright
        logger.warning(f"Search4Faces API failed ({result.error}), trying Playwright...")

    # Method 2: Playwright browser automation (free)
    result = _search_via_playwright(image_data, filename, database, max_results)
    return result


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

            # Try to get similarity score from nearby text
            similarity = _extract_similarity_near(link)

            matches.append(FaceMatch(
                platform=platform,
                profile_url=href,
                username=username,
                similarity_score=similarity,
                thumbnail_url=thumbnail,
                name=name
            ))

    else:
        for card in result_cards:
            try:
                # Extract profile link
                link = card.select_one('a[href*="vk.com"], a[href*="ok.ru"]')
                if not link:
                    link = card.find_parent('a')
                    if not link or ('vk.com' not in str(link.get('href', '')) and 'ok.ru' not in str(link.get('href', ''))):
                        link = card.find('a')

                if not link:
                    continue

                profile_url = link.get('href', '')
                if not profile_url:
                    continue

                if 'vk.com' in profile_url:
                    platform = 'vk'
                elif 'ok.ru' in profile_url:
                    platform = 'ok'
                else:
                    continue

                username = extract_username(profile_url, platform)

                # Extract similarity score
                score_selectors = ['.similarity', '.score', '.match-percent', '[class*="score"]', '[class*="percent"]']
                similarity = None
                for selector in score_selectors:
                    score_elem = card.select_one(selector)
                    if score_elem:
                        score_text = score_elem.get_text()
                        numbers = re.findall(r'(\d+\.?\d*)', score_text)
                        if numbers:
                            val = float(numbers[0])
                            similarity = val / 100.0 if val > 1.0 else val
                            break

                if similarity is None:
                    similarity = _extract_similarity_near(card)

                # Extract thumbnail
                thumb = card.select_one('img')
                thumbnail_url = thumb.get('src') if thumb else None

                # Extract name
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


def _extract_similarity_near(element) -> Optional[float]:
    """Try to extract a similarity percentage from text near an element."""
    try:
        text = element.get_text()
        # Look for patterns like "92%", "0.92", "92.3%"
        pct_match = re.search(r'(\d{1,3}(?:\.\d+)?)\s*%', text)
        if pct_match:
            val = float(pct_match.group(1))
            return val / 100.0 if val > 1.0 else val
    except Exception as e:
        logger.debug(f"[Search4Faces] Similarity extraction failed: {e}")
    return None


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


def search_all_databases_with_status(
    image_path: str = None,
    image_url: str = None,
    image_bytes: bytes = None,
    max_results_per_db: int = 20,
) -> tuple:
    """Like search_all_databases but also returns a status distinguishing
    "searched, no match" from "could not search".

    Returns (matches, status) where status is one of:
    - 'ok'          — a database search ran and returned >=1 match
    - 'empty'       — a search ran (API key or Playwright) but found no match
    - 'no_face'     — no detectable face in the supplied photo (can't search)
    - 'unavailable' — neither the API (no SEARCH4FACES_API_KEY) nor Playwright
                      could perform the search; result is NOT "no photos found"
    - 'error'       — image could not be prepared / unexpected failure

    Any status other than 'ok'/'empty' means the photo was NOT actually
    matched against the database — the empty list must not read as
    "no photos of this person exist online".
    """
    all_matches = []
    seen_urls = set()
    any_searchable = False   # a real face search executed (key or browser)
    any_no_face = False

    for db_name in ['vkok', 'vk01']:
        try:
            result = search_by_photo(
                image_path=image_path, image_url=image_url,
                image_bytes=image_bytes, database=db_name,
                max_results=max_results_per_db,
            )
        except Exception as exc:
            logger.warning(f"Search4faces {db_name} raised: {exc}")
            continue

        if result.success:
            if result.error and 'no face' in result.error.lower():
                any_no_face = True
            else:
                any_searchable = True
                for match in result.matches:
                    if match.profile_url not in seen_urls:
                        all_matches.append(match)
                        seen_urls.add(match.profile_url)
        else:
            logger.warning(f"Search4faces {db_name} failed: {result.error}")
        time.sleep(2)

    if all_matches:
        status = 'ok'
    elif any_searchable:
        status = 'empty'
    elif any_no_face:
        status = 'no_face'
    else:
        status = 'unavailable'
    return all_matches, status


def search_vk_only(
    image_path: str = None,
    image_url: str = None,
    image_bytes: bytes = None,
    max_results: int = 50
) -> Search4FacesResults:
    """Search only VK database (largest, 1.1B faces)."""
    return search_by_photo(
        image_path=image_path, image_url=image_url, image_bytes=image_bytes,
        database='vk01', max_results=max_results
    )


def search_vk_ok_combined(
    image_path: str = None,
    image_url: str = None,
    image_bytes: bytes = None,
    max_results: int = 50
) -> Search4FacesResults:
    """Search combined VK+OK avatars database."""
    return search_by_photo(
        image_path=image_path, image_url=image_url, image_bytes=image_bytes,
        database='vkok', max_results=max_results
    )
