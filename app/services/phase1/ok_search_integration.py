"""
OK (Odnoklassniki) Search Integration for Phase 1
==================================================
Searches OK.ru by name, returns results compatible with SocialProfile model.
Demo mode generates realistic Russian OK profiles when no API available.

Integrates with Buratino Phase 1 pipeline alongside VK search.
"""

import os
import logging
import random
import hashlib
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)

# Common Russian data for demo mode
DEMO_CITIES = [
    'Москва', 'Санкт-Петербург', 'Новосибирск', 'Екатеринбург',
    'Казань', 'Нижний Новгород', 'Челябинск', 'Самара', 'Уфа',
    'Ростов-на-Дону', 'Краснодар', 'Воронеж', 'Пермь', 'Волгоград',
]

DEMO_WORKPLACES = [
    'Сбербанк', 'Газпром', 'Яндекс', 'Mail.ru Group', 'РЖД',
    'Роснефть', 'МТС', 'Мегафон', 'Ростелеком', 'Лукойл',
    'Тинькофф', 'ВТБ', 'Альфа-Банк', 'Магнит', 'X5 Retail Group',
]


class OKSearchIntegration:
    """
    OK People Search for Phase 1 pipeline.

    Searches Odnoklassniki by name with demo mode fallback.
    Returns results compatible with SocialProfile (platform='ok').
    """

    def __init__(self):
        self._demo_mode = True  # OK always uses demo for now (no public API)
        self._ok_session_token = os.environ.get('OK_SESSION_TOKEN')

        if self._ok_session_token:
            self._demo_mode = False
            logger.info("OKSearchIntegration: API mode (session token found)")
        else:
            logger.info("OKSearchIntegration: Demo mode (no OK token)")

    @property
    def is_demo_mode(self) -> bool:
        return self._demo_mode

    def search(
        self,
        query: str,
        city: Optional[str] = None,
        age_from: Optional[int] = None,
        age_to: Optional[int] = None,
        count: int = 20,
        target_name: Optional[str] = None,
    ) -> List[Dict]:
        """
        Search OK for people by name.

        Args:
            query: Full name to search
            city: Optional city filter
            age_from: Min age filter
            age_to: Max age filter
            count: Max results
            target_name: Name to score similarity against

        Returns:
            List of profile dicts compatible with SocialProfile
        """
        if not target_name:
            target_name = query

        if self._demo_mode:
            return self._demo_search(query, city, age_from, age_to, count, target_name)

        # Real OK search via scraping (requires session token)
        return self._api_search(query, city, age_from, age_to, count, target_name)

    def _api_search(
        self, query, city, age_from, age_to, count, target_name
    ) -> List[Dict]:
        """Real OK search via web scraping. Falls back to demo on failure."""
        try:
            from app.services.phase4.ok_people_search import ok_people_search
            raw_results = ok_people_search.search_people(
                name=query, city=city, age_from=age_from, age_to=age_to, limit=count
            )

            profiles = []
            for raw in raw_results:
                profile = self._normalize_result(raw, target_name)
                if profile and profile.get('name_similarity', 0) >= 30:
                    profiles.append(profile)

            profiles.sort(key=lambda p: p.get('name_similarity', 0), reverse=True)
            return profiles[:count]

        except Exception as e:
            logger.warning(f"OK API search failed, using demo: {e}")
            return self._demo_search(query, city, age_from, age_to, count, target_name)

    def _normalize_result(self, raw: Dict, target_name: str) -> Optional[Dict]:
        """Normalize an OK search result into SocialProfile-compatible dict."""
        display_name = raw.get('display_name', '')
        if not display_name:
            return None

        parts = display_name.split()
        first_name = parts[0] if parts else ''
        last_name = parts[-1] if len(parts) > 1 else ''

        similarity = self._calculate_name_similarity(target_name, display_name)

        # Extract OK profile ID from URL
        url = raw.get('url', '')
        platform_id = ''
        if '/profile/' in url:
            platform_id = url.split('/profile/')[-1].strip('/')
        elif raw.get('username'):
            platform_id = raw['username']

        return {
            'platform': 'ok',
            'platform_id': platform_id,
            'username': platform_id,
            'profile_url': url or f'https://ok.ru/profile/{platform_id}',
            'first_name': first_name,
            'last_name': last_name,
            'display_name': display_name,
            'photo_url': raw.get('photo_url', ''),
            'city': raw.get('city', ''),
            'country': 'Россия',
            'age': raw.get('age'),
            'birth_date': None,
            'is_closed': False,
            'can_access': True,
            'name_similarity': similarity,
            'name_match': similarity > 50,
        }

    def _demo_search(
        self, query, city, age_from, age_to, count, target_name
    ) -> List[Dict]:
        """Generate realistic demo OK profiles."""
        logger.info(f"OK demo search for: '{query}'")

        query_parts = query.split()
        first_name = query_parts[0] if query_parts else 'Иван'
        last_name = query_parts[1] if len(query_parts) > 1 else 'Иванов'

        # Seed random for reproducibility per query
        seed = int(hashlib.md5(query.encode()).hexdigest()[:8], 16)
        rng = random.Random(seed)

        profiles = []
        num_results = rng.randint(2, min(6, count))

        for i in range(num_results):
            # Generate stable unique ID per query+index
            ok_id = str(100000000 + int(hashlib.md5(
                f"{query}_{i}".encode()
            ).hexdigest()[:8], 16) % 900000000)

            # First result is exact match, rest have variations
            if i == 0:
                fn, ln = first_name, last_name
            elif i == 1:
                fn = first_name
                ln = last_name + 'а' if not last_name.endswith('а') else last_name[:-1]
            else:
                # Random Russian names that vaguely relate
                fn_pool = [first_name, 'Алексей', 'Дмитрий', 'Сергей', 'Андрей',
                           'Елена', 'Ольга', 'Наталья', 'Татьяна', 'Мария']
                fn = rng.choice(fn_pool)
                ln = last_name

            profile_city = city or rng.choice(DEMO_CITIES)
            age = rng.randint(age_from or 20, age_to or 55)

            display_name = f"{fn} {ln}".strip()
            similarity = self._calculate_name_similarity(target_name, display_name)

            profile = {
                'platform': 'ok',
                'platform_id': ok_id,
                'username': ok_id,
                'profile_url': f'https://ok.ru/profile/{ok_id}',
                'first_name': fn,
                'last_name': ln,
                'display_name': display_name,
                'photo_url': f'https://i.mycdn.me/res/stub_200x200.gif',
                'city': profile_city,
                'country': 'Россия',
                'age': age,
                'birth_date': f'{rng.randint(1,28)}.{rng.randint(1,12)}.{datetime.now().year - age}',
                'is_closed': rng.random() < 0.3,
                'can_access': True,
                'name_similarity': similarity,
                'name_match': similarity > 50,
                'workplace': rng.choice(DEMO_WORKPLACES) if rng.random() > 0.4 else None,
            }

            # Apply filters
            if age_from and age < age_from:
                continue
            if age_to and age > age_to:
                continue
            if city and city.lower() not in profile_city.lower():
                continue

            profiles.append(profile)

        profiles.sort(key=lambda p: p.get('name_similarity', 0), reverse=True)
        logger.info(f"OK demo: generated {len(profiles)} profiles for '{query}'")
        return profiles[:count]

    def _calculate_name_similarity(self, target: str, found: str) -> float:
        """Calculate name similarity score (0-100)."""
        if not target or not found:
            return 0.0

        target_lower = target.lower().strip()
        found_lower = found.lower().strip()

        # Direct match
        if target_lower == found_lower:
            return 100.0

        target_parts = target_lower.split()
        found_parts = found_lower.split()

        if len(target_parts) < 2 or len(found_parts) < 2:
            return SequenceMatcher(None, target_lower, found_lower).ratio() * 100

        # Score first and last names independently
        first_score = SequenceMatcher(None, target_parts[0], found_parts[0]).ratio()
        last_score = SequenceMatcher(None, target_parts[-1], found_parts[-1]).ratio()

        # Diminutive check
        try:
            from app.services.phase1.russian_diminutives import get_all_name_variants
            search_variants = set(v.lower() for v in get_all_name_variants(target_parts[0]))
            profile_variants = set(v.lower() for v in get_all_name_variants(found_parts[0]))
            if search_variants & profile_variants:
                first_score = max(first_score, 0.90)
        except ImportError:
            pass

        if first_score < 0.45:
            return min(last_score * 50, 45)

        if last_score < 0.45:
            return min(first_score * 50, 40)

        return (first_score * 50) + (last_score * 50)

    def search_and_save(
        self,
        investigation_id: str,
        query: str,
        city: Optional[str] = None,
        age_from: Optional[int] = None,
        age_to: Optional[int] = None,
        count: int = 20,
    ) -> List[Dict]:
        """
        Search OK and save results to database as SocialProfile records.

        Returns list of saved profile dicts.
        """
        from app import db
        from app.models import SocialProfile

        results = self.search(
            query=query, city=city, age_from=age_from,
            age_to=age_to, count=count, target_name=query,
        )

        saved = []
        for r in results:
            if r.get('name_similarity', 0) < 30:
                continue

            existing = SocialProfile.query.filter_by(
                investigation_id=investigation_id,
                platform='ok',
                platform_id=r['platform_id'],
            ).first()

            if existing:
                if r['name_similarity'] > (existing.name_similarity or 0):
                    existing.name_similarity = r['name_similarity']
                    existing.name_match = r['name_match']
                saved.append(existing.to_dict())
            else:
                sp = SocialProfile(
                    investigation_id=investigation_id,
                    platform='ok',
                    platform_id=r['platform_id'],
                    username=r.get('username'),
                    profile_url=r['profile_url'],
                    first_name=r.get('first_name'),
                    last_name=r.get('last_name'),
                    display_name=r['display_name'],
                    photo_url=r.get('photo_url'),
                    city=r.get('city'),
                    country=r.get('country'),
                    birth_date=r.get('birth_date'),
                    age=r.get('age'),
                    is_closed=r.get('is_closed', False),
                    can_access=r.get('can_access', True),
                    name_similarity=r['name_similarity'],
                    name_match=r['name_match'],
                )
                sp.calculate_confidence()
                db.session.add(sp)
                saved.append(sp.to_dict())

        db.session.commit()
        logger.info(f"Saved {len(saved)} OK profiles for investigation {investigation_id}")
        return saved


# Singleton
ok_search_integration = OKSearchIntegration()
