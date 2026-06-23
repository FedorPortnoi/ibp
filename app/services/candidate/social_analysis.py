"""
Social Analysis Orchestrator (Stage 5)
=======================================
Orchestrates facial recognition, social graph building,
username search (Snoop), and Yandex service discovery (YaSeeker).

Returns results for pipeline storage + new accounts for Stage 4 re-enrichment.
"""

import difflib
import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

import requests

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


def _run_face_search(photo_url: str = None, photo_path: str = None):
    """Run facial recognition via Search4Faces.

    Supports both image URL (from VK profile) and local file path (from upload).
    Returns (matches, status). Status distinguishes "searched, no match" from
    "could not search" (no API key + Playwright unavailable, or no detectable
    face) so the dossier never shows a false "no photos found online".
    """
    try:
        from app.services.phase2.search4faces_service import search_all_databases_with_status
        matches, status = search_all_databases_with_status(
            image_url=photo_url,
            image_path=photo_path,
            max_results_per_db=10,
        )
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
        ], status
    except Exception as e:
        logger.error(f"Face search failed: {e}")
        return [], 'error'


# Status semantics for the username-search tools (Snoop/Maigret/Sherlock).
# 'unavailable' (tool not installed) and 'error' must NEVER render as "no
# accounts found" — that is a false clean. Only 'empty' means we actually
# searched and the candidate's username turned up nothing.
def _combine_username_status(statuses: Dict[str, str]) -> str:
    """Combine the per-tool statuses of the username-search trio into one
    honest source status.

    Precedence: any tool found accounts -> 'ok'; else any tool actually
    searched and was clean -> 'empty'; else any tool errored -> 'error';
    else every tool was missing -> 'unavailable'. Empty input -> '' (the
    trio never ran, e.g. no usernames to search). 'unavailable'/'error'
    must not be rendered as "no accounts found".
    """
    if not statuses:
        return ''
    vals = set(statuses.values())
    if 'ok' in vals:
        return 'ok'
    if 'empty' in vals:
        return 'empty'
    if 'error' in vals:
        return 'error'
    return 'unavailable'


def _run_snoop_search(usernames: List[str]) -> Tuple[List[Dict], str]:
    """Run Snoop username search. Returns (accounts, status)."""
    try:
        from app.services.snoop_search import SnoopSearchService
        snoop = SnoopSearchService()
        if not snoop.available:
            logger.info("Snoop not available, skipping username search")
            return [], 'unavailable'

        all_results = []
        for username in usernames[:3]:
            try:
                results = snoop.search_username(username, timeout=120, russian_only=True)
                found = snoop.get_found_profiles(results)
                all_results.extend(found)
            except Exception as e:
                logger.warning(f"Snoop search for '{username}' failed: {e}")
        return all_results, ('ok' if all_results else 'empty')
    except Exception as e:
        logger.error(f"Snoop search failed: {e}")
        return [], 'error'


def _run_maigret_search(usernames: List[str]) -> Tuple[List[Dict], str]:
    """Run Maigret username search. Returns (accounts, status)."""
    try:
        from app.services.maigret_search import MaigretSearchService
        maigret = MaigretSearchService()
        if not maigret.available:
            logger.info("Maigret not available, skipping")
            return [], 'unavailable'

        all_results = []
        for username in usernames[:3]:
            try:
                results = maigret.search_username(username, timeout=120)
                found = maigret.get_found_profiles(results)
                all_results.extend(found)
            except Exception as e:
                logger.warning(f"Maigret search for '{username}' failed: {e}")
        return all_results, ('ok' if all_results else 'empty')
    except Exception as e:
        logger.error(f"Maigret search failed: {e}")
        return [], 'error'


def _run_sherlock_search(usernames: List[str]) -> Tuple[List[Dict], str]:
    """Run Sherlock username search. Returns (accounts, status)."""
    try:
        from app.services.sherlock_search import SherlockSearchService
        sherlock = SherlockSearchService()
        if not sherlock.available:
            logger.info("Sherlock not available, skipping")
            return [], 'unavailable'

        all_results = []
        for username in usernames[:3]:
            try:
                results = sherlock.search_username(username, timeout=120)
                found = sherlock.get_found_profiles(results)
                all_results.extend(found)
            except Exception as e:
                logger.warning(f"Sherlock search for '{username}' failed: {e}")
        return all_results, ('ok' if all_results else 'empty')
    except Exception as e:
        logger.error(f"Sherlock search failed: {e}")
        return [], 'error'


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


def analyze_friends_risk_deep(vk_id: int, vk_token: str) -> dict:
    """
    Fetch VK friends and check each against local MVD/extremist databases.

    Uses difflib.SequenceMatcher with 0.90 threshold for fuzzy name matching
    against data/mvd_wanted.json and data/extremist_list.json.

    Args:
        vk_id: VK user numeric ID.
        vk_token: VK API access token (service or user).

    Returns:
        {
            'total_friends': int,
            'checked_friends': int,
            'flagged_count': int,
            'flagged_friends': [top 20 matches],
            'risk_level': 'high' | 'medium' | 'low'
        }
    """
    SIMILARITY_THRESHOLD = 0.90
    MAX_FRIENDS = 500
    MAX_FLAGGED = 20

    empty_result = {
        'total_friends': 0,
        'checked_friends': 0,
        'flagged_count': 0,
        'flagged_friends': [],
        'risk_level': 'low',
    }

    if not vk_id or not vk_token:
        logger.info("[FriendsRiskDeep] No vk_id or token, skipping")
        return empty_result

    # ── Step 1: Fetch friends via VK API ──
    try:
        resp = requests.get(
            'https://api.vk.com/method/friends.get',
            params={
                'user_id': vk_id,
                'fields': 'first_name,last_name,deactivated,city',
                'count': MAX_FRIENDS,
                'access_token': vk_token,
                'v': '5.199',
            },
            timeout=15,
        )
        data = resp.json()
        if 'error' in data:
            error_msg = data['error'].get('error_msg', 'unknown')
            logger.warning(f"[FriendsRiskDeep] VK API error: {error_msg}")
            return empty_result
        items = data.get('response', {}).get('items', [])
    except requests.exceptions.Timeout:
        logger.warning("[FriendsRiskDeep] VK API timeout (15s)")
        return empty_result
    except Exception as e:
        logger.error(f"[FriendsRiskDeep] VK friends fetch failed: {e}")
        return empty_result

    # Filter out deactivated accounts
    active_friends = [u for u in items if not _is_deleted_account(u)]
    total_friends = len(items)
    checked_friends = len(active_friends)

    if not active_friends:
        logger.info("[FriendsRiskDeep] No active friends to check")
        result = empty_result.copy()
        result['total_friends'] = total_friends
        return result

    # ── Step 2: Load security databases ──
    data_dir = Path(__file__).parent.parent.parent.parent / 'data'

    mvd_entries = []
    mvd_path = data_dir / 'mvd_wanted.json'
    if mvd_path.exists():
        try:
            with open(mvd_path, 'r', encoding='utf-8') as f:
                mvd_entries = json.load(f)
            logger.info(f"[FriendsRiskDeep] Loaded {len(mvd_entries)} MVD records")
        except Exception as e:
            logger.error(f"[FriendsRiskDeep] Failed to load MVD data: {e}")

    extremist_entries = []
    extremist_path = data_dir / 'extremist_list.json'
    if extremist_path.exists():
        try:
            with open(extremist_path, 'r', encoding='utf-8') as f:
                extremist_entries = json.load(f)
            logger.info(f"[FriendsRiskDeep] Loaded {len(extremist_entries)} extremist records")
        except Exception as e:
            logger.error(f"[FriendsRiskDeep] Failed to load extremist data: {e}")

    if not mvd_entries and not extremist_entries:
        logger.info("[FriendsRiskDeep] No security DB data available, skipping")
        result = empty_result.copy()
        result['total_friends'] = total_friends
        result['checked_friends'] = checked_friends
        return result

    # Pre-normalize all DB names for faster comparison
    def _normalize(name: str) -> str:
        return ' '.join(name.strip().lower().split())

    mvd_names = []
    for entry in mvd_entries:
        raw_name = entry.get('full_name', '') or entry.get('name', '')
        if raw_name:
            mvd_names.append((_normalize(raw_name), raw_name))

    extremist_names = []
    for entry in extremist_entries:
        raw_name = entry.get('full_name', '') or entry.get('name', '')
        if raw_name:
            extremist_names.append((_normalize(raw_name), raw_name))

    # ── Step 3: Check each friend against both databases ──
    flagged_friends = []

    for friend in active_friends:
        first = (friend.get('first_name') or '').strip()
        last = (friend.get('last_name') or '').strip()
        if not first or not last:
            continue

        friend_name_norm = _normalize(f"{last} {first}")
        friend_vk_id = friend.get('id', 0)
        city_obj = friend.get('city')
        city = city_obj.get('title', '') if isinstance(city_obj, dict) else ''

        hits = []

        # Check MVD wanted list
        for norm_name, raw_name in mvd_names:
            sim = difflib.SequenceMatcher(None, friend_name_norm, norm_name).ratio()
            if sim >= SIMILARITY_THRESHOLD:
                hits.append({
                    'source': 'mvd_wanted',
                    'matched_name': raw_name,
                    'similarity': round(sim, 3),
                })

        # Check extremist list
        for norm_name, raw_name in extremist_names:
            sim = difflib.SequenceMatcher(None, friend_name_norm, norm_name).ratio()
            if sim >= SIMILARITY_THRESHOLD:
                hits.append({
                    'source': 'extremist_list',
                    'matched_name': raw_name,
                    'similarity': round(sim, 3),
                })

        if hits:
            flagged_friends.append({
                'name': f"{last} {first}",
                'vk_id': friend_vk_id,
                'url': f"https://vk.com/id{friend_vk_id}",
                'city': city,
                'hits': hits,
            })

    flagged_count = len(flagged_friends)

    # Sort by highest similarity (best match first), take top 20
    flagged_friends.sort(
        key=lambda f: max(h['similarity'] for h in f['hits']),
        reverse=True,
    )
    flagged_friends = flagged_friends[:MAX_FLAGGED]

    if flagged_count > 0:
        risk_level = 'high' if flagged_count >= 3 else 'medium'
    else:
        risk_level = 'low'

    logger.info(
        f"[FriendsRiskDeep] Checked {checked_friends}/{total_friends} friends, "
        f"flagged {flagged_count}, risk_level={risk_level}"
    )

    return {
        'total_friends': total_friends,
        'checked_friends': checked_friends,
        'flagged_count': flagged_count,
        'flagged_friends': flagged_friends,
        'risk_level': risk_level,
    }


def run_social_analysis(check, task_status_callback=None) -> Dict[str, Any]:
    """
    Stage 5: Deep Social Analysis.

    Orchestrates face search, social graph, Snoop, YaSeeker, and
    deep friends risk analysis (MVD/extremist DB cross-check).

    Args:
        check: CandidateCheck model instance
        task_status_callback: Optional callable(stage, message, percent) for progress

    Returns:
        {
            'face_matches': [...],
            'social_graph': {...},
            'username_accounts': [...],
            'new_accounts_for_enrichment': [...],
            'friends_risk_deep': {...}
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

    # Check for uploaded photo (local file from form)
    uploaded_photo = getattr(check, 'photo_path', None)
    if uploaded_photo and not os.path.exists(uploaded_photo):
        logger.warning(f"Uploaded photo not found at {uploaded_photo}")
        uploaded_photo = None

    results = {
        'face_matches': [],
        'face_search_status': '',
        'social_graph': {},
        'username_accounts': [],
        'new_accounts_for_enrichment': [],
        'friends_risk_deep': {},
    }

    # Run face search, snoop, maigret, sherlock, and yaseeker in parallel
    _update('Поиск по лицу + имени пользователя', 56)

    # Propagate Flask app context to ThreadPoolExecutor workers
    try:
        from flask import current_app
        _app = current_app._get_current_object()
    except (ImportError, RuntimeError):
        _app = None

    def _submit_with_ctx(executor, fn, *args, **kwargs):
        def _wrapper():
            if _app:
                with _app.app_context():
                    return fn(*args, **kwargs)
            return fn(*args, **kwargs)
        return executor.submit(_wrapper)

    executor = ThreadPoolExecutor(max_workers=5)
    try:
        futures = {}

        # 5a. Face search (uploaded photo takes priority over profile photo)
        if uploaded_photo:
            logger.info(f"[SocialAnalysis] face search: using uploaded photo {uploaded_photo}")
            futures['face'] = _submit_with_ctx(executor, _run_face_search, photo_path=uploaded_photo)
        elif photo_url:
            futures['face'] = _submit_with_ctx(executor, _run_face_search, photo_url=photo_url)

        # 5c. Snoop username search
        if usernames:
            futures['snoop'] = _submit_with_ctx(executor, _run_snoop_search, usernames)

        # 5c2. Maigret username search
        if usernames:
            futures['maigret'] = _submit_with_ctx(executor, _run_maigret_search, usernames)

        # 5c3. Sherlock username search
        if usernames:
            futures['sherlock'] = _submit_with_ctx(executor, _run_sherlock_search, usernames)

        # 5d. YaSeeker
        if usernames:
            futures['yaseeker'] = _submit_with_ctx(executor, _run_yaseeker, usernames)

        # Per-tool status for the username-search trio (Snoop/Maigret/Sherlock),
        # combined into one honest source status below.
        username_tool_statuses: Dict[str, str] = {}
        for key, future in futures.items():
            try:
                result = future.result(timeout=180)
                if key == 'face':
                    # _run_face_search returns (matches, status)
                    if isinstance(result, tuple):
                        face_list, face_status = result
                    else:  # defensive: older return shape
                        face_list, face_status = result, 'ok'
                    results['face_matches'] = face_list
                    results['face_search_status'] = face_status
                    if face_list:
                        logger.info(f"[SocialAnalysis] face: found {len(face_list)} matches")
                    elif face_status in ('ok', 'empty'):
                        logger.info("[SocialAnalysis] face: 0 matches (searched)")
                    else:
                        logger.info(f"[SocialAnalysis] face: not searched (status={face_status})")
                elif key in ('snoop', 'maigret', 'sherlock'):
                    # These now return (accounts, status); be defensive about
                    # the older bare-list shape.
                    if isinstance(result, tuple):
                        accts, u_status = result
                    else:
                        accts, u_status = result, ('ok' if result else 'empty')
                    results['username_accounts'].extend(accts)
                    username_tool_statuses[key] = u_status
                    if accts:
                        logger.info(f"[SocialAnalysis] {key}: found {len(accts)} accounts")
                    else:
                        logger.info(f"[SocialAnalysis] {key}: 0 results (status={u_status})")
                elif key == 'yaseeker':
                    results['username_accounts'].extend(result)
                    if result:
                        logger.info(f"[SocialAnalysis] {key}: found {len(result)} accounts")
                    else:
                        logger.info(f"[SocialAnalysis] {key}: 0 results (tool may be unavailable)")
            except Exception as e:
                logger.error(f"Social analysis sub-task '{key}' failed: {e}")
                if key in ('snoop', 'maigret', 'sherlock'):
                    username_tool_statuses[key] = 'error'

        # Combine the trio into one honest username-search status.
        _combined = _combine_username_status(username_tool_statuses)
        if _combined:
            results['username_search_status'] = _combined

        # Deduplicate username_accounts by URL
        seen_urls = set()
        deduped = []
        for acct in results['username_accounts']:
            url = acct.get('url', '')
            if url and url not in seen_urls:
                seen_urls.add(url)
                deduped.append(acct)
        results['username_accounts'] = deduped
    finally:
        # Use wait=False so a hung Playwright task in _run_face_search cannot
        # prevent run_social_analysis from returning (the pipeline outer timeout
        # on stage5_future.result(timeout=90) would otherwise fire first anyway,
        # but this ensures the Stage 5 thread itself exits cleanly).
        executor.shutdown(wait=False, cancel_futures=True)

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
                # Build center node data; fall back to check.full_name
                # to avoid empty label when VK profile lacks first/last name.
                c_first = center_profile.get('first_name', '')
                c_last = center_profile.get('last_name', '')
                if not c_first and not c_last and check.full_name:
                    parts = check.full_name.strip().split()
                    # Russian order: Фамилия Имя Отчество
                    c_last = parts[0] if parts else ''
                    c_first = parts[1] if len(parts) > 1 else ''
                center_data = {
                    'first_name': c_first,
                    'last_name': c_last,
                    'photo_100': center_profile.get('photo_url', ''),
                    'city': {'title': center_profile.get('city', '')} if center_profile.get('city') else None,
                }

                # Fetch friends via VK API (user token required for friends.get)
                friends = _fetch_vk_friends(vk_id, user_token or builder.token)
                graph = builder.build_from_friends(vk_id, center_data, friends)

            results['social_graph'] = builder.export_visjs(graph)

        except Exception as e:
            logger.error(f"Social graph building failed: {e}")

    # 5b2. Deep friends risk analysis (MVD/extremist cross-check)
    if vk_id:
        _update('Проверка друзей по базам МВД/розыска', 67)
        try:
            from app.utils.vk_token_manager import get_vk_token as _get_token
            risk_token = _get_token('private') or _get_token('search')
            friends_risk = analyze_friends_risk_deep(vk_id, risk_token)
            results['friends_risk_deep'] = friends_risk

            # Embed into social_graph dict so it gets persisted via
            # check.social_graph_data in the pipeline (pipeline.py saves
            # social_results['social_graph'] -> check.social_graph_data)
            if results['social_graph']:
                results['social_graph']['friends_risk_deep'] = friends_risk
            else:
                results['social_graph'] = {'friends_risk_deep': friends_risk}

            flagged_n = friends_risk.get('flagged_count', 0)
            if flagged_n > 0:
                logger.warning(
                    f"[SocialAnalysis] friends risk: {flagged_n} flagged in "
                    f"MVD/extremist databases"
                )
                # Add risk flag for downstream risk scorer consumption
                if 'risk_flags' not in results:
                    results['risk_flags'] = []
                results['risk_flags'].append({
                    'type': 'fact',
                    'code': 'risky_friends',
                    'description': (
                        f'Среди друзей ВКонтакте {flagged_n} человек '
                        f'числится в базах МВД/розыска'
                    ),
                    'severity': 'high' if flagged_n >= 3 else 'medium',
                    'recommendation': (
                        'Проверить связи кандидата с указанными лицами'
                    ),
                })
            else:
                logger.info("[SocialAnalysis] friends risk: clean (0 flagged)")
        except Exception as e:
            logger.error(f"[SocialAnalysis] friends risk deep failed: {e}")

    # 5e. Collect new accounts for enrichment
    existing_contacts = check.contact_discoveries or {}
    results['new_accounts_for_enrichment'] = _collect_new_accounts(
        results['face_matches'],
        results['username_accounts'],
        existing_contacts,
    )

    _update('Социальный анализ завершён', 70)
    return results


def _is_deleted_account(user: Dict) -> bool:
    """Check if a VK user account is deleted or banned.

    Returns True when any of these conditions hold:
    - ``deactivated`` field is ``'deleted'`` or ``'banned'``
    - ``first_name`` is ``'DELETED'``
    - ``last_name`` is ``'DELETED'``
    """
    if user.get('deactivated') in ('deleted', 'banned'):
        return True
    if user.get('first_name', '') == 'DELETED':
        return True
    if user.get('last_name', '') == 'DELETED':
        return True
    return False


def _fetch_vk_friends(vk_id: int, token: str) -> List[Dict]:
    """Fetch VK friends list via API, filtering out deleted/banned accounts."""
    if not token:
        return []
    try:
        resp = requests.get(
            'https://api.vk.com/method/friends.get',
            params={
                'user_id': vk_id,
                'fields': 'first_name,last_name,photo_100,city,deactivated',
                'access_token': token,
                'v': '5.199',
            },
            timeout=15,
        )
        data = resp.json()
        if 'response' in data:
            items = data['response'].get('items', [])
            before = len(items)
            items = [u for u in items if not _is_deleted_account(u)]
            filtered = before - len(items)
            if filtered:
                logger.info(f"Social graph: filtered {filtered} deleted/banned accounts")
            return items
    except Exception as e:
        logger.warning(f"VK friends fetch failed: {e}")
    return []
