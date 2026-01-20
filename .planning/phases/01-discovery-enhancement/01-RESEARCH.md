# Phase 1: Discovery Enhancement - Research

**Researched:** 2026-01-19
**Domain:** VK profile lookup, Yandex reverse image search
**Confidence:** MEDIUM (verified against existing codebase patterns; external APIs require runtime validation)

## Summary

This phase adds two new discovery sources to the existing search pipeline: VK direct username lookup and Yandex reverse image search. Research confirms both are feasible using HTTP scraping approaches similar to the existing `telegram_search.py` pattern.

**VK Direct Search:** Can validate `vk.com/{username}` existence using simple HTTP GET requests without authentication. The existing `url_validator.py` and `photo_harvester.py` already have VK-aware code that can be extended. VK has anti-bot detection but rate-limited scraping with proper headers works reliably.

**Yandex Reverse Image Search:** Requires multipart form POST to upload images, then HTML parsing of results. No official API exists. Anti-bot detection is aggressive; using the user's uploaded photo (not many automated queries) mitigates this. Returns similar images and pages containing the photo.

**Primary recommendation:** Implement both services as standalone modules in `app/services/` following the `telegram_search.py` pattern. Integrate into `CombinedSearchService` as additional search phases running in parallel with Maigret/Sherlock.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| requests | 2.x | HTTP client | Already used in codebase (`telegram_search.py`, `url_validator.py`) |
| beautifulsoup4 | 4.x | HTML parsing | Already used in `photo_harvester.py` |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| cloudscraper | - | Anti-bot bypass | Optional - already in `photo_harvester.py`, helps with CAPTCHA avoidance |
| lxml | - | Fast HTML parser | Optional - BS4 backend for better performance |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Raw requests | Selenium/Playwright | Overkill for simple profile checks; slower, more resource-intensive |
| Direct scraping | VK API (requires token) | More reliable but requires auth setup; OSINT tools typically avoid auth |
| Direct scraping | SerpAPI/SearchAPI | Paid services; adds cost and external dependency |

**Installation:**
```bash
# No new dependencies needed - all already in requirements.txt
pip install requests beautifulsoup4
# Optional: pip install cloudscraper
```

## Architecture Patterns

### Recommended Project Structure
```
app/services/
    vk_search.py           # NEW: VK username validation
    yandex_image_search.py # NEW: Yandex reverse image search
    combined_search.py     # MODIFY: Add VK and Yandex to pipeline
```

### Pattern 1: Simple Service Module (follow telegram_search.py)
**What:** Single-file service with check function and batch function
**When to use:** Simple HTTP-based profile validation
**Example:**
```python
# Source: existing telegram_search.py pattern
"""VK username search service."""

import requests
import re

def check_vk_username(username: str) -> dict:
    """Check if VK account exists and get profile info."""
    url = f"https://vk.com/{username}"
    try:
        resp = requests.get(url, timeout=10, headers=HEADERS)
        if _is_valid_profile(resp.text):
            return {
                'platform': 'VK',
                'username': username,
                'url': url,
                'display_name': _extract_name(resp.text),
                'exists': True
            }
    except Exception:
        pass
    return {'exists': False}

def check_vk_usernames(usernames: list) -> list:
    """Check multiple VK usernames and return found profiles."""
    results = []
    for username in usernames:
        result = check_vk_username(username)
        if result.get('exists'):
            results.append(result)
    return results
```

### Pattern 2: Integration into CombinedSearchService
**What:** Add new search source as additional phase in pipeline
**When to use:** Extending the orchestrator
**Example:**
```python
# Source: existing combined_search.py pattern
from app.services.vk_search import check_vk_usernames
from app.services.yandex_image_search import yandex_reverse_image_search

# In search() method:
# PHASE 2.5: VK direct search (fast)
self._update_progress(phase="vk_search", current_step=2.5,
                      message="Checking VK...")
vk_results = check_vk_usernames(usernames)
self.progress.log(f"VK found {len(vk_results)} accounts")

# PHASE 2.6: Yandex reverse image (if photo provided)
yandex_results = []
if target_photo_path:
    self._update_progress(phase="yandex_search", current_step=2.6,
                          message="Searching Yandex Images...")
    yandex_results = yandex_reverse_image_search(target_photo_path)
```

### Anti-Patterns to Avoid
- **Overcomplicating with async:** The codebase uses synchronous requests with ThreadPoolExecutor for parallelism. Don't introduce asyncio.
- **Adding new authentication systems:** OSINT tools should work without requiring user API tokens. Keep it simple HTTP scraping.
- **Heavy browser automation:** Selenium/Playwright adds complexity and resource usage. Simple requests work for profile validation.

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTTP session management | Custom connection pooling | `requests.Session()` | Already handles keepalive, cookies, retries |
| HTML parsing | Regex-only parsing | BeautifulSoup | More robust, handles malformed HTML |
| User-agent rotation | Custom header management | Existing `DEFAULT_HEADERS` from `photo_harvester.py` | Already tested, works |
| URL validation | Custom regex | `urlparse` from stdlib | Handles edge cases |
| Profile existence check | Status code only | Content inspection (like `_is_error_page` in url_validator.py) | 200 OK doesn't mean profile exists |

**Key insight:** The codebase already has robust HTTP handling patterns in `url_validator.py` and `photo_harvester.py`. Reuse those patterns rather than building new ones.

## Common Pitfalls

### Pitfall 1: VK Profile Redirect Confusion
**What goes wrong:** VK returns 200 OK even for non-existent usernames, redirecting to generic error page
**Why it happens:** VK doesn't use 404 for missing profiles; it shows "page deleted" or "user not found" message in HTML
**How to avoid:** Check response content for error indicators, not just status code
**Warning signs:** Getting lots of "valid" profiles that don't actually exist

```python
# WRONG: Status code only
if response.status_code == 200:
    return True  # Profile exists

# RIGHT: Check content
error_indicators = [
    'page not found',
    'user not found',
    'deleted',
    'banned',
    'deactivated'
]
content_lower = response.text.lower()
for indicator in error_indicators:
    if indicator in content_lower:
        return False
```

### Pitfall 2: Yandex CAPTCHA/Bot Detection
**What goes wrong:** Yandex blocks requests after few queries, returns CAPTCHA page
**Why it happens:** Aggressive anti-bot detection, especially for image upload endpoints
**How to avoid:**
- Use realistic headers (User-Agent, Accept-Language)
- Rate limit requests (1+ second between)
- Only do one Yandex search per investigation (not per username)
- Consider using the photo upload endpoint rather than URL-based search
**Warning signs:** Response contains "captcha" or "SmartCaptcha" in HTML

### Pitfall 3: Mixing Result Formats
**What goes wrong:** VK/Yandex results don't merge cleanly with Maigret/Sherlock results
**Why it happens:** Different services return different data structures
**How to avoid:** Normalize all results to standard format used by existing pipeline:
```python
{
    'platform': 'VK',
    'url': 'https://vk.com/username',
    'username': 'username',
    'source': 'vk_direct'  # Mark source for debugging
}
```
**Warning signs:** Missing fields, duplicate handling fails, UI display issues

### Pitfall 4: VK Anonymous Access Limitations
**What goes wrong:** Some profile data not visible without authentication
**Why it happens:** VK restricts anonymous access to privacy-protected profiles
**How to avoid:** Accept that only public profiles will be fully accessible. Focus on:
- Profile existence (yes/no)
- Public display name
- Public profile photo URL
Don't try to extract private data (friends, posts, etc.)
**Warning signs:** Empty display names, missing photos for profiles that exist

## Code Examples

Verified patterns from official sources and existing codebase:

### VK Profile Check (HTTP GET)
```python
# Source: Combination of telegram_search.py pattern + url_validator.py
import requests
import re

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5,ru;q=0.3',
}

def check_vk_username(username: str) -> dict:
    """Check if VK account exists and get profile info."""
    url = f"https://vk.com/{username}"
    try:
        resp = requests.get(url, timeout=10, headers=HEADERS, allow_redirects=True)

        # Check for error indicators in content
        content_lower = resp.text.lower()[:5000]
        error_indicators = [
            'page not found',
            'user not found',
            'the page you requested',
            'deleted page',
            'deactivated'
        ]

        for indicator in error_indicators:
            if indicator in content_lower:
                return {'exists': False}

        # Check for valid profile indicators
        if 'page_name' in resp.text or 'profile' in resp.text:
            # Extract display name
            name_match = re.search(r'<title>([^|<]+)', resp.text)
            display_name = name_match.group(1).strip() if name_match else username

            # Extract profile photo
            photo_match = re.search(r'<img[^>]+class="[^"]*page_avatar[^"]*"[^>]+src="([^"]+)"', resp.text)
            photo_url = photo_match.group(1) if photo_match else None

            return {
                'platform': 'VK',
                'username': username,
                'url': url,
                'display_name': display_name,
                'photo_url': photo_url,
                'exists': True,
                'source': 'vk_direct'
            }
    except Exception:
        pass
    return {'exists': False}
```

### Yandex Reverse Image Search (POST Upload)
```python
# Source: pythontutorials.net + adaptation for codebase patterns
import requests
from bs4 import BeautifulSoup
import re

YANDEX_UPLOAD_URL = 'https://yandex.com/images/search'

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9,ru;q=0.8',
    'Referer': 'https://yandex.com/images/',
}

def yandex_reverse_image_search(image_path: str) -> list:
    """
    Perform Yandex reverse image search and return found profiles/pages.

    Args:
        image_path: Path to local image file

    Returns:
        List of result dicts with 'url', 'title', 'snippet'
    """
    results = []

    try:
        # Prepare multipart form data
        with open(image_path, 'rb') as f:
            files = {
                'upfile': ('image.jpg', f, 'image/jpeg')
            }
            data = {
                'rpt': 'imageview',
                'format': 'json',
                'request': '{"blocks":[{"block":"b-page_type_search-by-image__link"}]}'
            }

            resp = requests.post(
                YANDEX_UPLOAD_URL,
                headers=HEADERS,
                files=files,
                data=data,
                timeout=30
            )

        # Handle redirect to results page
        if 'Location' in resp.headers:
            results_url = resp.headers['Location']
        else:
            # Parse response for redirect URL
            # Yandex may return meta refresh or JSON with URL
            location_match = re.search(r'"url"\s*:\s*"([^"]+)"', resp.text)
            if location_match:
                results_url = location_match.group(1).replace('\\/', '/')
            else:
                return results

        # Fetch results page
        results_resp = requests.get(results_url, headers=HEADERS, timeout=30)

        # Parse results
        soup = BeautifulSoup(results_resp.text, 'html.parser')

        # Extract similar image results
        for item in soup.select('.serp-item, .other-sites__item'):
            link = item.select_one('a')
            if link and link.get('href'):
                href = link.get('href')

                # Filter for social media URLs
                if any(domain in href for domain in ['vk.com', 'ok.ru', 'instagram.com', 'facebook.com']):
                    results.append({
                        'platform': _detect_platform(href),
                        'url': href,
                        'source': 'yandex_image',
                        'title': item.get_text(strip=True)[:100]
                    })

    except Exception as e:
        print(f"Yandex search error: {e}")

    return results

def _detect_platform(url: str) -> str:
    """Detect platform from URL."""
    url_lower = url.lower()
    if 'vk.com' in url_lower:
        return 'VK'
    elif 'ok.ru' in url_lower:
        return 'OK'
    elif 'instagram.com' in url_lower:
        return 'Instagram'
    elif 'facebook.com' in url_lower:
        return 'Facebook'
    return 'Web'
```

### Integration Point in CombinedSearchService
```python
# Source: Adaptation of existing combined_search.py pattern
# Add to search() method after Phase 2 (Telegram)

# PHASE 2.5: VK direct search
self._update_progress(phase="vk_search", current_step=2,
                      message="Checking VK profiles...")
self.progress.log("Phase 2.5: VK direct search")
try:
    from app.services.vk_search import check_vk_usernames
    vk_results = check_vk_usernames(usernames)
    self.progress.log(f"VK found {len(vk_results)} accounts")
except ImportError:
    vk_results = []
    self.progress.log("VK search not available")

# PHASE 2.6: Yandex reverse image (if photo provided)
yandex_results = []
if target_photo_path and os.path.exists(target_photo_path):
    self._update_progress(phase="yandex_search", current_step=2,
                          message="Searching Yandex Images...")
    self.progress.log("Phase 2.6: Yandex reverse image search")
    try:
        from app.services.yandex_image_search import yandex_reverse_image_search
        yandex_results = yandex_reverse_image_search(target_photo_path)
        self.progress.log(f"Yandex found {len(yandex_results)} results")
    except ImportError:
        self.progress.log("Yandex search not available")

# Combine all results
all_results = telegram_results + vk_results + yandex_results + maigret_results + sherlock_results
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| VK API with OAuth | Direct HTML scraping | 2023+ | VK API requires app registration; scraping works for public profiles |
| Yandex Images API | Multipart form POST | 2022+ | No official API; POST upload works but has CAPTCHA risk |
| Browser automation for VK | Simple HTTP requests | - | VK doesn't require JS for basic profile view |

**Deprecated/outdated:**
- VK FOAF endpoint (`/foaf.php?id=`) - Still works for metadata extraction but not profile validation
- API token-based approaches - Unnecessary complexity for profile existence checking

## Open Questions

Things that couldn't be fully resolved:

1. **Yandex CAPTCHA frequency**
   - What we know: Yandex triggers CAPTCHA after repeated automated requests
   - What's unclear: Exact threshold (number of requests per time period)
   - Recommendation: Start with single search per investigation; add exponential backoff if CAPTCHA detected

2. **VK rate limiting specifics**
   - What we know: VK has anti-bot detection; rate limiting helps
   - What's unclear: Exact rate limits for anonymous requests
   - Recommendation: Use 0.5-1 second delay between requests (matching existing `request_delay` pattern)

3. **Yandex reverse image result quality**
   - What we know: Returns pages containing similar images
   - What's unclear: How well it finds social media profiles vs general web pages
   - Recommendation: Filter results to prioritize social media domains (VK, OK, Instagram)

## Sources

### Primary (HIGH confidence)
- Existing codebase: `telegram_search.py`, `combined_search.py`, `url_validator.py`, `photo_harvester.py`
- Pattern validation against working code in IBP repository

### Secondary (MEDIUM confidence)
- [pythontutorials.net - Yandex Reverse Image Search](https://www.pythontutorials.net/blog/reverse-search-an-image-in-yandex-images-using-python/) - Verified approach for image upload
- [SerpAPI Yandex Reverse Image API Documentation](https://serpapi.com/yandex-reverse-image-api) - URL parameter format reference
- [GitHub vk-url-scraper](https://github.com/bellingcat/vk-url-scraper) - Bellingcat VK scraping tool (requires auth, but shows patterns)
- [GitHub cryptolok/vMetaDate](https://gist.github.com/cryptolok/8a023875b47e20bc5e64ba8e27294261) - VK FOAF endpoint documentation

### Tertiary (LOW confidence)
- [Bright Data VK Scraper](https://brightdata.com/products/web-scraper/vk) - Commercial tool; confirms VK scrapability
- Various WebSearch results about anti-bot bypass - General patterns, not verified for VK/Yandex specifically

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Uses existing dependencies
- Architecture: HIGH - Follows established codebase patterns
- VK implementation: MEDIUM - Approach verified against existing url_validator.py, but VK HTML structure may change
- Yandex implementation: MEDIUM - POST upload approach verified in tutorials, but CAPTCHA risk needs runtime validation
- Pitfalls: MEDIUM - Based on common patterns and WebSearch findings

**Research date:** 2026-01-19
**Valid until:** 30 days (stable patterns, but external site HTML may change)
