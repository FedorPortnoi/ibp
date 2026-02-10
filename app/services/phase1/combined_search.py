"""
Combined VK + OK Search for Phase 1
====================================
Wraps both VK People Search and OK People Search into a single call.
Used by Phase 1 routes to run both searches and merge results.
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
    vk_count: int = 50,
    ok_count: int = 20,
) -> Dict[str, List[Dict]]:
    """
    Run both VK and OK search, save results, return combined.

    Args:
        investigation_id: Investigation to save profiles to
        query: Full name to search
        city: Optional city filter
        age_from: Min age
        age_to: Max age
        vk_count: Max VK results
        ok_count: Max OK results

    Returns:
        Dict with 'vk' and 'ok' keys, each containing list of saved profile dicts
    """
    results = {'vk': [], 'ok': []}

    # VK search
    try:
        from app.services.phase1.buratino_vk_search import buratino_vk_search
        results['vk'] = buratino_vk_search.search_and_save(
            investigation_id=investigation_id,
            query=query,
            city=city,
            age_from=age_from,
            age_to=age_to,
            count=vk_count,
        )
        logger.info(f"Combined search: {len(results['vk'])} VK profiles for '{query}'")
    except Exception as e:
        logger.error(f"VK search failed in combined search: {e}")

    # OK search
    try:
        from app.services.phase1.ok_search_integration import ok_search_integration
        results['ok'] = ok_search_integration.search_and_save(
            investigation_id=investigation_id,
            query=query,
            city=city,
            age_from=age_from,
            age_to=age_to,
            count=ok_count,
        )
        logger.info(f"Combined search: {len(results['ok'])} OK profiles for '{query}'")
    except Exception as e:
        logger.warning(f"OK search failed in combined search: {e}")

    total = len(results['vk']) + len(results['ok'])
    logger.info(f"Combined search: {total} total profiles for '{query}'")
    return results
