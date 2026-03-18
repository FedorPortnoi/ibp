"""
Social Analysis Orchestrator (Stage 5)
=======================================
Orchestrates facial recognition, social graph building,
username search (Snoop), and Yandex service discovery (YaSeeker).

Returns results for pipeline storage + new accounts for Stage 4 re-enrichment.
"""

import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


def _get_photo_url(profiles: List[Dict]) -> Optional[str]:
    """Extract a usable photo URL from confirmed profiles."""
    for p in profiles:
        url = p.get('photo_url') or p.get('photo_100') or p.get('photo_200')
        if url and not url.endswith('camera_100.png'):
            return url
    return None


def _extract_usernames(profiles: List[Dict]) -> List[str]:
    """Extract unique usernames from profiles."""
    usernames = set()
    for p in profiles:
        username = (p.get('username') or '').strip()
        if username and len(username) >= 3:
            # Skip default VK IDs like "id123456"
            if not (username.startswith('id') and username[2:].isdigit()):
                usernames.add(username)
    return list(usernames)[:5]


def _get_vk_id(profiles: List[Dict]) -> Optional[int]:
    """Get VK user ID from confirmed profiles."""
    for p in profiles:
        if p.get('platform') == 'vk':
            vk_id = p.get('platform_id') or p.get('vk_id') or p.get('id')
            if vk_id:
                try:
                    return int(vk_id)
                except (ValueError, TypeError):
                    pass
            # Fallback: extract numeric ID from URL (e.g., https://vk.com/id380010961)
            url = p.get('url', '')
            if '/id' in url:
                try:
                    return int(url.split('/id')[-1].split('?')[0].split('/')[0])
                except (ValueError, IndexError):
                    pass
    return None


def _run_face_search(photo_url: str) -> List[Dict]:
    """Run facial recognition via Search4Faces."""
    try:
        from app.services.phase2.search4faces_service import search_all_databases
        matches = search_all_databases(image_url=photo_url, max_results_per_db=10)
        return [
            {
                'platform': m.platform,
                'profile_url': m.profile_url,
                'username': m.username,
                'similarity_score': m.similarity_score,
                'name': m.name,
                'thumbnail_url': m.thumbnail_url,
            }
            for m in matches
        ]
    except Exception as e:
        logger.error(f"Face search failed: {e}")
        return []


def _run_snoop_search(usernames: List[str]) -> List[Dict]:
    """Run Snoop username search."""
    try:
        from app.services.snoop_search import SnoopSearchService
        snoop = SnoopSearchService()
        if not snoop.available:
            logger.info("Snoop not available, skipping username search")
            return []

        all_results = []
        for username in usernames[:3]:
            try:
                results = snoop.search_username(username, timeout=120, russian_only=True)
                found = snoop.get_found_profiles(results)
                all_results.extend(found)
            except Exception as e:
                logger.warning(f"Snoop search for '{username}' failed: {e}")
        return all_results
    except Exception as e:
        logger.error(f"Snoop search failed: {e}")
        return []


def _run_maigret_search(usernames: List[str]) -> List[Dict]:
    """Run Maigret username search."""
    try:
        from app.services.maigret_search import MaigretSearchService
        maigret = MaigretSearchService()
        if not maigret.available:
            logger.info("Maigret not available, skipping")
            return []

        all_results = []
        for username in usernames[:3]:
            try:
                results = maigret.search_username(username, timeout=120)
                found = maigret.get_found_profiles(results)
                all_results.extend(found)
            except Exception as e:
                logger.warning(f"Maigret search for '{username}' failed: {e}")
        return all_results
    except Exception as e:
        logger.error(f"Maigret search failed: {e}")
        return []


def _run_sherlock_search(usernames: List[str]) -> List[Dict]:
    """Run Sherlock username search."""
    try:
        from app.services.sherlock_search import SherlockSearchService
        sherlock = SherlockSearchService()
        if not sherlock.available:
            logger.info("Sherlock not available, skipping")
            return []

        all_results = []
        for username in usernames[:3]:
            try:
                results = sherlock.search_username(username, timeout=120)
                found = sherlock.get_found_profiles(results)
                all_results.extend(found)
            except Exception as e:
                logger.warning(f"Sherlock search for '{username}' failed: {e}")
        return all_results
    except Exception as e:
        logger.error(f"Sherlock search failed: {e}")
        return []


def _run_yaseeker(usernames: List[str]) -> List[Dict]:
    """Run YaSeeker Yandex service discovery."""
    try:
        from app.services.phase2.yaseeker_service import YaSeekerService
        service = YaSeekerService()
        all_accounts = []
        for username in usernames[:5]:
            try:
                accounts = service.check_all_services(username)
                for acc in accounts:
                    if acc.found:
                        all_accounts.append({
                            'platform': acc.platform,
                            'platform_display': acc.platform_display,
                            'url': acc.url,
                            'username': acc.username,
                            'source': acc.source,
                        })
            except Exception as e:
                logger.warning(f"YaSeeker check for '{username}' failed: {e}")
        return all_accounts
    except Exception as e:
        logger.error(f"YaSeeker search failed: {e}")
        return []


def _collect_new_accounts(
    face_matches: List[Dict],
    username_accounts: List[Dict],
    existing_contacts: Dict
) -> List[Dict]:
    """Identify accounts not already known from Stage 4."""
    existing_urls = set()
    existing_usernames = set()

    # Collect known URLs/usernames from existing contact discoveries
    for key in ('phones', 'emails'):
        for item in (existing_contacts.get(key) or []):
            profile_name = (item.get('profile_name') or '').lower()
            if profile_name:
                existing_usernames.add(profile_name)

    new_accounts = []

    # From face matches
    for match in face_matches:
        url = match.get('profile_url', '')
        username = match.get('username', '')
        if url and url not in existing_urls:
            existing_urls.add(url)
            new_accounts.append({
                'url': url,
                'username': username,
                'platform': match.get('platform', 'unknown'),
                'source': 'face_search',
            })

    # From Snoop/YaSeeker username accounts
    for account in username_accounts:
        url = account.get('url', '')
        username = account.get('username', '')
        if url and url not in existing_urls:
            existing_urls.add(url)
            new_accounts.append({
                'url': url,
                'username': username,
                'platform': account.get('platform', 'unknown'),
                'source': account.get('source', 'username_search'),
            })

    return new_accounts


def _demo_response() -> Dict[str, Any]:
    """Return realistic fake data for demo mode."""
    return {
        'face_matches': [
            {
                'platform': 'vk',
                'profile_url': 'https://vk.com/id100001',
                'username': 'ivanov.demo1',
                'similarity_score': 0.92,
                'name': 'Иван Иванов',
                'thumbnail_url': None,
            },
            {
                'platform': 'vk',
                'profile_url': 'https://vk.com/id100002',
                'username': 'ivan.ivanov92',
                'similarity_score': 0.87,
                'name': 'Иван Иванов',
                'thumbnail_url': None,
            },
            {
                'platform': 'ok',
                'profile_url': 'https://ok.ru/profile/100003',
                'username': 'ivanov.ok',
                'similarity_score': 0.73,
                'name': 'Иван Иванов',
                'thumbnail_url': None,
            },
        ],
        'social_graph': {
            'nodes': [
                {'id': 'vk_1', 'label': 'Центр', 'level': 0}
            ] + [
                {'id': f'vk_{i}', 'label': f'Друг {i}', 'level': 1}
                for i in range(2, 16)
            ],
            'edges': [
                {'from': 'vk_1', 'to': f'vk_{i}'}
                for i in range(2, 16)
            ] + [
                {'from': 'vk_2', 'to': 'vk_3'},
                {'from': 'vk_3', 'to': 'vk_4'},
                {'from': 'vk_5', 'to': 'vk_6'},
                {'from': 'vk_7', 'to': 'vk_8'},
                {'from': 'vk_9', 'to': 'vk_10'},
            ],
            'stats': {'node_count': 15, 'edge_count': 19},
            'clusters': [],
        },
        'username_accounts': [
            {'platform': 'github', 'url': 'https://github.com/ivanovdemo', 'username': 'ivanovdemo', 'source': 'snoop'},
            {'platform': 'instagram', 'url': 'https://instagram.com/ivanovdemo', 'username': 'ivanovdemo', 'source': 'snoop'},
            {'platform': 'twitter', 'url': 'https://twitter.com/ivanovdemo', 'username': 'ivanovdemo', 'source': 'snoop'},
            {'platform': 'ok.ru', 'url': 'https://ok.ru/ivanovdemo', 'username': 'ivanovdemo', 'source': 'snoop'},
            {'platform': 'habr', 'url': 'https://habr.com/users/ivanovdemo', 'username': 'ivanovdemo', 'source': 'snoop'},
        ],
        'new_accounts_for_enrichment': [
            {'url': 'https://github.com/ivanovdemo', 'username': 'ivanovdemo', 'platform': 'github', 'source': 'snoop'},
            {'url': 'https://instagram.com/ivanovdemo', 'username': 'ivanovdemo', 'platform': 'instagram', 'source': 'snoop'},
        ],
    }


def run_social_analysis(check, task_status_callback=None) -> Dict[str, Any]:
    """
    Stage 5: Deep Social Analysis.

    Orchestrates face search, social graph, Snoop, and YaSeeker.

    Args:
        check: CandidateCheck model instance
        task_status_callback: Optional callable(stage, message, percent) for progress

    Returns:
        {
            'face_matches': [...],
            'social_graph': {...},
            'username_accounts': [...],
            'new_accounts_for_enrichment': [...]
        }
    """
    def _update(msg, pct=None):
        if task_status_callback:
            try:
                task_status_callback('social_analysis', msg, pct)
            except Exception as e:
                logger.debug(f"[SocialAnalysis] Status callback failed: {e}")

    # Get profiles to work with
    confirmed = check.confirmed_profiles or check.social_media_profiles or []
    if not confirmed:
        logger.info("No profiles found for social analysis")
        # Check if we should use demo mode
        from app.utils.vk_token_manager import get_vk_token
        vk_token = get_vk_token('search')
        if not vk_token:
            _update('Демо-режим: нет VK токена', 70)
            return _demo_response()
        return {
            'face_matches': [],
            'social_graph': {},
            'username_accounts': [],
            'new_accounts_for_enrichment': [],
        }

    photo_url = _get_photo_url(confirmed)
    usernames = _extract_usernames(confirmed)
    vk_id = _get_vk_id(confirmed)

    results = {
        'face_matches': [],
        'social_graph': {},
        'username_accounts': [],
        'new_accounts_for_enrichment': [],
    }

    # Run face search, snoop, maigret, sherlock, and yaseeker in parallel
    _update('Поиск по лицу + имени пользователя', 56)

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {}

        # 5a. Face search (if photo available)
        if photo_url:
            futures['face'] = executor.submit(_run_face_search, photo_url)

        # 5c. Snoop username search
        if usernames:
            futures['snoop'] = executor.submit(_run_snoop_search, usernames)

        # 5c2. Maigret username search
        if usernames:
            futures['maigret'] = executor.submit(_run_maigret_search, usernames)

        # 5c3. Sherlock username search
        if usernames:
            futures['sherlock'] = executor.submit(_run_sherlock_search, usernames)

        # 5d. YaSeeker
        if usernames:
            futures['yaseeker'] = executor.submit(_run_yaseeker, usernames)

        for key, future in futures.items():
            try:
                result = future.result(timeout=180)
                if key == 'face':
                    results['face_matches'] = result
                elif key in ('snoop', 'maigret', 'sherlock', 'yaseeker'):
                    results['username_accounts'].extend(result)
            except Exception as e:
                logger.error(f"Social analysis sub-task '{key}' failed: {e}")

        # Deduplicate username_accounts by URL
        seen_urls = set()
        deduped = []
        for acct in results['username_accounts']:
            url = acct.get('url', '')
            if url and url not in seen_urls:
                seen_urls.add(url)
                deduped.append(acct)
        results['username_accounts'] = deduped

    # 5b. Social graph (needs VK data, runs after parallel tasks)
    if vk_id:
        _update('Построение социального графа', 64)
        try:
            from app.services.phase2.social_graph import SocialGraphBuilder
            from app.utils.vk_token_manager import get_vk_token
            # friends.get requires user token (private data)
            user_token = get_vk_token('private')
            builder = SocialGraphBuilder(service_token=user_token)

            if builder.is_demo_mode:
                name = check.full_name or 'Неизвестный'
                graph = builder.get_demo_graph(name)
            else:
                # Get center profile data
                center_profile = next(
                    (p for p in confirmed if p.get('platform') == 'vk'), {}
                )
                center_data = {
                    'first_name': center_profile.get('first_name', ''),
                    'last_name': center_profile.get('last_name', ''),
                    'photo_100': center_profile.get('photo_url', ''),
                    'city': {'title': center_profile.get('city', '')} if center_profile.get('city') else None,
                }

                # Fetch friends via VK API (user token required for friends.get)
                friends = _fetch_vk_friends(vk_id, user_token or builder.token)
                graph = builder.build_from_friends(vk_id, center_data, friends)

            results['social_graph'] = builder.export_visjs(graph)

        except Exception as e:
            logger.error(f"Social graph building failed: {e}")

    # 5e. Collect new accounts for enrichment
    existing_contacts = check.contact_discoveries or {}
    results['new_accounts_for_enrichment'] = _collect_new_accounts(
        results['face_matches'],
        results['username_accounts'],
        existing_contacts,
    )

    _update('Социальный анализ завершён', 70)
    return results


def _fetch_vk_friends(vk_id: int, token: str) -> List[Dict]:
    """Fetch VK friends list via API."""
    if not token:
        return []
    try:
        import requests
        resp = requests.get(
            'https://api.vk.com/method/friends.get',
            params={
                'user_id': vk_id,
                'fields': 'first_name,last_name,photo_100,city',
                'access_token': token,
                'v': '5.199',
            },
            timeout=15,
        )
        data = resp.json()
        if 'response' in data:
            return data['response'].get('items', [])
    except Exception as e:
        logger.warning(f"VK friends fetch failed: {e}")
    return []
