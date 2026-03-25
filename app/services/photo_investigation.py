"""
Photo-First Investigation Service
==================================
Upload photo -> face search -> discover social profiles.
Uses Search4faces API when available, demo mode otherwise.
"""

import os
import uuid
import logging
import hashlib
import random
from datetime import datetime
from typing import List, Dict, Optional
from werkzeug.utils import secure_filename

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


class PhotoInvestigation:
    """
    Photo-first investigation flow:
    1. Accept uploaded photo (validate format/size)
    2. Search faces via Search4faces API or demo mode
    3. Return potential matches for user selection
    4. Create investigation from selected match
    """

    def __init__(self):
        self._api_key = os.environ.get('SEARCH4FACES_API_KEY')
        self._demo_mode = not self._api_key

        if self._demo_mode:
            logger.info("PhotoInvestigation: Demo mode (no SEARCH4FACES_API_KEY)")
        else:
            logger.info("PhotoInvestigation: API mode enabled")

    @property
    def is_demo_mode(self) -> bool:
        return self._demo_mode

    def validate_photo(self, file) -> Optional[str]:
        """
        Validate uploaded photo file.

        Returns error message or None if valid.
        """
        if not file or not file.filename:
            return 'Файл не выбран'

        ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
        if ext not in ALLOWED_EXTENSIONS:
            return f'Неподдерживаемый формат. Разрешены: {", ".join(ALLOWED_EXTENSIONS)}'

        # Check size by reading content length
        file.seek(0, 2)
        size = file.tell()
        file.seek(0)

        if size > MAX_FILE_SIZE:
            return f'Файл слишком большой. Максимум: {MAX_FILE_SIZE // (1024*1024)} МБ'

        if size < 1024:
            return 'Файл слишком маленький. Минимум: 1 КБ'

        return None

    def save_photo(self, file, upload_folder: str) -> str:
        """Save uploaded photo and return the file path."""
        os.makedirs(upload_folder, exist_ok=True)
        filename = secure_filename(f"{uuid.uuid4().hex}_{file.filename}")
        filepath = os.path.join(upload_folder, filename)
        file.save(filepath)
        return filepath

    def search_by_photo(self, photo_path: str, max_results: int = 20) -> List[Dict]:
        """
        Search for faces matching the uploaded photo.

        Returns list of potential matches with profile info.
        """
        if self._demo_mode:
            return self._demo_search(photo_path, max_results)

        return self._api_search(photo_path, max_results)

    def _api_search(self, photo_path: str, max_results: int) -> List[Dict]:
        """Real API search via Search4faces."""
        try:
            from app.services.phase2.search4faces_service import search_by_photo

            result = search_by_photo(
                image_path=photo_path,
                database='vkok',
                max_results=max_results,
            )

            if not result.success:
                logger.warning(f"Search4faces failed: {result.error}")
                return self._demo_search(photo_path, max_results)

            matches = []
            for m in result.matches:
                matches.append({
                    'platform': m.platform or 'vk',
                    'profile_url': m.profile_url,
                    'username': m.username,
                    'display_name': m.name or '',
                    'photo_url': m.thumbnail_url or '',
                    'similarity_score': m.similarity_score or 0.5,
                    'source': 'search4faces',
                })

            return matches[:max_results]

        except Exception as e:
            logger.error(f"Photo API search failed: {e}")
            return self._demo_search(photo_path, max_results)

    def _demo_search(self, photo_path: str, max_results: int) -> List[Dict]:
        """Generate demo face match results."""
        logger.info("Photo search: generating demo results")

        # Seed based on file hash for reproducibility
        if os.path.exists(photo_path):
            with open(photo_path, 'rb') as f:
                file_hash = hashlib.md5(f.read(4096), usedforsecurity=False).hexdigest()
        else:
            file_hash = hashlib.md5(photo_path.encode(), usedforsecurity=False).hexdigest()

        rng = random.Random(int(file_hash[:8], 16))

        demo_profiles = [
            {
                'first_name': 'Анна', 'last_name': 'Петрова',
                'city': 'Москва', 'age': 28, 'platform': 'vk',
            },
            {
                'first_name': 'Мария', 'last_name': 'Иванова',
                'city': 'Санкт-Петербург', 'age': 25, 'platform': 'vk',
            },
            {
                'first_name': 'Елена', 'last_name': 'Сидорова',
                'city': 'Казань', 'age': 32, 'platform': 'ok',
            },
            {
                'first_name': 'Ольга', 'last_name': 'Козлова',
                'city': 'Новосибирск', 'age': 27, 'platform': 'vk',
            },
            {
                'first_name': 'Дмитрий', 'last_name': 'Волков',
                'city': 'Екатеринбург', 'age': 30, 'platform': 'ok',
            },
            {
                'first_name': 'Алексей', 'last_name': 'Новиков',
                'city': 'Москва', 'age': 35, 'platform': 'vk',
            },
        ]

        rng.shuffle(demo_profiles)
        results = []

        for i, p in enumerate(demo_profiles[:max_results]):
            profile_id = str(rng.randint(10000000, 999999999))
            similarity = round(0.95 - i * 0.12 + rng.uniform(-0.05, 0.05), 2)
            similarity = max(0.3, min(0.99, similarity))

            display_name = f"{p['first_name']} {p['last_name']}"
            platform = p['platform']

            if platform == 'vk':
                url = f"https://vk.com/id{profile_id}"
                photo = 'https://vk.com/images/camera_200.png'
            else:
                url = f"https://ok.ru/profile/{profile_id}"
                photo = 'https://i.mycdn.me/res/stub_200x200.gif'

            results.append({
                'platform': platform,
                'platform_id': profile_id,
                'profile_url': url,
                'username': f"id{profile_id}" if platform == 'vk' else profile_id,
                'first_name': p['first_name'],
                'last_name': p['last_name'],
                'display_name': display_name,
                'photo_url': photo,
                'city': p['city'],
                'age': p['age'],
                'similarity_score': similarity,
                'source': 'search4faces_demo',
            })

        results.sort(key=lambda x: x['similarity_score'], reverse=True)
        logger.info(f"Photo demo: generated {len(results)} matches")
        return results

    def create_investigation_from_match(self, match: Dict, photo_path: str) -> str:
        """
        Create a new investigation from a photo match result.

        Returns the investigation ID.
        """
        from app import db
        from app.models import Investigation, SocialProfile

        investigation_id = uuid.uuid4().hex
        display_name = match.get('display_name', 'Unknown')

        investigation = Investigation(
            id=investigation_id,
            input_name=display_name,
            input_photo_path=photo_path,
            status='phase_1',
        )
        investigation.phase1_stats = {
            'search_type': 'photo',
            'search_started_at': datetime.now().isoformat(),
            'photo_match_score': match.get('similarity_score', 0),
        }

        db.session.add(investigation)

        # Create SocialProfile for the matched result
        sp = SocialProfile(
            investigation_id=investigation_id,
            platform=match.get('platform', 'vk'),
            platform_id=match.get('platform_id', match.get('username', '')),
            username=match.get('username'),
            profile_url=match.get('profile_url', ''),
            first_name=match.get('first_name', ''),
            last_name=match.get('last_name', ''),
            display_name=display_name,
            photo_url=match.get('photo_url', ''),
            city=match.get('city', ''),
            age=match.get('age'),
            face_match=True,
            face_similarity=match.get('similarity_score', 0) * 100,
            name_similarity=100.0,
            name_match=True,
        )
        sp.calculate_confidence()
        db.session.add(sp)
        db.session.commit()

        logger.info(f"Created investigation {investigation_id} from photo match: {display_name}")
        return investigation_id


# Singleton
photo_investigation = PhotoInvestigation()
