"""
Phase 2 Source Manager
======================
Orchestrates all Phase 2 data sources.

Auto-discovers source plugins from the sources/ directory,
runs them in parallel, deduplicates results, and cross-validates
data across sources for confidence boosting.
"""

import importlib
import inspect
import logging
import os
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Optional, Any

from .base_source import BaseSource, SourceResult, SourceTier, SourceType

logger = logging.getLogger(__name__)

# Directory containing source plugins
SOURCES_DIR = os.path.join(os.path.dirname(__file__), 'sources')
SOURCES_PACKAGE = 'app.services.phase2.sources'


class SourceManager:
    """
    Orchestrates all Phase 2 data sources.

    Features:
    - Auto-discovers source plugins from sources/ directory
    - Runs all available sources in parallel (ThreadPoolExecutor)
    - Deduplicates results (same email from 2 sources = merge, boost confidence)
    - Cross-validates data (phone found by breach DB + confirmed by GetContact)
    - Groups results by data_type for easy consumption
    - Provides source status dashboard for UI
    """

    def __init__(self, max_workers: int = 8, timeout: float = 30.0):
        """
        Initialize SourceManager.

        Args:
            max_workers: Max parallel source queries
            timeout: Overall timeout for all sources (seconds)
        """
        self.max_workers = max_workers
        self.timeout = timeout
        self.sources: List[BaseSource] = []
        self._discover_sources()

    def _discover_sources(self):
        """
        Auto-import all source modules from sources/ directory.
        Finds every class that inherits from BaseSource and instantiates it.
        """
        self.sources = []

        if not os.path.isdir(SOURCES_DIR):
            logger.warning(f"Sources directory not found: {SOURCES_DIR}")
            return

        for filename in sorted(os.listdir(SOURCES_DIR)):
            if not filename.endswith('.py') or filename.startswith('_'):
                continue

            module_name = filename[:-3]  # strip .py
            full_module = f"{SOURCES_PACKAGE}.{module_name}"

            try:
                module = importlib.import_module(full_module)

                # Find all BaseSource subclasses in the module
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (inspect.isclass(attr)
                            and issubclass(attr, BaseSource)
                            and attr is not BaseSource):
                        try:
                            instance = attr()
                            self.sources.append(instance)
                            logger.debug(
                                f"Registered source: {instance.name} "
                                f"(tier={instance.source_tier.name}, "
                                f"available={instance.is_available()})"
                            )
                        except Exception as e:
                            logger.warning(f"Failed to instantiate {attr_name}: {e}")

            except Exception as e:
                logger.warning(f"Failed to import source module {full_module}: {e}")

        logger.info(
            f"Discovered {len(self.sources)} sources: "
            f"{[s.name for s in self.sources]}"
        )

    def run_all(self, exclude_sources=None, **kwargs) -> Dict[str, List[SourceResult]]:
        """
        Run ALL available and enabled sources in parallel.

        Args:
            exclude_sources: Optional list of source names to skip
            **kwargs: Query parameters passed to each source:
                name: str — target's full name
                phone: str — known phone number
                email: str — known email address
                username: str — known username
                vk_id: str — VK profile ID
                photo_path: str — path to target photo

        Returns:
            Dict grouped by data_type:
            {
                "email": [SourceResult, ...],
                "phone": [SourceResult, ...],
                "profile": [SourceResult, ...],
                "identity": [SourceResult, ...],
            }
        """
        start_time = time.time()
        exclude_set = set(exclude_sources or [])

        # Filter to enabled + available sources
        active_sources = [
            s for s in self.sources
            if s.enabled and s.is_available() and s.name not in exclude_set
        ]

        if not active_sources:
            logger.warning("No active sources available")
            return {}

        logger.info(
            f"Running {len(active_sources)} sources: "
            f"{[s.name for s in active_sources]}"
        )

        all_results: List[SourceResult] = []

        # Run all sources in parallel
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_source = {
                executor.submit(source.query, **kwargs): source
                for source in active_sources
            }

            try:
                for future in as_completed(future_to_source, timeout=self.timeout):
                    source = future_to_source[future]
                    try:
                        results = future.result(timeout=5)
                        if results:
                            all_results.extend(results)
                            logger.info(
                                "Source %s: returned %d results",
                                source.name, len(results),
                            )
                    except Exception as e:
                        logger.warning("Source %s failed: %s", source.name, e)
            except TimeoutError:
                logger.warning("Source manager: some sources timed out (%ds)", self.timeout)
                for f in future_to_source:
                    f.cancel()

        # Deduplicate
        deduped = self._deduplicate(all_results)

        # Cross-validate
        validated = self._cross_validate(deduped)

        # Sort by confidence (highest first)
        validated.sort(key=lambda r: r.confidence, reverse=True)

        # Group by data_type
        grouped = self._group_by_type(validated)

        elapsed = time.time() - start_time
        total = sum(len(v) for v in grouped.values())
        logger.info(
            f"SourceManager complete: {total} results in {elapsed:.1f}s "
            f"(types: {', '.join(f'{k}={len(v)}' for k, v in grouped.items())})"
        )

        return grouped

    def run_tier(self, tier: SourceTier, **kwargs) -> Dict[str, List[SourceResult]]:
        """Run only sources of a specific tier."""
        original_enabled = {}
        try:
            # Temporarily disable sources not in the requested tier
            for source in self.sources:
                original_enabled[id(source)] = source.enabled
                if source.source_tier != tier:
                    source.enabled = False
            return self.run_all(**kwargs)
        finally:
            # Restore original enabled states
            for source in self.sources:
                source.enabled = original_enabled.get(id(source), True)

    def get_source_status(self) -> List[Dict[str, Any]]:
        """
        Get status of all registered sources.
        Used for the UI dashboard to show which sources are configured.
        """
        status = []
        for source in self.sources:
            info = source.get_info()
            status.append(info)

        # Sort: available first, then by tier (S > A > B > C)
        tier_order = {'S': 0, 'A': 1, 'B': 2, 'C': 3}
        status.sort(key=lambda s: (
            0 if s['available'] else 1,
            tier_order.get(s['tier_label'], 99)
        ))

        return status

    def _deduplicate(self, results: List[SourceResult]) -> List[SourceResult]:
        """
        Merge duplicate results from different sources.

        Rules:
        - Same data_type + value = same data point
        - Merge metadata, keep track of all contributing sources
        - Boost confidence when multiple sources agree
        - Keep the highest individual confidence as baseline
        """
        merged: Dict[str, SourceResult] = {}

        for result in results:
            key = f"{result.data_type}:{result.value.lower().strip()}"

            if key not in merged:
                # First time seeing this data point
                result.metadata['sources'] = [result.source_name]
                result.metadata['source_count'] = 1
                merged[key] = result
            else:
                existing = merged[key]

                # Track contributing sources
                sources_list = existing.metadata.get('sources', [])
                if result.source_name not in sources_list:
                    sources_list.append(result.source_name)
                existing.metadata['sources'] = sources_list
                existing.metadata['source_count'] = len(sources_list)

                # Boost confidence (multi-source corroboration)
                # Each additional source adds up to 0.15 confidence
                boost = min(0.15, (1.0 - existing.confidence) * 0.5)
                existing.confidence = min(1.0, existing.confidence + boost)

                # Keep higher tier
                tier_priority = {
                    SourceTier.S: 0, SourceTier.A: 1,
                    SourceTier.B: 2, SourceTier.C: 3
                }
                if tier_priority.get(result.source_tier, 99) < tier_priority.get(existing.source_tier, 99):
                    existing.source_tier = result.source_tier

                # Merge raw_data (keep both)
                for k, v in result.raw_data.items():
                    if k not in existing.raw_data:
                        existing.raw_data[k] = v

                # Merge metadata
                for k, v in result.metadata.items():
                    if k not in ('sources', 'source_count') and k not in existing.metadata:
                        existing.metadata[k] = v

        return list(merged.values())

    def _cross_validate(self, results: List[SourceResult]) -> List[SourceResult]:
        """
        Cross-validate results across data types.

        If a phone is found AND a name is found from the same breach record,
        the phone gets a confidence boost. If conflicting names are found
        for the same phone, confidence drops.
        """
        # Build lookup indexes
        phones = {r.value: r for r in results if r.data_type == 'phone'}
        emails = {r.value: r for r in results if r.data_type == 'email'}

        # If both phone and email come from Tier S (breach), mark as cross-validated
        for phone_result in phones.values():
            if phone_result.source_tier == SourceTier.S:
                for email_result in emails.values():
                    if email_result.source_tier == SourceTier.S:
                        # Both from breach sources — likely same person
                        phone_result.verified = True
                        email_result.verified = True
                        phone_result.metadata['cross_validated_with'] = 'email_breach'
                        email_result.metadata['cross_validated_with'] = 'phone_breach'

        # Multi-source confirmation
        for result in results:
            source_count = result.metadata.get('source_count', 1)
            if source_count >= 3:
                result.verified = True
                result.metadata['verified_reason'] = f'confirmed_by_{source_count}_sources'
            elif source_count >= 2 and result.confidence >= 0.7:
                result.verified = True
                result.metadata['verified_reason'] = 'dual_source_high_confidence'

        return results

    def _group_by_type(self, results: List[SourceResult]) -> Dict[str, List[SourceResult]]:
        """Group results by data_type."""
        grouped = defaultdict(list)
        for result in results:
            grouped[result.data_type].append(result)
        return dict(grouped)
