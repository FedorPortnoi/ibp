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

__all__ = [
    'VKPeopleSearch',
    'vk_people_search',
    'search_vk_people',
]
