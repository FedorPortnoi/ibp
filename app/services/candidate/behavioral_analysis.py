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
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

import requests

logger = logging.getLogger(__name__)

VK_API_VERSION = '5.199'


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

def analyze_activity_patterns(wall_posts: list) -> dict:
    """Detect posting patterns — timezone, night activity, frequency."""
    if not wall_posts:
        return {}

    hours = []
    days = []
    dates = []

    for post in wall_posts:
        ts = post.get('date', 0)
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

    return {
        'peak_hours': peak_hours,
        'night_activity_pct': round(night_pct, 1),
        'posts_per_day': round(posts_per_day, 2),
        'estimated_timezone': tz_hint,
        'day_distribution': dict(day_counts),
        'hour_distribution': dict(hour_counts),
        'activity_flags': flags,
    }


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
        'photo_hash': hashlib.md5(photo_url.encode()).hexdigest() if photo_url else '',
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


def _build_activity_timeline(posts: List[Dict], check) -> List[Dict]:
    """Build activity timeline from wall posts and check events."""
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

    # 6a. Text analysis
    _update('Анализ текстов', 75)
    try:
        if posts:
            results['text_analysis'] = _run_text_analysis(posts)
    except Exception as e:
        logger.error(f"Text analysis failed: {e}")

    # 6b. Geo extraction
    _update('Извлечение геоданных', 78)
    try:
        results['geo_analysis'] = _run_geo_extraction(all_profiles)
    except Exception as e:
        logger.error(f"Geo extraction failed: {e}")

    # 6b2. Geo extraction from post text (supplement profile-based geo)
    try:
        if posts:
            from app.services.phase3.geo_extractor import GeoExtractor
            text_geo = GeoExtractor()
            text_locations = text_geo.extract_locations_from_posts(posts)
            if text_locations:
                existing_geo = results.get('geo_analysis', {})
                existing_locs = existing_geo.get('locations', [])
                for loc in text_locations:
                    loc_dict = loc.to_dict()
                    # Avoid duplicates by city name
                    if not any(el.get('city', '').lower() == loc.city.lower() for el in existing_locs):
                        existing_locs.append(loc_dict)
                existing_geo['locations'] = existing_locs
                # Update stats
                existing_geo.setdefault('stats', {})['total_locations'] = len(existing_locs)
                existing_geo['stats']['unique_cities'] = len(set(
                    l.get('city', '') for l in existing_locs if l.get('city')
                ))
                results['geo_analysis'] = existing_geo
                logger.info(f"Post text geo: found {len(text_locations)} locations from {len(posts)} posts")
    except Exception as e:
        logger.error(f"Post text geo extraction failed: {e}")

    # 6c. Activity timeline
    _update('Построение таймлайна', 80)
    try:
        results['activity_timeline'] = _build_activity_timeline(posts, check)
    except Exception as e:
        logger.error(f"Activity timeline failed: {e}")

    # 6d. VK Groups Intelligence
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

    if vk_id:
        _update('Анализ групп VK', 80)
        try:
            groups = fetch_vk_groups(int(vk_id), vk_token)
            if groups:
                results['group_analysis'] = analyze_groups(groups)
                flagged_count = len(results['group_analysis'].get('flagged_groups', []))
                logger.info(f"VK groups: {len(groups)} total, {flagged_count} flagged")
        except Exception as e:
            logger.error(f"VK groups analysis failed: {e}")

        # 6e. Profile anomaly detection
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
                results['profile_anomalies'] = detect_profile_anomalies(
                    vk_profile, check.full_name,
                )
                store_vk_snapshot(check, vk_profile)
        except Exception as e:
            logger.error(f"Profile anomaly detection failed: {e}")

    # 6f. Activity patterns
    if posts:
        _update('Анализ паттернов активности', 81)
        try:
            results['activity_patterns'] = analyze_activity_patterns(posts)
        except Exception as e:
            logger.error(f"Activity patterns analysis failed: {e}")

    _update('Поведенческий анализ завершён', 82)
    return results
