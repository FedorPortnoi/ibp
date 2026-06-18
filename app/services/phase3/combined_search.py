"""
Phase 3 Combined Search Orchestrator
=====================================
Coordinates all Phase 3 deep investigation services.

Updated step flow:
1. Business Registry Search (nalog.ru EGRUL → Rusprofile fallback)
2. FSSP Enforcement Proceedings (if token configured)
3. Court Records (sudact.ru → fallback URLs)
4. Social Graph Analysis (from confirmed profiles)
5. Text Analysis (sentiment from posts/bio)
6. Risk Assessment & Summary + Manual Search Links
"""

import logging
from typing import List, Dict, Optional, Callable
from dataclasses import dataclass, field
from urllib.parse import quote
import time

from .business_registry import BusinessRegistrySearch, BusinessRecord
from .court_search import CourtRecordSearch, CourtCase
from .fssp_search import FSSPSearch, EnforcementProceeding
from .geo_extractor import GeoExtractor, LocationPoint
from .text_analyzer import TextAnalyzer, TextAnalysisResult

logger = logging.getLogger(__name__)


@dataclass
class ManualSearchLink:
    """A manual search link for user reference."""
    name: str
    url: str
    description: str = ""

    def to_dict(self) -> Dict:
        return {
            'name': self.name,
            'url': self.url,
            'description': self.description,
        }


@dataclass
class Phase3Results:
    """Complete results from Phase 3 deep investigation."""
    business_records: List[BusinessRecord] = field(default_factory=list)
    court_cases: List[CourtCase] = field(default_factory=list)
    enforcement_proceedings: List[EnforcementProceeding] = field(default_factory=list)
    locations: List[LocationPoint] = field(default_factory=list)
    text_analysis: Optional[TextAnalysisResult] = None
    manual_search_links: List[ManualSearchLink] = field(default_factory=list)
    stats: Dict = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            'business_records': [r.to_dict() for r in self.business_records],
            'court_cases': [c.to_dict() for c in self.court_cases],
            'enforcement_proceedings': [e.to_dict() for e in self.enforcement_proceedings],
            'locations': [loc.to_dict() if hasattr(loc, 'to_dict') else loc.__dict__ for loc in self.locations],
            'text_analysis': self.text_analysis.to_dict() if self.text_analysis else None,
            'manual_search_links': [l.to_dict() for l in self.manual_search_links],
            'stats': self.stats,
            'errors': self.errors
        }


