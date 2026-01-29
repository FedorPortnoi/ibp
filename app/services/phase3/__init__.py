"""
Phase 3 Services - Deep Investigation
=====================================
Business records, court cases, property lookup.
"""

from .business_registry import (
    BusinessRegistrySearch,
    business_registry_search,
    BusinessRecord
)
from .court_search import (
    CourtRecordSearch,
    court_search,
    CourtCase
)
from .geo_extractor import (
    GeoExtractor,
    geo_extractor,
    LocationPoint
)
from .text_analyzer import (
    TextAnalyzer,
    text_analyzer,
    TextAnalysisResult
)

__all__ = [
    'BusinessRegistrySearch',
    'business_registry_search',
    'BusinessRecord',
    'CourtRecordSearch',
    'court_search',
    'CourtCase',
    'GeoExtractor',
    'geo_extractor',
    'LocationPoint',
    'TextAnalyzer',
    'text_analyzer',
    'TextAnalysisResult',
]
