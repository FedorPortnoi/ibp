"""
Geo Intelligence Service
========================
Aggregates location data from all pipeline stages into a unified
geo-intelligence picture: presence map, activity timeline, location history.

Sources:
  - VK profile city/country/home_town
  - VK post geo-tags (coordinates)
  - VK last_seen timestamps + platform
  - EGRUL business addresses
  - Candidate form address
  - Telegram last_seen status

Output stored in CandidateCheck.geo_intelligence (JSON).
"""

import logging
import threading
import time
from collections import Counter
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any

import requests

from app.services.phase3.geo_extractor import RUSSIAN_CITIES

logger = logging.getLogger(__name__)

# Nominatim rate limit: 1 req/sec per ToS. geocode_city() is called from
# ThreadPoolExecutor workers across the pipeline, so the rate-limit gate and
# the result cache are guarded by a lock — otherwise two threads can clear the
# 1s check simultaneously and double-fire Nominatim, risking an IP ban.
_nominatim_lock = threading.Lock()
_last_nominatim_ts: float = 0.0
# Process-wide cache of successful geocodes (city->coords is stable). Failures
# are NOT cached so transient timeouts/rate-limits can be retried.
_geocode_cache: Dict[str, Tuple[float, float]] = {}

# VK last_seen platform codes
VK_PLATFORM_MAP = {
    1: 'mobile',
    2: 'iPhone',
    3: 'iPad',
    4: 'Android',
    5: 'Windows Phone',
    6: 'Windows',
    7: 'web',
}


# ── Geocoding ──────────────────────────────────────────────────────

def geocode_city(city_name: str) -> Optional[Tuple[float, float]]:
    """
    Resolve a city name to (lat, lon).
    1. Check local RUSSIAN_CITIES dict (instant, no network).
    2. Fall back to Nominatim (1 req/sec rate limit).
    """
    if not city_name:
        return None

    # Normalize
    key = city_name.strip().lower().replace('ё', 'е')

    # Strip common prefixes: "г. Москва" → "москва", "г Казань" → "казань"
    for prefix in ('г. ', 'г ', 'город '):
        if key.startswith(prefix):
            key = key[len(prefix):]
            break

    # Try local dict first
    if key in RUSSIAN_CITIES:
        return RUSSIAN_CITIES[key]

    # Try without region suffix: "москва, россия" → "москва"
    base = key.split(',')[0].strip()
    if base in RUSSIAN_CITIES:
        return RUSSIAN_CITIES[base]

    # Nominatim fallback
    return _nominatim_geocode(city_name)


def _nominatim_geocode(query: str) -> Optional[Tuple[float, float]]:
    """Geocode via Nominatim, thread-safe with 1 req/sec rate limiting + cache.

    The lock makes the rate-limit gate atomic across threads (ToS compliance)
    and serializes Nominatim calls. Successful results are cached process-wide;
    failures are not, so a transient error can be retried later.
    """
    global _last_nominatim_ts
    cache_key = query.strip().lower()

    with _nominatim_lock:
        if cache_key in _geocode_cache:
            return _geocode_cache[cache_key]

        elapsed = time.time() - _last_nominatim_ts
        if elapsed < 1.0:
            time.sleep(1.0 - elapsed)

        try:
            r = requests.get(
                'https://nominatim.openstreetmap.org/search',
                params={'q': query, 'format': 'json', 'limit': 1},
                headers={'User-Agent': 'SLED-IBP/1.0'},
                timeout=5,
            )
            _last_nominatim_ts = time.time()
            r.raise_for_status()
            data = r.json()
            if data:
                coords = (float(data[0]['lat']), float(data[0]['lon']))
                _geocode_cache[cache_key] = coords
                return coords
        except Exception as e:
            logger.debug(f"Nominatim geocode failed for '{query}': {e}")
            _last_nominatim_ts = time.time()
    return None


# ── Location Point Builders ────────────────────────────────────────

def _extract_vk_profile_locations(social_profiles: list) -> List[Dict]:
    """Extract city/country from VK profile data."""
    points = []
    for p in social_profiles:
        platform = (p.get('platform') or '').lower()
        if platform in ('ok', 'telegram', 'tg'):
            # Only process VK profiles; skip other platforms
            continue

        vk_data = p.get('vk_data') or p.get('raw_data') or p
        city_obj = vk_data.get('city') or {}
        city_name = city_obj.get('title', '') if isinstance(city_obj, dict) else str(city_obj)
        country_obj = vk_data.get('country') or {}
        country_name = country_obj.get('title', '') if isinstance(country_obj, dict) else str(country_obj)
        home_town = vk_data.get('home_town', '')

        # Profile city
        if city_name:
            location_str = city_name
            if country_name:
                location_str += f', {country_name}'
            coords = geocode_city(city_name)
            points.append({
                'source': 'vk_profile',
                'label': 'Город ВКонтакте',
                'location': location_str,
                'lat': coords[0] if coords else None,
                'lon': coords[1] if coords else None,
                'timestamp': None,
                'confidence': 'high',
                'icon_color': 'yellow',
            })

        # Home town (if different from city)
        if home_town and home_town.lower() != city_name.lower():
            coords = geocode_city(home_town)
            points.append({
                'source': 'vk_profile',
                'label': 'Родной город (ВК)',
                'location': home_town,
                'lat': coords[0] if coords else None,
                'lon': coords[1] if coords else None,
                'timestamp': None,
                'confidence': 'medium',
                'icon_color': 'yellow',
            })

    return points


def _extract_vk_post_geo(social_profiles: list) -> List[Dict]:
    """Extract geo-tags from VK posts (if available in cached data)."""
    points = []
    for p in social_profiles:
        vk_data = p.get('vk_data') or p.get('raw_data') or {}
        posts = vk_data.get('wall_posts') or vk_data.get('posts') or []
        for post in posts:
            geo = post.get('geo')
            if not geo:
                continue
            coords = geo.get('coordinates', '')
            place = geo.get('place', {})
            if isinstance(coords, str) and ' ' in coords:
                parts = coords.split(' ')
                try:
                    lat, lon = float(parts[0]), float(parts[1])
                except (ValueError, IndexError):
                    continue
            elif isinstance(coords, dict):
                lat = coords.get('latitude') or coords.get('lat')
                lon = coords.get('longitude') or coords.get('lon')
                if not lat or not lon:
                    continue
            else:
                continue

            ts = post.get('date')
            timestamp = None
            if ts:
                try:
                    timestamp = datetime.fromtimestamp(ts).strftime('%Y-%m-%d')
                except (ValueError, OSError):
                    pass

            city = ''
            if isinstance(place, dict):
                city = place.get('city', place.get('title', ''))

            points.append({
                'source': 'vk_post',
                'label': f'Геотег: {city}' if city else 'Геотег ВК',
                'location': city or f'{lat:.4f}, {lon:.4f}',
                'lat': lat,
                'lon': lon,
                'timestamp': timestamp,
                'confidence': 'high',
                'icon_color': 'green',
            })
    return points


def _extract_egrul_locations(identity_confirmation: dict, business_records: list) -> List[Dict]:
    """Extract business registration addresses from EGRUL data."""
    points = []
    seen_addresses = set()

    # From identity confirmation (Stage 0 EGRUL)
    egrul = identity_confirmation.get('egrul') or {}
    if isinstance(egrul, list):
        for entry in egrul:
            addr = entry.get('address', '')
            if addr and addr not in seen_addresses:
                seen_addresses.add(addr)
                city = _extract_city_from_address(addr)
                coords = geocode_city(city) if city else None
                points.append({
                    'source': 'egrul',
                    'label': 'ЕГРЮЛ',
                    'location': addr,
                    'lat': coords[0] if coords else None,
                    'lon': coords[1] if coords else None,
                    'timestamp': entry.get('registration_date'),
                    'confidence': 'high',
                    'icon_color': 'red',
                })
    elif isinstance(egrul, dict):
        addr = egrul.get('address', '')
        if addr and addr not in seen_addresses:
            seen_addresses.add(addr)
            city = _extract_city_from_address(addr)
            coords = geocode_city(city) if city else None
            points.append({
                'source': 'egrul',
                'label': 'ЕГРЮЛ',
                'location': addr,
                'lat': coords[0] if coords else None,
                'lon': coords[1] if coords else None,
                'timestamp': egrul.get('registration_date'),
                'confidence': 'high',
                'icon_color': 'red',
            })

    # From business records
    for biz in business_records:
        addr = biz.get('address', '')
        if addr and addr not in seen_addresses:
            seen_addresses.add(addr)
            city = _extract_city_from_address(addr)
            coords = geocode_city(city) if city else None
            points.append({
                'source': 'egrul',
                'label': f'ЕГРЮЛ: {biz.get("name", "")}',
                'location': addr,
                'lat': coords[0] if coords else None,
                'lon': coords[1] if coords else None,
                'timestamp': biz.get('registration_date'),
                'confidence': 'high',
                'icon_color': 'red',
            })

    return points


def _extract_city_from_address(address: str) -> str:
    """Extract city name from a Russian address string."""
    if not address:
        return ''
    # Common patterns: "г. Москва, ...", "г Казань, ..."
    addr_lower = address.lower()
    for prefix in ('г. ', 'г '):
        idx = addr_lower.find(prefix)
        if idx != -1:
            rest = address[idx + len(prefix):]
            city = rest.split(',')[0].strip()
            return city
    # Try first comma-separated part
    parts = address.split(',')
    if parts:
        first = parts[0].strip()
        # Check if it looks like a city
        if first.lower().replace('ё', 'е') in RUSSIAN_CITIES:
            return first
    return ''


def _extract_form_location(registered_address: str, region: str) -> List[Dict]:
    """Extract location from candidate form input."""
    points = []
    if registered_address:
        city = _extract_city_from_address(registered_address)
        coords = geocode_city(city or registered_address)
        points.append({
            'source': 'form',
            'label': 'Адрес регистрации',
            'location': registered_address,
            'lat': coords[0] if coords else None,
            'lon': coords[1] if coords else None,
            'timestamp': None,
            'confidence': 'high',
            'icon_color': 'red',
        })
    elif region:
        coords = geocode_city(region)
        if coords:
            points.append({
                'source': 'form',
                'label': 'Регион',
                'location': region,
                'lat': coords[0] if coords else None,
                'lon': coords[1] if coords else None,
                'timestamp': None,
                'confidence': 'medium',
                'icon_color': 'red',
            })
    return points


def _extract_telegram_locations(social_profiles: list) -> List[Dict]:
    """Extract any location info from Telegram profiles."""
    points = []
    for p in social_profiles:
        platform = (p.get('platform') or '').lower()
        if platform not in ('telegram', 'tg'):
            continue
        # Telegram doesn't expose city directly, but some bios mention it
        bio = p.get('bio') or p.get('description') or ''
        if not bio:
            continue
        # Try to find city mentions in bio
        bio_lower = bio.lower().replace('ё', 'е')
        for city_key, coords in RUSSIAN_CITIES.items():
            if city_key in bio_lower and len(city_key) >= 4:
                city_display = city_key.capitalize()
                points.append({
                    'source': 'telegram',
                    'label': 'Telegram Bio',
                    'location': city_display,
                    'lat': coords[0],
                    'lon': coords[1],
                    'timestamp': None,
                    'confidence': 'low',
                    'icon_color': 'blue',
                })
                break  # One city per profile
    return points


# ── VK Activity Timeline ──────────────────────────────────────────

def parse_vk_activity(activity_patterns: dict, activity_timeline: list) -> List[Dict]:
    """
    Build 7-day activity timeline from VK last_seen and activity data.

    Returns list of day entries:
    [{
        "date": "2026-03-27",
        "day_label": "Чт",
        "slots": {"morning": bool, "afternoon": bool, "evening": bool, "night": bool},
        "platform": "mobile",
        "total_activity": 3,  # number of active slots
    }]
    """
    days = []
    now = datetime.now()
    day_names_ru = {0: 'Пн', 1: 'Вт', 2: 'Ср', 3: 'Чт', 4: 'Пт', 5: 'Сб', 6: 'Вс'}

    # Build 7-day grid
    for i in range(6, -1, -1):
        day = now - timedelta(days=i)
        days.append({
            'date': day.strftime('%Y-%m-%d'),
            'day_label': day_names_ru.get(day.weekday(), ''),
            'slots': {'morning': False, 'afternoon': False, 'evening': False, 'night': False},
            'platform': None,
            'total_activity': 0,
        })

    # Extract timestamps from activity_timeline
    date_to_day = {d['date']: d for d in days}

    for entry in (activity_timeline or []):
        ts = entry.get('timestamp') or entry.get('time') or entry.get('date')
        if not ts:
            continue
        try:
            if isinstance(ts, (int, float)):
                dt = datetime.fromtimestamp(ts)
            else:
                dt = datetime.fromisoformat(str(ts).replace('Z', '+00:00'))
            date_key = dt.strftime('%Y-%m-%d')
            if date_key in date_to_day:
                day_entry = date_to_day[date_key]
                hour = dt.hour
                if 6 <= hour < 12:
                    day_entry['slots']['morning'] = True
                elif 12 <= hour < 18:
                    day_entry['slots']['afternoon'] = True
                elif 18 <= hour < 23:
                    day_entry['slots']['evening'] = True
                else:
                    day_entry['slots']['night'] = True
                day_entry['total_activity'] = sum(day_entry['slots'].values())
        except (ValueError, TypeError, OSError):
            continue

    # Extract platform from activity_patterns
    last_seen = activity_patterns.get('last_seen') or {}
    preferred = last_seen.get('preferred_platform', '')
    most_recent = last_seen.get('most_recent') or {}
    platform_name = most_recent.get('platform_name', preferred)

    # Fill platform info and mark recent activity
    if most_recent:
        last_ts = most_recent.get('last_seen_ts')
        if last_ts:
            try:
                last_dt = datetime.fromtimestamp(last_ts)
                date_key = last_dt.strftime('%Y-%m-%d')
                if date_key in date_to_day:
                    day_entry = date_to_day[date_key]
                    day_entry['platform'] = platform_name or 'online'
                    hour = last_dt.hour
                    if 6 <= hour < 12:
                        day_entry['slots']['morning'] = True
                    elif 12 <= hour < 18:
                        day_entry['slots']['afternoon'] = True
                    elif 18 <= hour < 23:
                        day_entry['slots']['evening'] = True
                    else:
                        day_entry['slots']['night'] = True
                    day_entry['total_activity'] = sum(day_entry['slots'].values())
            except (ValueError, OSError):
                pass

    # Set platform on all days that have activity
    for d in days:
        if d['total_activity'] > 0 and not d['platform']:
            d['platform'] = platform_name or None

    return days


# ── Location History ──────────────────────────────────────────────

def build_location_history(location_points: List[Dict]) -> List[Dict]:
    """
    Build chronological location change history from all points.

    Returns sorted list:
    [{
        "date": "2024-01",
        "source": "vk_profile",
        "location": "Казань, РФ",
        "confidence": "high",  # high=●●●, medium=●●○, low=●○○
    }]
    """
    history = []
    seen = set()

    for pt in location_points:
        if not pt.get('location'):
            continue

        date = pt.get('timestamp') or ''
        # Normalize to YYYY-MM format
        if date and len(date) >= 7:
            date_key = date[:7]
        elif date and len(date) == 4:
            date_key = date
        else:
            date_key = ''

        # Deduplicate by (location, source)
        dedup_key = (pt['location'].lower(), pt['source'], date_key)
        if dedup_key in seen:
            continue
        seen.add(dedup_key)

        history.append({
            'date': date_key,
            'date_display': _format_date_display(date_key),
            'source': pt['source'],
            'source_label': _source_label(pt['source']),
            'location': pt['location'],
            'confidence': pt.get('confidence', 'medium'),
        })

    # Sort: entries with dates first (chronological), then undated
    history.sort(key=lambda x: (x['date'] or 'zzzz'))
    return history


def _format_date_display(date_str: str) -> str:
    """Format YYYY-MM to human-readable Russian."""
    if not date_str:
        return '—'
    months_ru = {
        '01': 'Янв', '02': 'Фев', '03': 'Мар', '04': 'Апр',
        '05': 'Май', '06': 'Июн', '07': 'Июл', '08': 'Авг',
        '09': 'Сен', '10': 'Окт', '11': 'Ноя', '12': 'Дек',
    }
    parts = date_str.split('-')
    if len(parts) >= 2:
        year = parts[0]
        month = months_ru.get(parts[1], parts[1])
        return f'{month} {year}'
    return date_str


def _source_label(source: str) -> str:
    """Human-readable source label."""
    return {
        'vk_profile': 'VK профиль',
        'vk_post': 'VK геотег',
        'egrul': 'ЕГРЮЛ',
        'form': 'Анкета',
        'telegram': 'Telegram',
    }.get(source, source)


# ── Demo Data ─────────────────────────────────────────────────────

def _get_demo_geo_intelligence() -> Dict[str, Any]:
    """Return realistic demo geo intelligence data."""
    now = datetime.now()
    day_names_ru = {0: 'Пн', 1: 'Вт', 2: 'Ср', 3: 'Чт', 4: 'Пт', 5: 'Сб', 6: 'Вс'}

    location_points = [
        {
            'source': 'form',
            'label': 'Адрес регистрации',
            'location': 'г. Казань, ул. Баумана, д. 15',
            'lat': 55.7903,
            'lon': 49.1147,
            'timestamp': '2024-01-15',
            'confidence': 'high',
            'icon_color': 'red',
        },
        {
            'source': 'vk_profile',
            'label': 'Город ВКонтакте',
            'location': 'Москва, Россия',
            'lat': 55.7558,
            'lon': 37.6173,
            'timestamp': None,
            'confidence': 'high',
            'icon_color': 'yellow',
        },
        {
            'source': 'vk_post',
            'label': 'Геотег: Санкт-Петербург',
            'location': 'Санкт-Петербург',
            'lat': 59.9343,
            'lon': 30.3351,
            'timestamp': '2025-08-20',
            'confidence': 'high',
            'icon_color': 'green',
        },
        {
            'source': 'egrul',
            'label': 'ЕГРЮЛ: ООО "Альфа-Строй"',
            'location': 'г. Москва, ул. Ленина, д. 10',
            'lat': 55.7558,
            'lon': 37.6173,
            'timestamp': '2018-03-15',
            'confidence': 'high',
            'icon_color': 'red',
        },
    ]

    # 7-day activity timeline
    activity_timeline = []
    for i in range(6, -1, -1):
        day = now - timedelta(days=i)
        # Simulate activity pattern: more active on weekdays
        is_weekday = day.weekday() < 5
        activity_timeline.append({
            'date': day.strftime('%Y-%m-%d'),
            'day_label': day_names_ru.get(day.weekday(), ''),
            'slots': {
                'morning': is_weekday and i != 3,
                'afternoon': is_weekday,
                'evening': i != 5,
                'night': i == 6 or i == 0,
            },
            'platform': 'Android' if i % 2 == 0 else 'web',
            'total_activity': (3 if is_weekday else 2) - (1 if i == 3 else 0),
        })

    location_history = [
        {
            'date': '2018-03',
            'date_display': 'Мар 2018',
            'source': 'egrul',
            'source_label': 'ЕГРЮЛ',
            'location': 'г. Москва, ул. Ленина, д. 10',
            'confidence': 'high',
        },
        {
            'date': '2024-01',
            'date_display': 'Янв 2024',
            'source': 'form',
            'source_label': 'Анкета',
            'location': 'г. Казань, ул. Баумана, д. 15',
            'confidence': 'high',
        },
        {
            'date': '2025-08',
            'date_display': 'Авг 2025',
            'source': 'vk_post',
            'source_label': 'VK геотег',
            'location': 'Санкт-Петербург',
            'confidence': 'high',
        },
    ]

    return {
        'location_points': location_points,
        'activity_timeline': activity_timeline,
        'location_history': location_history,
        'summary': {
            'total_locations': len(location_points),
            'sources_count': 4,
            'primary_city': 'Москва',
            'has_relocation': True,
        },
    }


# ── Main Entry Point ──────────────────────────────────────────────

def collect_geo_intelligence(check, is_demo: bool = False) -> Dict[str, Any]:
    """
    Aggregate geo intelligence from all pipeline data on a CandidateCheck.

    Args:
        check: CandidateCheck model instance (must have completed stages 0-6).
        is_demo: If True, return demo data.

    Returns:
        Dict with keys: location_points, activity_timeline, location_history, summary
    """
    if is_demo:
        return _get_demo_geo_intelligence()

    # Collect location points from all sources
    all_points: List[Dict] = []

    # 1. VK profile city/country/home_town
    profiles = check.social_media_profiles or []
    all_points.extend(_extract_vk_profile_locations(profiles))

    # 2. VK post geo-tags
    all_points.extend(_extract_vk_post_geo(profiles))

    # 3. EGRUL addresses
    identity = check.identity_confirmation or {}
    biz_records = check.business_records or []
    all_points.extend(_extract_egrul_locations(identity, biz_records))

    # 4. Candidate form address
    all_points.extend(_extract_form_location(
        check.registered_address or '',
        check.region or '',
    ))

    # 5. Telegram locations
    all_points.extend(_extract_telegram_locations(profiles))

    # Filter out points without coordinates
    geo_points = [p for p in all_points if p.get('lat') and p.get('lon')]
    non_geo_points = [p for p in all_points if not (p.get('lat') and p.get('lon'))]

    # 6. Activity timeline (7-day)
    activity_patterns = check.activity_patterns or {}
    activity_tl = check.activity_timeline or []
    timeline_7d = parse_vk_activity(activity_patterns, activity_tl)

    # 7. Location history
    location_history = build_location_history(all_points)

    # 8. Summary
    sources = set(p['source'] for p in all_points)
    cities = [p['location'] for p in geo_points]
    city_counter = Counter(cities)
    primary_city = city_counter.most_common(1)[0][0] if city_counter else None

    # Detect relocation: different cities with dates
    dated_cities = []
    for p in all_points:
        if p.get('timestamp') and p.get('location'):
            city = _extract_city_from_address(p['location']) or p['location']
            dated_cities.append((p['timestamp'], city.lower()))
    dated_cities.sort()
    unique_dated = []
    for _, c in dated_cities:
        if not unique_dated or unique_dated[-1] != c:
            unique_dated.append(c)
    has_relocation = len(unique_dated) > 1

    return {
        'location_points': geo_points + non_geo_points,
        'activity_timeline': timeline_7d,
        'location_history': location_history,
        'summary': {
            'total_locations': len(all_points),
            'geo_locations': len(geo_points),
            'sources_count': len(sources),
            'primary_city': primary_city,
            'has_relocation': has_relocation,
        },
    }
