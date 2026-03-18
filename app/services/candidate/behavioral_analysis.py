"""
Behavioral Analysis Orchestrator (Stage 6)
==========================================
Orchestrates text analysis, geo extraction, and activity timeline
construction from VK wall posts and profile data.
"""

import logging
import os
import random
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

import requests

logger = logging.getLogger(__name__)

VK_API_VERSION = '5.199'


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

    # 6c. Activity timeline
    _update('Построение таймлайна', 80)
    try:
        results['activity_timeline'] = _build_activity_timeline(posts, check)
    except Exception as e:
        logger.error(f"Activity timeline failed: {e}")

    _update('Поведенческий анализ завершён', 82)
    return results
