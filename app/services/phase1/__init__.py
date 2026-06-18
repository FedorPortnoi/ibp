"""
Phase 1 Services - VK People Search (Buratino-style)
====================================================
Person-first investigation: Name → VK Search → Select Profile → Confirm

Primary service: BuratinoVKSearch
- Uses VK API (users.search) for accurate name-based discovery
- Demo mode fallback when no API token
"""

from app.services.phase1.buratino_vk_search import (
    BuratinoVKSearch,
    buratino_vk_search,
    VKProfileResult,
)

__all__ = [
    'BuratinoVKSearch',
    'buratino_vk_search',
    'VKProfileResult',
]
