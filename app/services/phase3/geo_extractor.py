"""
Geo-Information Extractor
=========================
Extract location data from social media posts and build location timeline.
"""

import logging
import os
import re
import json
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from collections import Counter
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


@dataclass
class LocationPoint:
    """A single location point extracted from posts."""
    latitude: float
    longitude: float
    name: str = ""
    address: str = ""
    city: str = ""
    country: str = "Russia"
    timestamp: str = ""
    source: str = ""  # VK, OK, Instagram, Telegram
    post_url: str = ""
    confidence: str = "medium"  # high, medium, low

    def to_dict(self) -> Dict:
        return {
            'lat': self.latitude,
            'lng': self.longitude,
            'name': self.name,
            'address': self.address,
            'city': self.city,
            'country': self.country,
            'timestamp': self.timestamp,
            'source': self.source,
            'post_url': self.post_url,
            'confidence': self.confidence
        }


@dataclass
class LocationAnalysis:
    """Analysis results for location data."""
    locations: List[LocationPoint] = field(default_factory=list)
    home_location: Optional[LocationPoint] = None
    work_location: Optional[LocationPoint] = None
    frequent_places: List[Tuple[str, int]] = field(default_factory=list)
    travel_destinations: List[str] = field(default_factory=list)
    timeline: List[Dict] = field(default_factory=list)
    stats: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            'locations': [loc.to_dict() for loc in self.locations],
            'home_location': self.home_location.to_dict() if self.home_location else None,
            'work_location': self.work_location.to_dict() if self.work_location else None,
            'frequent_places': self.frequent_places,
            'travel_destinations': self.travel_destinations,
            'timeline': self.timeline,
            'stats': self.stats
        }


# Major Russian cities with coordinates
RUSSIAN_CITIES = {
    'москва': (55.7558, 37.6173),
    'moscow': (55.7558, 37.6173),
    'санкт-петербург': (59.9343, 30.3351),
    'saint petersburg': (59.9343, 30.3351),
    'спб': (59.9343, 30.3351),
    'питер': (59.9343, 30.3351),
    'новосибирск': (55.0084, 82.9357),
    'екатеринбург': (56.8389, 60.6057),
    'казань': (55.8304, 49.0661),
    'нижний новгород': (56.2965, 43.9361),
    'челябинск': (55.1644, 61.4368),
    'самара': (53.1959, 50.1002),
    'омск': (54.9885, 73.3242),
    'ростов-на-дону': (47.2357, 39.7015),
    'уфа': (54.7388, 55.9721),
    'красноярск': (56.0153, 92.8932),
    'воронеж': (51.6754, 39.2088),
    'пермь': (58.0105, 56.2502),
    'волгоград': (48.7080, 44.5133),
    'краснодар': (45.0393, 38.9870),
    'сочи': (43.6028, 39.7342),
    'владивосток': (43.1332, 131.9113),
    'иркутск': (52.2869, 104.3050),
    'тюмень': (57.1533, 65.5343),
    'калининград': (54.7065, 20.5109),
}


class GeoExtractor:
    """
    Extract geo-information from social media profiles and posts.

    Features:
    - Parse VK check-ins and location tags
    - Extract coordinates from posts
    - Build location timeline
    - Identify home/work locations
    - Generate map data for visualization
    """

    VK_API_VERSION = "5.131"

    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json, text/html',
        'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
    }

    def __init__(self, vk_service_token: Optional[str] = None):
        self.vk_token = vk_service_token or os.environ.get('VK_SERVICE_TOKEN')
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)

    def extract_from_profiles(
        self,
        profiles: List[Dict],
        max_posts_per_profile: int = 100
    ) -> LocationAnalysis:
        """
        Extract location data from multiple profiles.

        Args:
            profiles: List of profile dictionaries with platform, url, username
            max_posts_per_profile: Max posts to analyze per profile

        Returns:
            LocationAnalysis with all discovered locations
        """
        all_locations = []

        for profile in profiles:
            try:
                platform = profile.get('platform', '').lower()
                url = profile.get('url', '')
                username = profile.get('username', '')

                logger.info(f"Extracting locations from {platform}: {username}")

                if platform == 'vk' or 'vk.com' in url:
                    locs = self._extract_vk_locations(url, username, max_posts_per_profile)
                    all_locations.extend(locs)

                elif platform == 'ok' or 'ok.ru' in url:
                    locs = self._extract_ok_locations(url, username, max_posts_per_profile)
                    all_locations.extend(locs)

                elif platform == 'telegram' or 't.me' in url:
                    locs = self._extract_telegram_locations(url, username)
                    all_locations.extend(locs)

                # Extract city from profile info
                city = profile.get('city', '')
                if city:
                    loc = self._city_to_location(city, f"Profile: {platform}")
                    if loc:
                        all_locations.append(loc)

            except Exception as e:
                logger.warning(f"Failed to extract locations from {profile}: {e}")

        # Analyze locations
        return self._analyze_locations(all_locations)

    def _extract_vk_locations(
        self,
        profile_url: str,
        username: str,
        max_posts: int
    ) -> List[LocationPoint]:
        """Extract locations from VK profile."""
        locations = []

        # Extract user ID from URL
        user_id = self._extract_vk_user_id(profile_url)
        if not user_id:
            return locations

        # Try to get posts with geo data (requires API token)
        if self.vk_token:
            try:
                posts = self._get_vk_posts_with_geo(user_id, max_posts)
                for post in posts:
                    if post.get('geo'):
                        geo = post['geo']
                        coords = geo.get('coordinates', '').split()
                        if len(coords) >= 2:
                            locations.append(LocationPoint(
                                latitude=float(coords[0]),
                                longitude=float(coords[1]),
                                name=geo.get('place', {}).get('title', ''),
                                city=geo.get('place', {}).get('city', ''),
                                timestamp=datetime.fromtimestamp(post.get('date', 0)).isoformat() if post.get('date') else '',
                                source='VK',
                                post_url=f"https://vk.com/wall{user_id}_{post.get('id', '')}",
                                confidence='high'
                            ))
            except Exception as e:
                logger.debug(f"VK API geo extraction failed: {e}")

        # Fallback: scrape profile page for location mentions
        try:
            response = self.session.get(profile_url, timeout=30)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'lxml')

                # Look for city in profile
                city_elem = soup.select_one('.profile_info_row, [data-task="profile_city"]')
                if city_elem:
                    city_text = city_elem.get_text(strip=True)
                    loc = self._city_to_location(city_text, "VK profile")
                    if loc:
                        locations.append(loc)

                # Look for check-ins
                checkins = soup.select('.post_geo, .geo_link, [data-geo]')
                for checkin in checkins[:50]:
                    place_name = checkin.get_text(strip=True)
                    loc = self._place_to_location(place_name, "VK check-in")
                    if loc:
                        locations.append(loc)

        except Exception as e:
            logger.debug(f"VK scraping failed: {e}")

        return locations

    def _extract_vk_user_id(self, url: str) -> Optional[str]:
        """Extract VK user ID from URL."""
        # Patterns: vk.com/id123, vk.com/username
        match = re.search(r'vk\.com/(?:id(\d+)|([a-zA-Z][\w.]+))', url)
        if match:
            return match.group(1) or match.group(2)
        return None

    def _get_vk_posts_with_geo(self, user_id: str, count: int) -> List[Dict]:
        """Get VK posts with geo data via API."""
        if not self.vk_token:
            return []

        try:
            # Resolve screen name to ID if needed
            if not user_id.isdigit():
                resolve_url = f"https://api.vk.com/method/utils.resolveScreenName"
                response = self.session.get(resolve_url, params={
                    'screen_name': user_id,
                    'access_token': self.vk_token,
                    'v': self.VK_API_VERSION
                })
                data = response.json()
                if 'response' in data and data['response']:
                    user_id = str(data['response'].get('object_id', user_id))

            # Get wall posts
            wall_url = "https://api.vk.com/method/wall.get"
            response = self.session.get(wall_url, params={
                'owner_id': user_id,
                'count': count,
                'access_token': self.vk_token,
                'v': self.VK_API_VERSION
            })

            data = response.json()
            if 'response' in data:
                return data['response'].get('items', [])

        except Exception as e:
            logger.debug(f"VK API error: {e}")

        return []

    def _extract_ok_locations(
        self,
        profile_url: str,
        username: str,
        max_posts: int
    ) -> List[LocationPoint]:
        """Extract locations from OK profile."""
        locations = []

        try:
            response = self.session.get(profile_url, timeout=30)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'lxml')

                # City from profile
                city_elem = soup.select_one('.user-info__city, .location, [data-location]')
                if city_elem:
                    city = city_elem.get_text(strip=True)
                    loc = self._city_to_location(city, "OK profile")
                    if loc:
                        locations.append(loc)

                # Check-ins from feed
                geo_posts = soup.select('.feed-geo, .geo-tag, [data-geo]')
                for geo in geo_posts[:50]:
                    place = geo.get_text(strip=True)
                    loc = self._place_to_location(place, "OK check-in")
                    if loc:
                        locations.append(loc)

        except Exception as e:
            logger.debug(f"OK extraction failed: {e}")

        return locations

    def _extract_telegram_locations(
        self,
        profile_url: str,
        username: str
    ) -> List[LocationPoint]:
        """Extract locations from Telegram (limited - public channels only)."""
        locations = []

        # Telegram doesn't expose location data easily
        # Could parse bio for city mentions
        try:
            response = self.session.get(profile_url, timeout=30)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'lxml')

                # Check bio for city mentions
                bio_elem = soup.select_one('.tgme_page_description')
                if bio_elem:
                    bio = bio_elem.get_text()
                    # Look for Russian cities in bio
                    for city, coords in RUSSIAN_CITIES.items():
                        if city in bio.lower():
                            locations.append(LocationPoint(
                                latitude=coords[0],
                                longitude=coords[1],
                                name=city.title(),
                                city=city.title(),
                                source="Telegram bio",
                                confidence="low"
                            ))
                            break

        except Exception as e:
            logger.debug(f"Telegram extraction failed: {e}")

        return locations

    def extract_from_text(self, text: str) -> List[LocationPoint]:
        """Extract location points from arbitrary text (address, bio, etc.)."""
        locations = []
        if not text:
            return locations
        text_lower = text.lower()
        for city_name, coords in RUSSIAN_CITIES.items():
            if city_name in text_lower:
                locations.append(LocationPoint(
                    latitude=coords[0],
                    longitude=coords[1],
                    name=city_name.title(),
                    city=city_name.title(),
                    address=text.strip()[:200],
                    source="text_extraction",
                    confidence="medium"
                ))
        return locations

    def _city_to_location(self, city_text: str, source: str) -> Optional[LocationPoint]:
        """Convert city name to location point."""
        if not city_text:
            return None

        city_lower = city_text.lower().strip()

        # Check known cities
        for city_name, coords in RUSSIAN_CITIES.items():
            if city_name in city_lower or city_lower in city_name:
                return LocationPoint(
                    latitude=coords[0],
                    longitude=coords[1],
                    name=city_text,
                    city=city_text,
                    source=source,
                    confidence="high"
                )

        # If not found, try to geocode (simplified - just return None for unknown)
        return None

    def _place_to_location(self, place_text: str, source: str) -> Optional[LocationPoint]:
        """Convert place name to location point."""
        if not place_text:
            return None

        place_lower = place_text.lower()

        # Check if it contains a known city
        for city_name, coords in RUSSIAN_CITIES.items():
            if city_name in place_lower:
                return LocationPoint(
                    latitude=coords[0],
                    longitude=coords[1],
                    name=place_text,
                    city=city_name.title(),
                    source=source,
                    confidence="medium"
                )

        return None

    def _analyze_locations(self, locations: List[LocationPoint]) -> LocationAnalysis:
        """Analyze location data to identify patterns."""
        analysis = LocationAnalysis(locations=locations)

        if not locations:
            return analysis

        # Count location occurrences
        city_counts = Counter()
        for loc in locations:
            if loc.city:
                city_counts[loc.city] += 1

        # Frequent places
        analysis.frequent_places = city_counts.most_common(10)

        # Home location (most frequent)
        if city_counts:
            home_city = city_counts.most_common(1)[0][0]
            for loc in locations:
                if loc.city == home_city:
                    analysis.home_location = loc
                    break

        # Build timeline
        timeline = []
        for loc in sorted(locations, key=lambda x: x.timestamp or '', reverse=True):
            if loc.timestamp:
                timeline.append({
                    'date': loc.timestamp,
                    'location': loc.name or loc.city,
                    'source': loc.source
                })
        analysis.timeline = timeline[:50]  # Last 50 entries

        # Travel destinations (places with only 1-2 visits)
        travel = [city for city, count in city_counts.items() if count <= 2]
        analysis.travel_destinations = travel[:10]

        # Stats
        analysis.stats = {
            'total_locations': len(locations),
            'unique_cities': len(city_counts),
            'date_range': {
                'earliest': min((l.timestamp for l in locations if l.timestamp), default=''),
                'latest': max((l.timestamp for l in locations if l.timestamp), default='')
            }
        }

        return analysis

    def generate_map_data(self, locations: List[LocationPoint]) -> Dict:
        """Generate data for Leaflet map visualization."""
        markers = []
        for loc in locations:
            if loc.latitude and loc.longitude:
                markers.append({
                    'lat': loc.latitude,
                    'lng': loc.longitude,
                    'popup': f"<b>{loc.name or loc.city}</b><br>"
                             f"Source: {loc.source}<br>"
                             f"Date: {loc.timestamp or 'Unknown'}",
                    'color': self._get_marker_color(loc.source)
                })

        # Calculate center
        if markers:
            avg_lat = sum(m['lat'] for m in markers) / len(markers)
            avg_lng = sum(m['lng'] for m in markers) / len(markers)
        else:
            # Default to Moscow
            avg_lat, avg_lng = 55.7558, 37.6173

        return {
            'center': [avg_lat, avg_lng],
            'zoom': 6,
            'markers': markers
        }

    def _get_marker_color(self, source: str) -> str:
        """Get marker color based on source."""
        colors = {
            'VK': 'blue',
            'OK': 'orange',
            'Telegram': 'purple',
            'Instagram': 'pink'
        }
        return colors.get(source, 'gray')


# Singleton instance
geo_extractor = GeoExtractor()
