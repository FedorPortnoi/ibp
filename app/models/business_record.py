"""
Business Record Model
=====================
SQLAlchemy model for storing business/company affiliations.
Data from ЕГРЮЛ, rusprofile.ru, list-org.com.
"""

import logging
from datetime import datetime
from app import db
import json

logger = logging.getLogger(__name__)


class BusinessRecord(db.Model):
    """
    Business/company record from Russian registries.

    Stores company affiliations (director, founder, etc.)
    discovered during Phase 3 deep investigation.
    """
    __tablename__ = 'business_records'

    id = db.Column(db.Integer, primary_key=True)
    investigation_id = db.Column(db.String(36), db.ForeignKey('investigations.id'), nullable=False)

    # Company identification
    inn = db.Column(db.String(12), index=True)  # 10-digit for company, 12-digit for IP
    ogrn = db.Column(db.String(15), index=True)  # 13-digit ОГРН or 15-digit ОГРНИП
    kpp = db.Column(db.String(9))

    # Company info
    company_name = db.Column(db.String(500))
    short_name = db.Column(db.String(255))
    company_type = db.Column(db.String(50))  # ooo, zao, oao, ip (ИП, ООО, ЗАО, ОАО)
    status = db.Column(db.String(50))  # active, liquidated, liquidating, reorganizing

    # Registration dates
    registration_date = db.Column(db.Date)
    liquidation_date = db.Column(db.Date)

    # Address
    legal_address = db.Column(db.String(500))
    region = db.Column(db.String(100))
    city = db.Column(db.String(100))

    # Target's role in company
    person_name = db.Column(db.String(255))  # Full name as in registry
    role = db.Column(db.String(100))  # director, founder, shareholder
    role_start_date = db.Column(db.Date)
    role_end_date = db.Column(db.Date)
    share_percent = db.Column(db.Float)  # For founders/shareholders
    share_amount = db.Column(db.Float)  # In rubles

    # Financial data
    authorized_capital = db.Column(db.Float)  # Уставный капитал
    revenue = db.Column(db.Float)  # Annual revenue if available
    employees_count = db.Column(db.Integer)

    # Activity codes
    main_okved = db.Column(db.String(20))  # Primary ОКВЭД code
    main_okved_name = db.Column(db.String(500))
    _okved_codes = db.Column(db.Text, default='[]')  # JSON array of additional codes

    # Tax info
    tax_authority = db.Column(db.String(255))
    tax_authority_code = db.Column(db.String(10))

    # Source info
    source = db.Column(db.String(100))  # nalog.ru, rusprofile.ru, list-org.com
    source_url = db.Column(db.String(500))

    # Raw data
    _raw_data = db.Column(db.Text, default='{}')

    # Timestamps
    discovered_at = db.Column(db.DateTime, default=datetime.utcnow)
    data_updated_at = db.Column(db.DateTime)  # When registry data was last updated

    # JSON property helpers
    @property
    def okved_codes(self):
        return json.loads(self._okved_codes or '[]')

    @okved_codes.setter
    def okved_codes(self, value):
        self._okved_codes = json.dumps(value, ensure_ascii=False)

    @property
    def raw_data(self):
        return json.loads(self._raw_data or '{}')

    @raw_data.setter
    def raw_data(self, value):
        self._raw_data = json.dumps(value, ensure_ascii=False)

    @property
    def is_active(self):
        return self.status and self.status.lower() in ['active', 'действующая', 'действующее']

    @property
    def role_display(self):
        """Human-readable role name in Russian."""
        roles = {
            'director': 'Директор',
            'founder': 'Учредитель',
            'shareholder': 'Акционер',
            'ceo': 'Генеральный директор',
            'cfo': 'Финансовый директор',
            'Директор': 'Директор',
            'Учредитель': 'Учредитель',
            'Связан': 'Связан',
            'ИП': 'ИП (Предприниматель)',
        }
        return roles.get(self.role, self.role or 'Не указано')

    @property
    def address(self):
        """Alias for legal_address for template compatibility."""
        return self.legal_address

    @property
    def confidence(self):
        """Return confidence level - default medium for DB records."""
        return 'medium'

    def to_dict(self):
        """Convert to dictionary for JSON API responses."""
        return {
            'id': self.id,
            'investigation_id': self.investigation_id,
            'inn': self.inn,
            'ogrn': self.ogrn,
            'kpp': self.kpp,
            'company_name': self.company_name,
            'short_name': self.short_name,
            'company_type': self.company_type,
            'status': self.status,
            'is_active': self.is_active,
            'registration_date': self.registration_date.isoformat() if self.registration_date else None,
            'liquidation_date': self.liquidation_date.isoformat() if self.liquidation_date else None,
            'legal_address': self.legal_address,
            'region': self.region,
            'city': self.city,
            'person_name': self.person_name,
            'role': self.role,
            'role_start_date': self.role_start_date.isoformat() if self.role_start_date else None,
            'role_end_date': self.role_end_date.isoformat() if self.role_end_date else None,
            'share_percent': self.share_percent,
            'share_amount': self.share_amount,
            'authorized_capital': self.authorized_capital,
            'revenue': self.revenue,
            'employees_count': self.employees_count,
            'main_okved': self.main_okved,
            'main_okved_name': self.main_okved_name,
            'okved_codes': self.okved_codes,
            'source': self.source,
            'source_url': self.source_url,
            'discovered_at': self.discovered_at.isoformat() if self.discovered_at else None,
        }

    def to_summary_dict(self):
        """Brief summary for lists."""
        return {
            'id': self.id,
            'company_name': self.company_name or self.short_name,
            'inn': self.inn,
            'role': self.role,
            'status': self.status,
            'is_active': self.is_active,
            'city': self.city,
        }

    @classmethod
    def from_registry_data(cls, data: dict, investigation_id: str):
        """Create BusinessRecord from registry API response."""
        record = cls(
            investigation_id=investigation_id,
            inn=data.get('inn'),
            ogrn=data.get('ogrn'),
            kpp=data.get('kpp'),
            company_name=data.get('name') or data.get('full_name'),
            short_name=data.get('short_name'),
            company_type=data.get('type') or data.get('opf'),
            status=data.get('status'),
            legal_address=data.get('address') or data.get('legal_address'),
            region=data.get('region'),
            city=data.get('city'),
            person_name=data.get('person_name') or data.get('director_name'),
            role=data.get('role'),
            source=data.get('source', 'unknown'),
            source_url=data.get('source_url'),
        )

        # Parse dates
        if data.get('registration_date'):
            try:
                from dateutil.parser import parse
                record.registration_date = parse(data['registration_date']).date()
            except Exception as e:
                logger.warning(f"Error parsing registration_date: {e}")

        # Financial data
        record.authorized_capital = data.get('authorized_capital')
        record.revenue = data.get('revenue')
        record.employees_count = data.get('employees_count')

        # OKVED
        record.main_okved = data.get('main_okved') or data.get('okved')
        record.main_okved_name = data.get('main_okved_name') or data.get('okved_name')
        if data.get('okved_codes'):
            record.okved_codes = data['okved_codes']

        # Raw data
        record.raw_data = data

        return record

    def __repr__(self):
        return f'<BusinessRecord {self.inn}: {self.short_name or self.company_name}>'
