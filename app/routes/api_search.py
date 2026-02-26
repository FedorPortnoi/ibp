"""
Phase 1 Search API — Parallel Multi-Platform Discovery
=======================================================
Two independent endpoints for parallel AJAX calls:
  POST /api/search/vk       → VK People Search
  POST /api/search/telegram  → Telegram Discovery (3 methods)

Each endpoint accepts JSON body with name, city, age_from, age_to
and returns a unified profile response format.
"""

import logging
import re
import time
from datetime import datetime
from flask import Blueprint, request, jsonify, render_template

from app import limiter

logger = logging.getLogger(__name__)

api_search_bp = Blueprint('api_search', __name__, url_prefix='/api/search')


@api_search_bp.route('/page')
def search_page():
    """Render the two-column people search page."""
    return render_template('people_search.html')


@api_search_bp.route('/vk', methods=['POST'])
@limiter.limit("30 per minute")
def search_vk():
    """
    VK People Search — uses existing BuratinoVKSearch pipeline.
    Returns VK profiles as JSON.
    """
    start = time.time()

    try:
        data = request.get_json(silent=True) or {}
        name = (data.get('name') or '').strip()
        if not name:
            return jsonify({'status': 'error', 'count': 0, 'profiles': [], 'errors': ['Имя обязательно']})

        city = (data.get('city') or '').strip() or None
        age_from = data.get('age_from')
        age_to = data.get('age_to')

        # Parse name into parts
        name_parts = name.split()
        first_name = name_parts[0] if name_parts else name
        last_name = name_parts[1] if len(name_parts) > 1 else ''

        from app.services.phase1.buratino_vk_search import buratino_vk_search
        profiles, total = buratino_vk_search.search(
            query=name,
            city=city,
            age_from=int(age_from) if age_from else None,
            age_to=int(age_to) if age_to else None,
            target_name=name,
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


@api_search_bp.route('/telegram', methods=['POST'])
@limiter.limit("30 per minute")
def search_telegram():
    """
    Telegram Discovery — three methods:
      A) VK cross-reference (check t.me/{vk_screen_name})
      B) Username guessing (generate candidates, check t.me/{candidate})
      C) Telethon directory search (search Telegram by name)

    Accepts vk_screen_names from the frontend (extracted after VK search completes).
    """
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

        from app.services.phase1.telegram_discovery import TelegramDiscoveryService
        svc = TelegramDiscoveryService()

        try:
            profiles = svc.discover(
                first_name=first_name,
                last_name=last_name,
                vk_screen_names=vk_screen_names,
                city=city,
                age_from=int(age_from) if age_from else None,
                age_to=int(age_to) if age_to else None,
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


@api_search_bp.route('/save-selection', methods=['POST'])
def save_selection():
    """
    Save a selected profile from the three-column search to the investigation.
    Creates a SocialProfile record, confirms it, and updates investigation status.
    """
    try:
        from app import db
        from app.models import Investigation, SocialProfile

        data = request.get_json(silent=True) or {}
        investigation_id = data.get('investigation_id')
        profile_data = data.get('profile', {})

        if not investigation_id or not profile_data:
            return jsonify({'success': False, 'error': 'Недостаточно данных'})

        investigation = Investigation.query.get(investigation_id)
        if not investigation:
            return jsonify({'success': False, 'error': 'Расследование не найдено'})

        platform = profile_data.get('platform', 'vk')
        platform_id = profile_data.get('id', '')
        username = profile_data.get('username', '')
        url = profile_data.get('url', '')

        # Sanitize inputs
        first_name = re.sub(r'<[^>]+>', '', (profile_data.get('first_name') or '')[:255])
        last_name = re.sub(r'<[^>]+>', '', (profile_data.get('last_name') or '')[:255])

        # Create SocialProfile record
        social_profile = SocialProfile(
            investigation_id=investigation_id,
            platform=platform,
            platform_id=str(platform_id) if platform_id else username,
            username=username,
            profile_url=url,
            first_name=first_name,
            last_name=last_name,
            display_name=f"{first_name} {last_name}".strip(),
            photo_url=profile_data.get('photo_url'),
            city=profile_data.get('city'),
            age=profile_data.get('age'),
            bio=profile_data.get('bio', '')[:1000] if profile_data.get('bio') else None,
            name_match=True,
            name_similarity=100.0,
        )
        social_profile.calculate_confidence()

        db.session.add(social_profile)
        db.session.flush()  # Get the ID

        # Confirm the profile
        social_profile.confirm()

        # Update investigation with confirmed profile data
        investigation.confirmed_profile = social_profile.to_dict()
        investigation.confirmed_username = username
        investigation.confirmed_platform = platform
        investigation.confirmed_profile_url = url
        investigation.status = 'phase_1_complete'
        investigation.profile_confirmed_at = datetime.now()

        # Store platform-specific ID in phase1_stats
        stats = investigation.phase1_stats or {}
        if platform == 'vk' and platform_id:
            stats['confirmed_vk_id'] = platform_id
        stats['confirmed_from'] = 'three_column_search'
        stats['confirmed_platform'] = platform
        investigation.phase1_stats = stats

        db.session.commit()

        logger.info(f"Saved selection: {platform} @{username} for investigation {investigation_id}")

        return jsonify({
            'success': True,
            'profile_id': social_profile.id,
            'redirect': f'/phase2/analyze/{investigation_id}',
        })

    except Exception as e:
        logger.error(f"Save selection error: {e}", exc_info=True)
        return jsonify({'success': False, 'error': 'Внутренняя ошибка сервера'})
