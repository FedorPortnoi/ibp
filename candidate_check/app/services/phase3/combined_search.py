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
    social_connections: List[SocialConnection] = field(default_factory=list)
    locations: List[LocationPoint] = field(default_factory=list)
    risk_indicators: List[RiskIndicator] = field(default_factory=list)
    text_analysis: Optional[TextAnalysisResult] = None
    manual_search_links: List[ManualSearchLink] = field(default_factory=list)
    stats: Dict = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            'business_records': [r.to_dict() for r in self.business_records],
            'court_cases': [c.to_dict() for c in self.court_cases],
            'enforcement_proceedings': [e.to_dict() for e in self.enforcement_proceedings],
            'social_connections': [s.to_dict() for s in self.social_connections],
            'locations': [loc.to_dict() if hasattr(loc, 'to_dict') else loc.__dict__ for loc in self.locations],
            'risk_indicators': [r.to_dict() for r in self.risk_indicators],
            'text_analysis': self.text_analysis.to_dict() if self.text_analysis else None,
            'manual_search_links': [l.to_dict() for l in self.manual_search_links],
            'stats': self.stats,
            'errors': self.errors
        }


class Phase3CombinedSearch:
    """
    Orchestrates all Phase 3 deep investigation services.

    Step flow:
    1 (0-25%):   Business Registry Search
    2 (25-40%):  FSSP Enforcement Proceedings
    3 (40-60%):  Court Records Search
    4 (60-75%):  Social Graph Analysis
    5 (75-90%):  Text Analysis
    6 (90-100%): Risk Assessment & Summary
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.progress_callback: Optional[Callable] = None
        self.business_search = BusinessRegistrySearch(timeout=25)
        self.court_search = CourtRecordSearch(timeout=25)
        self.fssp_search = FSSPSearch(timeout=25)
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
        """Run full Phase 3 deep investigation."""
        start_time = time.time()

        self.logger.info("=" * 60)
        self.logger.info(f"PHASE 3 START: Target={target_name}")
        self.logger.info(f"Confirmed profiles: {len(confirmed_profiles)}")
        self.logger.info("=" * 60)

        business_records: List[BusinessRecord] = []
        court_cases: List[CourtCase] = []
        enforcement_proceedings: List[EnforcementProceeding] = []
        social_connections: List[SocialConnection] = []
        locations: List[LocationPoint] = []
        risk_indicators: List[RiskIndicator] = []
        text_analysis = None
        manual_links: List[ManualSearchLink] = []
        errors: List[str] = []

        # ===== STEP 1 (0-25%): Business Registry Search =====
        if search_business:
            self._update_progress("Searching business registries (ЕГРЮЛ)...", 5)
            self.logger.info("Step 1: Business registry search")

            try:
                business_results = self.business_search.search_by_name(
                    target_name, search_directors=True, search_founders=True, limit=50
                )
                business_records.extend(business_results)
                self.logger.info(f"Found {len(business_results)} business records")

                # Risk indicators from business records
                director_count = sum(1 for r in business_results if r.role in ['Директор', 'director'])
                liquidated_count = sum(1 for r in business_results if 'ликвидир' in r.status.lower())

                if liquidated_count > 0:
                    risk_indicators.append(RiskIndicator(
                        category="financial",
                        severity="medium",
                        description=f"Связан с {liquidated_count} ликвидированными компаниями",
                        source="ЕГРЮЛ",
                        details=", ".join(r.company_name for r in business_results if 'ликвидир' in r.status.lower())[:200]
                    ))

                if director_count >= 5:
                    risk_indicators.append(RiskIndicator(
                        category="financial",
                        severity="medium",
                        description=f"Директор/руководитель в {director_count} компаниях (возможны подставные фирмы)",
                        source="ЕГРЮЛ"
                    ))

            except Exception as e:
                error_msg = f"Business registry search error: {str(e)}"
                errors.append(error_msg)
                self.logger.warning(error_msg)

            # Add business manual links
            for link in BusinessRegistrySearch.get_manual_search_urls(target_name):
                manual_links.append(ManualSearchLink(**link))

        # ===== STEP 2 (25-40%): FSSP Enforcement Proceedings =====
        self._update_progress("Searching enforcement proceedings (ФССП)...", 25)
        self.logger.info("Step 2: FSSP enforcement proceedings")

        try:
            fssp_results = self.fssp_search.search_by_full_name(target_name)
            enforcement_proceedings.extend(fssp_results)
            self.logger.info(f"Found {len(fssp_results)} enforcement proceedings")

            # Risk indicators from FSSP
            for proc in fssp_results:
                severity = "medium"
                try:
                    amount_val = float(proc.amount.replace(',', '.').replace(' ', ''))
                    if amount_val > 1000000:
                        severity = "high"
                except (ValueError, AttributeError):
                    pass

                risk_indicators.append(RiskIndicator(
                    category="financial",
                    severity=severity,
                    description=f"Исполнительное производство: {proc.debt_type or 'не указан тип'}",
                    source="ФССП",
                    details=f"Сумма: {proc.amount}, №{proc.proceeding_number}"
                ))

        except Exception as e:
            error_msg = f"FSSP search error: {str(e)}"
            errors.append(error_msg)
            self.logger.warning(error_msg)

        # Add FSSP manual link
        fssp_link = FSSPSearch.get_manual_search_url(target_name)
        manual_links.append(ManualSearchLink(
            name=fssp_link['name'],
            url=fssp_link['url'],
            description=fssp_link.get('description', '')
        ))

        # ===== STEP 3 (40-60%): Court Records Search =====
        if search_courts:
            self._update_progress("Searching court records...", 40)
            self.logger.info("Step 3: Court records search")

            try:
                court_results = self.court_search.search_by_name(
                    target_name, search_plaintiff=True, search_defendant=True, limit=50
                )
                court_cases.extend(court_results)
                self.logger.info(f"Found {len(court_results)} court cases")

                # Risk indicators from court cases
                for case in court_results:
                    if case.case_type == "уголовное":
                        risk_indicators.append(RiskIndicator(
                            category="legal",
                            severity="high",
                            description=f"Уголовное дело: {case.case_number}",
                            source="court_records",
                            details=f"Суд: {case.court_name}, Роль: {case.role}"
                        ))
                    elif case.role == "ответчик":
                        risk_indicators.append(RiskIndicator(
                            category="legal",
                            severity="medium",
                            description=f"Ответчик в деле: {case.case_number}",
                            source="court_records",
                            details=f"Тип: {case.case_type}, Суд: {case.court_name}"
                        ))

            except Exception as e:
                error_msg = f"Court records search error: {str(e)}"
                errors.append(error_msg)
                self.logger.warning(error_msg)

            # Add court manual links
            for link in CourtRecordSearch.get_manual_search_urls(target_name):
                manual_links.append(ManualSearchLink(**link))

        # ===== STEP 4 (60-75%): Social Graph Analysis =====
        if build_social_graph and confirmed_profiles:
            self._update_progress("Analyzing social connections...", 60)
            self.logger.info("Step 4: Social graph analysis")

            try:
                connections = self._build_social_graph(confirmed_profiles)
                social_connections.extend(connections)
                self.logger.info(f"Found {len(connections)} social connections")
            except Exception as e:
                error_msg = f"Social graph error: {str(e)}"
                errors.append(error_msg)
                self.logger.warning(error_msg)

        # ===== STEP 4b: Location Extraction =====
        self._update_progress("Extracting locations...", 70)

        try:
            for record in business_records:
                if record.address:
                    loc = self.geo_extractor.extract_from_text(record.address)
                    if loc:
                        locations.extend(loc)

            for profile in confirmed_profiles:
                bio = profile.get('bio', '') or profile.get('description', '')
                if bio:
                    loc = self.geo_extractor.extract_from_text(bio)
                    if loc:
                        locations.extend(loc)

            # Deduplicate
            seen = set()
            unique_locations = []
            for loc in locations:
                key = f"{loc.city}_{loc.latitude}_{loc.longitude}"
                if key not in seen:
                    seen.add(key)
                    unique_locations.append(loc)
            locations = unique_locations

        except Exception as e:
            errors.append(f"Location extraction error: {str(e)}")

        # ===== STEP 5 (75-90%): Text Analysis =====
        if analyze_text and confirmed_profiles:
            self._update_progress("Analyzing profile text...", 80)
            self.logger.info("Step 5: Text analysis")

            try:
                combined_text = ""
                for profile in confirmed_profiles:
                    bio = profile.get('bio', '') or profile.get('description', '')
                    if bio:
                        combined_text += f"\n{bio}"

                if combined_text.strip():
                    text_analysis = self.text_analyzer.analyze(combined_text)
                    self.logger.info(f"Text analysis complete: {len(combined_text)} chars")

                    if text_analysis and text_analysis.keywords:
                        risk_keywords = ['долг', 'кредит', 'суд', 'банкрот', 'розыск']
                        for kw, count in text_analysis.keywords:
                            if any(rk in kw.lower() for rk in risk_keywords):
                                risk_indicators.append(RiskIndicator(
                                    category="reputational",
                                    severity="low",
                                    description=f"Ключевое слово в профиле: {kw}",
                                    source="text_analysis"
                                ))

            except Exception as e:
                errors.append(f"Text analysis error: {str(e)}")

        # ===== STEP 6 (90-100%): Risk Assessment & Summary =====
        self._update_progress("Assessing risks...", 90)
        self.logger.info("Step 6: Risk assessment")

        # Calculate overall risk
        high_risks = sum(1 for r in risk_indicators if r.severity == "high")
        medium_risks = sum(1 for r in risk_indicators if r.severity == "medium")

        overall_risk = "low"
        if high_risks > 0:
            overall_risk = "high"
        elif medium_risks >= 2:
            overall_risk = "medium"
        elif medium_risks == 1:
            overall_risk = "medium"

        # Calculate stats
        elapsed_time = time.time() - start_time
        stats = {
            'business_records_found': len(business_records),
            'court_cases_found': len(court_cases),
            'enforcement_proceedings_found': len(enforcement_proceedings),
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
        self.logger.info(f"  FSSP proceedings: {len(enforcement_proceedings)}")
        self.logger.info(f"  Social connections: {len(social_connections)}")
        self.logger.info(f"  Risk indicators: {len(risk_indicators)}")
        self.logger.info(f"  Overall risk: {overall_risk}")
        self.logger.info(f"  Time: {elapsed_time:.1f}s")
        self.logger.info("=" * 60)

        return Phase3Results(
            business_records=business_records,
            court_cases=court_cases,
            enforcement_proceedings=enforcement_proceedings,
            social_connections=social_connections,
            locations=locations,
            risk_indicators=risk_indicators,
            text_analysis=text_analysis,
            manual_search_links=manual_links,
            stats=stats,
            errors=errors
        )

    def _build_social_graph(self, profiles: List[Dict]) -> List[SocialConnection]:
        """Build social graph from profile connections."""
        connections = []

        for profile in profiles:
            platform = profile.get('platform', '').lower()

            friends = profile.get('friends', []) or []
            for friend in friends[:20]:
                if isinstance(friend, dict):
                    name = friend.get('name', '') or friend.get('display_name', '')
                    url = friend.get('url', '') or friend.get('profile_url', '')
                else:
                    name = str(friend)
                    url = ''
                if name:
                    connections.append(SocialConnection(
                        name=name, relationship="friend", platform=platform, profile_url=url
                    ))

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
                        name=name, relationship="mentioned", platform=platform,
                        profile_url=url, confidence="low"
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
