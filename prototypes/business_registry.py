"""
Business Registry Search - IBP Prototype B.9
Search Russian business registries (EGRUL/EGRIP)

Features:
- Search companies by name, INN, OGRN
- Search individual entrepreneurs (IP) by name, INN, OGRNIP
- Extract company details (address, director, founding date)
- Multiple data sources (nalog.ru, egrul.ru, etc.)
- Pagination support
- INN/OGRN validation

Requirements:
    pip install requests beautifulsoup4

Usage:
    registry = BusinessRegistry()
    results = registry.search_company(name="Газпром")
    for company in results:
        print(f"{company.name} - INN: {company.inn}")
"""

import os
import re
import json
import time
import logging
import hashlib
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple, Generator
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


class EntityType(Enum):
    """Business entity types"""
    COMPANY = "company"  # Юридическое лицо (ООО, АО, ПАО, etc.)
    INDIVIDUAL = "individual"  # ИП (Индивидуальный предприниматель)
    UNKNOWN = "unknown"


class CompanyStatus(Enum):
    """Company registration status"""
    ACTIVE = "active"  # Действующее
    LIQUIDATING = "liquidating"  # В процессе ликвидации
    LIQUIDATED = "liquidated"  # Ликвидировано
    REORGANIZING = "reorganizing"  # В процессе реорганизации
    BANKRUPT = "bankrupt"  # Банкрот
    UNKNOWN = "unknown"


@dataclass
class Address:
    """Legal address"""
    full_address: str
    region: Optional[str] = None
    city: Optional[str] = None
    street: Optional[str] = None
    building: Optional[str] = None
    postal_code: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "full_address": self.full_address,
            "region": self.region,
            "city": self.city,
            "street": self.street,
            "building": self.building,
            "postal_code": self.postal_code
        }


@dataclass
class Person:
    """Director/founder information"""
    full_name: str
    position: Optional[str] = None
    inn: Optional[str] = None
    share_percent: Optional[float] = None
    share_amount: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "full_name": self.full_name,
            "position": self.position,
            "inn": self.inn,
            "share_percent": self.share_percent,
            "share_amount": self.share_amount
        }


@dataclass
class OKVEDCode:
    """OKVED activity code"""
    code: str
    description: str
    is_primary: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "description": self.description,
            "is_primary": self.is_primary
        }


@dataclass
class BusinessEntity:
    """Russian business entity (company or IP)"""
    # Identifiers
    inn: str  # ИНН (10 digits for companies, 12 for IP)
    ogrn: Optional[str] = None  # ОГРН (13 digits) or ОГРНИП (15 digits)
    kpp: Optional[str] = None  # КПП (9 digits, companies only)

    # Basic info
    name: str = ""
    short_name: Optional[str] = None
    full_name: Optional[str] = None
    entity_type: EntityType = EntityType.UNKNOWN
    legal_form: Optional[str] = None  # ООО, АО, ИП, etc.

    # Status
    status: CompanyStatus = CompanyStatus.UNKNOWN
    status_text: Optional[str] = None

    # Dates
    registration_date: Optional[date] = None
    liquidation_date: Optional[date] = None

    # Address
    address: Optional[Address] = None

    # Capital
    authorized_capital: Optional[float] = None
    capital_currency: str = "RUB"

    # People
    director: Optional[Person] = None
    founders: List[Person] = field(default_factory=list)

    # Activities
    okved_codes: List[OKVEDCode] = field(default_factory=list)
    primary_activity: Optional[str] = None

    # Tax info
    tax_authority: Optional[str] = None
    tax_authority_code: Optional[str] = None

    # Additional
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None

    # Source
    source: str = "unknown"
    source_url: Optional[str] = None

    # Raw data
    raw_data: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_company(self) -> bool:
        return self.entity_type == EntityType.COMPANY

    @property
    def is_individual(self) -> bool:
        return self.entity_type == EntityType.INDIVIDUAL

    @property
    def is_active(self) -> bool:
        return self.status == CompanyStatus.ACTIVE

    @property
    def primary_okved(self) -> Optional[OKVEDCode]:
        for code in self.okved_codes:
            if code.is_primary:
                return code
        return self.okved_codes[0] if self.okved_codes else None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "inn": self.inn,
            "ogrn": self.ogrn,
            "kpp": self.kpp,
            "name": self.name,
            "short_name": self.short_name,
            "full_name": self.full_name,
            "entity_type": self.entity_type.value,
            "legal_form": self.legal_form,
            "status": self.status.value,
            "status_text": self.status_text,
            "registration_date": self.registration_date.isoformat() if self.registration_date else None,
            "liquidation_date": self.liquidation_date.isoformat() if self.liquidation_date else None,
            "address": self.address.to_dict() if self.address else None,
            "authorized_capital": self.authorized_capital,
            "director": self.director.to_dict() if self.director else None,
            "founders": [f.to_dict() for f in self.founders],
            "okved_codes": [c.to_dict() for c in self.okved_codes],
            "primary_activity": self.primary_activity,
            "tax_authority": self.tax_authority,
            "phone": self.phone,
            "email": self.email,
            "website": self.website,
            "source": self.source,
            "source_url": self.source_url
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)


@dataclass
class SearchResult:
    """Business registry search results"""
    query: str
    query_type: str  # name, inn, ogrn
    total_found: int
    entities: List[BusinessEntity] = field(default_factory=list)
    page: int = 1
    has_more: bool = False
    search_time_ms: float = 0.0
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "query_type": self.query_type,
            "total_found": self.total_found,
            "returned": len(self.entities),
            "page": self.page,
            "has_more": self.has_more,
            "search_time_ms": round(self.search_time_ms, 2),
            "entities": [e.to_dict() for e in self.entities],
            "error": self.error
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)


class INNValidator:
    """Russian INN (tax identification number) validator"""

    @staticmethod
    def validate(inn: str) -> Tuple[bool, str]:
        """
        Validate INN

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Clean input
        inn = re.sub(r'\D', '', inn)

        if len(inn) == 10:
            # Company INN (10 digits)
            return INNValidator._validate_company_inn(inn)
        elif len(inn) == 12:
            # Individual INN (12 digits)
            return INNValidator._validate_individual_inn(inn)
        else:
            return False, f"Invalid length: {len(inn)} (expected 10 or 12)"

    @staticmethod
    def _validate_company_inn(inn: str) -> Tuple[bool, str]:
        """Validate 10-digit company INN"""
        weights = [2, 4, 10, 3, 5, 9, 4, 6, 8]

        checksum = sum(int(inn[i]) * weights[i] for i in range(9)) % 11 % 10

        if checksum == int(inn[9]):
            return True, ""
        return False, "Invalid checksum"

    @staticmethod
    def _validate_individual_inn(inn: str) -> Tuple[bool, str]:
        """Validate 12-digit individual INN"""
        weights1 = [7, 2, 4, 10, 3, 5, 9, 4, 6, 8]
        weights2 = [3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8]

        checksum1 = sum(int(inn[i]) * weights1[i] for i in range(10)) % 11 % 10
        checksum2 = sum(int(inn[i]) * weights2[i] for i in range(11)) % 11 % 10

        if checksum1 == int(inn[10]) and checksum2 == int(inn[11]):
            return True, ""
        return False, "Invalid checksum"

    @staticmethod
    def get_type(inn: str) -> EntityType:
        """Determine entity type from INN"""
        inn = re.sub(r'\D', '', inn)
        if len(inn) == 10:
            return EntityType.COMPANY
        elif len(inn) == 12:
            return EntityType.INDIVIDUAL
        return EntityType.UNKNOWN


class OGRNValidator:
    """Russian OGRN (registration number) validator"""

    @staticmethod
    def validate(ogrn: str) -> Tuple[bool, str]:
        """Validate OGRN/OGRNIP"""
        ogrn = re.sub(r'\D', '', ogrn)

        if len(ogrn) == 13:
            # Company OGRN
            return OGRNValidator._validate_ogrn(ogrn)
        elif len(ogrn) == 15:
            # Individual OGRNIP
            return OGRNValidator._validate_ogrnip(ogrn)
        else:
            return False, f"Invalid length: {len(ogrn)} (expected 13 or 15)"

    @staticmethod
    def _validate_ogrn(ogrn: str) -> Tuple[bool, str]:
        """Validate 13-digit OGRN"""
        number = int(ogrn[:12])
        checksum = number % 11 % 10

        if checksum == int(ogrn[12]):
            return True, ""
        return False, "Invalid checksum"

    @staticmethod
    def _validate_ogrnip(ogrn: str) -> Tuple[bool, str]:
        """Validate 15-digit OGRNIP"""
        number = int(ogrn[:14])
        checksum = number % 13 % 10

        if checksum == int(ogrn[14]):
            return True, ""
        return False, "Invalid checksum"


class BusinessRegistry:
    """
    Russian business registry search service

    Searches EGRUL (companies) and EGRIP (individual entrepreneurs)
    data from multiple sources.
    """

    # Data source URLs
    NALOG_URL = "https://egrul.nalog.ru"
    EGRUL_URL = "https://egrul.ru"

    # Rate limiting
    MIN_REQUEST_INTERVAL = 1.0

    def __init__(
        self,
        demo_mode: bool = False
    ):
        """
        Initialize registry search

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
                "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8"
            })

        if self.demo_mode:
            logger.info("Running in DEMO mode")

    def _rate_limit(self):
        """Apply rate limiting"""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.MIN_REQUEST_INTERVAL:
            time.sleep(self.MIN_REQUEST_INTERVAL - elapsed)
        self._last_request_time = time.time()

    def validate_inn(self, inn: str) -> Tuple[bool, str]:
        """Validate INN format and checksum"""
        return INNValidator.validate(inn)

    def validate_ogrn(self, ogrn: str) -> Tuple[bool, str]:
        """Validate OGRN/OGRNIP format and checksum"""
        return OGRNValidator.validate(ogrn)

    def search_by_inn(self, inn: str) -> SearchResult:
        """
        Search by INN

        Args:
            inn: 10 or 12 digit INN

        Returns:
            SearchResult with found entity
        """
        start_time = time.time()
        inn = re.sub(r'\D', '', inn)

        # Validate
        is_valid, error = self.validate_inn(inn)
        if not is_valid:
            return SearchResult(
                query=inn,
                query_type="inn",
                total_found=0,
                error=f"Invalid INN: {error}",
                search_time_ms=(time.time() - start_time) * 1000
            )

        if self.demo_mode:
            return self._demo_search_inn(inn)

        self._rate_limit()

        # Try nalog.ru API
        try:
            return self._search_nalog_inn(inn)
        except Exception as e:
            logger.error(f"nalog.ru search failed: {e}")
            return SearchResult(
                query=inn,
                query_type="inn",
                total_found=0,
                error=str(e),
                search_time_ms=(time.time() - start_time) * 1000
            )

    def search_by_ogrn(self, ogrn: str) -> SearchResult:
        """
        Search by OGRN/OGRNIP

        Args:
            ogrn: 13 or 15 digit OGRN

        Returns:
            SearchResult with found entity
        """
        start_time = time.time()
        ogrn = re.sub(r'\D', '', ogrn)

        # Validate
        is_valid, error = self.validate_ogrn(ogrn)
        if not is_valid:
            return SearchResult(
                query=ogrn,
                query_type="ogrn",
                total_found=0,
                error=f"Invalid OGRN: {error}",
                search_time_ms=(time.time() - start_time) * 1000
            )

        if self.demo_mode:
            return self._demo_search_ogrn(ogrn)

        self._rate_limit()

        try:
            return self._search_nalog_ogrn(ogrn)
        except Exception as e:
            return SearchResult(
                query=ogrn,
                query_type="ogrn",
                total_found=0,
                error=str(e),
                search_time_ms=(time.time() - start_time) * 1000
            )

    def search_by_name(
        self,
        name: str,
        region: Optional[str] = None,
        page: int = 1,
        limit: int = 20
    ) -> SearchResult:
        """
        Search by company/IP name

        Args:
            name: Company or person name
            region: Region filter (region code or name)
            page: Page number
            limit: Results per page

        Returns:
            SearchResult with matching entities
        """
        start_time = time.time()

        if self.demo_mode:
            return self._demo_search_name(name, region, page, limit)

        self._rate_limit()

        try:
            return self._search_nalog_name(name, region, page, limit)
        except Exception as e:
            return SearchResult(
                query=name,
                query_type="name",
                total_found=0,
                error=str(e),
                search_time_ms=(time.time() - start_time) * 1000
            )

    def search_by_director(
        self,
        name: str,
        region: Optional[str] = None
    ) -> SearchResult:
        """
        Search companies by director name

        Args:
            name: Director's full name
            region: Region filter

        Returns:
            SearchResult with companies where person is director
        """
        # In demo mode, simulate search
        if self.demo_mode:
            return self._demo_search_director(name)

        # In real implementation, would use specialized API or scraping
        return SearchResult(
            query=name,
            query_type="director",
            total_found=0,
            error="Director search requires authenticated API access"
        )

    def get_entity(self, inn: str) -> Optional[BusinessEntity]:
        """
        Get full entity details by INN

        Args:
            inn: Entity INN

        Returns:
            BusinessEntity with full details
        """
        result = self.search_by_inn(inn)
        if result.entities:
            return result.entities[0]
        return None

    def _search_nalog_inn(self, inn: str) -> SearchResult:
        """Search nalog.ru by INN"""
        # nalog.ru requires specific flow with token
        # This is a simplified implementation

        url = f"{self.NALOG_URL}/api/search"
        params = {"query": inn}

        response = self.session.get(url, params=params, timeout=30)

        # Parse response (implementation depends on actual API response format)
        # This is a placeholder for actual parsing logic

        return SearchResult(
            query=inn,
            query_type="inn",
            total_found=0,
            error="nalog.ru API requires session token"
        )

    def _search_nalog_ogrn(self, ogrn: str) -> SearchResult:
        """Search nalog.ru by OGRN"""
        return SearchResult(
            query=ogrn,
            query_type="ogrn",
            total_found=0,
            error="nalog.ru API requires session token"
        )

    def _search_nalog_name(
        self,
        name: str,
        region: Optional[str],
        page: int,
        limit: int
    ) -> SearchResult:
        """Search nalog.ru by name"""
        return SearchResult(
            query=name,
            query_type="name",
            total_found=0,
            error="nalog.ru API requires session token"
        )

    # Demo mode implementations
    def _demo_search_inn(self, inn: str) -> SearchResult:
        """Simulated INN search"""
        time.sleep(0.1)

        inn_hash = hashlib.md5(inn.encode()).hexdigest()
        entity_type = INNValidator.get_type(inn)

        # Generate demo data
        if entity_type == EntityType.COMPANY:
            entity = self._generate_demo_company(inn, inn_hash)
        else:
            entity = self._generate_demo_ip(inn, inn_hash)

        return SearchResult(
            query=inn,
            query_type="inn",
            total_found=1,
            entities=[entity],
            search_time_ms=100.0
        )

    def _demo_search_ogrn(self, ogrn: str) -> SearchResult:
        """Simulated OGRN search"""
        time.sleep(0.1)

        ogrn_hash = hashlib.md5(ogrn.encode()).hexdigest()

        # Generate matching INN
        if len(ogrn) == 13:
            inn = ogrn_hash[:10]
            entity = self._generate_demo_company(inn, ogrn_hash)
        else:
            inn = ogrn_hash[:12]
            entity = self._generate_demo_ip(inn, ogrn_hash)

        entity.ogrn = ogrn

        return SearchResult(
            query=ogrn,
            query_type="ogrn",
            total_found=1,
            entities=[entity],
            search_time_ms=100.0
        )

    def _demo_search_name(
        self,
        name: str,
        region: Optional[str],
        page: int,
        limit: int
    ) -> SearchResult:
        """Simulated name search"""
        time.sleep(0.1)

        name_hash = hashlib.md5(name.encode()).hexdigest()
        total = int(name_hash[:2], 16) % 50 + 1  # 1-50 results

        entities = []
        start_idx = (page - 1) * limit

        demo_prefixes = ["ООО", "АО", "ПАО", "ЗАО", "ИП"]
        demo_suffixes = ["", "Трейд", "Групп", "Сервис", "Плюс", "Про"]

        for i in range(min(limit, total - start_idx)):
            idx = start_idx + i
            entity_hash = hashlib.md5(f"{name}_{idx}".encode()).hexdigest()

            # Generate varied company names
            prefix = demo_prefixes[int(entity_hash[0], 16) % len(demo_prefixes)]
            suffix = demo_suffixes[int(entity_hash[1], 16) % len(demo_suffixes)]
            company_name = f'{prefix} "{name}{suffix}"'

            if prefix == "ИП":
                inn = entity_hash[:12]
                entity = self._generate_demo_ip(inn, entity_hash)
                entity.name = f"ИП {name}"
            else:
                inn = entity_hash[:10]
                entity = self._generate_demo_company(inn, entity_hash)
                entity.name = company_name
                entity.short_name = f"{name}{suffix}"

            # Apply region filter
            if region:
                entity.address = Address(
                    full_address=f"{region}, ул. Примерная, д. {idx + 1}",
                    region=region,
                    city=region
                )

            entities.append(entity)

        return SearchResult(
            query=name,
            query_type="name",
            total_found=total,
            entities=entities,
            page=page,
            has_more=page * limit < total,
            search_time_ms=100.0
        )

    def _demo_search_director(self, name: str) -> SearchResult:
        """Simulated director search"""
        time.sleep(0.1)

        name_hash = hashlib.md5(name.encode()).hexdigest()
        count = int(name_hash[0], 16) % 5  # 0-4 companies

        entities = []
        for i in range(count):
            entity_hash = hashlib.md5(f"{name}_{i}".encode()).hexdigest()
            inn = entity_hash[:10]
            entity = self._generate_demo_company(inn, entity_hash)
            entity.director = Person(
                full_name=name,
                position="Генеральный директор"
            )
            entities.append(entity)

        return SearchResult(
            query=name,
            query_type="director",
            total_found=count,
            entities=entities,
            search_time_ms=100.0
        )

    def _generate_demo_company(self, inn: str, seed_hash: str) -> BusinessEntity:
        """Generate demo company data"""
        demo_names = [
            "Технологии будущего",
            "ИнвестКапитал",
            "СтройМастер",
            "ТоргСервис",
            "МедиаГрупп"
        ]

        demo_directors = [
            "Иванов Иван Иванович",
            "Петров Петр Петрович",
            "Сидорова Мария Сергеевна",
            "Козлов Алексей Владимирович"
        ]

        demo_cities = ["Москва", "Санкт-Петербург", "Казань", "Новосибирск", "Екатеринбург"]

        name_idx = int(seed_hash[2], 16) % len(demo_names)
        director_idx = int(seed_hash[3], 16) % len(demo_directors)
        city_idx = int(seed_hash[4], 16) % len(demo_cities)

        legal_forms = ["ООО", "АО", "ПАО"]
        legal_form = legal_forms[int(seed_hash[5], 16) % len(legal_forms)]

        company_name = demo_names[name_idx]

        # Generate OGRN
        ogrn_base = seed_hash[:12]
        ogrn_check = str(int(ogrn_base) % 11 % 10)
        ogrn = ogrn_base + ogrn_check

        # Registration date
        year = 2000 + int(seed_hash[6:8], 16) % 24
        month = int(seed_hash[8:10], 16) % 12 + 1
        day = int(seed_hash[10:12], 16) % 28 + 1
        reg_date = date(year, month, day)

        return BusinessEntity(
            inn=inn,
            ogrn=ogrn,
            kpp=seed_hash[:9],
            name=f'{legal_form} "{company_name}"',
            short_name=company_name,
            full_name=f'{legal_form} "{company_name}"',
            entity_type=EntityType.COMPANY,
            legal_form=legal_form,
            status=CompanyStatus.ACTIVE if int(seed_hash[0], 16) > 2 else CompanyStatus.LIQUIDATED,
            registration_date=reg_date,
            address=Address(
                full_address=f"г. {demo_cities[city_idx]}, ул. Примерная, д. {int(seed_hash[12:14], 16) % 100}",
                region=demo_cities[city_idx],
                city=demo_cities[city_idx]
            ),
            authorized_capital=float(int(seed_hash[14:18], 16)) * 100,
            director=Person(
                full_name=demo_directors[director_idx],
                position="Генеральный директор"
            ),
            okved_codes=[
                OKVEDCode(
                    code=f"{int(seed_hash[18:20], 16) % 99}.{int(seed_hash[20:22], 16) % 99}",
                    description="Основная деятельность",
                    is_primary=True
                )
            ],
            source="demo",
            source_url=f"https://egrul.nalog.ru/{inn}"
        )

    def _generate_demo_ip(self, inn: str, seed_hash: str) -> BusinessEntity:
        """Generate demo individual entrepreneur data"""
        demo_names = [
            "Иванов Иван Иванович",
            "Петрова Мария Сергеевна",
            "Сидоров Алексей Владимирович",
            "Козлова Елена Петровна"
        ]

        demo_cities = ["Москва", "Санкт-Петербург", "Казань", "Новосибирск"]

        name_idx = int(seed_hash[2], 16) % len(demo_names)
        city_idx = int(seed_hash[4], 16) % len(demo_cities)

        # Generate OGRNIP (15 digits)
        ogrnip_base = seed_hash[:14]
        ogrnip_check = str(int(ogrnip_base) % 13 % 10)
        ogrnip = ogrnip_base + ogrnip_check

        year = 2005 + int(seed_hash[6:8], 16) % 19
        month = int(seed_hash[8:10], 16) % 12 + 1
        day = int(seed_hash[10:12], 16) % 28 + 1
        reg_date = date(year, month, day)

        return BusinessEntity(
            inn=inn,
            ogrn=ogrnip,
            name=f"ИП {demo_names[name_idx]}",
            full_name=f"Индивидуальный предприниматель {demo_names[name_idx]}",
            entity_type=EntityType.INDIVIDUAL,
            legal_form="ИП",
            status=CompanyStatus.ACTIVE,
            registration_date=reg_date,
            address=Address(
                full_address=f"г. {demo_cities[city_idx]}",
                region=demo_cities[city_idx],
                city=demo_cities[city_idx]
            ),
            okved_codes=[
                OKVEDCode(
                    code=f"{int(seed_hash[18:20], 16) % 99}.{int(seed_hash[20:22], 16) % 99}",
                    description="Розничная торговля",
                    is_primary=True
                )
            ],
            source="demo"
        )


def demo():
    """Demonstrate business registry capabilities"""
    print("=" * 60)
    print("Business Registry Search - IBP Prototype B.9")
    print("=" * 60)
    print()

    # Initialize in demo mode
    registry = BusinessRegistry(demo_mode=True)

    print("Demo Mode - Simulated Registry Search")
    print("-" * 40)

    # Test INN validation
    print("\nINN Validation:")
    test_inns = ["7707083893", "123456789", "772301001", "771234567890"]
    for inn in test_inns:
        is_valid, error = registry.validate_inn(inn)
        status = "Valid" if is_valid else f"Invalid ({error})"
        print(f"  {inn}: {status}")

    # Test INN search
    print("\n\nSearch by INN:")
    print("-" * 40)

    result = registry.search_by_inn("7707083893")
    if result.entities:
        entity = result.entities[0]
        print(f"  Name: {entity.name}")
        print(f"  INN: {entity.inn}")
        print(f"  OGRN: {entity.ogrn}")
        print(f"  Status: {entity.status.value}")
        print(f"  Director: {entity.director.full_name if entity.director else 'N/A'}")
        print(f"  Address: {entity.address.full_address if entity.address else 'N/A'}")
        print(f"  Capital: {entity.authorized_capital:,.0f} RUB" if entity.authorized_capital else "")

    # Test name search
    print("\n\nSearch by Name:")
    print("-" * 40)

    result = registry.search_by_name("Газпром", limit=5)
    print(f"Found: {result.total_found} results")

    for entity in result.entities[:3]:
        print(f"\n  {entity.name}")
        print(f"    INN: {entity.inn}")
        print(f"    Status: {entity.status.value}")

    # Test director search
    print("\n\nSearch by Director:")
    print("-" * 40)

    result = registry.search_by_director("Иванов Иван Иванович")
    print(f"Found: {result.total_found} companies")

    for entity in result.entities:
        print(f"  - {entity.name} (INN: {entity.inn})")

    print("\n" + "=" * 60)
    print("Usage Example:")
    print("-" * 40)
    print("""
from business_registry import BusinessRegistry

# Initialize
registry = BusinessRegistry()

# Search by INN
result = registry.search_by_inn("7707083893")
if result.entities:
    company = result.entities[0]
    print(f"Company: {company.name}")
    print(f"Director: {company.director.full_name}")

# Validate INN
is_valid, error = registry.validate_inn("1234567890")
if not is_valid:
    print(f"Invalid INN: {error}")

# Search by company name
result = registry.search_by_name("Газпром", region="Москва")
for company in result.entities:
    print(f"{company.name} - {company.inn}")

# Search by director name
result = registry.search_by_director("Иванов Иван Иванович")
for company in result.entities:
    print(f"Director of: {company.name}")

# Get full entity details
entity = registry.get_entity("7707083893")
if entity:
    print(f"OKVED: {entity.primary_okved.description}")
""")

    print("\n" + "=" * 60)
    print("\nJSON Output Example:")
    print("-" * 40)

    result = registry.search_by_inn("7707083893")
    if result.entities:
        print(result.entities[0].to_json())


if __name__ == "__main__":
    demo()
