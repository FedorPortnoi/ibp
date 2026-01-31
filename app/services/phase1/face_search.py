"""
Face Search Service for Phase 1
================================
Combines facial recognition services to find profiles by face.

Services integrated:
- search4faces.com (312M+ faces from VK/OK)
- Yandex Images reverse search

Features:
- Search by photo
- Cross-reference with name search results
- Calculate confidence scores
- Prioritize face matches

Based on Буратино research Section 4.1 - Photo → Profile Discovery
"""

import logging
import os
from typing import List, Dict, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class FaceSearchResult:
    """Result from face search."""
    platform: str
    url: str
    username: str = ""
    display_name: str = ""
    photo_url: Optional[str] = None
    face_similarity: float = 0.0
    face_match: bool = False
    name_similarity: float = 0.0
    name_match: bool = False
    source: str = "face_search"
    confidence_score: float = 0.0
    confidence_level: str = "uncertain"


class FaceSearchService:
    """
    Unified face search service for Phase 1.

    Combines multiple facial recognition sources:
    1. search4faces.com - VK/OK face database
    2. Yandex Images - Reverse image search

    Cross-references results with name search for higher confidence.
    """

    def __init__(self):
        self._search4faces_available = None
        self._yandex_available = None

    def search_by_photo(
        self,
        photo_path: str,
        target_name: str = None,
        limit: int = 20
    ) -> List[Dict]:
        """
        Search for profiles by face.

        Args:
            photo_path: Path to target's photo
            target_name: Target's name for cross-referencing
            limit: Maximum results

        Returns:
            List of profile dicts with confidence scores
        """
        logger.info(f"Face search starting: photo={photo_path}, name={target_name}")

        if not photo_path or not os.path.exists(photo_path):
            logger.warning(f"Photo not found: {photo_path}")
            return []

        results = []

        # 1. Search with search4faces
        s4f_results = self._search_search4faces(photo_path, limit)
        results.extend(s4f_results)
        logger.info(f"search4faces found {len(s4f_results)} profiles")

        # 2. Search with Yandex Images (already done in combined_search, but we can enhance)
        yandex_results = self._search_yandex(photo_path, limit)
        results.extend(yandex_results)
        logger.info(f"Yandex Images found {len(yandex_results)} profiles")

        # 3. Deduplicate
        results = self._deduplicate(results)

        # 4. Calculate name similarity if target_name provided
        if target_name:
            results = self._calculate_name_similarity(results, target_name)

        # 5. Calculate confidence scores
        for r in results:
            self._calculate_confidence(r)

        # 6. Sort by confidence
        results.sort(key=lambda x: x.get('confidence_score', 0), reverse=True)

        logger.info(f"Face search complete: {len(results)} profiles")
        return results[:limit]

    def _search_search4faces(self, photo_path: str, limit: int) -> List[Dict]:
        """Search search4faces.com databases."""
        results = []

        try:
            from app.services.phase2.search4faces_service import search_all_databases

            matches = search_all_databases(
                image_path=photo_path,
                max_results_per_db=limit
            )

            for match in matches:
                results.append({
                    'platform': match.platform.upper() if match.platform else 'VK',
                    'url': match.profile_url,
                    'username': match.username or '',
                    'display_name': match.name or '',
                    'photo_url': match.thumbnail_url,
                    'face_similarity': match.similarity_score or 75.0,  # Default high for face match
                    'face_match': True,
                    'source': 'search4faces',
                    'exists': True,
                })

        except ImportError:
            logger.warning("search4faces_service not available")
        except Exception as e:
            logger.error(f"search4faces error: {e}")

        return results

    def _search_yandex(self, photo_path: str, limit: int) -> List[Dict]:
        """Search Yandex Images for social profiles."""
        results = []

        try:
            from app.services.yandex_image_search import yandex_reverse_image_search

            matches = yandex_reverse_image_search(photo_path)

            for match in matches:
                url = match.get('url', '')

                # Filter to only VK/OK/Telegram
                if 'vk.com' not in url.lower() and 'ok.ru' not in url.lower() and 't.me' not in url.lower():
                    continue

                # Extract username from URL
                username = self._extract_username(url)

                results.append({
                    'platform': match.get('platform', 'VK'),
                    'url': url,
                    'username': username,
                    'display_name': match.get('title', ''),
                    'photo_url': None,
                    'face_similarity': 70.0,  # Default for Yandex (image match, not face)
                    'face_match': True,
                    'source': 'yandex_images',
                    'exists': True,
                })

        except ImportError:
            logger.warning("yandex_image_search not available")
        except Exception as e:
            logger.error(f"Yandex search error: {e}")

        return results[:limit]

    def _extract_username(self, url: str) -> str:
        """Extract username from profile URL."""
        import re

        patterns = [
            r'vk\.com/((?:id)?[a-zA-Z0-9_.]+)',
            r'ok\.ru/(?:profile/)?([a-zA-Z0-9_.]+)',
            r't\.me/([a-zA-Z0-9_.]+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)

        return ""

    def _deduplicate(self, results: List[Dict]) -> List[Dict]:
        """Remove duplicate URLs."""
        seen = set()
        unique = []

        for r in results:
            url = r.get('url', '').lower().rstrip('/')
            if url and url not in seen:
                seen.add(url)
                unique.append(r)

        return unique

    def _calculate_name_similarity(self, results: List[Dict], target_name: str) -> List[Dict]:
        """Calculate name similarity for each result."""
        from difflib import SequenceMatcher

        target_lower = target_name.lower().strip()
        target_parts = target_lower.split()

        for r in results:
            display_name = r.get('display_name', '').lower().strip()

            if not display_name:
                r['name_similarity'] = 0.0
                r['name_match'] = False
                continue

            # Direct comparison
            direct = SequenceMatcher(None, target_lower, display_name).ratio() * 100

            # Part-based comparison
            found_parts = display_name.split()
            matches = 0
            for tp in target_parts:
                for fp in found_parts:
                    if tp in fp or fp in tp:
                        matches += 1
                        break
                    if len(tp) > 3 and len(fp) > 3:
                        if SequenceMatcher(None, tp, fp).ratio() > 0.8:
                            matches += 1
                            break

            part_score = (matches / len(target_parts)) * 100 if target_parts else 0

            similarity = max(direct, part_score)
            r['name_similarity'] = round(similarity, 1)
            r['name_match'] = similarity > 50

        return results

    def _calculate_confidence(self, result: Dict) -> None:
        """Calculate confidence score for a result."""
        score = 0.0

        # Face match is strong indicator (50 points max)
        if result.get('face_match', False):
            face_sim = result.get('face_similarity', 0)
            score += min(50.0, face_sim / 2)

        # Name match (30 points max)
        if result.get('name_match', False):
            name_sim = result.get('name_similarity', 0)
            score += min(30.0, name_sim * 0.3)

        # Source bonus
        source = result.get('source', '').lower()
        if 'search4faces' in source:
            score += 10.0  # Dedicated face search is more reliable
        elif 'yandex' in source:
            score += 5.0

        # Has photo bonus
        if result.get('photo_url'):
            score += 5.0

        result['confidence_score'] = round(min(100.0, score), 1)

        # Determine level
        if score >= 70 or (result.get('face_match') and result.get('name_match')):
            result['confidence_level'] = 'high'
        elif score >= 40 or result.get('face_match'):
            result['confidence_level'] = 'medium'
        elif score >= 20:
            result['confidence_level'] = 'low'
        else:
            result['confidence_level'] = 'uncertain'


def search_faces(
    photo_path: str,
    target_name: str = None,
    limit: int = 20
) -> List[Dict]:
    """
    Convenience function to search by face.

    Args:
        photo_path: Path to target's photo
        target_name: Target's name for cross-referencing
        limit: Maximum results

    Returns:
        List of profile dicts with confidence scores
    """
    service = FaceSearchService()
    return service.search_by_photo(photo_path, target_name, limit)


# Singleton instance
face_search_service = FaceSearchService()
