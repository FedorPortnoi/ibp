"""
Phase 3 Services - Deep Investigation
=====================================
Business records, court cases, property lookup, text/video analysis.

Буратино-style workflow:
1. Search REAL business records (ЕГРЮЛ/ЕГРИП)
2. Search REAL court cases
3. Build social graph from confirmed profiles
4. Risk assessment
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
from .video_analyzer import (
    VideoAnalyzer,
    video_analyzer,
    VideoFrame,
    VideoMetadata,
    VideoAnalysisResult
)
from .fssp_search import (
    FSSPSearch,
    fssp_search,
    EnforcementProceeding
)
from .combined_search import (
    Phase3CombinedSearch,
    phase3_combined_search,
    Phase3Results,
    SocialConnection,
    RiskIndicator
)

__all__ = [
    # Business Registry
    'BusinessRegistrySearch',
    'business_registry_search',
    'BusinessRecord',
    # Court Search
    'CourtRecordSearch',
    'court_search',
    'CourtCase',
    # Geo Extractor
    'GeoExtractor',
    'geo_extractor',
    'LocationPoint',
    # Text Analyzer
    'TextAnalyzer',
    'text_analyzer',
    'TextAnalysisResult',
    # Video Analyzer
    'VideoAnalyzer',
    'video_analyzer',
    'VideoFrame',
    'VideoMetadata',
    'VideoAnalysisResult',
    # FSSP
    'FSSPSearch',
    'fssp_search',
    'EnforcementProceeding',
    # Combined Search (Orchestrator)
    'Phase3CombinedSearch',
    'phase3_combined_search',
    'Phase3Results',
    'SocialConnection',
    'RiskIndicator',
]
