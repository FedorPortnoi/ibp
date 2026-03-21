import logging
import os
import time
from flask import Blueprint, render_template, request, jsonify
from .auth import login_required

logger = logging.getLogger(__name__)

search_bp = Blueprint('search', __name__)


@search_bp.route('/')
@login_required
def index():
    return render_template('search.html')


@search_bp.route('/health')
def health():
    return jsonify({'status': 'ok', 'app': 'people_search'})


@search_bp.route('/search/vk', methods=['POST'])
@login_required
def search_vk():
    """VK People Search -- returns all matching profiles."""
    start = time.time()
    try:
        data = request.get_json(silent=True) or {}
        name = (data.get('name') or '').strip()
        if not name:
            return jsonify({'status': 'error', 'count': 0, 'profiles': [], 'errors': ['Имя обязательно']})

        city = (data.get('city') or '').strip() or None
        age_from = data.get('age_from')
        age_to = data.get('age_to')

        from ..services.vk_search import BuratinoVKSearch
        searcher = BuratinoVKSearch()
        profiles, total = searcher.search(
            query=name,
            city=city,
            age_from=int(age_from) if age_from else None,
            age_to=int(age_to) if age_to else None,
            target_name=name,
            strict_mode=False,
        )

        results = []
        for p in profiles:
            results.append({
                'platform': 'vk',
                'id': str(p.vk_id),
                'url': p.profile_url,
                'first_name': p.first_name,
                'last_name': p.last_name,
                'photo_url': p.photo_url,
                'city': p.city or '',
                'age': p.age,
                'username': p.screen_name or '',
                'bio': '',
                'confidence': 'high' if p.name_similarity > 70 else 'medium' if p.name_similarity > 50 else 'low',
                'source': 'VK API',
            })

        elapsed = round(time.time() - start, 1)
        logger.info(f"VK search: {len(results)} results in {elapsed}s for '{name}'")

        return jsonify({
            'status': 'ok',
            'count': len(results),
            'profiles': results,
            'errors': [],
            'search_time': elapsed,
        })

    except Exception as e:
        logger.error(f"VK search API error: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'count': 0,
            'profiles': [],
            'errors': ['Ошибка поиска VK'],
        })


@search_bp.route('/search/telegram', methods=['POST'])
@login_required
def search_telegram():
    """Telegram Discovery -- returns all found profiles."""
    start = time.time()
    try:
        data = request.get_json(silent=True) or {}
        name = (data.get('name') or '').strip()
        if not name:
            return jsonify({'status': 'error', 'count': 0, 'profiles': [], 'errors': ['Имя обязательно']})

        city = (data.get('city') or '').strip()
        age_from = data.get('age_from')
        age_to = data.get('age_to')
        vk_screen_names = data.get('vk_screen_names', [])

        name_parts = name.split()
        first_name = name_parts[0] if name_parts else name
        last_name = name_parts[1] if len(name_parts) > 1 else ''

        from ..services.telegram_search import TelegramDiscoveryService
        svc = TelegramDiscoveryService()

        try:
            profiles = svc.discover(
                first_name=first_name,
                last_name=last_name,
                vk_screen_names=vk_screen_names,
                city=city,
                age_from=int(age_from) if age_from else None,
                age_to=int(age_to) if age_to else None,
                strict_mode=False,
            )
        finally:
            svc.close()

        elapsed = round(time.time() - start, 1)
        logger.info(f"Telegram search: {len(profiles)} results in {elapsed}s for '{name}'")

        return jsonify({
            'status': 'ok',
            'count': len(profiles),
            'profiles': profiles,
            'errors': [],
            'search_time': elapsed,
        })

    except Exception as e:
        logger.error(f"Telegram search API error: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'count': 0,
            'profiles': [],
            'errors': ['Ошибка поиска Telegram'],
        })


@search_bp.route('/vk-preview/<int:vk_id>')
@login_required
def vk_preview(vk_id):
    """Quick preview data for VK profile hover tooltip."""
    import requests as http_requests

    token = os.environ.get('VK_USER_TOKEN') or os.environ.get('VK_TOKEN') or os.environ.get('VK_SERVICE_TOKEN')
    if not token:
        return jsonify({'error': 'No VK token configured'})

    try:
        profile_r = http_requests.get('https://api.vk.com/method/users.get', params={
            'user_ids': vk_id,
            'fields': 'photo_400_orig,last_seen,counters,status,city',
            'access_token': token,
            'v': '5.199'
        }, timeout=10)

        wall_r = http_requests.get('https://api.vk.com/method/wall.get', params={
            'owner_id': vk_id,
            'count': 3,
            'filter': 'owner',
            'access_token': token,
            'v': '5.199'
        }, timeout=10)

        profile_data = profile_r.json().get('response', [{}])
        profile = profile_data[0] if profile_data else {}
        posts = wall_r.json().get('response', {}).get('items', [])

        return jsonify({
            'photo': profile.get('photo_400_orig', ''),
            'last_seen': profile.get('last_seen', {}).get('time'),
            'friends': profile.get('counters', {}).get('friends', 0),
            'groups': profile.get('counters', {}).get('groups', 0),
            'status': profile.get('status', ''),
            'posts': [
                {'text': p.get('text', '')[:150], 'date': p.get('date')}
                for p in posts if p.get('text')
            ]
        })
    except Exception as e:
        logger.warning(f"VK preview error for id{vk_id}: {e}")
        return jsonify({'error': str(e)})
