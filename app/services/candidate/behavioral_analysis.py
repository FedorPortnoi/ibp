"""
Behavioral Analysis Orchestrator (Stage 6)
==========================================
Orchestrates text analysis, geo extraction, and activity timeline
construction from VK wall posts and profile data.
"""

import hashlib
import logging
import os
import random
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

import requests

logger = logging.getLogger(__name__)

VK_API_VERSION = '5.199'

# VK last_seen platform codes
VK_PLATFORM_NAMES = {
    1: 'Mobile',
    2: 'iPhone',
    3: 'iPad',
    4: 'Android',
    5: 'Windows Phone',
    6: 'Windows',
    7: 'Web',
}


def analyze_last_seen_patterns(vk_profiles: List[Dict], vk_token: str) -> Dict[str, Any]:
    """
    Fetch and analyze last_seen data from VK profiles.

    Returns:
        {
            'profiles': [{vk_id, last_seen_ts, last_seen_dt, platform, platform_name, online}],
            'most_recent': {vk_id, last_seen_ts, last_seen_dt, platform_name, time_ago},
            'preferred_platform': str,
            'flags': [...]
        }
    """
    if not vk_token or not vk_profiles:
        return {}

    results = []
    platform_counts = Counter()

    for profile in vk_profiles[:3]:
        vk_id = profile.get('platform_id') or profile.get('vk_id') or profile.get('id')
        if not vk_id:
            url = profile.get('url', '')
            if '/id' in url:
                try:
                    vk_id = int(url.split('/id')[-1].split('?')[0].split('/')[0])
                except (ValueError, IndexError):
                    pass
        if not vk_id:
            continue

        try:
            resp = requests.get('https://api.vk.com/method/users.get', params={
                'user_ids': vk_id,
                'fields': 'last_seen,online',
                'access_token': vk_token,
                'v': VK_API_VERSION,
            }, timeout=10)
            data = resp.json()
            users = data.get('response', [])
            if not users:
                continue

            user = users[0]
            last_seen = user.get('last_seen')
            if not last_seen:
                continue

            ts = last_seen.get('time', 0)
            platform_code = last_seen.get('platform', 0)
            platform_name = VK_PLATFORM_NAMES.get(platform_code, f'Unknown ({platform_code})')
            is_online = user.get('online', 0) == 1

            try:
                dt = datetime.fromtimestamp(ts)
                dt_iso = dt.isoformat()
            except (ValueError, OSError):
                dt = None
                dt_iso = ''

            if platform_code in VK_PLATFORM_NAMES:
                platform_counts[platform_name] += 1

            results.append({
                'vk_id': vk_id,
                'last_seen_ts': ts,
                'last_seen_dt': dt_iso,
                'platform': platform_code,
                'platform_name': platform_name,
                'online': is_online,
            })
        except Exception as e:
            logger.warning(f"VK last_seen fetch for {vk_id} failed: {e}")

    if not results:
        return {}

    # Find most recent
    most_recent = max(results, key=lambda r: r.get('last_seen_ts', 0))
    now = datetime.now()
    try:
        last_dt = datetime.fromtimestamp(most_recent['last_seen_ts'])
        delta = now - last_dt
        if delta.days == 0:
            if delta.seconds < 3600:
                time_ago = f'{delta.seconds // 60} мин. назад'
            else:
                time_ago = f'{delta.seconds // 3600} ч. назад'
        elif delta.days == 1:
            time_ago = 'вчера'
        elif delta.days < 30:
            time_ago = f'{delta.days} дн. назад'
        elif delta.days < 365:
            time_ago = f'{delta.days // 30} мес. назад'
        else:
            time_ago = f'{delta.days // 365} г. назад'
    except (ValueError, OSError):
        time_ago = ''
        delta = None

    most_recent['time_ago'] = time_ago

    # Preferred platform
    preferred = platform_counts.most_common(1)[0][0] if platform_counts else ''

    # Risk flags
    flags = []
    if delta and delta.days > 180:
        flags.append({
            'type': 'suspicion',
            'code': 'account_inactive',
            'description': f'Аккаунт неактивен более 6 месяцев (последний визит: {time_ago})',
            'severity': 'low',
        })
    elif delta and delta.days < 1:
        flags.append({
            'type': 'fact',
            'code': 'recently_active',
            'description': f'Активен сегодня ({time_ago})',
            'severity': 'info',
        })

    return {
        'profiles': results,
        'most_recent': most_recent,
        'preferred_platform': preferred,
        'flags': flags,
    }


# ── VK Group Intelligence ──

GROUP_CATEGORIES = {
    'political_opposition': [
        'навальный', 'navalny', 'оппозиция', 'протест', 'митинг',
        'фбк', 'fbk', 'антикоррупция', 'свободу', 'долой',
        'несогласные', 'либертарианц',
    ],
    'political_progovernment': [
        'единая россия', 'молодая гвардия', 'юнармия', 'нод',
        'антимайдан', 'ночные волки', 'народный фронт',
    ],
    'religious_extremist': [
        'свидетели иеговы', 'хизб', 'таблиги', 'ваххаб',
        'салаф', 'исламское государство', 'игил',
    ],
    'criminal': [
        'аук', 'арестантский', 'вор в законе', 'криминал',
        'зк ', 'тюрьма', 'зона', 'урка', 'блатн',
    ],
    'gambling': [
        'казино', 'ставки', 'букмекер', 'покер', 'слоты',
        'ставка', 'выигрыш', 'беттинг',
    ],
    'drugs': [
        'наркотик', 'закладк', 'соль ', 'скорость ', 'марихуан',
        'гашиш', 'спайс', 'мефедрон',
    ],
    'security_interest': [
        'взлом', 'хакер', 'hack', 'exploit', 'уязвимост',
        'darknet', 'даркнет', 'анонимность',
    ],
}


def _categorize_group(group: dict) -> list:
    """Return list of risk categories for a VK group."""
    text = (
        (group.get('name') or '') + ' ' +
        (group.get('description') or '') + ' ' +
        (group.get('activity') or '')
    ).lower()

    categories = []
    for category, keywords in GROUP_CATEGORIES.items():
        if any(kw in text for kw in keywords):
            categories.append(category)
    return categories


def fetch_vk_groups(vk_id: int, vk_token: str) -> list:
    """Fetch groups the candidate belongs to."""
    try:
        r = requests.get('https://api.vk.com/method/groups.get', params={
            'user_id': vk_id,
            'extended': 1,
            'fields': 'name,screen_name,description,members_count,activity',
            'count': 200,
            'access_token': vk_token,
            'v': VK_API_VERSION,
        }, timeout=15)
        data = r.json()
        return data.get('response', {}).get('items', [])
    except Exception as e:
        logger.warning(f"VK groups fetch for {vk_id} failed: {e}")
        return []


def analyze_groups(groups: list) -> dict:
    """Categorize VK groups and produce intelligence report."""
    flagged = []
    all_categories = {}

    for group in groups:
        cats = _categorize_group(group)
        if cats:
            flagged.append({
                'name': group.get('name', ''),
                'url': f"https://vk.com/{group.get('screen_name', '')}",
                'members': group.get('members_count', 0),
                'categories': cats,
                'risk': 'HIGH' if any(c in ('criminal', 'religious_extremist', 'drugs')
                                      for c in cats) else 'MEDIUM',
            })
        for cat in cats:
            all_categories[cat] = all_categories.get(cat, 0) + 1

    return {
        'total_groups': len(groups),
        'flagged_groups': flagged,
        'category_counts': all_categories,
        'risk_summary': _summarize_group_risk(flagged),
    }


def _summarize_group_risk(flagged: list) -> str:
    """Build human-readable summary of group risk."""
    if not flagged:
        return 'Подозрительных групп не обнаружено'
    high_risk = [g for g in flagged if g.get('risk') == 'HIGH']
    if high_risk:
        return f'Обнаружено {len(high_risk)} группа(ы) высокого риска из {len(flagged)} подозрительных'
    return f'Обнаружено {len(flagged)} группа(ы) среднего риска'


# ── Activity Pattern Analysis ──

def analyze_activity_patterns(wall_posts: list, last_seen_data: Optional[Dict] = None) -> dict:
    """Detect posting patterns — timezone, night activity, frequency.

    Args:
        wall_posts: VK wall posts with 'date' timestamps
        last_seen_data: Optional last_seen analysis from analyze_last_seen_patterns()
    """
    if not wall_posts and not last_seen_data:
        return {}

    hours = []
    days = []
    dates = []

    for post in wall_posts or []:
        ts = post.get('date', 0)
        if ts:
            try:
                dt = datetime.fromtimestamp(ts)
                hours.append(dt.hour)
                days.append(dt.weekday())
                dates.append(dt.date())
            except (ValueError, OSError):
                pass

    # Include last_seen timestamps for better coverage
    if last_seen_data:
        for profile in last_seen_data.get('profiles', []):
            ts = profile.get('last_seen_ts', 0)
            if ts:
                try:
                    dt = datetime.fromtimestamp(ts)
                    hours.append(dt.hour)
                    days.append(dt.weekday())
                    dates.append(dt.date())
                except (ValueError, OSError):
                    pass

    if not hours:
        return {}

    hour_counts = Counter(hours)
    day_counts = Counter(days)

    peak_hours = sorted(hour_counts.items(), key=lambda x: x[1], reverse=True)[:3]

    # Night activity (23:00 - 05:00)
    night_posts = sum(hour_counts.get(h, 0)
                      for h in list(range(23, 24)) + list(range(0, 6)))
    night_pct = (night_posts / len(hours) * 100) if hours else 0

    tz_hint = _estimate_timezone(peak_hours[0][0] if peak_hours else 12)

    if dates:
        date_range = (max(dates) - min(dates)).days + 1
        posts_per_day = len(wall_posts) / max(date_range, 1)
    else:
        posts_per_day = 0

    flags = []
    if night_pct > 40:
        flags.append({
            'type': 'suspicion',
            'code': 'high_night_activity',
            'description': f'Высокая ночная активность: {night_pct:.0f}% постов с 23:00 до 05:00',
            'severity': 'low',
        })
    if tz_hint and tz_hint != 'moscow':
        flags.append({
            'type': 'fact',
            'code': 'unusual_timezone',
            'description': f'Пик активности указывает на часовой пояс: {tz_hint}',
            'severity': 'low',
        })

    result = {
        'peak_hours': peak_hours,
        'night_activity_pct': round(night_pct, 1),
        'posts_per_day': round(posts_per_day, 2),
        'estimated_timezone': tz_hint,
        'day_distribution': dict(day_counts),
        'hour_distribution': dict(hour_counts),
        'activity_flags': flags,
    }

    # Merge last_seen data if available
    if last_seen_data:
        most_recent = last_seen_data.get('most_recent', {})
        result['last_seen'] = {
            'last_online_dt': most_recent.get('last_seen_dt', ''),
            'last_online_ago': most_recent.get('time_ago', ''),
            'platform_name': most_recent.get('platform_name', ''),
            'online_now': most_recent.get('online', False),
        }
        result['preferred_platform'] = last_seen_data.get('preferred_platform', '')
        # Add last_seen risk flags
        for flag in last_seen_data.get('flags', []):
            flags.append(flag)

    return result


def _estimate_timezone(peak_hour: int) -> str:
    """Rough timezone estimation from peak posting hour."""
    local_peak = 16
    offset = peak_hour - local_peak

    tz_map = {
        'moscow': range(-2, 2),
        'yekaterinburg': range(2, 5),
        'novosibirsk': range(5, 8),
        'vladivostok': range(7, 10),
        'europe': range(-5, -2),
    }
    for name, r in tz_map.items():
        if offset in r:
            return name
    return 'unknown'


# ── Profile Anomaly Detection ──

def detect_profile_anomalies(vk_profile: dict, check_full_name: str) -> list:
    """Detect suspicious VK profile characteristics."""
    flags = []

    # Check 1: Name mismatch
    vk_name = f"{vk_profile.get('last_name', '')} {vk_profile.get('first_name', '')}".strip()
    if vk_name and check_full_name:
        from difflib import SequenceMatcher
        similarity = SequenceMatcher(None, vk_name.lower(), check_full_name.lower()).ratio()
        if similarity < 0.5:
            flags.append({
                'type': 'suspicion',
                'code': 'name_mismatch',
                'description': f'Имя в VK "{vk_name}" значительно отличается от указанного "{check_full_name}"',
                'severity': 'medium',
            })

    # Check 2: New account (high VK ID)
    vk_id = vk_profile.get('id', 0)
    if vk_id > 700_000_000:
        flags.append({
            'type': 'fact',
            'code': 'new_account',
            'description': f'Аккаунт создан относительно недавно (ID: {vk_id})',
            'severity': 'low',
        })

    # Check 3: Private profile
    if vk_profile.get('is_closed', False):
        flags.append({
            'type': 'fact',
            'code': 'private_profile',
            'description': 'Профиль закрыт — данные ограничены',
            'severity': 'low',
        })

    # Check 4: No photo
    photo = vk_profile.get('photo_200') or vk_profile.get('photo_100', '')
    if not photo or 'camera_200' in photo:
        flags.append({
            'type': 'fact',
            'code': 'no_photo',
            'description': 'Фото профиля отсутствует',
            'severity': 'low',
        })

    return flags


def store_vk_snapshot(check, vk_profile: dict):
    """Store VK profile snapshot for future comparison."""
    photo_url = vk_profile.get('photo_200', '')
    check.vk_snapshot = {
        'name': f"{vk_profile.get('last_name', '')} {vk_profile.get('first_name', '')}",
        'city': (vk_profile.get('city') or {}).get('title', ''),
        'photo_hash': hashlib.md5(photo_url.encode(), usedforsecurity=False).hexdigest() if photo_url else '',
        'is_closed': vk_profile.get('is_closed', False),
        'vk_id': vk_profile.get('id'),
        'snapshot_date': datetime.now().isoformat(),
    }


# ── Connected Checks ──

def find_connected_checks(check) -> list:
    """Find connections between this check and all previous completed checks."""
    from app.models.candidate_check import CandidateCheck

    connections = []
    try:
        all_checks = CandidateCheck.query.filter(
            CandidateCheck.status == 'complete',
            CandidateCheck.id != check.id,
        ).all()
    except Exception as e:
        logger.warning(f"Connected checks query failed: {e}")
        return []

    # This check's data
    my_contacts = check.contact_discoveries or {}
    my_phones = {c.get('number') or c.get('value', '') for c in (my_contacts.get('phones') or []) if c.get('number') or c.get('value')}
    my_emails = {c.get('email', '') for c in (my_contacts.get('emails') or []) if c.get('email')}
    my_biz_inns = {b.get('inn') for b in (check.business_records or []) if b.get('inn')}

    for other in all_checks:
        shared = []

        # Shared business (same INN company)
        other_biz_inns = {b.get('inn') for b in (other.business_records or []) if b.get('inn')}
        shared_biz = my_biz_inns & other_biz_inns
        if shared_biz:
            shared.append({
                'type': 'shared_business',
                'description': f'Совместный бизнес: {len(shared_biz)} компани(й)',
                'inns': list(shared_biz),
            })

        # Shared phone
        other_contacts = other.contact_discoveries or {}
        other_phones = {c.get('number') or c.get('value', '') for c in (other_contacts.get('phones') or []) if c.get('number') or c.get('value')}
        shared_phones = my_phones & other_phones
        if shared_phones:
            shared.append({
                'type': 'shared_phone',
                'description': f'Общий телефон: {list(shared_phones)[0]}',
            })

        # Shared email
        other_emails = {c.get('email', '') for c in (other_contacts.get('emails') or []) if c.get('email')}
        shared_emails = my_emails & other_emails
        if shared_emails:
            shared.append({
                'type': 'shared_email',
                'description': f'Общий email: {list(shared_emails)[0]}',
            })

        if shared:
            connections.append({
                'connected_check_id': other.id,
                'connected_name': other.full_name,
                'connected_check_date': other.created_at.isoformat() if other.created_at else '',
                'connected_risk_level': other.risk_level,
                'connection_types': shared,
            })

    return connections


def _get_vk_profiles(check) -> List[Dict]:
    """Get VK profiles from confirmed or social media profiles."""
    confirmed = check.confirmed_profiles or check.social_media_profiles or []
    return [p for p in confirmed if p.get('platform') == 'vk']


def _fetch_vk_wall_posts(vk_profiles: List[Dict], token: str, max_posts: int = 100) -> List[Dict]:
    """Fetch VK wall posts for text and timeline analysis."""
    if not token or not vk_profiles:
        return []

    all_posts = []
    for profile in vk_profiles[:2]:  # Max 2 VK profiles
        vk_id = profile.get('platform_id') or profile.get('vk_id') or profile.get('id')
        # Fallback: extract numeric ID from URL (e.g., https://vk.com/id380010961)
        if not vk_id:
            url = profile.get('url', '')
            if '/id' in url:
                try:
                    vk_id = int(url.split('/id')[-1].split('?')[0].split('/')[0])
                except (ValueError, IndexError):
                    pass
        if not vk_id:
            continue

        try:
            resp = requests.get(
                'https://api.vk.com/method/wall.get',
                params={
                    'owner_id': vk_id,
                    'count': max_posts,
                    'access_token': token,
                    'v': VK_API_VERSION,
                },
                timeout=15,
            )
            data = resp.json()
            if 'response' in data:
                items = data['response'].get('items', [])
                for item in items:
                    post = {
                        'text': item.get('text', ''),
                        'date': item.get('date'),
                        'id': item.get('id'),
                        'owner_id': item.get('owner_id'),
                    }
                    if item.get('geo'):
                        post['geo'] = item['geo']
                    all_posts.append(post)
        except Exception as e:
            logger.warning(f"VK wall fetch for {vk_id} failed: {e}")

    return all_posts


def _run_text_analysis(posts: List[Dict]) -> Dict:
    """Run text analysis on wall posts."""
    try:
        from app.services.phase3.text_analyzer import TextAnalyzer
        analyzer = TextAnalyzer()
        result = analyzer.analyze_posts(posts)
        return result.to_dict()
    except Exception as e:
        logger.error(f"Text analysis failed: {e}")
        return {}


def _run_geo_extraction(profiles: List[Dict]) -> Dict:
    """Run geo extraction from profiles."""
    try:
        from app.services.phase3.geo_extractor import GeoExtractor
        extractor = GeoExtractor()
        analysis = extractor.extract_from_profiles(profiles)
        result = analysis.to_dict()
        # Add map data
        result['map_data'] = extractor.generate_map_data(analysis.locations)
        return result
    except Exception as e:
        logger.error(f"Geo extraction failed: {e}")
        return {}


def _build_activity_timeline(posts: List[Dict], check, last_seen_data: Optional[Dict] = None) -> List[Dict]:
    """Build activity timeline from wall posts, last_seen, and check events."""
    events = []

    # From wall posts
    for post in posts:
        ts = post.get('date')
        if not ts:
            continue
        try:
            dt = datetime.fromtimestamp(ts)
            text = (post.get('text') or '')[:100]
            events.append({
                'timestamp': dt.isoformat(),
                'type': 'post',
                'source': 'vk_wall',
                'summary': text if text else 'Запись на стене',
            })
        except (ValueError, OSError):
            pass

    # From last_seen (most recent activity data point)
    if last_seen_data:
        most_recent = last_seen_data.get('most_recent', {})
        ts = most_recent.get('last_seen_ts', 0)
        if ts:
            try:
                dt = datetime.fromtimestamp(ts)
                platform = most_recent.get('platform_name', '')
                events.append({
                    'timestamp': dt.isoformat(),
                    'type': 'last_seen',
                    'source': 'vk_last_seen',
                    'summary': f'Последний визит VK ({platform})' if platform else 'Последний визит VK',
                })
            except (ValueError, OSError):
                pass

    # From check creation
    if check.created_at:
        events.append({
            'timestamp': check.created_at.isoformat(),
            'type': 'check_started',
            'source': 'system',
            'summary': 'Проверка начата',
        })

    # Sort newest first
    events.sort(key=lambda e: e.get('timestamp', ''), reverse=True)
    return events[:100]


def search_telegram_public_messages(full_name: str, username: str = None) -> dict:
    """
    Search Telegram public channels/groups for messages mentioning the target.

    Uses Telethon's SearchGlobalRequest to find public messages.
    Follows the same async/session pattern as telegram_discovery.py Method C.

    Args:
        full_name: Target's full name for search query.
        username: Optional Telegram username (searched first if available).

    Returns:
        {
            'messages': [{'text': str, 'date': str, 'chat_id': int}],
            'total_found': int,
            'groups_mentioned': [],  # unique chat IDs
            'error': str or None
        }
    """
    import asyncio

    empty_result = {
        'messages': [],
        'total_found': 0,
        'groups_mentioned': [],
        'error': None,
    }

    # Check Telethon credentials
    api_id = os.environ.get('TELEGRAM_API_ID', '')
    api_hash = os.environ.get('TELEGRAM_API_HASH', '')
    phone = os.environ.get('TELEGRAM_PHONE', '')

    if not all([api_id, api_hash, phone]):
        logger.info("Telegram public search: credentials not configured, skipping")
        return empty_result

    # Check session file exists (same path logic as telegram_discovery.py)
    session_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        '..', '..', '..', 'tg_session'
    )
    session_file = os.path.join(session_dir, 'ibp_session.session')
    if not os.path.exists(session_file):
        logger.info("Telegram public search: session file not found, skipping")
        return empty_result

    session_path = os.path.join(session_dir, 'ibp_session')

    # Build search query: prefer username, fall back to full name
    query = username if username else full_name
    if not query or not query.strip():
        return empty_result
    query = query.strip()

    async def _search_global():
        from telethon import TelegramClient
        from telethon.tl.functions.messages import SearchGlobalRequest
        from telethon.tl.types import InputMessagesFilterEmpty

        client = TelegramClient(
            session_path, int(api_id), api_hash,
            connection_retries=1, retry_delay=0, timeout=10,
            request_retries=1,
        )
        try:
            await asyncio.wait_for(client.connect(), timeout=10)
        except (asyncio.TimeoutError, RuntimeError, OSError) as e:
            logger.warning(f"Telegram public search: connect failed: {e}")
            try:
                await client.disconnect()
            except Exception:
                pass
            return empty_result

        if not await client.is_user_authorized():
            logger.warning(
                "Telegram public search: session expired or not authorized. "
                "Run: python scripts/auth_telegram.py"
            )
            await client.disconnect()
            return {
                'messages': [],
                'total_found': 0,
                'groups_mentioned': [],
                'error': 'Telegram session not authorized',
            }

        messages = []
        chat_ids = set()
        try:
            result = await asyncio.wait_for(
                client(SearchGlobalRequest(
                    q=query,
                    filter=InputMessagesFilterEmpty(),
                    min_date=None,
                    max_date=None,
                    offset_rate=0,
                    offset_peer=await client.get_input_entity('me'),
                    offset_id=0,
                    limit=50,
                )),
                timeout=30,
            )

            for msg in result.messages[:20]:
                text = getattr(msg, 'message', '') or ''
                date = getattr(msg, 'date', None)
                peer_id = getattr(msg, 'peer_id', None)

                chat_id = 0
                if peer_id:
                    chat_id = getattr(peer_id, 'channel_id', 0) or \
                              getattr(peer_id, 'chat_id', 0) or \
                              getattr(peer_id, 'user_id', 0)

                messages.append({
                    'text': text[:200],
                    'date': date.isoformat() if date else '',
                    'chat_id': chat_id,
                })
                if chat_id:
                    chat_ids.add(chat_id)

            total_found = getattr(result, 'count', len(result.messages)) if hasattr(result, 'count') else len(result.messages)

        finally:
            try:
                await client.disconnect()
            except Exception:
                pass

        return {
            'messages': messages,
            'total_found': total_found,
            'groups_mentioned': list(chat_ids),
            'error': None,
        }

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                asyncio.wait_for(_search_global(), timeout=15)
            )
        finally:
            loop.close()
        return result
    except (asyncio.TimeoutError, RuntimeError) as e:
        logger.warning(f"Telegram public search: timeout/event loop error: {e}")
        return {
            'messages': [],
            'total_found': 0,
            'groups_mentioned': [],
            'error': f'Telegram error: {e}',
        }
    except ImportError:
        logger.info("Telegram public search: Telethon not installed, skipping")
        return empty_result
    except Exception as e:
        logger.error(f"Telegram public search error: {e}")
        return {
            'messages': [],
            'total_found': 0,
            'groups_mentioned': [],
            'error': str(e),
        }


def _demo_response() -> Dict[str, Any]:
    """Return realistic fake data for demo mode."""
    base_date = datetime(2025, 8, 15)
    timeline = []
    for i in range(30):
        dt = base_date + timedelta(days=i * 6, hours=random.choice([9, 12, 15, 18, 20, 22, 23, 2, 3]))
        timeline.append({
            'timestamp': dt.isoformat(),
            'type': 'post',
            'source': 'vk_wall',
            'summary': random.choice([
                'Хороший день на работе',
                'Встреча с друзьями',
                'Новый проект запущен',
                'Отпуск в Сочи',
                'Спортзал утром',
                'Книга прочитана',
                'Концерт вечером',
                'Рабочая поездка в СПб',
            ]),
        })
    timeline.sort(key=lambda e: e['timestamp'], reverse=True)

    return {
        'text_analysis': {
            'sentiment': {
                'score': 0.15,
                'label': 'neutral',
                'positive_words': ['хорошо', 'отлично', 'супер'],
                'negative_words': ['устал'],
                'confidence': 0.6,
            },
            'keywords': [
                ('работа', 12), ('проект', 8), ('друзья', 7), ('москва', 6),
                ('спорт', 5), ('книга', 4), ('кино', 4), ('код', 3),
                ('семья', 3), ('отпуск', 2),
            ],
            'topics': {
                'работа': 0.35,
                'хобби': 0.25,
                'путешествия': 0.20,
            },
            'word_count': 1500,
            'avg_word_length': 5.2,
            'emoji_count': 15,
            'hashtags': ['работа', 'спорт', 'москва'],
            'mentions': [],
            'language': 'ru',
            'posting_times': [9, 12, 15, 18, 20, 22, 23, 2, 3, 18, 20, 22],
        },
        'geo_analysis': {
            'locations': [
                {'lat': 55.7558, 'lng': 37.6173, 'name': 'Москва', 'city': 'Москва', 'country': 'Russia', 'confidence': 'high', 'source': 'VK profile', 'timestamp': '', 'address': '', 'post_url': ''},
                {'lat': 59.9343, 'lng': 30.3351, 'name': 'Санкт-Петербург', 'city': 'Санкт-Петербург', 'country': 'Russia', 'confidence': 'medium', 'source': 'VK check-in', 'timestamp': '', 'address': '', 'post_url': ''},
                {'lat': 55.8304, 'lng': 49.0661, 'name': 'Казань', 'city': 'Казань', 'country': 'Russia', 'confidence': 'medium', 'source': 'VK check-in', 'timestamp': '', 'address': '', 'post_url': ''},
                {'lat': 43.6028, 'lng': 39.7342, 'name': 'Сочи', 'city': 'Сочи', 'country': 'Russia', 'confidence': 'medium', 'source': 'VK check-in', 'timestamp': '', 'address': '', 'post_url': ''},
            ],
            'home_location': {'lat': 55.7558, 'lng': 37.6173, 'name': 'Москва', 'city': 'Москва', 'country': 'Russia', 'confidence': 'high', 'source': 'VK profile', 'timestamp': '', 'address': '', 'post_url': ''},
            'work_location': None,
            'frequent_places': [('Москва', 5), ('Санкт-Петербург', 2), ('Казань', 1), ('Сочи', 1)],
            'travel_destinations': ['Казань', 'Сочи'],
            'timeline': [],
            'stats': {'total_locations': 4, 'unique_cities': 4},
            'map_data': {
                'center': [55.7558, 37.6173],
                'zoom': 6,
                'markers': [
                    {'lat': 55.7558, 'lng': 37.6173, 'popup': '<b>Москва</b>', 'color': 'blue'},
                    {'lat': 59.9343, 'lng': 30.3351, 'popup': '<b>Санкт-Петербург</b>', 'color': 'blue'},
                ],
            },
        },
        'activity_timeline': timeline,
    }


def run_behavioral_analysis(check, task_status_callback=None) -> Dict[str, Any]:
    """
    Stage 6: Behavioral Intelligence.

    Orchestrates text analysis, geo extraction, and activity timeline.

    Args:
        check: CandidateCheck model instance
        task_status_callback: Optional callable(stage, message, percent)

    Returns:
        {
            'text_analysis': {...},
            'geo_analysis': {...},
            'activity_timeline': [...]
        }
    """
    def _update(msg, pct=None):
        if task_status_callback:
            try:
                task_status_callback('behavioral', msg, pct)
            except Exception as e:
                logger.debug(f"[BehavioralAnalysis] Status callback failed: {e}")

    from app.utils.vk_token_manager import get_vk_token
    # wall.get requires user token (private data)
    vk_token = get_vk_token('private') or get_vk_token('search')
    vk_profiles = _get_vk_profiles(check)
    all_profiles = check.confirmed_profiles or check.social_media_profiles or []

    # Demo mode: no VK token
    if not vk_token:
        _update('Демо-режим: нет VK токена', 80)
        return _demo_response()

    results = {
        'text_analysis': {},
        'geo_analysis': {},
        'activity_timeline': [],
        'group_analysis': {},
        'activity_patterns': {},
        'profile_anomalies': [],
    }

    # Fetch wall posts (needed for text analysis and timeline)
    _update('Загрузка постов VK', 72)
    posts = _fetch_vk_wall_posts(vk_profiles, vk_token)

    # --- Pre-compute vk_id (no I/O, just a loop) ---
    vk_id = None
    for p in vk_profiles:
        vk_id = p.get('platform_id') or p.get('vk_id') or p.get('id')
        if not vk_id:
            url = p.get('url', '')
            if '/id' in url:
                try:
                    vk_id = int(url.split('/id')[-1].split('?')[0].split('/')[0])
                except (ValueError, IndexError):
                    pass
        if vk_id:
            break

    # --- Pre-compute telegram username (no I/O) ---
    tg_username = None
    for p in all_profiles:
        if p.get('platform') == 'telegram':
            tg_username = p.get('username') or p.get('screen_name')
            if tg_username:
                break

    # --- Define parallel worker functions ---
    # Each returns a (key, value) tuple for merging into results.

    def _worker_text_analysis():
        """6a. Text analysis from VK wall posts."""
        try:
            if posts:
                return ('text_analysis', _run_text_analysis(posts))
        except Exception as e:
            logger.error(f"Text analysis failed: {e}")
        return ('text_analysis', {})

    def _worker_geo_extraction():
        """6b + 6b2. Geo extraction from profiles + post text."""
        geo_result = {}
        try:
            geo_result = _run_geo_extraction(all_profiles)
        except Exception as e:
            logger.error(f"Geo extraction failed: {e}")

        # 6b2. Supplement with geo from post text
        try:
            if posts:
                from app.services.phase3.geo_extractor import GeoExtractor
                text_geo = GeoExtractor()
                text_locations = text_geo.extract_locations_from_posts(posts)
                if text_locations:
                    existing_locs = geo_result.get('locations', [])
                    for loc in text_locations:
                        loc_dict = loc.to_dict()
                        # Avoid duplicates by city name
                        if not any(el.get('city', '').lower() == loc.city.lower() for el in existing_locs):
                            existing_locs.append(loc_dict)
                    geo_result['locations'] = existing_locs
                    # Update stats
                    geo_result.setdefault('stats', {})['total_locations'] = len(existing_locs)
                    geo_result['stats']['unique_cities'] = len(set(
                        l.get('city', '') for l in existing_locs if l.get('city')
                    ))
                    logger.info(f"Post text geo: found {len(text_locations)} locations from {len(posts)} posts")
        except Exception as e:
            logger.error(f"Post text geo extraction failed: {e}")

        return ('geo_analysis', geo_result)

    def _worker_groups():
        """6d. VK Groups Intelligence."""
        if not vk_id:
            return ('group_analysis', {})
        try:
            groups = fetch_vk_groups(int(vk_id), vk_token)
            if groups:
                group_result = analyze_groups(groups)
                flagged_count = len(group_result.get('flagged_groups', []))
                logger.info(f"VK groups: {len(groups)} total, {flagged_count} flagged")
                return ('group_analysis', group_result)
        except Exception as e:
            logger.error(f"VK groups analysis failed: {e}")
        return ('group_analysis', {})

    def _worker_anomaly_detection():
        """6e. Profile anomaly detection."""
        if not vk_id:
            return ('profile_anomalies', [])
        try:
            # Fetch full VK profile for anomaly check
            resp = requests.get('https://api.vk.com/method/users.get', params={
                'user_ids': vk_id,
                'fields': 'first_name,last_name,is_closed,photo_200,photo_100,city,last_seen',
                'access_token': vk_token,
                'v': VK_API_VERSION,
            }, timeout=10)
            vk_data = resp.json()
            vk_users = vk_data.get('response', [])
            if vk_users:
                vk_profile = vk_users[0]
                anomalies = detect_profile_anomalies(
                    vk_profile, check.full_name,
                )
                store_vk_snapshot(check, vk_profile)
                return ('profile_anomalies', anomalies)
        except Exception as e:
            logger.error(f"Profile anomaly detection failed: {e}")
        return ('profile_anomalies', [])

    def _worker_last_seen():
        """6f. Last seen analysis."""
        if not (vk_profiles and vk_token):
            return ('last_seen_analysis', {})
        try:
            lsd = analyze_last_seen_patterns(vk_profiles, vk_token)
            if lsd:
                most_recent = lsd.get('most_recent', {})
                if most_recent.get('time_ago'):
                    logger.info(f"VK last seen: {most_recent['time_ago']}, platform: {most_recent.get('platform_name', '?')}")
                return ('last_seen_analysis', lsd)
        except Exception as e:
            logger.error(f"Last seen analysis failed: {e}")
        return ('last_seen_analysis', {})

    def _worker_telegram_public():
        """6i. Telegram public message search."""
        try:
            tg_public = search_telegram_public_messages(
                full_name=check.full_name or '',
                username=tg_username,
            )
            if tg_public and (tg_public.get('messages') or tg_public.get('error')):
                msg_count = len(tg_public.get('messages', []))
                if msg_count:
                    logger.info(f"Telegram public messages: found {msg_count} messages in {len(tg_public.get('groups_mentioned', []))} groups")
                return ('telegram_public_activity', tg_public)
        except Exception as e:
            logger.error(f"Telegram public message search failed: {e}")
        return ('telegram_public_activity', None)

    # --- Run all substeps in parallel ---
    _update('Параллельный анализ: тексты, гео, группы, аномалии, Telegram', 75)

    workers = [
        _worker_text_analysis,
        _worker_geo_extraction,
        _worker_groups,
        _worker_anomaly_detection,
        _worker_last_seen,
        _worker_telegram_public,
    ]

    # Propagate Flask app context to ThreadPoolExecutor workers
    try:
        from flask import current_app
        _app = current_app._get_current_object()
    except (ImportError, RuntimeError):
        _app = None

    def _run_with_ctx(fn):
        if _app:
            with _app.app_context():
                return fn()
        return fn()

    executor = ThreadPoolExecutor(max_workers=6)
    try:
        futures = {executor.submit(_run_with_ctx, fn): fn.__doc__ for fn in workers}
        for future in as_completed(futures):
            label = futures[future]
            try:
                key, value = future.result()
                if value is not None:
                    results[key] = value
            except Exception as e:
                logger.error(f"Parallel worker '{label}' raised: {e}")
    finally:
        executor.shutdown(wait=False, cancel_futures=True)

    # --- Post-parallel sequential steps (depend on last_seen_data) ---
    last_seen_data = results.get('last_seen_analysis', {})

    # 6g. Activity patterns (combines post timestamps + last_seen)
    if posts or last_seen_data:
        _update('Анализ паттернов активности', 82)
        try:
            results['activity_patterns'] = analyze_activity_patterns(posts, last_seen_data)
        except Exception as e:
            logger.error(f"Activity patterns analysis failed: {e}")

    # 6h. Build activity timeline (after last_seen is available)
    try:
        results['activity_timeline'] = _build_activity_timeline(posts, check, last_seen_data)
    except Exception as e:
        logger.error(f"Activity timeline failed: {e}")

    _update('Поведенческий анализ завершён', 82)
    return results
