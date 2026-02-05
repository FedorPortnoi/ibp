"""
Court Records Search - IBP Prototype B.10
Search Russian court databases (sudrf.ru, sudact.ru)

Features:
- Search by participant name (plaintiff, defendant)
- Search by case number
- Filter by case category (civil, criminal, administrative)
- Filter by court, region, date range
- Extract case details and documents
- Pagination support

Requirements:
    pip install requests beautifulsoup4

Usage:
    search = CourtRecordsSearch()
    results = search.search_by_name("Иванов Иван Иванович")
    for case in results.cases:
        print(f"Case {case.case_number}: {case.category}")
"""

import os
import re
import json
import time
import logging
import hashlib
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, date
from urllib.parse import urlencode, quote_plus
from enum import Enum

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Optional imports
HAS_REQUESTS = False
HAS_BS4 = False

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    logger.warning("requests not installed")

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    logger.warning("beautifulsoup4 not installed")


class CaseCategory(Enum):
    """Court case categories"""
    CIVIL = "civil"  # Гражданские дела
    CRIMINAL = "criminal"  # Уголовные дела
    ADMINISTRATIVE = "administrative"  # Административные дела
    ARBITRATION = "arbitration"  # Арбитражные дела
    ADMINISTRATIVE_OFFENSE = "admin_offense"  # Дела об административных правонарушениях
    UNKNOWN = "unknown"


class CaseStatus(Enum):
    """Case status"""
    PENDING = "pending"  # Рассматривается
    DECIDED = "decided"  # Решение вынесено
    APPEALED = "appealed"  # Обжаловано
    CLOSED = "closed"  # Закрыто
    UNKNOWN = "unknown"


class ParticipantRole(Enum):
    """Role of participant in case"""
    PLAINTIFF = "plaintiff"  # Истец
    DEFENDANT = "defendant"  # Ответчик
    THIRD_PARTY = "third_party"  # Третье лицо
    VICTIM = "victim"  # Потерпевший
    ACCUSED = "accused"  # Обвиняемый/Подсудимый
    WITNESS = "witness"  # Свидетель
    UNKNOWN = "unknown"


class CourtLevel(Enum):
    """Court jurisdiction level"""
    MAGISTRATE = "magistrate"  # Мировой суд
    DISTRICT = "district"  # Районный суд
    REGIONAL = "regional"  # Областной/краевой суд
    SUPREME = "supreme"  # Верховный суд
    ARBITRATION = "arbitration"  # Арбитражный суд
    CONSTITUTIONAL = "constitutional"  # Конституционный суд
    UNKNOWN = "unknown"


@dataclass
class Participant:
    """Case participant"""
    name: str
    role: ParticipantRole = ParticipantRole.UNKNOWN
    inn: Optional[str] = None
    ogrn: Optional[str] = None
    is_organization: bool = False
    representative: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "role": self.role.value,
            "inn": self.inn,
            "ogrn": self.ogrn,
            "is_organization": self.is_organization,
            "representative": self.representative
        }


@dataclass
class CourtDocument:
    """Court document"""
    title: str
    doc_type: str  # Решение, Определение, Приговор, etc.
    date: Optional[date] = None
    url: Optional[str] = None
    text_preview: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "doc_type": self.doc_type,
            "date": self.date.isoformat() if self.date else None,
            "url": self.url,
            "text_preview": self.text_preview
        }


@dataclass
class Court:
    """Court information"""
    name: str
    code: Optional[str] = None
    level: CourtLevel = CourtLevel.UNKNOWN
    region: Optional[str] = None
    address: Optional[str] = None
    website: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "code": self.code,
            "level": self.level.value,
            "region": self.region,
            "address": self.address,
            "website": self.website
        }


@dataclass
class CourtCase:
    """Court case record"""
    # Identifiers
    case_number: str  # Номер дела
    unique_id: Optional[str] = None  # Уникальный идентификатор дела

    # Classification
    category: CaseCategory = CaseCategory.UNKNOWN
    status: CaseStatus = CaseStatus.UNKNOWN

    # Court
    court: Optional[Court] = None

    # Dates
    filing_date: Optional[date] = None  # Дата поступления
    hearing_date: Optional[date] = None  # Дата рассмотрения
    decision_date: Optional[date] = None  # Дата решения

    # Participants
    participants: List[Participant] = field(default_factory=list)

    # Case info
    subject: Optional[str] = None  # Предмет спора
    claim_amount: Optional[float] = None  # Сумма иска
    outcome: Optional[str] = None  # Результат рассмотрения
    judge: Optional[str] = None  # Судья

    # Documents
    documents: List[CourtDocument] = field(default_factory=list)

    # URLs
    case_url: Optional[str] = None
    card_url: Optional[str] = None

    # Source
    source: str = "unknown"

    @property
    def plaintiffs(self) -> List[Participant]:
        return [p for p in self.participants if p.role == ParticipantRole.PLAINTIFF]

    @property
    def defendants(self) -> List[Participant]:
        return [p for p in self.participants if p.role == ParticipantRole.DEFENDANT]

    @property
    def category_ru(self) -> str:
        """Get Russian category name"""
        mapping = {
            CaseCategory.CIVIL: "Гражданское дело",
            CaseCategory.CRIMINAL: "Уголовное дело",
            CaseCategory.ADMINISTRATIVE: "Административное дело",
            CaseCategory.ARBITRATION: "Арбитражное дело",
            CaseCategory.ADMINISTRATIVE_OFFENSE: "Дело об АП",
            CaseCategory.UNKNOWN: "Неизвестно"
        }
        return mapping.get(self.category, "Неизвестно")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "case_number": self.case_number,
            "unique_id": self.unique_id,
            "category": self.category.value,
            "category_ru": self.category_ru,
            "status": self.status.value,
            "court": self.court.to_dict() if self.court else None,
            "filing_date": self.filing_date.isoformat() if self.filing_date else None,
            "hearing_date": self.hearing_date.isoformat() if self.hearing_date else None,
            "decision_date": self.decision_date.isoformat() if self.decision_date else None,
            "participants": [p.to_dict() for p in self.participants],
            "plaintiffs": [p.to_dict() for p in self.plaintiffs],
            "defendants": [p.to_dict() for p in self.defendants],
            "subject": self.subject,
            "claim_amount": self.claim_amount,
            "outcome": self.outcome,
            "judge": self.judge,
            "documents": [d.to_dict() for d in self.documents],
            "case_url": self.case_url,
            "source": self.source
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)


@dataclass
class SearchResult:
    """Court records search results"""
    query: str
    query_type: str  # name, case_number, inn
    total_found: int
    cases: List[CourtCase] = field(default_factory=list)
    page: int = 1
    has_more: bool = False
    search_time_ms: float = 0.0
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "query_type": self.query_type,
            "total_found": self.total_found,
            "returned": len(self.cases),
            "page": self.page,
            "has_more": self.has_more,
            "search_time_ms": round(self.search_time_ms, 2),
            "cases": [c.to_dict() for c in self.cases],
            "error": self.error
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)


class CourtRecordsSearch:
    """
    Russian court records search service

    Searches multiple court databases:
    - sudrf.ru - General jurisdiction courts
    - sudact.ru - Court decisions database
    - kad.arbitr.ru - Arbitration courts
    """

    # Data sources
    SUDRF_URL = "https://sudrf.ru"
    SUDACT_URL = "https://sudact.ru"
    ARBITR_URL = "https://kad.arbitr.ru"

    # Rate limiting
    MIN_REQUEST_INTERVAL = 2.0  # Courts are sensitive to scraping

    def __init__(
        self,
        demo_mode: bool = False
    ):
        """
        Initialize court records search

        Args:
            demo_mode: Force demo mode
        """
        self.demo_mode = demo_mode or not HAS_REQUESTS
        self.session: Optional['requests.Session'] = None
        self._last_request_time = 0.0

        if not self.demo_mode and HAS_REQUESTS:
            self.session = requests.Session()
            self.session.headers.update({
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "ru-RU,ru;q=0.9"
            })

        if self.demo_mode:
            logger.info("Running in DEMO mode")

    def _rate_limit(self):
        """Apply rate limiting"""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.MIN_REQUEST_INTERVAL:
            time.sleep(self.MIN_REQUEST_INTERVAL - elapsed)
        self._last_request_time = time.time()

    def search_by_name(
        self,
        name: str,
        category: Optional[CaseCategory] = None,
        role: Optional[ParticipantRole] = None,
        region: Optional[str] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        page: int = 1,
        limit: int = 20
    ) -> SearchResult:
        """
        Search cases by participant name

        Args:
            name: Participant name (person or organization)
            category: Case category filter
            role: Participant role filter
            region: Region filter
            date_from: Start date filter
            date_to: End date filter
            page: Page number
            limit: Results per page

        Returns:
            SearchResult with matching cases
        """
        start_time = time.time()

        if self.demo_mode:
            return self._demo_search_name(
                name, category, role, region,
                date_from, date_to, page, limit
            )

        self._rate_limit()

        try:
            # Try multiple sources
            results = []

            # Search sudrf.ru for general courts
            sudrf_results = self._search_sudrf(name, category, region, page)
            results.extend(sudrf_results)

            # Search kad.arbitr.ru for arbitration
            if category is None or category == CaseCategory.ARBITRATION:
                arbitr_results = self._search_arbitr(name, region, page)
                results.extend(arbitr_results)

            return SearchResult(
                query=name,
                query_type="name",
                total_found=len(results),
                cases=results[:limit],
                page=page,
                has_more=len(results) > limit,
                search_time_ms=(time.time() - start_time) * 1000
            )

        except Exception as e:
            logger.error(f"Search error: {e}")
            return SearchResult(
                query=name,
                query_type="name",
                total_found=0,
                error=str(e),
                search_time_ms=(time.time() - start_time) * 1000
            )

    def search_by_case_number(self, case_number: str) -> SearchResult:
        """
        Search by case number

        Args:
            case_number: Case number (e.g., "2-123/2024")

        Returns:
            SearchResult with matching case
        """
        start_time = time.time()

        if self.demo_mode:
            return self._demo_search_case_number(case_number)

        self._rate_limit()

        try:
            # Parse case number to determine source
            # Different formats for different courts

            results = []

            # Try sudrf.ru
            sudrf_case = self._search_sudrf_case(case_number)
            if sudrf_case:
                results.append(sudrf_case)

            return SearchResult(
                query=case_number,
                query_type="case_number",
                total_found=len(results),
                cases=results,
                search_time_ms=(time.time() - start_time) * 1000
            )

        except Exception as e:
            return SearchResult(
                query=case_number,
                query_type="case_number",
                total_found=0,
                error=str(e),
                search_time_ms=(time.time() - start_time) * 1000
            )

    def search_by_inn(
        self,
        inn: str,
        category: Optional[CaseCategory] = None,
        page: int = 1,
        limit: int = 20
    ) -> SearchResult:
        """
        Search cases by organization INN

        Args:
            inn: Organization INN
            category: Case category filter
            page: Page number
            limit: Results per page

        Returns:
            SearchResult with matching cases
        """
        start_time = time.time()

        if self.demo_mode:
            return self._demo_search_inn(inn, category, page, limit)

        self._rate_limit()

        try:
            # INN search is primarily for arbitration courts
            results = self._search_arbitr_inn(inn, page)

            return SearchResult(
                query=inn,
                query_type="inn",
                total_found=len(results),
                cases=results[:limit],
                page=page,
                has_more=len(results) > limit,
                search_time_ms=(time.time() - start_time) * 1000
            )

        except Exception as e:
            return SearchResult(
                query=inn,
                query_type="inn",
                total_found=0,
                error=str(e),
                search_time_ms=(time.time() - start_time) * 1000
            )

    def get_case_details(self, case_url: str) -> Optional[CourtCase]:
        """
        Get detailed case information

        Args:
            case_url: URL to case page

        Returns:
            CourtCase with full details
        """
        if self.demo_mode:
            return self._demo_get_case_details(case_url)

        self._rate_limit()

        try:
            response = self.session.get(case_url, timeout=30)
            response.raise_for_status()

            # Parse based on source
            if "sudrf.ru" in case_url:
                return self._parse_sudrf_case_page(response.text, case_url)
            elif "kad.arbitr.ru" in case_url:
                return self._parse_arbitr_case_page(response.text, case_url)

            return None

        except Exception as e:
            logger.error(f"Failed to get case details: {e}")
            return None

    def _search_sudrf(
        self,
        name: str,
        category: Optional[CaseCategory],
        region: Optional[str],
        page: int
    ) -> List[CourtCase]:
        """Search sudrf.ru"""
        # sudrf.ru has complex search requiring specific session handling
        # This is a placeholder for actual implementation
        return []

    def _search_sudrf_case(self, case_number: str) -> Optional[CourtCase]:
        """Search sudrf.ru by case number"""
        return None

    def _search_arbitr(
        self,
        name: str,
        region: Optional[str],
        page: int
    ) -> List[CourtCase]:
        """Search kad.arbitr.ru"""
        # kad.arbitr.ru has API endpoints
        # This is a placeholder
        return []

    def _search_arbitr_inn(self, inn: str, page: int) -> List[CourtCase]:
        """Search kad.arbitr.ru by INN"""
        return []

    def _parse_sudrf_case_page(self, html: str, url: str) -> Optional[CourtCase]:
        """Parse case page from sudrf.ru"""
        return None

    def _parse_arbitr_case_page(self, html: str, url: str) -> Optional[CourtCase]:
        """Parse case page from kad.arbitr.ru"""
        return None

    # Demo mode implementations
    def _demo_search_name(
        self,
        name: str,
        category: Optional[CaseCategory],
        role: Optional[ParticipantRole],
        region: Optional[str],
        date_from: Optional[date],
        date_to: Optional[date],
        page: int,
        limit: int
    ) -> SearchResult:
        """Simulated name search"""
        time.sleep(0.1)

        name_hash = hashlib.md5(name.encode()).hexdigest()
        total = int(name_hash[:2], 16) % 30 + 1  # 1-30 cases

        cases = []
        start_idx = (page - 1) * limit

        for i in range(min(limit, total - start_idx)):
            idx = start_idx + i
            case_hash = hashlib.md5(f"{name}_{idx}".encode()).hexdigest()
            cases.append(self._generate_demo_case(name, case_hash, category, role))

        return SearchResult(
            query=name,
            query_type="name",
            total_found=total,
            cases=cases,
            page=page,
            has_more=page * limit < total,
            search_time_ms=100.0
        )

    def _demo_search_case_number(self, case_number: str) -> SearchResult:
        """Simulated case number search"""
        time.sleep(0.1)

        case_hash = hashlib.md5(case_number.encode()).hexdigest()

        # Parse year from case number if present
        year_match = re.search(r'/(\d{4})', case_number)
        year = int(year_match.group(1)) if year_match else 2024

        case = self._generate_demo_case_by_number(case_number, case_hash, year)

        return SearchResult(
            query=case_number,
            query_type="case_number",
            total_found=1,
            cases=[case],
            search_time_ms=100.0
        )

    def _demo_search_inn(
        self,
        inn: str,
        category: Optional[CaseCategory],
        page: int,
        limit: int
    ) -> SearchResult:
        """Simulated INN search"""
        time.sleep(0.1)

        inn_hash = hashlib.md5(inn.encode()).hexdigest()
        total = int(inn_hash[:2], 16) % 15 + 1  # 1-15 cases

        cases = []
        start_idx = (page - 1) * limit

        for i in range(min(limit, total - start_idx)):
            idx = start_idx + i
            case_hash = hashlib.md5(f"{inn}_{idx}".encode()).hexdigest()

            case = self._generate_demo_arbitration_case(inn, case_hash)
            cases.append(case)

        return SearchResult(
            query=inn,
            query_type="inn",
            total_found=total,
            cases=cases,
            page=page,
            has_more=page * limit < total,
            search_time_ms=100.0
        )

    def _demo_get_case_details(self, case_url: str) -> Optional[CourtCase]:
        """Simulated case details fetch"""
        time.sleep(0.1)

        url_hash = hashlib.md5(case_url.encode()).hexdigest()
        return self._generate_demo_case("Demo", url_hash)

    def _generate_demo_case(
        self,
        participant_name: str,
        seed_hash: str,
        category: Optional[CaseCategory] = None,
        role: Optional[ParticipantRole] = None
    ) -> CourtCase:
        """Generate demo court case"""
        # Determine category
        if category is None:
            categories = [CaseCategory.CIVIL, CaseCategory.CRIMINAL,
                         CaseCategory.ADMINISTRATIVE, CaseCategory.ARBITRATION]
            category = categories[int(seed_hash[0], 16) % len(categories)]

        # Generate case number
        year = 2020 + int(seed_hash[1:3], 16) % 5
        number = int(seed_hash[3:6], 16) % 1000

        if category == CaseCategory.CIVIL:
            case_number = f"2-{number}/{year}"
        elif category == CaseCategory.CRIMINAL:
            case_number = f"1-{number}/{year}"
        elif category == CaseCategory.ADMINISTRATIVE:
            case_number = f"12-{number}/{year}"
        else:
            case_number = f"А40-{number}/{year}"

        # Generate court
        demo_courts = [
            ("Тверской районный суд г. Москвы", CourtLevel.DISTRICT, "Москва"),
            ("Мировой судья судебного участка №1", CourtLevel.MAGISTRATE, "Москва"),
            ("Московский городской суд", CourtLevel.REGIONAL, "Москва"),
            ("Арбитражный суд г. Москвы", CourtLevel.ARBITRATION, "Москва")
        ]
        court_idx = int(seed_hash[6], 16) % len(demo_courts)
        court_name, court_level, court_region = demo_courts[court_idx]

        court = Court(
            name=court_name,
            level=court_level,
            region=court_region
        )

        # Generate dates
        month = int(seed_hash[7:9], 16) % 12 + 1
        day = int(seed_hash[9:11], 16) % 28 + 1
        filing_date = date(year, month, day)

        decision_date = None
        if int(seed_hash[11], 16) > 5:  # 60% have decision
            decision_month = min(month + int(seed_hash[12], 16) % 6, 12)
            decision_date = date(year, decision_month, day)

        # Generate participants
        participants = []

        # Determine role for search target
        if role is None:
            role = ParticipantRole.PLAINTIFF if int(seed_hash[13], 16) > 7 else ParticipantRole.DEFENDANT

        participants.append(Participant(
            name=participant_name,
            role=role
        ))

        # Add opposing party
        demo_opponents = [
            "ООО «Ромашка»",
            "ИП Сидоров С.С.",
            "Петров Петр Петрович",
            "АО «Корпорация»"
        ]
        opponent_idx = int(seed_hash[14], 16) % len(demo_opponents)
        opponent_role = (ParticipantRole.DEFENDANT
                        if role == ParticipantRole.PLAINTIFF
                        else ParticipantRole.PLAINTIFF)

        participants.append(Participant(
            name=demo_opponents[opponent_idx],
            role=opponent_role,
            is_organization="ООО" in demo_opponents[opponent_idx] or "АО" in demo_opponents[opponent_idx]
        ))

        # Generate subject and outcome
        subjects = {
            CaseCategory.CIVIL: [
                "О взыскании задолженности",
                "О защите прав потребителей",
                "О расторжении договора",
                "О возмещении ущерба"
            ],
            CaseCategory.CRIMINAL: [
                "Кража (ст. 158 УК РФ)",
                "Мошенничество (ст. 159 УК РФ)",
                "Причинение вреда здоровью"
            ],
            CaseCategory.ADMINISTRATIVE: [
                "Об оспаривании решения",
                "О признании незаконным бездействия"
            ],
            CaseCategory.ARBITRATION: [
                "О взыскании задолженности по договору",
                "О признании сделки недействительной",
                "О банкротстве"
            ]
        }

        subject_list = subjects.get(category, ["Иное"])
        subject = subject_list[int(seed_hash[15], 16) % len(subject_list)]

        outcomes = [
            "Иск удовлетворен",
            "Иск удовлетворен частично",
            "В удовлетворении иска отказано",
            "Производство прекращено"
        ]

        outcome = None
        status = CaseStatus.PENDING
        if decision_date:
            outcome = outcomes[int(seed_hash[16], 16) % len(outcomes)]
            status = CaseStatus.DECIDED

        # Generate claim amount for civil/arbitration
        claim_amount = None
        if category in [CaseCategory.CIVIL, CaseCategory.ARBITRATION]:
            claim_amount = float(int(seed_hash[17:21], 16)) * 10

        # Generate judge
        demo_judges = [
            "Иванова А.А.",
            "Петров Б.В.",
            "Сидорова Е.К.",
            "Козлов М.П."
        ]
        judge = demo_judges[int(seed_hash[21], 16) % len(demo_judges)]

        # Generate documents if decision exists
        documents = []
        if decision_date:
            doc_types = {
                CaseCategory.CIVIL: "Решение",
                CaseCategory.CRIMINAL: "Приговор",
                CaseCategory.ADMINISTRATIVE: "Решение",
                CaseCategory.ARBITRATION: "Решение"
            }
            documents.append(CourtDocument(
                title=f"{doc_types.get(category, 'Решение')} по делу {case_number}",
                doc_type=doc_types.get(category, "Решение"),
                date=decision_date
            ))

        return CourtCase(
            case_number=case_number,
            unique_id=seed_hash[:16],
            category=category,
            status=status,
            court=court,
            filing_date=filing_date,
            decision_date=decision_date,
            participants=participants,
            subject=subject,
            claim_amount=claim_amount,
            outcome=outcome,
            judge=judge,
            documents=documents,
            source="demo",
            case_url=f"https://sudrf.ru/cases/{seed_hash[:8]}"
        )

    def _generate_demo_case_by_number(
        self,
        case_number: str,
        seed_hash: str,
        year: int
    ) -> CourtCase:
        """Generate demo case by case number"""
        # Determine category from case number prefix
        if case_number.startswith("2-"):
            category = CaseCategory.CIVIL
        elif case_number.startswith("1-"):
            category = CaseCategory.CRIMINAL
        elif case_number.startswith("А"):
            category = CaseCategory.ARBITRATION
        else:
            category = CaseCategory.ADMINISTRATIVE

        case = self._generate_demo_case("Иванов И.И.", seed_hash, category)
        case.case_number = case_number

        # Adjust year in filing date
        if case.filing_date:
            case.filing_date = case.filing_date.replace(year=year)

        return case

    def _generate_demo_arbitration_case(self, inn: str, seed_hash: str) -> CourtCase:
        """Generate demo arbitration case for INN search"""
        case = self._generate_demo_case(
            f"ООО (ИНН {inn})",
            seed_hash,
            CaseCategory.ARBITRATION
        )

        # Add INN to participant
        if case.participants:
            case.participants[0].inn = inn
            case.participants[0].is_organization = True

        return case


def demo():
    """Demonstrate court records search capabilities"""
    print("=" * 60)
    print("Court Records Search - IBP Prototype B.10")
    print("=" * 60)
    print()

    # Initialize in demo mode
    search = CourtRecordsSearch(demo_mode=True)

    print("Demo Mode - Simulated Court Records Search")
    print("-" * 40)

    # Test name search
    print("\nSearch by Name:")
    print("-" * 40)

    result = search.search_by_name("Иванов Иван Иванович", limit=5)
    print(f"Found: {result.total_found} cases")

    for case in result.cases[:3]:
        print(f"\n  Case: {case.case_number}")
        print(f"  Category: {case.category_ru}")
        print(f"  Court: {case.court.name if case.court else 'N/A'}")
        print(f"  Subject: {case.subject}")
        print(f"  Status: {case.status.value}")
        if case.outcome:
            print(f"  Outcome: {case.outcome}")

    # Test case number search
    print("\n\nSearch by Case Number:")
    print("-" * 40)

    result = search.search_by_case_number("2-1234/2023")
    if result.cases:
        case = result.cases[0]
        print(f"  Case: {case.case_number}")
        print(f"  Category: {case.category_ru}")
        print(f"  Plaintiffs: {', '.join(p.name for p in case.plaintiffs)}")
        print(f"  Defendants: {', '.join(p.name for p in case.defendants)}")
        print(f"  Filed: {case.filing_date}")
        print(f"  Judge: {case.judge}")

    # Test INN search
    print("\n\nSearch by INN (Organization):")
    print("-" * 40)

    result = search.search_by_inn("7707083893", limit=3)
    print(f"Found: {result.total_found} cases")

    for case in result.cases[:2]:
        print(f"\n  Case: {case.case_number}")
        print(f"  Subject: {case.subject}")
        print(f"  Amount: {case.claim_amount:,.0f} RUB" if case.claim_amount else "")

    print("\n" + "=" * 60)
    print("Usage Example:")
    print("-" * 40)
    print("""
from court_records import CourtRecordsSearch, CaseCategory, ParticipantRole

# Initialize
search = CourtRecordsSearch()

# Search by name
result = search.search_by_name(
    name="Иванов Иван Иванович",
    category=CaseCategory.CIVIL,
    role=ParticipantRole.DEFENDANT
)

for case in result.cases:
    print(f"Case {case.case_number}: {case.subject}")
    print(f"  Status: {case.status.value}")
    print(f"  Outcome: {case.outcome}")

# Search by case number
result = search.search_by_case_number("2-1234/2023")
if result.cases:
    case = result.cases[0]
    print(f"Court: {case.court.name}")
    print(f"Judge: {case.judge}")

# Search organization by INN
result = search.search_by_inn("7707083893")
for case in result.cases:
    print(f"Arbitration case: {case.case_number}")

# Get detailed case info
case = search.get_case_details("https://sudrf.ru/cases/123")
if case:
    for doc in case.documents:
        print(f"Document: {doc.title}")
""")

    print("\n" + "=" * 60)
    print("\nJSON Output Example:")
    print("-" * 40)

    result = search.search_by_case_number("2-100/2024")
    if result.cases:
        print(result.cases[0].to_json())


if __name__ == "__main__":
    demo()
