"""
Research Orchestrator - Coordinates all Phase 4 search and analysis.
Agent 1 - Final Integration Agent

Workflow:
1. Search all platforms in parallel (VK, OK, Telegram)
2. Merge similar profiles using EntityResolver
3. Analyze connections using ConnectionAnalyzer
4. Return unified results

Platform Integration:
- VK: Uses username generation + checking (app.services.vk_search)
- OK: Uses name-based people search (phase4.ok_people_search)
- Telegram: Uses name-based search (phase4.telegram_search)
"""
import logging
import time
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError

logger = logging.getLogger(__name__)


class ResearchOrchestrator:
    """
    Orchestrates multi-platform OSINT search and analysis.

    Integrates:
    - VK Search (username-based checking)
    - OK People Search (name-based)
    - Telegram Search (name-based)
    - Entity Resolution (profile merging)
    - Connection Analysis (relationship discovery)
    - Username Generator (for VK)
    """

    def __init__(self):
        # Lazy load modules to avoid import errors during testing
        self._vk = None
        self._tg = None
        self._ok = None
        self._resolver = None
        self._analyzer = None
        self._username_gen = None

    @property
    def vk(self):
        """VK username checker (username-based)."""
        if self._vk is None:
            from app.services.vk_search import check_vk_usernames
            self._vk = check_vk_usernames
        return self._vk

    @property
    def tg(self):
        """Telegram search service (name-based)."""
        if self._tg is None:
            from app.services.phase4.telegram_search import telegram_search
            self._tg = telegram_search
        return self._tg

    @property
    def ok(self):
        """OK (Odnoklassniki) people search (name-based)."""
        if self._ok is None:
            from app.services.phase4.ok_people_search import ok_people_search
            self._ok = ok_people_search
        return self._ok

    @property
    def resolver(self):
        if self._resolver is None:
            from app.services.phase4.entity_resolver import entity_resolver
            self._resolver = entity_resolver
        return self._resolver

    @property
    def analyzer(self):
        if self._analyzer is None:
            from app.services.phase4.connection_analyzer import connection_analyzer
            self._analyzer = connection_analyzer
        return self._analyzer

    @property
    def username_generator(self):
        if self._username_gen is None:
            from app.services.username_generator import generate_usernames
            self._username_gen = generate_usernames
        return self._username_gen

    def search_person(
        self,
        name: str,
        city: str = None,
        age_from: int = None,
        age_to: int = None,
        birth_year: int = None,
        platforms: List[str] = None,
        investigation_id: int = None,
        timeout: int = 60,
        max_usernames: int = 30
    ) -> Dict:
        """
        Search for a person across all Russian social platforms.

        Args:
            name: Full name (Russian or English)
            city: City filter for OK/VK
            age_from: Minimum age
            age_to: Maximum age
            birth_year: Optional birth year for better username generation
            platforms: List of platforms ['vk', 'ok', 'telegram']
            investigation_id: ID for storing connections
            timeout: Max seconds for search
            max_usernames: Max usernames to check for VK

        Returns:
            Dict with profiles, merged_identities, connections, stats
        """
        start_time = time.time()

        if platforms is None:
            platforms = ['vk', 'ok', 'telegram']

        logger.info("=" * 60)
        logger.info("RESEARCH ORCHESTRATOR - STARTING SEARCH")
        logger.info("=" * 60)
        logger.info(f"Name: {name}")
        logger.info(f"City: {city}")
        logger.info(f"Age: {age_from}-{age_to}")
        logger.info(f"Platforms: {platforms}")

        results = {
            'profiles': [],
            'merged_identities': [],
            'connections': [],
            'stats': {
                'platforms_searched': platforms,
                'total_found': 0,
                'by_platform': {},
                'search_time': 0,
                'merges_performed': 0,
                'connections_found': 0,
                'errors': []
            }
        }

        # Parse name for multi-platform search
        name_parts = name.strip().split()
        first_name = name_parts[0] if name_parts else name
        last_name = name_parts[-1] if len(name_parts) > 1 else ''

        # Generate usernames for VK (username-based search)
        usernames = []
        if 'vk' in [p.lower() for p in platforms]:
            try:
                usernames = self.username_generator(name, birth_year=birth_year, max_results=max_usernames)
                logger.info(f"Generated {len(usernames)} usernames for VK search")
            except Exception as e:
                logger.warning(f"Username generation failed: {e}")
                results['stats']['errors'].append(f"Username generation: {str(e)}")

        # Step 1: Search all platforms in parallel
        logger.info("-" * 40)
        logger.info("STEP 1: Parallel Platform Search")
        logger.info("-" * 40)

        all_profiles = self._search_all_platforms(
            name=name,
            first_name=first_name,
            last_name=last_name,
            usernames=usernames,
            city=city,
            age_from=age_from,
            age_to=age_to,
            platforms=platforms,
            timeout=timeout
        )

        results['profiles'] = all_profiles
        results['stats']['total_found'] = len(all_profiles)

        # Count by platform
        for profile in all_profiles:
            platform = profile.get('platform', 'unknown')
            results['stats']['by_platform'][platform] = \
                results['stats']['by_platform'].get(platform, 0) + 1

        logger.info(f"Total profiles found: {len(all_profiles)}")
        for platform, count in results['stats']['by_platform'].items():
            logger.info(f"  {platform}: {count}")

        # Step 2: Merge similar profiles
        if len(all_profiles) > 1:
            logger.info("-" * 40)
            logger.info("STEP 2: Entity Resolution (Merging)")
            logger.info("-" * 40)

            merged = self._merge_similar_profiles(all_profiles)
            results['merged_identities'] = merged
            results['stats']['merges_performed'] = len([
                m for m in merged
                if isinstance(m, dict) and m.get('merge_confidence', 0) > 0
            ])

            logger.info(f"Merged into {len(merged)} identities")
        else:
            results['merged_identities'] = all_profiles

        # Step 3: Analyze connections
        if investigation_id and all_profiles:
            logger.info("-" * 40)
            logger.info("STEP 3: Connection Analysis")
            logger.info("-" * 40)

            try:
                connections = self.analyzer.analyze_profiles(all_profiles, investigation_id)

                # Try to save to database
                try:
                    from app import db
                    for conn in connections:
                        if hasattr(conn, 'id'):  # It's a model instance
                            db.session.add(conn)
                    db.session.commit()
                    logger.info(f"Saved {len(connections)} connections to database")
                except Exception as e:
                    logger.warning(f"Could not save to database: {e}")

                # Convert to dicts for response
                results['connections'] = [
                    c.to_dict() if hasattr(c, 'to_dict') else c
                    for c in connections
                ]
                results['stats']['connections_found'] = len(connections)

            except Exception as e:
                logger.error(f"Connection analysis failed: {e}")
                results['stats']['errors'].append(f"Connection analysis: {str(e)}")

        # Final stats
        results['stats']['search_time'] = round(time.time() - start_time, 2)

        logger.info("=" * 60)
        logger.info("SEARCH COMPLETE")
        logger.info(f"Total: {results['stats']['total_found']} profiles")
        logger.info(f"Time: {results['stats']['search_time']}s")
        logger.info("=" * 60)

        return results

    def _search_all_platforms(
        self,
        name: str,
        first_name: str,
        last_name: str,
        usernames: List[str],
        city: str,
        age_from: int,
        age_to: int,
        platforms: List[str],
        timeout: int
    ) -> List[Dict]:
        """Search all platforms in parallel with timeout."""
        all_profiles = []

        # Define search functions for each platform
        def search_vk():
            """VK uses username-based search."""
            try:
                if not usernames:
                    logger.info("VK: No usernames to check")
                    return []
                logger.info(f"VK: Checking {len(usernames)} usernames...")
                results = self.vk(usernames)
                logger.info(f"VK: Found {len(results)} profiles")
                return results
            except Exception as e:
                logger.error(f"VK search error: {e}")
                return []

        def search_ok():
            """OK uses name-based people search."""
            try:
                logger.info(f"OK: Searching for '{name}'...")
                results = self.ok.search_people(
                    name=name,
                    city=city,
                    age_from=age_from,
                    age_to=age_to,
                    limit=20
                )
                logger.info(f"OK: Found {len(results)} profiles")
                return results
            except Exception as e:
                logger.error(f"OK search error: {e}")
                return []

        def search_telegram():
            """Telegram uses name-based search."""
            try:
                logger.info(f"Telegram: Searching for '{first_name} {last_name}'...")
                results = self.tg.search_by_name(
                    first_name=first_name,
                    last_name=last_name,
                    check_limit=15
                )
                logger.info(f"Telegram: Found {len(results)} profiles")
                return results
            except Exception as e:
                logger.error(f"Telegram search error: {e}")
                return []

        search_funcs = {
            'vk': search_vk,
            'ok': search_ok,
            'telegram': search_telegram,
        }

        # Execute searches in parallel
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {}
            for platform in platforms:
                if platform.lower() in search_funcs:
                    future = executor.submit(search_funcs[platform.lower()])
                    futures[future] = platform

            # Collect results with timeout
            for future in as_completed(futures, timeout=timeout):
                platform = futures[future]
                try:
                    profiles = future.result(timeout=5)
                    if profiles:
                        all_profiles.extend(profiles)
                except TimeoutError:
                    logger.warning(f"{platform.upper()}: Timed out")
                except Exception as e:
                    logger.error(f"{platform.upper()}: Error - {e}")

        return all_profiles

    def _merge_similar_profiles(self, profiles: List[Dict]) -> List[Dict]:
        """Group and merge profiles that likely belong to same person."""
        if len(profiles) <= 1:
            return profiles

        merged_groups = []
        used_indices = set()

        for i, profile_a in enumerate(profiles):
            if i in used_indices:
                continue

            # Find profiles that match this one
            group = [profile_a]
            used_indices.add(i)

            for j, profile_b in enumerate(profiles):
                if j in used_indices:
                    continue

                try:
                    score, evidence = self.resolver.calculate_match_score(profile_a, profile_b)

                    if score >= 0.4:  # 40% confidence threshold
                        group.append(profile_b)
                        used_indices.add(j)
                        logger.debug(
                            f"Merge candidates ({score:.0%}): "
                            f"{profile_a.get('display_name')} + {profile_b.get('display_name')}"
                        )
                except Exception as e:
                    logger.debug(f"Match score calculation failed: {e}")

            # Merge the group if multiple profiles
            if len(group) > 1:
                try:
                    merged = self.resolver.merge_profiles(group)
                    merged_groups.append(merged)
                except Exception as e:
                    logger.warning(f"Merge failed: {e}")
                    merged_groups.extend(group)
            else:
                merged_groups.append(profile_a)

        return merged_groups

    def quick_search(
        self,
        name: str,
        platforms: List[str] = None,
        max_usernames: int = 20
    ) -> List[Dict]:
        """
        Quick search without full analysis - just return profiles.
        """
        if platforms is None:
            platforms = ['vk', 'telegram']

        results = self.search_person(
            name=name,
            platforms=platforms,
            timeout=30,
            max_usernames=max_usernames
        )

        return results.get('profiles', [])

    def search_by_usernames(
        self,
        usernames: List[str],
        platforms: List[str] = None,
        timeout: int = 60
    ) -> Dict:
        """
        Search specific usernames across platforms (skip username generation).
        Only works for VK as OK/Telegram use name-based search.
        """
        start_time = time.time()

        if platforms is None:
            platforms = ['vk']

        logger.info(f"Searching {len(usernames)} usernames across {platforms}")

        all_profiles = []

        # VK username check
        if 'vk' in [p.lower() for p in platforms]:
            try:
                vk_results = self.vk(usernames)
                all_profiles.extend(vk_results)
            except Exception as e:
                logger.error(f"VK search failed: {e}")

        return {
            'profiles': all_profiles,
            'stats': {
                'total_found': len(all_profiles),
                'usernames_checked': len(usernames),
                'search_time': round(time.time() - start_time, 2)
            }
        }


# Singleton instance
research_orchestrator = ResearchOrchestrator()
