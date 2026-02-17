"""
Candidate Check Model
=====================
Stores background check data for the "Проверка кандидата" module.
"""

from datetime import datetime
from app import db
import json


class CandidateCheck(db.Model):
    """
    Background check record.

    Stores input identifiers, results from each source,
    red flags, and overall risk assessment.
    """
    __tablename__ = 'candidate_checks'

    id = db.Column(db.String(36), primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    status = db.Column(db.String(20), default='pending')  # pending/running/complete/error

    # Input
    full_name = db.Column(db.String(255), nullable=False)
    date_of_birth = db.Column(db.Date, nullable=False)
    inn = db.Column(db.String(12))
    passport_series = db.Column(db.String(4))
    passport_number = db.Column(db.String(6))
    registered_address = db.Column(db.Text)
    region = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    email = db.Column(db.String(255))

    # Results (JSON)
    _business_records = db.Column('business_records', db.Text, default='[]')
    _court_records = db.Column('court_records', db.Text, default='[]')
    _fssp_records = db.Column('fssp_records', db.Text, default='[]')
    _bankruptcy_records = db.Column('bankruptcy_records', db.Text, default='[]')
    _sanctions_results = db.Column('sanctions_results', db.Text, default='{}')
    _social_media_profiles = db.Column('social_media_profiles', db.Text, default='[]')
    _contact_discoveries = db.Column('contact_discoveries', db.Text, default='{}')

    # Risk
    risk_level = db.Column(db.String(20))  # low/medium/high/critical
    _red_flags = db.Column('red_flags', db.Text, default='[]')
    red_flag_count = db.Column(db.Integer, default=0)

    # Meta
    sources_checked = db.Column(db.Integer, default=0)
    sources_with_results = db.Column(db.Integer, default=0)
    check_duration_seconds = db.Column(db.Float)

    # --- JSON property helpers ---

    @staticmethod
    def _load_json(raw, default):
        try:
            return json.loads(raw) if raw else default
        except (json.JSONDecodeError, TypeError):
            return default

    @staticmethod
    def _dump_json(value):
        return json.dumps(value, ensure_ascii=False, default=str)

    # business_records
    @property
    def business_records(self):
        return self._load_json(self._business_records, [])

    @business_records.setter
    def business_records(self, value):
        self._business_records = self._dump_json(value)

    # court_records
    @property
    def court_records(self):
        return self._load_json(self._court_records, [])

    @court_records.setter
    def court_records(self, value):
        self._court_records = self._dump_json(value)

    # fssp_records
    @property
    def fssp_records(self):
        return self._load_json(self._fssp_records, [])

    @fssp_records.setter
    def fssp_records(self, value):
        self._fssp_records = self._dump_json(value)

    # bankruptcy_records
    @property
    def bankruptcy_records(self):
        return self._load_json(self._bankruptcy_records, [])

    @bankruptcy_records.setter
    def bankruptcy_records(self, value):
        self._bankruptcy_records = self._dump_json(value)

    # sanctions_results
    @property
    def sanctions_results(self):
        return self._load_json(self._sanctions_results, {})

    @sanctions_results.setter
    def sanctions_results(self, value):
        self._sanctions_results = self._dump_json(value)

    # social_media_profiles
    @property
    def social_media_profiles(self):
        return self._load_json(self._social_media_profiles, [])

    @social_media_profiles.setter
    def social_media_profiles(self, value):
        self._social_media_profiles = self._dump_json(value)

    # contact_discoveries
    @property
    def contact_discoveries(self):
        return self._load_json(self._contact_discoveries, {})

    @contact_discoveries.setter
    def contact_discoveries(self, value):
        self._contact_discoveries = self._dump_json(value)

    # red_flags
    @property
    def red_flags(self):
        return self._load_json(self._red_flags, [])

    @red_flags.setter
    def red_flags(self, value):
        self._red_flags = self._dump_json(value)

    # --- Computed properties ---

    @property
    def check_level(self):
        """Quality level based on fields provided."""
        if self.inn and self.passport_series and self.registered_address:
            return 'full'
        elif self.inn:
            return 'extended'
        return 'basic'

    @property
    def check_level_display(self):
        return {
            'full': 'Полная проверка',
            'extended': 'Расширенная проверка',
            'basic': 'Базовая проверка',
        }.get(self.check_level, 'Базовая проверка')

    @property
    def risk_level_display(self):
        return {
            'low': 'НИЗКИЙ РИСК',
            'medium': 'СРЕДНИЙ РИСК',
            'high': 'ВЫСОКИЙ РИСК',
            'critical': 'КРИТИЧЕСКИЙ РИСК',
        }.get(self.risk_level, '')

    @property
    def name_parts(self):
        """Split full_name into last, first, patronymic."""
        parts = self.full_name.strip().split()
        return {
            'last': parts[0] if len(parts) > 0 else '',
            'first': parts[1] if len(parts) > 1 else '',
            'patronymic': parts[2] if len(parts) > 2 else '',
        }

    def to_dict(self):
        return {
            'id': self.id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'status': self.status,
            'full_name': self.full_name,
            'date_of_birth': self.date_of_birth.isoformat() if self.date_of_birth else None,
            'inn': self.inn,
            'region': self.region,
            'risk_level': self.risk_level,
            'risk_level_display': self.risk_level_display,
            'red_flag_count': self.red_flag_count,
            'check_level': self.check_level,
            'check_level_display': self.check_level_display,
            'sources_checked': self.sources_checked,
            'sources_with_results': self.sources_with_results,
            'check_duration_seconds': self.check_duration_seconds,
        }

    def __repr__(self):
        return f'<CandidateCheck {self.id[:8]}: {self.full_name}>'
