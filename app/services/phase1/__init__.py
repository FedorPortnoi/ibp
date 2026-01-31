"""
Phase 1 Services - Social Media Discovery
==========================================
Services for finding social media profiles by name and photo.

Буратино-style workflow:
1. Search by name (VK, OK, Telegram)
2. Search by photo (Yandex Images, search4faces)
3. Calculate confidence scores
4. Present profiles for user confirmation
"""

from app.services.phase1.vk_people_search import (
    VKPeopleSearch,
    vk_people_search,
    search_vk_people
)

from app.services.phase1.ok_people_search import (
    OKPeopleSearch,
    ok_people_search,
    search_ok_people
)

from app.services.phase1.telegram_people_search import (
    TelegramPeopleSearch,
    telegram_people_search,
    search_telegram_people
)

from app.services.phase1.face_search import (
    FaceSearchService,
    face_search_service,
    search_faces
)

__all__ = [
    # VK People Search
    'VKPeopleSearch',
    'vk_people_search',
    'search_vk_people',
    # OK People Search
    'OKPeopleSearch',
    'ok_people_search',
    'search_ok_people',
    # Telegram People Search
    'TelegramPeopleSearch',
    'telegram_people_search',
    'search_telegram_people',
    # Face Search
    'FaceSearchService',
    'face_search_service',
    'search_faces',
]
