"""
VK Search for Phase 1
=====================
Compatibility wrapper for the legacy combined-search call site.
"""

import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


def combined_search_and_save(
    investigation_id: str,
    query: str,
    city: Optional[str] = None,
    age_from: Optional[int] = None,
    age_to: Optional[int] = None,
) -> Dict[str, List[Dict]]:
    """
    Run VK search, save results, return a consistent result shape.

    Args:
        investigation_id: Investigation to save profiles to
        query: Full name to search
        city: Optional city filter
        age_from: Min age
        age_to: Max age
    Returns:
        Dict with 'vk' key containing saved profile dicts.
    """
    results = {'vk': []}

    # VK search
    try:
        from app.services.phase1.buratino_vk_search import buratino_vk_search
        results['vk'] = buratino_vk_search.search_and_save(
            investigation_id=investigation_id,
            query=query,
            city=city,
            age_from=age_from,
            age_to=age_to,
        )
        logger.info(f"Combined search: {len(results['vk'])} VK profiles for '{query}'")
    except Exception as e:
        logger.error(f"VK search failed in combined search: {e}")

    total = len(results['vk'])
    logger.info(f"Combined search: {total} total profiles for '{query}'")
    return results
