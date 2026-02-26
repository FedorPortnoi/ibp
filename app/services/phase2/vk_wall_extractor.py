"""
VK Wall Post Contact Extractor
==============================
Extract contact information from VK wall posts, comments, photos, and profile fields.
Searches for phone numbers, emails, Telegram links, and contact mentions in:
- User's own wall posts (up to 1000)
- Comments on the user's posts
- Photo descriptions and album descriptions
- Bio/status/about fields
- Posts the user is tagged in

Based on: OSINT techniques for VK contact discovery
"""

import re
import requests
from typing import List, Dict, Optional, Set
from dataclasses import dataclass, field
import logging
from bs4 import BeautifulSoup
import time
import math

logger = logging.getLogger(__name__)


@dataclass
class ExtractedContact:
    """A contact found in VK content."""
    value: str  # Phone number or email
    contact_type: str  # 'phone' or 'email'
    source: str  # Where it was found
    context: str  # Surrounding text
    confidence: str  # 'high', 'medium', 'low'
    post_url: Optional[str] = None
    post_date: Optional[str] = None


@dataclass
class WallExtractionResult:
    """Results from wall extraction."""
    profile_url: str
    phones: List[ExtractedContact] = field(default_factory=list)
    emails: List[ExtractedContact] = field(default_factory=list)
    telegram_usernames: List[str] = field(default_factory=list)
    instagram_usernames: List[str] = field(default_factory=list)
    other_contacts: List[Dict] = field(default_factory=list)
    posts_analyzed: int = 0
    comments_analyzed: int = 0
    photos_analyzed: int = 0
    errors: List[str] = field(default_factory=list)


class VKWallExtractor:
    """
    Extract contacts from VK wall posts, comments, photos, and profile fields.

    Searches public content for:
    - Phone numbers in various Russian formats
    - Email addresses
    - Telegram usernames and t.me links
    - WhatsApp contacts
    - Instagram handles
    """

    # Russian phone patterns (comprehensive)
    PHONE_PATTERNS = [
        # International format with country code
        r'\+7\s*[\(\-]?\s*(\d{3})\s*[\)\-]?\s*(\d{3})\s*[\-]?\s*(\d{2})\s*[\-]?\s*(\d{2})',
        # Domestic format starting with 8
        r'8\s*[\(\-]?\s*(\d{3})\s*[\)\-]?\s*(\d{3})\s*[\-]?\s*(\d{2})\s*[\-]?\s*(\d{2})',
        # Plain digits
        r'\+7(\d{10})',
        r'8(\d{10})',
        # With "тел" prefix
        r'(?:тел\.?|телефон|phone|моб\.?)[\s:]*(\+?[78][\s\-\(\)]?\d{3}[\s\-\(\)]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2})',
    ]

    # Email patterns
    EMAIL_PATTERNS = [
        r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
        # With "почта" prefix
        r'(?:почта|email|e-mail|mail)[\s:]*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
    ]

    # Telegram patterns (extended for Russian VK posts)
    TELEGRAM_PATTERNS = [
        r'(?:https?://)?t\.me/([a-zA-Z0-9_]{5,32})',
        r'(?:https?://)?telegram\.me/([a-zA-Z0-9_]{5,32})',
        # Russian context markers for Telegram
        r'(?:telegram|тг|тел[её]га|телеграм|тележка|tg)[\s:]*@?([a-zA-Z0-9_]{5,32})',
        # "Пишите в тг" / "мой тг" / "тг канал" patterns
        r'(?:пиши(?:те)?|мой|наш|канал|чат|бот)\s+(?:в\s+)?(?:тг|телеграм[ме]?)[\s:]*@?([a-zA-Z0-9_]{5,32})',
        # @username pattern (last — most generic, needs filtering)
        r'@([a-zA-Z][a-zA-Z0-9_]{4,31})',
    ]

    # WhatsApp patterns
    WHATSAPP_PATTERNS = [
        r'(?:whatsapp|wa|вотсап|вацап|ватсап)[\s:]*(\+?[78][\d\s\-\(\)]{10,15})',
        r'wa\.me/(\d+)',
    ]

    # Instagram patterns
    INSTAGRAM_PATTERNS = [
        r'(?:https?://)?(?:www\.)?instagram\.com/([a-zA-Z0-9_.]{3,30})',
        r'(?:инст[аы]?|inst[aа]?|ig)[\s:]*@?([a-zA-Z0-9_.]{3,30})',
    ]

    # Telegram link exclusions — common VK/service paths that aren't usernames
    _TG_EXCLUDE = {
        'share', 'joinchat', 'addstickers', 'login', 'proxy', 'socks',
        'setlanguage', 'addtheme', 'confirmphone', 'iv', 'embed',
    }

    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml',
        'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
    }

    def __init__(self, access_token: Optional[str] = None):
        """
        Initialize wall extractor.

        Args:
            access_token: VK API access token (optional, for API access)
        """
        self.access_token = access_token
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)

    def extract_from_profile(
        self,
        profile_url: str,
        max_posts: int = 50
    ) -> WallExtractionResult:
        """
        Extract contacts from VK profile wall.

        Args:
            profile_url: VK profile URL
            max_posts: Maximum posts to analyze

        Returns:
            WallExtractionResult with found contacts
        """
        result = WallExtractionResult(profile_url=profile_url)

        # Extract user ID from URL
        user_id = self._extract_user_id(profile_url)
        if not user_id:
            result.errors.append("Could not extract user ID from URL")
            return result

        # Try API first if token available
        if self.access_token:
            api_result = self._extract_via_api(user_id, max_posts)
            if api_result:
                return api_result

        # Fallback to web scraping
        return self._extract_via_scraping(profile_url, max_posts, result)

    def _extract_user_id(self, url: str) -> Optional[str]:
        """Extract VK user ID or screen name from URL."""
        patterns = [
            r'vk\.com/id(\d+)',
            r'vk\.com/([a-zA-Z0-9_.]+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    def _resolve_user_id(self, user_id: str) -> Optional[int]:
        """Resolve screen name to numeric user ID via VK API."""
        if user_id.isdigit():
            return int(user_id)

        if not self.access_token:
            return None

        try:
            resp = self.session.get(
                'https://api.vk.com/method/utils.resolveScreenName',
                params={
                    'screen_name': user_id,
                    'access_token': self.access_token,
                    'v': '5.199',
                },
                timeout=10,
            )
            data = resp.json()
            obj = data.get('response', {})
            if obj and obj.get('type') == 'user':
                return obj.get('object_id')
        except Exception as e:
            logger.debug(f"resolveScreenName error: {e}")

        return None

    def _vk_api_call(self, method: str, params: dict) -> Optional[dict]:
        """Generic VK API call helper with error handling."""
        if not self.access_token:
            return None

        params.setdefault('access_token', self.access_token)
        params.setdefault('v', '5.199')

        try:
            resp = self.session.get(
                f'https://api.vk.com/method/{method}',
                params={k: v for k, v in params.items() if v is not None},
                timeout=15,
            )
            data = resp.json()
            if 'error' in data:
                error_msg = data['error'].get('error_msg', 'Unknown')
                error_code = data['error'].get('error_code', 0)
                # 15 = access denied (private profile), 30 = profile is private
                if error_code in (15, 30):
                    logger.debug(f"VK API access denied for {method}: {error_msg}")
                else:
                    logger.warning(f"VK API error in {method}: [{error_code}] {error_msg}")
                return None
            return data.get('response')
        except Exception as e:
            logger.error(f"VK API call {method} error: {e}")
            return None

    def _extract_via_api(
        self,
        user_id: str,
        max_posts: int
    ) -> Optional[WallExtractionResult]:
        """Extract wall posts, comments, photos via VK API."""
        if not self.access_token:
            return None

        result = WallExtractionResult(
            profile_url=f"https://vk.com/{user_id}"
        )

        numeric_id = self._resolve_user_id(user_id)

        # ----- 1. Wall posts (paginated, up to max_posts capped at 1000) -----
        effective_max = min(max_posts, 1000)
        self._scan_wall_posts(user_id, numeric_id, effective_max, result)

        # ----- 2. Comments on own posts (top posts only) -----
        if numeric_id:
            self._scan_post_comments(numeric_id, result)

        # ----- 3. Photo descriptions -----
        if numeric_id:
            self._scan_photos(numeric_id, result)

        # ----- 4. Profile info fields (about, status, activities, interests, site) -----
        self._scan_profile_fields(user_id, result)

        # ----- 5. Posts where user is tagged/mentioned -----
        if numeric_id:
            self._scan_mentions(numeric_id, result)

        # ----- 6. Tagged posts by OTHER people on the subject's wall -----
        self._scan_others_wall_posts(user_id, numeric_id, result)

        # ----- 7. Photo comments -----
        if numeric_id:
            self._scan_photo_comments(numeric_id, result)

        return result

    def _scan_wall_posts(
        self,
        user_id: str,
        numeric_id: Optional[int],
        max_posts: int,
        result: WallExtractionResult,
    ):
        """Scan wall posts with pagination (up to max_posts, max 1000)."""
        fetched = 0
        offset = 0
        batch_size = 100  # VK API max per request

        while fetched < max_posts:
            count = min(batch_size, max_posts - fetched)
            params = {
                'count': count,
                'offset': offset,
            }
            if user_id.isdigit():
                params['owner_id'] = user_id
            else:
                params['domain'] = user_id

            response = self._vk_api_call('wall.get', params)
            if not response:
                break

            posts = response.get('items', [])
            if not posts:
                break

            for post in posts:
                text = post.get('text', '')

                # Also extract text from attachments (links, notes)
                for attach in post.get('attachments', []):
                    if attach.get('type') == 'link':
                        link = attach.get('link', {})
                        text += ' ' + link.get('title', '') + ' ' + link.get('description', '')
                    elif attach.get('type') == 'note':
                        note = attach.get('note', {})
                        text += ' ' + note.get('title', '') + ' ' + note.get('text', '')

                # Check copy_history (reposts) — the subject may repost their own contact info
                for repost in post.get('copy_history', []):
                    text += ' ' + repost.get('text', '')

                post_id = post.get('id')
                owner_id = post.get('owner_id')
                post_date = post.get('date')
                post_url = f"https://vk.com/wall{owner_id}_{post_id}" if owner_id and post_id else None

                self._extract_contacts_from_text(
                    text, result,
                    source='VK wall post',
                    post_url=post_url,
                    post_date=str(post_date) if post_date else None
                )

            fetched += len(posts)
            offset += len(posts)
            result.posts_analyzed = fetched

            # If we got fewer than requested, we've reached the end
            if len(posts) < count:
                break

            # Rate limiting between pages
            if fetched < max_posts:
                time.sleep(0.35)

    def _scan_post_comments(self, owner_id: int, result: WallExtractionResult):
        """Scan comments on wall posts for contact info."""
        # Get the most recent 50 posts to scan comments on
        response = self._vk_api_call('wall.get', {
            'owner_id': owner_id,
            'count': 50,
        })
        if not response:
            return

        posts = response.get('items', [])
        comments_found = 0
        max_comments_per_post = 50
        max_comments_total = 500  # cap to avoid excessive API calls

        for post in posts:
            post_id = post.get('id')
            comment_count = post.get('comments', {}).get('count', 0)
            if not post_id or comment_count == 0:
                continue

            # Fetch comments for this post (up to 50 per post)
            comments_resp = self._vk_api_call('wall.getComments', {
                'owner_id': owner_id,
                'post_id': post_id,
                'count': min(max_comments_per_post, max_comments_total - comments_found),
                'sort': 'asc',
                'need_likes': 0,
            })

            if not comments_resp:
                continue

            comments = comments_resp.get('items', [])
            for comment in comments:
                text = comment.get('text', '')
                if text:
                    post_url = f"https://vk.com/wall{owner_id}_{post_id}?reply={comment.get('id', '')}"
                    comment_date = comment.get('date')
                    self._extract_contacts_from_text(
                        text, result,
                        source='VK post comment',
                        post_url=post_url,
                        post_date=str(comment_date) if comment_date else None,
                    )

            comments_found += len(comments)
            result.comments_analyzed += len(comments)

            if comments_found >= max_comments_total:
                break

            time.sleep(0.35)  # Rate limiting

    def _scan_photos(self, owner_id: int, result: WallExtractionResult):
        """Scan photo descriptions and album descriptions for contacts."""
        # Get all photos (paginated)
        photos_resp = self._vk_api_call('photos.getAll', {
            'owner_id': owner_id,
            'count': 200,
            'photo_sizes': 0,
            'no_service_albums': 0,
        })

        if not photos_resp:
            return

        photos = photos_resp.get('items', [])
        for photo in photos:
            text = photo.get('text', '')
            if text:
                self._extract_contacts_from_text(
                    text, result,
                    source='VK photo description',
                    post_url=None,
                    post_date=str(photo.get('date')) if photo.get('date') else None,
                )

        result.photos_analyzed = len(photos)

        # Also scan album descriptions
        albums_resp = self._vk_api_call('photos.getAlbums', {
            'owner_id': owner_id,
            'need_system': 1,
        })

        if albums_resp:
            albums = albums_resp.get('items', []) if isinstance(albums_resp, dict) else albums_resp
            for album in albums:
                desc = album.get('description', '')
                title = album.get('title', '')
                text = f"{title} {desc}"
                if text.strip():
                    self._extract_contacts_from_text(
                        text, result,
                        source='VK album description',
                    )

    def _scan_profile_fields(self, user_id: str, result: WallExtractionResult):
        """Extract contacts from profile info fields (about, status, site, social links, etc.)."""
        fields = [
            'about', 'status', 'activities', 'interests', 'books', 'games',
            'movies', 'music', 'tv', 'site', 'contacts', 'connections',
            'mobile_phone', 'home_phone', 'personal',
            # Social connections — cross-platform identity
            'twitter', 'facebook', 'skype', 'instagram', 'livejournal',
            # Additional profile fields
            'screen_name', 'career', 'city', 'home_town',
        ]

        response = self._vk_api_call('users.get', {
            'user_ids': user_id,
            'fields': ','.join(fields),
        })

        if not response or not isinstance(response, list) or not response:
            return

        user = response[0]

        # Gather all text fields
        text_parts = []
        for f in ['about', 'status', 'activities', 'interests', 'books',
                   'games', 'movies', 'music', 'tv']:
            val = user.get(f, '')
            if val:
                text_parts.append(val)

        # Site field
        site = user.get('site', '')
        if site:
            text_parts.append(site)

        # Personal section (political, religion, etc. — may contain contacts)
        personal = user.get('personal', {})
        if isinstance(personal, dict):
            for key in ('religion', 'inspired_by', 'people_main', 'life_main'):
                val = personal.get(key, '')
                if isinstance(val, str) and val:
                    text_parts.append(val)

        combined = ' '.join(text_parts)
        if combined.strip():
            self._extract_contacts_from_text(
                combined, result,
                source='VK profile fields',
            )

        # Direct phone fields
        for phone_field in ('mobile_phone', 'home_phone'):
            phone = user.get(phone_field, '')
            if phone and len(phone) > 5:
                digits = re.sub(r'\D', '', phone)
                if len(digits) >= 10:
                    contact = ExtractedContact(
                        value=self._normalize_phone(digits),
                        contact_type='phone',
                        source='VK profile contacts',
                        context=f'{phone_field}: {phone}',
                        confidence='high',
                    )
                    if not any(p.value == contact.value for p in result.phones):
                        result.phones.append(contact)

        # Extract cross-platform social links
        social_fields = {
            'twitter': 'twitter',
            'facebook': 'facebook',
            'instagram': 'instagram',
            'skype': 'skype',
            'livejournal': 'livejournal',
        }
        for field_name, platform in social_fields.items():
            val = (user.get(field_name) or '').strip()
            if not val:
                continue

            if platform == 'instagram':
                username = val.lstrip('@').lower().rstrip('/')
                if username and username not in result.instagram_usernames:
                    result.instagram_usernames.append(username)
            elif platform == 'skype':
                # Skype username can correlate to email (skype_user@outlook.com)
                result.other_contacts.append({
                    'type': 'skype',
                    'value': val,
                    'source': 'VK profile connections',
                })
            else:
                result.other_contacts.append({
                    'type': platform,
                    'value': val,
                    'source': 'VK profile connections',
                })

        # Extract career info for corporate email generation
        career = user.get('career')
        if career and isinstance(career, list):
            for job in career:
                company = job.get('company', '')
                if company:
                    result.other_contacts.append({
                        'type': 'employer',
                        'value': company,
                        'source': 'VK career field',
                    })

    def _scan_mentions(self, user_id: int, result: WallExtractionResult):
        """Scan posts where the user is tagged/mentioned via newsfeed.getMentions."""
        response = self._vk_api_call('newsfeed.getMentions', {
            'owner_id': user_id,
            'count': 50,
        })

        if not response:
            return

        items = response.get('items', [])
        for item in items:
            text = item.get('text', '')
            if text:
                post_id = item.get('id')
                owner = item.get('owner_id') or item.get('from_id')
                post_url = f"https://vk.com/wall{owner}_{post_id}" if owner and post_id else None
                self._extract_contacts_from_text(
                    text, result,
                    source='VK mention/tag',
                    post_url=post_url,
                    post_date=str(item.get('date')) if item.get('date') else None,
                )

    def _scan_others_wall_posts(
        self,
        user_id: str,
        numeric_id: Optional[int],
        result: WallExtractionResult,
    ):
        """Scan posts written by OTHER people on the subject's wall (filter=others).
        Friends often write messages like 'Саша, вот мой номер: 89161234567'.
        Also scans comments on those posts — people often reply with contact info."""
        params = {
            'count': 100,
            'filter': 'others',
        }
        if user_id.isdigit():
            params['owner_id'] = user_id
        else:
            params['domain'] = user_id

        response = self._vk_api_call('wall.get', params)
        if not response:
            return

        posts = response.get('items', [])
        # Collect post IDs with comments for comment scanning below
        posts_with_comments = []

        for post in posts:
            text = post.get('text', '')
            for repost in post.get('copy_history', []):
                text += ' ' + repost.get('text', '')

            post_id = post.get('id')
            owner_id = post.get('owner_id')
            post_date = post.get('date')
            post_url = f"https://vk.com/wall{owner_id}_{post_id}" if owner_id and post_id else None

            self._extract_contacts_from_text(
                text, result,
                source='VK wall post (by others)',
                post_url=post_url,
                post_date=str(post_date) if post_date else None,
            )

            # Track posts with comments for deeper scanning
            comment_count = post.get('comments', {}).get('count', 0)
            if comment_count > 0 and post_id and owner_id:
                posts_with_comments.append((owner_id, post_id))

        # Scan comments on tagged/others posts (up to 200 comments total)
        if posts_with_comments and numeric_id:
            self._scan_others_post_comments(posts_with_comments, result)

    def _scan_others_post_comments(
        self,
        posts: List[tuple],
        result: WallExtractionResult,
    ):
        """Scan comments on posts by others (filter=others) for contact info.
        Limited to 200 total comments across all tagged posts."""
        comments_scanned = 0
        max_comments = 200

        for owner_id, post_id in posts[:20]:  # max 20 posts
            if comments_scanned >= max_comments:
                break

            comments_resp = self._vk_api_call('wall.getComments', {
                'owner_id': owner_id,
                'post_id': post_id,
                'count': min(30, max_comments - comments_scanned),
                'sort': 'asc',
                'need_likes': 0,
            })
            if not comments_resp:
                continue

            comments = comments_resp.get('items', [])
            for comment in comments:
                text = comment.get('text', '')
                if text:
                    comment_url = f"https://vk.com/wall{owner_id}_{post_id}?reply={comment.get('id', '')}"
                    comment_date = comment.get('date')
                    self._extract_contacts_from_text(
                        text, result,
                        source='VK tagged post comment',
                        post_url=comment_url,
                        post_date=str(comment_date) if comment_date else None,
                    )

            comments_scanned += len(comments)
            result.comments_analyzed += len(comments)
            time.sleep(0.35)

    def _scan_photo_comments(self, owner_id: int, result: WallExtractionResult):
        """Scan comments on photos for contact info."""
        # Get recent photos
        photos_resp = self._vk_api_call('photos.getAll', {
            'owner_id': owner_id,
            'count': 50,
            'photo_sizes': 0,
        })
        if not photos_resp:
            return

        photos = photos_resp.get('items', [])
        comments_scanned = 0
        max_photo_comments = 200

        for photo in photos:
            photo_id = photo.get('id')
            if not photo_id:
                continue
            comment_count = photo.get('comments', {})
            if isinstance(comment_count, dict):
                comment_count = comment_count.get('count', 0)
            if not comment_count:
                continue

            comments_resp = self._vk_api_call('photos.getComments', {
                'owner_id': owner_id,
                'photo_id': photo_id,
                'count': min(50, max_photo_comments - comments_scanned),
                'sort': 'asc',
            })
            if not comments_resp:
                continue

            comments = comments_resp.get('items', [])
            for comment in comments:
                text = comment.get('text', '')
                if text:
                    self._extract_contacts_from_text(
                        text, result,
                        source='VK photo comment',
                    )

            comments_scanned += len(comments)
            if comments_scanned >= max_photo_comments:
                break
            time.sleep(0.35)

    def _extract_via_scraping(
        self,
        profile_url: str,
        max_posts: int,
        result: WallExtractionResult
    ) -> WallExtractionResult:
        """Extract wall posts by scraping (limited without login)."""
        try:
            # Try to access public wall
            response = self.session.get(profile_url, timeout=15)

            if response.status_code != 200:
                result.errors.append(f"HTTP {response.status_code}")
                return result

            soup = BeautifulSoup(response.text, 'html.parser')

            # Find wall posts
            post_elements = soup.select('.wall_post_text, .post_content, .wall_text')

            result.posts_analyzed = min(len(post_elements), max_posts)

            for i, post in enumerate(post_elements[:max_posts]):
                text = post.get_text(separator=' ')
                self._extract_contacts_from_text(
                    text, result,
                    source='VK wall post (scraped)',
                    post_url=None
                )

            # Also check profile info sections
            info_sections = soup.select(
                '.profile_info_row, .page_info_row, .pp_info, '
                '.profile_info_block, .page_block_header_extra'
            )

            for section in info_sections:
                text = section.get_text(separator=' ')
                self._extract_contacts_from_text(
                    text, result,
                    source='VK profile info'
                )

            # Check status
            status = soup.select_one('.page_status, .profile_info_status')
            if status:
                self._extract_contacts_from_text(
                    status.get_text(),
                    result,
                    source='VK status'
                )

        except Exception as e:
            result.errors.append(str(e))
            logger.error(f"VK scraping error: {e}")

        return result

    def _extract_contacts_from_text(
        self,
        text: str,
        result: WallExtractionResult,
        source: str,
        post_url: Optional[str] = None,
        post_date: Optional[str] = None
    ):
        """Extract all contact types from text."""
        if not text:
            return

        # Extract phones
        for pattern in self.PHONE_PATTERNS:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                phone = match.group()
                # Normalize phone
                phone_digits = re.sub(r'\D', '', phone)
                if len(phone_digits) >= 10:
                    # Get context (surrounding 50 chars)
                    start = max(0, match.start() - 25)
                    end = min(len(text), match.end() + 25)
                    context = text[start:end].strip()

                    contact = ExtractedContact(
                        value=self._normalize_phone(phone_digits),
                        contact_type='phone',
                        source=source,
                        context=context,
                        confidence='high' if 'тел' in text.lower() or 'phone' in text.lower() else 'medium',
                        post_url=post_url,
                        post_date=post_date
                    )

                    # Avoid duplicates
                    if not any(p.value == contact.value for p in result.phones):
                        result.phones.append(contact)

        # Extract emails
        for pattern in self.EMAIL_PATTERNS:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                email = match.group() if '@' in match.group() else match.group(1)
                email = email.lower()

                # Filter garbage
                if any(x in email for x in ['.png', '.jpg', '.gif', 'example']):
                    continue

                start = max(0, match.start() - 25)
                end = min(len(text), match.end() + 25)
                context = text[start:end].strip()

                contact = ExtractedContact(
                    value=email,
                    contact_type='email',
                    source=source,
                    context=context,
                    confidence='high' if 'почта' in text.lower() or 'email' in text.lower() else 'medium',
                    post_url=post_url,
                    post_date=post_date
                )

                if not any(e.value == contact.value for e in result.emails):
                    result.emails.append(contact)

        # Extract Telegram usernames
        for pattern in self.TELEGRAM_PATTERNS:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                username = match.group(1) if match.lastindex else match.group()
                username = username.lstrip('@').lower()

                # Filter out service paths and too-short names
                if len(username) < 5:
                    continue
                if username in self._TG_EXCLUDE:
                    continue
                # Filter obvious non-usernames (all digits, common words)
                if username.isdigit():
                    continue

                if username not in result.telegram_usernames:
                    result.telegram_usernames.append(username)

        # Extract Instagram usernames
        for pattern in self.INSTAGRAM_PATTERNS:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                username = match.group(1).lower().rstrip('/')
                if len(username) >= 3 and username not in result.instagram_usernames:
                    result.instagram_usernames.append(username)

        # Extract WhatsApp mentions
        for pattern in self.WHATSAPP_PATTERNS:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                wa_contact = match.group(1) if match.lastindex else match.group()
                # Deduplicate
                if not any(
                    c.get('type') == 'whatsapp' and c.get('value') == wa_contact
                    for c in result.other_contacts
                ):
                    result.other_contacts.append({
                        'type': 'whatsapp',
                        'value': wa_contact,
                        'source': source
                    })

    def _normalize_phone(self, digits: str) -> str:
        """Normalize phone to +7 (XXX) XXX-XX-XX format."""
        if len(digits) == 11:
            if digits.startswith('8'):
                digits = '7' + digits[1:]
            return f"+{digits[0]} ({digits[1:4]}) {digits[4:7]}-{digits[7:9]}-{digits[9:11]}"
        elif len(digits) == 10:
            return f"+7 ({digits[0:3]}) {digits[3:6]}-{digits[6:8]}-{digits[8:10]}"
        return digits

    def extract_from_multiple_profiles(
        self,
        profile_urls: List[str],
        max_posts_each: int = 30
    ) -> List[WallExtractionResult]:
        """Extract contacts from multiple VK profiles."""
        results = []
        for url in profile_urls:
            result = self.extract_from_profile(url, max_posts_each)
            results.append(result)
            time.sleep(0.5)  # Rate limiting
        return results


def extract_vk_wall_contacts(
    profile_url: str,
    access_token: Optional[str] = None
) -> WallExtractionResult:
    """Convenience function for single profile extraction."""
    extractor = VKWallExtractor(access_token=access_token)
    return extractor.extract_from_profile(profile_url)


def extract_multiple_vk_wall_contacts(
    profile_urls: List[str],
    access_token: Optional[str] = None
) -> List[WallExtractionResult]:
    """Convenience function for multiple profile extraction."""
    extractor = VKWallExtractor(access_token=access_token)
    return extractor.extract_from_multiple_profiles(profile_urls)
