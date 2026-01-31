"""
Phase 3 Combined Search Orchestrator
=====================================
Coordinates all Phase 3 deep investigation services.

Буратино-style workflow:
1. Business registry search (ЕГРЮЛ/ЕГРИП)
2. Court records search (судебные дела)
3. Social graph analysis
4. Risk assessment
5. Text/media analysis from profiles
"""

import logging
from typing import List, Dict, Optional, Callable
from dataclasses import dataclass, field
import time

from .business_registry import BusinessRegistrySearch, BusinessRecord
from .court_search import CourtRecordSearch, CourtCase
from .geo_extractor import GeoExtractor, LocationPoint
from .text_analyzer import TextAnalyzer, TextAnalysisResult

logger = logging.getLogger(__name__)


@dataclass
class SocialConnection:
    """A social connection discovered from profiles."""
    name: str
    relationship: str  # friend, colleague, family, business_partner
    platform: str
    profile_url: str = ""
    confidence: str = "medium"

    def to_dict(self) -> Dict:
        return {
            'name': self.name,
            'relationship': self.relationship,
            'platform': self.platform,
            'profile_url': self.profile_url,
            'confidence': self.confidence
        }


@dataclass
class RiskIndicator:
    """A risk indicator found during investigation."""
    category: str  # legal, financial, reputational, security
    severity: str  # low, medium, high, critical
    description: str
    source: str
    details: str = ""

    def to_dict(self) -> Dict:
        return {
            'category': self.category,
            'severity': self.severity,
            'description': self.description,
            'source': self.source,
            'details': self.details
        }


@dataclass
class Phase3Results:
    """Complete results from Phase 3 deep investigation."""
    business_records: List[BusinessRecord] = field(default_factory=list)
    court_cases: List[CourtCase] = field(default_factory=list)
    social_connections: List[SocialConnection] = field(default_factory=list)
    locations: List[LocationPoint] = field(default_factory=list)
    risk_indicators: List[RiskIndicator] = field(default_factory=list)
    text_analysis: Optional[TextAnalysisResult] = None
    stats: Dict = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            'business_records': [r.to_dict() for r in self.business_records],
            'court_cases': [c.to_dict() for c in self.court_cases],
            'social_connections': [s.to_dict() for s in self.social_connections],
            'locations': [loc.__dict__ for loc in self.locations],
            'risk_indicators': [r.to_dict() for r in self.risk_indicators],
            'text_analysis': self.text_analysis.__dict__ if self.text_analysis else None,
            'stats': self.stats,
            'errors': self.errors
        }


class Phase3CombinedSearch:
    """
    Orchestrates all Phase 3 deep investigation services.

    Буратино-style approach:
    - Search REAL business records (not generated)
    - Search REAL court cases (not generated)
    - Build social graph from CONFIRMED profiles
    - Assess risks based on VERIFIED data
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.progress_callback: Optional[Callable] = None

        # Initialize services
        self.business_search = BusinessRegistrySearch()
        self.court_search = CourtRecordSearch()
        self.geo_extractor = GeoExtractor()
        self.text_analyzer = TextAnalyzer()

    def set_progress_callback(self, callback: Callable[[str, int], None]):
        """Set callback function for progress updates."""
        self.progress_callback = callback

    def _update_progress(self, step: str, percent: int):
        """Update progress if callback is set."""
        if self.progress_callback:
            try:
                self.progress_callback(step, percent)
            except Exception as e:
                self.logger.warning(f"Progress callback error: {e}")

    def investigate(
        self,
        target_name: str,
        confirmed_profiles: List[Dict],
        discovered_contacts: Dict,
        search_business: bool = True,
        search_courts: bool = True,
        build_social_graph: bool = True,
        analyze_text: bool = True
    ) -> Phase3Results:
        """
        Run full Phase 3 deep investigation.

        Args:
            target_name: Full name of target (Russian preferred)
            confirmed_profiles: Profiles confirmed in Phase 1
            discovered_contacts: Contacts from Phase 2 (phones, emails)
            search_business: Search business registries
            search_courts: Search court records
            build_social_graph: Analyze social connections
            analyze_text: Analyze text from profiles

        Returns:
            Phase3Results with all discovered information
        """
        start_time = time.time()

        self.logger.info("=" * 60)
        self.logger.info(f"PHASE 3 START: Target={target_name}")
        self.logger.info(f"Confirmed profiles: {len(confirmed_profiles)}")
        self.logger.info("=" * 60)

        business_records: List[BusinessRecord] = []
        court_cases: List[CourtCase] = []
        social_connections: List[SocialConnection] = []
        locations: List[LocationPoint] = []
        risk_indicators: List[RiskIndicator] = []
        text_analysis = None
        errors: List[str] = []

        # ===== STEP 1: Business Registry Search =====
        if search_business:
            self._update_progress("Searching business registries...", 5)
            self.logger.info("Step 1: Business registry search")

            try:
                business_results = self.business_search.search_by_name(
                    target_name,
                    search_directors=True,
                    search_founders=True,
                    limit=50
                )
                business_records.extend(business_results)
                self.logger.info(f"Found {len(business_results)} business records")

                # Add risk indicators for business records
                for record in business_results:
                    if record.status and 'ликвидир' in record.status.lower():
                        risk_indicators.append(RiskIndicator(
                            category="financial",
                            severity="medium",
                            description=f"Связан с ликвидированной компанией: {record.company_name}",
                            source="business_registry",
                            details=f"ИНН: {record.inn}, Статус: {record.status}"
                        ))

                    if record.role == "Директор":
                        # Being a director is neutral, but note it
                        pass

            except Exception as e:
                error_msg = f"Business registry search error: {str(e)}"
                errors.append(error_msg)
                self.logger.warning(error_msg)

        # ===== STEP 2: Court Records Search =====
        if search_courts:
            self._update_progress("Searching court records...", 25)
            self.logger.info("Step 2: Court records search")

            try:
                court_results = self.court_search.search_by_name(
                    target_name,
                    search_plaintiff=True,
                    search_defendant=True,
                    limit=50
                )
                court_cases.extend(court_results)
                self.logger.info(f"Found {len(court_results)} court cases")

                # Add risk indicators for court cases
                for case in court_results:
                    severity = "low"
                    if case.case_type == "уголовное":
                        severity = "high"
                    elif case.role == "ответчик":
                        severity = "medium"

                    if case.case_type == "уголовное" or case.role == "ответчик":
                        risk_indicators.append(RiskIndicator(
                            category="legal",
                            severity=severity,
                            description=f"Судебное дело: {case.case_number}",
                            source="court_records",
                            details=f"Роль: {case.role}, Тип: {case.case_type}, Суд: {case.court_name}"
                        ))

            except Exception as e:
                error_msg = f"Court records search error: {str(e)}"
                errors.append(error_msg)
                self.logger.warning(error_msg)

        # ===== STEP 3: Social Graph Analysis =====
        if build_social_graph and confirmed_profiles:
            self._update_progress("Building social graph...", 45)
            self.logger.info("Step 3: Social graph analysis")

            try:
                connections = self._build_social_graph(confirmed_profiles)
                social_connections.extend(connections)
                self.logger.info(f"Found {len(connections)} social connections")

            except Exception as e:
                error_msg = f"Social graph error: {str(e)}"
                errors.append(error_msg)
                self.logger.warning(error_msg)

        # ===== STEP 4: Location Extraction =====
        self._update_progress("Extracting locations...", 65)
        self.logger.info("Step 4: Location extraction")

        try:
            # Extract locations from business records
            for record in business_records:
                if record.address:
                    loc = self.geo_extractor.extract_from_text(record.address)
                    if loc:
                        locations.extend(loc)

            # Extract from profile bios
            for profile in confirmed_profiles:
                bio = profile.get('bio', '') or profile.get('description', '')
                if bio:
                    loc = self.geo_extractor.extract_from_text(bio)
                    if loc:
                        locations.extend(loc)

            # Deduplicate locations
            seen = set()
            unique_locations = []
            for loc in locations:
                key = f"{loc.city}_{loc.region}"
                if key not in seen:
                    seen.add(key)
                    unique_locations.append(loc)
            locations = unique_locations

            self.logger.info(f"Extracted {len(locations)} unique locations")

        except Exception as e:
            error_msg = f"Location extraction error: {str(e)}"
            errors.append(error_msg)
            self.logger.warning(error_msg)

        # ===== STEP 5: Text Analysis =====
        if analyze_text and confirmed_profiles:
            self._update_progress("Analyzing profile text...", 80)
            self.logger.info("Step 5: Text analysis")

            try:
                # Combine all bio text
                combined_text = ""
                for profile in confirmed_profiles:
                    bio = profile.get('bio', '') or profile.get('description', '')
                    if bio:
                        combined_text += f"\n{bio}"

                if combined_text.strip():
                    text_analysis = self.text_analyzer.analyze(combined_text)
                    self.logger.info(f"Text analysis complete: {len(combined_text)} chars")

                    # Add risk indicators from text analysis
                    if text_analysis and text_analysis.keywords:
                        risk_keywords = ['долг', 'кредит', 'суд', 'банкрот', 'розыск']
                        for keyword in text_analysis.keywords:
                            if any(rk in keyword.lower() for rk in risk_keywords):
                                risk_indicators.append(RiskIndicator(
                                    category="reputational",
                                    severity="low",
                                    description=f"Ключевое слово в профиле: {keyword}",
                                    source="text_analysis"
                                ))

            except Exception as e:
                error_msg = f"Text analysis error: {str(e)}"
                errors.append(error_msg)
                self.logger.warning(error_msg)

        # ===== STEP 6: Risk Assessment =====
        self._update_progress("Assessing risks...", 90)
        self.logger.info("Step 6: Risk assessment")

        # Calculate overall risk
        high_risks = len([r for r in risk_indicators if r.severity == "high"])
        medium_risks = len([r for r in risk_indicators if r.severity == "medium"])

        overall_risk = "low"
        if high_risks > 0:
            overall_risk = "high"
        elif medium_risks >= 2:
            overall_risk = "medium"

        # ===== Calculate Stats =====
        elapsed_time = time.time() - start_time
        stats = {
            'business_records_found': len(business_records),
            'court_cases_found': len(court_cases),
            'social_connections_found': len(social_connections),
            'locations_extracted': len(locations),
            'risk_indicators_found': len(risk_indicators),
            'overall_risk': overall_risk,
            'high_risks': high_risks,
            'medium_risks': medium_risks,
            'search_time': f"{elapsed_time:.1f}s",
            'errors_count': len(errors)
        }

        self._update_progress("Complete!", 100)

        self.logger.info("=" * 60)
        self.logger.info("PHASE 3 RESULTS:")
        self.logger.info(f"  Business records: {len(business_records)}")
        self.logger.info(f"  Court cases: {len(court_cases)}")
        self.logger.info(f"  Social connections: {len(social_connections)}")
        self.logger.info(f"  Risk indicators: {len(risk_indicators)}")
        self.logger.info(f"  Overall risk: {overall_risk}")
        self.logger.info(f"  Time: {elapsed_time:.1f}s")
        self.logger.info("=" * 60)

        return Phase3Results(
            business_records=business_records,
            court_cases=court_cases,
            social_connections=social_connections,
            locations=locations,
            risk_indicators=risk_indicators,
            text_analysis=text_analysis,
            stats=stats,
            errors=errors
        )

    def _build_social_graph(self, profiles: List[Dict]) -> List[SocialConnection]:
        """Build social graph from profile connections."""
        connections = []

        for profile in profiles:
            platform = profile.get('platform', '').lower()

            # Extract friends/followers if available
            friends = profile.get('friends', []) or []
            followers = profile.get('followers', []) or []

            for friend in friends[:20]:  # Limit to avoid overload
                if isinstance(friend, dict):
                    name = friend.get('name', '') or friend.get('display_name', '')
                    url = friend.get('url', '') or friend.get('profile_url', '')
                else:
                    name = str(friend)
                    url = ''

                if name:
                    connections.append(SocialConnection(
                        name=name,
                        relationship="friend",
                        platform=platform,
                        profile_url=url
                    ))

            # Extract tagged people
            tags = profile.get('tags', []) or profile.get('mentions', [])
            for tag in tags[:10]:
                if isinstance(tag, dict):
                    name = tag.get('name', '')
                    url = tag.get('url', '')
                else:
                    name = str(tag)
                    url = ''

                if name:
                    connections.append(SocialConnection(
                        name=name,
                        relationship="mentioned",
                        platform=platform,
                        profile_url=url,
                        confidence="low"
                    ))

        # Deduplicate
        seen = set()
        unique = []
        for conn in connections:
            key = f"{conn.name.lower()}_{conn.platform}"
            if key not in seen:
                seen.add(key)
                unique.append(conn)

        return unique


# Singleton instance
phase3_combined_search = Phase3CombinedSearch()
