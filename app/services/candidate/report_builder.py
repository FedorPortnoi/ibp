"""
Report Builder (Stage 8)
========================
Compiles ALL data from all 8 pipeline stages into a single report structure.
Used by the dossier template, JSON export, and PDF export.
"""

import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


def _safe_json(value, default):
    """Safely handle JSON fields that might be strings or already parsed."""
    if value is None:
        return default
    if isinstance(value, str):
        try:
            import json
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return default
    return value


def _extract_phones(contact_discoveries: Dict) -> List[Dict]:
    """Extract phone list from contact discoveries."""
    phones = []
    for item in (contact_discoveries.get('phones') or []):
        if isinstance(item, dict):
            phones.append({
                'number': item.get('number', ''),
                'source': item.get('source', ''),
                'confidence': item.get('confidence', ''),
            })
    return phones


def _extract_emails(contact_discoveries: Dict) -> List[Dict]:
    """Extract email list from contact discoveries."""
    emails = []
    for item in (contact_discoveries.get('emails') or []):
        if isinstance(item, dict):
            emails.append({
                'address': item.get('email', item.get('address', '')),
                'source': item.get('source', ''),
                'confidence': item.get('confidence', ''),
                'verified': item.get('verified', False),
            })
    return emails


def _build_timeline_events(check) -> List[Dict]:
    """Build chronological events from all sources."""
    events = []

    # From activity timeline (Stage 6)
    timeline = _safe_json(check.activity_timeline, [])
    for event in timeline:
        if isinstance(event, dict):
            events.append({
                'timestamp': event.get('timestamp', ''),
                'type': event.get('type', 'unknown'),
                'source': event.get('source', ''),
                'summary': event.get('summary', ''),
            })

    # Check creation/completion
    if check.created_at:
        events.append({
            'timestamp': check.created_at.isoformat(),
            'type': 'check_started',
            'source': 'system',
            'summary': 'Проверка начата',
        })
    if check.completed_at:
        events.append({
            'timestamp': check.completed_at.isoformat(),
            'type': 'check_completed',
            'source': 'system',
            'summary': 'Проверка завершена',
        })

    # Sort by timestamp, newest first
    events.sort(key=lambda e: e.get('timestamp', ''), reverse=True)
    return events


def _build_social_graph_summary(graph_data: Dict) -> Dict:
    """Summarize social graph data."""
    if not graph_data or not isinstance(graph_data, dict):
        return {'node_count': 0, 'edge_count': 0, 'communities': 0, 'key_connections': []}

    stats = graph_data.get('stats', {})
    clusters = graph_data.get('clusters', [])

    # Find key connections (highest degree nodes)
    key_connections = []
    for node in (graph_data.get('nodes') or [])[:5]:
        if isinstance(node, dict) and not node.get('is_center', False):
            key_connections.append({
                'name': node.get('label', ''),
                'id': node.get('id', ''),
            })

    return {
        'node_count': stats.get('node_count', 0),
        'edge_count': stats.get('edge_count', 0),
        'communities': len(clusters),
        'density': stats.get('density', 0),
        'key_connections': key_connections[:5],
    }


def _build_geo_summary(geo_data: Dict) -> Dict:
    """Summarize geo analysis data."""
    if not geo_data or not isinstance(geo_data, dict):
        return {'home_location': None, 'frequent_places': [], 'total_locations': 0}

    home = geo_data.get('home_location')
    home_summary = None
    if isinstance(home, dict):
        home_summary = {
            'city': home.get('city', ''),
            'lat': home.get('lat', 0),
            'lng': home.get('lng', 0),
        }

    return {
        'home_location': home_summary,
        'frequent_places': geo_data.get('frequent_places', [])[:5],
        'total_locations': len(geo_data.get('locations', [])),
        'map_data': geo_data.get('map_data', {}),
    }


def _build_behavioral_summary(text_data: Dict) -> Dict:
    """Summarize behavioral analysis data."""
    if not text_data or not isinstance(text_data, dict):
        return {'sentiment': None, 'keywords': [], 'topics': {}, 'posting_pattern': 'unknown'}

    sentiment = text_data.get('sentiment')
    sentiment_summary = None
    if isinstance(sentiment, dict):
        sentiment_summary = {
            'score': sentiment.get('score', 0),
            'label': sentiment.get('label', 'neutral'),
        }

    # Determine posting pattern from posting_times
    posting_times = text_data.get('posting_times', [])
    pattern = 'unknown'
    if posting_times:
        night = sum(1 for h in posting_times if 0 <= h <= 5)
        morning = sum(1 for h in posting_times if 6 <= h <= 11)
        day = sum(1 for h in posting_times if 12 <= h <= 17)
        evening = sum(1 for h in posting_times if 18 <= h <= 23)
        total = len(posting_times)
        if total > 0:
            if night / total > 0.3:
                pattern = 'night_owl'
            elif morning / total > 0.3:
                pattern = 'early_bird'
            elif evening / total > 0.4:
                pattern = 'evening_active'
            else:
                pattern = 'regular'

    return {
        'sentiment': sentiment_summary,
        'keywords': text_data.get('keywords', [])[:10],
        'topics': text_data.get('topics', {}),
        'posting_pattern': pattern,
        'word_count': text_data.get('word_count', 0),
    }


def _demo_report() -> Dict[str, Any]:
    """Return a complete fake report for demo mode."""
    return {
        'identity_card': {
            'full_name': 'Иванов Иван Петрович',
            'date_of_birth': '1985-03-15',
            'photo_url': '',
            'city': 'Москва',
            'confirmed_accounts': [
                {'platform': 'vk', 'username': 'ivan.ivanov', 'url': 'https://vk.com/ivan.ivanov'},
            ],
        },
        'risk_summary': {
            'risk_level': 'low',
            'risk_score': 15.0,
            'top_flags': [
                {'severity': 'low', 'text': 'Не обнаружено присутствие в соцсетях (необычно)'},
            ],
        },
        'government_records': {
            'business_records': [
                {'company_name': 'ООО "Тест"', 'inn': '7701234567', 'role': 'Учредитель', 'status': 'Действующее'},
            ],
            'court_records': [],
            'fssp_records': [],
            'bankruptcy_records': [],
        },
        'sanctions': {
            'checked': True,
            'found': False,
            'sources': ['Росфинмониторинг', 'МВД'],
        },
        'social_profiles': [
            {'platform': 'vk', 'username': 'ivan.ivanov', 'url': 'https://vk.com/ivan.ivanov', 'city': 'Москва'},
        ],
        'contact_info': {
            'phones': [{'number': '+79161234567', 'source': 'vk_profile', 'confidence': 'высокая'}],
            'emails': [{'address': 'ivan.ivanov@mail.ru', 'source': 'holehe_verified', 'confidence': 'высокая', 'verified': True}],
        },
        'social_graph_summary': {
            'node_count': 50,
            'edge_count': 120,
            'communities': 3,
            'density': 0.05,
            'key_connections': [
                {'name': 'Петр Петров', 'id': 'vk_111'},
                {'name': 'Мария Сидорова', 'id': 'vk_222'},
            ],
        },
        'geo_summary': {
            'home_location': {'city': 'Москва', 'lat': 55.7558, 'lng': 37.6173},
            'frequent_places': [('Москва', 15), ('Санкт-Петербург', 3)],
            'total_locations': 18,
            'map_data': {'center': [55.7558, 37.6173], 'zoom': 6, 'markers': []},
        },
        'behavioral_summary': {
            'sentiment': {'score': 0.15, 'label': 'neutral'},
            'keywords': [('работа', 12), ('проект', 8)],
            'topics': {'работа': 0.35, 'хобби': 0.25},
            'posting_pattern': 'evening_active',
            'word_count': 1500,
        },
        'face_matches': [
            {'platform': 'vk', 'similarity_score': 0.92, 'profile_url': 'https://vk.com/id100001', 'name': 'Иван Иванов'},
        ],
        'timeline_events': [
            {'timestamp': '2026-01-15T10:00:00', 'type': 'check_started', 'source': 'system', 'summary': 'Проверка начата'},
        ],
        'metadata': {
            'check_id': 'demo-check-001',
            'created_at': '2026-01-15T10:00:00',
            'completed_at': '2026-01-15T10:05:00',
            'duration_seconds': 300,
            'mode': 'quick',
            'stages_completed': 8,
        },
    }


def build_report(check) -> Dict[str, Any]:
    """
    Compile ALL data from all 8 stages into a single report structure.

    Args:
        check: CandidateCheck model instance

    Returns:
        Complete report dict with all sections.
    """
    # Check for demo/empty data
    has_real_data = bool(
        _safe_json(check.business_records, [])
        or _safe_json(check.court_records, [])
        or _safe_json(check.social_media_profiles, [])
        or _safe_json(check.contact_discoveries, {}).get('phones')
        or _safe_json(check.contact_discoveries, {}).get('emails')
    )

    if not has_real_data and not check.full_name:
        return _demo_report()

    # Gather all data
    business_records = _safe_json(check.business_records, [])
    court_records = _safe_json(check.court_records, [])
    fssp_records = _safe_json(check.fssp_records, [])
    bankruptcy_records = _safe_json(check.bankruptcy_records, [])
    sanctions_results = _safe_json(check.sanctions_results, {})
    social_profiles = _safe_json(check.social_media_profiles, [])
    confirmed_profiles = _safe_json(check.confirmed_profiles, [])
    contact_discoveries = _safe_json(check.contact_discoveries, {})
    social_graph = _safe_json(check.social_graph_data, {})
    face_matches = _safe_json(check.face_matches, [])
    username_accounts = _safe_json(check.username_accounts, [])
    text_analysis = _safe_json(check.text_analysis, {})
    geo_analysis = _safe_json(check.geo_analysis, {})
    red_flags = _safe_json(check.red_flags, [])
    risk_breakdown = _safe_json(check.risk_breakdown, {})

    # Determine photo URL
    photo_url = ''
    for p in (confirmed_profiles or social_profiles):
        if isinstance(p, dict):
            url = p.get('photo_url') or p.get('photo_100') or p.get('photo_200', '')
            if url:
                photo_url = url
                break

    # Determine city
    city = ''
    for p in (confirmed_profiles or social_profiles):
        if isinstance(p, dict) and p.get('city'):
            city = p['city']
            break

    # Build confirmed accounts list
    confirmed_accounts = []
    for p in (confirmed_profiles or social_profiles):
        if isinstance(p, dict):
            confirmed_accounts.append({
                'platform': p.get('platform', ''),
                'username': p.get('username', ''),
                'url': p.get('url', p.get('profile_url', '')),
                'city': p.get('city', ''),
            })

    # Calculate duration
    duration = None
    if check.created_at and check.completed_at:
        duration = (check.completed_at - check.created_at).total_seconds()
    elif check.check_duration_seconds:
        duration = check.check_duration_seconds

    # Identity confirmation data from Stage 0
    identity_confirmation = _safe_json(getattr(check, 'identity_confirmation', None), {})

    report = {
        'identity_card': {
            'full_name': check.full_name,
            'confirmed_name': getattr(check, 'confirmed_name', None),
            'inn': check.inn,
            'identity_confirmed': getattr(check, 'identity_confirmed', False),
            'date_of_birth': check.date_of_birth.isoformat() if check.date_of_birth else None,
            'photo_url': photo_url,
            'city': city,
            'confirmed_accounts': confirmed_accounts,
        },
        'identity_confirmation': {
            'inn': check.inn,
            'confirmed_name': getattr(check, 'confirmed_name', None),
            'identity_confirmed': getattr(check, 'identity_confirmed', False),
            'egrul_status': identity_confirmation.get('egrul_status'),
            'business_network': identity_confirmation.get('business_network', []),
            'name_discrepancy': identity_confirmation.get('name_discrepancy', False),
        },
        'risk_summary': {
            'risk_level': check.risk_level or 'unknown',
            'risk_score': check.risk_score_numeric,
            'top_flags': red_flags[:5],
            'risk_breakdown': risk_breakdown,
        },
        'government_records': {
            'business_records': business_records,
            'court_records': court_records,
            'fssp_records': fssp_records,
            'bankruptcy_records': bankruptcy_records,
        },
        'sanctions': sanctions_results,
        'social_profiles': confirmed_accounts + [
            {
                'platform': a.get('platform', ''),
                'username': a.get('username', ''),
                'url': a.get('url', ''),
                'source': a.get('source', ''),
            }
            for a in username_accounts
            if isinstance(a, dict)
        ],
        'contact_info': {
            'phones': _extract_phones(contact_discoveries),
            'emails': _extract_emails(contact_discoveries),
        },
        'social_graph_summary': _build_social_graph_summary(social_graph),
        'geo_summary': _build_geo_summary(geo_analysis),
        'behavioral_summary': _build_behavioral_summary(text_analysis),
        'face_matches': face_matches,
        'timeline_events': _build_timeline_events(check),
        'metadata': {
            'check_id': check.id,
            'created_at': check.created_at.isoformat() if check.created_at else None,
            'completed_at': check.completed_at.isoformat() if check.completed_at else None,
            'duration_seconds': duration,
            'mode': getattr(check, 'check_mode', 'quick') or 'quick',
            'stages_completed': _count_stages(check),
        },
    }

    return report


def _count_stages(check) -> int:
    """Count how many pipeline stages have data."""
    count = 0
    if getattr(check, 'identity_confirmed', False) or _safe_json(getattr(check, 'identity_confirmation', None), {}):
        count += 1  # Stage 0
    if _safe_json(check.business_records, []) or _safe_json(check.court_records, []):
        count += 1  # Stage 1
    if _safe_json(check.sanctions_results, {}):
        count += 1  # Stage 2
    if _safe_json(check.social_media_profiles, []):
        count += 1  # Stage 3
    if _safe_json(check.contact_discoveries, {}).get('phones') or _safe_json(check.contact_discoveries, {}).get('emails'):
        count += 1  # Stage 4
    if _safe_json(check.social_graph_data, {}) or _safe_json(check.face_matches, []):
        count += 1  # Stage 5
    if _safe_json(check.text_analysis, {}) or _safe_json(check.geo_analysis, {}):
        count += 1  # Stage 6
    if check.risk_level:
        count += 1  # Stage 7
    if getattr(check, 'report_generated', False):
        count += 1  # Stage 8
    return count
